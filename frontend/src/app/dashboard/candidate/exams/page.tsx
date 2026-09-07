"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Skeleton,
  cx,
  formatDate,
} from "@/components/ui";
import { IconArrowRight, IconClock, IconExam, IconShield } from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateExamCard, SessionStatus } from "@/lib/types";

const STATUS_TONE: Record<SessionStatus, "accent" | "mint" | "amber" | "rose"> = {
  in_progress: "accent",
  submitted: "mint",
  auto_submitted: "amber",
  terminated: "rose",
};

const STATUS_LABEL: Record<SessionStatus, string> = {
  in_progress: "In progress",
  submitted: "Submitted",
  auto_submitted: "Auto-submitted",
  terminated: "Terminated",
};

/**
 * My Exams — every paper assigned to this candidate.
 */
export default function MyExamsPage() {
  const { user } = useRequireAuth(["candidate"]);
  const [exams, setExams] = useState<CandidateExamCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<"all" | "academic" | "corporate">("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user) return;
      try {
        const data = await api.get<CandidateExamCard[]>("/my/exams");
        if (!cancelled) setExams(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load your exams.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  const filtered = useMemo(() => {
    return exams.filter((e) => {
      if (filterMode === "academic" && e.exam_type !== "academic") return false;
      if (filterMode === "corporate" && e.exam_type !== "corporate") return false;
      return true;
    });
  }, [exams, filterMode]);

  if (!user) return null;

  const open = filtered.filter((e) => e.can_start);
  const scheduled = filtered.filter((e) => !e.can_start && !e.session_status);
  const done = filtered.filter((e) => !e.can_start && e.session_status);

  return (
    <div className="space-y-6">
      <Hero
        title="My Examinations"
        body="Assigned assessments across Academic courses and Corporate hiring assessments. Open an exam to view details and launch the proctored runner."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {/* Category Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
          {[
            { key: "all", label: `All Exams (${exams.length})` },
            { key: "academic", label: `🎓 Academic (${exams.filter((e) => e.exam_type === "academic").length})` },
            { key: "corporate", label: `💼 Corporate Hiring (${exams.filter((e) => e.exam_type === "corporate").length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilterMode(tab.key as any)}
              className={cx(
                "rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-all",
                filterMode === tab.key
                  ? "bg-accent text-white shadow-sm"
                  : "text-ink-muted hover:text-ink hover:bg-surface-elevated"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-[210px] rounded-[14px]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No examinations found"
          body={exams.length === 0 ? "When an examiner assigns you to a paper it will appear here." : "No exams match the selected filter category."}
        />
      ) : (
        <>
          <Section title="Open for Attempt" count={open.length}>
            {open.length === 0 ? (
              <EmptyState
                title="Nothing open right now"
                body="None of your assigned exams are inside their active window at this time."
              />
            ) : (
              <div className="grid gap-4 md:grid-cols-2">
                {open.map((card) => (
                  <ExamCard key={card.exam_id} card={card} />
                ))}
              </div>
            )}
          </Section>

          {scheduled.length > 0 && (
            <Section title="Upcoming / Scheduled" count={scheduled.length}>
              <div className="grid gap-4 md:grid-cols-2">
                {scheduled.map((card) => (
                  <ExamCard key={card.exam_id} card={card} />
                ))}
              </div>
            </Section>
          )}

          {done.length > 0 && (
            <Section title="Completed Submissions" count={done.length}>
              <Card>
                <ul className="divide-y divide-line">
                  {done.map((card) => (
                    <li key={card.exam_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="truncate text-[13.5px] font-medium text-ink">
                            {card.title}
                          </p>
                          <Badge tone={card.exam_type === "corporate" ? "purple" : "accent"}>
                            {card.exam_type === "corporate" ? "💼 Corporate" : "🎓 Academic"}
                          </Badge>
                        </div>
                        <p className="text-[12px] text-ink-muted mt-0.5">
                          {card.exam_type === "corporate" && card.company_name
                            ? `${card.company_name} · ${card.job_role || card.subject_name}`
                            : `${card.subject_name}${card.course ? ` · ${card.course}` : ""}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {card.session_status && (
                          <Badge tone={STATUS_TONE[card.session_status]}>
                            {STATUS_LABEL[card.session_status]}
                          </Badge>
                        )}
                        {card.result_published && card.result_id ? (
                          <Link href={`/results/${card.result_id}`}>
                            <Button size="sm" variant="secondary">
                              View Result
                            </Button>
                          </Link>
                        ) : (
                          <span className="text-[12px] text-ink-muted">Awaiting Result</span>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </Section>
          )}
        </>
      )}
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
        <Badge tone="neutral">{count}</Badge>
      </div>
      {children}
    </div>
  );
}

function ExamCard({ card }: { card: CandidateExamCard }) {
  const isCorp = card.exam_type === "corporate";

  return (
    <Card className="flex flex-col justify-between hover:border-line-strong transition-all">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={cx(
                "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] text-lg shadow-sm",
                isCorp
                  ? "bg-purple-100 text-purple-600 dark:bg-purple-950/50 dark:text-purple-300"
                  : "bg-accent-soft text-accent"
              )}
            >
              {isCorp ? "💼" : "🎓"}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="truncate text-[15px] font-semibold tracking-tight text-ink">
                  {card.title}
                </p>
              </div>
              <p className="mt-0.5 text-[12.5px] text-ink-muted">
                {isCorp && card.company_name
                  ? `${card.company_name}${card.job_role ? ` · ${card.job_role}` : ""}`
                  : card.course
                  ? `${card.subject_name} · ${card.course}`
                  : card.subject_name}
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1">
            <Badge tone={isCorp ? "purple" : "accent"}>
              {isCorp ? "Hiring Drive" : "Academic"}
            </Badge>
            {card.can_start ? (
              <Badge tone={card.session_status === "in_progress" ? "accent" : "mint"}>
                {card.session_status === "in_progress" ? "resume" : "open now"}
              </Badge>
            ) : (
              <Badge tone="amber">scheduled</Badge>
            )}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2 rounded-[10px] bg-sunken/60 p-3 text-center">
          {[
            ["Duration", `${card.duration_minutes} min`],
            ["Questions", String(card.total_questions)],
            ["Closes", formatDate(card.ends_at, false)],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-[10.5px] uppercase tracking-wide text-ink-muted">{label}</dt>
              <dd className="mt-0.5 text-[12.5px] font-semibold text-ink">{value}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11.5px] text-ink-muted">
          <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5 border border-line">
            <IconShield size={12} /> AI Proctored
          </span>
          {card.sections_count && card.sections_count > 0 ? (
            <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5 border border-line">
              📑 {card.sections_count} Sections
            </span>
          ) : null}
          {card.has_coding && (
            <span className="inline-flex items-center gap-1 rounded bg-purple-50 dark:bg-purple-950/30 text-purple-700 dark:text-purple-300 px-2 py-0.5 border border-purple-200 dark:border-purple-800 font-semibold">
              💻 Coding Challenge
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded bg-surface px-2 py-0.5 border border-line">
            <IconClock size={12} /> Single Attempt
          </span>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-line/60 pt-3">
        <p className="text-[11.5px] text-ink-muted">{card.reason ?? "Ready for sitting"}</p>
        <Link href={`/dashboard/candidate/exams/${card.exam_id}`}>
          <Button size="sm" variant={card.can_start ? "primary" : "secondary"}>
            {card.can_start ? "Start / Resume" : "View Details"}
            <IconArrowRight size={14} />
          </Button>
        </Link>
      </div>
    </Card>
  );
}
