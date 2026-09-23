"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Modal,
  SectionTitle,
  Select,
  Skeleton,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { QuestionEditor } from "@/components/QuestionEditor";
import { QuestionImporter } from "@/components/QuestionImporter";
import { QuestionPreviewModal } from "@/components/QuestionPreviewModal";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  Difficulty,
  PdfImportResult,
  Question,
  QuestionCategory,
  QuestionStatus,
  QuestionType,
  Subject,
} from "@/lib/types";
import {
  CATEGORY_LABEL,
  OPTION_BEARING_TYPES,
  QUESTION_TYPE_LABEL as TYPE_LABEL,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

const OBJECTIVE = OPTION_BEARING_TYPES;

/** The shelves the spec asks for, expressed as filter presets over one bank. */
type Shelf = "all" | "mine" | "shared" | "ai" | "imported" | "archived";

const SHELVES: { key: Shelf; label: string }[] = [
  { key: "all", label: "All" },
  { key: "mine", label: "My questions" },
  { key: "shared", label: "Shared" },
  { key: "ai", label: "AI generated" },
  { key: "imported", label: "Imported" },
  { key: "archived", label: "Archived" },
];

export default function QuestionBankPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  // "Create Question" from the dashboard lands here with the editor already open,
  // rather than on a list the examiner then has to find a button on.
  const searchParams = useSearchParams();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [subjectFilter, setSubjectFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<QuestionType | "">("");
  const [difficultyFilter, setDifficultyFilter] = useState<Difficulty | "">("");
  const [categoryFilter, setCategoryFilter] = useState<QuestionCategory | "">("");
  const [topicFilter, setTopicFilter] = useState("");
  const [marksFilter, setMarksFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [search, setSearch] = useState("");
  const [topics, setTopics] = useState<string[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  /** The shelves the bank is organised into. Filter presets, not separate stores. */
  const [shelf, setShelf] = useState<Shelf>("all");

  const [composing, setComposing] = useState(searchParams.get("compose") === "1");
  const [editing, setEditing] = useState<Question | null>(null);
  const [previewing, setPreviewing] = useState<Question | null>(null);
  const [managingSubjects, setManagingSubjects] = useState(false);
  const [importingPdf, setImportingPdf] = useState(false);
  const [importingFile, setImportingFile] = useState(false);
  const [typeCounts, setTypeCounts] = useState<Record<string, Record<string, number>>>({});

  const loadSubjects = useCallback(async () => {
    try {
      setSubjects(await api.get<Subject[]>("/subjects"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load subjects.");
    }
  }, []);

  const loadTypeCounts = useCallback(async () => {
    try {
      setTypeCounts(await api.get<Record<string, Record<string, number>>>("/subjects/type-counts"));
    } catch {
      setTypeCounts({}); // a missing breakdown just hides the count strip
    }
  }, []);

  const loadQuestions = useCallback(async () => {
    const query = new URLSearchParams();
    if (subjectFilter) query.set("subject_id", subjectFilter);
    if (typeFilter) query.set("question_type", typeFilter);
    if (difficultyFilter) query.set("difficulty", difficultyFilter);
    if (categoryFilter) query.set("category", categoryFilter);
    if (topicFilter) query.set("topic", topicFilter);
    if (marksFilter) query.set("marks", marksFilter);
    if (tagFilter) query.set("tags", tagFilter);
    if (search.trim()) query.set("search", search.trim());

    if (shelf === "mine") query.set("mine", "true");
    if (shelf === "ai") query.set("source", "ai_generated");
    if (shelf === "imported") query.set("source", "imported");
    if (shelf === "archived") {
      query.set("status", "archived");
      query.set("include_inactive", "true");
    }

    try {
      const data = await api.get<Question[]>(`/questions?${query.toString()}`);
      // "Shared" is everything somebody else wrote. There is no sharing flag - an
      // examiner looking for reusable material means "things I did not write".
      setQuestions(
        shelf === "shared" && user
          ? data.filter((q) => q.created_by_id && q.created_by_id !== user.id)
          : data,
      );
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load questions.");
    } finally {
      setLoading(false);
    }
  }, [
    subjectFilter,
    typeFilter,
    difficultyFilter,
    categoryFilter,
    topicFilter,
    marksFilter,
    tagFilter,
    search,
    shelf,
    user,
  ]);

  const loadTopics = useCallback(async () => {
    try {
      const params = subjectFilter ? `?subject_id=${subjectFilter}` : "";
      setTopics(await api.get<string[]>(`/questions/topics${params}`));
    } catch {
      setTopics([]); // a missing topic list is a degraded filter, not a failure
    }
  }, [subjectFilter]);

  const loadTags = useCallback(async () => {
    try {
      setAllTags(await api.get<string[]>("/questions/tags"));
    } catch {
      setAllTags([]); // a missing tag list is a degraded filter, not a failure
    }
  }, []);

  useEffect(() => {
    if (user) void loadSubjects();
  }, [user, loadSubjects]);

  useEffect(() => {
    if (user) void loadTypeCounts();
  }, [user, loadTypeCounts]);

  useEffect(() => {
    if (user) void loadTopics();
  }, [user, loadTopics]);

  useEffect(() => {
    if (user) void loadTags();
  }, [user, loadTags]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void loadQuestions(), 250);
    return () => window.clearTimeout(timer);
  }, [user, loadQuestions]);

  async function remove(question: Question) {
    try {
      const response = await api.delete<{ detail: string }>(`/questions/${question.id}`);
      toast(response.detail, "neutral");
      void loadQuestions();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete", "rose");
    }
  }

  async function duplicate(question: Question) {
    try {
      await api.post(`/questions/${question.id}/duplicate`, {});
      toast("Copied into your own questions", "mint");
      void loadQuestions();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not duplicate", "rose");
    }
  }

  /**
   * Archive rather than delete.
   *
   * A question that has been sat cannot be removed without orphaning results, and one
   * that has not been sat is still somebody's work. Archiving takes it out of the way
   * and leaves it recoverable from the Archived shelf.
   */
  async function setStatus(question: Question, status: QuestionStatus) {
    try {
      await api.patch(`/questions/${question.id}`, { status });
      toast(status === "archived" ? "Archived" : "Restored to the bank", "neutral");
      void loadQuestions();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not update", "rose");
    }
  }

  /** An examiner owns what they wrote; an admin may edit anything. */
  function mayEdit(question: Question) {
    return (
      user?.role === "admin" ||
      !question.created_by_id ||
      question.created_by_id === user?.id
    );
  }

  if (!user) return null;

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* ─── Hero ────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-[20px] font-bold tracking-tight text-ink sm:text-[24px]">
            Question Bank
          </h1>
          <p className="mt-1 text-[13px] text-ink-muted sm:text-[14px]">
            {questions.length > 0
              ? `${questions.length} question${questions.length === 1 ? "" : "s"} across ${subjects.length} subjects`
              : "Five question types, tagged by subject and difficulty."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/dashboard/questions/ai-generate">
            <Button size="sm" variant="secondary">
              ✨ AI Generate
            </Button>
          </Link>
          <Button size="sm" variant="secondary" onClick={() => setImportingFile((v) => !v)}>
            {importingFile ? "Close Import" : "📥 Import File"}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setImportingPdf((v) => !v)}>
            {importingPdf ? "Close PDF Import" : "📄 PDF → AI"}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setManagingSubjects((v) => !v)}>
            {managingSubjects ? "Close Subjects" : "Manage Subjects"}
          </Button>
          <Button size="sm" onClick={() => setComposing((v) => !v)}>
            {composing ? "Close Composer" : "+ New Question"}
          </Button>
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {importingFile && (
        <QuestionImporter subjects={subjects} onImported={() => void loadQuestions()} />
      )}

      {importingPdf && <PdfImportSection subjects={subjects} />}

      {managingSubjects && (
        <SubjectManager
          subjects={subjects}
          typeCounts={typeCounts}
          onChanged={() => {
            void loadSubjects();
            void loadTypeCounts();
          }}
        />
      )}

      {composing && (
        <Card>
          <div className="mb-4 flex items-center justify-between gap-2">
            <h2 className="text-[15px] font-semibold tracking-tight text-ink">
              Create question
            </h2>
            <Badge tone="neutral">saved to your bank</Badge>
          </div>
          <QuestionEditor
            subjects={subjects}
            stayOpen
            onCancel={() => setComposing(false)}
            onSaved={() => {
              void loadQuestions();
              void loadTopics();
            }}
          />
        </Card>
      )}

      {editing && (
        <Modal open onClose={() => setEditing(null)} title="Edit question" size="xl">
          <QuestionEditor
            subjects={subjects}
            question={editing}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null);
              void loadQuestions();
            }}
          />
        </Modal>
      )}

      <QuestionPreviewModal question={previewing} onClose={() => setPreviewing(null)} />

      <Card>
        {/* ─── Shelves ────────────────────────────────────────── */}
        <div className="mb-4 flex flex-wrap gap-1 rounded-xl border border-line bg-sunken/40 p-1">
          {SHELVES.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setShelf(tab.key)}
              className={cx(
                "rounded-lg px-3 py-1.5 text-[12.5px] font-semibold transition-all",
                shelf === tab.key
                  ? "bg-accent text-white shadow-sm"
                  : "text-ink-muted hover:bg-surface hover:text-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ─── Filter bar ─────────────────────────────────────── */}
        {/* One column on a phone, then two, then the full row - the controls used to be
            fixed-width and pushed the card into a horizontal scroll below ~700px. */}
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_190px_170px_140px]">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="🔍 Search questions..."
          />
          <Select value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value)}>
            <option value="">All subjects</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </Select>
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as QuestionType | "")}
          >
            <option value="">All types</option>
            {Object.entries(TYPE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>
          <Select
            value={difficultyFilter}
            onChange={(e) => setDifficultyFilter(e.target.value as Difficulty | "")}
          >
            <option value="">Any difficulty</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
          <Select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as QuestionCategory | "")}
          >
            <option value="">All categories</option>
            {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
              <option key={value} value={value}>
                {CATEGORY_LABEL[value]}
              </option>
            ))}
          </Select>
          <Select value={topicFilter} onChange={(e) => setTopicFilter(e.target.value)}>
            <option value="">Any topic</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>
                {topic}
              </option>
            ))}
          </Select>
          <Input
            type="number"
            min="0"
            step="0.5"
            value={marksFilter}
            onChange={(e) => setMarksFilter(e.target.value)}
            placeholder="Marks"
          />
          <Select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)}>
            <option value="">Any tag</option>
            {allTags.map((tag) => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </Select>
          {/* Active filter indicator */}
          {(subjectFilter ||
            typeFilter ||
            difficultyFilter ||
            categoryFilter ||
            topicFilter ||
            marksFilter ||
            tagFilter ||
            search) && (
            <button
              onClick={() => {
                setSubjectFilter("");
                setTypeFilter("");
                setDifficultyFilter("");
                setCategoryFilter("");
                setTopicFilter("");
                setMarksFilter("");
                setTagFilter("");
                setSearch("");
              }}
              className="justify-self-start rounded-[8px] px-3 py-2 text-[12.5px] font-medium text-rose transition hover:bg-rose-soft"
            >
              ✕ Clear filters
            </button>
          )}
        </div>

        {subjectFilter && typeCounts[subjectFilter] && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {Object.entries(typeCounts[subjectFilter])
              .sort(([, a], [, b]) => b - a)
              .map(([qtype, count]) => (
                <Badge key={qtype} tone="neutral" size="xs">
                  {TYPE_LABEL[qtype as QuestionType] ?? qtype}: {count}
                </Badge>
              ))}
          </div>
        )}

        <p className="mb-3 flex items-center gap-2 text-[12.5px] text-ink-muted">
          {loading ? (
            "Loading…"
          ) : (
            <>
              <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-accent px-1.5 text-[10px] font-bold text-white">
                {questions.length}
              </span>
              {questions.length === 1 ? "question" : "questions"}
            </>
          )}
        </p>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-[12px]" />
            ))}
          </div>
        ) : questions.length === 0 ? (
          <EmptyState
            title="No questions here yet"
            body="Add your first question, or relax the filters."
            action={<Button size="sm" onClick={() => setComposing(true)}>New question</Button>}
          />
        ) : (
          <ul className="space-y-2">
            {questions.map((question) => (
              <li
                key={question.id}
                className="card-hover group rounded-[12px] border border-line bg-surface p-4 hover:border-line-strong"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    {/* Type + difficulty badges row */}
                    <div className="mb-2 flex flex-wrap items-center gap-1.5">
                      <span className={cx(
                        "inline-flex items-center rounded-[6px] px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide",
                        question.question_type === "mcq" ? "bg-accent-soft text-accent" :
                        question.question_type === "short_answer" ? "bg-green-soft text-green" :
                        question.question_type === "long_answer" ? "bg-mint-soft text-mint" :
                        question.question_type === "true_false" ? "bg-amber-soft text-amber" :
                        "bg-sunken text-ink-muted",
                      )}>
                        {TYPE_LABEL[question.question_type]}
                      </span>
                      <Badge tone={DIFFICULTY_TONE[question.difficulty]} size="xs">{question.difficulty}</Badge>
                      <Badge tone="neutral" size="xs">{question.marks} marks</Badge>
                      {question.negative_marks > 0 && (
                        <Badge tone="rose" size="xs">−{question.negative_marks}</Badge>
                      )}
                      {!question.is_active && <Badge tone="amber" size="xs">retired</Badge>}
                      {question.status === "archived" && (
                        <Badge tone="neutral" size="xs">archived</Badge>
                      )}
                      {question.source === "ai_generated" && (
                        <Badge tone="purple" size="xs">AI generated</Badge>
                      )}
                      {question.source === "imported" && (
                        <Badge tone="amber" size="xs">imported</Badge>
                      )}
                      {question.topic && <Badge tone="neutral" size="xs">{question.topic}</Badge>}
                      {question.tags?.map((tag) => (
                        <Badge key={tag} tone="purple" size="xs">{tag}</Badge>
                      ))}
                      {question.created_by_name && (
                        <span className="text-[11px] text-ink-muted">
                          by {question.created_by_name}
                        </span>
                      )}
                    </div>

                    {/* Question body */}
                    <p className="text-[13.5px] leading-relaxed text-ink">{question.body}</p>

                    {/* MCQ options */}
                    {OBJECTIVE.includes(question.question_type) && (
                      <ul className="mt-2.5 grid gap-1 sm:grid-cols-2">
                        {question.options.map((option, index) => (
                          <li
                            key={option.id}
                            className={cx(
                              "flex items-start gap-2 rounded-[8px] px-2.5 py-1.5 text-[12.5px]",
                              option.is_correct
                                ? "bg-green-soft text-green-ink"
                                : "bg-sunken/60 text-ink-soft",
                            )}
                          >
                            <span className="font-semibold">{String.fromCharCode(65 + index)}</span>
                            <span>{option.text}</span>
                          </li>
                        ))}
                      </ul>
                    )}

                    {/* Model answer (collapsible) */}
                    {question.model_answer && (
                      <details className="mt-2.5">
                        <summary className="cursor-pointer text-[12.5px] font-medium text-accent">
                          Model answer
                        </summary>
                        <p className="mt-1.5 whitespace-pre-wrap rounded-[8px] bg-sunken/60 p-3 text-[12.5px] leading-relaxed text-ink-soft">
                          {question.model_answer}
                        </p>
                      </details>
                    )}
                  </div>

                  <div className="flex shrink-0 flex-wrap items-center gap-1 transition-opacity duration-200 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
                    <Button size="sm" variant="ghost" onClick={() => setPreviewing(question)}>
                      Preview
                    </Button>
                    {mayEdit(question) ? (
                      <Button size="sm" variant="ghost" onClick={() => setEditing(question)}>
                        Edit
                      </Button>
                    ) : (
                      <span
                        className="px-2 text-[11.5px] text-ink-muted"
                        title="Another examiner wrote this. Duplicate it to make your own copy."
                      >
                        read-only
                      </span>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => void duplicate(question)}>
                      Duplicate
                    </Button>
                    {mayEdit(question) &&
                      (question.status === "archived" ? (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void setStatus(question, "published")}
                        >
                          Restore
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void setStatus(question, "archived")}
                        >
                          Archive
                        </Button>
                      ))}
                    {mayEdit(question) && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-rose hover:bg-rose-soft hover:text-rose-ink"
                        onClick={() => remove(question)}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- pdf import */

/** The question types the generator can produce - same set the AI Tools page offers. */
const PDF_QUESTION_TYPES: QuestionType[] = [
  "mcq",
  "multi_select",
  "true_false",
  "fill_blank",
  "numerical",
  "short_answer",
  "coding",
];

const MAX_PDF_MB = 20;

/**
 * Turn a syllabus, past paper or set of notes into question drafts.
 *
 * The drafts land in the same review queue as anything else the generator produces, so
 * an import cannot put a question into the live bank without an examiner approving it.
 * The PDF itself is never stored - only the text it yielded is sent, and only the
 * drafts are kept.
 */
function PdfImportSection({ subjects }: { subjects: Subject[] }) {
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [chosenSubjectId, setChosenSubjectId] = useState("");
  const [category, setCategory] = useState<QuestionCategory>("technical");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [type, setType] = useState<QuestionType>("mcq");
  const [count, setCount] = useState("5");
  const [extra, setExtra] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PdfImportResult | null>(null);

  /** Reject the wrong type and the oversized file here, so a 20 MB upload is not spent
      finding out the server would refuse it. */
  function accept(candidate: File | undefined) {
    if (!candidate) return;
    setResult(null);
    if (candidate.type !== "application/pdf") {
      setFile(null);
      setError("That is not a PDF. Export or print the document to PDF first.");
      return;
    }
    if (candidate.size > MAX_PDF_MB * 1024 * 1024) {
      setFile(null);
      setError(`That PDF is ${(candidate.size / 1024 / 1024).toFixed(1)} MB — the limit is ${MAX_PDF_MB} MB.`);
      return;
    }
    setError(null);
    setFile(candidate);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append("file", file);
    form.append("category", category);
    form.append("difficulty", difficulty);
    form.append("question_type", type);
    form.append("count", count);
    // Optional fields are left off rather than sent empty - the API validates
    // subject_id as a UUID, and "" is not one.
    if (chosenSubjectId) form.append("subject_id", chosenSubjectId);
    if (topic.trim()) form.append("topic", topic.trim());
    if (extra.trim()) form.append("extra_instructions", extra.trim());

    try {
      const imported = await api.upload<PdfImportResult>(
        "/questions/ai-generate/from-pdf",
        form,
      );
      setResult(imported);
      toast(`${imported.drafts.length} draft(s) from ${imported.filename} — review them next`, "mint");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not import that PDF.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="pdf-import-heading">
      <Card>
        <SectionTitle
          title="Import from PDF"
          hint="Upload a syllabus, past paper or lecture notes. Every draft goes to the review queue — nothing reaches the bank unapproved."
        />
        <h2 id="pdf-import-heading" className="sr-only">
          Import questions from a PDF
        </h2>

        <form onSubmit={submit} className="space-y-4">
          {/* ─── Drop zone ─────────────────────────────────── */}
          <label
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              accept(e.dataTransfer.files?.[0]);
            }}
            className={cx(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[12px] border-2 border-dashed px-5 py-8 text-center transition",
              dragging
                ? "border-accent bg-accent-soft"
                : file
                  ? "border-green-border bg-green-soft"
                  : "border-line-strong bg-sunken/50 hover:border-accent/50 hover:bg-accent-soft/40",
            )}
          >
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={(e) => accept(e.target.files?.[0])}
            />
            <span className="text-[22px]" aria-hidden>
              {file ? "✅" : "📄"}
            </span>
            {file ? (
              <>
                <span className="max-w-full truncate text-[13.5px] font-semibold text-green-ink">
                  {file.name}
                </span>
                <span className="text-[12px] text-ink-muted">
                  {(file.size / 1024).toFixed(0)} KB · click to choose a different file
                </span>
              </>
            ) : (
              <>
                <span className="text-[13.5px] font-semibold text-ink">
                  Drop a PDF here, or click to browse
                </span>
                <span className="text-[12px] text-ink-muted">
                  Digital PDFs only, up to {MAX_PDF_MB} MB. A scan has no text layer to read.
                </span>
              </>
            )}
          </label>

          {/* ─── Generation settings ───────────────────────── */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Category">
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value as QuestionCategory)}
              >
                {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Question type">
              <Select value={type} onChange={(e) => setType(e.target.value as QuestionType)}>
                {PDF_QUESTION_TYPES.map((value) => (
                  <option key={value} value={value}>
                    {TYPE_LABEL[value]}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Difficulty">
              <Select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value as Difficulty)}
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </Select>
            </Field>
            <Field label="How many" hint="1–20 drafts.">
              <Input
                type="number"
                min="1"
                max="20"
                value={count}
                onChange={(e) => setCount(e.target.value)}
                required
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Subject" hint="Optional. Tags the drafts for the bank.">
              <Select
                value={chosenSubjectId}
                onChange={(e) => setChosenSubjectId(e.target.value)}
              >
                <option value="">— None —</option>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.code} — {subject.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Topic" hint="Optional. Narrows the generator to one part of the document.">
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Normalisation"
                maxLength={120}
              />
            </Field>
          </div>

          <Field
            label="Extra instructions"
            hint="Optional. Added to the generation prompt."
          >
            <Textarea
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
              rows={2}
              maxLength={500}
              placeholder="e.g. 'Only chapters 3 and 4. Avoid definition-recall questions.'"
            />
          </Field>

          {error && <Alert tone="rose">{error}</Alert>}

          {result && <PdfImportSummary result={result} />}

          <div className="flex flex-wrap justify-end gap-2">
            {result && (
              <Link href="/dashboard/questions/ai-generate">
                <Button type="button" variant="secondary">
                  Review {result.drafts.length} draft{result.drafts.length === 1 ? "" : "s"}
                </Button>
              </Link>
            )}
            <Button type="submit" loading={busy} disabled={!file}>
              {busy ? "Reading PDF…" : "Extract questions"}
            </Button>
          </div>
        </form>
      </Card>
    </section>
  );
}

/** What was actually read, so the examiner can judge the drafts before opening them. */
function PdfImportSummary({ result }: { result: PdfImportResult }) {
  return (
    <div className="space-y-3 rounded-[12px] border border-line bg-sunken/50 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="mint">{result.drafts.length} drafts</Badge>
        <Badge tone="neutral">{result.pages} pages read</Badge>
        <Badge tone="neutral">{result.characters.toLocaleString()} characters</Badge>
        {result.empty_pages > 0 && (
          <Badge tone="amber">{result.empty_pages} pages had no text</Badge>
        )}
        <span className="truncate text-[12px] text-ink-muted">{result.filename}</span>
      </div>

      {!result.source_grounded && (
        <Alert tone="amber" title="These drafts are not from your PDF">
          No AI provider is configured, so the offline stub produced template questions
          instead. Read every draft before approving it — set an API key to generate from
          the document itself.
        </Alert>
      )}

      {result.truncated && (
        <Alert tone="amber" title="Only part of the document was used">
          The PDF was longer than one generation prompt allows. Import it again with a
          topic set to reach the later sections.
        </Alert>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- composers */
function SubjectManager({
  subjects,
  typeCounts,
  onChanged,
}: {
  subjects: Subject[];
  typeCounts: Record<string, Record<string, number>>;
  onChanged: () => void;
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [savingId, setSavingId] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/subjects", { code: code.trim().toUpperCase(), name: name.trim() });
      toast(`Subject ${code.toUpperCase()} created`, "mint");
      setCode("");
      setName("");
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the subject.");
    } finally {
      setBusy(false);
    }
  }

  function startEdit(subject: Subject) {
    setEditingId(subject.id);
    setEditName(subject.name);
  }

  async function saveEdit(subject: Subject) {
    if (!editName.trim()) return;
    setSavingId(subject.id);
    try {
      await api.patch(`/subjects/${subject.id}`, { name: editName.trim() });
      toast("Subject renamed", "mint");
      setEditingId(null);
      onChanged();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not rename the subject", "rose");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <Card>
      <SectionTitle title="Manage Subjects" hint="Add a subject, or rename an existing one. Questions and exams are grouped by subject." />

      <form onSubmit={submit} className="mb-5 flex flex-wrap items-end gap-3">
        <div className="w-[160px]">
          <Field label="Code">
            <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="CS101" required minLength={2} />
          </Field>
        </div>
        <div className="min-w-[240px] flex-1">
          <Field label="Name">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Computer Science Fundamentals"
              required
              minLength={2}
            />
          </Field>
        </div>
        <Button type="submit" loading={busy}>
          Add Subject
        </Button>
      </form>
      {error && (
        <div className="mb-4">
          <Alert tone="rose">{error}</Alert>
        </div>
      )}

      <div className="-mx-5 overflow-x-auto px-5">
        <table className="w-full min-w-[520px] border-collapse text-left">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
              <th className="pb-2 pr-3 font-medium">Code</th>
              <th className="pb-2 pr-3 font-medium">Name</th>
              <th className="pb-2 pr-3 font-medium">Questions</th>
              <th className="pb-2 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {subjects.map((subject) => {
              const total = Object.values(typeCounts[subject.id] ?? {}).reduce((s, n) => s + n, 0);
              return (
                <tr key={subject.id}>
                  <td className="py-2.5 pr-3 text-[12.5px] font-mono text-ink-muted">{subject.code}</td>
                  <td className="py-2.5 pr-3 text-[13px] text-ink">
                    {editingId === subject.id ? (
                      <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="max-w-xs" />
                    ) : (
                      subject.name
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-[12.5px] text-ink-soft">{total}</td>
                  <td className="py-2.5 text-right">
                    {editingId === subject.id ? (
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" loading={savingId === subject.id} onClick={() => saveEdit(subject)}>
                          Save
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}>
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => startEdit(subject)}>
                        Edit
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
