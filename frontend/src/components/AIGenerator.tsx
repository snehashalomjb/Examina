"use client";

/**
 * Ask for a batch of questions, then review every one before it counts.
 *
 * The review step is not a formality. A generated question that reads plausibly can
 * still be wrong, off-syllabus, or keyed to the wrong option - so nothing here writes
 * to the bank or an exam until the examiner presses approve on that specific draft.
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Modal,
  Select,
  Skeleton,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  CATEGORY_LABEL,
  type AiDraft,
  type Difficulty,
  type QuestionCategory,
  type QuestionType,
  type Subject,
} from "@/lib/types";

/** The types the generator produces well. Passage needs children; upload needs a scan. */
const GENERATABLE: QuestionType[] = [
  "mcq",
  "multi_select",
  "true_false",
  "fill_blank",
  "numerical",
  "short_answer",
  "long_answer",
  "coding",
];

interface DraftPayload {
  body?: string;
  marks?: number;
  negative_marks?: number;
  model_answer?: string | null;
  explanation?: string | null;
  options?: { text: string; is_correct?: boolean }[];
  source_grounded?: boolean;
  [key: string]: unknown;
}

export interface AIGeneratorProps {
  subjects: Subject[];
  /** When set, approving a draft adds the question to this exam's pool. */
  examId?: string;
  subjectId?: string;
  /** Called after any approval, so the caller can refetch the pool. */
  onApproved?: () => void;
}

