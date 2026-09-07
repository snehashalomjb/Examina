"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

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
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Exam, ExamAnalytics } from "@/lib/types";

export default function AnalyticsPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const params = useParams<{ id: string }>();
  const examId = params.id;

  const [exam, setExam] = useState<Exam | null>(null);
  const [analytics, setAnalytics] = useState<ExamAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !examId) return;
    let cancelled = false;
    (async () => {
      try {
        const [examData, analyticsData] = await Promise.all([
          api.get<Exam>(`/exams/${examId}`),
          api.get<ExamAnalytics>(`/exams/${examId}/analytics`),
        ]);
        if (!cancelled) {
          setExam(examData);
          setAnalytics(analyticsData);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load analytics.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, examId]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title={exam ? `Analytics — ${exam.title}` : "Exam Analytics"}
        body={`${exam?.exam_type === "corporate" ? "Corporate" : "Academic"} exam performance statistics`}
        action={
          <div className="flex gap-2">
            <Link href="/dashboard/exams">
              <Button variant="secondary" size="sm">← Back to Exams</Button>
            </Link>
            {exam?.exam_type === "corporate" && (
              <Link href={`/dashboard/exams/${examId}/ranking`}>
                <Button size="sm">View Ranking</Button>
              </Link>
            )}
          </div>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {loading ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[104px] rounded-[14px]" />
            ))}
          </div>
          <Skeleton className="h-[300px] rounded-[14px]" />
        </div>
      ) : !analytics ? null : (
        <>
          {/* Key Metrics */}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              {
                label: "Total Sessions",
                value: analytics.total_sessions,
                hint: `${analytics.completed_sessions} completed`,
                tone: "neutral" as const,
              },
              {
                label: "Average Score",
                value: `${analytics.avg_percentage.toFixed(1)}%`,
                hint: `Highest: ${analytics.highest_percentage.toFixed(1)}%`,
                tone: analytics.avg_percentage >= 70 ? "mint" as const : analytics.avg_percentage >= 50 ? "amber" as const : "rose" as const,
              },
              {
                label: "Pass Rate",
                value: `${analytics.pass_rate.toFixed(1)}%`,
                hint: `Passing threshold: ${exam?.passing_percentage ?? 50}%`,
                tone: analytics.pass_rate >= 70 ? "mint" as const : "amber" as const,
              },
              {
                label: "Score Range",
                value: `${analytics.lowest_percentage.toFixed(1)}–${analytics.highest_percentage.toFixed(1)}%`,
                hint: "Min to max across all sittings",
                tone: "accent" as const,
              },
            ].map(({ label, value, hint, tone }) => {
              const toneClasses = {
                neutral: "bg-line-strong",
                accent: "bg-accent",
                mint: "bg-mint",
                amber: "bg-amber",
                rose: "bg-rose",
              };
              return (
                <Card key={label} className="relative overflow-hidden">
                  <span className={`absolute inset-x-0 top-0 h-0.5 ${toneClasses[tone]}`} />
                  <p className="text-[12px] font-medium uppercase tracking-wide text-ink-muted">{label}</p>
                  <p className="mt-2 text-[26px] font-semibold leading-none tracking-tight text-ink">{value}</p>
                  {hint && <p className="mt-2 text-[12px] text-ink-muted">{hint}</p>}
                </Card>
              );
            })}
          </div>

          {/* Score Distribution */}
          {analytics.score_distribution.length > 0 && (
            <Card>
              <SectionTitle
                title="Score Distribution"
                hint={`${analytics.score_distribution.length} completed sessions`}
              />
              <ScoreHistogram scores={analytics.score_distribution} />
            </Card>
          )}

          <div className="grid gap-5 lg:grid-cols-2">
            {/* Section Analytics (corporate) */}
            {analytics.section_analytics.length > 0 && (
              <Card>
                <SectionTitle
                  title="Section-wise Performance"
                  hint="Average scores per section across all candidates"
                />
                <ul className="space-y-4">
                  {analytics.section_analytics.map((sec) => (
                    <li key={sec.section_name}>
                      <div className="mb-1.5 flex items-baseline justify-between gap-2">
                        <p className="truncate text-[13.5px] font-medium text-ink">{sec.section_name}</p>
                        <span className="shrink-0 text-[12px] text-ink-muted">
                          {sec.avg_percentage.toFixed(1)}% avg · {sec.pass_rate.toFixed(1)}% pass rate
                        </span>
                      </div>
                      <ProgressBar
                        value={sec.avg_percentage}
                        tone={sec.avg_percentage >= 70 ? "mint" : sec.avg_percentage >= 50 ? "amber" : "rose"}
                      />
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {/* Topic Performance */}
            {analytics.topic_performance.length > 0 && (
              <Card>
                <SectionTitle
                  title="Topic Performance"
                  hint="Average scores by question topic"
                />
                <ul className="space-y-3">
                  {analytics.topic_performance.slice(0, 10).map((topic) => (
                    <li key={topic.topic} className="flex items-center gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="mb-1 flex items-baseline justify-between gap-2">
                          <p className="truncate text-[13px] text-ink">{topic.topic}</p>
                          <span className="shrink-0 text-[12px] text-ink-muted">
                            {topic.avg_score_pct.toFixed(1)}%
                          </span>
                        </div>
                        <ProgressBar
                          value={topic.avg_score_pct}
                          tone={topic.avg_score_pct >= 70 ? "mint" : topic.avg_score_pct >= 50 ? "amber" : "rose"}
                        />
                      </div>
                      <Badge>
                        {topic.total_questions}q
                      </Badge>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>

          {analytics.completed_sessions === 0 && (
            <EmptyState
              title="No completed sessions yet"
              body="Analytics will appear once candidates submit the exam."
            />
          )}
        </>
      )}
    </div>
  );
}

/** Bucket score_distribution into 10% bins and render as a bar chart. */
function ScoreHistogram({ scores }: { scores: number[] }) {
  const bins = Array.from({ length: 10 }, (_, i) => {
    const low = i * 10;
    const high = low + 10;
    return {
      label: `${low}–${high}%`,
      count: scores.filter((s) => s >= low && (i === 9 ? s <= high : s < high)).length,
    };
  });
  const maxCount = Math.max(...bins.map((b) => b.count), 1);

  return (
    <div className="flex items-end gap-1.5 h-36">
      {bins.map((bin) => (
        <div key={bin.label} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-[10px] text-ink-muted">{bin.count > 0 ? bin.count : ""}</span>
          <div className="w-full rounded-t-[4px] bg-accent/70 transition-all duration-500"
            style={{ height: `${(bin.count / maxCount) * 100}%`, minHeight: bin.count ? 4 : 0 }}
          />
          <span className="text-[9px] text-ink-muted rotate-[-30deg] origin-top-right translate-y-2 whitespace-nowrap">
            {bin.label.split("–")[0]}
          </span>
        </div>
      ))}
    </div>
  );
}
