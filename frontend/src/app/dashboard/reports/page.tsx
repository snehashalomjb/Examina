"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Skeleton,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ExamReportSummary } from "@/lib/types";

export default function ExamReportsPage() {
  const t = useTranslations("results");
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [summaries, setSummaries] = useState<ExamReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.get<ExamReportSummary[]>("/reports/exams");
        if (!cancelled) setSummaries(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load exam reports.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user]);

  async function downloadFullReport(summary: ExamReportSummary) {
    setDownloading(summary.exam_id);
    try {
      const safeName = summary.exam_title.replace(/\s+/g, "_");
      await api.download(`/reports/exams/${summary.exam_id}/pdf`, `marklist_${safeName}.pdf`);
    } catch (err) {
      toast(
        err instanceof ApiError ? err.message : "Could not download the exam report",
        "rose",
      );
    } finally {
      setDownloading(null);
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title={t("reportsPageTitle")}
        body="Approval status and official downloads for every exam you can see - only examiner-reviewed, published results count as approved."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-[220px] rounded-[14px]" />
          ))}
        </div>
      ) : summaries.length === 0 ? (
        <EmptyState
          title="No exam reports yet"
          body="Once candidates start sitting your exams, their results and approval status will show up here."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {summaries.map((summary) => (
            <Card key={summary.exam_id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[15px] font-semibold text-ink">{summary.exam_title}</p>
                  <p className="text-[12px] text-ink-muted">
                    {summary.subject_name ?? "—"} · {formatDate(summary.exam_date, false)}
                  </p>
                </div>
                <Badge tone="neutral">{summary.total_candidates} candidates</Badge>
              </div>

              <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
                {[
                  ["Completed", summary.completed, "text-ink"],
                  ["Pending Review", summary.pending_review, "text-amber"],
                  ["Approved", summary.approved, "text-mint"],
                  ["Flagged", summary.flagged, "text-rose"],
                  ["Rejected", summary.rejected, "text-rose"],
                  [
                    "Avg Marks",
                    summary.average_marks != null ? summary.average_marks.toFixed(1) : "—",
                    "text-ink",
                  ],
                ].map(([label, value, tint]) => (
                  <div key={label as string} className="rounded-[9px] bg-sunken/60 py-2">
                    <dt className="text-[10px] uppercase tracking-wide text-ink-muted">{label}</dt>
                    <dd className={`mt-0.5 text-[14px] font-semibold ${tint}`}>{value}</dd>
                  </div>
                ))}
              </dl>

              {(summary.highest_marks != null || summary.lowest_marks != null) && (
                <p className="mt-3 text-[12px] text-ink-muted">
                  Highest {summary.highest_marks ?? "—"} · Lowest {summary.lowest_marks ?? "—"}
                  {" "}(approved results only)
                </p>
              )}

              <div className="mt-4 flex items-center justify-end gap-2">
                <Link href={`/dashboard/exams/${summary.exam_id}/ranking`}>
                  <Button size="sm" variant="secondary">View Results</Button>
                </Link>
                <Button
                  size="sm"
                  loading={downloading === summary.exam_id}
                  disabled={summary.approved === 0}
                  onClick={() => downloadFullReport(summary)}
                >
                  Download Full Report PDF
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
