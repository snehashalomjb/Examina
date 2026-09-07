"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";

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
import { ProctorEngine, type ProctorStatus } from "@/lib/proctor";
import type { ExamSession, HeartbeatOut, PaperQuestion, SessionSection } from "@/lib/types";
import { QUESTION_TYPE_LABEL as TYPE_LABEL } from "@/lib/types";
import { countWords, wordLabel, wordState } from "@/lib/words";

type SaveState = "idle" | "saving" | "saved" | "error";

const HEARTBEAT_MS = 30_000;
const AUTOSAVE_DEBOUNCE_MS = 800;

export default function ExamRunner() {
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
  const [proctor, setProctor] = useState<ProctorStatus | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [finished, setFinished] = useState<string | null>(null);
  const [clearTarget, setClearTarget] = useState<PaperQuestion | null>(null);

  const examToken = useRef<string | null>(null);
  const engine = useRef<ProctorEngine | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const saveTimers = useRef<Record<string, number>>({});

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
          setFinished(`This session is already ${data.status.replace("_", " ")}.`);
        }
      } catch (err) {
        setLoadError(err instanceof ApiError ? err.message : "Could not load this exam session.");
      }
    })();
  }, [user, sessionId]);

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
        onStatus: setProctor,
        onWarnings: (incoming) => setWarnings(incoming),
        onTerminated: (reason) => {
          setFinished(reason);
          toast(reason, "rose");
        },
      },
    });
    engine.current = instance;
    void instance.start(videoRef.current, canvasRef.current);

    return () => {
      void instance.flush().finally(() => instance.stop());
      engine.current = null;
    };
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
        }
        if (data.warnings.length) setWarnings(data.warnings);
        if (data.status !== "in_progress") {
          setFinished(
            data.status === "auto_submitted"
              ? "Your time expired and the exam was submitted automatically."
              : `This session is ${data.status.replace("_", " ")}.`,
          );
        }
      } catch {
        /* transient - the next beat will correct it */
      }
    }

    const timer = window.setInterval(() => void beat(), HEARTBEAT_MS);
    return () => window.clearInterval(timer);
  }, [session, sessionId, finished]);

  /* ------------------------------------------------- time-up: submit for them */
  useEffect(() => {
    if (!session || finished || remaining > 0) return;
    void submitExam(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining, session, finished]);

  /* ------------------------------------------------------------- fullscreen */
  useEffect(() => {
    if (!session?.proctor_config.require_fullscreen || finished) return;
    const enter = () => void document.documentElement.requestFullscreen?.().catch(() => {});
    window.addEventListener("click", enter, { once: true });
    return () => window.removeEventListener("click", enter);
  }, [session, finished]);

  useEffect(() => {
    document.body.classList.add("exam-mode");
    return () => document.body.classList.remove("exam-mode");
  }, []);

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
      }
    },
    [sessionId],
  );

  const queueSave = useCallback(
    (questionId: string, payload: { selected_option_ids?: string[]; text_answer?: string }) => {
      window.clearTimeout(saveTimers.current[questionId]);
      saveTimers.current[questionId] = window.setTimeout(
        () => void persist(questionId, payload),
        AUTOSAVE_DEBOUNCE_MS,
      );
    },
    [persist],
  );

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
      toast("Answer image uploaded", "mint");
    } catch (err) {
      setSaveState("error");
      toast(err instanceof ApiError ? err.message : "Upload failed", "rose");
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
      toast("Could not update review flag", "rose");
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
      toast("Answer cleared", "mint");
    } catch {
      setSaveState("error");
      toast("Could not clear answer", "rose");
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
      setFinished(auto ? "Your time expired and your paper was submitted." : result.message);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFinished(err.message);
      } else {
        toast(err instanceof ApiError ? err.message : "Could not submit", "rose");
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

  if (booting || (!session && !loadError)) return <Splash label="Loading your paper" />;

  if (loadError) {
    return (
      <CentredNotice
        title="This exam could not be opened"
        body={loadError}
        action={
          <Button onClick={() => router.replace("/dashboard/candidate")}>Back to dashboard</Button>
        }
      />
    );
  }

  if (finished && session) {
    return (
      <CentredNotice
        title="Your paper is in"
        body={finished}
        detail="Objective questions were scored on submission. Written answers go to an examiner for review — your result appears once it is published."
        action={
          <Button onClick={() => router.replace("/dashboard/candidate")}>Back to dashboard</Button>
        }
      />
    );
  }

  if (!session) return null;

  const question = visibleQuestions[current] ?? session.questions[current];
  const answer = answers[question.question_id] ?? { options: [], text: "", imageUrl: null };
  const lowTime = remaining <= 300;
  const criticalTime = remaining <= 60;
  const isReviewing = reviewFlags.has(question.question_id);
  const isAnswered = answer.options.length > 0 || answer.text.trim() || answer.imageUrl;

  return (
    <div className="flex h-screen flex-col bg-paper">
      {/* ------------------------------------------------------------ top bar */}
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-line bg-surface px-4 py-2.5 lg:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <Mark size={24} />
          <div className="min-w-0">
            <p className="truncate text-[13.5px] font-semibold tracking-tight text-ink">
              {session.exam_title}
            </p>
            <p className="text-[11.5px] text-ink-muted">
              {answeredCount}/{session.questions.length} answered · {session.total_marks} marks
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <SaveIndicator state={saveState} />
          <ProctorPill status={proctor} enabled={session.proctor_config.webcam_enabled} />
          <div
            className={cx(
              "rounded-[10px] border px-2 py-1 text-center tabular-nums sm:px-3 sm:py-1.5",
              criticalTime
                ? "animate-pulse border-rose/40 bg-rose-soft"
                : lowTime
                  ? "border-amber/30 bg-amber-soft"
                  : "border-line bg-sunken",
            )}
          >
            <p className="text-[10px] uppercase tracking-wide text-ink-muted">Remaining</p>
            <p
              className={cx(
                "text-[16px] font-semibold leading-tight",
                criticalTime ? "text-rose" : lowTime ? "text-amber" : "text-ink",
              )}
            >
              {formatDuration(remaining)}
            </p>
          </div>
          <Button size="sm" onClick={() => setConfirming(true)}>
            Submit
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

      {warnings.length > 0 && (
        <div className="shrink-0 border-b border-amber/25 bg-amber-soft px-4 py-2 lg:px-6">
          <p className="text-[12.5px] text-amber">{warnings.join(" ")}</p>
        </div>
      )}
      {proctor?.lastError && (
        <div className="shrink-0 border-b border-rose/25 bg-rose-soft px-4 py-2 lg:px-6">
          <p className="text-[12.5px] text-rose">{proctor.lastError}</p>
        </div>
      )}

      {/* --------------------------------------------------------------- body */}
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* Palette + webcam */}
        <aside className="flex shrink-0 flex-col border-b border-line bg-surface p-3 lg:w-[228px] lg:border-b-0 lg:border-r lg:p-4">
          <div className="flex items-center justify-between gap-3 lg:block">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-muted lg:mb-3">
              Questions
            </p>
            <button
              type="button"
              onClick={() => setPaletteOpen((open) => !open)}
              aria-expanded={paletteOpen}
              className="shrink-0 rounded-[8px] border border-line px-2.5 py-1 text-[12px] font-medium text-ink-soft transition hover:bg-sunken lg:hidden"
            >
              {paletteOpen ? "Hide" : `${current + 1} of ${visibleQuestions.length}`}
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
                        ? "Answered + marked for review"
                        : flagged
                          ? "Marked for review"
                          : done
                            ? "Answered"
                            : "Not answered"
                    }
                    className={cx(
                      "relative flex h-9 items-center justify-center rounded-[8px] border text-[12.5px] font-medium transition",
                      isCurrent
                        ? "border-accent bg-accent text-white"
                        : done && flagged
                          ? "border-amber/40 bg-amber-soft text-amber"
                          : done
                            ? "border-mint/30 bg-mint-soft text-mint"
                            : flagged
                              ? "border-amber/30 bg-surface text-amber"
                              : "border-line bg-surface text-ink-muted hover:border-line-strong",
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
              <Legend swatch="bg-accent" label="Current" />
              <Legend swatch="bg-mint-soft border border-mint/30" label="Answered" />
              <Legend swatch="bg-surface border border-line" label="Not answered" />
              <Legend swatch="bg-amber-soft border border-amber/30" label="Marked for review" />
              <Legend swatch="bg-amber-soft border border-amber/40" label="Answered + review" icon="⚑" />
            </div>
          </div>

          {/* Webcam */}
          <div className="mx-auto mt-3 w-32 lg:mx-0 lg:mt-auto lg:w-auto">
            <WebcamPreview
              videoRef={videoRef}
              canvasRef={canvasRef}
              status={proctor}
              enabled={session.proctor_config.webcam_enabled}
            />
          </div>
        </aside>

        {/* question pane */}
        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-6 lg:px-10">
          <div className="mx-auto max-w-3xl">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Badge tone="accent">
                Question {(activeSection
                  ? session.questions.findIndex((q) => q.question_id === question.question_id)
                  : current) + 1}
                {session.sections.length > 0 && (
                  <> of {session.questions.length}</>
                )}
              </Badge>
              <Badge>{TYPE_LABEL[question.question_type]}</Badge>
              <Badge tone="mint">{question.marks} marks</Badge>
              {question.negative_marks > 0 && (
                <Badge tone="rose">−{question.negative_marks} if wrong</Badge>
              )}
              {isReviewing && <Badge tone="amber">⚑ Marked for review</Badge>}
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
                  alt="Question figure"
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
                Clear
              </Button>
              <Button
                size="sm"
                variant={isReviewing ? "secondary" : "ghost"}
                onClick={() => void toggleReview(question.question_id)}
              >
                {isReviewing ? "⚑ Reviewing" : "Mark for review"}
              </Button>
            </div>

            <div className="mt-5 flex items-center justify-between gap-3">
              <Button
                variant="secondary"
                onClick={() => setCurrent((i) => Math.max(0, i - 1))}
                disabled={current === 0}
              >
                Previous
              </Button>

              <div className="flex gap-2 lg:hidden">
                <span className="self-center text-[12px] text-ink-muted">
                  {current + 1} / {visibleQuestions.length}
                </span>
              </div>

              {current === visibleQuestions.length - 1 ? (
                <Button onClick={() => setConfirming(true)}>Review &amp; submit</Button>
              ) : (
                <Button onClick={() => setCurrent((i) => Math.min(visibleQuestions.length - 1, i + 1))}>
                  Next
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
          question={clearTarget}
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
    <div className="flex shrink-0 items-center gap-1 overflow-x-auto border-b border-line bg-surface px-4 py-2 lg:px-6">
      {sections.map((sec) => {
        const answered = sec.question_ids.filter((qid) => {
          const a = answers[qid];
          return a && (a.options.length > 0 || a.text.trim() || a.imageUrl);
        }).length;
        const isActive = sec.id === activeSection;
        return (
          <button
            key={sec.id}
            onClick={() => onSelect(sec.id)}
            className={cx(
              "flex shrink-0 items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[12.5px] font-medium transition",
              isActive
                ? "bg-accent text-white"
                : "text-ink-soft hover:bg-sunken hover:text-ink",
            )}
          >
            {sec.name}
            <span
              className={cx(
                "rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
                isActive ? "bg-white/20 text-white" : "bg-sunken text-ink-muted",
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
    const trueLabel = spec?.true_label ?? "True";
    const falseLabel = spec?.false_label ?? "False";
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
        <p className="mb-2 text-[12.5px] text-ink-muted">Type your answer in the blank.</p>
        <input
          type="text"
          value={answer.text}
          onChange={(e) => onWrite(e.target.value)}
          placeholder="Your answer…"
          className="w-full rounded-[10px] border border-line bg-surface px-4 py-3 text-[14.5px] text-ink outline-none placeholder:text-ink-muted focus:border-accent focus:ring-2 focus:ring-accent/20 transition"
        />
      </div>
    );
  }

  if (qt === "numerical") {
    const spec = question.spec as { unit?: string | null } | null;
    return (
      <div>
        <p className="mb-2 text-[12.5px] text-ink-muted">Enter a numerical value.</p>
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
            qt === "long_answer"
              ? "Write your full answer here. Structure it clearly — an examiner reads this."
              : "Write a concise answer."
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
          Passage {spec?.source ? `— ${spec.source}` : ""}
        </p>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">
          {spec?.passage_text ?? "Read the passage and answer the questions below."}
        </p>
        <p className="mt-3 text-[12px] italic text-ink-muted">
          This is a reading passage — no answer required for this item. Answer the numbered questions that follow.
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
      This question type ({qt}) is not yet supported in this interface.
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
  return (
    <div className="space-y-2">
      {multi && (
        <p className="mb-3 text-[12.5px] text-ink-muted">Select every option that applies.</p>
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
            <p><span className="font-semibold text-ink-muted">Input: </span>{spec.input_format}</p>
          )}
          {spec?.output_format && (
            <p><span className="font-semibold text-ink-muted">Output: </span>{spec.output_format}</p>
          )}
          {spec?.constraints && (
            <p><span className="font-semibold text-ink-muted">Constraints: </span>{spec.constraints}</p>
          )}
        </div>
      )}

      {spec?.sample_cases && spec.sample_cases.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Sample cases</p>
          {spec.sample_cases.slice(0, 2).map((sc, i) => (
            <div key={i} className="grid gap-2 rounded-[9px] border border-line bg-surface p-3 text-[12.5px] sm:grid-cols-2">
              <div>
                <p className="mb-1 text-[10.5px] font-medium uppercase tracking-wide text-ink-muted">Input</p>
                <pre className="whitespace-pre-wrap font-mono text-ink">{sc.input}</pre>
              </div>
              <div>
                <p className="mb-1 text-[10.5px] font-medium uppercase tracking-wide text-ink-muted">Output</p>
                <pre className="whitespace-pre-wrap font-mono text-ink">{sc.output}</pre>
              </div>
            </div>
          ))}
        </div>
      )}

      <div>
        <div className="mb-2 flex items-center gap-3">
          <p className="text-[12.5px] font-medium text-ink">Your solution</p>
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
          placeholder={`# Write your ${lang} solution here`}
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
  const text = spec?.passage_text ?? parent?.body;
  if (!text) return null;
  return (
    <div className="mb-4 max-h-48 overflow-y-auto rounded-[11px] border border-accent/20 bg-accent-soft/30 p-4">
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-accent-ink">
        Passage — read before answering
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
  const map = {
    idle: { text: "Ready", tone: "text-ink-muted" },
    saving: { text: "Saving…", tone: "text-accent-ink" },
    saved: { text: "Saved", tone: "text-mint" },
    error: { text: "Not saved", tone: "text-rose" },
  } as const;
  return (
    <span className={cx("hidden text-[12px] font-medium sm:inline", map[state].tone)}>
      {map[state].text}
    </span>
  );
}

function ProctorPill({ status, enabled }: { status: ProctorStatus | null; enabled: boolean }) {
  if (!enabled) return <Badge>Proctoring off</Badge>;
  if (!status || !status.cameraReady) return <Badge tone="rose">Camera off</Badge>;
  if (status.faceCount > 1) return <Badge tone="rose">{status.faceCount} faces</Badge>;
  if (!status.facePresent) return <Badge tone="amber">Face not visible</Badge>;
  if (status.lookingAway) return <Badge tone="amber">Look at the screen</Badge>;
  return <Badge tone="mint">Proctoring active</Badge>;
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
  return (
    <div className="rounded-[11px] border border-line bg-sunken p-2">
      <div className="relative overflow-hidden rounded-[8px] bg-ink/90">
        <video
          ref={videoRef}
          muted
          playsInline
          className="h-[104px] w-full scale-x-[-1] object-cover"
        />
        <canvas ref={canvasRef} className="hidden" />
        {!enabled && (
          <div className="absolute inset-0 grid place-items-center text-[11px] text-white/70">
            Webcam not required
          </div>
        )}
      </div>
      <p className="mt-1.5 text-[11px] leading-tight text-ink-muted">
        {status?.visionMode === "landmarks"
          ? "Face and head position monitored"
          : status?.visionMode === "degraded"
            ? "Recording only — detection unavailable"
            : enabled
              ? "Waiting for camera…"
              : "Behaviour monitoring only"}
      </p>
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
  const count = countWords(text);
  const state = wordState(count, bounds);

  return (
    <div className="mt-1.5 flex items-baseline justify-between gap-3">
      <p className="text-[11.5px] text-ink-muted">
        {bounds.min_words != null && state !== "over" && (
          <span>Minimum {bounds.min_words} words</span>
        )}
        {state === "over" && (
          <span className="font-medium text-rose">
            Trim this answer to save it — over the limit, nothing is being stored.
          </span>
        )}
      </p>
      <p
        className={cx(
          "shrink-0 text-right text-[11.5px] tabular-nums",
          state === "over" ? "font-medium text-rose" : "text-ink-muted",
        )}
      >
        {wordLabel(count, bounds)}
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
      toast("Camera permission denied", "rose");
    }
  }

  function stopCamera() {
    cameraStream?.getTracks().forEach((t) => t.stop());
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
              alt="Captured preview"
              className="max-h-[360px] w-full object-contain bg-sunken"
            />
            <div className="flex gap-2 p-3">
              <Button size="sm" variant="secondary" onClick={() => setCapturedBlob(null)}>
                Retake
              </Button>
              <Button size="sm" onClick={confirmCapture}>
                Use this photo
              </Button>
              <Button size="sm" variant="ghost" onClick={stopCamera}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <video ref={cameraVideoRef} playsInline muted className="max-h-[360px] w-full object-cover bg-ink/90" />
            <canvas ref={captureCanvasRef} className="hidden" />
            <div className="flex gap-2 p-3">
              <Button size="sm" onClick={capturePhoto}>
                📷 Capture
              </Button>
              <Button size="sm" variant="ghost" onClick={stopCamera}>
                Cancel
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
            {imageUrl ? "Replace your uploaded answer" : "Drag & drop or click to upload"}
          </span>
          <span className="mt-1 text-[12px] text-ink-muted">JPEG, PNG or WebP · up to 8 MB</span>
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
          📷 Use camera instead
        </button>
      </div>

      {imageUrl && (
        <div className="mt-4 overflow-hidden rounded-[12px] border border-line">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={imageUrl} alt="Your uploaded answer" className="max-h-[420px] w-full object-contain bg-sunken" />
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
  const unanswered = total - answered;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm">
      <Card className="animate-rise w-full max-w-md">
        <h2 className="text-[17px] font-semibold tracking-tight text-ink">Submit your paper?</h2>
        <p className="mt-1.5 text-[13.5px] text-ink-soft">
          You cannot reopen this exam once it is submitted.
        </p>

        <div className="mt-4 grid grid-cols-3 gap-3 rounded-[10px] bg-sunken/60 p-3 text-center">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">Answered</p>
            <p className="mt-0.5 text-[18px] font-semibold text-ink">{answered}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">Blank</p>
            <p className={cx("mt-0.5 text-[18px] font-semibold", unanswered ? "text-amber" : "text-ink")}>
              {unanswered}
            </p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wide text-ink-muted">Time left</p>
            <p className="mt-0.5 text-[18px] font-semibold tabular-nums text-ink">
              {formatDuration(remaining)}
            </p>
          </div>
        </div>

        {unanswered > 0 && (
          <div className="mt-4">
            <Alert tone="amber">
              {unanswered} question{unanswered === 1 ? " is" : "s are"} still blank. Blank answers
              score zero but never attract a negative mark.
            </Alert>
          </div>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel} disabled={submitting}>
            Keep working
          </Button>
          <Button onClick={onConfirm} loading={submitting}>
            Submit paper
          </Button>
        </div>
      </Card>
    </div>
  );
}

function ConfirmClear({
  question,
  onCancel,
  onConfirm,
}: {
  question: PaperQuestion;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm">
      <Card className="animate-rise w-full max-w-sm">
        <h2 className="text-[16px] font-semibold tracking-tight text-ink">Clear your answer?</h2>
        <p className="mt-1.5 text-[13.5px] text-ink-soft">
          This will delete your saved answer for this question. You can answer again afterwards.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button onClick={onConfirm}>Clear answer</Button>
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
