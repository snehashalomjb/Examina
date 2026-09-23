/**
 * Browser-side proctoring engine.
 *
 * Vision runs here, in the candidate's browser, so the server cost of proctoring does
 * not scale with the number of concurrent sittings. The server is still the authority:
 * it re-scores every event it stores and decides when to warn or terminate. Snapshots
 * are uploaded as an audit trail precisely because client-side inference is, by nature,
 * tamperable.
 *
 * What is actually measured:
 *   - face presence and face count, from MediaPipe's face landmarker
 *   - head orientation (a proxy for gaze - this is head pose, not true eye tracking)
 *   - browser behaviour: tab switches, focus loss, fullscreen exit, copy/paste
 *
 * If the vision model cannot load, the engine degrades honestly: behaviour signals keep
 * working, a camera-blocked check keeps working from frame luminance, and it stops
 * claiming to see faces rather than inventing detections.
 */

import { API_BASE, api, flushOnUnload, tokens } from "@/lib/api";
import type { ProctorBatchOut, ProctorConfig, ProctorEventType } from "@/lib/types";

const WASM_PATH = "/mediapipe/wasm";
const MODEL_PATH = "/models/face_landmarker.task";
const OBJECT_MODEL_PATH = "/models/efficientdet_lite0.tflite";

/**
 * MediaPipe's WASM runtime logs its own startup notices - "Created TensorFlow Lite
 * XNNPACK delegate for CPU" and similar glog "INFO:"/"WARNING:" lines - by calling
 * `console.error` directly, not by throwing. Next's dev overlay treats any
 * `console.error` call as a crash and shows it as one, misattributing the stack to
 * whichever MediaPipe call happened to be in flight. Nothing actually failed. This
 * filters exactly those known-benign lines out of `console.error` for the duration of
 * one MediaPipe call, so a real error from the same call still surfaces normally.
 */
const BENIGN_MEDIAPIPE_LOG = /^(INFO|WARNING): |XNNPACK delegate|TensorFlow Lite/i;

async function quietingMediaPipeLogs<T>(fn: () => Promise<T> | T): Promise<T> {
  const originalError = console.error;
  console.error = (...args: unknown[]) => {
    if (typeof args[0] === "string" && BENIGN_MEDIAPIPE_LOG.test(args[0])) return;
    originalError(...args);
  };
  try {
    return await fn();
  } finally {
    console.error = originalError;
  }
}

/** COCO label the EfficientDet-Lite0 model uses for a mobile phone. */
const PHONE_CATEGORY = "cell phone";
const PHONE_SCORE_THRESHOLD = 0.5;
/** Same model's "person" class - a coarser body-in-frame signal, independent of the
 *  face landmarker's face count. Two people can share a frame with only one face
 *  clearly visible (someone leaning in from behind, say), which multiple_faces misses. */
const PERSON_CATEGORY = "person";
const PERSON_SCORE_THRESHOLD = 0.5;
const PERSON_SAMPLES = 6; // ~1.5s

/** Must match WS_SUBPROTOCOL in backend/app/api/v1/proctor.py. */
const WS_SUBPROTOCOL = "exam-proctor.v1";

const SAMPLE_INTERVAL_MS = 250; // ~4 fps is plenty for presence and head pose
const FLUSH_INTERVAL_MS = 10_000;
const MAX_BUFFER = 150;

/** Consecutive bad samples before an event fires - stops a blink or a lean flapping. */
const FACE_MISSING_SAMPLES = 8; // ~2s
const MULTI_FACE_SAMPLES = 4; // ~1s
const GAZE_AWAY_SAMPLES = 12; // ~3s
const DARK_FRAME_SAMPLES = 12;
const PHONE_SAMPLES = 4; // ~1s

export type VisionMode = "landmarks" | "degraded" | "off";

