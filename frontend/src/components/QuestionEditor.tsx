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

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

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
import { LOCALE_NAMES, SUPPORTED_LOCALES, type Locale } from "@/lib/locale";
import {
  CATEGORY_LABEL,
  CONTAINER_TYPES,
  OPTION_BEARING_TYPES,
  QUESTION_TYPE_LABEL,
  type CodingLanguage,
  type Difficulty,
  type GeneratedTranslations,
  type Question,
  type QuestionCategory,
  type QuestionImage,
  type QuestionSource,
  type QuestionType,
  type Subject,
} from "@/lib/types";

//: Every locale the platform supports, except English - English is the master text
//: authored above, never a "translation" of itself.
const TRANSLATABLE_LOCALES = SUPPORTED_LOCALES.filter((l) => l !== "en") as Locale[];

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
  /** Per-locale translated text, keyed by locale (never "en" - see `text` above). */
  translations: Record<string, string>;
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
  /**
   * Starting content for a NEW question - a worked example the examiner is adapting.
   *
   * Distinct from `question` on purpose: a seed prefills the form but the save is still
   * a POST. Passing an example as `question` would make the editor believe it is editing
   * something that exists, and PATCH an id that was never real.
   */
  seed?: Partial<Question> | null;
  /** Pre-selected difficulty, e.g. the section rule this question is being written for. */
  initialDifficulty?: Difficulty;
  onSaved?: (question: Question) => void;
  onCancel?: () => void;
  /** Keep the form open and cleared after a save, for authoring several in a row. */
  stayOpen?: boolean;
}

/** Blank slate, or the question being edited unpacked back into form state. */
function initialOptions(
  question: Partial<Question> | null | undefined,
  type: QuestionType,
): DraftOption[] {
  if (question?.options?.length) {
    return question.options.map((o) => ({
      text: o.text,
      is_correct: Boolean(o.is_correct),
      translations: stripEnglish(o.translations),
    }));
  }
  if (type === "true_false") {
    return [
      { text: "True", is_correct: true, translations: {} },
      { text: "False", is_correct: false, translations: {} },
    ];
  }
  return [
    { text: "", is_correct: true, translations: {} },
    { text: "", is_correct: false, translations: {} },
    { text: "", is_correct: false, translations: {} },
    { text: "", is_correct: false, translations: {} },
  ];
}

function stripEnglish(map: Record<string, string> | undefined): Record<string, string> {
  if (!map) return {};
  const { en: _en, ...rest } = map;
  return rest;
}

