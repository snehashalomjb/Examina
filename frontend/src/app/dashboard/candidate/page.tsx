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
  RingProgress,
  Skeleton,
  Sparkline,
  StatCard,
  cx,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateExamCard, CandidateStats, SessionStatus } from "@/lib/types";

const STATUS_TONE: Record<SessionStatus, "accent" | "green" | "amber" | "rose"> = {
  in_progress: "accent",
  submitted: "green",
  auto_submitted: "amber",
  terminated: "rose",
};

/** Server `reason` strings (exam_sessions.py) are English; map the known ones to keys. */
function translateReason(
  reason: string | null | undefined,
  startsAt: string | null | undefined,
  tc: ReturnType<typeof useTranslations>,
): string | null {
  if (!reason) return null;
  if (reason === "Attempt in progress") return tc("reason_attempt_in_progress");
  if (reason === "Already attempted") return tc("reason_already_attempted");
  if (reason === "This exam is closed") return tc("reason_exam_closed");
  if (reason === "The exam window has closed") return tc("reason_window_closed");
  if (reason.startsWith("Opens ")) return tc("reason_opens", { date: formatDate(startsAt) });
  return reason;
}

export default function CandidateDashboard() {
  const t = useTranslations("exam");
  const tc = useTranslations("candidatePages");
  const { user } = useRequireAuth(["candidate"]);
  const router = useRouter();

  const [exams, setExams] = useState<CandidateExamCard[]>([]);
  const [stats, setStats] = useState<CandidateStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const approved = user?.access_status === "approved";

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user || !approved) { if (!cancelled) setLoading(false); return; }
      try {
        const [examData, statsData] = await Promise.all([
          api.get<CandidateExamCard[]>("/my/exams"),
          api.get<CandidateStats>("/my/stats/summary"),
        ]);
        if (cancelled) return;
        setExams(examData);
        setStats(statsData);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : tc("error_load_exams"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, approved]);

  function enter(card: CandidateExamCard) {
    router.push(`/dashboard/candidate/exams/${card.exam_id}`);
  }

  if (!user) return null;
  if (!approved) {
    return <AwaitingApproval role="candidate" status={user.access_status} note={user.access_note} />;
  }

  const available = exams.filter((e) => e.can_start);
  const history = exams.filter((e) => !e.can_start && e.session_status);
  const upcoming = exams.filter((e) => !e.can_start && !e.session_status);

  /* Sparkline data: published scores, oldest -> newest, last 7. `/my/exams` arrives
   * newest-first by exam start, so it has to be re-sorted by submission time - otherwise
   * the line reads backwards and the highlighted end dot sits on the oldest result. */
  const scoreHistory = history
    .filter((e) => e.percentage !== null && e.percentage !== undefined)
    .sort(
      (a, b) =>
        new Date(a.submitted_at ?? a.starts_at).getTime() -
        new Date(b.submitted_at ?? b.starts_at).getTime(),
    )
    .slice(-7)
    .map((e) => Math.round(e.percentage as number));
  const latestScore = scoreHistory.length ? scoreHistory[scoreHistory.length - 1] : null;
  const scoreDelta =
    scoreHistory.length >= 2 ? latestScore! - scoreHistory[scoreHistory.length - 2] : null;

  /* Motivational message */
  const motivational =
    available.length > 0
      ? tc("motivational_open", { count: available.length })
      : upcoming.length > 0
        ? tc("motivational_upcoming", { count: upcoming.length })
        : tc("motivational_caught_up");

  return (
    <div className="space-y-6">

      {/* ─── Welcome Hero ─────────────────────────────────────── */}
      <div
        className="relative overflow-hidden rounded-[20px] border p-6 sm:p-8"
        style={{
          background: "linear-gradient(135deg, rgba(16,185,129,0.07) 0%, rgba(79,70,229,0.05) 60%, rgba(245,158,11,0.03) 100%)",
          borderColor: "rgba(16,185,129,0.2)",
          boxShadow: "0 4px 32px -8px rgba(16,185,129,0.10)",
        }}
      >
        {/* Decorative circles */}
        <div className="pointer-events-none absolute -right-12 -top-12 h-52 w-52 rounded-full opacity-[0.05]"
          style={{ background: "radial-gradient(circle, #10b981, transparent 70%)" }} />
        <div className="pointer-events-none absolute -bottom-6 right-24 h-36 w-36 rounded-full opacity-[0.04]"
          style={{ background: "radial-gradient(circle, #4f46e5, transparent 70%)" }} />

        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex-1">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-green-soft border border-green-border px-3 py-1">
              <span className="h-2 w-2 rounded-full bg-green animate-pulse" />
              <span className="text-[11px] font-bold text-green-ink tracking-wide uppercase">{tc("candidate_portal")}</span>
            </div>
            <h1 className="text-[22px] font-extrabold tracking-tight text-ink sm:text-[26px]">
              {tc("welcome_back", { name: user.full_name.split(" ")[0] })}
            </h1>
            <p className="mt-1.5 text-[13.5px] text-ink-muted max-w-lg">{motivational}</p>
          </div>

          {/* Score trend card - latest published score, change since the previous one,
              and the trend line once there are two points to draw. */}
          {latestScore !== null && (
            <div className="w-full shrink-0 rounded-[14px] border border-line bg-surface/80 p-3.5 backdrop-blur-sm sm:w-auto sm:min-w-[168px]">
              <p className="text-[10.5px] font-bold uppercase tracking-widest text-ink-muted">{tc("score_trend")}</p>
              <div className="mt-1 flex items-end justify-between gap-4">
                <div>
                  <p className="text-[22px] font-extrabold leading-none tracking-tight text-ink">
                    {latestScore}%
                  </p>
                  {scoreDelta !== null && (
                    <p
                      className={cx(
                        "mt-1 text-[11px] font-semibold",
                        scoreDelta > 0 ? "text-green-ink" : scoreDelta < 0 ? "text-rose-ink" : "text-ink-muted",
                      )}
                    >
                      {scoreDelta > 0 ? "▲" : scoreDelta < 0 ? "▼" : "•"} {tc("pts_vs_previous", { count: Math.abs(scoreDelta) })}
                    </p>
                  )}
                </div>
                {scoreHistory.length >= 2 && (
                  <Sparkline
                    data={scoreHistory}
                    width={96}
                    height={36}
                    tone={scoreDelta !== null && scoreDelta < 0 ? "rose" : "green"}
                  />
                )}
              </div>
              <p className="mt-1.5 text-[11px] text-ink-muted">
                {scoreHistory.length === 1
                  ? tc("first_published_result")
                  : tc("last_n_results", { count: scoreHistory.length })}
              </p>
            </div>
          )}
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {/* ─── Stats Grid ───────────────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-[14px] border border-line bg-surface p-5">
              <Skeleton className="mb-3 h-3 w-20" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))
        ) : (
          <>
            <StatCard
              label={tc("stat_open_to_sit")}
              value={stats.available_exams}
              tone={stats.available_exams ? "green" : "neutral"}
              trend={stats.available_exams > 0 ? { value: tc("stat_available_now"), up: true } : undefined}
              hint={tc("stat_not_yet_attempted")}
              icon={<ExamIcon />}
            />
            <StatCard
              label={tc("stat_completed")}
              value={stats.completed_exams}
              tone="neutral"
              hint={tc("stat_papers_submitted")}
              icon={<CheckIcon />}
            />
            <StatCard
              label={tc("stat_average_score")}
              value={stats.average_percentage !== null ? `${stats.average_percentage}%` : "—"}
              tone="accent"
              hint={tc("stat_across_published")}
              icon={<TrendIcon />}
            />
            <StatCard
              label={tc("stat_best_result")}
              value={stats.best_percentage !== null ? `${stats.best_percentage}%` : "—"}
              tone={stats.best_percentage !== null && stats.best_percentage >= 80 ? "mint" : "amber"}
              hint={tc("stat_published_count", { count: stats.published_results })}
              icon={<StarIcon />}
            />
          </>
        )}
      </div>

      {/* ─── Available Exams (Open to Sit) ────────────────────── */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-[16px] font-bold text-ink">{t("heading_ready_to_sit")}</h2>
            <p className="mt-0.5 text-[12.5px] text-ink-muted">{tc("camera_check_hint")}</p>
          </div>
          <Link href="/dashboard/candidate/exams">
            <Button variant="secondary" size="sm">{tc("view_all")}</Button>
          </Link>
        </div>

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="rounded-[16px] border border-line bg-surface p-5">
                <Skeleton className="mb-3 h-5 w-48" />
                <Skeleton className="mb-4 h-3 w-32" />
                <Skeleton className="h-16 rounded-[10px]" />
                <Skeleton className="mt-4 h-9 w-full rounded-[10px]" />
              </div>
            ))}
          </div>
        ) : available.length === 0 ? (
          <EmptyState
            title={tc("no_exams_open_title")}
            body={tc("no_exams_open_body")}
            icon={<ExamIcon />}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {available.map((card) => (
              <ExamAvailableCard key={card.exam_id} card={card} onEnter={() => enter(card)} />
            ))}
          </div>
        )}
      </div>

      {/* ─── History + Upcoming (two-column) ──────────────────── */}
      <div className="grid gap-5 lg:grid-cols-2">

        {/* Your Attempts */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-ink">{t("heading_your_attempts")}</h2>
            <Link href="/dashboard/results" className="text-[12.5px] font-semibold text-accent hover:underline">
              {tc("results_link")}
            </Link>
          </div>
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 rounded-[10px]" />)}
            </div>
          ) : history.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-3xl">📝</p>
              <p className="mt-2 text-[13px] font-semibold text-ink">{tc("no_attempts_title")}</p>
              <p className="mt-0.5 text-[12px] text-ink-muted">{tc("no_attempts_body")}</p>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {history.map((card) => {
                const hasPct = card.percentage !== null && card.percentage !== undefined;
                const pct = hasPct ? Math.round(card.percentage as number) : null;
                return (
                  <li key={card.exam_id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                    {/* Score ring */}
                    {hasPct && pct !== null ? (
                      <div className="relative shrink-0">
                        <RingProgress
                          value={pct}
                          size={40}
                          stroke={4}
                          tone={pct >= 75 ? "green" : pct >= 50 ? "amber" : "rose"}
                          label={`${pct}`}
                        />
                      </div>
                    ) : (
                      <div className="h-10 w-10 shrink-0 rounded-full bg-sunken flex items-center justify-center text-[10px] text-ink-muted font-bold">
                        —
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-semibold text-ink">{card.title}</p>
                      <p className="truncate text-[11.5px] text-ink-muted">
                        {card.subject_name}
                        {card.session_status && (
                          <> · <Badge tone={STATUS_TONE[card.session_status]} size="xs">{tc(`status_${card.session_status}`)}</Badge></>
                        )}
                      </p>
                    </div>
                    {card.result_published && card.result_id ? (
                      <div className="shrink-0">
                        {card.passed !== null && card.passed !== undefined && (
                          <Badge tone={card.passed ? "mint" : "rose"} size="xs" className="mr-1">
                            {card.passed ? tc("pass") : tc("fail")}
                          </Badge>
                        )}
                        <Link href={`/results/${card.result_id}`}>
                          <Button size="sm" variant="secondary">{t("button_view_result")}</Button>
                        </Link>
                      </div>
                    ) : (
                      <span className="shrink-0 whitespace-nowrap text-[11px] text-ink-muted">
                        {tc("under_review")}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Upcoming / Scheduled */}
        <Card>
          <h2 className="mb-4 text-[15px] font-bold text-ink">{t("heading_scheduled")}</h2>
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 rounded-[10px]" />)}
            </div>
          ) : upcoming.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-3xl">📅</p>
              <p className="mt-2 text-[13px] font-semibold text-ink">{tc("nothing_scheduled_title")}</p>
              <p className="mt-0.5 text-[12px] text-ink-muted">{tc("nothing_scheduled_body")}</p>
            </div>
          ) : (
            <ul className="space-y-2.5">
              {upcoming.map((card) => {
                const opensAt = card.reason?.startsWith("Opens") ? card.starts_at ?? null : null;
                return (
                  <li
                    key={card.exam_id}
                    className="rounded-[12px] border border-line bg-gradient-to-br from-accent/[0.03] to-transparent p-3.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-[13px] font-semibold text-ink">{card.title}</p>
                        <p className="mt-0.5 text-[11.5px] text-ink-muted">
                          {card.subject_name} ·{" "}
                          {tc("minutes_questions_short", { minutes: card.duration_minutes, count: card.total_questions })}
                        </p>
                      </div>
                      <Badge tone="accent" size="xs">{tc("badge_upcoming")}</Badge>
                    </div>
                    {opensAt ? (
                      <div className="mt-2 flex items-center gap-1.5 text-[11.5px] font-semibold text-accent">
                        <span>⏳</span>
                        <span>{tc.rich("opens_in", { countdown: () => <Countdown target={opensAt} /> })}</span>
                      </div>
                    ) : (
                      <p className="mt-1.5 text-[11.5px] text-ink-muted">{translateReason(card.reason, card.starts_at, tc)}</p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ─── Available Exam Card ────────────────────────────────────────── */
function ExamAvailableCard({ card, onEnter }: { card: CandidateExamCard; onEnter: () => void }) {
  const t = useTranslations("exam");
  const tc = useTranslations("candidatePages");
  const isResume = card.session_status === "in_progress";
  const diff = card.ends_at ? new Date(card.ends_at).getTime() - Date.now() : null;
  const closingSoon = diff !== null && diff < 3_600_000 && diff > 0;

  return (
    <Card
      variant="elevated"
      className={cx(
        "flex flex-col gap-4 transition-all duration-200",
        isResume ? "border-accent/30" : closingSoon ? "border-amber/30" : "border-green/20",
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[15px] font-extrabold tracking-tight text-ink">{card.title}</p>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">{card.subject_name}</p>
        </div>
        <Badge tone={isResume ? "accent" : closingSoon ? "amber" : "green"} size="xs">
          {isResume ? tc("status_in_progress") : closingSoon ? tc("badge_closing_soon") : tc("badge_open")}
        </Badge>
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-3 gap-2 rounded-[11px] bg-sunken px-3 py-2.5">
        {[
          [t("duration_label"), tc("minutes_short", { count: card.duration_minutes })],
          [t("questions_label"), String(card.total_questions)],
          [t("closes_label"), formatDate(card.ends_at, false)],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-[10px] font-bold uppercase tracking-[0.08em] text-ink-muted">{label}</dt>
            <dd className="mt-0.5 text-[12.5px] font-semibold text-ink">{value}</dd>
          </div>
        ))}
      </div>

      {/* Countdown timer if closing soon */}
      {closingSoon && (
        <div className="flex items-center gap-2 rounded-[9px] bg-amber-soft border border-amber/20 px-3 py-2 text-[12px] font-semibold text-amber-ink">
          <span>⏱</span>
          <span>{tc.rich("closes_in", { countdown: () => <Countdown target={card.ends_at} /> })}</span>
        </div>
      )}

      {/* Proctoring notice */}
      <div className="flex items-center gap-2 rounded-[9px] bg-sunken px-3 py-2 text-[11.5px] text-ink-muted">
        <span>🔒</span>
        <span>{tc("proctoring_notice")}</span>
      </div>

      {/* CTA */}
      <Button
        onClick={onEnter}
        className="w-full"
        size="lg"
        variant={isResume ? "primary" : "primary"}
      >
        {isResume ? tc("resume_assessment") : tc("start_assessment")}
      </Button>
    </Card>
  );
}

/* ─── Inline Icons ───────────────────────────────────────────────── */
function ExamIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M14 3v5h5" /><path d="M9 13l1.8 1.8L14.5 11" /></svg>;
}
function CheckIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12.5 9.5 17 19 7.5" /></svg>;
}
function TrendIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M3 17.5 9 11l4 4 8-8.5" /><path d="M15.5 6.5H21V12" /></svg>;
}
function StarIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 2l2.5 7.5H22l-6.5 4.5 2.5 7.5L12 17l-6 4.5 2.5-7.5L2 9.5h7.5L12 2Z" /></svg>;
}
