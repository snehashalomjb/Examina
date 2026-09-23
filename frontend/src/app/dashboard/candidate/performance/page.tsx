"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  SectionTitle,
  Skeleton,
  Stat,
  cx,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateStats, PerformanceAnalysis, Result } from "@/lib/types";

/**
 * Performance — what the published results say, read back to the candidate.
 *
 * Everything here is derived from results the examiner has already released; nothing is
 * inferred from papers still under review, because a provisional machine score is not a
 * grade and should not shape a candidate's sense of how they are doing.
 */
export default function PerformancePage() {
  const { user } = useRequireAuth(["candidate"]);
  const t = useTranslations("results");
  const [results, setResults] = useState<Result[]>([]);
  const [stats, setStats] = useState<CandidateStats | null>(null);
  /**
   * Topic-level analysis, computed server-side.
   *
   * The client cannot work this out: topics live on the questions, and a published
   * result only carries totals. It is built from released marks only, so nothing here
   * hints at a paper the examiner has not published yet.
   */
  const [topics, setTopics] = useState<PerformanceAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user) return;
      try {
        const [resultData, statsData, topicData] = await Promise.all([
          api.get<Result[]>("/my/results"),
          api.get<CandidateStats>("/my/stats/summary"),
          api.get<PerformanceAnalysis>("/my/performance-analysis"),
        ]);
        if (cancelled) return;
        setResults(resultData);
        setStats(statsData);
        setTopics(topicData);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load your performance.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const analysis = useMemo(() => {
    if (results.length === 0) return null;

    const ordered = [...results].sort(
      (a, b) =>
        new Date(a.published_at ?? 0).getTime() - new Date(b.published_at ?? 0).getTime(),
    );
    const percentages = ordered.map((r) => r.percentage);
    const totals = ordered.reduce(
      (acc, r) => ({
        correct: acc.correct + r.correct_count,
        incorrect: acc.incorrect + r.incorrect_count,
        blank: acc.blank + r.unanswered_count,
      }),
      { correct: 0, incorrect: 0, blank: 0 },
    );
    const attempted = totals.correct + totals.incorrect;
    const answeredShare =
      attempted + totals.blank > 0 ? (attempted / (attempted + totals.blank)) * 100 : 0;
    const accuracy = attempted > 0 ? (totals.correct / attempted) * 100 : 0;

    // Trend across the most recent half against the earlier half - blunt, but honest
    // about being blunt, and it needs at least two results to say anything at all.
    let trend: "up" | "down" | "flat" | null = null;
    if (percentages.length >= 2) {
      const half = Math.floor(percentages.length / 2) || 1;
      const early = percentages.slice(0, half);
      const late = percentages.slice(-half);
      const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
      const delta = mean(late) - mean(early);
      trend = Math.abs(delta) < 3 ? "flat" : delta > 0 ? "up" : "down";
    }

    return { ordered, totals, accuracy, answeredShare, trend };
  }, [results]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title={t("performance_title")}
        body={t("performance_body")}
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[104px] rounded-[14px]" />
          ))
        ) : (
          <>
            <Stat
              label={t("average")}
              value={stats.average_percentage !== null ? `${stats.average_percentage}%` : "—"}
              hint={t("across_published_results")}
              tone="accent"
            />
            <Stat
              label={t("best")}
              value={stats.best_percentage !== null ? `${stats.best_percentage}%` : "—"}
              hint={t("your_strongest_paper")}
              tone="mint"
            />
            <Stat
              label={t("accuracy")}
              value={analysis ? `${Math.round(analysis.accuracy)}%` : "—"}
              hint={t("correct_out_of_attempted")}
            />
            <Stat
              label={t("completion")}
              value={analysis ? `${Math.round(analysis.answeredShare)}%` : "—"}
              hint={t("questions_you_attempted")}
              tone={analysis && analysis.answeredShare < 90 ? "amber" : "neutral"}
            />
          </>
        )}
      </div>

      {loading ? (
        <Skeleton className="h-[260px] rounded-[14px]" />
      ) : !analysis ? (
        <EmptyState
          title={t("no_published_results_performance")}
          body={t("no_results_performance_body")}
          action={
            <Link href="/dashboard/candidate/exams">
              <Button size="sm">{t("see_my_exams")}</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <SectionTitle
              title={t("score_history")}
              hint={t("score_history_hint")}
            />
            <ScoreChart results={analysis.ordered} t={t} />
          </Card>

          <div className="space-y-5">
            <Card>
              <SectionTitle title={t("answer_breakdown")} hint={t("answer_breakdown_hint")} />
              <div className="space-y-3">
                {(
                  [
                    { label: t("correct"), value: analysis.totals.correct, tone: "mint" },
                    { label: t("incorrect"), value: analysis.totals.incorrect, tone: "rose" },
                    { label: t("left_blank"), value: analysis.totals.blank, tone: "neutral" },
                  ] as const
                ).map(({ label, value, tone }) => {
                  const total =
                    analysis.totals.correct + analysis.totals.incorrect + analysis.totals.blank;
                  const share = total ? (value / total) * 100 : 0;
                  return (
                    <div key={label}>
                      <div className="mb-1 flex justify-between text-[12.5px]">
                        <span className="text-ink-soft">{label}</span>
                        <span className="font-medium text-ink">{value}</span>
                      </div>
                      <ProgressBar value={share} tone={tone} />
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card>
              <SectionTitle title={t("reading")} hint={t("reading_hint")} />
              <ul className="space-y-2.5">
                {buildInsights(analysis, t).map((insight) => (
                  <li key={insight.text} className="flex gap-2.5">
                    <span
                      className={cx(
                        "mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45",
                        insight.tone === "mint"
                          ? "bg-mint"
                          : insight.tone === "amber"
                            ? "bg-amber"
                            : "bg-accent",
                      )}
                    />
                    <p className="text-[13px] leading-relaxed text-ink-soft">{insight.text}</p>
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-[11.5px] leading-relaxed text-ink-muted">
                {t("based_on_results", { count: results.length, plural: results.length === 1 ? "" : "s" })}
              </p>
            </Card>
          </div>

          {/* ---------------------------------------------------- by topic */}
          {topics && topics.topic_scores.length > 0 && (
            <Card>
              <SectionTitle
                title={t("by_topic")}
                hint={t("by_topic_hint")}
              />
              <ul className="space-y-3">
                {topics.topic_scores.map((score) => (
                  <li key={score.topic}>
                    <div className="mb-1 flex items-baseline justify-between gap-3">
                      <span className="truncate text-[13px] font-medium text-ink">
                        {score.topic}
                      </span>
                      <span className="shrink-0 text-[12.5px] text-ink-soft">
                        {Math.round(score.percentage)}%
                        <span className="ml-1.5 text-[11.5px] text-ink-muted">
                          over {score.answers} answer{score.answers === 1 ? "" : "s"}
                        </span>
                      </span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-sunken">
                      <div
                        className={cx(
                          "h-full rounded-full",
                          score.percentage >= 70
                            ? "bg-mint"
                            : score.percentage >= 50
                              ? "bg-amber"
                              : "bg-rose",
                        )}
                        style={{ width: `${Math.min(Math.max(score.percentage, 0), 100)}%` }}
                      />
                    </div>
                  </li>
                ))}
              </ul>

              {topics.recommendations.length > 0 && (
                <div className="mt-5 rounded-[10px] border border-line bg-sunken/50 p-3.5">
                  <p className="mb-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-ink-muted">
                    {t("where_to_put_your_time")}
                  </p>
                  <ul className="space-y-1">
                    {topics.recommendations.map((line) => (
                      <li key={line} className="text-[13px] text-ink-soft">
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="mt-3 text-[11.5px] leading-relaxed text-ink-muted">
                {t("topic_pattern_note")}
              </p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

interface Analysis {
  ordered: Result[];
  totals: { correct: number; incorrect: number; blank: number };
  accuracy: number;
  answeredShare: number;
  trend: "up" | "down" | "flat" | null;
}

function buildInsights(analysis: Analysis, t: ReturnType<typeof useTranslations>): { text: string; tone: "mint" | "amber" | "accent" }[] {
  const out: { text: string; tone: "mint" | "amber" | "accent" }[] = [];

  if (analysis.trend === "up") {
    out.push({ text: t("recent_papers_higher"), tone: "mint" });
  } else if (analysis.trend === "down") {
    out.push({
      text: t("recent_papers_lower"),
      tone: "amber",
    });
  } else if (analysis.trend === "flat") {
    out.push({ text: t("scores_holding_steady"), tone: "accent" });
  }

  if (analysis.answeredShare < 90) {
    out.push({
      text: t("left_blank_warning", { count: analysis.totals.blank }),
      tone: "amber",
    });
  } else {
    out.push({ text: t("attempt_nearly_everything"), tone: "mint" });
  }

  if (analysis.accuracy >= 75) {
    out.push({ text: t("accuracy_strong"), tone: "mint" });
  } else if (analysis.accuracy < 50) {
    out.push({
      text: t("accuracy_weak"),
      tone: "amber",
    });
  }

  return out;
}

/** Compact inline chart. Deliberately hand-drawn SVG rather than a charting dependency. */
function ScoreChart({ results, t }: { results: Result[]; t: ReturnType<typeof useTranslations> }) {
  if (results.length === 1) {
    const only = results[0];
    return (
      <div className="rounded-[11px] border border-line bg-sunken/40 p-6 text-center">
        <p className="text-[30px] font-semibold tracking-tight text-ink">{only.percentage}%</p>
        <p className="mt-1 text-[12.5px] text-ink-muted">
          {t("one_result_note")}
        </p>
      </div>
    );
  }

  const width = 100;
  const height = 44;
  const points = results.map((result, index) => ({
    x: (index / (results.length - 1)) * width,
    y: height - (result.percentage / 100) * height,
    result,
  }));
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${path} L${width},${height} L0,${height} Z`;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full" preserveAspectRatio="none">
        {[0, 0.5, 1].map((fraction) => (
          <line
            key={fraction}
            x1={0}
            x2={width}
            y1={height * fraction}
            y2={height * fraction}
            stroke="var(--color-line)"
            strokeWidth={0.4}
          />
        ))}
        <path d={area} fill="var(--color-accent)" fillOpacity={0.08} />
        <path d={path} fill="none" stroke="var(--color-accent)" strokeWidth={1.2} />
        {points.map((p) => (
          <circle key={p.result.id} cx={p.x} cy={p.y} r={1.4} fill="var(--color-accent)" />
        ))}
      </svg>

      <ul className="mt-4 divide-y divide-line">
        {[...results].reverse().map((result) => (
          <li key={result.id} className="flex items-center gap-3 py-2">
            <span className="flex-1 text-[12.5px] text-ink-muted">
              {formatDate(result.published_at, false)}
            </span>
            <span className="text-[12.5px] text-ink-soft">
              {result.obtained_marks}/{result.total_marks}
            </span>
            <Badge
              tone={
                result.percentage >= 70 ? "mint" : result.percentage >= 40 ? "amber" : "rose"
              }
            >
              {result.percentage}%
            </Badge>
            <Link href={`/results/${result.id}`}>
              <Button size="sm" variant="ghost">
                {t("detail_button")}
              </Button>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
