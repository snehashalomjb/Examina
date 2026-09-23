"use client";

/**
 * Section-by-section question selection.
 *
 * Instead of browsing the whole bank and hoping the right things land in the right
 * section, this walks the examiner through each section's rule one at a time: "Machine
 * Learning, Fill in the Blank, Medium - pick exactly 6", filtered to exactly that, with
 * nothing else selectable. A question already used by another section of this exam is
 * excluded outright, not just discouraged - no accidental reuse.
 *
 * A rule's questions are picked exactly, not drawn at random: when the pool for a
 * (section, rule) holds precisely `count` questions, the paper generator's random draw
 * degenerates to "everyone gets these", which is what makes this a fixed, reviewable
 * paper rather than a lottery over a bigger pool.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, Badge, Button, Card, EmptyState, Skeleton, cx, toast } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  CATEGORY_LABEL,
  QUESTION_TYPE_LABEL,
  type Difficulty,
  type ExamPool,
  type PoolEntry,
  type Question,
  type QuestionCategory,
  type QuestionType,
  type SelectionRule,
  type Subject,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

export interface SectionDraft {
  id?: string;
  name: string;
  rules: SelectionRule[];
}

interface Task {
  sIdx: number;
  rIdx: number;
  sectionName: string;
  sectionId: string | undefined;
  rule: SelectionRule;
  subjectLabel: string;
  subjectId: string | undefined;
}

export interface GuidedSectionPickerProps {
  sections: SectionDraft[];
  subjects: Subject[];
  examSubjectId: string;
  pool: ExamPool | null;
  onAdd: (sIdx: number, questionIds: string[]) => Promise<void> | void;
  onRemove: (questionId: string) => Promise<void> | void;
  onWriteOne: (sIdx: number, rIdx: number) => void;
  onAllComplete?: (complete: boolean) => void;
  /** Bump this to force a refetch of the current task's matching questions - e.g. after
   * writing a fresh one from the "not enough matches" prompt - without resetting which
   * task the examiner is on. */
  reloadToken?: number;
}

function taskKey(t: Task): string {
  return `${t.sIdx}:${t.rIdx}`;
}

function buildTasks(sections: SectionDraft[], subjects: Subject[], examSubjectId: string): Task[] {
  const bySubjectName = new Map(subjects.map((s) => [s.name, s]));
  const out: Task[] = [];
  sections.forEach((sec, sIdx) => {
    sec.rules.forEach((rule, rIdx) => {
      let subjectId: string | undefined;
      let subjectLabel: string;
      if (rule.topic) {
        const match = bySubjectName.get(rule.topic);
        subjectId = match?.id;
        subjectLabel = rule.topic;
      } else if (rule.category) {
        subjectId = undefined;
        subjectLabel = `Any subject — ${CATEGORY_LABEL[rule.category]}`;
      } else {
        subjectId = examSubjectId || undefined;
        subjectLabel = subjects.find((s) => s.id === examSubjectId)?.name ?? "Exam subject";
      }
      out.push({ sIdx, rIdx, sectionName: sec.name, sectionId: sec.id, rule, subjectId, subjectLabel });
    });
  });
  return out;
}

/** Question ids already committed to this exact (section, rule) - pre-checked, editable. */
function existingForTask(pool: ExamPool | null, task: Task): string[] {
  if (!pool || !task.sectionId) return [];
  return pool.entries
    .filter(
      (e) =>
        e.section_id === task.sectionId &&
        e.question_type === task.rule.question_type &&
        (task.rule.difficulty ? e.difficulty === task.rule.difficulty : true),
    )
    .map((e) => e.question_id);
}

function taskStatus(pool: ExamPool | null, task: Task): "complete" | "partial" | "empty" {
  const have = existingForTask(pool, task).length;
  if (have >= task.rule.count) return "complete";
  if (have > 0) return "partial";
  return "empty";
}

