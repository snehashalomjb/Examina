"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  Skeleton,
  cx,
  formatDate,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ProctorReview } from "@/lib/types";

const REFRESH_MS = 20_000;

export default function ProctoringPage() {
  const t = useTranslations("proctoring");
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [sessions, setSessions] = useState<ProctorReview[]>([]);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setSessions(
        await api.get<ProctorReview[]>(`/proctoring/sessions?flagged_only=${flaggedOnly}`),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load proctoring data.");
    } finally {
      setLoading(false);
    }
  }, [flaggedOnly]);

  useEffect(() => {
    if (!user) return;
    void load();
    // Live sittings move; a quiet poll keeps the panel honest without a socket.
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [user, load]);

  if (!user) return null;

  const live = sessions.filter((s) => s.status === "in_progress");
  const flagged = sessions.filter((s) => s.is_flagged);

  return (
    <div className="space-y-6">
      <Hero
        title={t("hero_proctoring")}
        body={t("hero_body_suspicion_scores")}
        action={
          <Button
            size="sm"
            variant={flaggedOnly ? "primary" : "secondary"}
            onClick={() => setFlaggedOnly((v) => !v)}
          >
            {flaggedOnly ? t("button_showing_flagged_only") : t("button_show_flagged_only")}
          </Button>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <p className="text-[12px] uppercase tracking-wide text-ink-muted">{t("stat_live_now")}</p>
          <p className="mt-1.5 text-[26px] font-semibold leading-none text-ink">{live.length}</p>
        </Card>
        <Card>
          <p className="text-[12px] uppercase tracking-wide text-ink-muted">{t("stat_flagged")}</p>
          <p
            className={cx(
              "mt-1.5 text-[26px] font-semibold leading-none",
              flagged.length ? "text-rose" : "text-ink",
            )}
          >
            {flagged.length}
          </p>
        </Card>
        <Card>
          <p className="text-[12px] uppercase tracking-wide text-ink-muted">{t("stat_sessions_listed")}</p>
          <p className="mt-1.5 text-[26px] font-semibold leading-none text-ink">{sessions.length}</p>
        </Card>
      </div>

      <Card>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-[12px]" />
            ))}
          </div>
        ) : sessions.length === 0 ? (
          <EmptyState
            title={flaggedOnly ? t("empty_nothing_flagged") : t("empty_no_sittings_recorded")}
            body={
              flaggedOnly
                ? t("empty_body_no_flagging_threshold")
                : t("empty_body_sessions_appear")
            }
          />
        ) : (
          <ul className="divide-y divide-line">
            {sessions.map((session) => {
              const severity =
                session.suspicion_score >= 60
                  ? "rose"
                  : session.suspicion_score >= 25
                    ? "amber"
                    : "mint";
              return (
                <li key={session.session_id} className="flex flex-wrap items-center gap-4 py-3">
                  <div className="min-w-[180px] flex-1">
                    <p className="truncate text-[13.5px] font-medium text-ink">
                      {session.candidate_name}
                    </p>
                    <p className="truncate text-[12px] text-ink-muted">
                      {session.exam_title} · started {formatDate(session.started_at)}
                    </p>
                  </div>

                  <div className="w-[150px]">
                    <div className="mb-1 flex justify-between text-[11.5px]">
                      <span className="text-ink-muted">{t("label_suspicion")}</span>
                      <span className="font-medium text-ink">{session.suspicion_score}</span>
                    </div>
                    <ProgressBar value={Math.min(100, session.suspicion_score)} tone={severity} />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Badge
                      tone={
                        session.status === "in_progress"
                          ? "accent"
                          : session.status === "terminated"
                            ? "rose"
                            : "neutral"
                      }
                    >
                      {session.status.replace("_", " ")}
                    </Badge>
                    {session.is_flagged && <Badge tone="rose">flagged</Badge>}
                    {session.focus_violation_count > 0 && (
                      <Badge tone="rose">
                        left exam {session.focus_violation_count}×
                      </Badge>
                    )}
                    {session.tab_switch_count > 0 && (
                      <Badge tone="amber">{session.tab_switch_count} tab</Badge>
                    )}
                  </div>

                  <Link href={`/dashboard/proctoring/${session.session_id}`}>
                    <Button size="sm" variant="secondary">
                      Review
                    </Button>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
