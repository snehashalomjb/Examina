"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  ProgressBar,
  Select,
  Skeleton,
  Textarea,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { GradingQueueItem, GradingSummary } from "@/lib/types";

export default function GradingPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [queue, setQueue] = useState<GradingQueueItem[]>([]);
  const [summaries, setSummaries] = useState<GradingSummary[]>([]);
  const [selected, setSelected] = useState<GradingQueueItem | null>(null);
  const [examFilter, setExamFilter] = useState("");
  const [questionFilter, setQuestionFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (examFilter) params.set("exam_id", examFilter);
      const query = params.toString() ? `?${params}` : "";
      const [queueData, summaryData] = await Promise.all([
        api.get<GradingQueueItem[]>(`/grading/queue${query}`),
        api.get<GradingSummary[]>("/grading/summary"),
      ]);
      setQueue(queueData);
      setSummaries(summaryData);
      setSelected((current) => {
        if (!current) return queueData[0] ?? null;
        return queueData.find((item) => item.answer_id === current.answer_id) ?? queueData[0] ?? null;
      });
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the grading queue.");
    } finally {
      setLoading(false);
    }
  }, [examFilter]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function publishResults(examId: string) {
    try {
      const response = await api.post<{ detail: string }>(`/exams/${examId}/results/publish`);
      toast(response.detail, "mint");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not publish results", "rose");
    }
  }

  if (!user) return null;

  const filteredQueue = questionFilter
    ? queue.filter((item) => item.question_id === questionFilter)
    : queue;

  return (
    <div className="space-y-6">
      <Hero
        title="Grading queue"
        body="Written answers arrive with a provisional score and a justification. Your decision is the one that counts — nothing publishes until every answer here is cleared."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {/* -------------------------------------------------- per-exam progress */}
      {summaries.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {summaries.map((summary) => {
            const total = summary.pending_review + summary.reviewed;
            const done = total ? (summary.reviewed / total) * 100 : 100;
            return (
              <Card key={summary.exam_id}>
                <p className="truncate text-[13.5px] font-semibold text-ink">{summary.exam_title}</p>
                <p className="mt-0.5 text-[12px] text-ink-muted">
                  {summary.submitted_sessions}/{summary.total_sessions} submitted
                </p>
                <div className="mt-3">
                  <ProgressBar value={done} tone={summary.pending_review ? "amber" : "mint"} />
                </div>
                <div className="mt-2.5 flex items-center justify-between gap-2">
                  <span className="text-[12px] text-ink-muted">
                    {summary.reviewed}/{total} reviewed
                  </span>
                  {summary.results_published ? (
                    <Badge tone="mint">published</Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant={summary.pending_review ? "ghost" : "primary"}
                      disabled={summary.pending_review > 0}
                      onClick={() => publishResults(summary.exam_id)}
                    >
                      {summary.pending_review > 0
                        ? `${summary.pending_review} left`
                        : "Publish results"}
                    </Button>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        {/* ------------------------------------------------------------ queue */}
        <Card padded={false} className="overflow-hidden">
          <div className="border-b border-line p-4 space-y-3">
            <Field label="Filter by exam">
              <Select value={examFilter} onChange={(e) => { setExamFilter(e.target.value); setQuestionFilter(""); }}>
                <option value="">All exams</option>
                {summaries.map((s) => (
                  <option key={s.exam_id} value={s.exam_id}>
                    {s.exam_title}
                  </option>
                ))}
              </Select>
            </Field>
            {questionFilter && (
              <div className="flex items-center gap-2">
                <Badge tone="accent">Question filter active</Badge>
                <button
                  type="button"
                  onClick={() => setQuestionFilter("")}
                  className="text-[12px] text-rose hover:underline"
                >
                  Clear
                </button>
              </div>
            )}
            <p className="text-[12px] text-ink-muted">
              {loading ? "Loading…" : `${filteredQueue.length} awaiting review`}
            </p>
          </div>

          <div className="max-h-[560px] overflow-y-auto">
            {loading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 rounded-[10px]" />
                ))}
              </div>
            ) : filteredQueue.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  title="Queue is clear"
                  body="Every written answer has been reviewed. Results can be published."
                />
              </div>
            ) : (
              <ul className="divide-y divide-line">
                {filteredQueue.map((item) => (
                  <li key={item.answer_id}>
                    <button
                      onClick={() => setSelected(item)}
                      className={cx(
                        "w-full px-4 py-3 text-left transition",
                        selected?.answer_id === item.answer_id
                          ? "bg-accent-soft"
                          : "hover:bg-sunken",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-[13px] font-medium text-ink">
                          {item.candidate_name}
                        </p>
                        <Badge tone={item.grade_status === "ai_scored" ? "accent" : "amber"}>
                          {item.grade_status === "ai_scored" ? "drafted" : "queued"}
                        </Badge>
                      </div>
                      <p className="mt-0.5 truncate text-[12px] text-ink-muted">{item.exam_title}</p>
                      <p className="mt-1 line-clamp-2 text-[12px] leading-snug text-ink-soft">
                        {item.question_body}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>

        {/* ----------------------------------------------------------- detail */}
        {selected ? (
          <GradeCard
            key={selected.answer_id}
            item={selected}
            onGraded={load}
            onFilterByQuestion={(qid) => setQuestionFilter(qid)}
          />
        ) : (
          !loading && (
            <Card>
              <EmptyState
                title="Nothing selected"
                body="Pick an answer from the queue to review it."
              />
            </Card>
          )
        )}
      </div>
    </div>
  );
}

function GradeCard({
  item,
  onGraded,
  onFilterByQuestion,
}: {
  item: GradingQueueItem;
  onGraded: () => void;
  onFilterByQuestion?: (questionId: string) => void;
}) {
  const [marks, setMarks] = useState(
    item.awarded_marks !== null ? String(item.awarded_marks) : "0",
  );
  const [comment, setComment] = useState(item.examiner_comment ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/grading/answers/${item.answer_id}/score`, {
        awarded_marks: Number(marks),
        comment: comment.trim() || null,
      });
      toast(`Scored ${marks}/${item.max_marks} for ${item.candidate_name}`, "mint");
      onGraded();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the score.");
    } finally {
      setBusy(false);
    }
  }

  const ai = item.ai_evaluation;

  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[15px] font-semibold tracking-tight text-ink">{item.candidate_name}</p>
          <p className="text-[12.5px] text-ink-muted">
            {item.candidate_email} · {item.exam_title} · submitted {formatDate(item.submitted_at)}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="accent">{item.max_marks} marks</Badge>
          {onFilterByQuestion && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onFilterByQuestion(item.question_id)}
              title="Grade this question for all candidates"
            >
              Grade for all
            </Button>
          )}
        </div>
      </div>

      <div className="rounded-[11px] border border-line bg-sunken/50 p-4">
        <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          Question
        </p>
        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">
          {item.question_body}
        </p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-[11px] border border-line p-4">
          <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            Candidate answer
          </p>
          {item.image_url ? (
            <>
              <AnnotationCanvas imageUrl={item.image_url} answerId={item.answer_id} />
              <OcrPanel text={item.ocr_text} confidence={item.ocr_confidence} />
            </>
          ) : item.text_answer ? (
            <>
              <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">
                {item.text_answer}
              </p>
              <LengthNote
                wordCount={item.word_count}
                shortfall={item.words_below_minimum}
              />
            </>
          ) : (
            <p className="text-[13.5px] italic text-ink-muted">Left blank</p>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-[11px] border border-line bg-surface p-4">
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
              Model answer
            </p>
            <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-soft">
              {item.model_answer ?? "No model answer recorded."}
            </p>
          </div>

          {item.rubric && Object.keys(item.rubric).length > 0 && (
            <RubricPanel
              rubric={item.rubric as Record<string, number>}
              maxMarks={item.max_marks}
              onMarksChange={(m) => setMarks(String(m))}
            />
          )}
        </div>
      </div>

      {ai && (
        <div className="mt-4 rounded-[11px] border border-accent/20 bg-accent-soft/60 p-4">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-medium uppercase tracking-wide text-accent-ink">
              Provisional score
            </p>
            <Badge tone="accent">
              {ai.score} / {ai.max_score}
            </Badge>
            <Badge>{ai.provider}{ai.model ? ` · ${ai.model}` : ""}</Badge>
            <Badge>confidence {Math.round(ai.confidence * 100)}%</Badge>
          </div>
          <p className="text-[13px] leading-relaxed text-ink-soft">{ai.justification}</p>
          {ai.error && (
            <p className="mt-2 text-[12px] text-rose">Grader error: {ai.error}</p>
          )}
          <p className="mt-2 text-[11.5px] text-ink-muted">
            This is a draft. The marks you enter below are what the candidate receives.
          </p>
        </div>
      )}

      <form onSubmit={submit} className="mt-5 space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-[150px]">
            <Field label={`Marks (0–${item.max_marks})`}>
              <Input
                type="number"
                min="0"
                max={item.max_marks}
                step="0.25"
                value={marks}
                onChange={(e) => setMarks(e.target.value)}
                required
              />
            </Field>
          </div>
          <div className="flex gap-1.5 pb-[2px]">
            {[0, 0.5, 0.75, 1].map((fraction) => (
              <Button
                key={fraction}
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setMarks(String(item.max_marks * fraction))}
              >
                {fraction === 0 ? "0" : fraction === 1 ? "Full" : `${fraction * 100}%`}
              </Button>
            ))}
            {ai && (
              <Button type="button" size="sm" variant="ghost" onClick={() => setMarks(String(ai.score))}>
                Accept draft
              </Button>
            )}
          </div>
        </div>

        <Field label="Comment to the candidate" hint="Shown with their result once published.">
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            placeholder="What was right, what was missing."
          />
        </Field>

        {error && <Alert tone="rose">{error}</Alert>}

        <div className="flex justify-end">
          <Button type="submit" loading={busy}>
            Save score
          </Button>
        </div>
      </form>
    </Card>
  );
}

/**
 * Tesseract's read of a handwritten scan.
 *
 * Collapsed by default and labelled as a machine transcription, because the examiner is
 * marking the image above it. It is here to make a script searchable and skimmable, never
 * to stand in for reading the handwriting.
 */
function OcrPanel({ text, confidence }: { text: string | null; confidence: number | null }) {
  const [open, setOpen] = useState(false);
  if (!text) return null;

  const percent = confidence == null ? null : Math.round(confidence * 100);
  return (
    <div className="mt-3 rounded-[9px] border border-line bg-sunken/40 p-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">
          Machine transcription {percent != null && `· ${percent}% confidence`}
        </span>
        <span className="text-[11.5px] text-ink-muted">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <>
          <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-ink-soft">
            {text}
          </p>
          <p className="mt-2 text-[11.5px] italic text-ink-muted">
            OCR is unreliable on handwriting. Mark the image, not this.
          </p>
        </>
      )}
    </div>
  );
}

/** Word count, plus the shortfall against the question's minimum if the examiner set one. */
function LengthNote({ wordCount, shortfall }: { wordCount: number | null; shortfall: number }) {
  if (wordCount == null) return null;
  return (
    <p className="mt-3 text-[11.5px] text-ink-muted">
      {wordCount} {wordCount === 1 ? "word" : "words"}
      {shortfall > 0 && (
        <span className="text-rose">
          {" "}
          · {shortfall} below the minimum this question asked for
        </span>
      )}
    </p>
  );
}

/* ─────────────────────── Rubric Panel ─────────────────────────────────── */

/**
 * Displays the rubric as a checklist where marking each criterion sums to
 * a total which is emitted via `onMarksChange`. The examiner can still
 * override the number field directly.
 *
 * Rubric format: { "Criterion label": maxMarksForCriterion }
 * Example: { "Core concept explained": 3, "Example given": 2 }
 */
function RubricPanel({
  rubric,
  maxMarks,
  onMarksChange,
}: {
  rubric: Record<string, number>;
  maxMarks: number;
  onMarksChange: (marks: number) => void;
}) {
  const entries = Object.entries(rubric);
  const [checked, setChecked] = useState<Record<string, boolean>>(
    Object.fromEntries(entries.map(([k]) => [k, false])),
  );

  function toggle(key: string) {
    setChecked((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      const total = entries.reduce(
        (sum, [k, v]) => sum + (next[k] ? Number(v) : 0),
        0,
      );
      onMarksChange(Math.min(total, maxMarks));
      return next;
    });
  }

  const earned = entries.reduce(
    (sum, [k, v]) => sum + (checked[k] ? Number(v) : 0),
    0,
  );

  return (
    <div className="rounded-[11px] border border-accent/20 bg-accent-soft/30 p-4">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-accent-ink">
          Rubric
        </p>
        <span className="text-[13px] font-bold tabular-nums text-ink">
          {earned} / {maxMarks}
        </span>
      </div>
      <ul className="space-y-2">
        {entries.map(([criterion, marks]) => (
          <li key={criterion}>
            <label className="flex cursor-pointer items-start gap-3 rounded-[8px] px-2 py-1.5 transition hover:bg-accent/5">
              <input
                type="checkbox"
                checked={checked[criterion] ?? false}
                onChange={() => toggle(criterion)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--color-accent)]"
              />
              <span className="flex-1 text-[13px] leading-snug text-ink">
                {criterion}
              </span>
              <span className="shrink-0 text-[12px] font-medium text-ink-muted">
                +{marks}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] italic text-ink-muted">
        Check criteria met — total updates the marks field. You can still edit it directly.
      </p>
    </div>
  );
}

/* ─────────────────────── Annotation Canvas ────────────────────────────── */

type AnnotationTool = "rect" | "pin" | "text";

interface Annotation {
  id: string;
  type: AnnotationTool;
  x: number;
  y: number;
  x2?: number;
  y2?: number;
  text?: string;
  color: string;
}

/**
 * Canvas overlay on a handwritten-answer image that lets the examiner draw
 * rectangles, drop pins, and add text comments using normalised coordinates
 * (0–1 range so annotations stay aligned at any viewport size).
 *
 * Annotations are stored locally and saved to the backend in one shot.
 * The original candidate image is never modified.
 */
function AnnotationCanvas({
  imageUrl,
  answerId,
}: {
  imageUrl: string;
  answerId: string;
}) {
  const [tool, setTool] = useState<AnnotationTool>("rect");
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [drawing, setDrawing] = useState<Annotation | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [textPrompt, setTextPrompt] = useState<{ x: number; y: number } | null>(null);
  const [textInput, setTextInput] = useState("");

  const COLORS = { rect: "#f59e0b", pin: "#ef4444", text: "#3b82f6" };

  function normCoords(e: React.MouseEvent): { x: number; y: number } | null {
    const el = containerRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  }

  function onMouseDown(e: React.MouseEvent) {
    const pt = normCoords(e);
    if (!pt) return;

    if (tool === "text") {
      setTextPrompt(pt);
      return;
    }

    const ann: Annotation = {
      id: crypto.randomUUID(),
      type: tool,
      x: pt.x,
      y: pt.y,
      color: COLORS[tool],
    };
    setDrawing(ann);
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!drawing || tool !== "rect") return;
    const pt = normCoords(e);
    if (!pt) return;
    setDrawing((prev) => prev ? { ...prev, x2: pt.x, y2: pt.y } : null);
  }

  function onMouseUp(e: React.MouseEvent) {
    if (!drawing) return;
    const pt = normCoords(e);
    const final = pt ? { ...drawing, x2: pt.x, y2: pt.y } : drawing;
    setAnnotations((prev) => [...prev, final]);
    setDrawing(null);
    setSaved(false);
  }

  function addTextAnnotation() {
    if (!textPrompt || !textInput.trim()) {
      setTextPrompt(null);
      setTextInput("");
      return;
    }
    setAnnotations((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        type: "text",
        x: textPrompt.x,
        y: textPrompt.y,
        text: textInput.trim(),
        color: COLORS.text,
      },
    ]);
    setTextPrompt(null);
    setTextInput("");
    setSaved(false);
  }

  function removeAnnotation(id: string) {
    setAnnotations((prev) => prev.filter((a) => a.id !== id));
    setSaved(false);
  }

  async function saveAnnotations() {
    setSaving(true);
    try {
      await api.put(`/grading/answers/${answerId}/annotations`, { annotations });
      setSaved(true);
      toast("Annotations saved", "mint");
    } catch {
      toast("Could not save annotations", "rose");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      {/* Tool bar */}
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted mr-2">
          Annotate
        </p>
        {(["rect", "pin", "text"] as AnnotationTool[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTool(t)}
            className={cx(
              "rounded-[7px] border px-2.5 py-1 text-[12px] font-medium transition",
              tool === t ? "border-accent bg-accent text-white" : "border-line text-ink-soft hover:bg-sunken",
            )}
          >
            {t === "rect" ? "□ Highlight" : t === "pin" ? "📍 Pin" : "💬 Comment"}
          </button>
        ))}
        {annotations.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => { setAnnotations((p) => p.slice(0, -1)); setSaved(false); }}
              className="rounded-[7px] border border-line px-2.5 py-1 text-[12px] text-ink-soft hover:bg-sunken"
            >
              ↩ Undo
            </button>
            <button
              type="button"
              onClick={() => { setAnnotations([]); setSaved(false); }}
              className="rounded-[7px] border border-rose/30 px-2.5 py-1 text-[12px] text-rose hover:bg-rose-soft"
            >
              Clear all
            </button>
          </>
        )}
        <div className="ml-auto">
          <Button
            size="sm"
            variant="secondary"
            loading={saving}
            onClick={saveAnnotations}
            disabled={annotations.length === 0 || saved}
          >
            {saved ? "Saved ✓" : "Save annotations"}
          </Button>
        </div>
      </div>

      {/* Image + overlay */}
      <div
        ref={containerRef}
        className={cx(
          "relative select-none overflow-hidden rounded-[10px] border border-line bg-sunken",
          tool !== "text" ? "cursor-crosshair" : "cursor-text",
        )}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imageUrl}
          alt="Handwritten answer"
          className="pointer-events-none max-h-[420px] w-full object-contain"
          draggable={false}
        />

        {/* Render committed annotations */}
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          {annotations.map((ann) => (
            <AnnotationShape key={ann.id} ann={ann} />
          ))}
          {drawing && drawing.type === "rect" && drawing.x2 != null && (
            <AnnotationShape ann={drawing} />
          )}
        </svg>

        {/* Click-to-remove on pin/text annotations */}
        {annotations.map((ann) =>
          ann.type === "pin" || ann.type === "text" ? (
            <button
              key={ann.id + "-del"}
              type="button"
              onClick={(e) => { e.stopPropagation(); removeAnnotation(ann.id); }}
              className="pointer-events-auto absolute -ml-2 -mt-2 flex h-5 w-5 items-center justify-center rounded-full bg-rose text-[10px] text-white opacity-0 transition hover:opacity-100 focus:opacity-100"
              style={{ left: `${ann.x * 100}%`, top: `${ann.y * 100}%` }}
              title="Remove"
            >
              ×
            </button>
          ) : null,
        )}
      </div>

      {/* Inline text input */}
      {textPrompt && (
        <div className="mt-2 flex gap-2">
          <input
            autoFocus
            type="text"
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") addTextAnnotation(); if (e.key === "Escape") { setTextPrompt(null); setTextInput(""); } }}
            placeholder="Comment text then Enter…"
            className="flex-1 rounded-[8px] border border-line bg-surface px-3 py-1.5 text-[13px] text-ink outline-none focus:border-accent"
          />
          <Button size="sm" onClick={addTextAnnotation}>Add</Button>
        </div>
      )}

      {annotations.length > 0 && (
        <p className="mt-1.5 text-[11px] text-ink-muted">
          {annotations.length} annotation{annotations.length === 1 ? "" : "s"} · Click pins/comments to remove
        </p>
      )}
    </div>
  );
}

function AnnotationShape({ ann }: { ann: Annotation }) {
  if (ann.type === "rect" && ann.x2 != null && ann.y2 != null) {
    const x = Math.min(ann.x, ann.x2) * 100;
    const y = Math.min(ann.y, ann.y2) * 100;
    const w = Math.abs(ann.x2 - ann.x) * 100;
    const h = Math.abs(ann.y2 - ann.y) * 100;
    return (
      <rect
        x={`${x}%`} y={`${y}%`}
        width={`${w}%`} height={`${h}%`}
        fill={`${ann.color}22`}
        stroke={ann.color}
        strokeWidth="1.5"
        strokeDasharray="4 2"
      />
    );
  }
  if (ann.type === "pin") {
    return (
      <g>
        <circle cx={`${ann.x * 100}%`} cy={`${ann.y * 100}%`} r="6" fill={ann.color} opacity="0.85" />
        <circle cx={`${ann.x * 100}%`} cy={`${ann.y * 100}%`} r="2.5" fill="white" />
      </g>
    );
  }
  if (ann.type === "text" && ann.text) {
    return (
      <g>
        <circle cx={`${ann.x * 100}%`} cy={`${ann.y * 100}%`} r="5" fill={ann.color} opacity="0.9" />
        <text
          x={`${ann.x * 100}%`} y={`${ann.y * 100}%`}
          dx="8" dy="4"
          fontSize="11"
          fill={ann.color}
          fontFamily="system-ui"
          style={{ filter: "drop-shadow(0 0 2px white)" }}
        >
          {ann.text}
        </text>
      </g>
    );
  }
  return null;
}

