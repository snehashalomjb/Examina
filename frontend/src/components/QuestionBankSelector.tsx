"use client";

/**
 * Browse the reusable bank and pull questions into an exam.
 *
 * This is one of four ways to fill a pool, not the only one - which is why it lives in
 * a tab rather than being the whole "add questions" step it used to be.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  EmptyState,
  Field,
  Input,
  Modal,
  Select,
  Skeleton,
  cx,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  CATEGORY_LABEL,
  QUESTION_SOURCE_LABEL,
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
      setError(err instanceof ApiError ? err.message : "Could not load the question bank.");
    } finally {
      setLoading(false);
    }
  }, [effectiveSubject, type, category, difficulty, topic, marks, search, shelf, currentUserId]);

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
            {tab.label}
          </button>
        ))}
      </div>

      {/* filters */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {!subjectId && (
          <Field label="Subject">
            <Select value={chosenSubject} onChange={(e) => setChosenSubject(e.target.value)}>
              <option value="">All subjects</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Type">
          <Select value={type} onChange={(e) => setType(e.target.value as QuestionType | "")}>
            <option value="">Any type</option>
            {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => (
              <option key={value} value={value}>
                {QUESTION_TYPE_LABEL[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Category">
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value as QuestionCategory | "")}
          >
            <option value="">Any category</option>
            {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
              <option key={value} value={value}>
                {CATEGORY_LABEL[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Difficulty">
          <Select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value as Difficulty | "")}
          >
            <option value="">Any difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
        </Field>
        <Field label="Topic">
          <Select value={topic} onChange={(e) => setTopic(e.target.value)}>
            <option value="">Any topic</option>
            {topics.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Marks">
          <Input
            type="number"
            min="0"
            step="0.5"
            value={marks}
            onChange={(e) => setMarks(e.target.value)}
            placeholder="Any"
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Search">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search question text and topics"
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
          {selected.length ? `${selected.length} selected` : `${questions.length} shown`}
        </label>
        <Button
          size="sm"
          disabled={!selected.length}
          loading={adding}
          onClick={() => void addSelected()}
        >
          Add {selected.length || ""} to exam
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
          title="Nothing matches those filters"
          body="Loosen a filter, or write the question yourself from the Create tab."
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
                        {QUESTION_TYPE_LABEL[question.question_type]}
                      </Badge>
                      <Badge tone={DIFFICULTY_TONE[question.difficulty]}>
                        {question.difficulty}
                      </Badge>
                      <Badge tone="accent">{question.marks} marks</Badge>
                      {question.topic && <Badge tone="neutral">{question.topic}</Badge>}
                      {question.source !== "manual" && (
                        <Badge tone={question.source === "ai_generated" ? "purple" : "amber"}>
                          {QUESTION_SOURCE_LABEL[question.source as QuestionSource]}
                        </Badge>
                      )}
                      {question.created_by_name && (
                        <span className="text-[11.5px] text-ink-muted">
                          by {question.created_by_name}
                        </span>
                      )}
                      {added && <Badge tone="mint">already in this exam</Badge>}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setPreview(question)}
                    >
                      Preview
                    </Button>
                    {onEdit && mayEdit(question) && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => onEdit(question)}
                      >
                        Edit
                      </Button>
                    )}
                    {onDuplicate && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => void onDuplicate(question)}
                      >
                        Duplicate
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

/**
 * The examiner's view of a question, answer key included.
 *
 * Deliberately different from what the candidate sees. The candidate's runner renders
 * options with no correctness marking at all; here the key is the point.
 */
export function QuestionPreviewModal({
  question,
  onClose,
}: {
  question: Question | null;
  onClose: () => void;
}) {
  if (!question) return null;
  const spec = (question.spec ?? {}) as Record<string, unknown>;

  return (
    <Modal open onClose={onClose} title="Question preview">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="neutral">{QUESTION_TYPE_LABEL[question.question_type]}</Badge>
          <Badge tone={DIFFICULTY_TONE[question.difficulty]}>{question.difficulty}</Badge>
          <Badge tone="accent">{question.marks} marks</Badge>
          {question.negative_marks > 0 && (
            <Badge tone="rose">−{question.negative_marks} if wrong</Badge>
          )}
          {question.topic && <Badge tone="neutral">{question.topic}</Badge>}
        </div>

        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">
          {question.body}
        </p>

        {question.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={question.image_url}
            alt="Question figure"
            className="max-h-64 rounded-[10px] border border-line object-contain"
          />
        )}

        {question.options.length > 0 && (
          <ul className="space-y-1.5">
            {question.options.map((option, index) => (
              <li
                key={option.id}
                className={cx(
                  "flex items-center gap-2 rounded-[9px] border px-3 py-2 text-[13.5px]",
                  option.is_correct
                    ? "border-mint bg-mint-soft text-ink"
                    : "border-line bg-surface text-ink-soft",
                )}
              >
                <span className="font-semibold">{String.fromCharCode(65 + index)}</span>
                <span className="flex-1">{option.text}</span>
                {option.is_correct && <Badge tone="mint">correct</Badge>}
              </li>
            ))}
          </ul>
        )}

        {typeof spec.answer !== "undefined" && (
          <Detail label="Expected answer">
            {String(spec.answer)}
            {typeof spec.tolerance === "number" && spec.tolerance > 0
              ? ` ± ${spec.tolerance}`
              : ""}
            {typeof spec.unit === "string" && spec.unit ? ` ${spec.unit}` : ""}
          </Detail>
        )}
        {Array.isArray(spec.accepted_answers) && (
          <Detail label="Accepted answers">
            {(spec.accepted_answers as string[]).join(" · ")}
          </Detail>
        )}
        {question.model_answer && (
          <Detail label="Model answer">{question.model_answer}</Detail>
        )}
        {question.explanation && <Detail label="Explanation">{question.explanation}</Detail>}

        <p className="text-[12px] text-ink-muted">
          Everything marked correct here stays on the server. The candidate&apos;s paper
          carries the question and its options, and nothing else.
        </p>
      </div>
    </Modal>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[10px] border border-line bg-sunken/50 p-3">
      <p className="mb-1 text-[11.5px] font-semibold uppercase tracking-wide text-ink-muted">
        {label}
      </p>
      <p className="whitespace-pre-wrap text-[13.5px] text-ink">{children}</p>
    </div>
  );
}
