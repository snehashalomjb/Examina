"use client";

import { useTranslations } from "next-intl";

import { Badge, Modal, cx } from "@/components/ui";
import type {
  CodingSpec,
  Difficulty,
  FillBlankSpec,
  NumericalSpec,
  PassageSpec,
  Question,
} from "@/lib/types";
import { OPTION_BEARING_TYPES } from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

/**
 * The whole question, read-only, before it goes anywhere near an exam.
 *
 * Deliberately the examiner's view rather than the candidate's: the correct option is
 * marked and the spec is shown, because the point is checking the question is *right*
 * before adding it to a paper. The candidate-shaped view already exists separately as
 * the paper preview, which never carries an answer key.
 */
export function QuestionPreviewModal({
  question,
  onClose,
}: {
  question: Question | null;
  onClose: () => void;
}) {
  const t = useTranslations("questionBank");
  if (!question) return null;

  const spec = question.spec;
  const coding = question.question_type === "coding" ? (spec as CodingSpec | null) : null;
  const numerical = question.question_type === "numerical" ? (spec as NumericalSpec | null) : null;
  const fillBlank = question.question_type === "fill_blank" ? (spec as FillBlankSpec | null) : null;
  const passage = question.question_type === "passage" ? (spec as PassageSpec | null) : null;

  return (
    <Modal open onClose={onClose} title={t("preview_title")} size="lg">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="accent" size="xs">
            {t(`type_${question.question_type}`)}
          </Badge>
          <Badge tone={DIFFICULTY_TONE[question.difficulty]} size="xs">
            {t(`difficulty_${question.difficulty}`)}
          </Badge>
          <Badge tone="neutral" size="xs">{t(`category_${question.category}`)}</Badge>
          <Badge tone="neutral" size="xs">{t("marks_count", { count: question.marks })}</Badge>
          {question.negative_marks > 0 && (
            <Badge tone="rose" size="xs">−{question.negative_marks}</Badge>
          )}
          {question.status === "archived" && <Badge tone="neutral" size="xs">{t("badge_archived")}</Badge>}
          {question.status === "draft" && <Badge tone="amber" size="xs">{t("badge_draft")}</Badge>}
          {question.topic && <Badge tone="neutral" size="xs">{question.topic}</Badge>}
        </div>

        {question.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={question.image_url}
            alt=""
            className="max-h-64 rounded-[10px] border border-line object-contain"
          />
        )}

        <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-ink">{question.body}</p>

        {passage?.passage_text && (
          <div className="rounded-[10px] border border-line bg-sunken/60 p-3">
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-ink-muted">
              {t("type_passage")}
            </p>
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-soft">
              {passage.passage_text}
            </p>
            {passage.source && (
              <p className="mt-1.5 text-[11.5px] text-ink-muted">{t("preview_source", { source: passage.source })}</p>
            )}
          </div>
        )}

        {OPTION_BEARING_TYPES.includes(question.question_type) && question.options.length > 0 && (
          <ul className="space-y-1.5">
            {question.options.map((option, index) => (
              <li
                key={option.id}
                className={cx(
                  "flex items-start gap-2 rounded-[8px] px-3 py-2 text-[13px]",
                  option.is_correct
                    ? "bg-green-soft text-green-ink"
                    : "bg-sunken/60 text-ink-soft",
                )}
              >
                <span className="font-semibold">{String.fromCharCode(65 + index)}</span>
                <span className="flex-1">{option.text}</span>
                {option.is_correct && (
                  <span className="text-[11px] font-bold uppercase tracking-wide">{t("preview_correct")}</span>
                )}
              </li>
            ))}
          </ul>
        )}

        {numerical && (
          <PreviewBlock label={t("preview_answer_key")}>
            <p className="text-[13px] text-ink">
              {numerical.answer}
              {numerical.unit ? ` ${numerical.unit}` : ""}
              {numerical.tolerance ? ` (± ${numerical.tolerance})` : ""}
            </p>
          </PreviewBlock>
        )}

        {fillBlank && (
          <PreviewBlock label={t("accepted_answers")}>
            <div className="flex flex-wrap gap-1.5">
              {fillBlank.accepted_answers.map((answer) => (
                <Badge key={answer} tone="green" size="xs">{answer}</Badge>
              ))}
            </div>
          </PreviewBlock>
        )}

        {coding && (
          <PreviewBlock label={t("preview_coding_brief")}>
            <dl className="space-y-1.5 text-[12.5px] text-ink-soft">
              <SpecLine term={t("languages")} detail={coding.languages.join(", ")} />
              <SpecLine term={t("preview_input")} detail={coding.input_format} />
              <SpecLine term={t("preview_output")} detail={coding.output_format} />
              <SpecLine term={t("constraints")} detail={coding.constraints} />
            </dl>
            <ul className="mt-2 space-y-1.5">
              {coding.sample_cases.map((sample, index) => (
                <li key={index} className="rounded-[8px] bg-sunken/60 p-2 font-mono text-[12px]">
                  <p className="text-ink-soft">{t("preview_sample_in")} {sample.input}</p>
                  <p className="text-ink">{t("preview_sample_out")} {sample.output}</p>
                </li>
              ))}
            </ul>
          </PreviewBlock>
        )}

        {question.model_answer && (
          <PreviewBlock label={t("model_answer")}>
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-soft">
              {question.model_answer}
            </p>
          </PreviewBlock>
        )}

        {question.explanation && (
          <PreviewBlock label={t("explanation")}>
            <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-soft">
              {question.explanation}
            </p>
          </PreviewBlock>
        )}

        {question.tags && question.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {question.tags.map((tag) => (
              <Badge key={tag} tone="purple" size="xs">{tag}</Badge>
            ))}
          </div>
        )}

        {(question.min_words || question.max_words) && (
          <p className="text-[12px] text-ink-muted">
            {t("preview_word_bounds", {
              min: question.min_words ?? "—",
              max: question.max_words ?? "—",
            })}
          </p>
        )}
      </div>
    </Modal>
  );
}

function PreviewBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[10px] border border-line p-3">
      <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-muted">{label}</p>
      {children}
    </div>
  );
}

function SpecLine({ term, detail }: { term: string; detail: string }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 font-semibold text-ink">{term}:</dt>
      <dd className="whitespace-pre-wrap">{detail}</dd>
    </div>
  );
}
