"use client";

/**
 * System Health.
 *
 * Two components here are genuinely probed on every load - the database (a real
 * query) and object storage (a real bucket check). The other three - the API,
 * WebSocket routes, and AI proctoring - have no server-side signal to poll: the API's
 * own answer proves it is up, and the proctoring/live-signal sockets and the vision
 * model are per-session and client-driven, not something a health check can dial into.
 * Those are labelled "configured" rather than "operational" so the page never claims a
 * live measurement it did not take - see `basis` on each row.
 */

import { useCallback, useEffect, useState } from "react";

import { Hero } from "@/components/Hero";
import { Alert, Badge, Button, Card, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ComponentHealth, SystemHealth } from "@/lib/types";

const ROWS: { key: keyof SystemHealth; label: string; hint: string }[] = [
  { key: "api", label: "API", hint: "This request answering at all is the check." },
  { key: "database", label: "Database", hint: "A live query against Postgres." },
  { key: "storage", label: "Storage", hint: "A live check against the object store." },
  { key: "websocket", label: "WebSocket", hint: "Proctoring + live-monitoring sockets are registered routes." },
  { key: "ai_proctoring", label: "AI Proctoring", hint: "Vision inference runs in the candidate's browser during a sitting." },
  { key: "authentication", label: "Authentication", hint: "This page only loaded because a valid admin token was verified." },
];

function statusTone(status: string): "mint" | "amber" | "rose" | "neutral" {
  if (["operational", "enabled"].includes(status)) return "mint";
  if (["disabled"].includes(status)) return "neutral";
  if (["unavailable", "degraded"].includes(status)) return "rose";
  return "amber";
}

export default function SystemHealthPage() {
  const { user } = useRequireAuth(["admin"]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setHealth(await api.get<SystemHealth>("/admin/system-health"));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load system health.");
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
        title="System Health"
        body="What is actually checkable from the server, and nothing invented for what isn't."
        action={
          <Button variant="secondary" size="sm" loading={refreshing} onClick={() => void load()}>
            Refresh
          </Button>
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {loading || !health
          ? Array.from({ length: 6 }).map((_, i) => (
              <Card key={i}>
                <Skeleton className="mb-3 h-3 w-24" />
                <Skeleton className="h-6 w-32" />
              </Card>
            ))
          : ROWS.map((row) => {
              const component = health[row.key] as ComponentHealth;
              return (
                <Card key={row.key}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[13.5px] font-semibold text-ink">{row.label}</p>
                    <Badge tone={statusTone(component.status)}>{component.status}</Badge>
                  </div>
                  <p className="mt-2 text-[12px] text-ink-muted">
                    {component.detail ?? row.hint}
                  </p>
                  <p className="mt-2 text-[10.5px] font-medium uppercase tracking-wide text-ink-placeholder">
                    {component.basis === "checked" ? "Live check" : "Configuration"}
                  </p>
                </Card>
              );
            })}
      </div>
    </div>
  );
}
