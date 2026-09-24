"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
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
  cx,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Exam, RankingRow, ShortlistStatus } from "@/lib/types";

/** Mirrors the server's publish gate (grading.py): finished, ungraded work cleared,
 * proctoring ruled on if flagged, not already published. */
function canPublish(row: RankingRow): boolean {
  return (
    Boolean(row.session_id) &&
    !row.published &&
    row.pending_review_count === 0 &&
    !row.needs_integrity_review &&
    row.integrity_verdict !== "malpractice"
  );
}

const SHORTLIST_TONE: Record<ShortlistStatus, "mint" | "rose" | "amber"> = {
  shortlisted: "mint",
  rejected: "rose",
  on_hold: "amber",
};

export default function RankingPage() {
  const t = useTranslations("results");
  const tx = useTranslations("examsOps");
  const { user } = useRequireAuth(["examiner", "admin"]);
  const params = useParams<{ id: string }>();
  const examId = params.id;

  const [exam, setExam] = useState<Exam | null>(null);
  const [rows, setRows] = useState<RankingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

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
        if (!cancelled) setError(err instanceof ApiError ? err.message : tx("ranking_error_load"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, examId, tx]);

  async function setShortlist(candidateId: string, status: ShortlistStatus) {
    setSaving(candidateId);
    try {
      await api.post(`/exams/${examId}/shortlist`, {
        decisions: [{ candidate_id: candidateId, status }],
      });
      setRows((prev) =>
        prev.map((r) => r.candidate_id === candidateId ? { ...r, shortlist_status: status } : r)
      );
      toast(status === "shortlisted" ? tx("shortlist_shortlisted") : status === "rejected" ? tx("shortlist_rejected") : tx("ranking_placed_on_hold"),
        status === "shortlisted" ? "mint" : status === "rejected" ? "rose" : "amber"
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : tx("ranking_error_shortlist"), "rose");
    } finally {
      setSaving(null);
    }
  }

  async function publishOne(row: RankingRow) {
    if (!row.session_id) return;
    setPublishing(row.session_id);
    try {
      const response = await api.post<{ detail: string }>(
        `/sessions/${row.session_id}/result/publish`,
      );
      toast(response.detail, "mint");
      setRows((prev) =>
        prev.map((r) => (r.session_id === row.session_id ? { ...r, published: true } : r)),
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : tx("ranking_error_publish"), "rose");
    } finally {
      setPublishing(null);
    }
  }

  async function downloadReport(row: RankingRow) {
    if (!row.result_id) return;
    setDownloading(row.result_id);
    try {
      const safeName = row.full_name.replace(/\s+/g, "_");
      await api.download(
        `/results/${row.result_id}/pdf?simple=true`,
        `report_${safeName}.pdf`,
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : tx("ranking_error_download"), "rose");
    } finally {
      setDownloading(null);
    }
  }

  if (!user) return null;

  const topPerformer = rows.length > 0 ? rows[0] : null;

  // Shortlisting is a hiring decision - meaningful for a corporate assessment, not for
  // an academic paper. The scores, attempt counts and proctoring flags below are the
  // same table for both; only the decide-and-shortlist column is corporate-only.
  const isCorporate = exam?.exam_type === "corporate";

  const shortlisted = rows.filter((r) => r.shortlist_status === "shortlisted").length;
  const rejected = rows.filter((r) => r.shortlist_status === "rejected").length;
  const pending = rows.filter((r) => !r.shortlist_status).length;

  return (
    <div className="space-y-6">
      <Hero
        title={exam ? tx("ranking_title_exam", { title: exam.title }) : tx("ranking_title")}
        body={
          exam?.company_name
            ? tx("ranking_body_corporate", { company: exam.job_role ? `${exam.company_name} · ${exam.job_role}` : exam.company_name })
            : tx("ranking_body")
        }
        action={
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">{tx("back_to_exams")}</Button>
          </Link>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {/* Summary stats */}
      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(isCorporate
            ? [
                { label: tx("ranking_total_appeared"), value: rows.length, tone: "neutral" as const },
                { label: tx("shortlist_shortlisted"), value: shortlisted, tone: "mint" as const },
                { label: tx("shortlist_rejected"), value: rejected, tone: "rose" as const },
                { label: tx("ranking_pending_decision"), value: pending, tone: "amber" as const },
              ]
            : [
                { label: tx("ranking_total_appeared"), value: rows.length, tone: "neutral" as const },
                {
                  label: tx("ranking_passed"),
                  value: rows.filter((r) => r.overall_percentage >= 50).length,
                  tone: "mint" as const,
                },
                {
                  label: tx("ranking_flagged"),
                  value: rows.filter((r) => r.is_flagged).length,
                  tone: "rose" as const,
                },
                {
                  label: tx("analytics_average_score"),
                  value: rows.length
                    ? `${(rows.reduce((s, r) => s + r.overall_percentage, 0) / rows.length).toFixed(1)}%`
                    : "0%",
                  tone: "neutral" as const,
                },
              ]
          ).map(({ label, value }) => (
            <Card key={label} className="text-center">
              <p className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</p>
              <p className="mt-1 text-[22px] font-semibold text-ink">{value}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Top performer */}
      {!loading && topPerformer && (
        <Card className="flex flex-wrap items-center justify-between gap-3 border-amber/30 bg-amber-soft/30">
          <div className="flex items-center gap-3">
            <span className="text-[22px]">🏆</span>
            <div>
              <p className="text-[11px] uppercase tracking-wide text-ink-muted">{t("topPerformer")}</p>
              <p className="text-[14px] font-semibold text-ink">{topPerformer.full_name}</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-[15px] font-semibold text-ink">
              {topPerformer.obtained_marks.toFixed(1)}/{topPerformer.total_marks.toFixed(1)}
            </p>
            <p className="text-[12px] text-ink-muted">{topPerformer.overall_percentage.toFixed(1)}%</p>
          </div>
        </Card>
      )}

      <Card padded={false}>
        <div className="p-5 border-b border-line">
          <SectionTitle
            title={t("candidateRankings")}
            hint={t("candidateRankingsHint")}
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
              title={t("noCompletedSessions")}
              body={t("noCompletedSessionsBody")}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-line bg-sunken/40 text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3 text-left">{t("rank")}</th>
                  <th className="px-5 py-3 text-left">{t("candidate")}</th>
                  <th className="px-5 py-3 text-right">{t("score")}</th>
                  <th className="px-5 py-3 text-right">{t("attempted")}</th>
                  <th className="px-5 py-3 text-right">{t("accuracy")}</th>
                  <th className="px-5 py-3 text-right">{t("time")}</th>
                  <th className="px-5 py-3 text-center">{t("proctor")}</th>
                  {isCorporate && <th className="px-5 py-3 text-center">{t("status")}</th>}
                  {isCorporate && <th className="px-5 py-3 text-right">{t("shortlist")}</th>}
                  <th className="px-5 py-3 text-right">{t("result")}</th>
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
                        <p className="font-medium text-ink">
                          {row.correct_count + row.incorrect_count}
                          <span className="text-ink-muted">
                            /{row.correct_count + row.incorrect_count + row.unanswered_count}
                          </span>
                        </p>
                        <p className="text-[11px]">
                          <span className="text-mint">{row.correct_count} ✓</span>
                          {" · "}
                          <span className="text-rose">{row.incorrect_count} ✗</span>
                          {row.unanswered_count > 0 && (
                            <>
                              {" · "}
                              <span>{tx("ranking_blank_count", { count: row.unanswered_count })}</span>
                            </>
                          )}
                        </p>
                      </td>
                      <td className="px-5 py-3 text-right text-ink-soft">
                        {row.accuracy.toFixed(1)}%
                      </td>
                      <td className="px-5 py-3 text-right text-ink-soft">
                        {row.time_taken_seconds != null
                          ? tx("ranking_time_taken", { m: Math.floor(row.time_taken_seconds / 60), s: row.time_taken_seconds % 60 })
                          : "—"}
                      </td>
                      <td className="px-5 py-3 text-center">
                        {row.is_flagged ? (
                          <Badge tone="rose">{tx("ranking_flagged_score", { score: row.suspicion_score.toFixed(0) })}</Badge>
                        ) : (
                          <Badge tone="mint">{t("clear")}</Badge>
                        )}
                      </td>
                      {isCorporate && (
                        <td className="px-5 py-3 text-center">
                          {row.shortlist_status ? (
                            <Badge tone={SHORTLIST_TONE[row.shortlist_status]}>
                              {tx(`shortlist_${row.shortlist_status}`)}
                            </Badge>
                          ) : (
                            <span className="text-ink-muted">{t("pending")}</span>
                          )}
                        </td>
                      )}
                      {isCorporate && (
                        <td className="px-5 py-3">
                          <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={saving === row.candidate_id}
                              onClick={() => setShortlist(row.candidate_id, "shortlisted")}
                              className="!text-mint hover:!bg-mint/10"
                            
                              title={tx("ranking_action_shortlist")}
                              aria-label={tx("ranking_action_shortlist")}
                            >
                              ✓
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={saving === row.candidate_id}
                              onClick={() => setShortlist(row.candidate_id, "on_hold")}
                              className="!text-amber hover:!bg-amber/10"
                            
                              title={tx("ranking_action_hold")}
                              aria-label={tx("ranking_action_hold")}
                            >
                              ⏸
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              loading={saving === row.candidate_id}
                              onClick={() => setShortlist(row.candidate_id, "rejected")}
                              className="!text-rose hover:!bg-rose/10"
                            
                              title={tx("ranking_action_reject")}
                              aria-label={tx("ranking_action_reject")}
                            >
                              ✗
                            </Button>
                          </div>
                        </td>
                      )}
                      <td className="px-5 py-3">
                        <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                          {row.published ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              loading={downloading === row.result_id}
                              disabled={!row.result_id}
                              onClick={() => downloadReport(row)}
                            >
                              {tx("ranking_download_report")}
                            </Button>
                          ) : canPublish(row) ? (
                            <Button
                              size="sm"
                              loading={publishing === row.session_id}
                              disabled={publishing !== null}
                              onClick={() => publishOne(row)}
                            >
                              {tx("ranking_publish_result")}
                            </Button>
                          ) : row.needs_integrity_review ? (
                            <Link href={`/dashboard/proctoring/${row.session_id}`}>
                              <Button size="sm" variant="ghost">{t("reviewFlags")}</Button>
                            </Link>
                          ) : (
                            <span className="text-[12px] text-ink-muted">
                              {row.integrity_verdict === "malpractice"
                                ? tx("ranking_withheld")
                                : row.pending_review_count > 0
                                  ? tx("ranking_grading_pending")
                                  : "—"}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Expanded section breakdown */}
                    {expandedRow === row.candidate_id && row.section_scores.length > 0 && (
                      <tr key={`${row.candidate_id}-expanded`} className="bg-sunken/30">
                        <td colSpan={isCorporate ? 9 : 7} className="px-8 py-4">
                          <p className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">
                            {t("sectionWiseBreakdown")}
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
            {isCorporate ? (
              <>
                <strong>{tx("ranking_legend_actions")}</strong> {tx("ranking_legend_body")}
              </>
            ) : (
              <>
                <strong>{t("proctor")}</strong> {t("proctorExplanation")}
              </>
            )}
          </p>
        </Card>
      )}
    </div>
  );
}
