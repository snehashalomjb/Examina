"use client";

/**
 * The examiner's full "Question Paper Preview" - required reading before publishing.
 *
 * Unlike `PaperPreview` (which simulates the candidate's screen, one question at a time,
 * answer key hidden), this renders the whole assembled paper in one scroll: exam
 * details, then every section with its subject/type/difficulty and every question in
 * it, body, options, and the correct answer - exactly what an examiner needs to catch a
 * wrong answer key or a misfiled question before candidates ever see it.
 */

import { useEffect, useState } from "react";

import { Alert, Badge, Card, EmptyState, Skeleton, cx } from "@/components/ui";
import type { ExamCategoryType } from "@/components/ExamCategoryCard";
import type { SectionDraft } from "@/components/GuidedSectionPicker";
import { ApiError, api } from "@/lib/api";
import {
  QUESTION_TYPE_LABEL,
  type Difficulty,
  type ExamPool,
  type Question,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

export interface ExaminerPaperPreviewProps {
  examId: string | null;
  examTitle: string;
  category: ExamCategoryType;
  subjectName: string | null;
  department: string | null;
  semester: string | null;
  companyName: string | null;
  jobRole: string | null;
  durationMinutes: number;
  instructions: string;
  sections: SectionDraft[];
  pool: ExamPool | null;
}

export function ExaminerPaperPreview({
  examId,
  examTitle,
  category,
  subjectName,
  department,
  semester,
  companyName,
  jobRole,
  durationMinutes,
  instructions,
  sections,
  pool,
}: ExaminerPaperPreviewProps) {
  const [questions, setQuestions] = useState<Record<string, Question>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!examId || !pool) return;
    const ids = pool.entries.map((e) => e.question_id);
    if (ids.length === 0) {
      setQuestions({});
      return;
    }
    setLoading(true);
    setError(null);
    // The pool listing only carries an option *count*, not the options themselves
    // (`exam_id` on /questions means "authored private to this exam", not "in this
    // exam's pool") - so the full body/options/answer key comes from one fetch per
    // pooled question, which is fine at exam scale (tens of questions, not thousands).
    Promise.all(ids.map((id) => api.get<Question>(`/questions/${id}`)))
      .then((list) => setQuestions(Object.fromEntries(list.map((q) => [q.id, q]))))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Could not load the full paper.");
      })
      .finally(() => setLoading(false));
  }, [examId, pool]);

  if (!examId) {
    return (
      <Alert tone="amber" title="Save the draft first">
        A paper preview is built from a saved exam and its pool.
      </Alert>
    );
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-32 rounded-[12px]" />
        <Skeleton className="h-64 rounded-[12px]" />
      </div>
    );
  }

  if (error) return <Alert tone="rose">{error}</Alert>;

  const entries = pool?.entries ?? [];
  if (entries.length === 0) {
    return <EmptyState title="Nothing to preview yet" body="Add questions to the pool first." />;
  }

  const bySection = new Map<string | null, typeof entries>();
  for (const e of entries) {
    const key = e.section_id;
    if (!bySection.has(key)) bySection.set(key, []);
    bySection.get(key)!.push(e);
  }
  for (const list of bySection.values()) list.sort((a, b) => a.order_index - b.order_index);

  const orderedSections = sections.filter((s) => s.id && bySection.has(s.id));
  const unassigned = bySection.get(null) ?? [];

  const totalMarks = entries.reduce((sum, e) => sum + e.effective_marks, 0);

  return (
    <div className="space-y-6">
      {/* exam details */}
      <Card className="space-y-3">
        <h2 className="text-[16px] font-bold text-ink">Exam Details</h2>
        <dl className="grid grid-cols-2 gap-3 text-[13px] sm:grid-cols-3">
          <Detail label="Exam Name" value={examTitle || "Untitled"} />
          {category === "academic" ? (
            <>
              <Detail label="Subject" value={subjectName ?? "—"} />
              <Detail label="Department" value={department ?? "—"} />
              <Detail label="Semester" value={semester ?? "—"} />
            </>
          ) : (
            <>
              <Detail label="Company" value={companyName ?? "—"} />
              <Detail label="Job Role" value={jobRole ?? "—"} />
            </>
          )}
          <Detail label="Duration" value={`${durationMinutes} minutes`} />
          <Detail label="Total Questions" value={String(entries.length)} />
          <Detail label="Total Marks" value={String(totalMarks)} />
        </dl>
        {instructions && (
          <div className="rounded-[10px] border border-line bg-sunken/40 p-3">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Instructions
            </p>
            <p className="whitespace-pre-wrap text-[13px] text-ink-soft">{instructions}</p>
          </div>
        )}
      </Card>

      {/* sections */}
      {orderedSections.map((sec, sIdx) => {
        const list = bySection.get(sec.id!) ?? [];
        return (
          <Card key={sec.id} className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
              <div>
                <h3 className="text-[15px] font-bold text-ink">
                  Section {sIdx + 1}: {sec.name}
                </h3>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {sec.rules.map((r, rIdx) => (
                    <Badge key={rIdx} tone="neutral">
                      {r.topic ?? subjectName ?? "Any subject"} · {QUESTION_TYPE_LABEL[r.question_type]}
                      {r.difficulty ? ` · ${r.difficulty}` : ""} · {r.count} q
                    </Badge>
                  ))}
                </div>
              </div>
              <Badge tone="accent">{list.length} question{list.length === 1 ? "" : "s"}</Badge>
            </div>

            <ol className="space-y-3">
              {list.map((entry, qIdx) => {
                const q = questions[entry.question_id];
                if (!q) return null;
                return (
                  <li key={entry.question_id} className="rounded-[10px] border border-line p-3">
                    <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone="neutral">Q{qIdx + 1}</Badge>
                      <Badge tone="neutral">{QUESTION_TYPE_LABEL[q.question_type]}</Badge>
                      <Badge tone={DIFFICULTY_TONE[q.difficulty]}>{q.difficulty}</Badge>
                      <Badge tone="accent">{entry.effective_marks} marks</Badge>
                    </div>
                    <p className="whitespace-pre-wrap text-[13.5px] text-ink">{q.body}</p>
                    {q.options.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {q.options.map((opt, oi) => (
                          <li
                            key={opt.id}
                            className={cx(
                              "flex items-center gap-2 rounded-[8px] border px-2.5 py-1.5 text-[12.5px]",
                              opt.is_correct
                                ? "border-mint bg-mint-soft text-ink"
                                : "border-line bg-surface text-ink-soft",
                            )}
                          >
                            <span className="font-semibold">{String.fromCharCode(65 + oi)}</span>
                            <span className="flex-1">{opt.text}</span>
                            {opt.is_correct && <Badge tone="mint">correct</Badge>}
                          </li>
                        ))}
                      </ul>
                    )}
                    {q.options.length === 0 && q.model_answer && (
                      <p className="mt-2 rounded-[8px] border border-line bg-sunken/40 px-2.5 py-1.5 text-[12.5px] text-ink-soft">
                        <span className="font-semibold text-ink">Expected answer: </span>
                        {q.model_answer}
                      </p>
                    )}
                  </li>
                );
              })}
            </ol>
          </Card>
        );
      })}

      {unassigned.length > 0 && (
        <Card className="space-y-3">
          <h3 className="text-[15px] font-bold text-ink">Unassigned to a section</h3>
          <p className="text-[12.5px] text-ink-muted">
            {unassigned.length} question(s) are in the pool but not pinned to a specific
            section - any matching rule may draw them.
          </p>
        </Card>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</dt>
      <dd className="mt-0.5 font-semibold text-ink">{value}</dd>
    </div>
  );
}
