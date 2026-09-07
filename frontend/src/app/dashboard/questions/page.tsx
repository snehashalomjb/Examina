"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  SectionTitle,
  Select,
  Skeleton,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  CodingLanguage,
  Difficulty,
  PdfImportResult,
  Question,
  QuestionCategory,
  QuestionImage,
  QuestionType,
  Subject,
} from "@/lib/types";
import {
  CATEGORY_LABEL,
  CONTAINER_TYPES,
  OPTION_BEARING_TYPES,
  QUESTION_TYPE_LABEL as TYPE_LABEL,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

const OBJECTIVE = OPTION_BEARING_TYPES;

const CODING_LANGUAGES: CodingLanguage[] = ["python", "java", "cpp", "javascript"];
const LANGUAGE_LABEL: Record<CodingLanguage, string> = {
  python: "Python",
  java: "Java",
  cpp: "C++",
  javascript: "JavaScript",
};

export default function QuestionBankPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [subjectFilter, setSubjectFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<QuestionType | "">("");
  const [difficultyFilter, setDifficultyFilter] = useState<Difficulty | "">("");
  const [search, setSearch] = useState("");

  const [composing, setComposing] = useState(false);
  const [addingSubject, setAddingSubject] = useState(false);
  const [importingPdf, setImportingPdf] = useState(false);

  const loadSubjects = useCallback(async () => {
    try {
      setSubjects(await api.get<Subject[]>("/subjects"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load subjects.");
    }
  }, []);

  const loadQuestions = useCallback(async () => {
    const query = new URLSearchParams();
    if (subjectFilter) query.set("subject_id", subjectFilter);
    if (typeFilter) query.set("question_type", typeFilter);
    if (difficultyFilter) query.set("difficulty", difficultyFilter);
    if (search.trim()) query.set("search", search.trim());
    try {
      setQuestions(await api.get<Question[]>(`/questions?${query.toString()}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load questions.");
    } finally {
      setLoading(false);
    }
  }, [subjectFilter, typeFilter, difficultyFilter, search]);

  useEffect(() => {
    if (user) void loadSubjects();
  }, [user, loadSubjects]);

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
          <Button size="sm" variant="secondary" onClick={() => setImportingPdf((v) => !v)}>
            {importingPdf ? "Close PDF Import" : "📄 Import PDF"}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => setAddingSubject((v) => !v)}>
            New Subject
          </Button>
          <Button size="sm" onClick={() => setComposing((v) => !v)}>
            {composing ? "Close Composer" : "+ New Question"}
          </Button>
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {importingPdf && <PdfImportSection subjects={subjects} />}

      {addingSubject && (
        <SubjectComposer
          onDone={() => {
            setAddingSubject(false);
            void loadSubjects();
          }}
        />
      )}

      {composing && (
        <QuestionComposer
          subjects={subjects}
          onDone={() => {
            setComposing(false);
            void loadQuestions();
            void loadSubjects();
          }}
        />
      )}

      <Card>
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
          {/* Active filter indicator */}
          {(subjectFilter || typeFilter || difficultyFilter || search) && (
            <button
              onClick={() => { setSubjectFilter(""); setTypeFilter(""); setDifficultyFilter(""); setSearch(""); }}
              className="justify-self-start rounded-[8px] px-3 py-2 text-[12.5px] font-medium text-rose transition hover:bg-rose-soft"
            >
              ✕ Clear filters
            </button>
          )}
        </div>

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
                className="group rounded-[12px] border border-line bg-surface p-4 transition hover:border-line-strong hover:shadow-[var(--shadow-xs)]"
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

                  <Button
                    size="sm"
                    variant="ghost"
                    className="opacity-0 group-hover:opacity-100 transition text-rose hover:bg-rose-soft hover:text-rose-ink"
                    onClick={() => remove(question)}
                  >
                    Delete
                  </Button>
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
function SubjectComposer({ onDone }: { onDone: () => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/subjects", { code: code.trim().toUpperCase(), name: name.trim() });
      toast(`Subject ${code.toUpperCase()} created`, "mint");
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the subject.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionTitle title="New subject" hint="Questions and exams are grouped by subject." />
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
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
          Create
        </Button>
        {error && (
          <div className="w-full">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}
      </form>
    </Card>
  );
}

interface DraftOption {
  text: string;
  is_correct: boolean;
}

function QuestionComposer({ subjects, onDone }: { subjects: Subject[]; onDone: () => void }) {
  // Empty means "whichever subject is first" - derived at use, so no effect is needed
  // to keep this in sync when the subject list loads.
  const [chosenSubjectId, setChosenSubjectId] = useState("");
  const subjectId = chosenSubjectId || subjects[0]?.id || "";
  const [type, setType] = useState<QuestionType>("mcq");
  const [category, setCategory] = useState<QuestionCategory>("academic");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [body, setBody] = useState("");
  const [modelAnswer, setModelAnswer] = useState("");
  const [explanation, setExplanation] = useState("");
  const [marks, setMarks] = useState("2");
  const [negative, setNegative] = useState("0");
  const [minWords, setMinWords] = useState("");
  const [maxWords, setMaxWords] = useState("");
  const [image, setImage] = useState<QuestionImage | null>(null);
  const [options, setOptions] = useState<DraftOption[]>([
    { text: "", is_correct: true },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
  ]);

  // --- per-type spec fields. Only the block for the active type is rendered,
  //     and only its values are sent, so switching type cannot smuggle stale
  //     configuration from a previous one into the payload.
  const [numericAnswer, setNumericAnswer] = useState("");
  const [tolerance, setTolerance] = useState("0");
  const [unit, setUnit] = useState("");
  const [acceptedAnswers, setAcceptedAnswers] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [languages, setLanguages] = useState<CodingLanguage[]>(["python"]);
  const [inputFormat, setInputFormat] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [constraints, setConstraints] = useState("");
  const [sampleInput, setSampleInput] = useState("");
  const [sampleOutput, setSampleOutput] = useState("");
  const [passageText, setPassageText] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const objective = OBJECTIVE.includes(type);
  const isContainer = CONTAINER_TYPES.includes(type);
  const needsModelAnswer = type === "short_answer" || type === "long_answer";
  const singleAnswer = type === "mcq" || type === "true_false";

  // A true/false question is two fixed options. Swapping to it replaces whatever the
  // examiner had typed, because "Option C" has no meaning here.
  function changeType(next: QuestionType) {
    setType(next);
    if (next === "true_false") {
      setOptions([
        { text: "True", is_correct: true },
        { text: "False", is_correct: false },
      ]);
    } else if (OBJECTIVE.includes(next) && options.length < 4) {
      setOptions([
        { text: "", is_correct: true },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
      ]);
    }
    if (CONTAINER_TYPES.includes(next)) {
      setMarks("0"); // a passage carries no marks - the server refuses otherwise
    } else if (marks === "0") {
      setMarks("2");
    }
  }

  function toggleCorrect(index: number) {
    setOptions((current) =>
      current.map((option, i) =>
        singleAnswer
          ? { ...option, is_correct: i === index } // exactly one, enforced in the UI too
          : i === index
            ? { ...option, is_correct: !option.is_correct }
            : option,
      ),
    );
  }

  function toggleLanguage(language: CodingLanguage) {
    setLanguages((current) =>
      current.includes(language)
        ? current.filter((l) => l !== language)
        : [...current, language],
    );
  }

  async function uploadImage(file: File) {
    const form = new FormData();
    form.append("file", file);
    try {
      setImage(await api.upload<QuestionImage>("/questions/images", form));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not upload that image.");
    }
  }

  /** Build the spec for the active type, or null when the type takes none. */
  function buildSpec(): Record<string, unknown> | null {
    switch (type) {
      case "numerical":
        return {
          answer: Number(numericAnswer),
          tolerance: Number(tolerance) || 0,
          unit: unit.trim() || null,
        };
      case "fill_blank":
        return {
          accepted_answers: acceptedAnswers
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean),
          case_sensitive: caseSensitive,
        };
      case "coding":
        return {
          languages,
          input_format: inputFormat.trim(),
          output_format: outputFormat.trim(),
          constraints: constraints.trim(),
          sample_cases: [{ input: sampleInput, output: sampleOutput }],
        };
      case "passage":
        return { passage_text: passageText.trim() || null, sticky: true };
      default:
        return null;
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    const payload = {
      subject_id: subjectId,
      question_type: type,
      category,
      topic: topic.trim() || null,
      difficulty,
      body: body.trim(),
      marks: Number(marks),
      negative_marks: Number(negative),
      model_answer: needsModelAnswer || type === "image_upload" ? modelAnswer.trim() || null : null,
      explanation: explanation.trim() || null,
      image_key: image?.image_key ?? null,
      // Only the active type's configuration is sent; every other type's fields are
      // ignored, so switching type cannot carry stale values into the payload.
      spec: buildSpec(),
      // Only written answers take word bounds - the API rejects them anywhere else.
      min_words: needsModelAnswer && minWords ? Number(minWords) : null,
      max_words: needsModelAnswer && maxWords ? Number(maxWords) : null,
      options: objective
        ? options
            .filter((option) => option.text.trim())
            .map((option, index) => ({
              text: option.text.trim(),
              is_correct: option.is_correct,
              order_index: index,
            }))
        : [],
    };

    try {
      await api.post("/questions", payload);
      toast("Question added to the bank", "mint");
      setBody("");
      setModelAnswer("");
      setExplanation("");
      setMinWords("");
      setMaxWords("");
      setImage(null);
      setNumericAnswer("");
      setTolerance("0");
      setUnit("");
      setAcceptedAnswers("");
      setInputFormat("");
      setOutputFormat("");
      setConstraints("");
      setSampleInput("");
      setSampleOutput("");
      setPassageText("");
      setOptions([
        { text: "", is_correct: true },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
        { text: "", is_correct: false },
      ]);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the question.");
    } finally {
      setBusy(false);
    }
  }

  if (subjects.length === 0) {
    return (
      <Card>
        <Alert tone="amber" title="Create a subject first">
          Every question belongs to a subject. Add one before composing questions.
        </Alert>
      </Card>
    );
  }

  return (
    <Card>
      <SectionTitle
        title="New question"
        hint="Validation mirrors the server: an MCQ needs exactly one correct option, written questions need a model answer."
      />
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          <Field label="Subject">
            <Select
              value={subjectId}
              onChange={(e) => setChosenSubjectId(e.target.value)}
              required
            >
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.code}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Type">
            <Select value={type} onChange={(e) => changeType(e.target.value as QuestionType)}>
              {Object.entries(TYPE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
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
          <div className="grid grid-cols-2 gap-2">
            <Field label="Marks">
              <Input
                type="number"
                min="0.5"
                step="0.5"
                value={marks}
                onChange={(e) => setMarks(e.target.value)}
                required
              />
            </Field>
            <Field label="Negative">
              <Input
                type="number"
                min="0"
                step="0.25"
                value={negative}
                onChange={(e) => setNegative(e.target.value)}
              />
            </Field>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Category" hint="The bank shelf. Corporate sections select on this.">
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
          <Field label="Topic" hint="Optional. e.g. OOP, Percentages, Blood Relations.">
            <Input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Free text"
              maxLength={120}
            />
          </Field>
        </div>

        <Field
          label={isContainer ? "Passage introduction" : "Question"}
          hint={image ? "Optional when a figure carries the question." : undefined}
        >
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={isContainer ? 5 : 3}
            placeholder={
              isContainer
                ? "A heading for the passage. The passage text itself goes below."
                : "Write the question exactly as the candidate should read it."
            }
            required={!image}
          />
        </Field>

        <Field label="Figure" hint="Optional. Shown above the question during the exam.">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void uploadImage(file);
              }}
              className="text-[13px] text-ink-soft file:mr-3 file:rounded-lg file:border file:border-line file:bg-surface-sunk file:px-3 file:py-1.5 file:text-[13px] file:text-ink"
            />
            {image?.thumbnail_url && (
              <span className="flex items-center gap-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={image.thumbnail_url}
                  alt="Uploaded figure preview"
                  className="h-14 w-auto rounded-lg border border-line object-contain"
                />
                <Button type="button" variant="ghost" onClick={() => setImage(null)}>
                  Remove
                </Button>
              </span>
            )}
          </div>
        </Field>

        {type === "numerical" && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Expected answer" hint="Required.">
              <Input
                type="number"
                step="any"
                value={numericAnswer}
                onChange={(e) => setNumericAnswer(e.target.value)}
                placeholder="9.81"
                required
              />
            </Field>
            <Field label="Tolerance" hint="Plus or minus. An answer this far out still scores.">
              <Input
                type="number"
                step="any"
                min="0"
                value={tolerance}
                onChange={(e) => setTolerance(e.target.value)}
              />
            </Field>
            <Field label="Unit" hint="Optional. Shown, never marked.">
              <Input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="m/s^2" />
            </Field>
          </div>
        )}

        {type === "fill_blank" && (
          <div className="space-y-4">
            <Field label="Accepted answers" hint="One per line. Any of them earns full marks.">
              <Textarea
                value={acceptedAnswers}
                onChange={(e) => setAcceptedAnswers(e.target.value)}
                rows={3}
                placeholder={"water\nH2O"}
                required
              />
            </Field>
            <label className="flex items-center gap-2 text-[13px] text-ink-soft">
              <input
                type="checkbox"
                checked={caseSensitive}
                onChange={(e) => setCaseSensitive(e.target.checked)}
                className="h-4 w-4 rounded border-line"
              />
              Match capitalisation exactly
            </label>
          </div>
        )}

        {type === "coding" && (
          <div className="space-y-4">
            <Field label="Languages" hint="What the candidate may answer in.">
              <div className="flex flex-wrap gap-3">
                {CODING_LANGUAGES.map((language) => (
                  <label
                    key={language}
                    className="flex items-center gap-2 text-[13px] text-ink-soft"
                  >
                    <input
                      type="checkbox"
                      checked={languages.includes(language)}
                      onChange={() => toggleLanguage(language)}
                      className="h-4 w-4 rounded border-line"
                    />
                    {LANGUAGE_LABEL[language]}
                  </label>
                ))}
              </div>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Input format">
                <Textarea
                  value={inputFormat}
                  onChange={(e) => setInputFormat(e.target.value)}
                  rows={2}
                  placeholder="A single integer n."
                  required
                />
              </Field>
              <Field label="Output format">
                <Textarea
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  rows={2}
                  placeholder="The nth Fibonacci number."
                  required
                />
              </Field>
            </div>
            <Field label="Constraints">
              <Input
                value={constraints}
                onChange={(e) => setConstraints(e.target.value)}
                placeholder="1 &lt;= n &lt;= 40"
                required
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Sample input">
                <Textarea
                  value={sampleInput}
                  onChange={(e) => setSampleInput(e.target.value)}
                  rows={2}
                  placeholder="5"
                />
              </Field>
              <Field label="Sample output">
                <Textarea
                  value={sampleOutput}
                  onChange={(e) => setSampleOutput(e.target.value)}
                  rows={2}
                  placeholder="5"
                />
              </Field>
            </div>
          </div>
        )}

        {isContainer && (
          <Field
            label="Passage text"
            hint="Shown above every question attached to this passage."
          >
            <Textarea
              value={passageText}
              onChange={(e) => setPassageText(e.target.value)}
              rows={8}
              placeholder="The full extract or case study."
            />
          </Field>
        )}

        {objective && (
          <div>
            <p className="mb-2 text-[13px] font-medium text-ink-soft">
              Options{" "}
              <span className="font-normal text-ink-muted">
                — {type === "mcq" ? "mark exactly one as correct" : "mark every correct option"}
              </span>
            </p>
            <div className="space-y-2">
              {options.map((option, index) => (
                <div key={index} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => toggleCorrect(index)}
                    className={cx(
                      "flex h-9 w-9 shrink-0 items-center justify-center border text-[12px] font-semibold transition",
                      type === "mcq" ? "rounded-full" : "rounded-[8px]",
                      option.is_correct
                        ? "border-mint bg-mint-soft text-mint"
                        : "border-line-strong text-ink-muted hover:bg-sunken",
                    )}
                    title={option.is_correct ? "Correct answer" : "Mark as correct"}
                  >
                    {String.fromCharCode(65 + index)}
                  </button>
                  <Input
                    value={option.text}
                    onChange={(e) =>
                      setOptions((current) =>
                        current.map((o, i) => (i === index ? { ...o, text: e.target.value } : o)),
                      )
                    }
                    placeholder={`Option ${String.fromCharCode(65 + index)}`}
                  />
                  {options.length > 2 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setOptions((c) => c.filter((_, i) => i !== index))}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              ))}
            </div>
            {options.length < 6 && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-2"
                onClick={() => setOptions((c) => [...c, { text: "", is_correct: false }])}
              >
                Add option
              </Button>
            )}
          </div>
        )}

        {(needsModelAnswer || type === "image_upload") && (
          <Field
            label={type === "image_upload" ? "Expected answer (for the examiner)" : "Model answer"}
            hint={
              needsModelAnswer
                ? "Required. The grader scores against this and the examiner sees it while reviewing."
                : "Optional guidance shown to the examiner when reviewing the scan."
            }
          >
            <Textarea
              value={modelAnswer}
              onChange={(e) => setModelAnswer(e.target.value)}
              rows={4}
              required={needsModelAnswer}
              placeholder="Describe what a full-mark answer contains."
            />
          </Field>
        )}

        {needsModelAnswer && (
          <div className="grid grid-cols-2 gap-2">
            <Field
              label="Minimum words"
              hint="Optional. Shown to the candidate; never blocks a save."
            >
              <Input
                type="number"
                min="0"
                step="10"
                value={minWords}
                onChange={(e) => setMinWords(e.target.value)}
                placeholder="No minimum"
              />
            </Field>
            <Field label="Maximum words" hint="Optional. Enforced — a longer answer is refused.">
              <Input
                type="number"
                min="1"
                step="10"
                value={maxWords}
                onChange={(e) => setMaxWords(e.target.value)}
                placeholder="No limit"
              />
            </Field>
          </div>
        )}

        {error && <Alert tone="rose">{error}</Alert>}

        <div className="flex justify-end gap-2">
          <Button type="submit" loading={busy}>
            Add to bank
          </Button>
        </div>
      </form>
    </Card>
  );
}
