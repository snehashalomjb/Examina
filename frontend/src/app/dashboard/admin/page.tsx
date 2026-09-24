"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  KPIBanner,
  Skeleton,
  StatCard,
  StatusDot,
  TimelineCard,
  cx,
  formatDate,
  initials,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  Activity,
  AdminStats,
  AdminUser,
  LiveExamRow,
  LoginRequestRow,
  SystemHealth,
} from "@/lib/types";

export default function AdminDashboard() {
  const t = useTranslations("dashboard-detail");
  const ta = useTranslations("adminShell");
  const tc = useTranslations("common");
  const { user } = useRequireAuth(["admin"]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [pending, setPending] = useState<AdminUser[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [loginRequests, setLoginRequests] = useState<LoginRequestRow[]>([]);
  const [liveExams, setLiveExams] = useState<LiveExamRow[]>([]);
  const [alerts, setAlerts] = useState<
    { id: string; alert_type: string; candidate_name: string; exam_title: string; time_ago: string; severity: "rose" | "amber" | "mint" }[]
  >([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [statsData, pendingData, activityData, requestData, liveExamsData, liveDashboard, healthData] =
        await Promise.all([
          api.get<AdminStats>("/admin/stats"),
          api.get<AdminUser[]>("/admin/users/pending"),
          api.get<Activity[]>("/admin/activity?limit=12"),
          api.get<LoginRequestRow[]>("/login-requests?status=pending"),
          api.get<LiveExamRow[]>("/analytics/live-exams"),
          api.get<{ proctoring_alerts: typeof alerts }>("/analytics/live-dashboard"),
          api.get<SystemHealth>("/admin/system-health"),
        ]);
      setStats(statsData);
      setPending(pendingData);
      setActivity(activityData);
      setLoginRequests(requestData);
      setLiveExams(liveExamsData);
      setAlerts(liveDashboard.proctoring_alerts);
      setHealth(healthData);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("could_not_load_dashboard"));
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
          ? ta("toast_access_granted", { name: target.full_name })
          : ta("toast_request_declined", { name: target.full_name }),
        status === "approved" ? "green" : "amber",
      );
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_update_access"), "rose");
    }
  }

  if (!user) return null;

  const pendingTotal = (stats?.pending_approvals ?? 0) + loginRequests.length;
  const systemOperational =
    health && health.database.status === "operational" && health.storage.status !== "unavailable";

  /* Map activity severity to timeline tone */
  const activityTone = (sev: string) =>
    sev === "critical" ? "rose" : sev === "warning" ? "amber" : "accent";

  const activityIcon = (msg: string) => {
    if (msg.toLowerCase().includes("exam")) return "📋";
    if (msg.toLowerCase().includes("user") || msg.toLowerCase().includes("approved")) return "👤";
    if (msg.toLowerCase().includes("flag") || msg.toLowerCase().includes("suspect")) return "🚩";
    if (msg.toLowerCase().includes("result") || msg.toLowerCase().includes("publish")) return "📊";
    return "●";
  };

  return (
    <div className="space-y-6">

      {/* ─── Admin Command Centre Banner ─────────────────────── */}
      <div
        className="relative overflow-hidden rounded-[20px] border p-6 sm:p-8"
        style={{
          background: "linear-gradient(135deg, rgba(220,38,38,0.06) 0%, rgba(79,70,229,0.06) 50%, rgba(245,158,11,0.04) 100%)",
          borderColor: "rgba(220,38,38,0.18)",
          boxShadow: "0 4px 32px -8px rgba(220,38,38,0.10)",
        }}
      >
        <div className="pointer-events-none absolute -right-12 -top-12 h-52 w-52 rounded-full opacity-[0.05]"
          style={{ background: "radial-gradient(circle, #dc2626, transparent 70%)" }} />

        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-rose/20 bg-rose-soft px-3 py-1">
              <span className="h-2 w-2 rounded-full bg-rose animate-pulse" />
              <span className="text-[11px] font-bold tracking-wide uppercase text-rose-ink">{ta("admin_control_centre_badge")}</span>
            </div>
            <h1 className="text-[22px] font-extrabold tracking-tight text-ink sm:text-[26px]">
              {t("admin_control_center")}
            </h1>
            <p className="mt-1.5 text-[13.5px] text-ink-muted max-w-lg">{t("admin_dashboard_subtitle")}</p>

            {/* System Health strip */}
            {health && (
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <StatusDot
                  tone={health.database.status === "operational" ? "green" : "rose"}
                  label={ta("database")}
                />
                <StatusDot
                  tone={health.storage.status === "operational" ? "green" : health.storage.status === "unavailable" ? "rose" : "amber"}
                  label={ta("storage")}
                />
                <StatusDot
                  tone={liveExams.length > 0 ? "green" : "neutral"}
                  label={ta("live_exams_count", { count: liveExams.length })}
                />
                <StatusDot
                  tone={pendingTotal > 0 ? "amber" : "green"}
                  label={pendingTotal > 0 ? ta("pending_count", { count: pendingTotal }) : ta("all_approved")}
                />
              </div>
            )}
          </div>

          <div className="flex shrink-0 flex-wrap items-start gap-2">
            <span className={cx(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11.5px] font-semibold",
              systemOperational
                ? "border-green-border bg-green-soft text-green-ink"
                : "border-amber/30 bg-amber-soft text-amber-ink",
            )}>
              <span className={cx("h-1.5 w-1.5 rounded-full", systemOperational ? "bg-green" : "bg-amber animate-pulse")} />
              {systemOperational ? t("system_operational") : t("system_degraded")}
            </span>
            <Button variant="secondary" size="sm" loading={refreshing} onClick={() => void load()}>
              ↻ {t("refresh")}
            </Button>
          </div>
        </div>
      </div>

      {error && <Alert tone="rose" title={t("could_not_load_dashboard")}>{error}</Alert>}

      {/* ─── KPI Banner ──────────────────────────────────────── */}
      {loading || !stats ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="rounded-[14px] border border-line bg-surface p-4">
              <Skeleton className="mb-2 h-2.5 w-14" />
              <Skeleton className="h-6 w-10" />
            </div>
          ))}
        </div>
      ) : (
        <KPIBanner items={[
          { label: t("total_candidates"),             value: stats.candidates,         tone: "accent" },
          { label: t("total_examiners"),              value: stats.examiners,          tone: "green" },
          { label: t("active_exams"),                 value: stats.live_exams,         tone: stats.live_exams > 0 ? "mint" : "neutral",
            trend: stats.live_exams > 0 ? { value: ta("trend_live_now"), up: true } : undefined },
          { label: t("completed_exams"),              value: stats.completed_exams,    tone: "neutral" },
          { label: t("active_proctoring_sessions"),   value: stats.live_sessions,      tone: "purple" },
          { label: t("flagged_sessions"),             value: stats.flagged_sessions,   tone: stats.flagged_sessions > 0 ? "rose" : "neutral",
            trend: stats.flagged_sessions > 0 ? { value: ta("trend_needs_review"), up: false } : undefined },
          { label: t("question_bank"),                value: stats.questions,          tone: "neutral" },
          { label: t("pending_requests"),             value: pendingTotal,             tone: pendingTotal > 0 ? "amber" : "neutral",
            trend: pendingTotal > 0 ? { value: ta("trend_action_needed"), up: false } : undefined },
        ]} />
      )}

      {/* ─── Live Exams + Alerts ─────────────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">

        {/* Live Examinations */}
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] font-bold text-ink">{t("live_examinations")}</h2>
              {liveExams.length > 0 && (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose text-[10px] font-bold text-white animate-pulse">
                  {liveExams.length}
                </span>
              )}
            </div>
            <Link href="/dashboard/live">
              <Button variant="secondary" size="sm">{t("open_live_console")}</Button>
            </Link>
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14 rounded-[10px]" />)}
            </div>
          ) : liveExams.length === 0 ? (
            <EmptyState title={t("no_active_examinations")} body={t("no_active_examinations_body")} />
          ) : (
            <div className="space-y-2.5">
              {liveExams.map((row) => (
                <div key={row.exam_id} className="rounded-[12px] border border-line bg-gradient-to-r from-rose/[0.03] to-transparent p-3.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="h-2 w-2 shrink-0 rounded-full bg-rose animate-pulse" />
                        <p className="truncate text-[13px] font-semibold text-ink">{row.exam_title}</p>
                      </div>
                      <p className="mt-0.5 truncate text-[11.5px] text-ink-muted pl-4">
                        {ta("by_name", { name: row.examiner_name })}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-[11.5px] text-ink-muted">
                      <span className="text-center">
                        <span className="block font-bold text-ink">{row.active_count}/{row.candidate_count}</span>
                        <span>{ta("label_active")}</span>
                      </span>
                      {row.flagged_count > 0 && (
                        <span className="text-center">
                          <span className="block font-bold text-rose">{row.flagged_count}</span>
                          <span className="text-rose">{ta("label_flagged")}</span>
                        </span>
                      )}
                      <span className="font-mono text-[12px]">{row.time_remaining_str}</span>
                    </div>
                    <Link href="/dashboard/live">
                      <Button size="sm" variant="secondary">{t("monitor")}</Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Proctoring Alerts */}
        <Card>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-[15px] font-bold text-ink">{t("proctoring_alerts")}</h2>
            <Link href="/dashboard/proctoring">
              <Button variant="secondary" size="sm">{t("all_alerts")}</Button>
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 rounded-[10px]" />)}
            </div>
          ) : alerts.length === 0 ? (
            <EmptyState title={t("no_proctoring_alerts")} body={t("no_proctoring_alerts_body")} />
          ) : (
            <ul className="space-y-2">
              {alerts.slice(0, 5).map((alert) => (
                <li key={alert.id} className={cx(
                  "rounded-[11px] border p-3",
                  alert.severity === "rose"
                    ? "border-rose/25 bg-rose-soft/50"
                    : "border-amber/25 bg-amber-soft/50",
                )}>
                  <div className="flex items-center gap-2">
                    <span className="text-[13px]">{alert.severity === "rose" ? "🔴" : "🟠"}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12.5px] font-semibold text-ink">{alert.candidate_name}</p>
                      <p className="truncate text-[11.5px] text-ink-muted">{alert.alert_type} · {alert.exam_title}</p>
                    </div>
                    <span className="shrink-0 text-[10.5px] text-ink-muted">{alert.time_ago}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* ─── Approval Queues (login requests + examiner accounts) */}
      {(loginRequests.length > 0 || pending.length > 0) && (
        <div className="grid gap-5 lg:grid-cols-2">

          {/* Candidate Login Requests */}
          {loginRequests.length > 0 && (
            <Card className="border-amber/20">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-[15px] font-bold text-ink">{t("candidate_login_requests")}</h2>
                    <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-amber px-1 text-[10px] font-bold text-white">
                      {loginRequests.length}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[12px] text-ink-muted">{t("candidate_login_requests_body")}</p>
                </div>
                <Link href="/dashboard/login-requests">
                  <Button variant="secondary" size="sm">{t("review_all")}</Button>
                </Link>
              </div>
              <ul className="divide-y divide-line">
                {loginRequests.slice(0, 4).map((row) => (
                  <li key={row.id} className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-soft text-[12px] font-bold text-amber-ink border border-amber/20">
                      {initials(row.full_name)}
                    </div>
                    <div className="min-w-0 flex-1 basis-40">
                      <p className="truncate text-[13px] font-semibold text-ink">{row.full_name}</p>
                      <p className="truncate text-[11.5px] text-ink-muted">
                        {row.email} · {formatDate(row.requested_at, false)}
                      </p>
                    </div>
                    <Link href="/dashboard/login-requests">
                      <Button size="sm">{t("decide")}</Button>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Examiner Account Requests */}
          {pending.length > 0 && (
            <Card>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-[15px] font-bold text-ink">{t("examiner_account_requests")}</h2>
                    <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-bold text-white">
                      {pending.length}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[12px] text-ink-muted">{t("examiner_account_requests_body")}</p>
                </div>
                <Link href="/dashboard/admin/users">
                  <Button variant="secondary" size="sm">{t("all_users")}</Button>
                </Link>
              </div>
              <ul className="divide-y divide-line">
                {pending.map((person) => (
                  <li key={person.id} className="flex flex-wrap items-center gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-[12px] font-bold text-accent border border-accent-border">
                      {initials(person.full_name)}
                    </div>
                    <div className="min-w-0 flex-1 basis-40">
                      <p className="truncate text-[13px] font-semibold text-ink">{person.full_name}</p>
                      <p className="truncate text-[11.5px] text-ink-muted">
                        {person.email} · {formatDate(person.created_at, false)}
                      </p>
                    </div>
                    <Badge tone="amber" size="xs">{tc(`role_${person.role}`)}</Badge>
                    <div className="flex shrink-0 gap-2">
                      <Button size="sm" variant="success" onClick={() => decide(person, "approved")}>
                        {t("approve")}
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => decide(person, "revoked")}>
                        {t("decline")}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}

      {/* ─── Activity Feed + Quick Actions ───────────────────── */}
      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">

        {/* Timeline activity */}
        <Card>
          <h2 className="mb-4 text-[15px] font-bold text-ink">{t("recent_activity")}</h2>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded-[8px]" />)}
            </div>
          ) : activity.length === 0 ? (
            <EmptyState title={t("nothing_yet")} body={t("nothing_yet_body")} />
          ) : (
            <div className="space-y-0">
              {activity.slice(0, 8).map((item, idx) => (
                <TimelineCard
                  key={idx}
                  icon={activityIcon(item.message)}
                  title={item.message}
                  time={formatDate(item.at)}
                  tone={activityTone(item.severity)}
                  last={idx === Math.min(activity.length, 8) - 1}
                />
              ))}
            </div>
          )}
        </Card>

        {/* Quick Actions */}
        <div className="space-y-4">
          <Card>
            <h2 className="mb-4 text-[14px] font-bold uppercase tracking-widest text-ink-muted">{t("quick_actions")}</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {[
                { href: "/dashboard/exams/create",       label: t("create_exam"),       icon: "📋", color: "#4f46e5" },
                { href: "/dashboard/admin/users",        label: t("manage_users"),      icon: "👤", color: "#0f9b8e" },
                { href: "/dashboard/questions",          label: t("question_bank"),     icon: "🗂️", color: "#0ea5e9" },
                { href: "/dashboard/live",               label: t("live_proctoring"),   icon: "🔴", color: "#dc2626" },
                { href: "/dashboard/admin/reports",      label: t("view_reports"),      icon: "📊", color: "#7c3aed" },
                { href: "/dashboard/admin/system-health",label: ta("nav_system_health"), icon: "🛡️", color: "#16a34a" },
              ].map((action) => (
                <Link key={action.href} href={action.href}>
                  <button className="group w-full rounded-[12px] border border-line bg-surface p-3.5 text-left transition-all duration-200 hover:border-accent/25 hover:bg-accent-soft/20 hover:-translate-y-[1px] hover:shadow-sm">
                    <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-[9px] text-[16px] transition-transform group-hover:scale-110"
                      style={{ background: `${action.color}15`, border: `1px solid ${action.color}30` }}>
                      {action.icon}
                    </div>
                    <p className="text-[12px] font-semibold text-ink group-hover:text-accent transition-colors leading-tight">{action.label}</p>
                  </button>
                </Link>
              ))}
            </div>
          </Card>

          {/* System Health Detail */}
          {health && (
            <Card>
              <h2 className="mb-3 text-[14px] font-bold uppercase tracking-widest text-ink-muted">{ta("nav_system_health")}</h2>
              <div className="space-y-2.5">
                {[
                  { key: "database", label: ta("database"), status: health.database.status, detail: health.database.detail ?? undefined },
                  { key: "storage", label: ta("storage"), status: health.storage.status,  detail: health.storage.detail ?? undefined },
                  { key: "api", label: ta("api"), status: health.api.status,      detail: health.api.detail ?? undefined },
                ].map((svc) => (
                  <div key={svc.key} className="flex items-center justify-between rounded-[9px] bg-sunken px-3 py-2">
                    <StatusDot
                      tone={svc.status === "operational" ? "green" : svc.status === "degraded" ? "amber" : "rose"}
                      label={svc.label}
                    />
                    <span className="text-[11px] text-ink-muted font-medium">
                      {svc.detail ?? (svc.status === "operational" ? ta("health_ok") : ta.has(`health_${svc.status}`) ? ta(`health_${svc.status}`) : svc.status)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Inline Icons ───────────────────────────────────────────────── */
function BellIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" /></svg>;
}
function UserCheckIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="9" cy="8" r="3.25" /><path d="M3 20a6 6 0 0 1 12 0" /><path d="M16 11l2 2 4-4" /></svg>;
}
function LiveIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="3" /><path d="M6.3 6.3a8 8 0 1 0 11.4 11.4M6.3 17.7A8 8 0 1 1 17.7 6.3" /></svg>;
}
function CheckIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 12.5l5 5L20 6" /></svg>;
}
function CameraIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><rect x="2" y="6" width="15" height="12" rx="2" /><path d="M17 10l5-3v10l-5-3" /></svg>;
}
function FlagIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 21V4M5 4h13l-3 4 3 4H5" /></svg>;
}
function BankIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 6.5c0-1.4 3.6-2.5 8-2.5s8 1.1 8 2.5-3.6 2.5-8 2.5-8-1.1-8-2.5Z" /><path d="M4 6.5v11c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-11M4 12c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5" /></svg>;
}
function CandidateIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="8.5" r="3.75" /><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" /></svg>;
}
function ExaminerIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M9 13l1.8 1.8L14.5 11" /></svg>;
}
