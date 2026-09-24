"use client";

/**
 * Browse the reusable bank and pull questions into an exam.
 *
 * This is one of four ways to fill a pool, not the only one - which is why it lives in
 * a tab rather than being the whole "add questions" step it used to be.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Select,
  Skeleton,
  cx,
} from "@/components/ui";
import { QuestionPreviewModal } from "@/components/QuestionPreviewModal";
import { ApiError, api } from "@/lib/api";
import {
  CATEGORY_LABEL,
  QUESTION_TYPE_LABEL,
  type Difficulty,
  type Question,
  type QuestionCategory,
  type QuestionSource,
  type QuestionType,
  type Subject,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

/** The shelves the spec asks for, expressed as query parameters. */
type Shelf = "all" | "mine" | "shared" | "ai" | "imported" | "archived";

const SHELVES: { key: Shelf; label: string }[] = [
  { key: "all", label: "All" },
  { key: "mine", label: "My questions" },
  { key: "shared", label: "Shared" },
  { key: "ai", label: "AI generated" },
  { key: "imported", label: "Imported" },
  { key: "archived", label: "Archived" },
];

export interface QuestionBankSelectorProps {
  subjects: Subject[];
  /** Restricts the browser to the exam's subject. A pool may not mix subjects. */
  subjectId?: string;
  /** Question ids already in the pool - shown as "added" rather than selectable. */
  alreadyIn?: string[];
  onAdd: (questionIds: string[]) => Promise<void> | void;
  /** Offered per row when the caller can host an editor. */
  onEdit?: (question: Question) => void;
  onDuplicate?: (question: Question) => Promise<void> | void;
  /** Signed-in examiner's id, for deciding whose questions may be edited. */
  currentUserId?: string;
  isAdmin?: boolean;
}

