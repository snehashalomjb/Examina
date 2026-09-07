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

export type VisionMode = "landmarks" | "degraded" | "off";

export interface ProctorStatus {
  cameraReady: boolean;
  visionMode: VisionMode;
  faceCount: number;
  facePresent: boolean;
  lookingAway: boolean;
  suspicionScore: number;
  tabSwitches: number;
  flagged: boolean;
  terminated: boolean;
  lastError: string | null;
}

interface BufferedEvent {
  event_type: ProctorEventType;
  occurred_at: string;
  severity?: "info" | "warning" | "critical";
  duration_ms?: number;
  metadata?: Record<string, unknown>;
}

export interface ProctorCallbacks {
  onStatus: (status: ProctorStatus) => void;
  onWarnings: (warnings: string[]) => void;
  onTerminated: (reason: string) => void;
}

interface LandmarkPoint {
  x: number;
  y: number;
  z: number;
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
  private hiddenSince: number | null = null;

  private status: ProctorStatus = {
    cameraReady: false,
    visionMode: "off",
    faceCount: 0,
    facePresent: false,
    lookingAway: false,
    suspicionScore: 0,
    tabSwitches: 0,
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

  getStatus(): ProctorStatus {
    return { ...this.status };
  }

  private update(patch: Partial<ProctorStatus>) {
    this.status = { ...this.status, ...patch };
    this.callbacks.onStatus(this.getStatus());
  }

  private record(
    type: ProctorEventType,
    metadata?: Record<string, unknown>,
    severity?: BufferedEvent["severity"],
    durationMs?: number,
  ) {
    if (this.stopped) return;
    if (this.buffer.length >= MAX_BUFFER) this.buffer.shift();
    this.buffer.push({
      event_type: type,
      occurred_at: new Date().toISOString(),
      severity,
      duration_ms: durationMs,
      metadata,
    });
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
        lastError: "Camera unavailable. Grant camera access and reload to continue being proctored.",
      });
      void this.flush();
      return;
    }

    await this.initVision();

    this.sampleTimer = window.setInterval(() => void this.sample(), SAMPLE_INTERVAL_MS);

    const snapshotEvery = Math.max(15, this.config.snapshot_interval_seconds) * 1000;
    this.snapshotTimer = window.setInterval(() => void this.snapshot(), snapshotEvery);
    // One snapshot up front establishes who actually sat down.
    window.setTimeout(() => void this.snapshot(), 3000);
  }

  private async initVision() {
    try {
      const vision = await import("@mediapipe/tasks-vision");
      const fileset = await vision.FilesetResolver.forVisionTasks(WASM_PATH);
      const landmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_PATH, delegate: "GPU" },
        runningMode: "VIDEO",
        numFaces: 3, // enough to notice a second person without paying for a crowd
        outputFaceBlendshapes: false,
        outputFacialTransformationMatrixes: false,
      });
      this.landmarker = landmarker as unknown as ProctorEngine["landmarker"];
      this.update({ visionMode: "landmarks" });
    } catch (error) {
      console.warn("Face landmarker unavailable, degrading to luminance checks", error);
      this.update({
        visionMode: "degraded",
        lastError:
          "Face detection could not start. Your camera is still recorded for review, and browser activity is still monitored.",
      });
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
      } else if (this.hiddenSince) {
        const away = Date.now() - this.hiddenSince;
        this.hiddenSince = null;
        this.status.tabSwitches += 1;
        this.record("tab_switch", { away_ms: away }, "warning", away);
        this.update({ tabSwitches: this.status.tabSwitches });
        void this.flush();
      }
    };

    const onBlur = () => {
      // Only meaningful when the document is still visible: a tab switch already
      // fires visibilitychange and should not be double-counted.
      if (!document.hidden) this.record("window_blur", undefined, "info");
    };

    const onFullscreen = () => {
      if (this.config.require_fullscreen && !document.fullscreenElement) {
        this.record("fullscreen_exit", undefined, "warning");
        void this.flush();
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
    window.addEventListener("pagehide", onUnload);

    this.detachListeners = [
      () => document.removeEventListener("visibilitychange", onVisibility),
      () => window.removeEventListener("blur", onBlur),
      () => document.removeEventListener("fullscreenchange", onFullscreen),
      () => document.removeEventListener("paste", onPaste),
      () => document.removeEventListener("copy", onCopy),
      () => window.removeEventListener("pagehide", onUnload),
    ];
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
    this.update({
      suspicionScore: outcome.suspicion_score,
      tabSwitches: outcome.tab_switch_count,
      flagged: outcome.is_flagged,
      terminated: outcome.terminated,
    });

    if (outcome.warnings.length) this.callbacks.onWarnings(outcome.warnings);
    if (outcome.terminated) {
      this.callbacks.onTerminated(
        outcome.warnings.at(-1) ?? "Your session was terminated by the proctoring system.",
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

    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;

    if (this.video) this.video.srcObject = null;
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function round(value: number) {
  return Math.round(value * 1000) / 1000;
}