export interface ProctorStatus {
  cameraReady: boolean;
  visionMode: VisionMode;
  faceCount: number;
  facePresent: boolean;
  lookingAway: boolean;
  phoneDetected: boolean;
  suspicionScore: number;
  tabSwitches: number;
  /** Times the candidate left the exam window - tab switch or fullscreen exit. */
  focusViolations: number;
  /** How many more are allowed before the paper is submitted. -1 = ladder is off. */
  focusViolationsLeft: number;
  /** Live: is the document in fullscreen right now? Drives the blocking overlay. */
  inFullscreen: boolean;
  flagged: boolean;
  terminated: boolean;
  /** The exam was submitted for them because the ladder ran out. */
  autoSubmitted: boolean;
  lastError: string | null;
}

interface BufferedEvent {
  event_type: ProctorEventType;
  occurred_at: string;
  severity?: "info" | "warning" | "critical";
  duration_ms?: number;
  confidence?: number;
  question_id?: string;
  metadata?: Record<string, unknown>;
}

export interface ProctorCallbacks {
  onStatus: (status: ProctorStatus) => void;
  onWarnings: (warnings: string[]) => void;
  onTerminated: (reason: string) => void;
  /**
   * The candidate just left the exam window.
   *
   * Fired *before* the event reaches the server, so the runner can persist any
   * debounced answer edits first. That ordering is the whole guarantee behind "answers
   * are saved before automatic submission": by the time the server can decide to
   * submit, the writes are already in flight.
   */
  onFocusViolation?: () => Promise<void> | void;
  /** The paper was submitted for them. Distinct from a termination. */
  onAutoSubmitted?: (reason: string) => void;
  /**
   * Fired the instant a suspicious event is recorded locally, before the next flush.
   * Drives the immediate visual feedback (severity dot, the brief red outline for a
   * high-risk event) - waiting for the server round trip would make it feel laggy.
   */
  onEvent?: (type: ProctorEventType, severity: "info" | "warning" | "critical") => void;
}

interface LandmarkPoint {
  x: number;
  y: number;
  z: number;
}

interface ObjectDetection {
  categories: { categoryName: string; score: number }[];
}

/** Face-mesh landmark indices used for the head-pose estimate. */
const NOSE_TIP = 1;
const EYE_OUTER_RIGHT = 33;
const EYE_OUTER_LEFT = 263;
const SILHOUETTE_RIGHT = 234;
const SILHOUETTE_LEFT = 454;
const FOREHEAD = 10;
const CHIN = 152;

export class ProctorEngine {
  private sessionId: string;
  private config: ProctorConfig;
  private callbacks: ProctorCallbacks;
  private examToken: string;

  private stream: MediaStream | null = null;
  private video: HTMLVideoElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private landmarker: {
    detectForVideo: (video: HTMLVideoElement, timestamp: number) => { faceLandmarks: LandmarkPoint[][] };
    close: () => void;
  } | null = null;
  private objectDetector: {
    detectForVideo: (video: HTMLVideoElement, timestamp: number) => { detections: ObjectDetection[] };
    close: () => void;
  } | null = null;

  private buffer: BufferedEvent[] = [];
  private sampleTimer: number | null = null;
  private flushTimer: number | null = null;
  private snapshotTimer: number | null = null;
  private detachListeners: (() => void)[] = [];
  private stopped = false;

  private socket: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private socketRetries = 0;
  /** Which channel the last flush actually used - surfaced for diagnostics. */
  private transport: "socket" | "http" = "http";

  private missingStreak = 0;
  private multiStreak = 0;
  private awayStreak = 0;
  private darkStreak = 0;
  private phoneStreak = 0;
  private personStreak = 0;
  private hiddenSince: number | null = null;
  private lastSelectionRecordAt = 0;
  private micStream: MediaStream | null = null;

  private status: ProctorStatus = {
    cameraReady: false,
    visionMode: "off",
    faceCount: 0,
    facePresent: false,
    lookingAway: false,
    phoneDetected: false,
    suspicionScore: 0,
    tabSwitches: 0,
    focusViolations: 0,
    focusViolationsLeft: -1,
    inFullscreen: false,
    autoSubmitted: false,
    flagged: false,
    terminated: false,
    lastError: null,
  };

  constructor(options: {
    sessionId: string;
    examToken: string;
    config: ProctorConfig;
    callbacks: ProctorCallbacks;
  }) {
    this.sessionId = options.sessionId;
    this.examToken = options.examToken;
    this.config = options.config;
    this.callbacks = options.callbacks;
  }