export function QuestionBankSelector({
  subjects,
  subjectId,
  alreadyIn = [],
  onAdd,
  onEdit,
  onDuplicate,
  currentUserId,
  isAdmin = false,
}: QuestionBankSelectorProps) {
  const t = useTranslations("questionBank");
  const [questions, setQuestions] = useState<Question[]>([]);
  const [topics, setTopics] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const [shelf, setShelf] = useState<Shelf>("all");
  const [chosenSubject, setChosenSubject] = useState(subjectId ?? "");
  const [type, setType] = useState<QuestionType | "">("");
  const [category, setCategory] = useState<QuestionCategory | "">("");
  const [difficulty, setDifficulty] = useState<Difficulty | "">("");
  const [topic, setTopic] = useState("");
  const [marks, setMarks] = useState("");
  const [search, setSearch] = useState("");

  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<Question | null>(null);

  const effectiveSubject = subjectId ?? chosenSubject;
  const inPool = useMemo(() => new Set(alreadyIn), [alreadyIn]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (effectiveSubject) params.set("subject_id", effectiveSubject);
    if (type) params.set("question_type", type);
    if (category) params.set("category", category);
    if (difficulty) params.set("difficulty", difficulty);
    if (topic) params.set("topic", topic);
    if (marks) params.set("marks", marks);
    if (search.trim()) params.set("search", search.trim());

    // The shelves are filter presets, not a separate concept on the server.
    if (shelf === "mine") params.set("mine", "true");
    if (shelf === "ai") params.set("source", "ai_generated");
    if (shelf === "imported") params.set("source", "imported");
    if (shelf === "archived") {
      params.set("status", "archived");
      params.set("include_inactive", "true");
    }

    try {
      const data = await api.get<Question[]>(`/questions?${params.toString()}`);
      // "Shared" means everyone else's - there is no separate sharing flag, and an
      // examiner browsing for reusable material means "things I did not write".
      setQuestions(
        shelf === "shared" && currentUserId
          ? data.filter((q) => q.created_by_id && q.created_by_id !== currentUserId)
          : data,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("selector_error_load"));
    } finally {
      setLoading(false);
    }
  }, [effectiveSubject, type, category, difficulty, topic, marks, search, shelf, currentUserId, t]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  useEffect(() => {
    (async () => {
      try {
        const params = effectiveSubject ? `?subject_id=${effectiveSubject}` : "";
        setTopics(await api.get<string[]>(`/questions/topics${params}`));
      } catch {
        setTopics([]); // a missing topic list is a degraded filter, not a failure
      }
    })();
  }, [effectiveSubject]);

  const selectable = questions.filter((q) => !inPool.has(q.id));
  const allSelected = selectable.length > 0 && selected.length === selectable.length;

  function toggle(id: string) {
    setSelected((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );
  }

  async function addSelected() {
    if (!selected.length) return;
    setAdding(true);
    try {
      await onAdd(selected);
      setSelected([]);
    } finally {
      setAdding(false);
    }
  }

  function mayEdit(question: Question) {
    return isAdmin || !question.created_by_id || question.created_by_id === currentUserId;
  }

  return (
    <div className="space-y-4">
      {/* shelves */}
      <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
        {SHELVES.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => {
              setShelf(tab.key);
              setSelected([]);
            }}
            className={cx(
              "rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition-all",
              shelf === tab.key
                ? "bg-accent text-white shadow-sm"
                : "text-ink-muted hover:bg-sunken hover:text-ink",
            )}
          >
            {t(`shelf_${tab.key}`)}
          </button>
        ))}
      </div>

      {/* filters */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {!subjectId && (
          <Field label={t("subject")}>
            <Select value={chosenSubject} onChange={(e) => setChosenSubject(e.target.value)}>
              <option value="">{t("all_subjects")}</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={t("type")}>
          <Select value={type} onChange={(e) => setType(e.target.value as QuestionType | "")}>
            <option value="">{t("any_type")}</option>
            {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => (
              <option key={value} value={value}>
                {t(`type_${value}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("category")}>
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value as QuestionCategory | "")}
          >
            <option value="">{t("any_category")}</option>
            {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
              <option key={value} value={value}>
                {t(`category_${value}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("difficulty")}>
          <Select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as Difficulty | "")}
          >
            <option value="">{t("any_difficulty")}</option>
            <option value="easy">{t("difficulty_easy")}</option>
            <option value="medium">{t("difficulty_medium")}</option>
            <option value="hard">{t("difficulty_hard")}</option>
          </Select>
        </Field>
        <Field label={t("topic")}>
          <Select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">{t("any_topic")}</option>
            {topics.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("marks")}>
          <Input
            type="number"
            min="0"
            step="0.5"
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
            placeholder={t("any")}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label={t("search")}>
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("selector_search_placeholder")}
            />
          </Field>
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {/* selection bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-line bg-sunken/50 px-3 py-2">
        <label className="flex items-center gap-2 text-[13px] text-ink-soft">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={() => setSelected(allSelected ? [] : selectable.map((q) => q.id))}
            className="h-4 w-4 rounded border-line-strong"
            disabled={selectable.length === 0}
          />
          {selected.length
            ? t("selector_selected", { count: selected.length })
            : t("selector_shown", { count: questions.length })}
        </label>
        <Button
          size="sm"
          disabled={!selected.length}
          loading={adding}
          onClick={() => void addSelected()}
        >
          {t("selector_add_to_exam", { count: selected.length })}
        </Button>
      </div>

      {/* results */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-[10px]" />
          ))}
        </div>
      ) : questions.length === 0 ? (
        <EmptyState
          title={t("selector_empty_title")}
          body={t("selector_empty_body")}
        />
      ) : (
        <ul className="space-y-2">
          {questions.map((question) => {
            const added = inPool.has(question.id);
            const checked = selected.includes(question.id);
            return (
              <li
                key={question.id}
                className={cx(
                  "rounded-[10px] border px-3 py-2.5 transition",
                  added
                    ? "border-line bg-sunken/60 opacity-70"
                    : checked
                      ? "border-accent bg-accent-soft/40"
                      : "border-line bg-surface hover:border-line-strong",
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={added}
                    onChange={() => toggle(question.id)}
                    className="mt-1 h-4 w-4 shrink-0 rounded border-line-strong"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-[13.5px] text-ink">{question.body}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone="neutral">
                        {t(`type_${question.question_type}`)}
                      </Badge>
                      <Badge tone={DIFFICULTY_TONE[question.difficulty]}>
                        {t(`difficulty_${question.difficulty}`)}
                      </Badge>
                      <Badge tone="accent">{t("marks_count", { count: question.marks })}</Badge>
                      {question.topic && <Badge tone="neutral">{question.topic}</Badge>}
                      {question.source !== "manual" && (
                        <Badge tone={question.source === "ai_generated" ? "purple" : "amber"}>
                          {t(`source_${question.source as QuestionSource}`)}
                        </Badge>
                      )}
                      {question.created_by_name && (
                        <span className="text-[11.5px] text-ink-muted">
                          {t("by_author", { name: question.created_by_name })}
                        </span>
                      )}
                      {added && <Badge tone="mint">{t("selector_already_in_exam")}</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setPreview(question)}
                    >
                      {t("btn_preview")}
                    </Button>
                    {onEdit && mayEdit(question) && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => onEdit(question)}
                      >
                        {t("btn_edit")}
                      </Button>
                    )}
                    {onDuplicate && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => void onDuplicate(question)}
                      >
                        {t("btn_duplicate")}
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <QuestionPreviewModal question={preview} onClose={() => setPreview(null)} />
    </div>
  );
}

