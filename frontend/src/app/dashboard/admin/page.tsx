"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Skeleton,
  StatCard,
  cx,
  formatDate,
  initials,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Activity, AdminStats, AdminUser, LoginRequestRow } from "@/lib/types";

export default function AdminDashboard() {
  const { user } = useRequireAuth(["admin"]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [pending, setPending] = useState<AdminUser[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [loginRequests, setLoginRequests] = useState<LoginRequestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [statsData, pendingData, activityData, requestData] = await Promise.all([
        api.get<AdminStats>("/admin/stats"),
        api.get<AdminUser[]>("/admin/users/pending"),
        api.get<Activity[]>("/admin/activity?limit=12"),
        api.get<LoginRequestRow[]>("/login-requests?status=pending"),
      ]);
      setStats(statsData);
      setPending(pendingData);
      setActivity(activityData);
      setLoginRequests(requestData);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the dashboard.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function decide(target: AdminUser, status: "approved" | "revoked") {
    try {
      await api.patch(`/admin/users/${target.id}/access`, {
        access_status: status,
        note: status === "approved" ? "Approved from the dashboard" : "Declined from the dashboard",
      });
      toast(
        status === "approved"
          ? `${target.full_name} now has access`
          : `${target.full_name}'s request was declined`,
        status === "approved" ? "green" : "amber",
      );
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not update access", "rose");
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-5 sm:space-y-6">
      <Hero
        title="Administrator Dashboard"
        body="Access requests, live sessions and the state of the question bank, in one place."
        action={
          <Button variant="secondary" size="sm" loading={refreshing} onClick={() => void load()}>
            Refresh
          </Button>
        }
      />

      {/* A failed load used to leave the skeletons spinning in silence. */}
      {error && (
        <Alert tone="rose" title="Could not load the dashboard">
          {error}
        </Alert>
      )}

      {/* ─── Stats grid ────────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="rounded-[12px] border border-line bg-surface p-5">
              <Skeleton className="mb-3 h-3 w-20" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))
        ) : !stats ? null : (
          <>
            <StatCard
              label="Login Requests"
              value={loginRequests.length}
              tone={loginRequests.length ? "amber" : "neutral"}
              hint={loginRequests.length ? "Candidates waiting" : "All clear"}
              icon={<BellIcon />}
            />
            <StatCard
              label="Pending Approvals"
              value={stats.pending_approvals}
              tone={stats.pending_approvals ? "amber" : "neutral"}
              hint={stats.pending_approvals ? "Examiner accounts" : "Nothing waiting"}
              icon={<UserCheckIcon />}
            />
            <StatCard
              label="Live Sessions"
              value={stats.live_sessions}
              tone={stats.flagged_sessions ? "rose" : "accent"}
              hint={`${stats.flagged_sessions} flagged`}
              icon={<LiveIcon />}
            />
            <StatCard
              label="Question Bank"
              value={stats.questions}
              tone="neutral"
              hint={`${stats.subjects} subjects`}
              icon={<BankIcon />}
            />
            <StatCard
              label="Pending Grading"
              value={stats.pending_grading}
              tone={stats.pending_grading ? "amber" : "neutral"}
              hint="Written answers"
              icon={<GradingIcon />}
            />
          </>
        )}
      </div>

      {/* ─── Login requests banner ────────────────────────── */}
      {loginRequests.length > 0 && (
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[15px] font-semibold text-ink">Candidate Login Requests</h2>
              <p className="mt-0.5 text-[12.5px] text-ink-muted">
                Accounts are active — they need permission to use the platform.
              </p>
            </div>
            <Link href="/dashboard/login-requests">
              <Button variant="secondary" size="sm">Review all</Button>
            </Link>
          </div>
          <ul className="divide-y divide-line">
            {loginRequests.slice(0, 4).map((row) => (
              <li key={row.id} className="flex flex-wrap items-center gap-3 py-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-soft text-[12px] font-bold text-amber-ink">
                  {initials(row.full_name)}
                </div>
                <div className="min-w-0 flex-1 basis-40">
                  <p className="truncate text-[13.5px] font-medium text-ink">{row.full_name}</p>
                  <p className="truncate text-[12px] text-ink-muted">
                    {row.email} · requested {formatDate(row.requested_at, false)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge tone="amber" size="xs">pending</Badge>
                  <Link href="/dashboard/login-requests">
                    <Button size="sm">Decide</Button>
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        {/* ─── Examiner approvals ─────────────────────────── */}
        <Card>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[15px] font-semibold text-ink">Examiner Account Requests</h2>
              <p className="mt-0.5 text-[12.5px] text-ink-muted">
                New examiner accounts are inactive until approved.
              </p>
            </div>
            <Link href="/dashboard/admin/users">
              <Button variant="secondary" size="sm">All users</Button>
            </Link>
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-[10px]" />)}
            </div>
          ) : pending.length === 0 ? (
            <EmptyState
              title="No pending requests"
              body="New examiner registrations will appear here for approval."
              icon={<UserCheckIcon />}
            />
          ) : (
            <ul className="divide-y divide-line">
              {pending.map((person) => (
                <li key={person.id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[12px] font-bold text-accent">
                    {initials(person.full_name)}
                  </div>
                  <div className="min-w-0 flex-1 basis-40">
                    <p className="truncate text-[13.5px] font-medium text-ink">{person.full_name}</p>
                    <p className="truncate text-[12px] text-ink-muted">
                      {person.email} · registered {formatDate(person.created_at, false)}
                    </p>
                  </div>
                  <Badge tone="amber" size="xs">{person.role}</Badge>
                  <div className="flex shrink-0 gap-2">
                    <Button size="sm" variant="success" onClick={() => decide(person, "approved")}>
                      Approve
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => decide(person, "revoked")}>
                      Decline
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ─── Activity feed ───────────────────────────────── */}
        <Card>
          <h2 className="mb-4 text-[15px] font-semibold text-ink">Recent Activity</h2>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-[8px]" />)}
            </div>
          ) : activity.length === 0 ? (
            <EmptyState title="Nothing yet" body="Activity will appear as the platform is used." />
          ) : (
            <ol className="relative space-y-3 pl-4">
              <span className="absolute left-[3px] top-1.5 bottom-1.5 w-px bg-line" />
              {activity.map((item, index) => (
                <li key={index} className="relative">
                  <span
                    className={cx(
                      "absolute -left-4 top-1.5 h-2 w-2 rounded-full border-2 border-surface",
                      item.severity === "critical"
                        ? "bg-rose"
                        : item.severity === "warning"
                          ? "bg-amber"
                          : "bg-accent",
                    )}
                  />
                  <p className="text-[13px] leading-snug text-ink">{item.message}</p>
                  <p className="text-[11.5px] text-ink-muted">{formatDate(item.at)}</p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      {/* ─── Population ──────────────────────────────────── */}
      {stats && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "Candidates", value: stats.candidates, tone: "accent" as const, icon: <CandidateIcon /> },
            { label: "Examiners", value: stats.examiners, tone: "green" as const, icon: <ExaminerIcon /> },
            { label: "Administrators", value: stats.admins, tone: "neutral" as const, icon: <AdminIcon /> },
          ].map((row) => (
            <StatCard key={row.label} label={row.label} value={row.value} tone={row.tone} icon={row.icon} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Inline icons ───────────────────────────────────────────────── */
function BellIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" /></svg>;
}
function UserCheckIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="9" cy="8" r="3.25" /><path d="M3 20a6 6 0 0 1 12 0" /><path d="M16 11l2 2 4-4" /></svg>;
}
function LiveIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="3" /><path d="M6.3 6.3a8 8 0 1 0 11.4 11.4M6.3 17.7A8 8 0 1 1 17.7 6.3" /></svg>;
}
function BankIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 6.5c0-1.4 3.6-2.5 8-2.5s8 1.1 8 2.5-3.6 2.5-8 2.5-8-1.1-8-2.5Z" /><path d="M4 6.5v11c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-11M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5" /></svg>;
}
function GradingIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H15l5 5v9.5a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5Z" /><path d="M8 14.5l2.2 2.2L16 11" /></svg>;
}
function CandidateIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="8.5" r="3.75" /><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" /></svg>;
}
function ExaminerIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M9 13l1.8 1.8L14.5 11" /></svg>;
}
function AdminIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3l7.5 3v5.5c0 4.6-3.1 8.3-7.5 9.5-4.4-1.2-7.5-4.9-7.5-9.5V6Z" /><path d="M9.2 12.2 11.3 14.3 15 10.5" /></svg>;
}
