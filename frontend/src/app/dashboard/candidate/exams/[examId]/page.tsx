"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  SectionTitle,
  Skeleton,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import {
  IconAlert,
  IconArrowRight,
  IconCamera,
  IconCheck,
  IconClock,
  IconExam,
  IconMic,
  IconMonitor,
  IconShield,
  IconWifi,
} from "@/components/icons";
import { API_BASE, ApiError, api, tokens } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { detectFaceOnce } from "@/lib/proctor";
import type { CandidateExamCard, ProctorConfig } from "@/lib/types";

type Stage = "details" | "system-check" | "instructions";

type CheckState = "idle" | "running" | "pass" | "fail" | "unsupported";

interface SystemCheck {
  key: string;
  label: string;
  detail: string;
  state: CheckState;
  message?: string;
}

/**
 * Exam details → system check → instructions → start.
 *
 * The gate here is a courtesy to the candidate, not a security control: the server still
 * verifies enrolment, the exam window and the single-attempt rule when `start` is called.
 * What this flow buys is that nobody discovers a dead camera thirty seconds into a
 * proctored paper.
 */
export default function ExamDetailPage() {
  const t = useTranslations("exam");
  const { user } = useRequireAuth(["candidate"]);
  const params = useParams<{ examId: string }>();
  const router = useRouter();

  const [card, setCard] = useState<CandidateExamCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>("details");
  const [starting, setStarting] = useState(false);
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user) return;
      try {
        const cards = await api.get<CandidateExamCard[]>("/my/exams");
        if (cancelled) return;
        const found = cards.find((c) => c.exam_id === params.examId);
        if (!found) {
          setError(t("exam_not_assigned"));
        } else {
          setCard(found);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : t("could_not_load_exam"));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, params.examId]);

  async function start() {
    if (!card) return;
    setStarting(true);
    try {
      const session = await api.post<{ session_id: string }>(`/exams/${card.exam_id}/start`);
      router.push(`/exam/${session.session_id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : t("could_not_start_exam"), "rose");
      setStarting(false);
    }
  }

  if (!user) return null;

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-[110px] rounded-[16px]" />
        <Skeleton className="h-[280px] rounded-[14px]" />
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="space-y-5">
        <Alert tone="rose">{error ?? t("exam_not_found")}</Alert>
        <Link href="/dashboard/candidate/exams">
          <Button variant="secondary">{t("back_to_exams")}</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard/candidate/exams">
          <Button variant="ghost" size="sm">
            ← {t("my_exams")}
          </Button>
        </Link>
      </div>

      <Hero title={card.title} body={`${card.subject_name} · ${card.reason ?? t("assigned_to_you")}`} />

      <Stepper stage={stage} />

      {stage === "details" && (
        <ExamDetails card={card} onContinue={() => setStage("system-check")} />
      )}

      {stage === "system-check" && (
        <SystemCheckStage
          card={card}
          onBack={() => setStage("details")}
          onContinue={() => setStage("instructions")}
        />
      )}

      {stage === "instructions" && (
        <InstructionsStage
          card={card}
          agreed={agreed}
          onAgree={setAgreed}
          starting={starting}
          onBack={() => setStage("system-check")}
          onStart={start}
        />
      )}
    </div>
  );
}

/* --------------------------------------------------------------------- stepper */
function Stepper({ stage }: { stage: Stage }) {
  const t = useTranslations("exam");
  const STAGES: { key: Stage; label: string }[] = [
    { key: "details", label: t("exam_details") },
    { key: "system-check", label: t("system_check") },
    { key: "instructions", label: t("instructions_title") },
  ];
  const index = STAGES.findIndex((s) => s.key === stage);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {STAGES.map((item, i) => (
        <div key={item.key} className="flex items-center gap-2">
          <span
            className={cx(
              "flex items-center gap-2 rounded-[10px] border px-3 py-1.5 text-[12.5px] font-medium",
              i < index
                ? "border-mint/30 bg-mint-soft text-mint"
                : i === index
                  ? "border-accent bg-accent-soft text-accent-ink"
                  : "border-line bg-surface text-ink-muted",
            )}
          >
            {i < index ? <IconCheck size={13} /> : <span className="tabular-nums">{i + 1}</span>}
            {item.label}
          </span>
          {i < STAGES.length - 1 && <span className="h-px w-4 bg-line-strong" />}
        </div>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------------- details */
function ExamDetails({
  card,
  onContinue,
}: {
  card: CandidateExamCard;
  onContinue: () => void;
}) {
  const t = useTranslations("exam");
  return (
    <Card>
      <SectionTitle title={t("exam_details_title")} hint={t("read_before_continue")} />

      <dl className="grid gap-3 sm:grid-cols-4">
        {(
          [
            { label: t("duration_label"), value: `${card.duration_minutes} min`, Icon: IconClock },
            { label: t("questions_label"), value: String(card.total_questions), Icon: IconExam },
            { label: t("opens_label"), value: formatDate(card.starts_at), Icon: IconClock },
            { label: t("closes_label"), value: formatDate(card.ends_at), Icon: IconClock },
          ] as const
        ).map(({ label, value, Icon }) => (
          <div key={label} className="rounded-[11px] border border-line p-3">
            <dt className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-ink-muted">
              <Icon size={13} />
              {label}
            </dt>
            <dd className="mt-1 text-[14px] font-semibold text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-5 space-y-2.5">
        {[
          t("paper_unique"),
          t("single_attempt"),
          t("answers_autosave"),
          t("marking_process"),
        ].map((line) => (
          <div key={line} className="flex gap-2.5">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-accent" />
            <p className="text-[13.5px] leading-relaxed text-ink-soft">{line}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between gap-3">
        <p className="text-[12.5px] text-ink-muted">
          {card.can_start ? t("exam_open_now") : card.reason}
        </p>
        <Button onClick={onContinue} disabled={!card.can_start}>
          {t("continue_to_system_check")}
          <IconArrowRight size={15} />
        </Button>
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------- system check */
type WindowWithScreenDetails = Window & {
  getScreenDetails?: () => Promise<{ screens: unknown[] }>;
};

function proctorFlag(config: ProctorConfig | undefined, key: keyof ProctorConfig, fallback: boolean): boolean {
  const value = config?.[key];
  return typeof value === "boolean" ? value : fallback;
}

async function waitForFrame(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= 2) return;
  await new Promise<void>((resolve) => {
    const onLoaded = () => {
      video.removeEventListener("loadeddata", onLoaded);
      resolve();
    };
    video.addEventListener("loadeddata", onLoaded);
    window.setTimeout(resolve, 1500);
  });
}

function SystemCheckStage({
  card,
  onBack,
  onContinue,
}: {
  card: CandidateExamCard;
  onBack: () => void;
  onContinue: () => void;
}) {
  const t = useTranslations("exam");
  const config = card.proctor_config;
  const needCamera = proctorFlag(config, "webcam_enabled", true);
  const needMic = proctorFlag(config, "require_microphone", true);
  const needFullscreen = proctorFlag(config, "require_fullscreen", true);
  const needDisplay = proctorFlag(config, "require_single_display", true);
  const minMbps = config?.min_bandwidth_mbps ?? 2;

  const initialChecks = useMemo<SystemCheck[]>(() => {
    const list: SystemCheck[] = [];
    // Required for every exam type, unconditionally - a candidate on an unsupported
    // browser needs to know before the sitting starts, not mid-exam when a check fails.
    list.push({
      key: "browser",
      label: t("browser_label"),
      detail: t("browser_required"),
      state: "idle",
    });
    if (needCamera) {
      list.push({
        key: "camera",
        label: t("camera_face_label"),
        detail: t("camera_needs_face"),
        state: "idle",
      });
    }
    if (needMic) {
      list.push({
        key: "microphone",
        label: t("microphone_label"),
        detail: t("microphone_required"),
        state: "idle",
      });
    }
    list.push({
      key: "speed",
      label: t("internet_speed_label"),
      detail: t("internet_speed_detail", { minMbps }),
      state: "idle",
    });
    if (needFullscreen) {
      list.push({
        key: "fullscreen",
        label: t("fullscreen_label"),
        detail: t("fullscreen_detail"),
        state: "idle",
      });
    }
    if (needDisplay) {
      list.push({
        key: "display",
        label: t("display_label"),
        detail: t("display_detail"),
        state: "idle",
      });
    }
    return list;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  const [checks, setChecks] = useState<SystemCheck[]>(initialChecks);
  const [running, setRunning] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const cameraStreamRef = useRef<MediaStream | null>(null);

  const update = useCallback((key: string, patch: Partial<SystemCheck>) => {
    setChecks((current) => current.map((c) => (c.key === key ? { ...c, ...patch } : c)));
  }, []);

  const runAuto = useCallback(async () => {
    setRunning(true);
    setChecks((current) =>
      current.map((c) =>
        c.key === "camera" || c.key === "microphone" || c.key === "speed"
          ? { ...c, state: "running", message: undefined }
          : c,
      ),
    );

    // --- browser support ----------------------------------------------------
    // Feature-detected rather than sniffed from the user-agent string, which lies
    // constantly - a browser that actually has these APIs can actually run the exam,
    // regardless of what it claims to be.
    const browserSupported =
      typeof navigator.mediaDevices?.getUserMedia === "function" &&
      typeof document.documentElement.requestFullscreen === "function" &&
      typeof window.WebSocket !== "undefined";
    update("browser", {
      state: browserSupported ? "pass" : "fail",
      message: browserSupported
        ? t("supported")
        : t("browser_not_supported"),
    });

    // --- camera + face -----------------------------------------------------
    if (needCamera) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
        cameraStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
          await waitForFrame(videoRef.current);
        }
        const { faceCount } = videoRef.current
          ? await detectFaceOnce(videoRef.current)
          : { faceCount: 0 };
        if (faceCount === 1) {
          update("camera", { state: "pass", message: t("face_detected") });
        } else if (faceCount === 0) {
          update("camera", {
            state: "fail",
            message: t("no_face_detected"),
          });
        } else {
          update("camera", {
            state: "fail",
            message: t("multiple_faces_detected", { faceCount }),
          });
        }
      } catch {
        cameraStreamRef.current = null;
        update("camera", {
          state: "fail",
          message: t("camera_access_denied"),
        });
      }
    }

    // --- microphone ---------------------------------------------------------
    if (needMic) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: false, audio: true });
        const track = stream.getAudioTracks()[0];
        const live = track?.readyState === "live";
        stream.getTracks().forEach((t) => t.stop());
        update("microphone", {
          state: live ? "pass" : "fail",
          message: live ? t("microphone_available") : t("microphone_not_active"),
        });
      } catch {
        update("microphone", {
          state: "fail",
          message: t("microphone_access_denied"),
        });
      }
    }

    // --- internet speed -------------------------------------------------
    try {
      const started = performance.now();
      const response = await fetch(`${API_BASE}/system/speed-test-payload`, {
        headers: { Authorization: `Bearer ${tokens.access() ?? ""}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error("bad response");
      const buffer = await response.arrayBuffer();
      const seconds = Math.max((performance.now() - started) / 1000, 0.001);
      const mbps = (buffer.byteLength * 8) / 1_000_000 / seconds;
      update("speed", {
        state: mbps >= minMbps ? "pass" : "fail",
        message:
          mbps >= minMbps
            ? t("speed_mbps", { mbps: mbps.toFixed(1) })
            : t("speed_too_low", { mbps: mbps.toFixed(1), minMbps }),
      });
    } catch {
      update("speed", {
        state: "fail",
        message: t("server_unreachable"),
      });
    }

    setRunning(false);
  }, [needCamera, needMic, minMbps, update]);

  useEffect(() => {
    void runAuto();
    return () => {
      cameraStreamRef.current?.getTracks().forEach((t) => t.stop());
      cameraStreamRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- fullscreen: needs a user gesture, and tracks exits while this stage is open
  useEffect(() => {
    if (!needFullscreen) return;
    const onChange = () => {
      update(
        "fullscreen",
        document.fullscreenElement
          ? { state: "pass", message: t("fullscreen_active") }
          : { state: "fail", message: t("fullscreen_not_enabled") },
      );
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, [needFullscreen, update, t]);

  async function enterFullscreen() {
    try {
      await document.documentElement.requestFullscreen();
    } catch {
      update("fullscreen", {
        state: "fail",
        message: t("fullscreen_blocked"),
      });
    }
  }

  // --- single display: detection itself also needs a user gesture
  useEffect(() => {
    if (!needDisplay) return;
    if (typeof (window as WindowWithScreenDetails).getScreenDetails !== "function") {
      update("display", {
        state: "unsupported",
        message: t("display_browser_unsupported"),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [needDisplay, t]);

  async function checkDisplays() {
    const getScreenDetails = (window as WindowWithScreenDetails).getScreenDetails;
    if (!getScreenDetails) return;
    update("display", { state: "running" });
    try {
      const details = await getScreenDetails();
      const count = details.screens.length;
      update("display", {
        state: count === 1 ? "pass" : "fail",
        message:
          count === 1
            ? t("display_single")
            : t("display_multiple", { count }),
      });
    } catch {
      update("display", {
        state: "fail",
        message: t("display_permission_denied"),
      });
    }
  }

  const blocking = checks.filter((c) => c.state !== "pass" && c.state !== "unsupported");
  const allClear = blocking.length === 0;

  const ICONS: Record<string, typeof IconCamera> = {
    camera: IconCamera,
    microphone: IconMic,
    speed: IconWifi,
    fullscreen: IconMonitor,
    display: IconMonitor,
  };

  return (
    <Card>
      <SectionTitle
        title={t("system_check_title")}
        hint={t("system_check_hint")}
      />

      <ul className="space-y-2.5">
        {checks.map((check) => {
          const Icon = ICONS[check.key] ?? IconShield;
          return (
            <li
              key={check.key}
              className={cx(
                "flex items-start gap-3 rounded-[11px] border p-3.5",
                check.state === "pass"
                  ? "border-mint/25 bg-mint-soft/50"
                  : check.state === "fail"
                    ? "border-rose/25 bg-rose-soft/50"
                    : check.state === "unsupported"
                      ? "border-line bg-sunken/50"
                      : "border-line",
              )}
            >
              <span
                className={cx(
                  "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px]",
                  check.state === "pass"
                    ? "bg-mint-soft text-mint"
                    : check.state === "fail"
                      ? "bg-rose-soft text-rose"
                      : "bg-sunken text-ink-muted",
                )}
              >
                <Icon size={16} />
              </span>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="text-[13.5px] font-medium text-ink">{check.label}</p>
                  {check.state === "running" && <Badge>checking…</Badge>}
                  {check.state === "pass" && <Badge tone="mint">ready</Badge>}
                  {check.state === "fail" && <Badge tone="rose">problem</Badge>}
                  {check.state === "unsupported" && <Badge tone="neutral">unverified</Badge>}
                </div>
                <p className="mt-0.5 text-[12.5px] text-ink-muted">
                  {check.message ?? check.detail}
                </p>

                {check.key === "camera" && needCamera && (
                  <video
                    ref={videoRef}
                    muted
                    playsInline
                    className={cx(
                      "mt-2 h-[90px] w-[120px] rounded-[8px] border border-line bg-sunken object-cover",
                      check.state === "running" || check.state === "pass" ? "" : "hidden",
                    )}
                  />
                )}

                {check.key === "fullscreen" && check.state !== "pass" && (
                  <Button size="sm" variant="secondary" className="mt-2" onClick={() => void enterFullscreen()}>
                    {t("enable_fullscreen")}
                  </Button>
                )}

                {check.key === "display" && check.state === "idle" && (
                  <Button size="sm" variant="secondary" className="mt-2" onClick={() => void checkDisplays()}>
                    {t("check_displays")}
                  </Button>
                )}
                {check.key === "display" && check.state === "fail" && (
                  <Button size="sm" variant="secondary" className="mt-2" onClick={() => void checkDisplays()}>
                    {t("recheck_displays")}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {!allClear && (
        <div className="mt-4">
          <Alert tone="amber" title={t("fix_before_start")}>
            {blocking.map((c) => c.label).join(", ")} {t("must_pass_to_continue")}
          </Alert>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={onBack}>
          {t("back_button")}
        </Button>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void runAuto()} loading={running}>
            {t("rerun_checks")}
          </Button>
          <Button onClick={onContinue} disabled={running || !allClear}>
            {t("continue_button")}
            <IconArrowRight size={15} />
          </Button>
        </div>
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------- instructions */
function InstructionsStage({
  card,
  agreed,
  onAgree,
  starting,
  onBack,
  onStart,
}: {
  card: CandidateExamCard;
  agreed: boolean;
  onAgree: (value: boolean) => void;
  starting: boolean;
  onBack: () => void;
  onStart: () => void;
}) {
  const t = useTranslations("exam");
  return (
    <Card>
      <SectionTitle
        title={t("instructions_title")}
        hint={t("instructions_hint")}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-[11px] border border-line p-4">
          <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink">
            <IconExam size={15} /> {t("sitting_paper")}
          </p>
          <ul className="space-y-1.5 text-[12.5px] leading-relaxed text-ink-soft">
            <li>· {t("questions_duration", { total_questions: card.total_questions, duration_minutes: card.duration_minutes })}</li>
            <li>· {t("move_between_questions")}</li>
            <li>· {t("answers_auto_save")}</li>
            <li>· {t("blank_no_negative")}</li>
            <li>· {t("submit_final")}</li>
          </ul>
        </div>

        <div className="rounded-[11px] border border-line p-4">
          <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink">
            <IconShield size={15} /> {t("while_monitored")}
          </p>
          <ul className="space-y-1.5 text-[12.5px] leading-relaxed text-ink-soft">
            <li>· {t("stay_in_frame")}</li>
            <li>· {t("leaving_recorded")}</li>
            <li>· {t("fullscreen_copy_paste")}</li>
            <li>· {t("snapshots_stored")}</li>
            <li>· {t("high_suspicion")}</li>
          </ul>
        </div>
      </div>

      <div className="mt-4">
        <Alert tone="amber" title={t("one_attempt_title")}>
          {t("one_attempt_detail")}
        </Alert>
      </div>

      <label className="mt-5 flex cursor-pointer items-start gap-3 rounded-[11px] border border-line p-3.5 transition hover:bg-sunken">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => onAgree(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]"
        />
        <span className="text-[13px] leading-relaxed text-ink-soft">
          {t("monitoring_consent")}
        </span>
      </label>

      <div className="mt-6 flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={onBack}>
          {t("back_button")}
        </Button>
        <Button onClick={onStart} loading={starting} disabled={!agreed}>
          {card.session_status === "in_progress" ? t("resume_exam") : t("start_exam_button")}
          <IconArrowRight size={15} />
        </Button>
      </div>

      {!agreed && (
        <p className="mt-2 flex items-center justify-end gap-1.5 text-[12px] text-ink-muted">
          <IconAlert size={13} />
          {t("confirm_declaration")}
        </p>
      )}
    </Card>
  );
}
