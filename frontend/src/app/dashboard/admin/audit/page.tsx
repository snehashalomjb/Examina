"use client";

/**
 * A lightweight audit trail.
 *
 * There is no dedicated AuditLog table in this platform - this reuses
 * `GET /admin/activity`, the same merged feed (registrations, sittings, published
 * results) the admin dashboard's "Recent Activity" panel already shows, just at a
 * larger page size and its own screen. Only the columns the data actually has -
 * timestamp, a description of what happened, and a severity - are shown; nothing here
 * invents a user/role/resource breakdown the endpoint doesn't return.
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import { Alert, Badge, Button, Card, EmptyState, Skeleton, formatDate } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Activity } from "@/lib/types";

export default function AuditLogsPage() {
  const t = useTranslations("dashboard-detail");
  const { user } = useRequireAuth(["admin"]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setActivity(await api.get<Activity[]>("/admin/activity?limit=50"));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load the audit log.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="Audit Logs"
        body="Registrations, sittings and published results, newest first - the same feed the dashboard's activity panel reads from."
        action={
          <Button variant="secondary" size="sm" loading={refreshing} onClick={() => void load()}>
            Refresh
          </Button>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-[10px]" />
            ))}
          </div>
        ) : activity.length === 0 ? (
          <EmptyState title="Nothing recorded yet" body="Platform events will appear here as the system is used." />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[640px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="pb-2 pr-3 font-medium">{t("timestamp")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("event")}</th>
                  <th className="pb-2 font-medium">{t("severity")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {activity.map((item, index) => (
                  <tr key={index}>
                    <td className="py-3 pr-3 whitespace-nowrap text-[12.5px] text-ink-muted">
                      {formatDate(item.at)}
                    </td>
                    <td className="py-3 pr-3 text-[13.5px] text-ink">{item.message}</td>
                    <td className="py-3">
                      <Badge
                        tone={
                          item.severity === "critical"
                            ? "rose"
                            : item.severity === "warning"
                              ? "amber"
                              : "neutral"
                        }
                      >
                        {item.severity}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