export function QuestionEditor({
  subjects,
  question = null,
  examId,
  lockedSubjectId,
  initialType,
  seed = null,
  initialDifficulty,
  onSaved,
  onCancel,
  stayOpen = false,
}: QuestionEditorProps) {
  const t = useTranslations("question");
  const editing = question !== null;
  /** What the form starts from. Only `question` decides whether the save is an edit. */
  const source = question ?? seed;
  const spec = (source?.spec ?? {}) as Record<string, unknown>;

  const [chosenSubjectId, setChosenSubjectId] = useState(source?.subject_id ?? "");
  const subjectId = lockedSubjectId || chosenSubjectId || subjects[0]?.id || "";

  const [type, setType] = useState<QuestionType>(
    source?.question_type ?? initialType ?? "mcq",
  );
  const [category, setCategory] = useState<QuestionCategory>(source?.category ?? "academic");
  const [topic, setTopic] = useState(source?.topic ?? "");
  const [difficulty, setDifficulty] = useState<Difficulty>(
    source?.difficulty ?? initialDifficulty ?? "medium",
  );
  const [body, setBody] = useState(source?.body ?? "");
  const [modelAnswer, setModelAnswer] = useState(source?.model_answer ?? "");
  const [explanation, setExplanation] = useState(source?.explanation ?? "");
  const [marks, setMarks] = useState(String(source?.marks ?? 2));
  const [negative, setNegative] = useState(String(source?.negative_marks ?? 0));
  const [minWords, setMinWords] = useState(source?.min_words ? String(source.min_words) : "");
  const [maxWords, setMaxWords] = useState(source?.max_words ? String(source.max_words) : "");
  const [tagList, setTagList] = useState<string[]>(source?.tags ?? []);
  const [tagInput, setTagInput] = useState("");
  const [knownTags, setKnownTags] = useState<string[]>([]);
  const [duplicateMatches, setDuplicateMatches] = useState<{ id: string; body: string }[]>([]);
  const [checkingDuplicate, setCheckingDuplicate] = useState(false);

  useEffect(() => {
    api
      .get<string[]>("/questions/tags")
      .then(setKnownTags)
      .catch(() => setKnownTags([])); // a missing tag list only costs autocomplete
  }, []);

  function addTag(raw: string) {
    const value = raw.trim();
    if (!value || tagList.includes(value)) return;
    setTagList((prev) => [...prev, value]);
    setTagInput("");
  }

  function removeTag(value: string) {
    setTagList((prev) => prev.filter((t) => t !== value));
  }

  // Non-blocking heads-up, not a gate: an examiner may genuinely want a near-duplicate
  // (a harder variant of the same question), so this only informs, never disables Save.
  useEffect(() => {
    if (!subjectId || body.trim().length < 8) {
      setDuplicateMatches([]);
      return;
    }
    setCheckingDuplicate(true);
    const timer = window.setTimeout(() => {
      api
        .post<{ matches: { id: string; body: string }[] }>("/questions/check-duplicate", {
          subject_id: subjectId,
          body: body.trim(),
          exclude_question_id: question?.id ?? null,
        })
        .then((res) => setDuplicateMatches(res.matches))
        .catch(() => setDuplicateMatches([]))
        .finally(() => setCheckingDuplicate(false));
    }, 600);
    return () => window.clearTimeout(timer);
  }, [body, subjectId, question?.id]);
  const [image, setImage] = useState<QuestionImage | null>(
    source?.image_key
      ? {
          image_key: source.image_key,
          image_url: source.image_url ?? null,
          thumbnail_url: source.image_url ?? null,
        }
      : null,
  );
  const [options, setOptions] = useState<DraftOption[]>(
    initialOptions(source, source?.question_type ?? initialType ?? "mcq"),
  );

  // --- translations. English above stays the master; these are optional per-locale
  //     overrides, entered by hand or via "Generate Translations" (which only fills the
  //     form - nothing is saved until the question itself is saved).
  const existingQuestionTranslations = (question?.translations ?? {}) as Record<
    string,
    { body?: string; explanation?: string }
  >;
  const [selectedLocales, setSelectedLocales] = useState<Locale[]>(
    () =>
      TRANSLATABLE_LOCALES.filter(
        (l) => existingQuestionTranslations[l] || question?.options?.some((o) => o.translations?.[l]),
      ),
  );
  const [qTranslations, setQTranslations] = useState<
    Record<string, { body: string; explanation: string }>
  >(() => {
    const out: Record<string, { body: string; explanation: string }> = {};
    for (const l of TRANSLATABLE_LOCALES) {
      const t = existingQuestionTranslations[l];
      out[l] = { body: t?.body ?? "", explanation: t?.explanation ?? "" };
    }
    return out;
  });
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generateNotice, setGenerateNotice] = useState<string | null>(null);

  function toggleLocale(locale: Locale) {
    setSelectedLocales((current) =>
      current.includes(locale) ? current.filter((l) => l !== locale) : [...current, locale],
    );
  }

  function setOptionTranslation(index: number, locale: Locale, text: string) {
    setOptions((current) =>
      current.map((o, i) =>
        i === index ? { ...o, translations: { ...o.translations, [locale]: text } } : o,
      ),
    );
  }

  async function generateTranslations() {
    if (!question) return; // needs a saved question id - see the disabled hint in the UI
    setGenerating(true);
    setGenerateError(null);
    setGenerateNotice(null);
    try {
      const targets = selectedLocales.length ? selectedLocales : TRANSLATABLE_LOCALES;
      const result = await api.post<GeneratedTranslations>(
        `/questions/${question.id}/generate-translations`,
        { locales: targets, overwrite_existing: true },
      );
      setQTranslations((current) => {
        const next = { ...current };
        for (const [locale, fields] of Object.entries(result.translations)) {
          next[locale] = { body: fields.body ?? "", explanation: fields.explanation ?? "" };
        }
        return next;
      });
      setOptions((current) =>
        current.map((o, i) => {
          const optionId = question.options[i]?.id;
          if (!optionId) return o;
          const perLocale = result.options[optionId];
          if (!perLocale) return o;
          return { ...o, translations: { ...o.translations, ...perLocale } };
        }),
      );
      setSelectedLocales((current) => Array.from(new Set([...current, ...targets])));
      setGenerateNotice(
        result.provider === "stub"
          ? "No translation model is configured, so this only copied the English text — edit each field by hand before saving."
          : "Generated. Review and edit before saving — nothing is saved yet.",
      );
    } catch (err) {
      setGenerateError(
        err instanceof ApiError ? err.message : "Could not generate translations. Try again.",
      );
    } finally {
      setGenerating(false);
    }
  }

  // --- rubric. Stored as JSON on the question; edited here as key points and a
  //     free-text scheme, because that is how examiners actually write one.
  const rubricSource = (source?.rubric ?? {}) as Record<string, unknown>;
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

  const [saveToBank, setSaveToBank] = useState(!source?.exam_only);
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
        { text: "True", is_correct: true, translations: {} },
        { text: "False", is_correct: false, translations: {} },
      ]);
    } else if (OPTION_BEARING_TYPES.includes(next) && options.length < 4) {
      setOptions([
        { text: "", is_correct: true, translations: {} },
        { text: "", is_correct: false, translations: {} },
        { text: "", is_correct: false, translations: {} },
        { text: "", is_correct: false, translations: {} },
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
    setTagList([]);
    setTagInput("");
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
    setSelectedLocales([]);
    setQTranslations(Object.fromEntries(TRANSLATABLE_LOCALES.map((l) => [l, { body: "", explanation: "" }])));
    setGenerateNotice(null);
    setGenerateError(null);
  }

  function buildQuestionTranslationsPayload(): Record<string, Record<string, string>> | undefined {
    if (!selectedLocales.length) return undefined;
    const out: Record<string, Record<string, string>> = {};
    for (const locale of selectedLocales) {
      const fields: Record<string, string> = {};
      const t = qTranslations[locale];
      if (t?.body.trim()) fields.body = t.body.trim();
      if (t?.explanation.trim()) fields.explanation = t.explanation.trim();
      if (Object.keys(fields).length) out[locale] = fields;
    }
    return Object.keys(out).length ? out : undefined;
  }

  function buildOptionTranslationsPayload(
    option: DraftOption,
  ): Record<string, Record<string, string>> | undefined {
    if (!selectedLocales.length) return undefined;
    const out: Record<string, Record<string, string>> = {};
    for (const locale of selectedLocales) {
      const text = option.translations[locale]?.trim();
      if (text) out[locale] = { text };
    }
    return Object.keys(out).length ? out : undefined;
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
      tags: tagList,
      min_words: needsModelAnswer && minWords ? Number(minWords) : null,
      max_words: needsModelAnswer && maxWords ? Number(maxWords) : null,
      options: objective
        ? options
            .filter((option) => option.text.trim())
            .map((option, index) => ({
              text: option.text.trim(),
              is_correct: option.is_correct,
              order_index: index,
              translations: buildOptionTranslationsPayload(option),
            }))
        : [],
      translations: buildQuestionTranslationsPayload(),
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
      <Alert tone="amber" title={t("create_subject_first_title")}>
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
            <option value="easy">{t("difficulty_easy")}</option>
            <option value="medium">{t("difficulty_medium")}</option>
            <option value="hard">{t("difficulty_hard")}</option>
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
            placeholder={t("placeholder_free_text")}
            maxLength={120}
          />
        </Field>
        <Field label="Tags" hint="Used for searching the bank and for blueprint rules.">
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-line bg-surface p-1.5">
            {tagList.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-[6px] bg-purple-50 px-2 py-0.5 text-[12px] font-medium text-purple-700"
              >
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  aria-label={`Remove tag ${tag}`}
                  className="text-purple-700/70 hover:text-purple-700"
                >
                  ×
                </button>
              </span>
            ))}
            <input
              list="question-tag-suggestions"
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") {
                  e.preventDefault();
                  addTag(tagInput);
                } else if (e.key === "Backspace" && !tagInput && tagList.length) {
                  removeTag(tagList[tagList.length - 1]);
                }
              }}
              onBlur={() => addTag(tagInput)}
              placeholder={tagList.length ? "" : t("placeholder_tags")}
              className="min-w-[100px] flex-1 border-0 bg-transparent px-1 py-0.5 text-[13px] outline-none"
            />
            <datalist id="question-tag-suggestions">
              {knownTags.filter((tag) => !tagList.includes(tag)).map((tag) => (
                <option key={tag} value={tag} />
              ))}
            </datalist>
          </div>
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

      {checkingDuplicate && (
        <p className="text-[12px] text-ink-muted">Checking the bank for a similar question…</p>
      )}
      {duplicateMatches.length > 0 && (
        <Alert tone="amber">
          This looks like a question already in the bank:{" "}
          <span className="font-medium">
            &ldquo;{duplicateMatches[0].body.slice(0, 120)}
            {duplicateMatches[0].body.length > 120 ? "…" : ""}&rdquo;
          </span>
          . Saving is still fine if this one is meant to be different.
        </Alert>
      )}

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
          onAdd={() => setOptions((c) => [...c, { text: "", is_correct: false, translations: {} }])}
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
              placeholder={t("placeholder_numeric")}
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
            <Input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder={t("placeholder_unit")} />
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
                placeholder={t("placeholder_input_format")}
              />
            </Field>
            <Field label="Output format" required>
              <Textarea
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                rows={2}
                placeholder={t("placeholder_output_format")}
              />
            </Field>
          </div>
          <Field label="Constraints" required>
            <Input
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              placeholder={t("placeholder_constraints")}
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
                    placeholder={index === 0 ? t("placeholder_sample_input") : `Input ${index + 1}`}
                  />
                  <Textarea
                    rows={2}
                    value={sample.output}
                    onChange={(e) =>
                      setSampleCases((c) =>
                        c.map((s, i) => (i === index ? { ...s, output: e.target.value } : s)),
                      )
                    }
                    placeholder={index === 0 ? t("placeholder_output") : `Output ${index + 1}`}
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
            placeholder={t("placeholder_passage")}
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
              placeholder={t("placeholder_upload_instructions")}
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
              placeholder={t("placeholder_model_answer")}
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
                  placeholder={t("placeholder_min_words")}
                />
              </Field>
              <Field label="Maximum words" hint="Enforced — a longer answer is refused.">
                <Input
                  type="number"
                  min="1"
                  step="10"
                  value={maxWords}
                  onChange={(e) => setMaxWords(e.target.value)}
                  placeholder={t("placeholder_max_words")}
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
          placeholder={t("placeholder_explanation")}
        />
      </Field>

      {/* -------------------------------------------------------------- translations */}
      <TranslationsPanel
        selectedLocales={selectedLocales}
        onToggleLocale={toggleLocale}
        qTranslations={qTranslations}
        onChangeQuestionField={(locale, field, value) =>
          setQTranslations((current) => ({
            ...current,
            [locale]: { ...current[locale], [field]: value },
          }))
        }
        options={options}
        onChangeOptionTranslation={setOptionTranslation}
        objective={objective}
        canGenerate={editing}
        generating={generating}
        onGenerate={() => void generateTranslations()}
        generateError={generateError}
        generateNotice={generateNotice}
      />

      {/* --------------------------------------------------------------- save block */}
      {problems.length > 0 && (
        <Alert tone="amber" title={t("alert_not_ready_to_save")}>
          <ul className="list-inside list-disc space-y-0.5">
            {problems.map((problem, index) => (
              <li key={index}>{problem}</li>
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
  const t = useTranslations("question");
  const letters = options.map((_, i) => String.fromCharCode(65 + i));
  const chosen = options
    .map((option, index) => (option.is_correct ? letters[index] : null))
    .filter(Boolean) as string[];

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-[13px] font-medium text-ink-soft">{t("label_options")}</p>
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
          <p className="text-[13px] font-semibold text-ink">{t("label_correct_answer")}</p>
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

/**
 * Which languages this question has (or will have) translated text for, and the
 * editable fields for each one chosen. English above is always the master; nothing
 * here is machine-generated without the examiner clicking "Generate Translations" and
 * reviewing the result first - see `generateTranslations` in the parent.
 */
function TranslationsPanel({
  selectedLocales,
  onToggleLocale,
  qTranslations,
  onChangeQuestionField,
  options,
  onChangeOptionTranslation,
  objective,
  canGenerate,
  generating,
  onGenerate,
  generateError,
  generateNotice,
}: {
  selectedLocales: Locale[];
  onToggleLocale: (locale: Locale) => void;
  qTranslations: Record<string, { body: string; explanation: string }>;
  onChangeQuestionField: (locale: Locale, field: "body" | "explanation", value: string) => void;
  options: DraftOption[];
  onChangeOptionTranslation: (index: number, locale: Locale, text: string) => void;
  objective: boolean;
  canGenerate: boolean;
  generating: boolean;
  onGenerate: () => void;
  generateError: string | null;
  generateNotice: string | null;
}) {
  const letters = options.map((_, i) => String.fromCharCode(65 + i));
  return (
    <div className="space-y-4 rounded-[12px] border border-line bg-sunken/40 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-ink">Available Translations</p>
          <p className="text-[12px] text-ink-muted">
            English above is the master version. Check a language to add or edit its text.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={generating}
          disabled={!canGenerate || generating}
          onClick={onGenerate}
          title={canGenerate ? undefined : "Save the question first, then generate translations."}
        >
          Generate Translations
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <label className="flex items-center gap-1.5 text-[13px] text-ink-soft opacity-60">
          <input type="checkbox" checked disabled className="h-4 w-4 rounded border-line-strong" />
          English
        </label>
        {TRANSLATABLE_LOCALES.map((locale) => (
          <label key={locale} className="flex items-center gap-1.5 text-[13px] text-ink-soft">
            <input
              type="checkbox"
              checked={selectedLocales.includes(locale)}
              onChange={() => onToggleLocale(locale)}
              className="h-4 w-4 rounded border-line-strong"
            />
            {LOCALE_NAMES[locale]}
          </label>
        ))}
      </div>

      {generateError && <Alert tone="rose">{generateError}</Alert>}
      {generateNotice && <Alert tone="amber">{generateNotice}</Alert>}

      {selectedLocales.map((locale) => (
        <div key={locale} className="space-y-3 rounded-[10px] border border-line bg-surface p-3">
          <p className="text-[12.5px] font-semibold text-ink">{LOCALE_NAMES[locale]}</p>
          <Field label="Question">
            <Textarea
              value={qTranslations[locale]?.body ?? ""}
              onChange={(e) => onChangeQuestionField(locale, "body", e.target.value)}
              rows={2}
              placeholder="Leave blank to fall back to English"
            />
          </Field>
          {objective && (
            <div className="space-y-1.5">
              <p className="text-[12px] font-medium text-ink-soft">Options</p>
              {options.map((option, index) => (
                <div key={index} className="flex items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] border border-line-strong bg-sunken text-[11px] font-semibold text-ink-soft">
                    {letters[index]}
                  </span>
                  <Input
                    value={option.translations[locale] ?? ""}
                    onChange={(e) => onChangeOptionTranslation(index, locale, e.target.value)}
                    placeholder={option.text || `Option ${letters[index]}`}
                  />
                </div>
              ))}
            </div>
          )}
          <Field label="Explanation">
            <Textarea
              value={qTranslations[locale]?.explanation ?? ""}
              onChange={(e) => onChangeQuestionField(locale, "explanation", e.target.value)}
              rows={2}
              placeholder="Leave blank to fall back to English"
            />
          </Field>
        </div>
      ))}
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
  const t = useTranslations("question");
  if (source === "ai_generated") return <Badge tone="purple">{t("badge_ai_generated")}</Badge>;
  if (source === "imported") return <Badge tone="amber">{t("badge_imported")}</Badge>;
  return null;
}
