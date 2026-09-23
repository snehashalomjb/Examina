"use client";

/**
 * Reports.
 *
 * Every tab points at a real, already-built view over real data rather than
 * duplicating it here - exams, candidates and proctoring already have their own full
 * pages. The one thing that does not exist yet is bulk exporting (CSV/Excel across a
 * whole report); that tab says so plainly instead of pretending a download button
 * works. The only export that is real today - a candidate's certified result PDF - is
 * linked to where it already lives.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import { Badge, Button, Card, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { AdminStats } from "@/lib/types";

type Tab = "exams" | "candidates" | "proctoring" | "performance" | "export";

export default function ReportsPage() {
  const t = useTranslations("dashboard-detail");
  const { user } = useRequireAuth(["admin"]);
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab = (searchParams.get("tab") as Tab | null) ?? "exams";
  const [stats, setStats] = useState<AdminStats | null>(null);

  const TABS: { value: Tab; label: string }[] = [
    { value: "exams", label: t("exam_reports") },
    { value: "candidates", label: t("candidate_reports") },
    { value: "proctoring", label: t("proctoring_reports") },
    { value: "performance", label: t("performance_reports") },
    { value: "export", label: t("export_reports") },
  ];

  useEffect(() => {
    if (!user) return;
    api.get<AdminStats>("/admin/stats").then(setStats).catch(() => setStats(null));
  }, [user]);

  if (!user) return null;

  function setTab(next: Tab) {
    router.push(`/dashboard/admin/reports?tab=${next}`);
  }

  return (
    <div className="space-y-6">
      <Hero title="Reports" body="A platform-wide view over exams, candidates and proctoring, drawn from the same data every other page reads." />

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "exams" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("exam_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? `${stats.exams} exams on the platform, ${stats.live_exams} live right now, ${stats.completed_exams} completed.` : "Loading…"}
          </p>
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">Open the Exams list →</Button>
          </Link>
        </Card>
      )}

      {tab === "candidates" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("candidate_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? `${stats.candidates} registered candidates.` : "Loading…"} Attempts, completion and average scores are on the candidate roster.
          </p>
          <Link href="/dashboard/candidates">
            <Button variant="secondary" size="sm">Open the Candidate roster →</Button>
          </Link>
        </Card>
      )}

      {tab === "proctoring" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("proctoring_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? `${stats.flagged_sessions} sittings flagged for review across the platform.` : "Loading…"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/dashboard/proctoring">
              <Button variant="secondary" size="sm">Open Proctoring review →</Button>
            </Link>
            <Link href="/dashboard/live">
              <Button variant="secondary" size="sm">Open Live Console →</Button>
            </Link>
          </div>
        </Card>
      )}

      {tab === "performance" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("performance_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            Difficulty and topic breakdowns are computed per exam. Open an exam to see its analytics.
          </p>
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">Choose an exam →</Button>
          </Link>
        </Card>
      )}

      {tab === "export" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("export_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            Certified result PDFs are available today, one candidate at a time, from that
            candidate&apos;s own result. Platform-wide bulk exports (CSV/Excel across a
            whole report) are not built yet.
          </p>
          <ul className="space-y-2">
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-surface px-3.5 py-2.5">
              <span className="text-[13px] text-ink">Candidate result — PDF</span>
              <Badge tone="mint">{t("available")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">Exam report — CSV</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">Candidate roster — Excel</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">Proctoring report — PDF</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
          </ul>
        </Card>
      )}
    </div>
  );
}