export function AIGenerator({ subjects, examId, subjectId, onApproved }: AIGeneratorProps) {
  const t = useTranslations("questionBank");
  const [chosenSubject, setChosenSubject] = useState(subjectId ?? "");
  const [category, setCategory] = useState<QuestionCategory>("technical");
  const [topic, setTopic] = useState("");
  const [types, setTypes] = useState<QuestionType[]>(["mcq"]);
  const [count, setCount] = useState("5");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [marksEach, setMarksEach] = useState("2");
  const [language, setLanguage] = useState("");
  const [syllabus, setSyllabus] = useState("");
  const [extra, setExtra] = useState("");

  const [drafts, setDrafts] = useState<AiDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<AiDraft | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const effectiveSubject = subjectId ?? chosenSubject;

  const loadDrafts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<AiDraft[]>("/questions/ai-drafts?status=pending&mine=true");
      setDrafts(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("ai_error_load_drafts"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadDrafts();
  }, [loadDrafts]);

  function toggleType(type: QuestionType) {
    setTypes((current) =>
      current.includes(type) ? current.filter((x) => x !== type) : [...current, type],
    );
  }

  async function generate() {
    if (!effectiveSubject) {
      // Subject is what actually scopes what gets asked - without it the prompt has no
      // notion of which course "Normalisation" belongs to, and the draft ends up
      // untethered from any syllabus. The wizard never hits this: it locks the subject
      // to the exam's before this component ever mounts.
      setError(t("ai_error_choose_subject"));
      return;
    }
    if (!types.length) {
      setError(t("ai_error_pick_type"));
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const created = await api.post<AiDraft[]>("/questions/ai-generate", {
        subject_id: effectiveSubject || null,
        category,
        topic: topic.trim() || null,
        difficulty,
        question_type: types[0],
        question_types: types,
        count: Number(count),
        marks_per_question: marksEach ? Number(marksEach) : null,
        syllabus: syllabus.trim() || null,
        language: language.trim() || null,
        extra_instructions: extra.trim() || null,
      });
      setDrafts((current) => [...created, ...current]);
      toast(t("ai_toast_generated", { count: created.length }), "accent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("ai_error_generation"));
    } finally {
      setGenerating(false);
    }
  }

  async function approve(draft: AiDraft, payload?: DraftPayload) {
    setBusyId(draft.id);
    setError(null);
    try {
      await api.put<AiDraft>(`/questions/ai-drafts/${draft.id}/approve`, {
        payload: payload ?? draft.payload,
        exam_id: examId ?? null,
        save_to_bank: true,
      });
      setDrafts((current) => current.filter((d) => d.id !== draft.id));
      setSelected((current) => current.filter((id) => id !== draft.id));
      toast(examId ? t("ai_toast_approved_exam") : t("ai_toast_approved_bank"), "mint");
      onApproved?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("ai_error_approve"));
    } finally {
      setBusyId(null);
    }
  }

  async function reject(draft: AiDraft, reason: string) {
    setBusyId(draft.id);
    try {
      await api.put(`/questions/ai-drafts/${draft.id}/reject`, { reason });
      setDrafts((current) => current.filter((d) => d.id !== draft.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("ai_error_reject"));
    } finally {
      setBusyId(null);
    }
  }

  async function regenerate(draft: AiDraft, feedback: string) {
    setBusyId(draft.id);
    setError(null);
    try {
      const replacement = await api.post<AiDraft>(
        `/questions/ai-drafts/${draft.id}/regenerate`,
        { feedback: feedback.trim() || null },
      );
      setDrafts((current) => [replacement, ...current.filter((d) => d.id !== draft.id)]);
      toast(t("ai_toast_regenerated"), "accent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("ai_error_regenerate"));
    } finally {
      setBusyId(null);
    }
  }

  async function approveSelected() {
    const chosen = drafts.filter((d) => selected.includes(d.id) && !d.error);
    if (!chosen.length) return;
    setBulkBusy(true);
    for (const draft of chosen) {
      await approve(draft);
    }
    setBulkBusy(false);
  }

  const usable = drafts.filter((d) => !d.error);

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------------------- the request */}
      <Card>
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <h3 className="text-[15px] font-semibold tracking-tight text-ink">{t("ai_generate_questions")}</h3>
          <Badge tone="purple">{t("ai_badge_assists")}</Badge>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          {!subjectId && (
            <Field label={t("subject")} required hint={t("ai_subject_hint")}>
              <Select value={chosenSubject} onChange={(e) => setChosenSubject(e.target.value)}>
                <option value="">{t("choose_subject")}</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} — {s.name}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          <Field label={t("category")}>
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value as QuestionCategory)}
            >
              {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
                <option key={value} value={value}>
                  {t(`category_${value}`)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("topic")} hint={t("ai_topic_hint")}>
            <Input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder={t("ai_topic_placeholder")}
              maxLength={120}
            />
          </Field>
          <Field label={t("difficulty")}>
            <Select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as Difficulty)}
            >
              <option value="easy">{t("difficulty_easy")}</option>
              <option value="medium">{t("difficulty_medium")}</option>
              <option value="hard">{t("difficulty_hard")}</option>
            </Select>
          </Field>
          <Field label={t("how_many")} hint={t("ai_how_many_hint")}>
            <Input
              type="number"
              min="1"
              max="20"
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </Field>
          <Field label={t("ai_marks_each")}>
            <Input
              type="number"
              min="0.5"
              step="0.5"
              value={marksEach}
              onChange={(e) => setMarksEach(e.target.value)}
            />
          </Field>
          <Field label={t("ai_language")} hint={t("ai_language_hint")}>
            <Input
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              placeholder={t("ai_language_placeholder")}
              maxLength={40}
            />
          </Field>
        </div>

        <div className="mt-4">
          <p className="mb-2 text-[13px] font-medium text-ink-soft">{t("question_types")}</p>
          <div className="flex flex-wrap gap-2">
            {GENERATABLE.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => toggleType(type)}
                className={cx(
                  "rounded-full border px-3 py-1.5 text-[12.5px] font-medium transition",
                  types.includes(type)
                    ? "border-accent bg-accent text-white"
                    : "border-line-strong bg-surface text-ink-soft hover:border-accent/60",
                )}
              >
                {t(`type_${type}`)}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Field
            label={t("ai_syllabus")}
            hint={t("ai_syllabus_hint")}
          >
            <Textarea
              value={syllabus}
              onChange={(e) => setSyllabus(e.target.value)}
              rows={4}
              placeholder={t("ai_syllabus_placeholder")}
            />
          </Field>
          <Field label={t("ai_additional_instructions")}>
            <Textarea
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              rows={4}
              placeholder={t("ai_additional_placeholder")}
              maxLength={500}
            />
          </Field>
        </div>

        {error && (
          <div className="mt-4">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <Button
            loading={generating}
            disabled={!effectiveSubject}
            onClick={() => void generate()}
          >
            {t("ai_generate_questions")}
          </Button>
        </div>
      </Card>

      {/* --------------------------------------------------------------- the review */}
      <div>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-semibold tracking-tight text-ink">
              {t("ai_awaiting_review")}
            </h3>
            <Badge tone="amber">{drafts.length}</Badge>
          </div>
          {usable.length > 0 && (
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 text-[13px] text-ink-soft">
                <input
                  type="checkbox"
                  checked={selected.length === usable.length}
                  onChange={() =>
                    setSelected(
                      selected.length === usable.length ? [] : usable.map((d) => d.id),
                    )
                  }
                  className="h-4 w-4 rounded border-line-strong"
                />
                {t("select_all")}
              </label>
              <Button
                size="sm"
                disabled={!selected.length}
                loading={bulkBusy}
                onClick={() => void approveSelected()}
              >
                {examId
                  ? t("ai_approve_selected_exam", { count: selected.length })
                  : t("ai_approve_selected_bank", { count: selected.length })}
              </Button>
            </div>
          )}
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-[12px]" />
            ))}
          </div>
        ) : drafts.length === 0 ? (
          <EmptyState
            title={t("ai_no_drafts_title")}
            body={t("ai_no_drafts_body")}
          />
        ) : (
          <ul className="space-y-3">
            {drafts.map((draft) => (
              <DraftCard
                key={draft.id}
                draft={draft}
                selected={selected.includes(draft.id)}
                busy={busyId === draft.id}
                inExam={Boolean(examId)}
                onToggle={() =>
                  setSelected((current) =>
                    current.includes(draft.id)
                      ? current.filter((id) => id !== draft.id)
                      : [...current, draft.id],
                  )
                }
                onApprove={() => void approve(draft)}
                onReject={(reason) => void reject(draft, reason)}
                onRegenerate={(feedback) => void regenerate(draft, feedback)}
                onEdit={() => setEditing(draft)}
              />
            ))}
          </ul>
        )}
      </div>

      {editing && (
        <DraftEditor
          draft={editing}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            await approve(editing, payload);
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function DraftCard({
  draft,
  selected,
  busy,
  inExam,
  onToggle,
  onApprove,
  onReject,
  onRegenerate,
  onEdit,
}: {
  draft: AiDraft;
  selected: boolean;
  busy: boolean;
  inExam: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: (reason: string) => void;
  onRegenerate: (feedback: string) => void;
  onEdit: () => void;
}) {
  const t = useTranslations("questionBank");
  const payload = draft.payload as DraftPayload;
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);
  const [duplicateOf, setDuplicateOf] = useState<string | null>(null);

  // A generated draft can land on wording already in the bank - the model has no memory
  // of what's already there. Non-blocking: it only tells the examiner, never withholds
  // the approve button, the same as the manual-authoring check this mirrors.
  useEffect(() => {
    const body = payload.body;
    if (!draft.subject_id || !body || body.trim().length < 8) return;
    let cancelled = false;
    api
      .post<{ matches: { id: string; body: string }[] }>("/questions/check-duplicate", {
        subject_id: draft.subject_id,
        body: body.trim(),
      })
      .then((res) => {
        if (!cancelled) setDuplicateOf(res.matches[0]?.body ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.id]);

  if (draft.error) {
    return (
      <li className="rounded-[12px] border border-rose/30 bg-rose-soft/40 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[13.5px] font-medium text-ink">{t("ai_draft_failed")}</p>
            <p className="mt-0.5 text-[12.5px] text-ink-muted">{draft.error}</p>
          </div>
          <Button size="sm" variant="ghost" loading={busy} onClick={() => onReject("Failed")}>
            {t("btn_dismiss")}
          </Button>
        </div>
      </li>
    );
  }

  return (
    <li
      className={cx(
        "rounded-[12px] border p-4 transition",
        selected ? "border-accent bg-accent-soft/30" : "border-line bg-surface",
      )}
    >
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong"
        />
        <div className="min-w-0 flex-1">
          <p className="text-[14px] leading-relaxed text-ink">{payload.body ?? t("ai_empty_body")}</p>

          {Array.isArray(payload.options) && payload.options.length > 0 && (
            <ul className="mt-2 space-y-1">
              {payload.options.map((option, index) => (
                <li
                  key={index}
                  className={cx(
                    "flex items-center gap-2 rounded-[8px] border px-2.5 py-1.5 text-[13px]",
                    option.is_correct
                      ? "border-mint bg-mint-soft text-ink"
                      : "border-line bg-sunken/40 text-ink-soft",
                  )}
                >
                  <span className="font-semibold">{String.fromCharCode(65 + index)}</span>
                  <span className="flex-1">{option.text}</span>
                  {option.is_correct && <Badge tone="mint">{t("ai_proposed_answer")}</Badge>}
                </li>
              ))}
            </ul>
          )}

          {payload.model_answer && (
            <p className="mt-2 rounded-[8px] border border-line bg-sunken/40 p-2.5 text-[13px] text-ink-soft">
              <span className="font-semibold text-ink">{t("model_answer_label")} </span>
              {payload.model_answer}
            </p>
          )}

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <Badge tone="purple">{t("source_ai_generated")}</Badge>
            <Badge tone="neutral">{t(`type_${draft.question_type}`)}</Badge>
            <Badge tone="neutral">{t(`difficulty_${draft.difficulty}`)}</Badge>
            {typeof payload.marks === "number" && (
              <Badge tone="accent">{t("marks_count", { count: payload.marks })}</Badge>
            )}
            {draft.topic && <Badge tone="neutral">{draft.topic}</Badge>}
            <span className="text-[11.5px] text-ink-muted">
              {draft.provider}
              {draft.model ? ` · ${draft.model}` : ""}
            </span>
          </div>

          {duplicateOf && (
            <p className="mt-2 rounded-[8px] border border-amber/25 bg-amber-soft px-2.5 py-1.5 text-[12px] text-amber-ink">
              ⚠ {t("ai_duplicate_warning", {
                text: duplicateOf.slice(0, 100) + (duplicateOf.length > 100 ? "…" : ""),
              })}
            </p>
          )}

          {payload.source_grounded === false && (
            <p className="mt-2 text-[12px] text-amber-ink">
              {t("ai_not_grounded")}
            </p>
          )}
        </div>
      </div>

      {showFeedback && (
        <div className="mt-3 space-y-2 rounded-[10px] border border-line bg-sunken/40 p-3">
          <Field label={t("ai_feedback_label")} hint={t("ai_feedback_hint")}>
            <Textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={2}
              placeholder={t("ai_feedback_placeholder")}
            />
          </Field>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="ghost" onClick={() => setShowFeedback(false)}>
              {t("btn_cancel")}
            </Button>
            <Button size="sm" loading={busy} onClick={() => onRegenerate(feedback)}>
              {t("btn_regenerate")}
            </Button>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap justify-end gap-2 border-t border-line/60 pt-3">
        <Button size="sm" variant="ghost" onClick={onEdit}>
          {t("btn_edit")}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setShowFeedback((v) => !v)}>
          {t("btn_regenerate")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          loading={busy}
          onClick={() => onReject("Not suitable")}
        >
          {t("btn_reject")}
        </Button>
        <Button size="sm" loading={busy} onClick={onApprove}>
          {inExam ? t("ai_approve_add_exam") : t("ai_approve_into_bank")}
        </Button>
      </div>
    </li>
  );
}

/**
 * Correct a draft before approving it.
 *
 * A form rather than a JSON box: an examiner fixing a mis-keyed option should not have
 * to know what the payload looks like, and a typo in JSON silently loses the edit.
 */
function DraftEditor({
  draft,
  onClose,
  onSave,
}: {
  draft: AiDraft;
  onClose: () => void;
  onSave: (payload: DraftPayload) => Promise<void>;
}) {
  const t = useTranslations("questionBank");
  const original = draft.payload as DraftPayload;
  const [body, setBody] = useState(original.body ?? "");
  const [marks, setMarks] = useState(String(original.marks ?? 1));
  const [negative, setNegative] = useState(String(original.negative_marks ?? 0));
  const [modelAnswer, setModelAnswer] = useState(original.model_answer ?? "");
  const [explanation, setExplanation] = useState(original.explanation ?? "");
  const [options, setOptions] = useState(
    (original.options ?? []).map((o) => ({ text: o.text, is_correct: Boolean(o.is_correct) })),
  );
  const [busy, setBusy] = useState(false);

  const single = draft.question_type === "mcq" || draft.question_type === "true_false";

  return (
    <Modal open onClose={onClose} title={t("ai_edit_before_approving")} size="lg">
      <div className="space-y-4">
        <Field label={t("question")}>
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} />
        </Field>

        {options.length > 0 && (
          <div>
            <p className="mb-2 text-[13px] font-medium text-ink-soft">
              {t("ai_options_tap_letter")}
            </p>
            <div className="space-y-2">
              {options.map((option, index) => (
                <div key={index} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setOptions((current) =>
                        current.map((o, i) =>
                          single
                            ? { ...o, is_correct: i === index }
                            : i === index
                              ? { ...o, is_correct: !o.is_correct }
                              : o,
                        ),
                      )
                    }
                    className={cx(
                      "flex h-9 w-9 shrink-0 items-center justify-center border text-[12px] font-semibold transition",
                      single ? "rounded-full" : "rounded-[8px]",
                      option.is_correct
                        ? "border-accent bg-accent text-white"
                        : "border-line-strong text-ink-muted hover:bg-sunken",
                    )}
                  >
                    {String.fromCharCode(65 + index)}
                  </button>
                  <Input
                    value={option.text}
                    onChange={(e) =>
                      setOptions((current) =>
                        current.map((o, i) =>
                          i === index ? { ...o, text: e.target.value } : o,
                        ),
                      )
                    }
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t("marks")}>
            <Input
              type="number"
              min="0"
              step="0.5"
              value={marks}
              onChange={(e) => setMarks(e.target.value)}
            />
          </Field>
          <Field label={t("negative_marks")}>
            <Input
              type="number"
              min="0"
              step="0.25"
              value={negative}
              onChange={(e) => setNegative(e.target.value)}
            />
          </Field>
        </div>

        {(draft.question_type === "short_answer" ||
          draft.question_type === "long_answer" ||
          modelAnswer) && (
          <Field label={t("model_answer")}>
            <Textarea
              value={modelAnswer}
              onChange={(e) => setModelAnswer(e.target.value)}
              rows={3}
            />
          </Field>
        )}

        <Field label={t("explanation")}>
          <Textarea
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            rows={2}
          />
        </Field>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            {t("btn_cancel")}
          </Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onSave({
                  ...original,
                  body: body.trim(),
                  marks: Number(marks),
                  negative_marks: Number(negative),
                  model_answer: modelAnswer.trim() || null,
                  explanation: explanation.trim() || null,
                  options: options.map((o) => ({ text: o.text.trim(), is_correct: o.is_correct })),
                });
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("ai_save_approve")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
