"use client";

/**
 * The exam's question pool: what has been assembled, and whether it is enough.
 *
 * Kept visually distinct from the Question Bank on purpose. The bank is a library; the
 * pool is this exam's shortlist; the paper is what one candidate sits. Three different
 * things that examiners routinely conflate, to their cost - a 50-question pool with a
 * 20-question rule is not a 50-question exam.
 */

import { useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  cx,
} from "@/components/ui";
import { QuestionPreviewModal } from "@/components/QuestionBankSelector";
import { ApiError, api } from "@/lib/api";
import {
  QUESTION_TYPE_LABEL,
  type Difficulty,
  type ExamPool,
  type PoolEntry,
  type Question,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

export interface QuestionPoolProps {
  pool: ExamPool | null;
  /** Disabled once candidates have sat the exam - the server refuses anyway. */
  editable?: boolean;
  /** Reordering is meaningless when every paper is shuffled per candidate. */
  reorderable?: boolean;
  onReorder: (questionIds: string[]) => Promise<void>;
  onRemove: (questionId: string) => Promise<void>;
  onOverrideMarks: (questionId: string, marks: number | null) => Promise<void>;
  onEdit?: (questionId: string) => void;
}

export function QuestionPool({
  pool,
  editable = true,
  reorderable = true,
  onReorder,
  onRemove,
  onOverrideMarks,
  onEdit,
}: QuestionPoolProps) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<Question | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [editingMarks, setEditingMarks] = useState<string | null>(null);
  const [marksDraft, setMarksDraft] = useState("");

  if (!pool) {
    return (
      <EmptyState
        title="No pool yet"
        body="Save the exam as a draft first, then add questions to it."
      />
    );
  }

  const entries = pool.entries;

  async function run(id: string, action: () => Promise<void>) {
    setBusyId(id);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That change could not be saved.");
    } finally {
      setBusyId(null);
    }
  }

  function move(index: number, delta: number) {
    const next = [...entries];
    const target = index + delta;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    void run(entries[index].question_id, () => onReorder(next.map((e) => e.question_id)));
  }

  function dropOn(targetId: string) {
    if (!dragging || dragging === targetId) return;
    const ids = entries.map((e) => e.question_id);
    const from = ids.indexOf(dragging);
    const to = ids.indexOf(targetId);
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    setDragging(null);
    void run(dragging, () => onReorder(ids));
  }

  async function openPreview(questionId: string) {
    try {
      setPreview(await api.get<Question>(`/questions/${questionId}`));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load that question.");
    }
  }

  return (
    <div className="space-y-4">
      <PoolSummary pool={pool} />

      {pool.problems.length > 0 && (
        <Alert tone="amber" title="This exam cannot be published yet">
          <ul className="list-inside list-disc space-y-0.5">
            {pool.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </Alert>
      )}

      {error && <Alert tone="rose">{error}</Alert>}

      {entries.length === 0 ? (
        <EmptyState
          title="The pool is empty"
          body="Write a question, pull one from the bank, generate a set with AI, or import a file."
        />
      ) : (
        <>
          {!reorderable && (
            <p className="text-[12.5px] text-ink-muted">
              Randomisation is on, so each candidate gets their own order — the pool
              order below only affects how the paper preview reads.
            </p>
          )}
          <ul className="space-y-2">
            {entries.map((entry, index) => (
              <li
                key={entry.question_id}
                draggable={editable && reorderable}
                onDragStart={() => setDragging(entry.question_id)}
                onDragEnd={() => setDragging(null)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => dropOn(entry.question_id)}
                className={cx(
                  "rounded-[10px] border bg-surface px-3 py-2.5 transition",
                  dragging === entry.question_id
                    ? "border-accent opacity-50"
                    : "border-line hover:border-line-strong",
                  busyId === entry.question_id && "opacity-60",
                )}
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-sunken text-[12px] font-semibold text-ink-soft">
                    {index + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-[13.5px] text-ink">{entry.body}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone="neutral">
                        {QUESTION_TYPE_LABEL[entry.question_type]}
                      </Badge>
                      <Badge tone={DIFFICULTY_TONE[entry.difficulty]}>{entry.difficulty}</Badge>
                      {editingMarks === entry.question_id ? (
                        <span className="flex items-center gap-1">
                          <Input
                            type="number"
                            min="0"
                            step="0.5"
                            value={marksDraft}
                            onChange={(e) => setMarksDraft(e.target.value)}
                            className="h-7 w-20"
                          />
                          <Button
                            size="sm"
                            onClick={() => {
                              const value = marksDraft.trim() === "" ? null : Number(marksDraft);
                              setEditingMarks(null);
                              void run(entry.question_id, () =>
                                onOverrideMarks(entry.question_id, value),
                              );
                            }}
                          >
                            Set
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingMarks(null)}
                          >
                            Cancel
                          </Button>
                        </span>
                      ) : (
                        <button
                          type="button"
                          disabled={!editable}
                          onClick={() => {
                            setEditingMarks(entry.question_id);
                            setMarksDraft(
                              entry.marks_override === null ? "" : String(entry.marks_override),
                            );
                          }}
                          title={editable ? "Re-weight for this exam only" : undefined}
                        >
                          <Badge tone={entry.marks_override === null ? "accent" : "purple"}>
                            {entry.effective_marks} marks
                            {entry.marks_override !== null && " (overridden)"}
                          </Badge>
                        </button>
                      )}
                      {entry.topic && <Badge tone="neutral">{entry.topic}</Badge>}
                      {entry.source === "ai_generated" && <Badge tone="purple">AI</Badge>}
                      {entry.source === "imported" && <Badge tone="amber">imported</Badge>}
                      {entry.exam_only && <Badge tone="neutral">this exam only</Badge>}
                      {!entry.has_answer_key && (
                        <Badge tone="rose">no answer key</Badge>
                      )}
                      {entry.created_by_name && (
                        <span className="text-[11.5px] text-ink-muted">
                          by {entry.created_by_name}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    {editable && reorderable && (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={index === 0}
                          onClick={() => move(index, -1)}
                          aria-label="Move up"
                        >
                          ↑
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={index === entries.length - 1}
                          onClick={() => move(index, 1)}
                          aria-label="Move down"
                        >
                          ↓
                        </Button>
                      </>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => void openPreview(entry.question_id)}
                    >
                      Preview
                    </Button>
                    {editable && onEdit && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => onEdit(entry.question_id)}
                      >
                        Edit
                      </Button>
                    )}
                    {editable && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          void run(entry.question_id, () => onRemove(entry.question_id))
                        }
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <QuestionPreviewModal question={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

/** Totals and distributions - the numbers the spec asks to be visible before publishing. */
export function PoolSummary({ pool }: { pool: ExamPool }) {
  const { stats } = pool;
  return (
    <Card className="space-y-3">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="In the pool" value={String(stats.total_questions)} />
        <Metric
          label="On each paper"
          value={String(pool.required_count)}
          hint="Set by the selection rules"
        />
        <Metric label="Pool marks" value={String(stats.total_marks)} />
        <Metric
          label="Ready to publish"
          value={pool.can_publish ? "Yes" : "Not yet"}
          tone={pool.can_publish ? "mint" : "amber"}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Distribution
          title="By type"
          rows={Object.entries(stats.by_type).map(([key, count]) => [
            QUESTION_TYPE_LABEL[key as keyof typeof QUESTION_TYPE_LABEL] ?? key,
            count,
          ])}
          total={stats.total_questions}
        />
        <Distribution
          title="By difficulty"
          rows={Object.entries(stats.by_difficulty).map(([key, count]) => [key, count])}
          total={stats.total_questions}
        />
      </div>
    </Card>
  );
}

function Metric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "mint" | "amber";
}) {
  return (
    <div className="rounded-[10px] border border-line bg-sunken/50 p-3">
      <p className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</p>
      <p
        className={cx(
          "mt-0.5 text-[18px] font-semibold tracking-tight",
          tone === "mint" ? "text-mint" : tone === "amber" ? "text-amber-ink" : "text-ink",
        )}
      >
        {value}
      </p>
      {hint && <p className="text-[11px] text-ink-muted">{hint}</p>}
    </div>
  );
}

function Distribution({
  title,
  rows,
  total,
}: {
  title: string;
  rows: [string, number][];
  total: number;
}) {
  if (!rows.length) return null;
  return (
    <div className="rounded-[10px] border border-line p-3">
      <p className="mb-2 text-[12px] font-semibold text-ink-soft">{title}</p>
      <ul className="space-y-1.5">
        {rows.map(([label, count]) => (
          <li key={label} className="flex items-center gap-2 text-[12.5px]">
            <span className="w-32 shrink-0 truncate capitalize text-ink-soft">{label}</span>
            <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken">
              <span
                className="block h-full rounded-full bg-accent"
                style={{ width: total ? `${(count / total) * 100}%` : "0%" }}
              />
            </span>
            <span className="w-6 text-right font-semibold text-ink">{count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Small helper so pages can show the pool count without mounting the whole list. */
export function poolCount(pool: ExamPool | null): number {
  return pool?.entries.length ?? 0;
}

export type { PoolEntry };
