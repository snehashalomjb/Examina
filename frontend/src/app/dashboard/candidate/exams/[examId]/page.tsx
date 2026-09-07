"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

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
  IconMonitor,
  IconShield,
} from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateExamCard } from "@/lib/types";

type Stage = "details" | "system-check" | "instructions";

type CheckState = "idle" | "running" | "pass" | "fail";

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
          setError("This examination is not assigned to you.");
        } else {
          setCard(found);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load this examination.");
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
      toast(err instanceof ApiError ? err.message : "Could not start the exam", "rose");
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
        <Alert tone="rose">{error ?? "Examination not found."}</Alert>
        <Link href="/dashboard/candidate/exams">
          <Button variant="secondary">Back to my exams</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard/candidate/exams">
          <Button variant="ghost" size="sm">
            ← My exams
          </Button>
        </Link>
      </div>

      <Hero title={card.title} body={`${card.subject_name} · ${card.reason ?? "Assigned to you"}`} />

      <Stepper stage={stage} />

      {stage === "details" && (
        <ExamDetails card={card} onContinue={() => setStage("system-check")} />
      )}

      {stage === "system-check" && (
        <SystemCheckStage
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
const STAGES: { key: Stage; label: string }[] = [
  { key: "details", label: "Exam details" },
  { key: "system-check", label: "System check" },
  { key: "instructions", label: "Instructions" },
];

function Stepper({ stage }: { stage: Stage }) {
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
  return (
    <Card>
      <SectionTitle title="Examination details" hint="Read this before you continue." />

      <dl className="grid gap-3 sm:grid-cols-4">
        {(
          [
            { label: "Duration", value: `${card.duration_minutes} min`, Icon: IconClock },
            { label: "Questions", value: String(card.total_questions), Icon: IconExam },
            { label: "Opens", value: formatDate(card.starts_at), Icon: IconClock },
            { label: "Closes", value: formatDate(card.ends_at), Icon: IconClock },
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
          "Your paper is generated for you alone — no two candidates get the same questions in the same order.",
          "You have a single attempt. The exam submits itself automatically when your time runs out.",
          "Your answers save as you work, so a refresh or a dropped connection will not lose them.",
          "Objective questions are marked immediately. Written answers are reviewed by an examiner before your result is released.",
        ].map((line) => (
          <div key={line} className="flex gap-2.5">
            <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-accent" />
            <p className="text-[13.5px] leading-relaxed text-ink-soft">{line}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between gap-3">
        <p className="text-[12.5px] text-ink-muted">
          {card.can_start ? "This exam is open now." : card.reason}
        </p>
        <Button onClick={onContinue} disabled={!card.can_start}>
          Continue to system check
          <IconArrowRight size={15} />
        </Button>
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------- system check */
function SystemCheckStage({
  onBack,
  onContinue,
}: {
  onBack: () => void;
  onContinue: () => void;
}) {
  const [checks, setChecks] = useState<SystemCheck[]>([
    {
      key: "camera",
      label: "Camera",
      detail: "Proctoring needs to see you for the whole sitting.",
      state: "idle",
    },
    {
      key: "browser",
      label: "Browser features",
      detail: "Fullscreen and visibility tracking must be available.",
      state: "idle",
    },
    {
      key: "connection",
      label: "Connection to the exam server",
      detail: "Your answers autosave over this connection.",
      state: "idle",
    },
  ]);
  const [running, setRunning] = useState(false);

  const update = useCallback((key: string, patch: Partial<SystemCheck>) => {
    setChecks((current) => current.map((c) => (c.key === key ? { ...c, ...patch } : c)));
  }, []);

  const run = useCallback(async () => {
    setRunning(true);
    setChecks((current) => current.map((c) => ({ ...c, state: "running", message: undefined })));

    // --- camera -----------------------------------------------------------
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      const label = stream.getVideoTracks()[0]?.label;
      // Release it again immediately - the exam runner opens its own stream.
      stream.getTracks().forEach((t) => t.stop());
      update("camera", { state: "pass", message: label || "Camera available" });
    } catch {
      update("camera", {
        state: "fail",
        message: "No camera access. Allow camera permission in your browser, then re-run.",
      });
    }

    // --- browser capabilities --------------------------------------------
    const hasFullscreen = typeof document.documentElement.requestFullscreen === "function";
    const hasVisibility = typeof document.hidden === "boolean";
    update("browser", {
      state: hasFullscreen && hasVisibility ? "pass" : "fail",
      message:
        hasFullscreen && hasVisibility
          ? "Fullscreen and focus tracking supported"
          : "This browser is missing features proctoring needs. Try Chrome, Edge or Firefox.",
    });

    // --- server -----------------------------------------------------------
    try {
      const started = performance.now();
      await api.get("/my/stats/summary");
      const ms = Math.round(performance.now() - started);
      update("connection", { state: "pass", message: `Reachable (${ms} ms)` });
    } catch {
      update("connection", {
        state: "fail",
        message: "Could not reach the exam server. Check your connection and re-run.",
      });
    }

    setRunning(false);
  }, [update]);

  useEffect(() => {
    void run();
  }, [run]);

  const allPassed = checks.every((c) => c.state === "pass");
  const anyFailed = checks.some((c) => c.state === "fail");

  return (
    <Card>
      <SectionTitle
        title="System check"
        hint="Confirming your machine can run a proctored exam before you start the clock."
      />

      <ul className="space-y-2.5">
        {checks.map((check) => (
          <li
            key={check.key}
            className={cx(
              "flex items-start gap-3 rounded-[11px] border p-3.5",
              check.state === "pass"
                ? "border-mint/25 bg-mint-soft/50"
                : check.state === "fail"
                  ? "border-rose/25 bg-rose-soft/50"
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
              {check.key === "camera" ? (
                <IconCamera size={16} />
              ) : check.key === "browser" ? (
                <IconMonitor size={16} />
              ) : (
                <IconShield size={16} />
              )}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-[13.5px] font-medium text-ink">{check.label}</p>
                {check.state === "running" && <Badge>checking…</Badge>}
                {check.state === "pass" && <Badge tone="mint">ready</Badge>}
                {check.state === "fail" && <Badge tone="rose">problem</Badge>}
              </div>
              <p className="mt-0.5 text-[12.5px] text-ink-muted">
                {check.message ?? check.detail}
              </p>
            </div>
          </li>
        ))}
      </ul>

      {anyFailed && (
        <div className="mt-4">
          <Alert tone="amber" title="Fix these before you start">
            You can still continue, but proctoring records a blocked camera as a critical
            event and it will count against your session.
          </Alert>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void run()} loading={running}>
            Re-run checks
          </Button>
          <Button onClick={onContinue} disabled={running}>
            {allPassed ? "Continue" : "Continue anyway"}
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
  return (
    <Card>
      <SectionTitle
        title="Instructions"
        hint="The clock starts the moment you begin, and it does not pause."
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-[11px] border border-line p-4">
          <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink">
            <IconExam size={15} /> Sitting the paper
          </p>
          <ul className="space-y-1.5 text-[12.5px] leading-relaxed text-ink-soft">
            <li>· {card.total_questions} questions, {card.duration_minutes} minutes.</li>
            <li>· Move freely between questions using the palette.</li>
            <li>· Answers save automatically as you type or select.</li>
            <li>· Blank answers score zero and never attract a negative mark.</li>
            <li>· Submitting is final — you cannot reopen the paper.</li>
          </ul>
        </div>

        <div className="rounded-[11px] border border-line p-4">
          <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-ink">
            <IconShield size={15} /> While you are monitored
          </p>
          <ul className="space-y-1.5 text-[12.5px] leading-relaxed text-ink-soft">
            <li>· Stay in frame, alone, with your face visible.</li>
            <li>· Leaving the exam tab is recorded and warned about.</li>
            <li>· Exiting fullscreen and copy/paste attempts are recorded.</li>
            <li>· Webcam snapshots are stored for examiner review.</li>
            <li>· A high suspicion score can end your session automatically.</li>
          </ul>
        </div>
      </div>

      <div className="mt-4">
        <Alert tone="amber" title="One attempt only">
          Once you start, this counts as your attempt even if you close the browser. If
          your time expires the paper is submitted for you.
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
          I have read the instructions, I am sitting this examination alone, and I consent
          to webcam and browser-activity monitoring for its duration.
        </span>
      </label>

      <div className="mt-6 flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onStart} loading={starting} disabled={!agreed}>
          {card.session_status === "in_progress" ? "Resume examination" : "Start examination"}
          <IconArrowRight size={15} />
        </Button>
      </div>

      {!agreed && (
        <p className="mt-2 flex items-center justify-end gap-1.5 text-[12px] text-ink-muted">
          <IconAlert size={13} />
          Confirm the declaration to begin.
        </p>
      )}
    </Card>
  );
}
