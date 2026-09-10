"use client";

/**
 * The one place a question is authored, wherever the examiner happens to be.
 *
 * The question bank page and the exam wizard both mount this. That matters beyond
 * saving duplication: the validation an examiner meets while building an exam has to
 * be the same validation they meet in the bank, or the same question becomes valid in
 * one screen and invalid in the other.
 *
 * The answer key is composed here and travels to the server, and nowhere else. It is
 * never part of what a candidate's paper API returns - see PaperQuestion, which has no
 * is_correct, no model_answer, no spec beyond the candidate-safe projection.
 */

import { useMemo, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  CATEGORY_LABEL,
  CONTAINER_TYPES,
  OPTION_BEARING_TYPES,
  QUESTION_TYPE_LABEL,
  type CodingLanguage,
  type Difficulty,
  type Question,
  type QuestionCategory,
  type QuestionImage,
  type QuestionSource,
  type QuestionType,
  type Subject,
} from "@/lib/types";

const CODING_LANGUAGES: CodingLanguage[] = ["python", "java", "cpp", "javascript"];
const LANGUAGE_LABEL: Record<CodingLanguage, string> = {
  python: "Python",
  java: "Java",
  cpp: "C++",
  javascript: "JavaScript",
};

const IMAGE_FORMATS = ["jpeg", "png", "webp", "pdf"] as const;
type ImageFormat = (typeof IMAGE_FORMATS)[number];

interface DraftOption {
  text: string;
  is_correct: boolean;
}

interface SampleCase {
  input: string;
  output: string;
}

export interface QuestionEditorProps {
  subjects: Subject[];
  /** Editing an existing question rather than writing a new one. */
  question?: Question | null;
  /**
   * The exam being built, when the editor is open inside the wizard. Its presence is
   * what turns on "Save & add to exam" and the save-to-bank choice - a question with
   * no exam has nowhere else to live, so the choice would be meaningless.
   */
  examId?: string;
  /** Locks the subject to the exam's. A pool may not mix subjects. */
  lockedSubjectId?: string;
  /** Pre-selected type, e.g. when a section says it wants short answers. */
  initialType?: QuestionType;
  onSaved?: (question: Question) => void;
  onCancel?: () => void;
  /** Keep the form open and cleared after a save, for authoring several in a row. */
  stayOpen?: boolean;
}

/** Blank slate, or the question being edited unpacked back into form state. */
function initialOptions(question: Question | null | undefined, type: QuestionType): DraftOption[] {
  if (question && question.options.length) {
    return question.options.map((o) => ({ text: o.text, is_correct: Boolean(o.is_correct) }));
  }
  if (type === "true_false") {
    return [
      { text: "True", is_correct: true },
      { text: "False", is_correct: false },
    ];
  }
  return [
    { text: "", is_correct: true },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
    { text: "", is_correct: false },
  ];
}