export function GuidedSectionPicker({
  sections,
  subjects,
  examSubjectId,
  pool,
  onAdd,
  onRemove,
  onWriteOne,
  onAllComplete,
  reloadToken = 0,
}: GuidedSectionPickerProps) {
  const tasks = useMemo(() => buildTasks(sections, subjects, examSubjectId), [sections, subjects, examSubjectId]);
  const [taskIndex, setTaskIndex] = useState(0);
  const [available, setAvailable] = useState<Question[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const task = tasks[taskIndex] as Task | undefined;

  const allDone = tasks.length > 0 && tasks.every((t) => taskStatus(pool, t) === "complete");
  useEffect(() => {
    onAllComplete?.(allDone);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allDone]);

  const load = useCallback(async () => {
    if (!task) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (task.subjectId) params.set("subject_id", task.subjectId);
      if (task.rule.category) params.set("category", task.rule.category);
      params.set("question_type", task.rule.question_type);
      if (task.rule.difficulty) params.set("difficulty", task.rule.difficulty);
      params.set("limit", "200");
      const data = await api.get<Question[]>(`/questions?${params.toString()}`);
      setAvailable(data);
      setSelected(existingForTask(pool, task));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load matching questions.");
      setAvailable([]);
    } finally {
      setLoading(false);
    }
    // pool is read only for the pre-check; re-running on every pool change would fight
    // the user's in-progress checkbox clicks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [task?.sIdx, task?.rIdx, task?.subjectId, task?.rule.category, task?.rule.question_type, task?.rule.difficulty, reloadToken]);

  useEffect(() => {
    void load();
  }, [load]);

  if (tasks.length === 0) {
    return (
      <EmptyState
        title="No sections yet"
        body="Go back and add at least one section with a selection rule before picking questions."
      />
    );
  }

  if (!task) return null;

  const already = new Set(
    (pool?.entries ?? [])
      .filter((e) => !existingForTask(pool, task).includes(e.question_id))
      .map((e) => e.question_id),
  );
  const pickable = available.filter((q) => !already.has(q.id));
  const requiredCount = task.rule.count;
  const selectedCount = selected.length;
  const canContinue = selectedCount === requiredCount;
  const shortfall = pickable.length < requiredCount;

  function toggle(id: string) {
    setSelected((cur) => {
      if (cur.includes(id)) return cur.filter((x) => x !== id);
      if (cur.length >= requiredCount) {
        toast(`Already selected ${requiredCount} of ${requiredCount} - deselect one first`, "amber");
        return cur;
      }
      return [...cur, id];
    });
  }

  async function confirmAndContinue() {
    if (!task || !canContinue) return;
    setSaving(true);
    try {
      const before = new Set(existingForTask(pool, task));
      const toAdd = selected.filter((id) => !before.has(id));
      const toRemove = [...before].filter((id) => !selected.includes(id));
      if (toAdd.length) await onAdd(task.sIdx, toAdd);
      for (const id of toRemove) await onRemove(id);
      toast(`${task.sectionName}: ${selectedCount}/${requiredCount} selected`, "mint");
      if (taskIndex < tasks.length - 1) setTaskIndex(taskIndex + 1);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save this section's picks.", "rose");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[220px_minmax(0,1fr)]">
      {/* progress rail */}
      <div className="space-y-1.5">
        {tasks.map((t, i) => {
          const status = taskStatus(pool, t);
          const have = existingForTask(pool, t).length;
          return (
            <button
              key={taskKey(t)}
              type="button"
              onClick={() => setTaskIndex(i)}
              className={cx(
                "w-full rounded-[10px] border px-3 py-2 text-left text-[12px] transition",
                i === taskIndex
                  ? "border-accent bg-accent-soft/40"
                  : status === "complete"
                    ? "border-mint/40 bg-mint-soft/20"
                    : "border-line bg-surface hover:border-line-strong",
              )}
            >
              <p className="truncate font-semibold text-ink">{t.sectionName}</p>
              <p className="text-ink-muted">
                {QUESTION_TYPE_LABEL[t.rule.question_type]}
                {t.rule.difficulty ? ` · ${t.rule.difficulty}` : ""}
              </p>
              <p className="mt-0.5">
                {status === "complete" ? (
                  <span className="font-semibold text-mint">✓ {have}/{t.rule.count}</span>
                ) : i === taskIndex ? (
                  <span className="font-semibold text-accent">→ {have}/{t.rule.count}</span>
                ) : (
                  <span className="text-ink-muted">{have}/{t.rule.count}</span>
                )}
              </p>
            </button>
          );
        })}
      </div>

      {/* current task */}
      <Card className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-bold text-ink">{task.sectionName}</h3>
            <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[12.5px] text-ink-muted">
              <Badge tone="neutral">{task.subjectLabel}</Badge>
              <Badge tone="neutral">{QUESTION_TYPE_LABEL[task.rule.question_type]}</Badge>
              {task.rule.difficulty && (
                <Badge tone={DIFFICULTY_TONE[task.rule.difficulty]}>{task.rule.difficulty}</Badge>
              )}
            </p>
          </div>
          <div className="text-right">
            <p className={cx("text-[15px] font-bold", canContinue ? "text-mint" : "text-ink")}>
              Selected: {selectedCount} / {requiredCount}
            </p>
            <p className="text-[11.5px] text-ink-muted">{pickable.length} matching available</p>
          </div>
        </div>

        {error && <Alert tone="rose">{error}</Alert>}

        {!loading && shortfall && (
          <Alert tone="amber" title="Not enough matching questions">
            Only {pickable.length} matching question{pickable.length === 1 ? "" : "s"}{" "}
            {pickable.length === 1 ? "is" : "are"} available in the Question Bank. Please add
            more questions to the bank, or change this section&apos;s requirements.
            <div className="mt-2">
              <Button size="sm" variant="secondary" onClick={() => onWriteOne(task.sIdx, task.rIdx)}>
                + Write a matching question
              </Button>
            </div>
          </Alert>
        )}

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-[10px]" />
            ))}
          </div>
        ) : pickable.length === 0 ? (
          <EmptyState
            title="No matching questions"
            body="Nothing in the bank matches this section's subject, type and difficulty yet."
          />
        ) : (
          <ul className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
            {pickable.map((q) => {
              const checked = selected.includes(q.id);
              const capped = !checked && selectedCount >= requiredCount;
              return (
                <li
                  key={q.id}
                  className={cx(
                    "rounded-[10px] border px-3 py-2.5 transition",
                    checked
                      ? "border-accent bg-accent-soft/40"
                      : capped
                        ? "border-line bg-sunken/40 opacity-50"
                        : "border-line bg-surface hover:border-line-strong",
                  )}
                >
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(q.id)}
                      className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="line-clamp-2 text-[13.5px] text-ink">{q.body}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <Badge tone="accent">{q.marks} marks</Badge>
                        {q.topic && <Badge tone="neutral">{q.topic}</Badge>}
                      </div>
                    </div>
                  </label>
                </li>
              );
            })}
          </ul>
        )}

        <div className="flex items-center justify-between border-t border-line pt-3">
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={taskIndex === 0}
              onClick={() => setTaskIndex((i) => Math.max(0, i - 1))}
            >
              ← Previous section
            </Button>
          </div>
          <Button size="sm" disabled={!canContinue} loading={saving} onClick={() => void confirmAndContinue()}>
            {taskIndex < tasks.length - 1 ? "Confirm & Continue →" : "Confirm selection"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

export { buildTasks, existingForTask, taskStatus };
