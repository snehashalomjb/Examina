"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

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
import type { CandidateStats, Result } from "@/lib/types";

/**
 * Performance — what the published results say, read back to the candidate.
 *
 * Everything here is derived from results the examiner has already released; nothing is
 * inferred from papers still under review, because a provisional machine score is not a
 * grade and should not shape a candidate's sense of how they are doing.
 */
export default function PerformancePage() {
  const { user } = useRequireAuth(["candidate"]);
  const [results, setResults] = useState<Result[]>([]);
  const [stats, setStats] = useState<CandidateStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user) return;
      try {
        const [resultData, statsData] = await Promise.all([
          api.get<Result[]>("/my/results"),
          api.get<CandidateStats>("/my/stats/summary"),
        ]);
        if (cancelled) return;
        setResults(resultData);
        setStats(statsData);
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
        title="Performance"
        body="How your released results look together — accuracy, completion, and whether your scores are moving."
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
              label="Average"
              value={stats.average_percentage !== null ? `${stats.average_percentage}%` : "—"}
              hint="Across published results"
              tone="accent"
            />
            <Stat
              label="Best"
              value={stats.best_percentage !== null ? `${stats.best_percentage}%` : "—"}
              hint="Your strongest paper"
              tone="mint"
            />
            <Stat
              label="Accuracy"
              value={analysis ? `${Math.round(analysis.accuracy)}%` : "—"}
              hint="Correct out of attempted"
            />
            <Stat
              label="Completion"
              value={analysis ? `${Math.round(analysis.answeredShare)}%` : "—"}
              hint="Questions you attempted"
              tone={analysis && analysis.answeredShare < 90 ? "amber" : "neutral"}
            />
          </>
        )}
      </div>

      {loading ? (
        <Skeleton className="h-[260px] rounded-[14px]" />
      ) : !analysis ? (
        <EmptyState
          title="No published results yet"
          body="Once an examiner releases a paper you have sat, your performance appears here."
          action={
            <Link href="/dashboard/candidate/exams">
              <Button size="sm">See my exams</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <Card>
            <SectionTitle
              title="Score history"
              hint="Oldest to newest, by the date each result was published."
            />
            <ScoreChart results={analysis.ordered} />
          </Card>

          <div className="space-y-5">
            <Card>
              <SectionTitle title="Answer breakdown" hint="Every published paper combined." />
              <div className="space-y-3">
                {(
                  [
                    { label: "Correct", value: analysis.totals.correct, tone: "mint" },
                    { label: "Incorrect", value: analysis.totals.incorrect, tone: "rose" },
                    { label: "Left blank", value: analysis.totals.blank, tone: "neutral" },
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
              <SectionTitle title="Reading" hint="What the numbers suggest." />
              <ul className="space-y-2.5">
                {buildInsights(analysis).map((insight) => (
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
                Based on {results.length} published result{results.length === 1 ? "" : "s"}.
                Papers still awaiting examiner review are not counted.
              </p>
            </Card>
          </div>
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

function buildInsights(analysis: Analysis): { text: string; tone: "mint" | "amber" | "accent" }[] {
  const out: { text: string; tone: "mint" | "amber" | "accent" }[] = [];

  if (analysis.trend === "up") {
    out.push({ text: "Your recent papers score higher than your earlier ones.", tone: "mint" });
  } else if (analysis.trend === "down") {
    out.push({
      text: "Your recent papers score lower than your earlier ones — worth reviewing what changed.",
      tone: "amber",
    });
  } else if (analysis.trend === "flat") {
    out.push({ text: "Your scores are holding steady across papers.", tone: "accent" });
  }

  if (analysis.answeredShare < 90) {
    out.push({
      text: `You left ${analysis.totals.blank} question(s) blank. Blank answers score zero but never cost a negative mark — a considered guess is usually better than nothing.`,
      tone: "amber",
    });
  } else {
    out.push({ text: "You attempt nearly everything put in front of you.", tone: "mint" });
  }

  if (analysis.accuracy >= 75) {
    out.push({ text: "When you answer, you are usually right — accuracy is strong.", tone: "mint" });
  } else if (analysis.accuracy < 50) {
    out.push({
      text: "Under half of your attempted answers are correct. Accuracy, not coverage, is the thing to work on.",
      tone: "amber",
    });
  }

  return out;
}

/** Compact inline chart. Deliberately hand-drawn SVG rather than a charting dependency. */
function ScoreChart({ results }: { results: Result[] }) {
  if (results.length === 1) {
    const only = results[0];
    return (
      <div className="rounded-[11px] border border-line bg-sunken/40 p-6 text-center">
        <p className="text-[30px] font-semibold tracking-tight text-ink">{only.percentage}%</p>
        <p className="mt-1 text-[12.5px] text-ink-muted">
          One published result — a trend needs at least two.
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
                Detail
              </Button>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
