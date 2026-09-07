"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ProgressBar,
  SectionTitle,
  Skeleton,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { ProctorEvent, ProctorReview } from "@/lib/types";

const EVENT_LABEL: Record<string, string> = {
  face_missing: "Face not visible",
  multiple_faces: "Multiple people detected",
  gaze_away: "Looking away from screen",
  tab_switch: "Left the exam tab",
  window_blur: "Window lost focus",
  fullscreen_exit: "Exited fullscreen",
  camera_blocked: "Camera blocked",
  paste_attempt: "Paste attempt",
  copy_attempt: "Copy attempt",
  devtools_open: "Developer tools opened",
};

export default function ProctorReviewPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const params = useParams<{ sessionId: string }>();
  const [review, setReview] = useState<ProctorReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<ProctorEvent | null>(null);

  const load = useCallback(async () => {
    try {
      setReview(await api.get<ProctorReview>(`/proctoring/sessions/${params.sessionId}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load this session.");
    } finally {
      setLoading(false);
    }
  }, [params.sessionId]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function terminate() {
    const reason = window.prompt("Reason for terminating this session?");
    if (!reason) return;
    try {
      await api.post(
        `/proctoring/sessions/${params.sessionId}/terminate?reason=${encodeURIComponent(reason)}`,
      );
      toast("Session terminated", "rose");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not terminate", "rose");
    }
  }

  if (!user) return null;

  const snapshots = review?.events.filter((event) => event.snapshot_url) ?? [];
  const maxWeight = Math.max(1, ...Object.values(review?.breakdown ?? { none: 1 }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Link href="/dashboard/proctoring">
          <Button variant="secondary" size="sm">
            ← All sessions
          </Button>
        </Link>
        {review?.status === "in_progress" && (
          <Button variant="danger" size="sm" onClick={terminate}>
            Terminate session
          </Button>
        )}
      </div>

      {error && <Alert tone="rose">{error}</Alert>}

      {loading ? (
        <div className="space-y-4">
          <Skeleton className="h-[110px] rounded-[16px]" />
          <Skeleton className="h-[320px] rounded-[14px]" />
        </div>
      ) : review ? (
        <>
          <Hero
            title={review.candidate_name}
            body={`${review.exam_title} · ${review.candidate_email} · started ${formatDate(review.started_at)}`}
          />

          <div className="grid gap-4 sm:grid-cols-4">
            <Card>
              <p className="text-[12px] uppercase tracking-wide text-ink-muted">Suspicion score</p>
              <p
                className={cx(
                  "mt-1.5 text-[26px] font-semibold leading-none",
                  review.suspicion_score >= 60
                    ? "text-rose"
                    : review.suspicion_score >= 25
                      ? "text-amber"
                      : "text-mint",
                )}
              >
                {review.suspicion_score}
              </p>
            </Card>
            <Card>
              <p className="text-[12px] uppercase tracking-wide text-ink-muted">Tab switches</p>
              <p className="mt-1.5 text-[26px] font-semibold leading-none text-ink">
                {review.tab_switch_count}
              </p>
            </Card>
            <Card>
              <p className="text-[12px] uppercase tracking-wide text-ink-muted">Events</p>
              <p className="mt-1.5 text-[26px] font-semibold leading-none text-ink">
                {review.events.length}
              </p>
            </Card>
            <Card>
              <p className="text-[12px] uppercase tracking-wide text-ink-muted">Status</p>
              <p className="mt-2 flex flex-wrap gap-1.5">
                <Badge
                  tone={
                    review.status === "in_progress"
                      ? "accent"
                      : review.status === "terminated"
                        ? "rose"
                        : "neutral"
                  }
                >
                  {review.status.replace("_", " ")}
                </Badge>
                {review.is_flagged && <Badge tone="rose">flagged</Badge>}
              </p>
            </Card>
          </div>

          {review.termination_reason && (
            <Alert tone="rose" title="Termination">
              {review.termination_reason}
            </Alert>
          )}

          <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
            {/* -------------------------------------------------- timeline */}
            <Card>
              <SectionTitle
                title="Event timeline"
                hint="Ordered by when it happened on the candidate's machine; the server timestamps arrival separately."
              />
              {review.events.length === 0 ? (
                <EmptyState
                  title="Clean session"
                  body="No proctoring events were recorded for this sitting."
                />
              ) : (
                <ol className="relative space-y-3 pl-5">
                  <span className="absolute left-[4px] top-2 bottom-2 w-px bg-line" />
                  {review.events.map((event) => (
                    <li key={event.id} className="relative">
                      <span
                        className={cx(
                          "absolute -left-5 top-1.5 h-2 w-2 rotate-45",
                          event.severity === "critical"
                            ? "bg-rose"
                            : event.severity === "warning"
                              ? "bg-amber"
                              : "bg-accent",
                        )}
                      />
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[13px] font-medium text-ink">
                          {EVENT_LABEL[event.event_type] ?? event.event_type}
                        </p>
                        <Badge
                          tone={
                            event.severity === "critical"
                              ? "rose"
                              : event.severity === "warning"
                                ? "amber"
                                : "neutral"
                          }
                        >
                          {event.severity}
                        </Badge>
                        {event.weight > 0 && <Badge>+{event.weight}</Badge>}
                        {event.snapshot_url && (
                          <button
                            onClick={() => setLightbox(event)}
                            className="text-[12px] font-medium text-accent hover:text-accent-ink"
                          >
                            View snapshot
                          </button>
                        )}
                      </div>
                      <p className="text-[11.5px] text-ink-muted">
                        {formatDate(event.occurred_at)}
                        {event.duration_ms ? ` · ${Math.round(event.duration_ms / 1000)}s` : ""}
                        {event.metadata ? ` · ${JSON.stringify(event.metadata)}` : ""}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </Card>

            {/* --------------------------------------------------- side panel */}
            <div className="space-y-5">
              <Card>
                <SectionTitle title="Score breakdown" hint="What contributed, and by how much." />
                {Object.keys(review.breakdown).length === 0 ? (
                  <p className="text-[13px] text-ink-muted">Nothing contributed to the score.</p>
                ) : (
                  <ul className="space-y-3">
                    {Object.entries(review.breakdown)
                      .sort((a, b) => b[1] - a[1])
                      .map(([type, weight]) => (
                        <li key={type}>
                          <div className="mb-1 flex justify-between text-[12.5px]">
                            <span className="text-ink-soft">{EVENT_LABEL[type] ?? type}</span>
                            <span className="font-medium text-ink">{weight}</span>
                          </div>
                          <ProgressBar
                            value={(weight / maxWeight) * 100}
                            tone={weight > 20 ? "rose" : weight > 8 ? "amber" : "accent"}
                          />
                        </li>
                      ))}
                  </ul>
                )}
              </Card>

              <Card>
                <SectionTitle
                  title="Snapshots"
                  hint={`${snapshots.length} frame${snapshots.length === 1 ? "" : "s"} stored`}
                />
                {snapshots.length === 0 ? (
                  <p className="text-[13px] text-ink-muted">
                    No webcam frames were captured for this session.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {snapshots.slice(0, 8).map((event) => (
                      <button
                        key={event.id}
                        onClick={() => setLightbox(event)}
                        className="overflow-hidden rounded-[9px] border border-line transition hover:border-accent"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={event.snapshot_url!}
                          alt={`Snapshot at ${formatDate(event.occurred_at)}`}
                          className="h-20 w-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      ) : null}

      {lightbox?.snapshot_url && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/60 p-6 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <div className="animate-rise max-w-2xl" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={lightbox.snapshot_url}
              alt="Proctoring snapshot"
              className="max-h-[70vh] w-full rounded-[12px] object-contain"
            />
            <div className="mt-3 flex items-center justify-between gap-3 rounded-[10px] bg-surface px-4 py-2.5">
              <div>
                <p className="text-[13px] font-medium text-ink">
                  {EVENT_LABEL[lightbox.event_type] ?? lightbox.event_type}
                </p>
                <p className="text-[12px] text-ink-muted">{formatDate(lightbox.occurred_at)}</p>
              </div>
              <Button size="sm" variant="secondary" onClick={() => setLightbox(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
