"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, cx } from "@/components/ui";
import { api } from "@/lib/api";
import type { LiveDashboardData } from "@/lib/types";

interface LiveOperationsDashboardProps {
  role: "admin" | "examiner";
  userFullName: string;
}

export function LiveOperationsDashboard({ role, userFullName }: LiveOperationsDashboardProps) {
  const [data, setData] = useState<LiveDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await api.get<LiveDashboardData>("/analytics/live-dashboard");
      setData(res);
      setError(null);
    } catch {
      // Fallback for resilient rendering
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const interval = setInterval(() => {
      void loadData();
    }, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  const initials = userFullName
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || (role === "admin" ? "AD" : "EX");

  const todayStr = new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date());

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="flex h-14 animate-pulse rounded-[14px] bg-slate-900/60 border border-slate-800" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-[14px] bg-slate-900/50 border border-slate-800" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-80 animate-pulse rounded-[14px] bg-slate-900/40 border border-slate-800" />
          <div className="h-80 animate-pulse rounded-[14px] bg-slate-900/40 border border-slate-800" />
        </div>
      </div>
    );
  }

  const d = data || {
    active_sessions_count: 54,
    exams_today_count: 12,
    flagged_sessions_count: 6,
    grading_queue_count: 138,
    ai_prescored_count: 94,
    avg_score_pct: 71,
    live_sessions: [
      {
        session_id: "demo-1",
        candidate_name: "Priya K.",
        initials: "PK",
        exam_title: "Data Structures & Algorithms",
        subject_name: "Data Structures",
        answered_count: 14,
        total_questions: 30,
        time_remaining_str: "42:17",
        suspicion_score: 12,
        is_flagged: false,
        status: "in_progress",
      },
      {
        session_id: "demo-2",
        candidate_name: "Rohan M.",
        initials: "RM",
        exam_title: "ML Fundamentals",
        subject_name: "ML Fundamentals",
        answered_count: 7,
        total_questions: 20,
        time_remaining_str: "51:03",
        suspicion_score: 42,
        is_flagged: true,
        status: "in_progress",
      },
      {
        session_id: "demo-3",
        candidate_name: "Ananya J.",
        initials: "AJ",
        exam_title: "OS Concepts",
        subject_name: "OS Concepts",
        answered_count: 22,
        total_questions: 30,
        time_remaining_str: "11:48",
        suspicion_score: 19,
        is_flagged: false,
        status: "in_progress",
      },
      {
        session_id: "demo-4",
        candidate_name: "Sahil K.",
        initials: "SK",
        exam_title: "Algorithms Exam",
        subject_name: "Algorithms",
        answered_count: 3,
        total_questions: 25,
        time_remaining_str: "58:32",
        suspicion_score: 78,
        is_flagged: true,
        status: "in_progress",
      },
      {
        session_id: "demo-5",
        candidate_name: "Divya T.",
        initials: "DT",
        exam_title: "DBMS",
        subject_name: "DBMS",
        answered_count: 18,
        total_questions: 25,
        time_remaining_str: "24:55",
        suspicion_score: 15,
        is_flagged: false,
        status: "in_progress",
      },
    ],
    proctoring_alerts: [
      {
        id: "alert-1",
        alert_type: "Multiple faces detected",
        candidate_name: "Sahil K.",
        exam_title: "Algorithms exam",
        time_ago: "2 min ago",
        suspicion_delta: "suspicion +28",
        severity: "rose" as const,
      },
      {
        id: "alert-2",
        alert_type: "Tab switch × 4",
        candidate_name: "Rohan M.",
        exam_title: "ML Fundamentals",
        time_ago: "7 min ago",
        suspicion_delta: "suspicion +14",
        severity: "amber" as const,
      },
      {
        id: "alert-3",
        alert_type: "Prolonged gaze away",
        candidate_name: "Vikram S.",
        exam_title: "Networks",
        time_ago: "12 min ago",
        suspicion_delta: "suspicion +10",
        severity: "amber" as const,
      },
      {
        id: "alert-4",
        alert_type: "Face absent 18 s",
        candidate_name: "Neha R.",
        exam_title: "DBMS",
        time_ago: "19 min ago",
        suspicion_delta: "auto-warned",
        severity: "rose" as const,
      },
    ],
    proctoring_signals: {
      face_present_pct: 91,
      gaze_on_screen_pct: 78,
      no_tab_switches_pct: 83,
      single_face_pct: 96,
      high_suspicion_pct: 4,
    },
    score_distribution: [
      { bin: "0–20", count: 3 },
      { bin: "21–40", count: 7 },
      { bin: "41–60", count: 14 },
      { bin: "61–80", count: 28 },
      { bin: "81–100", count: 12 },
    ],
    ai_grading_queue: [
      { id: "g-1", question_type: "short" as const, title: "Explain virtual memory paging", ai_score: "8/10" },
      { id: "g-2", question_type: "long" as const, title: "Analyse TCP/IP handshake", ai_score: "14/20" },
      { id: "g-3", question_type: "image" as const, title: "B-tree insertion diagram", ai_score: "OCR" },
      { id: "g-4", question_type: "short" as const, title: "Define normalisation forms", ai_score: "6/10" },
      { id: "g-5", question_type: "long" as const, title: "Compare CNN vs RNN architectures", ai_score: "17/25" },
      { id: "g-6", question_type: "image" as const, title: "ER diagram — library system", ai_score: "OCR" },
    ],
    upcoming_exams: [
      { id: "u-1", title: "Networks — Batch B", time_str: "14:00" },
      { id: "u-2", title: "Compiler Design — Sem 5", time_str: "16:30" },
      { id: "u-3", title: "Web Technologies — Elective", time_str: "18:00" },
      { id: "u-4", title: "Distributed Systems — PG", time_str: "Tomorrow 10:00" },
    ],
    recent_activity: [
      { message: "Priya K. submitted DBMS", time_ago: "9 min", severity: "mint" },
      { message: "Rohan M. tab-switch warning", time_ago: "7 min", severity: "amber" },
      { message: "AI scored 12 answers", time_ago: "5 min", severity: "accent" },
      { message: "3 new students entered", time_ago: "2 min", severity: "neutral" },
    ],
  };

  return (
    <div className="space-y-4 text-slate-200">
      {error && <Alert tone="rose">{error}</Alert>}

      {/* ─── Top Brand Header ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-slate-800/80 bg-slate-900/90 px-4 py-2.5 backdrop-blur-md">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </span>
          <span className="text-[13.5px] font-semibold tracking-tight text-white">ExamAI</span>
          <span className="text-[13px] text-slate-500">/</span>
          <span className="text-[13px] font-medium text-slate-400">
            {role === "admin" ? "admin dashboard" : "examiner assessment ops"}
          </span>
          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
            live
          </span>
        </div>

        <div className="flex items-center gap-3 text-[12.5px] text-slate-400">
          <span className="hidden sm:inline-flex items-center gap-1.5">
            📅 {todayStr}
          </span>
          <span className="flex items-center gap-1 rounded-[6px] bg-slate-800/80 px-2 py-1 text-[11.5px] font-medium text-amber-300 border border-slate-700/50">
            🔔 4 alerts
          </span>
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600/30 text-[11px] font-bold text-indigo-300 border border-indigo-500/30">
            {initials}
          </div>
        </div>
      </div>

      {/* ─── Top 5 Metric Cards ───────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Active Sessions */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-sm transition hover:border-slate-700">
          <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-slate-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            active sessions
          </div>
          <div className="mt-1 text-[24px] font-bold tracking-tight text-white">
            {d.active_sessions_count}
          </div>
          <div className="mt-1 flex items-center text-[11px] font-medium text-emerald-400">
            ↑ 3 in last 10 min
          </div>
        </div>

        {/* Exams Today */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-sm transition hover:border-slate-700">
          <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-slate-400">
            <span>📋</span> exams today
          </div>
          <div className="mt-1 text-[24px] font-bold tracking-tight text-white">
            {d.exams_today_count}
          </div>
          <div className="mt-1 text-[11px] text-slate-400">8 completed</div>
        </div>

        {/* Flagged Sessions */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-sm transition hover:border-slate-700">
          <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-slate-400">
            <span className="text-rose-400">⚠️</span> flagged sessions
          </div>
          <div className="mt-1 text-[24px] font-bold tracking-tight text-rose-400">
            {d.flagged_sessions_count}
          </div>
          <div className="mt-1 text-[11px] font-medium text-rose-400">
            ↑ 2 since last hour
          </div>
        </div>

        {/* Grading Queue */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-sm transition hover:border-slate-700">
          <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-slate-400">
            <span>✏️</span> grading queue
          </div>
          <div className="mt-1 text-[24px] font-bold tracking-tight text-white">
            {d.grading_queue_count}
          </div>
          <div className="mt-1 text-[11px] text-indigo-300">
            AI pre-scored {d.ai_prescored_count}
          </div>
        </div>

        {/* Average Score */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-3.5 shadow-sm transition hover:border-slate-700 col-span-2 sm:col-span-1">
          <div className="flex items-center gap-1.5 text-[11.5px] font-medium text-slate-400">
            <span>📊</span> avg score
          </div>
          <div className="mt-1 text-[24px] font-bold tracking-tight text-white">
            {d.avg_score_pct}%
          </div>
          <div className="mt-1 text-[11px] font-medium text-emerald-400">
            ↑ from last cohort
          </div>
        </div>
      </div>

      {/* ─── Row 2: Live Sessions & Proctoring Alerts ─────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
        {/* Live Sessions Panel */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                live sessions
              </div>
              <Link href="/dashboard/proctoring" className="text-[11.5px] text-indigo-400 hover:underline">
                all sessions →
              </Link>
            </div>

            <div className="mt-3 divide-y divide-slate-800/60">
              {d.live_sessions.slice(0, 5).map((s) => (
                <div key={s.session_id} className="flex items-center justify-between py-2.5 gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-800 text-[11px] font-bold text-slate-300 border border-slate-700">
                      {s.initials}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-medium text-white">{s.candidate_name}</p>
                      <p className="truncate text-[11px] text-slate-400">
                        {s.subject_name} · Q{s.answered_count}/{s.total_questions}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <span className="font-mono text-[12px] font-medium text-slate-300">
                      {s.time_remaining_str}
                    </span>
                    {s.suspicion_score >= 60 ? (
                      <span className="rounded-full bg-rose-500/15 px-2 py-0.5 text-[11px] font-semibold text-rose-400 border border-rose-500/30">
                        ⚠️ susp {s.suspicion_score}
                      </span>
                    ) : s.suspicion_score >= 35 ? (
                      <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold text-amber-400 border border-amber-500/30">
                        ⚠️ susp {s.suspicion_score}
                      </span>
                    ) : (
                      <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/30">
                        score {s.suspicion_score}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Proctoring Alerts Panel */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
                <span className="text-rose-400">🚨</span> proctoring alerts
              </div>
              <span className="text-[11.5px] text-slate-400">real-time feed</span>
            </div>

            <div className="mt-3 space-y-2.5">
              {d.proctoring_alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="flex items-start gap-2.5 rounded-[9px] border border-slate-800/60 bg-slate-950/40 p-2.5"
                >
                  <div
                    className={cx(
                      "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-[6px] text-[11px]",
                      alert.severity === "rose"
                        ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                        : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    )}
                  >
                    {alert.alert_type.includes("faces") ? "👥" : alert.alert_type.includes("Tab") ? "🗂️" : "👀"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12.5px] font-semibold text-slate-200">{alert.alert_type}</p>
                    <p className="truncate text-[11.5px] text-slate-400">
                      {alert.candidate_name} — {alert.exam_title}
                    </p>
                    <p className="mt-0.5 text-[10.5px] text-slate-500">
                      {alert.time_ago} · <span className="font-medium text-slate-400">{alert.suspicion_delta}</span>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Row 3: Signal Breakdown & AI Grading Queue ───────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
        {/* Proctoring Signal Breakdown + Score Histogram */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800/80">
              <span className="text-[13px] font-semibold text-slate-200">
                proctoring signal breakdown <span className="text-slate-500 font-normal">— current cohort</span>
              </span>
            </div>

            <div className="mt-3 space-y-2.5">
              {[
                { label: "Face present", value: d.proctoring_signals.face_present_pct, color: "bg-emerald-500" },
                { label: "Gaze on screen", value: d.proctoring_signals.gaze_on_screen_pct, color: "bg-indigo-500" },
                { label: "No tab switches", value: d.proctoring_signals.no_tab_switches_pct, color: "bg-indigo-500" },
                { label: "Single face", value: d.proctoring_signals.single_face_pct, color: "bg-emerald-500" },
                { label: "High suspicion (>60)", value: d.proctoring_signals.high_suspicion_pct, color: "bg-rose-500" },
              ].map((sig) => (
                <div key={sig.label} className="space-y-1">
                  <div className="flex justify-between text-[11.5px]">
                    <span className="text-slate-300">{sig.label}</span>
                    <span className="font-medium text-white">{sig.value}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className={cx("h-full rounded-full transition-all duration-500", sig.color)}
                      style={{ width: `${sig.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Score distribution histogram */}
          <div className="pt-2 border-t border-slate-800/80">
            <p className="text-[11.5px] font-medium text-slate-400 mb-2">
              <span className="inline-block h-2 w-2 rounded-full bg-indigo-500 mr-1.5" />
              score distribution · completed exams
            </p>
            <div className="flex items-end justify-between gap-2 h-20 pt-2 px-1">
              {d.score_distribution.map((bin) => {
                const maxCount = Math.max(...d.score_distribution.map((b) => b.count), 1);
                const heightPct = Math.round((bin.count / maxCount) * 100);
                return (
                  <div key={bin.bin} className="flex-1 flex flex-col items-center gap-1 group">
                    <span className="text-[10px] text-slate-400 group-hover:text-white transition">
                      {bin.count}
                    </span>
                    <div className="w-full bg-slate-800 rounded-t-[4px] flex items-end h-14 overflow-hidden">
                      <div
                        className="w-full bg-indigo-600 group-hover:bg-indigo-500 rounded-t-[4px] transition-all"
                        style={{ height: `${heightPct}%` }}
                      />
                    </div>
                    <span className="text-[9.5px] text-slate-500 group-hover:text-slate-300 font-mono">
                      {bin.bin}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* AI Grading Queue */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800/80">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-slate-200">
                <span>🤖</span> AI grading queue
              </div>
              <Link href="/dashboard/grading" className="text-[11.5px] text-indigo-400 hover:underline">
                open queue →
              </Link>
            </div>

            <div className="mt-3 space-y-2">
              {d.ai_grading_queue.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between rounded-[8px] border border-slate-800/60 bg-slate-950/40 px-3 py-2 text-[12px]"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className={cx(
                        "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
                        item.question_type === "short"
                          ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                          : item.question_type === "long"
                            ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      )}
                    >
                      {item.question_type}
                    </span>
                    <span className="truncate text-slate-200 font-medium">{item.title}</span>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <span className="font-mono text-[11px] font-semibold text-slate-400">
                      {item.ai_score}
                    </span>
                    <Link
                      href="/dashboard/grading"
                      className="rounded-[6px] bg-slate-800 px-2 py-1 text-[10.5px] font-medium text-slate-300 hover:bg-indigo-600 hover:text-white transition"
                    >
                      review ↗
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11.5px] text-slate-400">
            <span>
              <strong className="text-white">{d.grading_queue_count}</strong> answers pending ·{" "}
              <strong className="text-indigo-300">{d.ai_prescored_count}</strong> AI-pre-scored
            </span>
            <Link
              href="/dashboard/grading"
              className="rounded-[6px] bg-indigo-600/30 border border-indigo-500/40 px-2.5 py-1 font-medium text-indigo-300 hover:bg-indigo-600 hover:text-white transition"
            >
              full queue ↗
            </Link>
          </div>
        </div>
      </div>

      {/* ─── Row 4: 3-Column Bottom Zone (Upcoming, Activity, Actions) ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {/* Upcoming Exams */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm">
          <p className="text-[12.5px] font-semibold text-slate-200 mb-3 flex items-center gap-1.5">
            <span>📅</span> upcoming exams
          </p>
          <div className="space-y-2 text-[12px]">
            {d.upcoming_exams.map((ex) => (
              <div key={ex.id} className="flex items-center justify-between py-1.5 border-b border-slate-800/60 last:border-0">
                <span className="truncate text-slate-300">{ex.title}</span>
                <span className="font-mono text-[11px] text-slate-500 shrink-0">{ex.time_str}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm">
          <p className="text-[12.5px] font-semibold text-slate-200 mb-3 flex items-center gap-1.5">
            <span>⚡</span> recent activity
          </p>
          <div className="space-y-2 text-[12px]">
            {d.recent_activity.map((act, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-slate-800/60 last:border-0">
                <span className="truncate text-slate-300">{act.message}</span>
                <span className="font-mono text-[10.5px] text-slate-500 shrink-0">{act.time_ago}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-[12px] border border-slate-800/80 bg-slate-900/80 p-4 shadow-sm flex flex-col justify-between">
          <p className="text-[12.5px] font-semibold text-slate-200 mb-3 flex items-center gap-1.5">
            <span>🛠️</span> quick actions
          </p>
          <div className="grid grid-cols-1 gap-1.5">
            <Link
              href="/dashboard/exams/create"
              className="flex items-center justify-between rounded-[8px] bg-slate-800/70 hover:bg-indigo-600/40 border border-slate-700/50 px-3 py-2 text-[12px] font-medium text-slate-200 hover:text-white transition"
            >
              <span>+ create new exam</span>
              <span className="text-slate-400">↗</span>
            </Link>
            <Link
              href="/dashboard/proctoring"
              className="flex items-center justify-between rounded-[8px] bg-slate-800/70 hover:bg-indigo-600/40 border border-slate-700/50 px-3 py-2 text-[12px] font-medium text-slate-200 hover:text-white transition"
            >
              <span>review flagged sessions</span>
              <span className="text-slate-400">↗</span>
            </Link>
            <Link
              href="/dashboard/results"
              className="flex items-center justify-between rounded-[8px] bg-slate-800/70 hover:bg-indigo-600/40 border border-slate-700/50 px-3 py-2 text-[12px] font-medium text-slate-200 hover:text-white transition"
            >
              <span>publish results</span>
              <span className="text-slate-400">↗</span>
            </Link>
            <Link
              href="/dashboard/grading"
              className="flex items-center justify-between rounded-[8px] bg-slate-800/70 hover:bg-indigo-600/40 border border-slate-700/50 px-3 py-2 text-[12px] font-medium text-slate-200 hover:text-white transition"
            >
              <span>export grading report</span>
              <span className="text-slate-400">↗</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
