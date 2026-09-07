"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Skeleton,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Result } from "@/lib/types";

export default function MyResultsPage() {
  const { user } = useRequireAuth(["candidate"]);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        setResults(await api.get<Result[]>("/my/results"));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not load your results.");
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="Your results"
        body="A result appears here only after an examiner has reviewed every written answer and published the paper."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-[150px] rounded-[14px]" />
          ))}
        </div>
      ) : results.length === 0 ? (
        <EmptyState
          title="No published results yet"
          body="Once your paper has been marked and released, it will show up here with question-level feedback."
          action={
            <Link href="/dashboard/candidate">
              <Button size="sm">Back to exams</Button>
            </Link>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {results.map((result) => {
            const tone =
              result.percentage >= 70 ? "mint" : result.percentage >= 40 ? "amber" : "rose";
            return (
              <Card key={result.id}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[12px] uppercase tracking-wide text-ink-muted">Score</p>
                    <p className="mt-1 text-[30px] font-semibold leading-none tracking-tight text-ink">
                      {result.obtained_marks}
                      <span className="text-[16px] font-medium text-ink-muted">
                        {" "}
                        / {result.total_marks}
                      </span>
                    </p>
                  </div>
                  <Badge tone={tone}>{result.percentage}%</Badge>
                </div>

                <div className="mt-4">
                  <ProgressBar value={result.percentage} tone={tone} />
                </div>

                <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                  {[
                    ["Correct", result.correct_count, "text-mint"],
                    ["Incorrect", result.incorrect_count, "text-rose"],
                    ["Blank", result.unanswered_count, "text-ink-muted"],
                  ].map(([label, value, tint]) => (
                    <div key={label as string} className="rounded-[9px] bg-sunken/60 py-2">
                      <dt className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</dt>
                      <dd className={`mt-0.5 text-[15px] font-semibold ${tint}`}>{value}</dd>
                    </div>
                  ))}
                </dl>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <p className="text-[12px] text-ink-muted">
                    Published {formatDate(result.published_at, false)}
                  </p>
                  <Link href={`/results/${result.id}`}>
                    <Button size="sm" variant="secondary">
                      Question feedback
                    </Button>
                  </Link>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
