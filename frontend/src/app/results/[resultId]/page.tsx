"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { Mark } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import {
  Alert,
  Badge,
  Button,
  Card,
  ProgressBar,
  SectionTitle,
  Skeleton,
  cx,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  GradeStatus,
  QuestionResult,
  ResultDetail,
  SectionScoreResult,
} from "@/lib/types";

const GRADE_LABEL: Record<GradeStatus, string> = {
  unanswered: "Not answered",
  auto_scored: "Auto-scored",
  pending_ai: "Awaiting review",
  ai_scored: "Provisional",
  examiner_reviewed: "Examiner reviewed",
};

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function ResultDetailPage() {
  const { user, booting } = useRequireAuth();
  const params = useParams<{ resultId: string }>();
  const [detail, setDetail] = useState<ResultDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        setDetail(await api.get<ResultDetail>(`/results/${params.resultId}`));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not load this result.");
      }
    })();
  }, [user, params.resultId]);

  const [downloading, setDownloading] = useState(false);

  async function handleDownloadPdf() {
    if (!detail) return;
    setDownloading(true);
    try {
      const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:8000/api/v1";
      const token = typeof window !== "undefined" ? localStorage.getItem("exam.access") : null;
      const res = await fetch(`${BASE}/results/${params.resultId}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Failed to download PDF scorecard");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `scorecard_${detail.exam_title.replace(/\s+/g, "_")}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch {
      setError("Could not generate PDF scorecard. Please try again.");
    } finally {
      setDownloading(false);
    }
  }

  if (booting) return <Splash />;

  const backHref =
    user?.role === "candidate" ? "/dashboard/results" : "/dashboard/grading";

  const isPass =
    detail?.passing_percentage != null
      ? detail.result.percentage >= detail.passing_percentage
      : null;

  const statusLabel =
    detail?.exam_type === "corporate"
      ? isPass === true
        ? "QUALIFIED"
        : isPass === false
          ? "NOT QUALIFIED"
          : null
      : isPass === true
        ? "PASS"
        : isPass === false
          ? "FAIL"
          : null;

  return (
    <div className="mx-auto min-h-screen w-full max-w-[1040px] px-5 py-8">
      {/* nav bar */}
      <div className="mb-7 flex items-center justify-between gap-4">
        <Link href={backHref} className="flex items-center gap-2.5">
          <Mark size={24} />
          <span className="text-[14px] font-semibold tracking-tight text-ink">Smart Assess.ai</span>
        </Link>
        <div className="flex items-center gap-2.5">
          {detail && (
            <Button
              size="sm"
              variant="secondary"
              onClick={handleDownloadPdf}
              disabled={downloading}
            >
              <span>📄</span>
              {downloading ? "Generating PDF..." : "Download PDF Scorecard"}
            </Button>
          )}
          <Link href={backHref}>
            <Button variant="secondary" size="sm">Back</Button>
          </Link>
        </div>
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {!detail && !error && (
        <div className="space-y-4">
          <Skeleton className="h-[200px] rounded-[18px]" />
          <Skeleton className="h-[120px] rounded-[14px]" />
          <Skeleton className="h-[320px] rounded-[14px]" />
        </div>
      )}

      {detail && (
        <div className="space-y-6">
          {/* ─────────────────────── hero score card ─────────────────────── */}
          <div className="overflow-hidden rounded-[20px] border border-line bg-gradient-to-br from-surface to-sunken/60 shadow-sm">
            <div className="flex flex-col items-center gap-6 px-8 py-10 sm:flex-row sm:items-start">
              {/* Ring */}
              <div className="relative flex h-36 w-36 shrink-0 items-center justify-center">
                <ScoreRing pct={detail.result.percentage} pass={isPass} />
                <div className="absolute flex flex-col items-center">
                  <span className="text-[28px] font-bold leading-none tracking-tight text-ink">
                    {Math.round(detail.result.percentage)}
                    <span className="text-[16px] font-medium text-ink-muted">%</span>
                  </span>
                </div>
              </div>

              <div className="flex-1 text-center sm:text-left">
                <h1 className="text-[22px] font-bold tracking-tight text-ink">
                  {detail.exam_title}
                </h1>
                <p className="mt-1 text-[13.5px] text-ink-muted">
                  {detail.subject_name} · {detail.candidate_name}
                  {detail.submitted_at ? ` · submitted ${formatDate(detail.submitted_at)}` : ""}
                </p>

                {statusLabel && (
                  <div className="mt-4">
                    <span
                      className={cx(
                        "inline-block rounded-[10px] px-5 py-1.5 text-[14px] font-bold tracking-widest",
                        isPass
                          ? "bg-mint-soft text-mint"
                          : "bg-rose-soft text-rose",
                      )}
                    >
                      {statusLabel}
                    </span>
                  </div>
                )}

                {/* Stats row */}
                <div className="mt-5 flex flex-wrap justify-center gap-5 sm:justify-start">
                  <StatItem label="Score" value={`${detail.result.obtained_marks} / ${detail.result.total_marks}`} />
                  <StatItem
                    label="Accuracy"
                    value={`${detail.result.total_marks > 0 ? Math.round((detail.result.obtained_marks / detail.result.total_marks) * 100) : 0}%`}
                  />
                  {detail.time_taken_seconds != null && (
                    <StatItem label="Time taken" value={formatTime(detail.time_taken_seconds)} />
                  )}
                  <StatItem
                    label="Correct"
                    value={`${detail.result.correct_count}`}
                    accent="mint"
                  />
                  <StatItem
                    label="Wrong"
                    value={`${detail.result.incorrect_count}`}
                    accent="rose"
                  />
                  <StatItem
                    label="Blank"
                    value={`${detail.result.unanswered_count}`}
                  />
                </div>

                {/* Percentile */}
                {detail.percentile != null && (
                  <div className="mt-4 inline-flex items-center gap-2 rounded-[10px] border border-accent/20 bg-accent-soft/40 px-4 py-2 text-[13px]">
                    <span className="text-[15px]">📊</span>
                    <span className="text-ink">
                      You scored higher than{" "}
                      <strong className="text-accent-ink">{detail.percentile}%</strong> of{" "}
                      {detail.cohort_size} candidates.
                    </span>
                  </div>
                )}
              </div>
            </div>

            {detail.result.pending_review_count > 0 && (
              <div className="border-t border-amber/20 bg-amber-soft/40 px-8 py-3">
                <p className="text-[12.5px] text-amber">
                  ⚠ {detail.result.pending_review_count} answer
                  {detail.result.pending_review_count === 1 ? " is" : "s are"} still awaiting
                  examiner review — your score may change.
                </p>
              </div>
            )}
          </div>

          {/* ─────────────────── section scores (corporate / multi-section) ─────── */}
          {detail.section_scores.length > 0 && (
            <div>
              <SectionTitle title="Section breakdown" />
              <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {detail.section_scores.map((sec) => (
                  <SectionScoreCard key={sec.section_id} sec={sec} />
                ))}
              </div>
            </div>
          )}

          {/* ─────────────────── question breakdown ────────────────────────── */}
          <div>
            <SectionTitle title="Question by question" />
            <div className="mt-3 space-y-3">
              {detail.questions.map((question, index) => (
                <QuestionCard key={question.question_id} index={index} question={question} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════ sub-components ═══════════════════════════ */

function ScoreRing({ pct, pass }: { pct: number; pass: boolean | null }) {
  const r = 54;
  const circ = 2 * Math.PI * r;
  const dash = Math.min(1, pct / 100) * circ;
  const gap = circ - dash;
  const color =
    pass === true ? "#2dd4bf" : pass === false ? "#f87171" : pct >= 70 ? "#2dd4bf" : pct >= 40 ? "#fbbf24" : "#f87171";

  return (
    <svg width="144" height="144" viewBox="0 0 144 144" className="-rotate-90">
      <circle cx="72" cy="72" r={r} fill="none" stroke="currentColor" strokeWidth="10" className="text-line" />
      <circle
        cx="72"
        cy="72"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${dash} ${gap}`}
        className="transition-all duration-700"
      />
    </svg>
  );
}

function StatItem({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: "mint" | "rose";
}) {
  return (
    <div className="text-center sm:text-left">
      <p className="text-[11px] uppercase tracking-wide text-ink-muted">{label}</p>
      <p
        className={cx(
          "mt-0.5 text-[17px] font-semibold",
          accent === "mint" ? "text-mint" : accent === "rose" ? "text-rose" : "text-ink",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function SectionScoreCard({ sec }: { sec: SectionScoreResult }) {
  const tone =
    sec.percentage >= 70 ? "mint" : sec.percentage >= 40 ? "amber" : "rose";
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-[13px] font-semibold text-ink">{sec.section_name}</p>
        <span className="text-[13px] font-bold tabular-nums text-ink">
          {sec.obtained_marks}/{sec.total_marks}
        </span>
      </div>
      <ProgressBar value={sec.percentage} tone={tone} />
      <div className="mt-2.5 flex gap-3 text-[11.5px] text-ink-muted">
        <span className="text-mint">{sec.correct} correct</span>
        <span className="text-rose">{sec.incorrect} wrong</span>
        <span>{sec.unanswered} blank</span>
      </div>
    </Card>
  );
}

function QuestionCard({ index, question }: { index: number; question: QuestionResult }) {
  const scored = question.awarded_marks !== null;
  const full = scored && question.awarded_marks! >= question.marks;
  const zero = scored && question.awarded_marks! <= 0;
  const isImage = question.question_type === "image_upload";

  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone="accent">Q{index + 1}</Badge>
        {question.section_name && <Badge>{question.section_name}</Badge>}
        <Badge>{GRADE_LABEL[question.grade_status]}</Badge>
        <span className="ml-auto text-[13px] font-semibold text-ink">
          <span className={cx(full ? "text-mint" : zero ? "text-rose" : "text-amber")}>
            {scored ? question.awarded_marks : "—"}
          </span>
          <span className="text-ink-muted"> / {question.marks}</span>
        </span>
      </div>

      <p className="whitespace-pre-wrap text-[14.5px] leading-relaxed text-ink">{question.body}</p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-[10px] border border-line bg-sunken/50 p-3">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            Your answer
          </p>
          {question.your_answer ? (
            isImage ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={question.your_answer}
                alt="Your uploaded answer"
                className="max-h-64 w-full rounded-[8px] object-contain"
              />
            ) : (
              <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink">
                {question.your_answer}
              </p>
            )
          ) : (
            <p className="text-[13.5px] italic text-ink-muted">Left blank</p>
          )}
        </div>

        <div className="rounded-[10px] border border-line bg-surface p-3">
          <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-muted">
            {question.question_type === "mcq" || question.question_type === "multi_select"
              ? "Correct answer"
              : "Model answer"}
          </p>
          <p className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-ink-soft">
            {question.correct_answer ?? "—"}
          </p>
        </div>
      </div>

      {question.examiner_comment && (
        <div className="mt-3">
          <Alert tone="accent" title="Examiner comment">
            {question.examiner_comment}
          </Alert>
        </div>
      )}

      {question.ai_justification && (
        <div className="mt-3">
          <Alert tone="neutral" title="Automated first-pass note">
            {question.ai_justification}
          </Alert>
        </div>
      )}
    </Card>
  );
}
