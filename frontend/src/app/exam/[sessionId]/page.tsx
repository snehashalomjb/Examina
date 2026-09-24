"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { Mark } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import {
  Alert,
  Badge,
  Button,
  Card,
  Textarea,
  cx,
  formatDuration,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { LiveBroadcaster } from "@/lib/liveBroadcast";
import { LOCALE_NAMES, type Locale } from "@/lib/locale";
import { ProctorEngine, type ProctorStatus } from "@/lib/proctor";
import type { ExamSession, HeartbeatOut, PaperQuestion, SessionSection } from "@/lib/types";
import { QUESTION_TYPE_LABEL as TYPE_LABEL } from "@/lib/types";
import { countWords, wordState } from "@/lib/words";

type SaveState = "idle" | "saving" | "saved" | "error";

const HEARTBEAT_MS = 30_000;
const AUTOSAVE_DEBOUNCE_MS = 800;

const QUESTION_TYPE_KEYS = new Set([
  "mcq",
  "multi_select",
  "true_false",
  "fill_blank",
  "numerical",
  "short_answer",
  "long_answer",
  "image_upload",
  "passage",
  "coding",
]);

export default function ExamRunner() {
  const t = useTranslations("examRunner");
  const { user, booting } = useRequireAuth(["candidate"]);
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [session, setSession] = useState<ExamSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [answers, setAnswers] = useState<Record<string, { options: string[]; text: string; imageUrl: string | null }>>({});
  const [reviewFlags, setReviewFlags] = useState<Set<string>>(new Set());
  const [warnings, setWarnings] = useState<string[]>([]);
  /** Severity of the most recent event, driving the 🟢/🟡/🔴 status dot. */
  const [lastSeverity, setLastSeverity] = useState<"info" | "warning" | "critical">("info");
  /** Brief red outline around the content area on a high-risk event - not a permanent state. */
  const [riskFlash, setRiskFlash] = useState(false);
  const riskFlashTimer = useRef<number | null>(null);
  const [proctor, setProctor] = useState<ProctorStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [finished, setFinished] = useState<string | null>(null);
  /** Set when the exam was closed *for* the candidate, so the screen says why. */
  const [lockedReason, setLockedReason] = useState<string | null>(null);
  const [inFullscreen, setInFullscreen] = useState(false);
  /** False until the candidate has entered fullscreen once, so the gate can differ. */
  const [fullscreenEverEntered, setFullscreenEverEntered] = useState(false);
  const [clearTarget, setClearTarget] = useState<PaperQuestion | null>(null);
  const [switchingLocale, setSwitchingLocale] = useState(false);
  const [localeNotice, setLocaleNotice] = useState<string | null>(null);

  const examToken = useRef<string | null>(null);
  const engine = useRef<ProctorEngine | null>(null);
  const broadcaster = useRef<LiveBroadcaster | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const saveTimers = useRef<Record<string, number>>({});
  /**
   * The payload behind each debounced save, kept so it can be forced out early.
   *
   * Without this, "answers are saved before automatic submission" would be a hope: a
   * candidate who types and immediately switches tabs has their last edit sitting in a
   * timer, and the server can submit the paper before it fires.
   */
  const pendingSaves = useRef<
    Record<string, { selected_option_ids?: string[]; text_answer?: string }>
  >({});

  /* ------------------------------------------------------------ load paper */
  useEffect(() => {
    if (!user || !sessionId) return;
    (async () => {
      try {
        const data = await api.get<ExamSession>(`/sessions/${sessionId}`);
        examToken.current = data.exam_token;
        setSession(data);
        setRemaining(data.seconds_remaining);
        // Restore answers + review flags
        const answerMap: Record<string, { options: string[]; text: string; imageUrl: string | null }> = {};
        const flags = new Set<string>();
        data.questions.forEach((q) => {
          answerMap[q.question_id] = {
            options: q.saved_option_ids,
            text: q.saved_text ?? "",
            imageUrl: q.saved_image_url,
          };
          if (q.is_review_flagged) flags.add(q.question_id);
        });
        setAnswers(answerMap);
        setReviewFlags(flags);
        // Set first section active
        if (data.sections.length > 0) setActiveSection(data.sections[0].id);
        if (data.status !== "in_progress") {
          setFinished(t("session_already_status", { status: data.status }));
        }
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.message : t("load_session_failed"));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, sessionId]);

  /**
   * Switch the displayed language mid-exam. Re-fetches the same frozen paper rendered
   * in a different locale - question/option ids, marks, the timer, the session, and
   * every saved answer are untouched: `answers` state (keyed by question_id) never gets
   * cleared here, and the server's `_build_paper` merges the candidate's real answers
   * back in regardless of locale. Only the displayed text changes.
   */
  const changeExamLocale = useCallback(
    async (locale: string) => {
      if (!sessionId || switchingLocale) return;
      setSwitchingLocale(true);
      try {
        const data = await api.get<ExamSession>(`/sessions/${sessionId}?lang=${locale}`);
        examToken.current = data.exam_token ?? examToken.current;
        setSession(data);
        setLocaleNotice(
          data.locale !== locale
            ? t("translation_unavailable")
            : null,
        );
      } catch (err) {
        toast(err instanceof ApiError ? err.message : t("switch_language_failed"), "rose");
      } finally {
        setSwitchingLocale(false);
      }
    },
    [sessionId, switchingLocale, t],
  );

  /* -------------------------------------------------------------- proctoring */
  useEffect(() => {
    if (!session || session.status !== "in_progress" || !examToken.current) return;
    if (engine.current) return;
    if (!videoRef.current || !canvasRef.current) return;

    const instance = new ProctorEngine({
      sessionId: session.session_id,
      examToken: examToken.current,
      config: session.proctor_config,
      callbacks: {
        onStatus: (status) => {
          setProctor(status);
          setInFullscreen(status.inFullscreen);
        },
        onWarnings: (incoming) => setWarnings(incoming),
        onEvent: (_type, severity) => {
          setLastSeverity(severity);
          if (severity !== "critical") return;
          setRiskFlash(true);
          if (riskFlashTimer.current) window.clearTimeout(riskFlashTimer.current);
          riskFlashTimer.current = window.setTimeout(() => setRiskFlash(false), 2500);
        },
        // Fires before the violation reaches the server, which is what makes the
        // ordering "answers first, then the event, then the server's decision".
        onFocusViolation: flushPendingSaves,
        onAutoSubmitted: (reason) => {
          setLockedReason(reason);
          setFinished(reason);
          toast(reason, "rose");
          broadcaster.current?.stop();
          broadcaster.current = null;
        },
        onTerminated: (reason) => {
          setLockedReason(reason);
          setFinished(reason);
          toast(reason, "rose");
          broadcaster.current?.stop();
          broadcaster.current = null;
        },
      },
    });
    engine.current = instance;
    void instance.start(videoRef.current, canvasRef.current).then(() => {
      // Broadcasting reuses the exact stream ProctorEngine already opened for vision -
      // no second camera permission prompt, and nothing to send if the camera never
      // started (a denied/unavailable camera just means no live tile for this session).
      const stream = instance.getMediaStream();
      if (stream && examToken.current) {
        const live = new LiveBroadcaster({
          sessionId: session.session_id,
          examToken: examToken.current,
          stream,
        });
        broadcaster.current = live;
        live.start();
      }
    });

    return () => {
      void instance.flush().finally(() => instance.stop());
      engine.current = null;
      broadcaster.current?.stop();
      broadcaster.current = null;
      if (riskFlashTimer.current) window.clearTimeout(riskFlashTimer.current);
    };
    // flushPendingSaves is stable via useCallback on persist, which only depends on the
    // session id - re-creating the engine on every answer edit would be a disaster.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  /* ------------------------------------------------------------- countdown */
  useEffect(() => {
    if (!session || finished) return;
    const tick = window.setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(tick);
  }, [session, finished]);

  /* ------------------------------------------ heartbeat: server owns the clock */
  useEffect(() => {
    if (!session || session.status !== "in_progress" || finished) return;

    async function beat() {
      if (!examToken.current) return;
      try {
        const data = await api.post<HeartbeatOut>(
          `/sessions/${sessionId}/heartbeat`,
          undefined,
          { examToken: examToken.current },
        );
        setRemaining(data.seconds_remaining);
        if (data.exam_token) {
          examToken.current = data.exam_token;
          engine.current?.setExamToken(data.exam_token);
          broadcaster.current?.setExamToken(data.exam_token);
        }
        if (data.warnings.length) setWarnings(data.warnings);
        if (data.status !== "in_progress") {
          setFinished(
            data.status === "auto_submitted"
              ? t("time_expired_auto_submitted")
              : t("session_is_status", { status: data.status }),
          );
        }
      } catch {
        /* transient - the next beat will correct it */
      }
    }

    const timer = window.setInterval(() => void beat(), HEARTBEAT_MS);
    return () => window.clearInterval(timer);
  }, [session, sessionId, finished, t]);

  /* ------------------------------------------------- time-up: submit for them */
  useEffect(() => {
    if (!session || finished || remaining > 0) return;
    void submitExam(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, session, finished]);

  /* ------------------------------------------------------------- fullscreen
   *
   * Enforced rather than requested. The old behaviour asked for fullscreen on the first
   * click and then let the exam carry on happily in a window, which made "the exam runs
   * in fullscreen" a suggestion. Now the paper is covered whenever fullscreen is not
   * active, and only a user gesture can lift the cover - the browser will not grant
   * fullscreen any other way.
   */
  useEffect(() => {
    const sync = () => {
      const inside = Boolean(document.fullscreenElement);
      setInFullscreen(inside);
      if (inside) setFullscreenEverEntered(true);
    };
    sync();
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);

  const requestFullscreen = useCallback(async () => {
    // Through the engine when it is up, so its own state stays in step; directly
    // otherwise, because the gate is shown before the camera has finished starting.
    if (engine.current) {
      await engine.current.enterFullscreen();
    } else {
      try {
        await document.documentElement.requestFullscreen?.();
      } catch {
        /* the candidate can press the button again */
      }
    }
    const inside = Boolean(document.fullscreenElement);
    setInFullscreen(inside);
    if (inside) setFullscreenEverEntered(true);
  }, []);

  useEffect(() => {
    document.body.classList.add("exam-mode");
    return () => document.body.classList.remove("exam-mode");
  }, []);

  /**
   * Navigation lock while the exam is live: the backend is the real gate (any write
   * against a closed/expired session 409s), but a candidate should never even see the
   * dashboard flash behind the back button. Traps back/forward on this URL, and warns
   * on refresh/close so an accidental reload doesn't feel like the exam vanished.
   */
  useEffect(() => {
    if (!session || session.status !== "in_progress" || finished) return;

    const trap = () => window.history.pushState(null, "", window.location.href);
    trap();
    const onPopState = () => {
      trap();
      toast(t("cannot_leave_exam"), "amber");
    };
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("popstate", onPopState);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      window.removeEventListener("popstate", onPopState);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [session, finished, t]);

  /* ---------------------------------------------------------------- saving */
  const persist = useCallback(
    async (questionId: string, payload: { selected_option_ids?: string[]; text_answer?: string }) => {
      if (!examToken.current) return;
      setSaveState("saving");
      try {
        await api.put(`/sessions/${sessionId}/answers/${questionId}`, payload, {
          examToken: examToken.current,
        });
        setSaveState("saved");
      } catch (err) {
        setSaveState("error");
        if (err instanceof ApiError && err.status === 409) {
          setFinished(err.message);
        }
      } finally {
        delete pendingSaves.current[questionId];
      }
    },
    [sessionId],
  );

  const queueSave = useCallback(
    (questionId: string, payload: { selected_option_ids?: string[]; text_answer?: string }) => {
      pendingSaves.current[questionId] = payload;
      window.clearTimeout(saveTimers.current[questionId]);
      saveTimers.current[questionId] = window.setTimeout(
        () => void persist(questionId, payload),
        AUTOSAVE_DEBOUNCE_MS,
      );
    },
    [persist],
  );

  /** Write every debounced edit now, and wait for it. */
  const flushPendingSaves = useCallback(async () => {
    const outstanding = Object.entries(pendingSaves.current);
    if (!outstanding.length) return;
    for (const [questionId] of outstanding) {
      window.clearTimeout(saveTimers.current[questionId]);
    }
    await Promise.allSettled(
      outstanding.map(([questionId, payload]) => persist(questionId, payload)),
    );
  }, [persist]);

  function chooseOption(question: PaperQuestion, optionId: string) {
    setAnswers((prev) => {
      const existing = prev[question.question_id] ?? { options: [], text: "", imageUrl: null };
      const next =
        question.question_type === "mcq" || question.question_type === "true_false"
          ? [optionId]
          : existing.options.includes(optionId)
            ? existing.options.filter((id) => id !== optionId)
            : [...existing.options, optionId];

      void persist(question.question_id, { selected_option_ids: next });
      return { ...prev, [question.question_id]: { ...existing, options: next } };
    });
  }

  function writeText(question: PaperQuestion, text: string) {
    setAnswers((prev) => ({
      ...prev,
      [question.question_id]: {
        ...(prev[question.question_id] ?? { options: [], imageUrl: null }),
        options: prev[question.question_id]?.options ?? [],
        imageUrl: prev[question.question_id]?.imageUrl ?? null,
        text,
      },
    }));

    if (wordState(countWords(text), question) === "over") {
      window.clearTimeout(saveTimers.current[question.question_id]);
      setSaveState("error");
      return;
    }
    queueSave(question.question_id, { text_answer: text });
  }

  async function uploadImage(question: PaperQuestion, file: File) {
    if (!examToken.current) return;
    setSaveState("saving");
    const form = new FormData();
    form.append("file", file);
    try {
      await api.upload(`/sessions/${sessionId}/answers/${question.question_id}/image`, form, {
        examToken: examToken.current,
      });
      setAnswers((prev) => ({
        ...prev,
        [question.question_id]: {
          ...(prev[question.question_id] ?? { options: [], text: "" }),
          options: prev[question.question_id]?.options ?? [],
          text: prev[question.question_id]?.text ?? "",
          imageUrl: URL.createObjectURL(file),
        },
      }));
      setSaveState("saved");
      toast(t("answer_image_uploaded"), "mint");
    } catch (err) {
      setSaveState("error");
      toast(err instanceof ApiError ? err.message : t("upload_failed"), "rose");
    }
  }

  /* ------------------------------------------------------ mark for review */
  async function toggleReview(questionId: string) {
    if (!examToken.current) return;
    try {
      const resp = await api.put<{ is_review_flagged: boolean }>(
        `/sessions/${sessionId}/questions/${questionId}/review-flag`,
        undefined,
        { examToken: examToken.current },
      );
      setReviewFlags((prev) => {
        const next = new Set(prev);
        if (resp.is_review_flagged) next.add(questionId);
        else next.delete(questionId);
        return next;
      });
    } catch {
      toast(t("review_flag_failed"), "rose");
    }
  }

  /* --------------------------------------------------------- clear answer */
  async function clearAnswer(question: PaperQuestion) {
    if (!examToken.current) return;
    setSaveState("saving");
    try {
      await api.delete(`/sessions/${sessionId}/answers/${question.question_id}`, {
        examToken: examToken.current,
      });
      setAnswers((prev) => ({
        ...prev,
        [question.question_id]: { options: [], text: "", imageUrl: null },
      }));
      setSaveState("saved");
      setClearTarget(null);
      toast(t("answer_cleared"), "mint");
    } catch {
      setSaveState("error");
      toast(t("clear_answer_failed"), "rose");
    }
  }

  /* -------------------------------------------------------------- submitting */
  async function submitExam(auto = false) {
    if (submitting || finished || !examToken.current) return;
    setSubmitting(true);
    try {
      await engine.current?.flush();
      const result = await api.post<{ message: string }>(
        `/sessions/${sessionId}/submit`,
        undefined,
        { examToken: examToken.current },
      );
      engine.current?.stop();
      broadcaster.current?.stop();
      broadcaster.current = null;
      setFinished(auto ? t("time_expired_paper_submitted") : result.message);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFinished(err.message);
      } else {
        toast(err instanceof ApiError ? err.message : t("submit_failed"), "rose");
      }
    } finally {
      setSubmitting(false);
      setConfirming(false);
    }
  }

  /* ------------------------------------------------------------------ views */
  const answeredCount = useMemo(
    () =>
      Object.values(answers).filter((a) => a.options.length > 0 || a.text.trim() || a.imageUrl)
        .length,
    [answers],
  );

  /* Visible questions: if sections exist, filter to active section */
  const visibleQuestions = useMemo(() => {
    if (!session) return [];
    if (session.sections.length === 0 || !activeSection) return session.questions;
    const activeQuestionIds = new Set(
      session.sections.find((s) => s.id === activeSection)?.question_ids ?? [],
    );
    return session.questions.filter((q) => activeQuestionIds.has(q.question_id));
  }, [session, activeSection]);

  /* Tell the engine which question is on screen, so a proctoring event can be tied to it. */
  useEffect(() => {
    const q = visibleQuestions[current] ?? session?.questions[current];
    engine.current?.setCurrentQuestionId(q?.question_id);
  }, [current, visibleQuestions, session]);

  if (booting || (!session && !loadError)) return <Splash label={t("loading_paper")} />;

  if (loadError) {
    return (
      <CentredNotice
        title={t("exam_open_failed_title")}
        body={loadError}
        action={
          <Button onClick={() => router.replace("/dashboard/candidate")}>{t("back_to_dashboard")}</Button>
        }
      />
    );
  }

  if (finished && session) {
    // A paper closed by the proctoring rule is still a submitted paper. It says what
    // happened and that the answers were kept, and it does not pronounce on the
    // candidate - that is the examiner's call, made later, on the evidence.
    return (
      <CentredNotice
        title={lockedReason ? t("exam_closed_submitted_title") : t("exam_submitted_title")}
        body={lockedReason ?? finished}
        detail={lockedReason ? t("exam_closed_detail") : t("exam_submitted_detail")}
        action={
          <Button onClick={() => router.replace("/dashboard/candidate")}>{t("back_to_dashboard")}</Button>
        }
      />
    );
  }

  if (!session) return null;

  /* The exam-window rule, as the candidate experiences it. The counts come from the
     server (via the proctor engine and the heartbeat), so a reload does not reset
     them. */
  const violationLimit = Number(session.proctor_config.max_focus_violations ?? 3);
  const violationCount = proctor?.focusViolations ?? 0;
  const violationsLeft = proctor?.focusViolationsLeft ?? -1;
  const finalWarning = violationLimit > 0 && violationsLeft === 1;
  const mustReturnToFullscreen =
    Boolean(session.proctor_config.require_fullscreen) && !inFullscreen && !finished;

  const question = visibleQuestions[current] ?? session.questions[current];
  const answer = answers[question.question_id] ?? { options: [], text: "", imageUrl: null };
  const lowTime = remaining <= 300;
  const criticalTime = remaining <= 60;
  const isReviewing = reviewFlags.has(question.question_id);
  const isAnswered = answer.options.length > 0 || answer.text.trim() || answer.imageUrl;

  return (
    <div className="flex h-screen flex-col bg-paper">
      {/* Live camera - pinned to the bottom-right corner of the exam window itself, above
          everything else, so it stays put across every question and never depends on
          the palette sidebar being open. Not top-left: that is where the question palette
          sits, and the tile hid its first buttons. */}
      <div className="pointer-events-none fixed bottom-4 right-4 z-40 w-28 sm:w-32">
        <WebcamPreview
          videoRef={videoRef}
          canvasRef={canvasRef}
          status={proctor}
          enabled={session.proctor_config.webcam_enabled}
        />
      </div>

      {/* ------------------------------------------------- the fullscreen gate
       *
       * Covers the paper whenever fullscreen is required and not active. The button is
       * the user gesture the browser insists on before it will grant fullscreen, so
       * this is not merely a nag - there is no way to re-enter without it.
       */}
      {mustReturnToFullscreen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-ink/95 p-6 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[16px] border border-line bg-surface p-6 text-center shadow-2xl">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-amber-soft text-[22px]">
              ⛶
            </div>
            <h2 className="text-[17px] font-bold tracking-tight text-ink">
              {fullscreenEverEntered ? t("fullscreen_return_title") : t("fullscreen_required_title")}
            </h2>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
              {fullscreenEverEntered ? t("fullscreen_left_body") : t("fullscreen_intro_body")}
            </p>

            {violationLimit > 0 && (
              <p
                className={cx(
                  "mt-3 rounded-[10px] px-3 py-2 text-[12.5px]",
                  violationsLeft === 1
                    ? "bg-rose-soft text-rose-ink"
                    : "bg-sunken text-ink-soft",
                )}
              >
                {fullscreenEverEntered ? (
                  violationsLeft === 1 ? (
                    <>
                      <span className="font-semibold">{t("final_warning_label")}</span>{" "}
                      {t("final_warning_body")}
                    </>
                  ) : (
                    <>
                      {t.rich("times_left_exam", {
                        count: violationCount,
                        limit: violationLimit,
                        b: (chunks) => <span className="font-semibold">{chunks}</span>,
                      })}
                    </>
                  )
                ) : (
                  <>{t("leave_allowance", { limit: violationLimit })}</>
                )}
              </p>
            )}

            <Button className="mt-5 w-full" onClick={() => void requestFullscreen()}>
              {fullscreenEverEntered ? t("return_to_fullscreen") : t("enter_fullscreen_begin")}
            </Button>
            <p className="mt-2 text-[11.5px] text-ink-muted">
              {t("answers_saved_now")}
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------ top bar */}
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line px-4 py-2.5 lg:px-6"
        style={{
          background: "rgba(248,249,252,0.95)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}>
        {/* Accent top line */}
        <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-accent to-transparent opacity-50" />
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px]"
            style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.12), rgba(139,92,246,0.08))", border: "1px solid rgba(99,102,241,0.2)" }}>
            <Mark size={18} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-bold tracking-tight text-ink">
              {session.exam_title}
            </p>
            <p className="text-[11px] text-ink-muted">
              {t("answered_progress", { answered: answeredCount, total: session.questions.length })}
              <span className="mx-1.5 opacity-40">·</span>
              {t("marks_count", { count: session.total_marks })}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {session.available_languages.length > 1 && (
            <ExamLanguageSelector
              locale={session.locale}
              languages={session.available_languages}
              busy={switchingLocale}
              onChange={changeExamLocale}
            />
          )}
          {/* Hidden on phones: with the timer and Submit they overflow a 390px header and
              push Submit off-screen. The corner webcam tile still shows camera status. */}
          <div className="hidden items-center gap-3 sm:flex">
            <SaveIndicator state={saveState} />
            <ProctorPill status={proctor} enabled={session.proctor_config.webcam_enabled} severity={lastSeverity} />
          </div>
          {/* Premium timer */}
          <div
            className={cx(
              "rounded-[10px] border px-2.5 py-1.5 text-center tabular-nums transition-all duration-300 sm:px-3 sm:py-2",
              criticalTime
                ? "border-rose/40 bg-rose-soft animate-[pulse-ring-alert_1.1s_ease-out_infinite]"
                : lowTime
                  ? "border-amber/30 bg-amber-soft"
                  : "border-accent/20 bg-accent-soft/30",
            )}
          >
            <p className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-ink-muted">{t("time_left")}</p>
            <p
              className={cx(
                "text-[18px] font-bold leading-tight tabular-nums tracking-tight",
                criticalTime ? "text-rose" : lowTime ? "text-amber" : "text-accent",
              )}
            >
              {formatDuration(remaining)}
            </p>
          </div>
          <Button size="sm" onClick={() => setConfirming(true)}
            style={{ background: "linear-gradient(135deg, #4f46e5, #6366f1)", color: "white", border: "none", boxShadow: "0 2px 8px -2px rgba(79,70,229,0.4)" }}>
            {t("submit")}
          </Button>
        </div>
      </header>

      {/* ------------------------------------------------ section tabs */}
      {session.sections.length > 0 && (
        <SectionTabs
          sections={session.sections}
          activeSection={activeSection}
          answers={answers}
          onSelect={(id) => {
            setActiveSection(id);
            setCurrent(0);
          }}
        />
      )}

      {localeNotice && (
        <div className="shrink-0 border-b border-amber/25 bg-amber-soft px-4 py-2 lg:px-6">
          <p className="text-[12.5px] font-medium text-amber">{localeNotice}</p>
        </div>
      )}
      {warnings.length > 0 && (
        <div
          className={cx(
            "shrink-0 border-b px-4 py-2 lg:px-6",
            // One violation left reads as red, not amber. The step before losing the
            // sitting is the one that has to be impossible to skim past.
            finalWarning
              ? "border-rose/30 bg-rose-soft"
              : "border-amber/25 bg-amber-soft",
          )}
        >
          <p
            className={cx(
              "text-[12.5px] font-medium",
              finalWarning ? "text-rose-ink" : "text-amber",
            )}
          >
            {finalWarning && <span className="font-bold">⚠ </span>}
            {warnings.join(" ")}
          </p>
        </div>
      )}
      {proctor?.lastError && (
        <div className="shrink-0 border-b border-rose/25 bg-rose-soft px-4 py-2 lg:px-6">
          <p className="text-[12.5px] text-rose">{proctor.lastError}</p>
        </div>
      )}

      {/* --------------------------------------------------------------- body */}
      <div
        className={cx(
          "flex min-h-0 flex-1 flex-col lg:flex-row transition-shadow duration-300",
          // A high-risk event outlines the content area briefly and fades on its own -
          // the interface must never go permanently red, only flag the moment.
          riskFlash && "ring-4 ring-inset ring-rose/70",
        )}
      >
        {/* Palette */}
        <aside className="flex shrink-0 flex-col border-b border-line bg-surface p-3 lg:w-[228px] lg:border-b-0 lg:border-r lg:p-4">
          <div className="flex items-center justify-between gap-3 lg:block">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-muted lg:mb-3">
              {t("questions_heading")}
            </p>
            <button
              type="button"
              onClick={() => setPaletteOpen((open) => !open)}
              aria-expanded={paletteOpen}
              className="shrink-0 rounded-[8px] border border-line px-2.5 py-1 text-[12px] font-medium text-ink-soft transition hover:bg-sunken lg:hidden"
            >
              {paletteOpen
                ? t("hide")
                : t("position_of", { current: current + 1, total: visibleQuestions.length })}
            </button>
          </div>

          <div className={cx("mt-3 lg:mt-0 lg:block", paletteOpen ? "block" : "hidden")}>
            <div className="grid grid-cols-8 gap-1.5 sm:grid-cols-10 lg:grid-cols-5">
              {visibleQuestions.map((q, index) => {
                const a = answers[q.question_id];
                const done = a && (a.options.length > 0 || a.text.trim() || a.imageUrl);
                const flagged = reviewFlags.has(q.question_id);
                const isCurrent = index === current;
                return (
                  <button
                    key={q.question_id}
                    onClick={() => {
                      setCurrent(index);
                      setPaletteOpen(false);
                    }}
                    title={
                      flagged && done
                        ? t("state_answered_review")
                        : flagged
                          ? t("state_marked_review")
                          : done
                            ? t("state_answered")
                            : t("state_not_answered")
                    }
                    className={cx(
                      "btn-press relative flex h-9 items-center justify-center rounded-[8px] border text-[12.5px] font-medium transition-all duration-200",
                      isCurrent
                        ? "border-accent bg-accent text-white shadow-[0_0_0_3px_rgba(79,70,229,0.18)] scale-[1.04]"
                        : done && flagged
                          ? "border-amber/40 bg-amber-soft text-amber hover:scale-[1.04]"
                          : done
                            ? "border-mint/30 bg-mint-soft text-mint hover:scale-[1.04]"
                            : flagged
                              ? "border-amber/30 bg-surface text-amber hover:scale-[1.04]"
                              : "border-line bg-surface text-ink-muted hover:border-line-strong hover:scale-[1.04]",
                    )}
                  >
                    {flagged && (
                      <span className="absolute -right-1 -top-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber text-[8px] text-white">
                        ⚑
                      </span>
                    )}
                    {index + 1}
                  </button>
                );
              })}
            </div>

            <div className="mt-4 space-y-1.5 text-[11.5px] text-ink-muted lg:mt-5">
              <Legend swatch="bg-accent" label={t("legend_current")} />
              <Legend swatch="bg-mint-soft border border-mint/30" label={t("state_answered")} />
              <Legend swatch="bg-surface border border-line" label={t("state_not_answered")} />
              <Legend swatch="bg-amber-soft border border-amber/30" label={t("state_marked_review")} />
              <Legend swatch="bg-amber-soft border border-amber/40" label={t("legend_answered_review")} icon="⚑" />
            </div>
          </div>
        </aside>

        {/* question pane */}
        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-6 lg:px-10">
          <div className="mx-auto max-w-3xl">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Badge tone="accent">
                {(() => {
                  const number =
                    (activeSection
                      ? session.questions.findIndex((q) => q.question_id === question.question_id)
                      : current) + 1;
                  return session.sections.length > 0
                    ? t("question_number_of", { number, total: session.questions.length })
                    : t("question_number", { number });
                })()}
              </Badge>
              <Badge>
                {QUESTION_TYPE_KEYS.has(question.question_type)
                  ? t(`qtype_${question.question_type}`)
                  : TYPE_LABEL[question.question_type]}
              </Badge>
              <Badge tone="mint">{t("marks_count", { count: question.marks })}</Badge>
              {question.negative_marks > 0 && (
                <Badge tone="rose">{t("negative_if_wrong", { marks: question.negative_marks })}</Badge>
              )}
              {isReviewing && <Badge tone="amber">⚑ {t("state_marked_review")}</Badge>}
            </div>

            {/* Passage header (sticky text for passage children) */}
            {question.parent_question_id && (
              <PassageContext
                parentId={question.parent_question_id}
                questions={session.questions}
              />
            )}

            <Card>
              {question.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={question.image_url}
                  alt={t("question_figure_alt")}
                  className="mb-4 max-h-[300px] w-full rounded-[8px] object-contain bg-sunken"
                />
              )}
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink">
                {question.body}
              </p>

              <div className="mt-5">
                <QuestionRenderer
                  question={question}
                  answer={answer}
                  onChoose={(optionId) => chooseOption(question, optionId)}
                  onWrite={(text) => writeText(question, text)}
                  onUpload={(file) => void uploadImage(question, file)}
                />
              </div>
            </Card>

            {/* Action row */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  const hasAnswer = isAnswered;
                  if (!hasAnswer) {
                    void clearAnswer(question);
                  } else {
                    // For rich answers ask for confirmation
                    if (question.question_type === "long_answer" || question.question_type === "image_upload") {
                      setClearTarget(question);
                    } else {
                      void clearAnswer(question);
                    }
                  }
                }}
                disabled={!isAnswered}
              >
                {t("clear")}
              </Button>
              <Button
                size="sm"
                variant={isReviewing ? "secondary" : "ghost"}
                onClick={() => void toggleReview(question.question_id)}
              >
                {isReviewing ? `⚑ ${t("reviewing")}` : t("mark_for_review")}
              </Button>
            </div>

            <div className="mt-5 flex items-center justify-between gap-3">
              <Button
                variant="secondary"
                onClick={() => setCurrent((i) => Math.max(0, i - 1))}
                disabled={current === 0}
              >
                {t("previous")}
              </Button>

              <div className="flex gap-2 lg:hidden">
                <span className="self-center text-[12px] text-ink-muted">
                  {current + 1} / {visibleQuestions.length}
                </span>
              </div>

              {current === visibleQuestions.length - 1 ? (
                <Button onClick={() => setConfirming(true)}>{t("review_and_submit")}</Button>
              ) : (
                <Button onClick={() => setCurrent((i) => Math.min(visibleQuestions.length - 1, i + 1))}>
                  {t("next")}
                </Button>
              )}
            </div>
          </div>
        </main>
      </div>

      {confirming && (
        <ConfirmSubmit
          total={session.questions.length}
          answered={answeredCount}
          remaining={remaining}
          submitting={submitting}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void submitExam()}
        />
      )}

      {clearTarget && (
        <ConfirmClear
          onCancel={() => setClearTarget(null)}
          onConfirm={() => void clearAnswer(clearTarget)}
        />
      )}
    </div>
  );
}

/* ================================================================ sub-components */

/* ---------------------------------------------------------- section tabs */
function SectionTabs({
  sections,
  activeSection,
  answers,
  onSelect,
}: {
  sections: SessionSection[];
  activeSection: string | null;
  answers: Record<string, { options: string[]; text: string; imageUrl: string | null }>;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-1.5 overflow-x-auto border-b border-line px-4 py-2.5 lg:px-6"
      style={{ background: "rgba(248,249,252,0.9)" }}>
      {sections.map((sec) => {
        const answered = sec.question_ids.filter((qid) => {
          const a = answers[qid];
          return a && (a.options.length > 0 || a.text.trim() || a.imageUrl);
        }).length;
        const isActive = sec.id === activeSection;
        const pct = Math.round((answered / Math.max(sec.question_ids.length, 1)) * 100);
        return (
          <button
            key={sec.id}
            onClick={() => onSelect(sec.id)}
            className={cx(
              "flex shrink-0 items-center gap-2 rounded-[9px] px-3 py-1.5 text-[12.5px] font-semibold transition-all duration-200",
              isActive
                ? "text-white shadow-sm"
                : "text-ink-soft hover:bg-sunken hover:text-ink",
            )}
            style={isActive ? {
              background: "linear-gradient(135deg, #4f46e5, #6366f1)",
              boxShadow: "0 2px 8px -2px rgba(79,70,229,0.35)",
            } : {}}
          >
            {sec.name}
            <span
              className={cx(
                "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                isActive ? "bg-white/20 text-white" : pct === 100 ? "bg-green/15 text-green" : "bg-sunken text-ink-muted",
              )}
            >
              {answered}/{sec.question_ids.length}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ----------------------------------------------------- question renderer */
function QuestionRenderer({
  question,
  answer,
  onChoose,
  onWrite,
  onUpload,
}: {
  question: PaperQuestion;
  answer: { options: string[]; text: string; imageUrl: string | null };
  onChoose: (optionId: string) => void;
  onWrite: (text: string) => void;
  onUpload: (file: File) => void;
}) {
  const t = useTranslations("examRunner");
  const qt = question.question_type;

  if (qt === "mcq" || qt === "multi_select") {
    return (
      <OptionList
        question={question}
        answer={answer}
        onChoose={onChoose}
        multi={qt === "multi_select"}
      />
    );
  }

  if (qt === "true_false") {
    const spec = question.spec as { true_label?: string; false_label?: string } | null;
    const trueLabel = spec?.true_label ?? t("true_label");
    const falseLabel = spec?.false_label ?? t("false_label");
    const tfOptions = question.options.length > 0
      ? question.options
      : [{ id: "tf-true", text: trueLabel }, { id: "tf-false", text: falseLabel }];

    return (
      <div className="flex gap-3">
        {tfOptions.map((opt) => {
          const selected = answer.options.includes(opt.id);
          return (
            <button
              key={opt.id}
              onClick={() => onChoose(opt.id)}
              className={cx(
                "flex flex-1 items-center justify-center gap-2 rounded-[12px] border px-4 py-4 text-[15px] font-medium transition",
                selected
                  ? "border-accent bg-accent-soft text-accent-ink"
                  : "border-line hover:border-line-strong hover:bg-sunken text-ink",
              )}
            >
              <span className={cx(
                "flex h-5 w-5 items-center justify-center rounded-full border text-[11px] font-bold transition",
                selected ? "border-accent bg-accent text-white" : "border-line-strong text-ink-muted",
              )}>
                {selected ? "✓" : ""}
              </span>
              {opt.text}
            </button>
          );
        })}
      </div>
    );
  }

  if (qt === "fill_blank") {
    return (
      <div>
        <p className="mb-2 text-[12.5px] text-ink-muted">{t("fill_blank_hint")}</p>
        <input
          type="text"
          value={answer.text}
          onChange={(e) => onWrite(e.target.value)}
          placeholder={t("your_answer_placeholder")}
          className="w-full rounded-[10px] border border-line bg-surface px-4 py-3 text-[14.5px] text-ink outline-none placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/20 transition"
        />
      </div>
    );
  }

  if (qt === "numerical") {
    const spec = question.spec as { unit?: string | null } | null;
    return (
      <div>
        <p className="mb-2 text-[12.5px] text-ink-muted">{t("numerical_hint")}</p>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={answer.text}
            onChange={(e) => onWrite(e.target.value)}
            placeholder="0"
            step="any"
            className="w-48 rounded-[10px] border border-line bg-surface px-4 py-3 text-[14.5px] text-ink outline-none placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/20 transition"
          />
          {spec?.unit && (
            <span className="text-[13px] font-medium text-ink-muted">{spec.unit}</span>
          )}
        </div>
      </div>
    );
  }

  if (qt === "short_answer" || qt === "long_answer") {
    return (
      <div>
        <Textarea
          value={answer.text}
          onChange={(e) => onWrite(e.target.value)}
          rows={qt === "long_answer" ? 14 : 6}
          placeholder={
            qt === "long_answer" ? t("long_answer_placeholder") : t("short_answer_placeholder")
          }
        />
        <WordCounter text={answer.text} bounds={question} />
      </div>
    );
  }

  if (qt === "image_upload") {
    return (
      <ImageAnswer
        imageUrl={answer.imageUrl}
        onSelect={(file) => onUpload(file)}
      />
    );
  }

  if (qt === "passage") {
    const spec = question.spec as { passage_text?: string | null; source?: string | null } | null;
    return (
      <div className="rounded-[11px] border border-line bg-sunken/50 p-5">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          {t("passage_label")} {spec?.source ? `— ${spec.source}` : ""}
        </p>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">
          {spec?.passage_text ?? t("passage_default_text")}
        </p>
        <p className="mt-3 text-[12px] italic text-ink-muted">
          {t("passage_no_answer")}
        </p>
      </div>
    );
  }

  if (qt === "coding") {
    const spec = question.spec as {
      languages?: string[];
      sample_cases?: Array<{ input: string; output: string; explanation?: string | null }>;
      input_format?: string;
      output_format?: string;
      constraints?: string;
    } | null;
    const langs = spec?.languages ?? ["python"];
    return (
      <CodingRenderer
        answer={answer.text}
        languages={langs}
        spec={spec}
        onWrite={onWrite}
      />
    );
  }

  return (
    <p className="text-[13.5px] italic text-ink-muted">
      {t("unsupported_type", { type: qt })}
    </p>
  );
}

/* ---------------------------------------------------------- option list (MCQ / multi) */
function OptionList({
  question,
  answer,
  onChoose,
  multi,
}: {
  question: PaperQuestion;
  answer: { options: string[] };
  onChoose: (id: string) => void;
  multi: boolean;
}) {
  const t = useTranslations("examRunner");
  return (
    <div className="space-y-2">
      {multi && (
        <p className="mb-3 text-[12.5px] text-ink-muted">{t("select_all_that_apply")}</p>
      )}
      {question.options.map((option, index) => {
        const selected = answer.options.includes(option.id);
        return (
          <button
            key={option.id}
            onClick={() => onChoose(option.id)}
            className={cx(
              "flex w-full items-start gap-3 rounded-[11px] border px-4 py-3 text-left transition",
              selected
                ? "border-accent bg-accent-soft"
                : "border-line hover:border-line-strong hover:bg-sunken",
            )}
          >
            <span
              className={cx(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center border text-[11px] font-semibold",
                multi ? "rounded-[5px]" : "rounded-full",
                selected
                  ? "border-accent bg-accent text-white"
                  : "border-line-strong text-ink-muted",
              )}
            >
              {String.fromCharCode(65 + index)}
            </span>
            <span className="text-[14px] leading-relaxed text-ink">{option.text}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------------- coding renderer */
function CodingRenderer({
  answer,
  languages,
  spec,
  onWrite,
}: {
  answer: string;
  languages: string[];
  spec: {
    sample_cases?: Array<{ input: string; output: string; explanation?: string | null }>;
    input_format?: string;
    output_format?: string;
    constraints?: string;
  } | null;
  onWrite: (text: string) => void;
}) {
  const t = useTranslations("examRunner");
  const [lang, setLang] = useState(languages[0] ?? "python");

  // Embed the language choice in the answer text as a header comment
  function handleWrite(code: string) {
    onWrite(`[lang:${lang}]\n${code.replace(/^\[lang:[^\]]+\]\n?/, "")}`);
  }

  const codeBody = answer.replace(/^\[lang:[^\]]+\]\n?/, "");

  return (
    <div className="space-y-4">
      {(spec?.input_format || spec?.output_format || spec?.constraints) && (
        <div className="rounded-[10px] border border-line bg-sunken/60 p-4 text-[13px] space-y-2">
          {spec?.input_format && (
            <p><span className="font-semibold text-ink-muted">{t("input_label")}: </span>{spec.input_format}</p>
          )}
          {spec?.output_format && (
            <p><span className="font-semibold text-ink-muted">{t("output_label")}: </span>{spec.output_format}</p>
          )}
          {spec?.constraints && (
            <p><span className="font-semibold text-ink-muted">{t("constraints_label")}: </span>{spec.constraints}</p>
          )}
        </div>
      )}

      {spec?.sample_cases && spec.sample_cases.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{t("sample_cases")}</p>
          {spec.sample_cases.slice(0, 2).map((sc, i) => (
            <div key={i} className="grid gap-2 rounded-[9px] border border-line bg-surface p-3 text-[12.5px] sm:grid-cols-2">
              <div>
                <p className="mb-1 text-[10.5px] font-medium uppercase tracking-wide text-ink-muted">{t("input_label")}</p>
                <pre className="whitespace-pre-wrap font-mono text-ink">{sc.input}</pre>
              </div>
              <div>
                <p className="mb-1 text-[10.5px] font-medium uppercase tracking-wide text-ink-muted">{t("output_label")}</p>
                <pre className="whitespace-pre-wrap font-mono text-ink">{sc.output}</pre>
              </div>
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center gap-3">
          <p className="text-[12.5px] font-medium text-ink">{t("your_solution")}</p>
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="rounded-[8px] border border-line bg-surface px-2 py-1 text-[12.5px] text-ink outline-none focus:border-accent"
          >
            {languages.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <textarea
          value={codeBody}
          onChange={(e) => handleWrite(e.target.value)}
          rows={18}
          spellCheck={false}
          placeholder={t("code_placeholder", { language: lang })}
          className="w-full rounded-[10px] border border-line bg-[#1a1b26] px-4 py-3 font-mono text-[13px] leading-relaxed text-[#a9b1d6] outline-none placeholder:text-ink-muted/40 focus:border-accent/50 transition resize-y"
        />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------- passage context */
function PassageContext({
  parentId,
  questions,
}: {
  parentId: string;
  questions: PaperQuestion[];
}) {
  const parent = questions.find((q) => q.question_id === parentId);
  const spec = parent?.spec as { passage_text?: string | null } | null;
  const t = useTranslations("examRunner");
  const text = spec?.passage_text ?? parent?.body;
  if (!text) return null;
  return (
    <div className="mb-4 max-h-48 overflow-y-auto rounded-[11px] border border-accent/20 bg-accent-soft/30 p-4">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-accent-ink">
        {t("passage_read_before")}
      </p>
      <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">{text}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ pieces */
function Legend({ swatch, label, icon }: { swatch: string; label: string; icon?: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={cx("relative h-3 w-3 rounded-[4px]", swatch)}>
        {icon && (
          <span className="absolute -right-1 -top-1 text-[7px] leading-none">{icon}</span>
        )}
      </span>
      {label}
    </div>
  );
}

function SaveIndicator({ state }: { state: SaveState }) {
  const t = useTranslations("examRunner");
  const map = {
    idle: { text: t("save_ready"), tone: "text-ink-muted", dot: "bg-ink-muted" },
    saving: { text: t("save_saving"), tone: "text-accent-ink", dot: "bg-accent animate-pulse" },
    saved: { text: t("save_saved"), tone: "text-mint", dot: "bg-green" },
    error: { text: t("save_error"), tone: "text-rose", dot: "bg-rose" },
  } as const;
  const current = map[state];
  return (
    <span
      key={state}
      className={cx(
        "hidden items-center gap-1.5 text-[12px] font-medium transition-opacity duration-300 sm:inline-flex animate-fade",
        current.tone,
      )}
    >
      <span aria-hidden className={cx("h-[6px] w-[6px] rounded-full", current.dot)} />
      {current.text}
    </span>
  );
}

/**
 * The in-exam language selector. Only ever offers the languages the exam enabled (see
 * `ExamSessionOut.available_languages`) - never the full app-wide language list, so a
 * candidate never sees a language the examiner never translated anything into.
 */
function ExamLanguageSelector({
  locale,
  languages,
  busy,
  onChange,
}: {
  locale: string;
  languages: string[];
  busy: boolean;
  onChange: (locale: string) => void;
}) {
  const t = useTranslations("examRunner");
  return (
    <label className="flex items-center gap-1.5 rounded-full border border-line bg-white px-2.5 py-1.5 text-[12.5px] font-medium text-ink-soft">
      <span aria-hidden="true">🌐</span>
      <span className="sr-only">{t("language")}</span>
      <select
        aria-label={t("exam_language")}
        value={locale}
        disabled={busy}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer border-0 bg-transparent pr-1 text-[12.5px] font-medium text-ink-soft outline-none disabled:opacity-50"
      >
        {languages.map((code) => (
          <option key={code} value={code}>
            {LOCALE_NAMES[code as Locale] ?? code}
          </option>
        ))}
      </select>
    </label>
  );
}

const SEVERITY_DOT_CLASS: Record<"info" | "warning" | "critical", string> = {
  info: "status-dot status-dot-live",
  warning: "status-dot status-dot-warn",
  critical: "status-dot status-dot-alert is-pulsing",
};

function ProctorPill({
  status,
  enabled,
  severity,
}: {
  status: ProctorStatus | null;
  enabled: boolean;
  severity: "info" | "warning" | "critical";
}) {
  const t = useTranslations("examRunner");
  const dot = <span aria-hidden className={cx(SEVERITY_DOT_CLASS[severity], "mr-1.5 align-middle")} />;
  if (!enabled) return <Badge>{t("proctoring_off")}</Badge>;
  if (!status || !status.cameraReady) return <Badge tone="rose">{dot}{t("camera_off")}</Badge>;
  if (status.phoneDetected) return <Badge tone="rose">{dot}{t("phone_detected")}</Badge>;
  if (status.faceCount > 1) return <Badge tone="rose">{dot}{t("faces_count", { count: status.faceCount })}</Badge>;
  if (!status.facePresent) return <Badge tone="amber">{dot}{t("face_not_visible")}</Badge>;
  if (status.lookingAway) return <Badge tone="amber">{dot}{t("look_at_screen")}</Badge>;
  return <Badge tone="mint">{dot}{t("proctoring_active")}</Badge>;
}

function WebcamPreview({
  videoRef,
  canvasRef,
  status,
  enabled,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  status: ProctorStatus | null;
  enabled: boolean;
}) {
  const t = useTranslations("examRunner");
  const live = enabled && Boolean(status?.cameraReady);
  return (
    <div className="w-full rounded-[11px] border border-line bg-sunken p-1.5 shadow-md">
      <div className="relative overflow-hidden rounded-[9px] bg-ink/90">
        <video
          ref={videoRef}
          muted
          playsInline
          className="h-[92px] w-full scale-x-[-1] object-cover sm:h-[104px]"
        />
        <canvas ref={canvasRef} className="hidden" />
        {!enabled && (
          <div className="absolute inset-0 grid place-items-center text-[10px] text-white/70">
            {t("webcam_not_required")}
          </div>
        )}
        {live && (
          <div className="absolute left-1.5 top-1.5 flex items-center gap-1 rounded-full bg-black/55 px-1.5 py-0.5 backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-green animate-pulse" />
            <span className="text-[9px] font-bold uppercase tracking-wide text-white">{t("live")}</span>
          </div>
        )}
        {!live && enabled && (
          <div className="absolute left-1.5 top-1.5 rounded-full bg-black/55 px-1.5 py-0.5 backdrop-blur-sm">
            <span className="text-[9px] font-semibold text-white/80">
              {status?.visionMode === "degraded" ? t("recording") : t("connecting")}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function WordCounter({
  text,
  bounds,
}: {
  text: string;
  bounds: { min_words: number | null; max_words: number | null };
}) {
  const t = useTranslations("examRunner");
  const count = countWords(text);
  const state = wordState(count, bounds);

  /* Mirrors wordLabel() in lib/words, rendered through the translation catalogue. */
  let label: string;
  if (bounds.max_words != null) {
    const over = count - bounds.max_words;
    label = t("word_count_max", { count, max: bounds.max_words });
    if (over > 0) label += ` · ${t("words_over_limit", { over })}`;
  } else if (bounds.min_words != null && count > 0 && count < bounds.min_words) {
    label = `${t("word_count", { count })} · ${t("words_to_minimum", { remaining: bounds.min_words - count })}`;
  } else {
    label = t("word_count", { count });
  }

  return (
    <div className="mt-1.5 flex items-baseline justify-between gap-3">
      <p className="text-[11.5px] text-ink-muted">
        {bounds.min_words != null && state !== "over" && (
          <span>{t("minimum_words", { count: bounds.min_words })}</span>
        )}
        {state === "over" && (
          <span className="font-medium text-rose">
            {t("trim_answer")}
          </span>
        )}
      </p>
      <p
        className={cx(
          "shrink-0 text-right text-[11.5px] tabular-nums",
          state === "over" ? "font-medium text-rose" : "text-ink-muted",
        )}
      >
        {label}
      </p>
    </div>
  );
}

function ImageAnswer({
  imageUrl,
  onSelect,
}: {
  imageUrl: string | null;
  onSelect: (file: File) => void;
}) {
  const t = useTranslations("examRunner");
  const [isDragging, setIsDragging] = useState(false);
  const [cameraMode, setCameraMode] = useState(false);
  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const cameraVideoRef = useRef<HTMLVideoElement>(null);
  const captureCanvasRef = useRef<HTMLCanvasElement>(null);

  async function startCamera() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      setCameraStream(stream);
      if (cameraVideoRef.current) {
        cameraVideoRef.current.srcObject = stream;
        await cameraVideoRef.current.play();
      }
      setCameraMode(true);
    } catch {
      toast(t("camera_permission_denied"), "rose");
    }
  }

  function stopCamera() {
    cameraStream?.getTracks().forEach((track) => track.stop());
    setCameraStream(null);
    setCameraMode(false);
    setCapturedBlob(null);
  }

  function capturePhoto() {
    const video = cameraVideoRef.current;
    const canvas = captureCanvasRef.current;
    if (!video || !canvas) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) setCapturedBlob(blob);
    }, "image/jpeg", 0.9);
  }

  function confirmCapture() {
    if (!capturedBlob) return;
    const file = new File([capturedBlob], "camera-answer.jpg", { type: "image/jpeg" });
    onSelect(file);
    stopCamera();
  }

  if (cameraMode) {
    return (
      <div className="rounded-[12px] border border-line overflow-hidden">
        {capturedBlob ? (
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={URL.createObjectURL(capturedBlob)}
              alt={t("captured_preview_alt")}
              className="max-h-[360px] w-full object-contain bg-sunken"
            />
            <div className="flex gap-2 p-3">
              <Button size="sm" variant="secondary" onClick={() => setCapturedBlob(null)}>
                {t("retake")}
              </Button>
              <Button size="sm" onClick={confirmCapture}>
                {t("use_this_photo")}
              </Button>
              <Button size="sm" variant="ghost" onClick={stopCamera}>
                {t("cancel")}
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <video ref={cameraVideoRef} playsInline muted className="max-h-[360px] w-full object-cover bg-ink/90" />
            <canvas ref={captureCanvasRef} className="hidden" />
            <div className="flex gap-2 p-3">
              <Button size="sm" onClick={capturePhoto}>
                📷 {t("capture")}
              </Button>
              <Button size="sm" variant="ghost" onClick={stopCamera}>
                {t("cancel")}
              </Button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) onSelect(file);
        }}
      >
        <label
          className={cx(
            "flex cursor-pointer flex-col items-center justify-center rounded-[12px] border border-dashed px-6 py-8 text-center transition",
            isDragging
              ? "border-accent bg-accent-soft/50 scale-[1.01]"
              : "border-line-strong bg-sunken/50 hover:border-accent hover:bg-accent-soft/40",
          )}
        >
          <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[10px] border border-line bg-surface text-[20px]">
            📎
          </div>
          <span className="text-[13.5px] font-medium text-ink">
            {imageUrl ? t("replace_uploaded_answer") : t("drag_drop_upload")}
          </span>
          <span className="mt-1 text-[12px] text-ink-muted">{t("upload_formats")}</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onSelect(file);
            }}
          />
        </label>
      </div>

      <div className="mt-2 flex justify-center">
        <button
          type="button"
          onClick={startCamera}
          className="text-[12.5px] font-medium text-accent hover:underline"
        >
          📷 {t("use_camera_instead")}
        </button>
      </div>

      {imageUrl && (
        <div className="mt-4 overflow-hidden rounded-[12px] border border-line">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={imageUrl} alt={t("uploaded_answer_alt")} className="max-h-[420px] w-full object-contain bg-sunken" />
        </div>
      )}
    </div>
  );
}

function ConfirmSubmit({
  total,
  answered,
  remaining,
  submitting,
  onCancel,
  onConfirm,
}: {
  total: number;
  answered: number;
  remaining: number;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("examRunner");
  const unanswered = total - answered;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm">
      <Card className="animate-rise w-full max-w-md">
        <h2 className="text-[17px] font-semibold tracking-tight text-ink">{t("submit_paper_title")}</h2>
        <p className="mt-1.5 text-[13.5px] text-ink-soft">
          {t("cannot_reopen")}
        </p>

        <div className="mt-4 grid grid-cols-3 gap-3 rounded-[10px] bg-sunken/60 p-3 text-center">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">{t("state_answered")}</p>
            <p className="mt-0.5 text-[18px] font-semibold text-ink">{answered}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">{t("blank_label")}</p>
            <p className={cx("mt-0.5 text-[18px] font-semibold", unanswered ? "text-amber" : "text-ink")}>
              {unanswered}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">{t("time_left")}</p>
            <p className="mt-0.5 text-[18px] font-semibold tabular-nums text-ink">
              {formatDuration(remaining)}
            </p>
          </div>
        </div>

        {unanswered > 0 && (
          <div className="mt-4">
            <Alert tone="amber">
              {t("blank_warning", { count: unanswered })}
            </Alert>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            {t("keep_working")}
          </Button>
          <Button onClick={onConfirm} loading={submitting}>
            {t("submit_paper")}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ConfirmClear({
  onCancel,
  onConfirm,
}: {
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const t = useTranslations("examRunner");
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm">
      <Card className="animate-rise w-full max-w-sm">
        <h2 className="text-[16px] font-semibold tracking-tight text-ink">{t("clear_answer_title")}</h2>
        <p className="mt-1.5 text-[13.5px] text-ink-soft">
          {t("clear_answer_body")}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>{t("cancel")}</Button>
          <Button onClick={onConfirm}>{t("clear_answer")}</Button>
        </div>
      </Card>
    </div>
  );
}

function CentredNotice({
  title,
  body,
  detail,
  action,
}: {
  title: string;
  body: string;
  detail?: string;
  action: React.ReactNode;
}) {
  return (
    <div className="grid min-h-screen place-items-center px-5">
      <Card className="animate-rise w-full max-w-lg text-center">
        <div className="mx-auto mb-4 w-fit">
          <Mark size={36} />
        </div>
        <h1 className="text-[19px] font-semibold tracking-tight text-ink">{title}</h1>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-soft">{body}</p>
        {detail && <p className="mt-3 text-[12.5px] leading-relaxed text-ink-muted">{detail}</p>}
        <div className="mt-6 flex justify-center">{action}</div>
      </Card>
    </div>
  );
}
