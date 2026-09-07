"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AwaitingApproval } from "@/components/AwaitingApproval";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Skeleton,
  StatCard,
  cx,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Exam, ExaminerStats, GradingSummary, LoginRequestRow } from "@/lib/types";



export default function ExaminerDashboard() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [stats, setStats] = useState<ExaminerStats | null>(null);
  const [summaries, setSummaries] = useState<GradingSummary[]>([]);
  const [exams, setExams] = useState<Exam[]>([]);
  const [loginRequests, setLoginRequests] = useState<LoginRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const approved = user?.access_status === "approved" || user?.role === "admin";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user || !approved) { if (!cancelled) setLoading(false); return; }
      try {
        const [statsData, summaryData, examData, requestData] = await Promise.all([
          api.get<ExaminerStats>("/examiner/stats"),
          api.get<GradingSummary[]>("/grading/summary"),
          api.get<Exam[]>("/exams?limit=6"),
          api.get<LoginRequestRow[]>("/login-requests?status=pending"),
        ]);
        if (cancelled) return;
        setStats(statsData);
        setSummaries(summaryData);
        setExams(examData);
        setLoginRequests(requestData);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load the dashboard.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, approved]);

  if (!user) return null;
  if (!approved) {
    return <AwaitingApproval role="examiner" status={user.access_status} note={user.access_note} />;
  }

  return (
    <div className="space-y-6">

      {error && <Alert tone="rose">{error}</Alert>}

      {/* ─── Stats grid ────────────────────────────────────── */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-[12px] border border-line bg-surface p-5">
              <Skeleton className="mb-3 h-3 w-20" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))}
        </div>
      ) : stats ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="My Exams"
            value={stats.my_exams}
            tone="accent"
            icon={<ExamIcon />}
          />
          <StatCard
            label="Published"
            value={stats.published_exams}
            tone="green"
            icon={<UsersIcon />}
          />
          <StatCard
            label="Pending Grading"
            value={stats.pending_grading}
            tone={stats.pending_grading > 0 ? "amber" : "neutral"}
            icon={<GradingIcon />}
          />
          <StatCard
            label="Access Requests"
            value={loginRequests.length}
            tone={loginRequests.length > 0 ? "rose" : "neutral"}
            icon={<BellIcon />}
          />
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* ─── Recent Exams ──────────────────────────────── */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-ink">Recent Exams</h2>
            <Link href="/dashboard/exams" className="text-[12.5px] font-medium text-accent hover:underline">
              View all →
            </Link>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="rounded-[12px] border border-line bg-surface p-4">
                  <Skeleton className="mb-2 h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
              ))}
            </div>
          ) : exams.length === 0 ? (
            <EmptyState
              title="No exams yet"
              body="Create your first exam to start assessing candidates."
              action={
                <Link href="/dashboard/exams">
                  <Button size="sm">+ Create Exam</Button>
                </Link>
              }
            />
          ) : (
            <div className="space-y-2">
              {exams.map((exam) => (
                <ExamCard key={exam.id} exam={exam} />
              ))}
            </div>
          )}
        </div>

        {/* ─── Right column ─────────────────────────────── */}
        <div className="space-y-5">
          {/* Grading queue */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[15px] font-semibold text-ink">Grading Queue</h2>
              <Link href="/dashboard/grading" className="text-[12.5px] font-medium text-accent hover:underline">
                Review →
              </Link>
            </div>
            {loading ? (
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 rounded-[10px]" />)}
              </div>
            ) : summaries.length === 0 ? (
              <Card className="text-center py-8">
                <p className="text-[13px] text-ink-muted">All caught up ✓</p>
                <p className="mt-0.5 text-[12px] text-ink-muted">No pending reviews</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {summaries.slice(0, 4).map((summary) => (
                  <Link key={summary.exam_id} href={`/dashboard/grading?exam_id=${summary.exam_id}`}>
                    <Card hover className="!p-3.5 transition">
                      <p className="truncate text-[13px] font-medium text-ink">{summary.exam_title}</p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <div className="flex-1">
                          <ProgressBar
                            value={(summary.reviewed / Math.max(summary.pending_review + summary.reviewed, 1)) * 100}
                            tone="accent"
                            size="xs"
                          />
                        </div>
                        <Badge tone="amber" size="xs">{summary.pending_review} left</Badge>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Login requests */}
          {loginRequests.length > 0 && (
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-[15px] font-semibold text-ink">Access Requests</h2>
                <Link href="/dashboard/login-requests" className="text-[12.5px] font-medium text-accent hover:underline">
                  Manage →
                </Link>
              </div>
              <Card className="!p-3.5">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-amber-soft text-amber">
                    <BellIcon />
                  </div>
                  <div>
                    <p className="text-[13px] font-semibold text-ink">
                      {loginRequests.length} pending {loginRequests.length === 1 ? "request" : "requests"}
                    </p>
                    <p className="text-[12px] text-ink-muted">Candidates awaiting access</p>
                  </div>
                </div>
                <Link href="/dashboard/login-requests">
                  <Button variant="secondary" size="sm" className="mt-3 w-full">
                    Review Requests
                  </Button>
                </Link>
              </Card>
            </div>
          )}

          {/* Quick actions */}
          <div>
            <h2 className="mb-3 text-[15px] font-semibold text-ink">Quick Actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {[
                { href: "/dashboard/exams", label: "Create Exam", icon: <ExamIcon /> },
                { href: "/dashboard/questions", label: "Add Question", icon: <BankIcon /> },
                { href: "/dashboard/questions/ai-generate", label: "AI Generate", icon: <SparkleIcon /> },
                { href: "/dashboard/proctoring", label: "Proctoring", icon: <ShieldIcon /> },
              ].map((action) => (
                <Link key={action.href} href={action.href}>
                  <button className="w-full rounded-[10px] border border-line bg-surface p-3 text-left hover:bg-sunken hover:border-line-strong transition-all">
                    <div className="mb-2 flex h-7 w-7 items-center justify-center rounded-[8px] bg-accent-soft text-accent">
                      {action.icon}
                    </div>
                    <p className="text-[12px] font-semibold text-ink">{action.label}</p>
                  </button>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Exam Card ──────────────────────────────────────────────────── */
function ExamCard({ exam }: { exam: Exam }) {
  const statusTone: Record<string, "green" | "amber" | "neutral"> = {
    published: "green",
    draft: "amber",
    closed: "neutral",
  };
  const typeTone: Record<string, "accent" | "neutral"> = {
    corporate: "accent",
    academic: "neutral",
  };

  return (
    <Link href={`/dashboard/exams`}>
      <Card hover className="!p-4 group">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13.5px] font-semibold text-ink group-hover:text-accent transition">
              {exam.title}
            </p>
            <p className="mt-0.5 truncate text-[12px] text-ink-muted">
              {exam.subject_name}
              {exam.company_name && ` · ${exam.company_name}`}
              {exam.job_role && ` · ${exam.job_role}`}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Badge tone={typeTone[exam.exam_type ?? "academic"] ?? "neutral"} size="xs">
              {exam.exam_type === "corporate" ? "Corp" : "Acad"}
            </Badge>
            <Badge tone={statusTone[exam.status] ?? "neutral"} size="xs">
              {exam.status}
            </Badge>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-4 text-[12px] text-ink-muted">
          <span>{exam.total_questions} questions</span>
          <span>{exam.duration_minutes} min</span>
          {exam.exam_type === "corporate" && (
            <Link
              href={`/dashboard/exams/${exam.id}/ranking`}
              onClick={(e) => e.stopPropagation()}
              className="ml-auto font-medium text-accent hover:underline"
            >
              Ranking →
            </Link>
          )}
          {exam.exam_type === "academic" && (
            <Link
              href={`/dashboard/exams/${exam.id}/analytics`}
              onClick={(e) => e.stopPropagation()}
              className="ml-auto font-medium text-accent hover:underline"
            >
              Analytics →
            </Link>
          )}
        </div>
      </Card>
    </Link>
  );
}

/* ─── Inline icons ───────────────────────────────────────────────── */
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
      <path d="M14 3v5h5" />
      <path d="M9 13l1.8 1.8L14.5 11" />
    </svg>
  );
}
function UsersIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="9" cy="8" r="3.25" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <path d="M16.5 5.4a3.25 3.25 0 0 1 0 5.2M18 14.6A6 6 0 0 1 21 20" />
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
