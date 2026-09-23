"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { AwaitingApproval } from "@/components/AwaitingApproval";
import {
  Alert,
  Badge,
  Button,
  Card,
  Countdown,
  EmptyState,
  KPIBanner,
  ProgressBar,
  RingProgress,
  Skeleton,
  StatusDot,
  TimelineCard,
  cx,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  ProctorReview, Exam, ExaminerStats, GradingSummary, LoginRequestRow,
} from "@/lib/types";

/* ─── Greeting based on time of day ─────────────────────────────── */
function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export default function ExaminerDashboard() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const t = useTranslations("examiner");
  const [stats, setStats] = useState<ExaminerStats | null>(null);
  const [summaries, setSummaries] = useState<GradingSummary[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loginRequests, setLoginRequests] = useState<LoginRequestRow[]>([]);
  const [flagged, setFlagged] = useState<ProctorReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const approved = user?.access_status === "approved" || user?.role === "admin";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user || !approved) { if (!cancelled) setLoading(false); return; }
      try {
        const [statsData, summaryData, examData, requestData, flaggedData] = await Promise.all([
          api.get<ExaminerStats>("/examiner/stats"),
          api.get<GradingSummary[]>("/grading/summary"),
          api.get<Exam[]>("/exams?limit=6"),
          api.get<LoginRequestRow[]>("/login-requests?status=pending"),
          api.get<ProctorReview[]>("/proctoring/sessions?flagged_only=true&limit=50"),
        ]);
        if (cancelled) return;
        setStats(statsData);
        setSummaries(summaryData);
        setExams(examData);
        setLoginRequests(requestData);
        setFlagged(flaggedData);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : t("dashboard_error"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, approved]);

  const needsRuling = flagged.filter((s) => s.needs_integrity_review);
  const urgentGrading = [...summaries].sort((a, b) => b.pending_review - a.pending_review);

  if (!user) return null;
  if (!approved) {
    return <AwaitingApproval role="examiner" status={user.access_status} note={user.access_note} />;
  }

  return (
    <div className="space-y-7">

      {/* ─── Welcome Banner ──────────────────────────────────────── */}
      <div
        className="relative overflow-hidden rounded-[20px] border border-line p-6 sm:p-8"
        style={{
          background: "linear-gradient(135deg, rgba(79,70,229,0.08) 0%, rgba(124,58,237,0.05) 50%, rgba(16,185,129,0.04) 100%)",
          borderColor: "rgba(99,102,241,0.2)",
          boxShadow: "0 4px 32px -8px rgba(79,70,229,0.12)",
        }}
      >
        {/* background decoration */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full opacity-[0.04]"
          style={{ background: "radial-gradient(circle, #4f46e5, transparent 70%)" }} />
        <div className="pointer-events-none absolute -bottom-8 -left-8 h-40 w-40 rounded-full opacity-[0.03]"
          style={{ background: "radial-gradient(circle, #7c3aed, transparent 70%)" }} />

        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="mb-1 flex items-center gap-2">
              <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-[11px] font-bold tracking-wide text-accent uppercase">
                Examiner
              </span>
              {needsRuling.length > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-amber-soft px-2.5 py-0.5 text-[11px] font-bold text-amber-ink border border-amber/20">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber animate-pulse" />
                  {needsRuling.length} need{needsRuling.length === 1 ? "s" : ""} ruling
                </span>
              )}
            </div>
            <h1 className="text-[22px] font-extrabold tracking-tight text-ink sm:text-[26px]">
              {greeting()}, {user.full_name.split(" ")[0]} 👋
            </h1>
            <p className="mt-1 text-[13.5px] text-ink-muted max-w-md">
              {t("examiner_workspace_body")}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Link href="/dashboard/questions/ai-generate">
              <Button variant="secondary" size="sm">
                <SparkleIcon /> AI Generate
              </Button>
            </Link>
            <Link href="/dashboard/exams/create">
              <Button size="sm">
                <PlusIcon /> {t("create_exam_button")}
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {/* ─── KPI Strip ───────────────────────────────────────────── */}
      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-[14px] border border-line bg-surface p-4">
              <Skeleton className="mb-2 h-2.5 w-16" />
              <Skeleton className="h-7 w-12" />
            </div>
          ))}
        </div>
      ) : stats ? (
        <KPIBanner items={[
          { label: t("total_assessments"),      value: stats.my_exams,                   tone: "accent" },
          { label: t("active_assessments"),     value: stats.active_assessments,          tone: "green",
            trend: stats.active_assessments > 0 ? { value: "Live now", up: true } : undefined },
          { label: t("completed_assessments"),  value: stats.completed_assessments,       tone: "neutral" },
          { label: t("pending_result_reviews"), value: stats.pending_grading,             tone: stats.pending_grading > 0 ? "amber" : "neutral",
            trend: stats.pending_grading > 0 ? { value: "Needs review", up: false } : undefined },
          { label: t("published_results"),      value: stats.published_results_count,     tone: "mint" },
          { label: t("total_candidates"),       value: stats.total_candidates,            tone: "purple" },
        ]} />
      ) : null}

      {/* ─── Main body: 2/3 + 1/3 ───────────────────────────────── */}
      <div className="grid gap-6 lg:grid-cols-3">

        {/* LEFT: Exams */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-ink">{t("recent_exams_heading")}</h2>
            <Link href="/dashboard/exams" className="text-[12.5px] font-semibold text-accent hover:underline">
              {t("view_all")} →
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="rounded-[14px] border border-line bg-surface p-4">
                  <Skeleton className="mb-2 h-4 w-52" />
                  <Skeleton className="h-3 w-36" />
                </div>
              ))}
            </div>
          ) : exams.length === 0 ? (
            <EmptyState
              title={t("no_exams_yet")}
              body={t("no_exams_body")}
              icon={<ExamIcon />}
              action={
                <Link href="/dashboard/exams/create">
                  <Button size="sm">{t("create_exam_button")}</Button>
                </Link>
              }
            />
          ) : (
            <div className="space-y-2.5">
              {exams.map((exam) => (
                <ExamCard key={exam.id} exam={exam} t={t} />
              ))}
            </div>
          )}

          {/* ─── Grading Queue (full-width inside left column) ─── */}
          {!loading && summaries.length > 0 && (
            <div className="mt-2">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[15px] font-bold text-ink">{t("grading_queue_heading")}</h2>
                <Link href="/dashboard/grading" className="text-[12.5px] font-semibold text-accent hover:underline">
                  {t("review")} →
                </Link>
              </div>
              <div className="space-y-2.5">
                {urgentGrading.slice(0, 4).map((summary, idx) => {
                  const pct = (summary.reviewed / Math.max(summary.pending_review + summary.reviewed, 1)) * 100;
                  const urgent = summary.pending_review >= 10;
                  return (
                    <Link key={summary.exam_id} href={`/dashboard/grading?exam_id=${summary.exam_id}`}>
                      <Card hover className="!p-4 group">
                        <div className="flex items-start gap-4">
                          <RingProgress
                            value={pct}
                            size={48}
                            stroke={5}
                            tone={urgent ? "amber" : "accent"}
                            label={`${Math.round(pct)}%`}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-2">
                              <p className="truncate text-[13px] font-semibold text-ink group-hover:text-accent transition-colors">
                                {summary.exam_title}
                              </p>
                              <Badge tone={urgent ? "amber" : "neutral"} size="xs">
                                {t("pending_left", { count: summary.pending_review })}
                              </Badge>
                            </div>
                            <div className="mt-2">
                              <ProgressBar value={pct} tone={urgent ? "amber" : "accent"} size="sm" />
                            </div>
                            <p className="mt-1 text-[11px] text-ink-muted">
                              {summary.reviewed} graded · {summary.pending_review} left
                              {idx === 0 && urgent && (
                                <span className="ml-2 font-semibold text-amber">⚡ Highest priority</span>
                              )}
                            </p>
                          </div>
                        </div>
                      </Card>
                    </Link>
                  );
                })}
              </div>
            </div>
          )}

          {/* "All caught up" state */}
          {!loading && summaries.length === 0 && (
            <Card className="!py-8 text-center">
              <p className="text-[22px]">✅</p>
              <p className="mt-2 text-[13px] font-semibold text-ink">{t("all_caught_up")}</p>
              <p className="mt-0.5 text-[12px] text-ink-muted">{t("no_pending_reviews")}</p>
            </Card>
          )}
        </div>

        {/* RIGHT: Flagged + Requests + Quick actions */}
        <div className="space-y-5">

          {/* Flagged Sessions */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-[15px] font-bold text-ink">
                {t("flagged_sessions_heading")}
                {flagged.length > 0 && (
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-rose text-[10px] font-bold text-white">
                    {flagged.length}
                  </span>
                )}
              </h2>
              <Link href="/dashboard/proctoring" className="text-[12.5px] font-semibold text-accent hover:underline">
                {t("review")} →
              </Link>
            </div>

            {loading ? (
              <div className="space-y-2">
                {[...Array(2)].map((_, i) => <Skeleton key={i} className="h-20 rounded-[12px]" />)}
              </div>
            ) : flagged.length === 0 ? (
              <Card className="!py-8 text-center">
                <p className="text-[22px]">🛡️</p>
                <p className="mt-2 text-[13px] font-semibold text-ink">{t("nothing_flagged")}</p>
                <p className="mt-0.5 text-[12px] text-ink-muted">{t("no_integrity_ruling")}</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {needsRuling.length > 0 && (
                  <Alert tone="amber">
                    {t("flagged_alert", { count: needsRuling.length, plural: needsRuling.length === 1 ? "" : "s" })}
                  </Alert>
                )}
                {flagged.slice(0, 4).map((session) => {
                  const suspicion = Math.round(session.suspicion_score);
                  const tone = session.integrity_verdict === "malpractice" ? "rose"
                    : session.integrity_verdict === "cleared" ? "green" : "amber";
                  return (
                    <Link key={session.session_id} href={`/dashboard/proctoring/${session.session_id}`}>
                      <Card hover className="!p-3.5">
                        <div className="flex items-center gap-3">
                          {/* Risk gauge */}
                          <div className="relative shrink-0">
                            <RingProgress value={suspicion} size={44} stroke={4} tone={tone} />
                            <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-ink">
                              {suspicion}
                            </span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-1">
                              <p className="truncate text-[12.5px] font-semibold text-ink">
                                {session.candidate_name}
                              </p>
                              <Badge tone={tone} size="xs">
                                {session.integrity_verdict === "pending" ? t("needs_ruling") : session.integrity_verdict}
                              </Badge>
                            </div>
                            <p className="truncate text-[11.5px] text-ink-muted">{session.exam_title}</p>
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {session.focus_violation_count > 0 && (
                                <Badge tone="rose" size="xs">{t("left_exam", { count: session.focus_violation_count })}</Badge>
                              )}
                              {session.status === "auto_submitted" && (
                                <Badge tone="amber" size="xs">{t("auto_submitted")}</Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      </Card>
                    </Link>
                  );
                })}
                {flagged.length > 4 && (
                  <Link href="/dashboard/proctoring" className="block text-center text-[12.5px] font-semibold text-accent hover:underline pt-1">
                    {t("more_flagged", { count: flagged.length - 4 })}
                  </Link>
                )}
              </div>
            )}
          </div>

          {/* Login Requests */}
          {loginRequests.length > 0 && (
            <Card className="!p-4 border-amber/30 bg-amber-soft/20">
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-amber text-white">
                  <BellIcon />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-bold text-ink">
                    {t("pending_requests", { count: loginRequests.length, plural: loginRequests.length === 1 ? "request" : "requests" })}
                  </p>
                  <p className="mt-0.5 text-[12px] text-ink-muted">{t("candidates_awaiting_access")}</p>
                </div>
              </div>
              <Link href="/dashboard/login-requests">
                <Button variant="secondary" size="sm" className="mt-3 w-full">
                  {t("review_requests")}
                </Button>
              </Link>
            </Card>
          )}

          {/* Quick Actions */}
          <div>
            <h2 className="mb-3 text-[14px] font-bold text-ink uppercase tracking-wide">{t("quick_actions")}</h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { href: "/dashboard/exams/create",          label: t("quick_action_create_exam"),      icon: ExamIcon,    color: "#4f46e5" },
                { href: "/dashboard/questions?compose=1",   label: t("quick_action_new_question"),     icon: BankIcon,    color: "#0f9b8e" },
                { href: "/dashboard/questions/ai-generate", label: t("quick_action_ai_generate"),      icon: SparkleIcon, color: "#7c3aed" },
                { href: "/dashboard/questions",             label: t("quick_action_question_bank"),    icon: BankIcon,    color: "#0ea5e9" },
                { href: "/dashboard/grading",               label: t("quick_action_review_grading"),   icon: GradingIcon, color: "#d97706" },
                { href: "/dashboard/proctoring",            label: t("quick_action_proctoring"),       icon: ShieldIcon,  color: "#dc2626" },
              ].map((action) => (
                <Link key={action.href} href={action.href}>
                  <button className="group w-full rounded-[12px] border border-line bg-surface p-3.5 text-left transition-all duration-200 hover:border-accent/25 hover:bg-accent-soft/20 hover:-translate-y-[1px] hover:shadow-sm">
                    <div className="mb-2.5 flex h-8 w-8 items-center justify-center rounded-[9px] text-white transition-transform duration-200 group-hover:scale-110"
                      style={{ background: `linear-gradient(135deg, ${action.color}, ${action.color}bb)`, boxShadow: `0 2px 8px -2px ${action.color}55` }}>
                      <action.icon />
                    </div>
                    <p className="text-[12px] font-semibold text-ink group-hover:text-accent transition-colors">{action.label}</p>
                  </button>
                </Link>
              ))}
            </div>
          </div>

          {/* System Status */}
          <Card className="!p-4">
            <p className="mb-3 text-[11px] font-bold uppercase tracking-widest text-ink-muted">Platform Status</p>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <StatusDot tone="green" label="Exam Runner" />
                <span className="text-[11px] text-ink-muted">Operational</span>
              </div>
              <div className="flex items-center justify-between">
                <StatusDot tone="green" label="AI Proctoring" />
                <span className="text-[11px] text-ink-muted">Operational</span>
              </div>
              <div className="flex items-center justify-between">
                <StatusDot tone="green" label="Grading Queue" />
                <span className="text-[11px] text-ink-muted">Operational</span>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ─── Enhanced Exam Card ─────────────────────────────────────────── */
function ExamCard({ exam, t }: { exam: Exam; t: ReturnType<typeof useTranslations> }) {
  const router = useRouter();
  const statusTone: Record<string, "green" | "amber" | "neutral" | "rose"> = {
    published: "green", draft: "amber", closed: "neutral",
  };
  const statusIcon: Record<string, string> = {
    published: "🟢", draft: "🟡", closed: "⚫",
  };

  const isLive = exam.status === "published";

  return (
    <div
      role="link" tabIndex={0}
      onClick={() => router.push("/dashboard/exams")}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); router.push("/dashboard/exams"); } }}
      className="cursor-pointer"
    >
      <Card hover className={cx("!p-4 group transition-all duration-200",
        isLive && "border-green/20 hover:border-green/40")}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-[11px]">{statusIcon[exam.status] ?? "⚫"}</span>
              <p className="truncate text-[13.5px] font-semibold text-ink group-hover:text-accent transition-colors">
                {exam.title}
              </p>
            </div>
            <p className="truncate text-[12px] text-ink-muted">
              {exam.subject_name}
              {exam.company_name && ` · ${exam.company_name}`}
              {exam.job_role && ` · ${exam.job_role}`}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <Badge tone={exam.exam_type === "corporate" ? "accent" : "neutral"} size="xs">
              {exam.exam_type === "corporate" ? "Corp" : "Acad"}
            </Badge>
            <Badge tone={statusTone[exam.status] ?? "neutral"} size="xs">
              {exam.status}
            </Badge>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-3 text-[11.5px] text-ink-muted">
          <span className="flex items-center gap-1">
            <span>📋</span> {exam.total_questions} Q
          </span>
          <span className="flex items-center gap-1">
            <span>⏱</span> {exam.duration_minutes} min
          </span>
          {isLive && exam.ends_at && (
            <span className="flex items-center gap-1 font-semibold text-green">
              <span>🔴</span>
              Closes in <Countdown target={exam.ends_at} />
            </span>
          )}
          <span className="ml-auto flex items-center gap-3">
            <Link
              href={`/dashboard/exams/${exam.id}/ranking`}
              onClick={(e) => e.stopPropagation()}
              className="font-semibold text-accent hover:underline"
            >
              {exam.exam_type === "corporate" ? "Ranking →" : "Results →"}
            </Link>
            {exam.exam_type === "academic" && (
              <Link
                href={`/dashboard/exams/${exam.id}/analytics`}
                onClick={(e) => e.stopPropagation()}
                className="font-semibold text-accent hover:underline"
              >
                Analytics →
              </Link>
            )}
          </span>
        </div>
      </Card>
    </div>
  );
}

/* ─── Inline Icons ───────────────────────────────────────────────── */
function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={2} strokeLinecap="round" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
function SparkleIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z" />
    </svg>
  );
}
function ExamIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v5h5" /><path d="M9 13l1.8 1.8L14.5 11" />
    </svg>
  );
}
function GradingIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H15l5 5v9.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5Z" />
      <path d="M8 14.5l2.2 2.2L16 11" />
    </svg>
  );
}
function BellIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}
function BankIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 6.5c0-1.4 3.6-2.5 8-2.5s8 1.1 8 2.5-3.6 2.5-8 2.5-8-1.1-8-2.5Z" />
      <path d="M4 6.5v11c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-11M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5" />
    </svg>
  );
}
function ShieldIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 3l7.5 3v5.5c0 4.6-3.1 8.3-7.5 9.5-4.4-1.2-7.5-4.9-7.5-9.5V6Z" />
      <path d="M9.2 12.2 11.3 14.3 15 10.5" />
    </svg>
  );
}
