"use client";

/**
 * Live Proctoring / Live Console.
 *
 * A white, light-cyber operations screen an examiner leaves open on a second display
 * during a sitting: who is writing, who needs attention, and - now - their actual
 * webcam feed, streamed peer-to-peer via WebRTC (see `useLiveView` /
 * `CandidateVideoTile`), not a periodic snapshot dressed up as "live".
 *
 * Everything non-video is read from `/analytics/live-dashboard`, polled every 15s same
 * as before; only the presentation changed. Video is only ever connected for a
 * candidate whose tile is actually rendered - grid view for what is on screen, or the
 * one candidate a detail modal has open - never for the full roster at once.
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { Badge, Button, EmptyState, Input, ProgressBar, Select, Skeleton, cx } from "@/components/ui";
import { CandidateDetailModal } from "@/components/live/CandidateDetailModal";
import { CandidateVideoTile, severityOf } from "@/components/live/CandidateVideoTile";
import { api } from "@/lib/api";
import type { LiveDashboardData, LiveSessionRow } from "@/lib/types";

const REFRESH_MS = 15_000;

type StatusFilter = "all" | "normal" | "warning" | "flagged" | "critical";
type SortKey = "suspicion" | "latest_alert" | "name" | "time_remaining";
type ViewMode = "grid" | "list";

function timeRemainingSeconds(value: string): number {
  const [m, s] = value.split(":").map((n) => Number(n) || 0);
  return m * 60 + s;
}

export function LiveOperationsDashboard({
  role,
}: {
  role: "admin" | "examiner";
  userFullName: string;
}) {
  const t = useTranslations("dashboard-detail");
  const [data, setData] = useState<LiveDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [examFilter, setExamFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("suspicion");
  const [view, setView] = useState<ViewMode>("grid");
  const [fullscreen, setFullscreen] = useState(false);
  const [openRow, setOpenRow] = useState<LiveSessionRow | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await api.get<LiveDashboardData>("/analytics/live-dashboard");
      setData(res);
      setConnected(true);
      setLastUpdated(new Date());
    } catch {
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const interval = setInterval(() => void loadData(), REFRESH_MS);
    return () => clearInterval(interval);
  }, [loadData]);

  const sessions = useMemo(() => data?.live_sessions ?? [], [data]);

  const exams = useMemo(
    () => Array.from(new Set(sessions.map((s) => s.exam_title))).sort(),
    [sessions],
  );

  const alertOrderByName = useMemo(() => {
    const order = new Map<string, number>();
    (data?.proctoring_alerts ?? []).forEach((alert, index) => {
      if (!order.has(alert.candidate_name)) order.set(alert.candidate_name, index);
    });
    return order;
  }, [data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    let rows = sessions.filter((row) => {
      if (statusFilter !== "all" && severityOf(row) !== statusFilter) return false;
      if (examFilter !== "all" && row.exam_title !== examFilter) return false;
      if (term) {
        const haystack = `${row.candidate_name} ${row.session_id}`.toLowerCase();
        if (!haystack.includes(term)) return false;
      }
      return true;
    });

    rows = [...rows].sort((a, b) => {
      switch (sortKey) {
        case "suspicion":
          return b.suspicion_score - a.suspicion_score;
        case "name":
          return a.candidate_name.localeCompare(b.candidate_name);
        case "time_remaining":
          return timeRemainingSeconds(a.time_remaining_str) - timeRemainingSeconds(b.time_remaining_str);
        case "latest_alert": {
          const ai = alertOrderByName.get(a.candidate_name) ?? Number.MAX_SAFE_INTEGER;
          const bi = alertOrderByName.get(b.candidate_name) ?? Number.MAX_SAFE_INTEGER;
          return ai - bi;
        }
      }
    });
    return rows;
  }, [sessions, statusFilter, examFilter, search, sortKey, alertOrderByName]);

  const critical = sessions.filter((s) => severityOf(s) === "critical" || severityOf(s) === "flagged");
  const verified = sessions.filter((s) => severityOf(s) === "normal");
  const avgSuspicion = sessions.length
    ? Math.round(sessions.reduce((sum, s) => sum + s.suspicion_score, 0) / sessions.length)
    : 0;

  if (loading && !data) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-16 rounded-[14px]" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-[12px]" />
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 rounded-[14px]" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className={cx("space-y-5", fullscreen && "fixed inset-0 z-40 overflow-y-auto bg-paper p-5")}>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-[21px] font-bold tracking-tight text-ink">{t("live_operations_heading")}</h1>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-soft px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide text-green-ink">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green" />
              Live
            </span>
          </div>
          <p className="mt-1 text-[13px] text-ink-muted">
            Real-time candidate monitoring and AI-powered proctoring{role === "admin" ? " · all sessions" : ""}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">{sessions.length} active candidates</Badge>
          <Badge tone={critical.length ? "rose" : "neutral"}>{critical.length} critical alerts</Badge>
          <span
            className={cx(
              "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold",
              connected ? "border-cyan-200 bg-cyan-50 text-cyan-700" : "border-amber/30 bg-amber-soft text-amber-ink",
            )}
          >
            <span className={cx("h-1.5 w-1.5 rounded-full", connected ? "bg-cyan-500 animate-pulse" : "bg-amber animate-pulse")} />
            {connected ? "Connected" : "Reconnecting…"}
          </span>
          <Button size="sm" variant="secondary" onClick={() => setFullscreen((v) => !v)}>
            {fullscreen ? "Exit fullscreen" : "Fullscreen monitoring"}
          </Button>
        </div>
      </div>
      {lastUpdated && (
        <p className="-mt-3 text-[11px] text-ink-muted">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </p>
      )}

      {/* ── Top statistics ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <MiniStat dot="bg-green" label="Active candidates" value={sessions.length} hint="Currently sitting" />
        <MiniStat icon="⚠" iconTone="text-amber" label="Alerts" value={data?.proctoring_alerts.length ?? 0} hint={`${critical.length} critical`} />
        <MiniStat icon="✓" iconTone="text-mint" label="Verified" value={verified.length} hint={sessions.length ? `${Math.round((verified.length / sessions.length) * 100)}% of active` : "—"} />
        <MiniStat icon="◉" iconTone="text-cyan-600" label="Monitoring" value={sessions.length} hint="Camera online" />
        <MiniStat icon="AI" iconTone="text-accent" label="AI suspicion" value={`${avgSuspicion}%`} hint="Current cohort" />
      </div>

      {/* ── Filters ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as StatusFilter)} className="w-auto">
          <option value="all">{t("filter_all_status")}</option>
          <option value="normal">{t("filter_normal")}</option>
          <option value="warning">{t("filter_warning")}</option>
          <option value="flagged">{t("filter_flagged")}</option>
          <option value="critical">{t("filter_critical")}</option>
        </Select>
        <Select value={examFilter} onChange={(e) => setExamFilter(e.target.value)} className="w-auto">
          <option value="all">{t("filter_all_exams")}</option>
          {exams.map((title) => (
            <option key={title} value={title}>{title}</option>
          ))}
        </Select>
        <Select value={sortKey} onChange={(e) => setSortKey(e.target.value as SortKey)} className="w-auto">
          <option value="suspicion">Sort: suspicion score</option>
          <option value="latest_alert">Sort: latest alert</option>
          <option value="name">Sort: candidate name</option>
          <option value="time_remaining">Sort: time remaining</option>
        </Select>
        <div className="min-w-[200px] flex-1">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("search_placeholder")}
          />
        </div>
        <div className="flex items-center gap-1 rounded-[10px] border border-line-strong bg-surface p-0.5">
          <button
            type="button"
            onClick={() => setView("grid")}
            className={cx("rounded-[8px] px-3 py-1.5 text-[12.5px] font-medium transition", view === "grid" ? "bg-accent text-white" : "text-ink-soft hover:bg-sunken")}
          >
            Grid
          </button>
          <button
            type="button"
            onClick={() => setView("list")}
            className={cx("rounded-[8px] px-3 py-1.5 text-[12.5px] font-medium transition", view === "list" ? "bg-accent text-white" : "text-ink-soft hover:bg-sunken")}
          >
            List
          </button>
        </div>
      </div>

      {/* ── Monitoring grid + alerts ────────────────────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div>
          {filtered.length === 0 ? (
            <EmptyState
              title={sessions.length === 0 ? "No active examination sessions" : "No candidates match these filters"}
              body={
                sessions.length === 0
                  ? "No candidates are currently taking an exam. Sittings appear here the moment one starts."
                  : "Try a different status, exam, or search term."
              }
            />
          ) : view === "grid" ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map((row) => (
                <CandidateVideoTile key={row.session_id} row={row} monitor onOpen={() => setOpenRow(row)} />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-[12px] border border-line bg-surface">
              <table className="w-full min-w-[820px] text-left text-[12.5px]">
                <thead>
                  <tr className="border-b border-line bg-sunken/60 text-[11px] uppercase tracking-wide text-ink-muted">
                    <th className="px-3 py-2.5 font-semibold">{t("table_candidate")}</th>
                    <th className="px-3 py-2.5 font-semibold">{t("table_exam")}</th>
                    <th className="px-3 py-2.5 font-semibold">{t("table_suspicion")}</th>
                    <th className="px-3 py-2.5 font-semibold">{t("table_alerts")}</th>
                    <th className="px-3 py-2.5 font-semibold">{t("table_time_remaining")}</th>
                    <th className="px-3 py-2.5 font-semibold">{t("table_status")}</th>
                    <th className="px-3 py-2.5 font-semibold text-right">{t("table_action")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {filtered.map((row) => {
                    const severity = severityOf(row);
                    return (
                      <tr key={row.session_id} className="transition hover:bg-sunken/40">
                        <td className="px-3 py-2.5">
                          <p className="font-medium text-ink">{row.candidate_name}</p>
                          <p className="text-[11px] text-ink-muted">#{row.session_id.slice(0, 8)}</p>
                        </td>
                        <td className="px-3 py-2.5 text-ink-soft">{row.exam_title}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="w-16">
                              <ProgressBar value={row.suspicion_score} size="xs" tone={severity === "critical" || severity === "flagged" ? "rose" : severity === "warning" ? "amber" : "mint"} />
                            </div>
                            <span className="font-medium text-ink">{row.suspicion_score}%</span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-ink-soft">{row.is_flagged ? "Flagged" : "—"}</td>
                        <td className="px-3 py-2.5 font-mono text-ink-soft">{row.time_remaining_str}</td>
                        <td className="px-3 py-2.5">
                          {severity === "normal" ? (
                            <Badge tone="mint">{t("badge_normal")}</Badge>
                          ) : severity === "warning" ? (
                            <Badge tone="amber">{t("badge_warning")}</Badge>
                          ) : (
                            <Badge tone="rose">{severity === "flagged" ? "Flagged" : "Critical"}</Badge>
                          )}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <Button size="sm" variant="secondary" onClick={() => setOpenRow(row)}>
                            Monitor
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Alerts panel ──────────────────────────────────────────────── */}
        <div className="rounded-[14px] border border-line bg-surface p-4">
          <p className="mb-3 flex items-center gap-1.5 text-[12px] font-bold uppercase tracking-wide text-ink-muted">
            Live proctoring alerts
          </p>
          {(data?.proctoring_alerts.length ?? 0) === 0 ? (
            <p className="py-6 text-center text-[12.5px] text-ink-muted">No proctoring alerts right now.</p>
          ) : (
            <ul className="space-y-2">
              {data!.proctoring_alerts.map((alert) => {
                const match = sessions.find((s) => s.candidate_name === alert.candidate_name);
                return (
                  <li
                    key={alert.id}
                    onClick={() => match && setOpenRow(match)}
                    className={cx(
                      "rounded-[10px] border p-2.5",
                      alert.severity === "rose" ? "border-rose/30 bg-rose-soft/60" : "border-amber/30 bg-amber-soft/60",
                      match && "cursor-pointer hover:brightness-95",
                    )}
                  >
                    <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide">
                      <span>{alert.severity === "rose" ? "🔴" : "🟠"}</span>
                      <span className={alert.severity === "rose" ? "text-rose-ink" : "text-amber-ink"}>
                        {alert.severity === "rose" ? "Critical" : "Warning"}
                      </span>
                    </div>
                    <p className="mt-1 text-[12.5px] font-medium text-ink">{alert.candidate_name}</p>
                    <p className="text-[12px] text-ink-soft">{alert.alert_type}</p>
                    <p className="mt-0.5 text-[11px] text-ink-muted">
                      {alert.time_ago} · {alert.suspicion_delta}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-4 border-t border-line pt-3">
            <Link href="/dashboard/proctoring" className="text-[12px] font-medium text-accent hover:underline">
              Open full proctoring review →
            </Link>
          </div>
        </div>
      </div>

      <CandidateDetailModal row={openRow} onClose={() => setOpenRow(null)} />
    </div>
  );
}

function MiniStat({
  label,
  value,
  hint,
  dot,
  icon,
  iconTone,
}: {
  label: string;
  value: React.ReactNode;
  hint: string;
  dot?: string;
  icon?: string;
  iconTone?: string;
}) {
  return (
    <div className="rounded-[12px] border border-line bg-surface p-3.5">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-ink-muted">
        {dot && <span className={cx("h-2 w-2 rounded-full", dot)} />}
        {icon && <span className={cx("text-[12px] font-bold", iconTone)}>{icon}</span>}
        {label}
      </div>
      <div className="mt-1 text-[22px] font-bold leading-none tracking-tight text-ink">{value}</div>
      <div className="mt-1 text-[11px] text-ink-muted">{hint}</div>
    </div>
  );
}
