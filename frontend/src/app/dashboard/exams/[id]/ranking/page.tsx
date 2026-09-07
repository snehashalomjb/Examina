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
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Exam, RankingRow, ShortlistStatus } from "@/lib/types";

const SHORTLIST_LABEL: Record<ShortlistStatus, string> = {
  shortlisted: "Shortlisted",
  rejected: "Rejected",
  on_hold: "On Hold",
};

const SHORTLIST_TONE: Record<ShortlistStatus, "mint" | "rose" | "amber"> = {
  shortlisted: "mint",
  rejected: "rose",
  on_hold: "amber",
};

export default function RankingPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const params = useParams<{ id: string }>();
  const examId = params.id;

  const [exam, setExam] = useState<Exam | null>(null);
  const [rows, setRows] = useState<RankingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !examId) return;
    let cancelled = false;
    (async () => {
      try {
        const [examData, rankingData] = await Promise.all([
          api.get<Exam>(`/exams/${examId}`),
          api.get<RankingRow[]>(`/exams/${examId}/ranking`),
        ]);
        if (!cancelled) {
          setExam(examData);
          setRows(rankingData);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load ranking.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, examId]);

  async function setShortlist(candidateId: string, status: ShortlistStatus) {
    setSaving(candidateId);
    try {
      await api.post(`/exams/${examId}/shortlist`, {
        decisions: [{ candidate_id: candidateId, status }],
      });
      setRows((prev) =>
        prev.map((r) => r.candidate_id === candidateId ? { ...r, shortlist_status: status } : r)
      );
      toast(`${status === "shortlisted" ? "Shortlisted" : status === "rejected" ? "Rejected" : "Placed on hold"}`, 
        status === "shortlisted" ? "mint" : status === "rejected" ? "rose" : "amber"
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not update shortlist", "rose");
    } finally {
      setSaving(null);
    }
  }

  if (!user) return null;

  const shortlisted = rows.filter((r) => r.shortlist_status === "shortlisted").length;
  const rejected = rows.filter((r) => r.shortlist_status === "rejected").length;
  const pending = rows.filter((r) => !r.shortlist_status).length;

  return (
    <div className="space-y-6">
      <Hero
        title={exam ? `Ranking — ${exam.title}` : "Candidate Ranking"}
        body={
          exam?.company_name
            ? `${exam.company_name}${exam.job_role ? ` · ${exam.job_role}` : ""} — Corporate Assessment`
            : "Corporate exam ranking with section-wise breakdown"
        }
        action={
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">← Back to Exams</Button>
          </Link>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {/* Summary stats */}
      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Total Appeared", value: rows.length, tone: "neutral" as const },
            { label: "Shortlisted", value: shortlisted, tone: "mint" as const },
            { label: "Rejected", value: rejected, tone: "rose" as const },
            { label: "Pending Decision", value: pending, tone: "amber" as const },
          ].map(({ label, value, tone }) => (
            <Card key={label} className="text-center">
              <p className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</p>
              <p className="mt-1 text-[22px] font-semibold text-ink">{value}</p>
            </Card>
          ))}
        </div>
      )}

      <Card padded={false}>
        <div className="p-5 border-b border-line">
          <SectionTitle
            title="Candidate Rankings"
            hint="Sorted by overall percentage. Click a row to expand section scores."
          />
        </div>

        {loading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-[10px]" />
            ))}
          </div>
        ) : rows.length === 0 ? (
          <div className="p-8">
            <EmptyState
              title="No completed sessions yet"
              body="Candidates need to submit the exam before ranking data appears here."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-line bg-sunken/40 text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3 text-left">Rank</th>
                  <th className="px-5 py-3 text-left">Candidate</th>
                  <th className="px-5 py-3 text-right">Score</th>
                  <th className="px-5 py-3 text-right">Accuracy</th>
                  <th className="px-5 py-3 text-right">Time</th>
                  <th className="px-5 py-3 text-center">Proctor</th>
                  <th className="px-5 py-3 text-center">Status</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((row) => (
                  <>
                    <tr
                      key={row.candidate_id}
                      className={cx(
                        "cursor-pointer transition hover:bg-sunken/40",
                        expandedRow === row.candidate_id && "bg-sunken/60"
                      )}
                      onClick={() =>
                        setExpandedRow((prev) =>
                          prev === row.candidate_id ? null : row.candidate_id
                        )
                      }
                    >
                      <td className="px-5 py-3">
                        <span className={cx(
                          "inline-flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-bold",
                          row.rank === 1 ? "bg-amber/20 text-amber" :
                          row.rank === 2 ? "bg-ink-muted/20 text-ink" :
                          row.rank === 3 ? "bg-orange-200/60 text-orange-700" :
                          "bg-sunken text-ink-soft"
                        )}>
                          {row.rank}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <p className="font-medium text-ink">{row.full_name}</p>
                        <p className="text-[12px] text-ink-muted">{row.email}</p>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <p className="font-semibold text-ink">
                          {row.obtained_marks.toFixed(1)}/{row.total_marks.toFixed(1)}
                        </p>
                        <p className="text-[12px] text-ink-muted">{row.overall_percentage.toFixed(1)}%</p>
                        <div className="mt-1 w-24 ml-auto">
                          <ProgressBar
                            value={row.overall_percentage}
                            tone={row.overall_percentage >= 70 ? "mint" : row.overall_percentage >= 50 ? "amber" : "rose"}
                          />
                        </div>
                      </td>
                      <td className="px-5 py-3 text-right text-ink-soft">
                        {row.accuracy.toFixed(1)}%
                      </td>
                      <td className="px-5 py-3 text-right text-ink-soft">
                        {row.time_taken_seconds != null
                          ? `${Math.floor(row.time_taken_seconds / 60)}m ${row.time_taken_seconds % 60}s`
                          : "—"}
                      </td>
                      <td className="px-5 py-3 text-center">
                        {row.is_flagged ? (
                          <Badge tone="rose">Flagged {row.suspicion_score.toFixed(0)}</Badge>
                        ) : (
                          <Badge tone="mint">Clear</Badge>
                        )}
                      </td>
                      <td className="px-5 py-3 text-center">
                        {row.shortlist_status ? (
                          <Badge tone={SHORTLIST_TONE[row.shortlist_status]}>
                            {SHORTLIST_LABEL[row.shortlist_status]}
                          </Badge>
                        ) : (
                          <span className="text-ink-muted">Pending</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={saving === row.candidate_id}
                            onClick={() => setShortlist(row.candidate_id, "shortlisted")}
                            className="!text-mint hover:!bg-mint/10"
                          >
                            ✓
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={saving === row.candidate_id}
                            onClick={() => setShortlist(row.candidate_id, "on_hold")}
                            className="!text-amber hover:!bg-amber/10"
                          >
                            ⏸
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            loading={saving === row.candidate_id}
                            onClick={() => setShortlist(row.candidate_id, "rejected")}
                            className="!text-rose hover:!bg-rose/10"
                          >
                            ✗
                          </Button>
                        </div>
                      </td>
                    </tr>

                    {/* Expanded section breakdown */}
                    {expandedRow === row.candidate_id && row.section_scores.length > 0 && (
                      <tr key={`${row.candidate_id}-expanded`} className="bg-sunken/30">
                        <td colSpan={8} className="px-8 py-4">
                          <p className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                            Section-wise Breakdown
                          </p>
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {row.section_scores.map((sec) => (
                              <div key={sec.section_name} className="rounded-[10px] border border-line bg-surface p-3">
                                <p className="text-[13px] font-medium text-ink truncate">{sec.section_name}</p>
                                <div className="mt-2 flex items-center justify-between gap-2">
                                  <span className="text-[12px] text-ink-muted">
                                    {sec.obtained_marks.toFixed(1)}/{sec.total_marks.toFixed(1)}
                                  </span>
                                  <span className="text-[12px] font-semibold text-ink">
                                    {sec.percentage.toFixed(1)}%
                                  </span>
                                </div>
                                <div className="mt-1.5">
                                  <ProgressBar
                                    value={sec.percentage}
                                    tone={sec.percentage >= 70 ? "mint" : sec.percentage >= 50 ? "amber" : "rose"}
                                  />
                                </div>
                                <div className="mt-2 flex gap-3 text-[11px] text-ink-muted">
                                  <span className="text-mint">✓ {sec.correct}</span>
                                  <span className="text-rose">✗ {sec.incorrect}</span>
                                  <span>– {sec.unanswered}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Legend */}
      {!loading && rows.length > 0 && (
        <Card>
          <p className="text-[12px] text-ink-muted">
            <strong>Actions:</strong> ✓ = Shortlist · ⏸ = On Hold · ✗ = Reject.
            Decisions are recorded with your identity and timestamp and can be updated at any time.
            The platform assists your decision — it does not shortlist automatically.
          </p>
        </Card>
      )}
    </div>
  );
}