export function QuestionEditor({
  subjects,
  question = null,
  examId,
  lockedSubjectId,
  initialType,
  onSaved,
  onCancel,
  stayOpen = false,
}: QuestionEditorProps) {
  const editing = question !== null;
  const spec = (question?.spec ?? {}) as Record<string, unknown>;

  const [chosenSubjectId, setChosenSubjectId] = useState(question?.subject_id ?? "");
  const subjectId = lockedSubjectId || chosenSubjectId || subjects[0]?.id || "";

  const [type, setType] = useState<QuestionType>(
    question?.question_type ?? initialType ?? "mcq",
  );
  const [category, setCategory] = useState<QuestionCategory>(question?.category ?? "academic");
  const [topic, setTopic] = useState(question?.topic ?? "");
  const [difficulty, setDifficulty] = useState<Difficulty>(question?.difficulty ?? "medium");
  const [body, setBody] = useState(question?.body ?? "");
  const [modelAnswer, setModelAnswer] = useState(question?.model_answer ?? "");
  const [explanation, setExplanation] = useState(question?.explanation ?? "");
  const [marks, setMarks] = useState(String(question?.marks ?? 2));
  const [negative, setNegative] = useState(String(question?.negative_marks ?? 0));
  const [minWords, setMinWords] = useState(question?.min_words ? String(question.min_words) : "");
  const [maxWords, setMaxWords] = useState(question?.max_words ? String(question.max_words) : "");
  const [tags, setTags] = useState((question?.tags ?? []).join(", "));
  const [image, setImage] = useState<QuestionImage | null>(
    question?.image_key
      ? {
          image_key: question.image_key,
          image_url: question.image_url ?? null,
          thumbnail_url: question.image_url ?? null,
        }
      : null,
  );
  const [options, setOptions] = useState<DraftOption[]>(
    initialOptions(question, question?.question_type ?? initialType ?? "mcq"),
  );

  // --- rubric. Stored as JSON on the question; edited here as key points and a
  //     free-text scheme, because that is how examiners actually write one.
  const rubricSource = (question?.rubric ?? {}) as Record<string, unknown>;
  const [keyPoints, setKeyPoints] = useState(
    Array.isArray(rubricSource.key_points) ? (rubricSource.key_points as string[]).join("\n") : "",
  );
  const [rubricNotes, setRubricNotes] = useState(
    typeof rubricSource.scheme === "string" ? rubricSource.scheme : "",
  );

  // --- per-type configuration. Only the active type's block renders, and only its
  //     values are sent, so switching type cannot smuggle stale config into a payload.
  const [numericAnswer, setNumericAnswer] = useState(
    spec.answer !== undefined ? String(spec.answer) : "",
  );
  const [tolerance, setTolerance] = useState(
    spec.tolerance !== undefined ? String(spec.tolerance) : "0",
  );
  const [unit, setUnit] = useState(typeof spec.unit === "string" ? spec.unit : "");
  const [acceptedAnswers, setAcceptedAnswers] = useState(
    Array.isArray(spec.accepted_answers) ? (spec.accepted_answers as string[]).join("\n") : "",
  );
  const [caseSensitive, setCaseSensitive] = useState(Boolean(spec.case_sensitive));
  const [languages, setLanguages] = useState<CodingLanguage[]>(
    Array.isArray(spec.languages) ? (spec.languages as CodingLanguage[]) : ["python"],
  );
  const [inputFormat, setInputFormat] = useState(
    typeof spec.input_format === "string" ? spec.input_format : "",
  );
  const [outputFormat, setOutputFormat] = useState(
    typeof spec.output_format === "string" ? spec.output_format : "",
  );
  const [constraints, setConstraints] = useState(
    typeof spec.constraints === "string" ? spec.constraints : "",
  );
  const [sampleCases, setSampleCases] = useState<SampleCase[]>(
    Array.isArray(spec.sample_cases) && spec.sample_cases.length
      ? (spec.sample_cases as SampleCase[]).map((c) => ({ input: c.input, output: c.output }))
      : [{ input: "", output: "" }],
  );
  const [passageText, setPassageText] = useState(
    typeof spec.passage_text === "string" ? spec.passage_text : "",
  );
  const [uploadFormats, setUploadFormats] = useState<ImageFormat[]>(
    Array.isArray(spec.allowed_formats)
      ? (spec.allowed_formats as ImageFormat[])
      : ["jpeg", "png"],
  );
  const [uploadInstructions, setUploadInstructions] = useState(
    typeof spec.instructions === "string" ? spec.instructions : "",
  );

  const [saveToBank, setSaveToBank] = useState(!question?.exam_only);
  const [busy, setBusy] = useState<"save" | "save-add" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const objective = OPTION_BEARING_TYPES.includes(type);
  const isContainer = CONTAINER_TYPES.includes(type);
  const needsModelAnswer = type === "short_answer" || type === "long_answer";
  const singleAnswer = type === "mcq" || type === "true_false";
  const takesRubric = needsModelAnswer || type === "image_upload";

  const correctCount = options.filter((o) => o.is_correct && o.text.trim()).length;

  /** Live mirror of the server's rules, so the examiner is told before they submit. */
  const problems = useMemo(() => {
    const found: string[] = [];
    if (!subjectId) found.push("Pick a subject.");
    if (!body.trim() && !image) found.push("Write the question, or attach a figure.");
    if (objective) {
      const filled = options.filter((o) => o.text.trim());
      if (filled.length < 2) found.push("Give at least two options.");
      if (correctCount === 0) found.push("Mark the correct answer.");
      if (singleAnswer && correctCount > 1) found.push("Only one option may be correct.");
    }
    if (needsModelAnswer && !modelAnswer.trim()) {
      found.push("A written question needs a model answer to grade against.");
    }
    if (type === "numerical" && numericAnswer.trim() === "") {
      found.push("Give the expected numerical answer.");
    }
    if (type === "fill_blank" && !acceptedAnswers.trim()) {
      found.push("List at least one accepted answer.");
    }
    if (type === "coding" && languages.length === 0) {
      found.push("Pick at least one programming language.");
    }
    if (!isContainer && Number(marks) <= 0) found.push("Marks must be greater than zero.");
    if (minWords && maxWords && Number(minWords) > Number(maxWords)) {
      found.push("The minimum word count is above the maximum.");
    }
    return found;
  }, [
    subjectId,
    body,
    image,
    objective,
    options,
    correctCount,
    singleAnswer,
    needsModelAnswer,
    modelAnswer,
    type,
    numericAnswer,
    acceptedAnswers,
    languages,
    isContainer,
    marks,
    minWords,
    maxWords,
  ]);

  // A true/false question is two fixed options - "Option C" has no meaning there.
  function changeType(next: QuestionType) {
    setType(next);
    if (next === "true_false") {
      setOptions([
        { text: "True", is_correct: true },
        { text: "False", is_correct: false },
      ]);
    } else if (OPTION_BEARING_TYPES.includes(next) && options.length < 4) {
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

  function setCorrect(index: number) {
    setOptions((current) =>
      current.map((option, i) =>
        singleAnswer
          ? { ...option, is_correct: i === index }
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

  function toggleFormat(format: ImageFormat) {
    setUploadFormats((current) =>
      current.includes(format) ? current.filter((f) => f !== format) : [...current, format],
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
          sample_cases: sampleCases
            .filter((c) => c.input.trim() || c.output.trim())
            .map((c) => ({ input: c.input, output: c.output })),
        };
      case "passage":
        return { passage_text: passageText.trim() || null, sticky: true };
      case "image_upload":
        return {
          allowed_formats: uploadFormats,
          instructions: uploadInstructions.trim() || null,
        };
      default:
        return null;
    }
  }

  function buildRubric(): Record<string, unknown> | null {
    if (!takesRubric) return null;
    const points = keyPoints
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (!points.length && !rubricNotes.trim()) return null;
    return { key_points: points, scheme: rubricNotes.trim() || null };
  }

  function reset() {
    setBody("");
    setModelAnswer("");
    setExplanation("");
    setMinWords("");
    setMaxWords("");
    setTags("");
    setImage(null);
    setKeyPoints("");
    setRubricNotes("");
    setNumericAnswer("");
    setTolerance("0");
    setUnit("");
    setAcceptedAnswers("");
    setInputFormat("");
    setOutputFormat("");
    setConstraints("");
    setSampleCases([{ input: "", output: "" }]);
    setPassageText("");
    setUploadInstructions("");
    setOptions(initialOptions(null, type));
  }

  async function save(addToExam: boolean) {
    if (problems.length) {
      setError(problems[0]);
      return;
    }
    setBusy(addToExam ? "save-add" : "save");
    setError(null);

    const payload: Record<string, unknown> = {
      subject_id: subjectId,
      question_type: type,
      category,
      topic: topic.trim() || null,
      difficulty,
      body: body.trim(),
      marks: Number(marks),
      negative_marks: Number(negative),
      model_answer: takesRubric ? modelAnswer.trim() || null : null,
      explanation: explanation.trim() || null,
      rubric: buildRubric(),
      image_key: image?.image_key ?? null,
      spec: buildSpec(),
      tags: tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
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
      let saved: Question;
      if (editing && question) {
        saved = await api.patch<Question>(`/questions/${question.id}`, payload);
        toast("Question updated", "mint");
      } else {
        // Only a brand-new question carries these: an edit never moves a question
        // between the bank and an exam, which would surprise anyone reusing it.
        if (addToExam && examId) {
          payload.exam_id = examId;
          payload.save_to_bank = saveToBank;
        }
        saved = await api.post<Question>("/questions", payload);
        toast(
          addToExam && examId
            ? saveToBank
              ? "Added to the exam and saved to your bank"
              : "Added to this exam only"
            : "Question saved to your bank",
          "mint",
        );
      }
      onSaved?.(saved);
      if (stayOpen && !editing) reset();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the question.");
    } finally {
      setBusy(null);
    }
  }

  if (subjects.length === 0) {
    return (
      <Alert tone="amber" title="Create a subject first">
        Every question belongs to a subject. Add one before writing questions.
      </Alert>
    );
  }

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        void save(Boolean(examId));
      }}
    >
      {/* ---------------------------------------------------------- classification */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Subject" required>
          <Select
            value={subjectId}
            onChange={(e) => setChosenSubjectId(e.target.value)}
            disabled={Boolean(lockedSubjectId) || editing}
            required
          >
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.code} — {subject.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Question type" required>
          <Select
            value={type}
            onChange={(e) => changeType(e.target.value as QuestionType)}
            disabled={editing}
          >
            {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => (
              <option key={value} value={value}>
                {QUESTION_TYPE_LABEL[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Difficulty">
          <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Marks" required={!isContainer}>
            <Input
              type="number"
              min="0"
              step="0.5"
              value={marks}
              onChange={(e) => setMarks(e.target.value)}
              disabled={isContainer}
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

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Category" hint="The bank shelf. Corporate sections select on this.">
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value as QuestionCategory)}
          >
            {(Object.keys(CATEGORY_LABEL) as QuestionCategory[]).map((value) => (
              <option key={value} value={value}>
                {CATEGORY_LABEL[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Topic" hint="e.g. Neural Networks, Percentages, Blood Relations.">
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Free text"
            maxLength={120}
          />
        </Field>
        <Field label="Tags" hint="Comma separated. Used for searching the bank.">
          <Input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="unit-3, revision"
          />
        </Field>
      </div>

      {/* ---------------------------------------------------------------- the ask */}
      <Field
        label={isContainer ? "Passage introduction" : "Question"}
        required={!image}
        hint={image ? "Optional when the figure carries the question." : undefined}
      >
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={isContainer ? 4 : 3}
          placeholder={
            isContainer
              ? "A heading for the passage. The passage text itself goes below."
              : "Write the question exactly as the candidate should read it."
          }
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
            className="text-[13px] text-ink-soft file:mr-3 file:rounded-lg file:border file:border-line file:bg-sunken file:px-3 file:py-1.5 file:text-[13px] file:text-ink"
          />
          {image?.thumbnail_url && (
            <span className="flex items-center gap-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={image.thumbnail_url}
                alt="Uploaded figure preview"
                className="h-14 w-auto rounded-lg border border-line object-contain"
              />
              <Button type="button" variant="ghost" size="sm" onClick={() => setImage(null)}>
                Remove
              </Button>
            </span>
          )}
        </div>
      </Field>

      {/* ------------------------------------------------------- options + the key */}
      {objective && (
        <OptionsAndKey
          type={type}
          options={options}
          singleAnswer={singleAnswer}
          onChangeText={(index, text) =>
            setOptions((current) =>
              current.map((o, i) => (i === index ? { ...o, text } : o)),
            )
          }
          onSetCorrect={setCorrect}
          onRemove={(index) => setOptions((c) => c.filter((_, i) => i !== index))}
          onAdd={() => setOptions((c) => [...c, { text: "", is_correct: false }])}
        />
      )}

      {/* ------------------------------------------------------ per-type answer key */}
      {type === "numerical" && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Expected answer" required>
            <Input
              type="number"
              step="any"
              value={numericAnswer}
              onChange={(e) => setNumericAnswer(e.target.value)}
              placeholder="9.81"
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
          <Field label="Unit" hint="Shown to the candidate, never marked.">
            <Input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="m/s²" />
          </Field>
        </div>
      )}

      {type === "fill_blank" && (
        <div className="space-y-3">
          <Field label="Accepted answers" required hint="One per line. Any of them scores full marks.">
            <Textarea
              value={acceptedAnswers}
              onChange={(e) => setAcceptedAnswers(e.target.value)}
              rows={3}
              placeholder={"water\nH2O"}
            />
          </Field>
          <Checkbox
            checked={caseSensitive}
            onChange={setCaseSensitive}
            label="Match capitalisation exactly"
          />
        </div>
      )}

      {type === "coding" && (
        <div className="space-y-4 rounded-[12px] border border-line bg-sunken/40 p-4">
          <Field label="Languages" required hint="What the candidate may answer in.">
            <div className="flex flex-wrap gap-4">
              {CODING_LANGUAGES.map((language) => (
                <Checkbox
                  key={language}
                  checked={languages.includes(language)}
                  onChange={() => toggleLanguage(language)}
                  label={LANGUAGE_LABEL[language]}
                />
              ))}
            </div>
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Input format" required>
              <Textarea
                value={inputFormat}
                onChange={(e) => setInputFormat(e.target.value)}
                rows={2}
                placeholder="A single integer n."
              />
            </Field>
            <Field label="Output format" required>
              <Textarea
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                rows={2}
                placeholder="The nth Fibonacci number."
              />
            </Field>
          </div>
          <Field label="Constraints" required>
            <Input
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder="1 <= n <= 40"
            />
          </Field>
          <div>
            <p className="mb-2 text-[13px] font-medium text-ink-soft">
              Test cases{" "}
              <span className="font-normal text-ink-muted">
                — the first pair is shown to the candidate as the worked example
              </span>
            </p>
            <div className="space-y-2">
              {sampleCases.map((sample, index) => (
                <div key={index} className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                  <Textarea
                    rows={2}
                    value={sample.input}
                    onChange={(e) =>
                      setSampleCases((c) =>
                        c.map((s, i) => (i === index ? { ...s, input: e.target.value } : s)),
                      )
                    }
                    placeholder={index === 0 ? "Sample input" : `Input ${index + 1}`}
                  />
                  <Textarea
                    rows={2}
                    value={sample.output}
                    onChange={(e) =>
                      setSampleCases((c) =>
                        c.map((s, i) => (i === index ? { ...s, output: e.target.value } : s)),
                      )
                    }
                    placeholder={index === 0 ? "Sample output" : `Output ${index + 1}`}
                  />
                  {sampleCases.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setSampleCases((c) => c.filter((_, i) => i !== index))}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              ))}
            </div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={() => setSampleCases((c) => [...c, { input: "", output: "" }])}
            >
              Add test case
            </Button>
          </div>
        </div>
      )}

      {isContainer && (
        <Field label="Passage text" hint="Shown above every question attached to this passage.">
          <Textarea
            value={passageText}
            onChange={(e) => setPassageText(e.target.value)}
            rows={8}
            placeholder="The full extract or case study."
          />
        </Field>
      )}

      {type === "image_upload" && (
        <div className="space-y-3">
          <Field label="Instructions to the candidate" hint="Shown beside the upload control.">
            <Textarea
              value={uploadInstructions}
              onChange={(e) => setUploadInstructions(e.target.value)}
              rows={2}
              placeholder="Write your working on paper, then photograph the whole page."
            />
          </Field>
          <Field label="Allowed formats">
            <div className="flex flex-wrap gap-4">
              {IMAGE_FORMATS.map((format) => (
                <Checkbox
                  key={format}
                  checked={uploadFormats.includes(format)}
                  onChange={() => toggleFormat(format)}
                  label={format.toUpperCase()}
                />
              ))}
            </div>
          </Field>
        </div>
      )}

      {/* -------------------------------------------------- model answer and rubric */}
      {takesRubric && (
        <div className="space-y-4 rounded-[12px] border border-line bg-sunken/40 p-4">
          <p className="text-[12.5px] text-ink-muted">
            Examiner-only. None of this reaches the candidate during the exam — it is what
            the grader scores against and what you read while reviewing.
          </p>
          <Field
            label={type === "image_upload" ? "Expected answer" : "Model answer"}
            required={needsModelAnswer}
          >
            <Textarea
              value={modelAnswer}
              onChange={(e) => setModelAnswer(e.target.value)}
              rows={4}
              placeholder="Describe what a full-mark answer contains."
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Key points" hint="One per line. The grader reports which were hit.">
              <Textarea
                value={keyPoints}
                onChange={(e) => setKeyPoints(e.target.value)}
                rows={4}
                placeholder={"Defines the term\nGives an example\nStates a limitation"}
              />
            </Field>
            <Field label="Marking scheme" hint="Free text. How marks are apportioned.">
              <Textarea
                value={rubricNotes}
                onChange={(e) => setRubricNotes(e.target.value)}
                rows={4}
                placeholder="2 marks for the definition, 2 for a worked example, 1 for the caveat."
              />
            </Field>
          </div>
          {needsModelAnswer && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Minimum words" hint="Shown to the candidate; never blocks a save.">
                <Input
                  type="number"
                  min="0"
                  step="10"
                  value={minWords}
                  onChange={(e) => setMinWords(e.target.value)}
                  placeholder="No minimum"
                />
              </Field>
              <Field label="Maximum words" hint="Enforced — a longer answer is refused.">
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
        </div>
      )}

      <Field label="Explanation" hint="Optional. Released with the result, never during the exam.">
        <Textarea
          value={explanation}
          onChange={(e) => setExplanation(e.target.value)}
          rows={2}
          placeholder="Why the correct answer is correct."
        />
      </Field>

      {/* --------------------------------------------------------------- save block */}
      {problems.length > 0 && (
        <Alert tone="amber" title="Not ready to save">
          <ul className="list-inside list-disc space-y-0.5">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </Alert>
      )}
      {error && <Alert tone="rose">{error}</Alert>}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        {examId && !editing ? (
          <Checkbox
            checked={saveToBank}
            onChange={setSaveToBank}
            label="Save to my Question Bank"
            hint={
              saveToBank
                ? "Reusable in future exams."
                : "This exam only — it will not appear in the bank."
            }
          />
        ) : (
          <span className="text-[12px] text-ink-muted">
            {editing ? "Editing an existing question." : "Saved to your Question Bank."}
          </span>
        )}
        <div className="flex gap-2">
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
          {examId && !editing && (
            <Button
              type="button"
              variant="secondary"
              loading={busy === "save"}
              disabled={busy !== null || problems.length > 0}
              onClick={() => void save(false)}
            >
              Save to bank only
            </Button>
          )}
          <Button
            type="submit"
            loading={busy !== null}
            disabled={busy !== null || problems.length > 0}
          >
            {editing ? "Save changes" : examId ? "Save & add to exam" : "Save question"}
          </Button>
        </div>
      </div>
    </form>
  );
}

/**
 * Options and the answer key, side by side.
 *
 * The spec asks for the key to be its own labelled control rather than a subtle tint on
 * an option row - an examiner should be able to glance at the form and read off which
 * answer they marked, without having to decode the styling.
 */
function OptionsAndKey({
  type,
  options,
  singleAnswer,
  onChangeText,
  onSetCorrect,
  onRemove,
  onAdd,
}: {
  type: QuestionType;
  options: DraftOption[];
  singleAnswer: boolean;
  onChangeText: (index: number, text: string) => void;
  onSetCorrect: (index: number) => void;
  onRemove: (index: number) => void;
  onAdd: () => void;
}) {
  const letters = options.map((_, i) => String.fromCharCode(65 + i));
  const chosen = options
    .map((option, index) => (option.is_correct ? letters[index] : null))
    .filter(Boolean) as string[];

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-[13px] font-medium text-ink-soft">Options</p>
        <div className="space-y-2">
          {options.map((option, index) => (
            <div key={index} className="flex items-center gap-2">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] border border-line-strong bg-sunken text-[12px] font-semibold text-ink-soft">
                {letters[index]}
              </span>
              <Input
                value={option.text}
                onChange={(e) => onChangeText(index, e.target.value)}
                placeholder={`Option ${letters[index]}`}
                disabled={type === "true_false"}
              />
              {options.length > 2 && type !== "true_false" && (
                <Button type="button" variant="ghost" size="sm" onClick={() => onRemove(index)}>
                  Remove
                </Button>
              )}
            </div>
          ))}
        </div>
        {options.length < 6 && type !== "true_false" && (
          <Button type="button" variant="secondary" size="sm" className="mt-2" onClick={onAdd}>
            Add option
          </Button>
        )}
      </div>

      <div className="rounded-[12px] border border-accent-border bg-accent-soft/40 p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <p className="text-[13px] font-semibold text-ink">Correct answer</p>
          <Badge tone="accent">examiner only</Badge>
          <span className="text-[12px] text-ink-muted">
            {singleAnswer ? "Select the correct option." : "Select every correct option."}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {options.map((option, index) => (
            <button
              key={index}
              type="button"
              onClick={() => onSetCorrect(index)}
              disabled={!option.text.trim()}
              aria-pressed={option.is_correct}
              className={cx(
                "flex items-center gap-2 rounded-[9px] border px-3 py-2 text-[13px] transition",
                "disabled:cursor-not-allowed disabled:opacity-45",
                option.is_correct
                  ? "border-accent bg-accent text-white shadow-sm"
                  : "border-line-strong bg-surface text-ink-soft hover:border-accent/60",
              )}
            >
              <span
                className={cx(
                  "flex h-4 w-4 items-center justify-center border",
                  singleAnswer ? "rounded-full" : "rounded-[4px]",
                  option.is_correct ? "border-white bg-white/25" : "border-line-strong",
                )}
              >
                {option.is_correct && <span className="text-[10px] leading-none">✓</span>}
              </span>
              <span className="font-semibold">{letters[index]}</span>
              <span className="max-w-[16rem] truncate">
                {option.text.trim() || "empty option"}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-[12px] text-ink-muted">
          {chosen.length
            ? `Marked correct: ${chosen.join(", ")}. Stored on the server and never sent to a candidate's browser.`
            : "Nothing marked correct yet — the question cannot be saved until you choose."}
        </p>
      </div>
    </div>
  );
}

function Checkbox({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  hint?: string;
}) {
  return (
    <label className="flex items-start gap-2 text-[13px] text-ink-soft">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="mt-0.5 h-4 w-4 rounded border-line-strong"
      />
      <span>
        {label}
        {hint && <span className="block text-[12px] text-ink-muted">{hint}</span>}
      </span>
    </label>
  );
}

/**
 * The editor in a card with a heading, for pages that want it inline rather than in a
 * modal. Kept here so callers do not each invent their own framing.
 */
export function QuestionEditorCard(props: QuestionEditorProps & { title?: string }) {
  const { title, ...editorProps } = props;
  return (
    <Card>
      <div className="mb-4 flex items-center gap-2">
        <h3 className="text-[15px] font-semibold tracking-tight text-ink">
          {title ?? (props.question ? "Edit question" : "Create question")}
        </h3>
        {props.question && (
          <Badge tone="neutral">{QUESTION_TYPE_LABEL[props.question.question_type]}</Badge>
        )}
      </div>
      <QuestionEditor {...editorProps} />
    </Card>
  );
}

/** Re-exported so callers can label a question's provenance without importing twice. */
export function SourceBadge({ source }: { source: QuestionSource }) {
  if (source === "ai_generated") return <Badge tone="purple">AI generated</Badge>;
  if (source === "imported") return <Badge tone="amber">Imported</Badge>;
  return null;
}
