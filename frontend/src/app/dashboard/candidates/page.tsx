"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  SectionTitle,
  Skeleton,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateAttempt, CandidateRow } from "@/lib/types";

export default function CandidatesPage() {
  const t = useTranslations("dashboard-detail");
  const ta = useTranslations("adminShell");
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<CandidateRow | null>(null);
  const [attempts, setAttempts] = useState<CandidateAttempt[]>([]);
  const [attemptsLoading, setAttemptsLoading] = useState(false);
  const [publishing, setPublishing] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const load = useCallback(async () => {
    const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
    try {
      setCandidates(await api.get<CandidateRow[]>(`/admin/candidates${query}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ta("error_load_candidates"));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  const openCandidate = useCallback(async (candidate: CandidateRow) => {
    setOpen(candidate);
    setAttemptsLoading(true);
    try {
      setAttempts(await api.get<CandidateAttempt[]>(`/candidates/${candidate.id}/attempts`));
    } catch {
      setAttempts([]);
    } finally {
      setAttemptsLoading(false);
    }
  }, []);

  /**
   * The three conditions for releasing one candidate's marks, mirroring the server:
   * they have finished sitting, every answer has had a human decision, and — if
   * proctoring flagged the sitting — an examiner has ruled on it. The button is hidden
   * rather than disabled once a result is out, since republishing is a no-op.
   */
  function canPublish(attempt: CandidateAttempt): boolean {
    return (
      attempt.status !== "in_progress" &&
      !attempt.published &&
      attempt.pending_review_count === 0 &&
      !attempt.needs_integrity_review &&
      attempt.integrity_verdict !== "malpractice"
    );
  }

  async function publishOne(attempt: CandidateAttempt) {
    setPublishing(attempt.session_id);
    try {
      const response = await api.post<{ detail: string }>(
        `/sessions/${attempt.session_id}/result/publish`,
      );
      toast(response.detail, "mint");
      if (open) await openCandidate(open);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_publish_result"), "rose");
    } finally {
      setPublishing(null);
    }
  }

  async function downloadReport(attempt: CandidateAttempt) {
    if (!attempt.result_id) return;
    setDownloading(attempt.result_id);
    try {
      const safeName = open ? open.full_name.replace(/\s+/g, "_") : "candidate";
      await api.download(
        `/results/${attempt.result_id}/pdf?simple=true`,
        `report_${safeName}.pdf`,
      );
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_download_report"), "rose");
    } finally {
      setDownloading(null);
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title={ta("nav_candidates")}
        body={ta("candidates_body")}
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="mb-4 max-w-sm">
          <Field label={t("field_search")}>
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("placeholder_name_or_email")}
            />
          </Field>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-[12px]" />
            ))}
          </div>
        ) : candidates.length === 0 ? (
          <EmptyState title={ta("no_candidates_found")} body={ta("no_candidates_body")} />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="pb-2 pr-3 font-medium">{t("header_candidate")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("header_attempts")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("header_completed")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("header_average")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("header_flags")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("header_last_seen")}</th>
                  <th className="pb-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {candidates.map((row) => (
                  <tr key={row.id} className={cx(!row.is_active && "opacity-55")}>
                    <td className="py-3 pr-3">
                      <p className="text-[13.5px] font-medium text-ink">{row.full_name}</p>
                      <p className="text-[12px] text-ink-muted">{row.email}</p>
                    </td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">{row.attempts}</td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">{row.completed}</td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">
                      {row.average_percentage !== null ? `${row.average_percentage}%` : "—"}
                    </td>
                    <td className="py-3 pr-3">
                      {row.flagged_sessions > 0 ? (
                        <Badge tone="rose">{row.flagged_sessions}</Badge>
                      ) : (
                        <span className="text-[13px] text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-3 text-[12.5px] text-ink-muted">
                      {formatDate(row.last_login_at, false)}
                    </td>
                    <td className="py-3 text-right">
                      <Button size="sm" variant="secondary" onClick={() => openCandidate(row)}>
                        {ta("history")}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm"
          onClick={() => setOpen(null)}
        >
          <div
            className="w-full max-w-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Card className="animate-rise max-h-[80vh] overflow-y-auto">
              <SectionTitle
                title={open.full_name}
                hint={open.email}
                action={
                  <Button size="sm" variant="secondary" onClick={() => setOpen(null)}>
                    {ta("close")}
                  </Button>
                }
              />

              {attemptsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 rounded-[10px]" />
                  ))}
                </div>
              ) : attempts.length === 0 ? (
                <EmptyState
                  title={ta("no_attempts")}
                  body={ta("no_attempts_body")}
                />
              ) : (
                <ul className="divide-y divide-line">
                  {attempts.map((attempt) => (
                    <li key={attempt.session_id} className="flex flex-wrap items-center gap-3 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-ink">
                          {attempt.exam_title}
                        </p>
                        <p className="text-[12px] text-ink-muted">
                          {formatDate(attempt.started_at)} ·{" "}
                          {ta.has(`session_${attempt.status}`) ? ta(`session_${attempt.status}`) : attempt.status.replace("_", " ")}
                        </p>
                      </div>

                      {attempt.percentage !== null && (
                        <Badge
                          tone={
                            attempt.percentage >= 70
                              ? "mint"
                              : attempt.percentage >= 40
                                ? "amber"
                                : "rose"
                          }
                        >
                          {attempt.percentage}%
                        </Badge>
                      )}
                      {attempt.is_flagged && <Badge tone="rose">{ta("badge_flagged")}</Badge>}

                      {attempt.integrity_verdict === "malpractice" ? (
                        <Badge tone="rose">{ta("badge_malpractice")}</Badge>
                      ) : attempt.needs_integrity_review ? (
                        <Badge tone="amber">{ta("badge_needs_ruling")}</Badge>
                      ) : attempt.integrity_verdict === "cleared" ? (
                        <Badge tone="mint">{ta("badge_genuine")}</Badge>
                      ) : null}

                      {attempt.published ? (
                        <Badge tone="mint">{ta("badge_published")}</Badge>
                      ) : attempt.pending_review_count > 0 ? (
                        <Badge tone="amber">{ta("badge_to_grade", { count: attempt.pending_review_count })}</Badge>
                      ) : null}

                      <div className="flex gap-1.5">
                        <Link href={`/dashboard/proctoring/${attempt.session_id}`}>
                          <Button
                            size="sm"
                            variant={attempt.needs_integrity_review ? "primary" : "ghost"}
                          >
                            {attempt.needs_integrity_review ? ta("review_flags") : ta("nav_proctoring")}
                          </Button>
                        </Link>
                        {attempt.result_id && (
                          <Link href={`/results/${attempt.result_id}`}>
                            <Button size="sm" variant="secondary">
                              {ta("result")}
                            </Button>
                          </Link>
                        )}
                        {attempt.published && attempt.result_id && (
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={downloading === attempt.result_id}
                            onClick={() => void downloadReport(attempt)}
                          >
                            {ta("download_report")}
                          </Button>
                        )}
                        {canPublish(attempt) && (
                          <Button
                            size="sm"
                            loading={publishing === attempt.session_id}
                            disabled={publishing !== null}
                            onClick={() => void publishOne(attempt)}
                          >
                            {ta("publish_to_candidate")}
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
