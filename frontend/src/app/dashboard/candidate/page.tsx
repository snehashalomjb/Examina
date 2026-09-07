"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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
  formatDate,
  toast,
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

const STATUS_LABEL: Record<SessionStatus, string> = {
  in_progress: "In progress",
  submitted: "Submitted",
  auto_submitted: "Auto-submitted",
  terminated: "Terminated",
};

export default function CandidateDashboard() {
  const { user } = useRequireAuth(["candidate"]);
  const router = useRouter();

  const [exams, setExams] = useState<CandidateExamCard[]>([]);
  const [stats, setStats] = useState<CandidateStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState<string | null>(null);
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
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load your exams.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, approved]);

  async function enter(card: CandidateExamCard) {
    setStarting(card.exam_id);
    try {
      const session = await api.post<{ session_id: string }>(`/exams/${card.exam_id}/start`);
      router.push(`/exam/${session.session_id}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not start the exam", "rose");
      setStarting(null);
    }
  }

  if (!user) return null;
  if (!approved) {
    return <AwaitingApproval role="candidate" status={user.access_status} note={user.access_note} />;
  }

  const available = exams.filter((e) => e.can_start);
  const history = exams.filter((e) => !e.can_start && e.session_status);
  const upcoming = exams.filter((e) => !e.can_start && !e.session_status);

  return (
    <div className="space-y-7">
      {/* ─── Hero ─────────────────────────────────────────── */}
      <div>
        <h1 className="text-[24px] font-bold tracking-tight text-ink">
          Welcome back, {user.full_name.split(" ")[0]} 👋
        </h1>
        <p className="mt-1 text-[14px] text-ink-muted">
          Your personalized assessments and results are here.
        </p>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {/* ─── Stats grid ────────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {loading || !stats ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-[12px] border border-line bg-surface p-5">
              <Skeleton className="mb-3 h-3 w-20" />
              <Skeleton className="h-8 w-16" />
            </div>
          ))
        ) : (
          <>
            <StatCard
              label="Open to Sit"
              value={stats.available_exams}
              tone={stats.available_exams ? "accent" : "neutral"}
              hint="Not yet attempted"
              icon={<ExamIcon />}
            />
            <StatCard
              label="Completed"
              value={stats.completed_exams}
              tone="neutral"
              hint="Papers submitted"
              icon={<CheckIcon />}
            />
            <StatCard
              label="Average Score"
              value={stats.average_percentage !== null ? `${stats.average_percentage}%` : "—"}
              tone="green"
              hint="Across published results"
              icon={<TrendIcon />}
            />
            <StatCard
              label="Best Result"
              value={stats.best_percentage !== null ? `${stats.best_percentage}%` : "—"}
              tone="accent"
              hint={`${stats.published_results} published`}
              icon={<StarIcon />}
            />
          </>
        )}
      </div>

      {/* ─── Available exams ──────────────────────────────── */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-[16px] font-semibold text-ink">Ready to Sit</h2>
            <p className="mt-0.5 text-[12.5px] text-ink-muted">
              Ensure your camera is working before you begin.
            </p>
          </div>
          <Link href="/dashboard/candidate/exams">
            <Button variant="secondary" size="sm">View all exams →</Button>
          </Link>
        </div>

        {loading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="rounded-[12px] border border-line bg-surface p-5">
                <Skeleton className="mb-3 h-5 w-48" />
                <Skeleton className="mb-4 h-3 w-32" />
                <Skeleton className="h-16 rounded-[10px]" />
                <Skeleton className="mt-4 h-9 w-24 rounded-[9px]" />
              </div>
            ))}
          </div>
        ) : available.length === 0 ? (
          <EmptyState
            title="No exams open right now"
            body="When an examiner publishes an exam and its window opens, it will appear here."
            icon={<ExamIcon />}
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {available.map((card) => (
              <ExamAvailableCard
                key={card.exam_id}
                card={card}
                starting={starting === card.exam_id}
                onEnter={() => enter(card)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ─── History + Upcoming ──────────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Recent attempts */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[15px] font-semibold text-ink">Your Attempts</h2>
            <Link href="/dashboard/results" className="text-[12.5px] font-medium text-accent hover:underline">
              Results →
            </Link>
          </div>
          {loading ? (
            <Skeleton className="h-24 rounded-[10px]" />
          ) : history.length === 0 ? (
            <EmptyState title="No attempts yet" body="Papers you have sat will be listed here." />
          ) : (
            <ul className="divide-y divide-line">
              {history.map((card) => (
                <li key={card.exam_id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-medium text-ink">{card.title}</p>
                    <p className="truncate text-[12px] text-ink-muted">
                      {card.subject_name} · {card.reason}
                    </p>
                  </div>
                  {card.session_status && (
                    <Badge tone={STATUS_TONE[card.session_status]} size="xs">
                      {STATUS_LABEL[card.session_status]}
                    </Badge>
                  )}
                  {card.result_published && card.result_id ? (
                    <Link href={`/results/${card.result_id}`}>
                      <Button size="sm" variant="secondary">View result</Button>
                    </Link>
                  ) : (
                    <span className="whitespace-nowrap text-[12px] text-ink-muted">Pending</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Upcoming / scheduled */}
        <Card>
          <h2 className="mb-4 text-[15px] font-semibold text-ink">Scheduled</h2>
          {loading ? (
            <Skeleton className="h-24 rounded-[10px]" />
          ) : upcoming.length === 0 ? (
            <EmptyState title="Nothing scheduled" body="Future exam windows will show up here." />
          ) : (
            <ul className="divide-y divide-line">
              {upcoming.map((card) => (
                <li key={card.exam_id} className="py-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-[13.5px] font-medium text-ink">{card.title}</p>
                    <span
                      className={cx(
                        "shrink-0 text-[12px] font-medium",
                        card.reason?.startsWith("Opens") ? "text-accent" : "text-ink-muted",
                      )}
                    >
                      {card.reason}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[12px] text-ink-muted">
                    {card.subject_name} · {card.duration_minutes} min · {card.total_questions} questions
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

/* ─── Available exam card ────────────────────────────────────────── */
function ExamAvailableCard({
  card,
  starting,
  onEnter,
}: {
  card: CandidateExamCard;
  starting: boolean;
  onEnter: () => void;
}) {
  const isResume = card.session_status === "in_progress";
  return (
    <Card variant="elevated" className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[15px] font-bold tracking-tight text-ink">{card.title}</p>
          <p className="mt-0.5 text-[12.5px] text-ink-muted">{card.subject_name}</p>
        </div>
        <Badge tone={isResume ? "accent" : "green"} size="xs">
          {isResume ? "In Progress" : "Open"}
        </Badge>
      </div>

      {/* Exam metadata */}
      <div className="grid grid-cols-3 gap-2 rounded-[10px] bg-sunken px-3 py-2.5">
        {[
          ["Duration", `${card.duration_minutes} min`],
          ["Questions", String(card.total_questions)],
          ["Closes", formatDate(card.ends_at, false)],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-[10.5px] font-semibold uppercase tracking-[0.06em] text-ink-muted">{label}</dt>
            <dd className="mt-0.5 text-[13px] font-semibold text-ink">{value}</dd>
          </div>
        ))}
      </div>

      {/* Proctoring notice */}
      <div className="flex items-center gap-2 rounded-[8px] bg-amber-soft px-3 py-2 text-[12px] text-amber-ink">
        <span>⚠</span>
        <span>Webcam proctored · one attempt · auto-submits at time</span>
      </div>

      {/* CTA */}
      <Button loading={starting} onClick={onEnter} className="w-full" size="lg">
        {isResume ? "Resume Assessment" : "Start Assessment →"}
      </Button>
    </Card>
  );
}

/* ─── Inline icons ───────────────────────────────────────────────── */
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