  /** The exam token is short-lived and re-issued on every heartbeat. */
  setExamToken(token: string) {
    this.examToken = token;
    // An open socket authenticated with the *old* token stays valid for its lifetime -
    // the handshake is checked once - so there is nothing to reconnect for here. A fresh
    // token only matters for the next handshake and for the HTTP fallback.
  }

  /** Which transport the engine is currently using. Exposed for diagnostics. */
  getTransport(): "socket" | "http" {
    return this.transport;
  }

  /** The raw camera stream, for the live-monitoring broadcaster to attach to a
   * peer connection. Null until the camera has actually started (or if it never did). */
  getMediaStream(): MediaStream | null {
    return this.stream;
  }

  getStatus(): ProctorStatus {
    return { ...this.status };
  }

  private update(patch: Partial<ProctorStatus>) {
    this.status = { ...this.status, ...patch };
    this.callbacks.onStatus(this.getStatus());
  }

  /** Which question was on screen, set by the exam runner as the candidate navigates. */
  private currentQuestionId: string | undefined;

  setCurrentQuestionId(questionId: string | undefined) {
    this.currentQuestionId = questionId;
  }

  private record(
    type: ProctorEventType,
    metadata?: Record<string, unknown>,
    severity?: BufferedEvent["severity"],
    durationMs?: number,
    confidence?: number,
  ) {
    if (this.stopped) return;
    if (this.buffer.length >= MAX_BUFFER) this.buffer.shift();
    this.buffer.push({
      event_type: type,
      occurred_at: new Date().toISOString(),
      severity,
      duration_ms: durationMs,
      confidence,
      question_id: this.currentQuestionId,
      metadata,
    });
    this.callbacks.onEvent?.(type, severity ?? "info");
  }

  // ------------------------------------------------------------------ start
  async start(video: HTMLVideoElement, canvas: HTMLCanvasElement) {
    this.video = video;
    this.canvas = canvas;

    this.attachBehaviourListeners();

    this.flushTimer = window.setInterval(() => void this.flush(), FLUSH_INTERVAL_MS);
    this.connectSocket();

    if (!this.config.webcam_enabled) {
      this.update({ visionMode: "off" });
      return;
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      video.srcObject = this.stream;
      await video.play();
      this.update({ cameraReady: true });
    } catch {
      // A blocked camera is itself a proctoring signal, not just a UI problem.
      this.record("camera_blocked", { reason: "permission_denied_or_unavailable" }, "critical");
      this.update({
        cameraReady: false,
        visionMode: "off",
        lastError: "proctoring:camera_unavailable_warning",
      });
      void this.flush();
      return;
    }

    await this.initVision();

    if (this.config.require_microphone) {
      await this.initMic();
    }

    this.sampleTimer = window.setInterval(() => void this.sample(), SAMPLE_INTERVAL_MS);

    const snapshotEvery = Math.max(15, this.config.snapshot_interval_seconds) * 1000;
    this.snapshotTimer = window.setInterval(() => void this.snapshot(), snapshotEvery);
    // One snapshot up front establishes who actually sat down.
    window.setTimeout(() => void this.snapshot(), 3000);
  }

