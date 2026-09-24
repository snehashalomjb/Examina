"use client";

/**
 * What one candidate will actually sit.
 *
 * Two things are being demonstrated at once. The first is the paper: which questions
 * the rules drew, in which order, with options shuffled the way that candidate will
 * see them. The second is what is *not* there - no correct option, no model answer, no
 * marking scheme. The preview is fetched from the same candidate-shaped endpoint, so
 * if the key ever leaked into the candidate's paper it would show up here.
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Select,
  Skeleton,
  cx,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import {
  type CandidateRow,
  type Difficulty,
  type PaperPreviewResult,
} from "@/lib/types";

const DIFFICULTY_TONE: Record<Difficulty, "mint" | "amber" | "rose"> = {
  easy: "mint",
  medium: "amber",
  hard: "rose",
};

export interface PaperPreviewProps {
  examId: string | null;
  examTitle: string;
  durationMinutes: number;
  instructions?: string;
}

export function PaperPreview({
  examId,
  examTitle,
  durationMinutes,
  instructions,
}: PaperPreviewProps) {
  const t = useTranslations("examsOps");
  const [paper, setPaper] = useState<PaperPreviewResult | null>(null);
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [flagged, setFlagged] = useState<string[]>([]);

  const load = useCallback(
    async (forCandidate?: string) => {
      if (!examId) return;
      setLoading(true);
      setError(null);
      try {
        const data = await api.post<PaperPreviewResult>(
          `/exams/${examId}/preview-paper`,
          forCandidate ? { candidate_id: forCandidate } : {},
        );
        setPaper(data);
        setIndex(0);
        setAnswers({});
        setFlagged([]);
      } catch (err) {
        setError(
          err instanceof ApiError
            ? err.message
            : t("preview_error_build"),
        );
        setPaper(null);
      } finally {
        setLoading(false);
      }
    },
    [examId, t],
  );

  useEffect(() => {
    (async () => {
      try {
        setCandidates(await api.get<CandidateRow[]>("/admin/candidates?limit=50"));
      } catch {
        setCandidates([]); // preview falls back to the examiner's own seed
      }
    })();
  }, []);

  if (!examId) {
    return (
      <Alert tone="amber" title={t("preview_save_draft_first")}>
        {t("preview_generated_from_saved")}
      </Alert>
    );
  }

  const entry = paper?.entries[index];

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <Field
            label={t("preview_as")}
            hint={t("preview_as_hint")}
          >
            <Select
              value={candidateId}
              onChange={(e) => {
                setCandidateId(e.target.value);
                void load(e.target.value || undefined);
              }}
              className="min-w-[16rem]"
            >
              <option value="">{t("preview_yourself")}</option>
              {candidates.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.full_name} — {candidate.email}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              loading={loading}
              onClick={() => void load(candidateId || undefined)}
            >
              {paper ? t("preview_rebuild") : t("preview_generate")}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mt-3">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}

        {paper && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-muted">
            <Badge tone="accent">{t("questions_count", { count: paper.entries.length })}</Badge>
            <Badge tone="neutral">{t("marks_count", { count: paper.total_marks })}</Badge>
            <span className="font-mono">{t("preview_seed", { seed: paper.seed.slice(0, 12) })}</span>
            <span>{t("preview_determinism_note")}</span>
          </div>
        )}
      </Card>

      {loading && <Skeleton className="h-72 rounded-[12px]" />}

      {paper && entry && (
        <div className="overflow-hidden rounded-[14px] border-2 border-line-strong bg-sunken/40">
          {/* the candidate's chrome, reproduced so the examiner sees the real thing */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-4 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-[13.5px] font-semibold text-ink">
                {examTitle || t("preview_untitled_exam")}
              </p>
              <p className="text-[11.5px] text-ink-muted">
                {t("preview_question_of", { n: index + 1, total: paper.entries.length })}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone="neutral">⏱ {t("preview_remaining", { time: `${durationMinutes}:00` })}</Badge>
              <Badge tone="accent">{t("preview_ai_proctored")}</Badge>
            </div>
          </div>

          {instructions && index === 0 && (
            <div className="border-b border-line bg-accent-soft/30 px-4 py-2.5 text-[12.5px] text-ink-soft">
              <span className="font-semibold text-ink">{t("preview_instructions_label")} </span>
              {instructions}
            </div>
          )}

          <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_180px]">
            {/* the question */}
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-1.5">
                <Badge tone="neutral">{t(`qtype_${entry.question_type}`)}</Badge>
                <Badge tone={DIFFICULTY_TONE[entry.difficulty]}>{t(`difficulty_${entry.difficulty}`)}</Badge>
                <Badge tone="accent">{t("marks_count", { count: entry.marks })}</Badge>
                {entry.negative_marks > 0 && (
                  <Badge tone="rose">{t("preview_if_wrong", { marks: entry.negative_marks })}</Badge>
                )}
                {entry.topic && <Badge tone="neutral">{entry.topic}</Badge>}
              </div>

              <p className="text-[15px] leading-relaxed text-ink">{entry.body}</p>

              {entry.options.length > 0 ? (
                <ul className="mt-4 space-y-2">
                  {entry.options.map((option, position) => {
                    const chosen = answers[entry.question_id] === option.id;
                    return (
                      <li key={option.id}>
                        <button
                          type="button"
                          onClick={() =>
                            setAnswers((current) => ({
                              ...current,
                              [entry.question_id]: option.id,
                            }))
                          }
                          className={cx(
                            "flex w-full items-center gap-3 rounded-[10px] border px-3 py-2.5 text-left text-[13.5px] transition",
                            chosen
                              ? "border-accent bg-accent-soft/50 text-ink"
                              : "border-line bg-surface text-ink-soft hover:border-line-strong",
                          )}
                        >
                          <span
                            className={cx(
                              "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                              chosen
                                ? "border-accent bg-accent text-white"
                                : "border-line-strong text-ink-muted",
                            )}
                          >
                            {String.fromCharCode(65 + position)}
                          </span>
                          <span>{option.text}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <div className="mt-4 rounded-[10px] border border-dashed border-line-strong bg-surface p-4 text-[13px] text-ink-muted">
                  {entry.question_type === "image_upload"
                    ? t("preview_answer_area_upload")
                    : entry.question_type === "coding"
                      ? t("preview_answer_area_coding")
                      : t("preview_answer_area")}
                </div>
              )}

              <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={index === 0}
                  onClick={() => setIndex((i) => Math.max(0, i - 1))}
                >
                  {t("preview_previous")}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    setFlagged((current) =>
                      current.includes(entry.question_id)
                        ? current.filter((id) => id !== entry.question_id)
                        : [...current, entry.question_id],
                    )
                  }
                >
                  {flagged.includes(entry.question_id) ? t("preview_flagged") : t("preview_flag_for_review")}
                </Button>
                {index === paper.entries.length - 1 ? (
                  <Button size="sm" disabled title={t("preview_submit_disabled")}>
                    {t("preview_submit_exam")}
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => setIndex((i) => i + 1)}>
                    {t("preview_next")}
                  </Button>
                )}
              </div>
            </div>

            {/* the navigator */}
            <div className="rounded-[10px] border border-line bg-surface p-3">
              <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-ink-muted">
                {t("preview_navigator")}
              </p>
              <div className="grid grid-cols-5 gap-1.5">
                {paper.entries.map((item, position) => {
                  const answered = Boolean(answers[item.question_id]);
                  const isFlagged = flagged.includes(item.question_id);
                  return (
                    <button
                      key={item.question_id}
                      type="button"
                      onClick={() => setIndex(position)}
                      className={cx(
                        "flex h-7 items-center justify-center rounded-[6px] border text-[11px] font-semibold transition",
                        position === index
                          ? "border-accent bg-accent text-white"
                          : isFlagged
                            ? "border-amber bg-amber-soft text-amber-ink"
                            : answered
                              ? "border-mint bg-mint-soft text-mint"
                              : "border-line bg-sunken text-ink-muted",
                      )}
                    >
                      {position + 1}
                    </button>
                  );
                })}
              </div>
              <ul className="mt-3 space-y-1 text-[11px] text-ink-muted">
                <li>■ {t("preview_legend_answered")}</li>
                <li>■ {t("preview_legend_flagged")}</li>
                <li>■ {t("preview_legend_not_visited")}</li>
              </ul>
            </div>
          </div>

          <p className="border-t border-line bg-surface px-4 py-2 text-[11.5px] text-ink-muted">
            {t("preview_candidate_view_note")}
          </p>
        </div>
      )}

      {!paper && !loading && !error && (
        <Card className="text-center">
          <p className="text-[13px] text-ink-muted">
            {t("preview_generate_prompt")}
          </p>
        </Card>
      )}
    </div>
  );
}
