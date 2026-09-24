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
  const ta = useTranslations("adminShell");
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
      <Hero title={ta("reports_title")} body={ta("reports_body")} />

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "exams" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("exam_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? ta("reports_exams_summary", { exams: stats.exams, live: stats.live_exams, completed: stats.completed_exams }) : ta("loading")}
          </p>
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">{ta("open_exams_list")}</Button>
          </Link>
        </Card>
      )}

      {tab === "candidates" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("candidate_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? ta("reports_candidates_summary", { count: stats.candidates }) : ta("loading")}{" "}
            {ta("reports_candidates_note")}
          </p>
          <Link href="/dashboard/candidates">
            <Button variant="secondary" size="sm">{ta("open_candidate_roster")}</Button>
          </Link>
        </Card>
      )}

      {tab === "proctoring" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("proctoring_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {stats ? ta("reports_flagged_summary", { count: stats.flagged_sessions }) : ta("loading")}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link href="/dashboard/proctoring">
              <Button variant="secondary" size="sm">{ta("open_proctoring_review")}</Button>
            </Link>
            <Link href="/dashboard/live">
              <Button variant="secondary" size="sm">{ta("open_live_console")}</Button>
            </Link>
          </div>
        </Card>
      )}

      {tab === "performance" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("performance_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {ta("reports_performance_body")}
          </p>
          <Link href="/dashboard/exams">
            <Button variant="secondary" size="sm">{ta("choose_exam")}</Button>
          </Link>
        </Card>
      )}

      {tab === "export" && (
        <Card>
          <h2 className="mb-1 text-[15px] font-semibold text-ink">{t("export_reports")}</h2>
          <p className="mb-4 text-[13px] text-ink-muted">
            {ta("reports_export_body")}
          </p>
          <ul className="space-y-2">
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-surface px-3.5 py-2.5">
              <span className="text-[13px] text-ink">{ta("export_candidate_result_pdf")}</span>
              <Badge tone="mint">{t("available")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">{ta("export_exam_report_csv")}</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">{ta("export_candidate_roster_excel")}</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
            <li className="flex items-center justify-between rounded-[10px] border border-line bg-sunken/50 px-3.5 py-2.5 opacity-70">
              <span className="text-[13px] text-ink-muted">{ta("export_proctoring_report_pdf")}</span>
              <Badge tone="neutral">{t("coming_soon")}</Badge>
            </li>
          </ul>
        </Card>
      )}
    </div>
  );
}