  private async initVision() {
    try {
      const vision = await import("@mediapipe/tasks-vision");
      const fileset = await quietingMediaPipeLogs(() => vision.FilesetResolver.forVisionTasks(WASM_PATH));
      const landmarker = await quietingMediaPipeLogs(() =>
        vision.FaceLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_PATH, delegate: "GPU" },
          runningMode: "VIDEO",
          numFaces: 3, // enough to notice a second person without paying for a crowd
          outputFaceBlendshapes: false,
          outputFacialTransformationMatrixes: false,
        }),
      );
      this.landmarker = landmarker as unknown as ProctorEngine["landmarker"];
      this.update({ visionMode: "landmarks" });

      // A missing/failed phone model must never take face detection down with it.
      try {
        const objectDetector = await quietingMediaPipeLogs(() =>
          vision.ObjectDetector.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: OBJECT_MODEL_PATH, delegate: "GPU" },
            runningMode: "VIDEO",
            scoreThreshold: PHONE_SCORE_THRESHOLD,
            maxResults: 5,
          }),
        );
        this.objectDetector = objectDetector as unknown as ProctorEngine["objectDetector"];
      } catch (error) {
        console.warn("Phone/object detector unavailable, face detection continues without it", error);
      }
    } catch (error) {
      console.warn("Face landmarker unavailable, degrading to luminance checks", error);
      this.update({
        visionMode: "degraded",
        lastError:
          "proctoring:face_detection_failed_warning",
      });
    }
  }

  /** Only watches for the mic disappearing - no audio content is analysed or sent. */
  private async initMic() {
    try {
      this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.micStream.getAudioTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          this.record("mic_disconnected", { reason: "track_ended" }, "warning");
          void this.flush();
        });
        track.addEventListener("mute", () => {
          this.record("mic_disconnected", { reason: "track_muted" }, "warning");
          void this.flush();
        });
      });
    } catch {
      this.record("mic_disconnected", { reason: "permission_denied_or_unavailable" }, "warning");
      void this.flush();
    }
  }

  // ----------------------------------------------------------------- sample
  private async sample() {
    if (this.stopped || !this.video || this.video.readyState < 2) return;

    if (this.landmarker) {
      this.sampleWithLandmarks();
    } else {
      this.sampleLuminance();
    }
    if (this.objectDetector) {
      this.sampleObjects();
    }
  }

  /** Independent of the face-landmarker path - runs alongside it, on the same frame cadence. */
  private sampleObjects() {
    if (!this.video || !this.objectDetector) return;

    let detections: ObjectDetection[] = [];
    try {
      detections = this.objectDetector.detectForVideo(this.video, performance.now()).detections ?? [];
    } catch {
      return; // a dropped frame is not evidence of anything
    }

    const phoneMatch = detections
      .flatMap((d) => d.categories)
      .find((c) => c.categoryName === PHONE_CATEGORY && c.score >= PHONE_SCORE_THRESHOLD);

    if (phoneMatch) {
      this.phoneStreak += 1;
      if (this.phoneStreak === PHONE_SAMPLES) {
        this.record("phone_detected", { samples: this.phoneStreak }, "critical", undefined, phoneMatch.score);
        void this.snapshot("phone_detected");
      }
    } else {
      this.phoneStreak = 0;
    }

    this.update({ phoneDetected: this.phoneStreak >= PHONE_SAMPLES });

    const personCount = detections.filter((d) =>
      d.categories.some((c) => c.categoryName === PERSON_CATEGORY && c.score >= PERSON_SCORE_THRESHOLD),
    ).length;

    if (personCount > 1) {
      this.personStreak += 1;
      if (this.personStreak === PERSON_SAMPLES) {
        this.record("additional_person", { person_count: personCount }, "critical");
        void this.snapshot("additional_person");
      }
    } else {
      this.personStreak = 0;
    }
  }

  private sampleWithLandmarks() {
    if (!this.video || !this.landmarker) return;

    let faces: LandmarkPoint[][] = [];
    try {
      faces = this.landmarker.detectForVideo(this.video, performance.now()).faceLandmarks ?? [];
    } catch {
      return; // a dropped frame is not evidence of anything
    }

    const faceCount = faces.length;

    // --- nobody in frame -------------------------------------------------
    if (faceCount === 0) {
      this.missingStreak += 1;
      this.multiStreak = 0;
      this.awayStreak = 0;
      if (this.missingStreak === FACE_MISSING_SAMPLES) {
        this.record("face_missing", { samples: this.missingStreak }, "warning");
        void this.snapshot("face_missing");
      }
      this.update({ faceCount: 0, facePresent: false, lookingAway: false });
      return;
    }
    this.missingStreak = 0;

    // --- more than one person -------------------------------------------
    if (faceCount > 1) {
      this.multiStreak += 1;
      if (this.multiStreak === MULTI_FACE_SAMPLES) {
        this.record("multiple_faces", { face_count: faceCount }, "critical");
        void this.snapshot("multiple_faces");
      }
    } else {
      this.multiStreak = 0;
    }

    // --- head orientation -------------------------------------------------
    const pose = this.headPose(faces[0]);
    const threshold = 0.2 - 0.1 * clamp(this.config.gaze_sensitivity, 0, 1);
    const away =
      this.config.gaze_tracking_enabled &&
      (Math.abs(pose.yaw) > threshold || Math.abs(pose.pitch) > threshold * 1.6);

    if (away) {
      this.awayStreak += 1;
      if (this.awayStreak === GAZE_AWAY_SAMPLES) {
        this.record(
          "gaze_away",
          { yaw: round(pose.yaw), pitch: round(pose.pitch), threshold: round(threshold) },
          "info",
          GAZE_AWAY_SAMPLES * SAMPLE_INTERVAL_MS,
        );
      }
    } else {
      this.awayStreak = 0;
    }

    this.update({ faceCount, facePresent: true, lookingAway: away });
  }

  /**
   * Head orientation from mesh geometry rather than the transformation matrix: the nose
   * tip's offset from the eye midpoint, normalised by face width/height. It is
   * convention-independent, which matters more here than a few degrees of precision.
   */
  private headPose(landmarks: LandmarkPoint[]): { yaw: number; pitch: number } {
    const nose = landmarks[NOSE_TIP];
    const eyeR = landmarks[EYE_OUTER_RIGHT];
    const eyeL = landmarks[EYE_OUTER_LEFT];
    const silR = landmarks[SILHOUETTE_RIGHT];
    const silL = landmarks[SILHOUETTE_LEFT];
    const forehead = landmarks[FOREHEAD];
    const chin = landmarks[CHIN];

    if (!nose || !eyeR || !eyeL || !silR || !silL || !forehead || !chin) {
      return { yaw: 0, pitch: 0 };
    }

    const width = Math.abs(silL.x - silR.x) || 1e-6;
    const height = Math.abs(chin.y - forehead.y) || 1e-6;

    const eyeMidX = (eyeR.x + eyeL.x) / 2;
    const eyeMidY = (eyeR.y + eyeL.y) / 2;

    // Vertical reference: where the nose sits between the eye line and the chin when
    // the head is level is roughly a third of the face height.
    const yaw = (nose.x - eyeMidX) / width;
    const pitch = (nose.y - eyeMidY) / height - 0.33;

    return { yaw, pitch };
  }

  /** Fallback path: cannot see faces, but can tell that the lens is covered. */
  private sampleLuminance() {
    const frame = this.drawFrame(160, 120);
    if (!frame) return;

    let total = 0;
    for (let i = 0; i < frame.data.length; i += 4) {
      total += 0.299 * frame.data[i] + 0.587 * frame.data[i + 1] + 0.114 * frame.data[i + 2];
    }
    const mean = total / (frame.data.length / 4);

    if (mean < 12) {
      this.darkStreak += 1;
      if (this.darkStreak === DARK_FRAME_SAMPLES) {
        this.record("camera_blocked", { mean_luminance: round(mean) }, "critical");
        void this.snapshot("camera_blocked");
      }
    } else {
      this.darkStreak = 0;
    }
  }

  private drawFrame(width: number, height: number): ImageData | null {
    if (!this.video || !this.canvas) return null;
    const context = this.canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return null;
    this.canvas.width = width;
    this.canvas.height = height;
    context.drawImage(this.video, 0, 0, width, height);
    try {
      return context.getImageData(0, 0, width, height);
    } catch {
      return null;
    }
  }

  // --------------------------------------------------------------- snapshot
  private async snapshot(eventType?: ProctorEventType) {
    if (this.stopped || !this.status.cameraReady || !this.video || !this.canvas) return;

    const context = this.canvas.getContext("2d");
    if (!context) return;
    this.canvas.width = 480;
    this.canvas.height = 360;
    context.drawImage(this.video, 0, 0, 480, 360);

    const blob = await new Promise<Blob | null>((resolve) =>
      this.canvas!.toBlob((b) => resolve(b), "image/jpeg", 0.72),
    );
    if (!blob) return;

    const form = new FormData();
    form.append("file", blob, "snapshot.jpg");
    if (eventType) {
      form.append("event_type", eventType);
      form.append("occurred_at", new Date().toISOString());
    }

    try {
      await api.upload(`/sessions/${this.sessionId}/proctor/snapshot`, form, {
        examToken: this.examToken,
      });
    } catch {
      /* a lost snapshot must never interrupt the exam */
    }
  }

  // ----------------------------------------------------------- browser signals
  private attachBehaviourListeners() {
    const onVisibility = () => {
      if (document.hidden) {
        this.hiddenSince = Date.now();
        // Recorded on the way out, not on the way back. A candidate who switches away
        // and never returns still has the violation on the record, and the flush that
        // follows means the server hears about it while the page can still talk.
        void this.reportFocusViolation("tab_switch", { left_at: new Date().toISOString() });
      } else if (this.hiddenSince) {
        const away = Date.now() - this.hiddenSince;
        this.hiddenSince = null;
        this.status.tabSwitches += 1;
        this.update({ tabSwitches: this.status.tabSwitches });
        // The return trip carries how long they were away, as evidence, but must not
        // count as a second violation for the same departure.
        this.record("window_blur", { away_ms: away }, "info", away);
        void this.flush();
      }
    };

    const onBlur = () => {
      // Only meaningful when the document is still visible: a tab switch already
      // fires visibilitychange and should not be double-counted.
      if (!document.hidden) this.record("window_blur", undefined, "info");
    };

    const onFullscreen = () => {
      const inside = Boolean(document.fullscreenElement);
      this.update({ inFullscreen: inside });
      if (this.config.require_fullscreen && !inside) {
        void this.reportFocusViolation("fullscreen_exit");
      }
    };

    const onPaste = (event: ClipboardEvent) => {
      if (!this.config.block_copy_paste) return;
      event.preventDefault();
      this.record("paste_attempt", { length: event.clipboardData?.getData("text").length ?? 0 }, "warning");
      void this.flush();
    };

    const onCopy = (event: ClipboardEvent) => {
      if (!this.config.block_copy_paste) return;
      event.preventDefault();
      this.record("copy_attempt", undefined, "info");
    };

    const onCut = (event: ClipboardEvent) => {
      if (!this.config.block_copy_paste) return;
      event.preventDefault();
      this.record("cut_attempt", undefined, "warning");
      void this.flush();
    };

    const onContextMenu = (event: MouseEvent) => {
      if (this.config.block_copy_paste) event.preventDefault();
      this.record("right_click", undefined, "info");
    };

    let selectionThrottled = false;
    const onSelectStart = () => {
      // Reading the question involves selecting text constantly, so this is throttled
      // hard rather than streak-gated like the vision signals - it is evidence of
      // frequency, not a single alarming moment.
      if (selectionThrottled) return;
      selectionThrottled = true;
      window.setTimeout(() => { selectionThrottled = false; }, 5000);
      this.record("text_selection", undefined, "info");
    };

    const onOffline = () => {
      this.record("network_lost", undefined, "warning");
      void this.flush();
    };

    const onUnload = () => {
      if (this.buffer.length === 0) return;
      flushOnUnload(
        `/sessions/${this.sessionId}/proctor/events`,
        { events: this.buffer },
        this.examToken,
      );
      this.buffer = [];
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    document.addEventListener("fullscreenchange", onFullscreen);
    document.addEventListener("paste", onPaste);
    document.addEventListener("copy", onCopy);
    document.addEventListener("cut", onCut);
    document.addEventListener("contextmenu", onContextMenu);
    document.addEventListener("selectstart", onSelectStart);
    window.addEventListener("offline", onOffline);
    window.addEventListener("pagehide", onUnload);

    this.detachListeners = [
      () => document.removeEventListener("visibilitychange", onVisibility),
      () => window.removeEventListener("blur", onBlur),
      () => document.removeEventListener("fullscreenchange", onFullscreen),
      () => document.removeEventListener("paste", onPaste),
      () => document.removeEventListener("copy", onCopy),
      () => document.removeEventListener("cut", onCut),
      () => document.removeEventListener("contextmenu", onContextMenu),
      () => document.removeEventListener("selectstart", onSelectStart),
      () => window.removeEventListener("offline", onOffline),
      () => window.removeEventListener("pagehide", onUnload),
    ];
  }

  /**
   * Record one "left the exam" event and get it to the server promptly.
   *
   * Answers first, then the event. The runner's answer writes are debounced, so a
   * candidate who types and immediately alt-tabs could otherwise have their paper
   * submitted with the last edit still sitting in a timer. Awaiting the runner's flush
   * before the event goes out closes that window; if the flush throws, the violation is
   * still reported, because losing the evidence is the worse failure.
   */
  private async reportFocusViolation(
    type: "tab_switch" | "fullscreen_exit",
    metadata?: Record<string, unknown>,
  ) {
    this.status.focusViolations += 1;
    this.update({ focusViolations: this.status.focusViolations });

    try {
      await this.callbacks.onFocusViolation?.();
    } catch {
      /* an answer that would not save must not swallow the violation */
    }
    this.record(type, metadata, "warning");
    await this.flush();
  }

  /** Ask the browser for fullscreen. Only a user gesture can grant it. */
  async enterFullscreen(): Promise<boolean> {
    try {
      await document.documentElement.requestFullscreen?.();
      const inside = Boolean(document.fullscreenElement);
      this.update({ inFullscreen: inside });
      return inside;
    } catch {
      return false;
    }
  }

  // ----------------------------------------------------------------- socket
  /**
   * Open the live proctoring channel.
   *
   * The socket is preferred over POSTing batches because the server's verdict - a warning,
   * or a termination - reaches the candidate when the server decides, not on the client's
   * next poll. Everything degrades to the POST path if it cannot be held open: some
   * proxies will not carry a socket at all, and an exam must not depend on one.
   *
   * Credentials ride in `Sec-WebSocket-Protocol` because the browser WebSocket API cannot
   * set an `Authorization` header, and a token in the query string ends up in access logs.
   */
  private connectSocket() {
    if (this.stopped || this.socket) return;

    const access = tokens.access();
    if (!access || !this.examToken) return;

    const url = `${API_BASE.replace(/^http/, "ws")}/ws/sessions/${this.sessionId}/proctor`;
    let socket: WebSocket;
    try {
      socket = new WebSocket(url, [WS_SUBPROTOCOL, access, this.examToken]);
    } catch {
      this.transport = "http";
      return;
    }
    this.socket = socket;

    socket.onopen = () => {
      this.transport = "socket";
      this.socketRetries = 0;
    };

    socket.onmessage = (event) => {
      let payload: ProctorBatchOut | { error: string };
      try {
        payload = JSON.parse(event.data as string);
      } catch {
        return;
      }
      if ("error" in payload) {
        // The server rejected the frame's shape. Nothing to retry - a resend would be
        // rejected identically - so drop it and let the next flush carry on.
        console.warn("Proctor batch rejected by the server", payload);
        return;
      }
      this.applyOutcome(payload);
    };

    socket.onclose = () => {
      this.socket = null;
      if (this.stopped) return;
      this.transport = "http";
      // Back off, then try again. Until it reconnects, flush() posts - so a dropped
      // socket costs latency on the verdict, never evidence.
      const delay = Math.min(30_000, 2_000 * 2 ** this.socketRetries);
      this.socketRetries += 1;
      this.reconnectTimer = window.setTimeout(() => this.connectSocket(), delay);
    };

    socket.onerror = () => {
      // onclose always follows; the reconnect is scheduled there.
      this.transport = "http";
    };
  }

  private applyOutcome(outcome: ProctorBatchOut) {
    // The server's counts win over the ones counted here. The client's are for
    // immediate feedback; the server's are computed from the stored events and survive
    // a reload, which is what stops a refresh from buying a fresh set of warnings.
    this.update({
      suspicionScore: outcome.suspicion_score,
      tabSwitches: outcome.tab_switch_count,
      focusViolations: outcome.focus_violation_count ?? this.status.focusViolations,
      focusViolationsLeft: outcome.focus_violations_left ?? -1,
      flagged: outcome.is_flagged,
      terminated: outcome.terminated,
      autoSubmitted: Boolean(outcome.auto_submitted),
    });
    this.status.focusViolations = outcome.focus_violation_count ?? this.status.focusViolations;

    if (outcome.warnings.length) this.callbacks.onWarnings(outcome.warnings);

    if (outcome.auto_submitted) {
      this.callbacks.onAutoSubmitted?.(
        outcome.warnings.at(-1) ??
          "proctoring:too_many_focus_violations",
      );
      this.stop();
      return;
    }
    if (outcome.terminated) {
      this.callbacks.onTerminated(
        outcome.warnings.at(-1) ?? "proctoring:session_terminated",
      );
      this.stop();
    }
  }

  // ------------------------------------------------------------------ flush
  async flush(): Promise<void> {
    if (this.stopped || this.buffer.length === 0) return;
    const batch = this.buffer;
    this.buffer = [];

    // Preferred path: hand the batch to the open socket. The reply arrives on onmessage.
    if (this.socket?.readyState === WebSocket.OPEN) {
      try {
        this.socket.send(JSON.stringify({ events: batch }));
        return;
      } catch {
        // Fall through to HTTP rather than losing the batch to a half-dead socket.
      }
    }

    try {
      const response = await api.post<ProctorBatchOut>(
        `/sessions/${this.sessionId}/proctor/events`,
        { events: batch },
        { examToken: this.examToken },
      );
      this.applyOutcome(response);
    } catch {
      // Put the events back so a flaky network does not silently erase evidence.
      this.buffer = [...batch, ...this.buffer].slice(-MAX_BUFFER);
    }
  }

  // ------------------------------------------------------------------- stop
  stop() {
    if (this.stopped) return;
    this.stopped = true;

    if (this.sampleTimer) window.clearInterval(this.sampleTimer);
    if (this.flushTimer) window.clearInterval(this.flushTimer);
    if (this.snapshotTimer) window.clearInterval(this.snapshotTimer);
    if (this.reconnectTimer) window.clearTimeout(this.reconnectTimer);

    // Close before the tracks stop, so the server sees a clean 1000 rather than a drop.
    this.socket?.close(1000, "Session ended");
    this.socket = null;

    this.detachListeners.forEach((detach) => detach());
    this.detachListeners = [];

    this.landmarker?.close();
    this.landmarker = null;

    this.objectDetector?.close();
    this.objectDetector = null;

    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;

    this.micStream?.getTracks().forEach((track) => track.stop());
    this.micStream = null;

    if (this.video) this.video.srcObject = null;
  }
}

/**
 * One-shot face check for the pre-exam gate: loads its own landmarker instance (kept
 * separate from a live `ProctorEngine` so the check stage can run before any session
 * exists), runs a single detection pass, and tears the model down immediately. Shares
 * the same WASM/model assets as the live engine so there is exactly one place that knows
 * how to load MediaPipe.
 */
export async function detectFaceOnce(
  video: HTMLVideoElement,
): Promise<{ faceDetected: boolean; faceCount: number }> {
  const vision = await import("@mediapipe/tasks-vision");
  const fileset = await quietingMediaPipeLogs(() => vision.FilesetResolver.forVisionTasks(WASM_PATH));
  const landmarker = await quietingMediaPipeLogs(() =>
    vision.FaceLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_PATH, delegate: "GPU" },
      runningMode: "VIDEO",
      numFaces: 3,
      outputFaceBlendshapes: false,
      outputFacialTransformationMatrixes: false,
    }),
  );
  try {
    // The delegate is already created by this point, but the very first inference can
    // still emit the same startup notices, so this call is quieted too.
    const result = await quietingMediaPipeLogs(() => landmarker.detectForVideo(video, performance.now()));
    const faceCount = result.faceLandmarks?.length ?? 0;
    return { faceDetected: faceCount === 1, faceCount };
  } finally {
    landmarker.close();
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function round(value: number) {
  return Math.round(value * 1000) / 1000;
}
