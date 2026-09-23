"use client";

/**
 * Detailed monitoring view for one candidate: the same big real video the grid tile
 * shows, plus the actual event timeline and suspicion breakdown already computed by
 * `GET /proctoring/sessions/{id}` - nothing here is invented, only laid out larger.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Button, Modal, ProgressBar, Skeleton, cx, formatDate, toast } from "@/components/ui";
import { EVENT_LABEL } from "@/app/dashboard/proctoring/[sessionId]/page";
import { ApiError, api } from "@/lib/api";
import type { LiveSessionRow, ProctorReview } from "@/lib/types";
import { useLiveView } from "@/lib/useLiveView";
import { severityOf } from "@/components/live/CandidateVideoTile";

export function CandidateDetailModal({
  row,
  onClose,
}: {
  row: LiveSessionRow | null;
  onClose: () => void;
}) {
  const [review, setReview] = useState<ProctorReview | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const { state, stream } = useLiveView(row?.session_id ?? null, Boolean(row));

  useEffect(() => {
    if (!row) {
      setReview(null);
      return;
    }
    setLoading(true);
    api
      .get<ProctorReview>(`/proctoring/sessions/${row.session_id}`)
      .then(setReview)
      .catch(() => setReview(null))
      .finally(() => setLoading(false));
  }, [row]);

  async function terminate() {
    if (!row) return;
    const reason = window.prompt("Reason for ending this session now?");
    if (!reason) return;
    setBusy(true);
    try {
      await api.post(
        `/proctoring/sessions/${row.session_id}/terminate?reason=${encodeURIComponent(reason)}`,
      );
      toast("Session ended", "rose");
      onClose();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not end this session", "rose");
    } finally {
      setBusy(false);
    }
  }

  const severity = row ? severityOf(row) : "normal";
  const recentEvents = review ? [...review.events].reverse().slice(0, 12) : [];

  return (
    <Modal open={Boolean(row)} onClose={onClose} title={row ? `Monitoring · ${row.candidate_name}` : ""} size="xl">
      {row && (
        <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
          <div>
            <div className="relative aspect-video w-full overflow-hidden rounded-[12px] bg-slate-900">
              {stream && state === "connected" ? (
                <video
                  ref={(el) => {
                    if (el) el.srcObject = stream;
                  }}
                  autoPlay
                  muted
                  playsInline
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-slate-500">
                  <span className="text-[13px] font-medium">
                    {state === "unavailable"
                      ? "Camera unavailable"
                      : state === "waiting-for-candidate"
                        ? "Waiting for the candidate's camera"
                        : "Connecting…"}
                  </span>
                </div>
              )}
              <div className="absolute left-3 top-3">
                <span
                  className={cx(
                    "inline-flex items-center gap-1.5 rounded-full bg-ink/70 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide backdrop-blur-sm",
                    state === "connected" ? "text-cyan-300" : state === "reconnecting" ? "text-amber-300" : "text-slate-300",
                  )}
                >
                  <span
                    className={cx(
                      "h-1.5 w-1.5 rounded-full",
                      state === "connected" ? "bg-cyan-400 animate-pulse" : state === "reconnecting" ? "bg-amber animate-pulse" : "bg-slate-400",
                    )}
                  />
                  {state === "connected" ? "LIVE" : state === "reconnecting" ? "Reconnecting…" : "Not connected"}
                </span>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[13.5px] font-semibold text-ink">{row.exam_title}</p>
                <p className="text-[12px] text-ink-muted">Time remaining: {row.time_remaining_str}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`/dashboard/proctoring/${row.session_id}`}>
                  <Button size="sm" variant="secondary">Full review</Button>
                </Link>
                {review?.status === "in_progress" && (
                  <Button size="sm" variant="danger" loading={busy} onClick={() => void terminate()}>
                    End session
                  </Button>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-muted">AI Suspicion</p>
              <div className="mb-1 flex items-center justify-between text-[13px]">
                <span className="text-ink-soft">Score</span>
                <span className="font-semibold text-ink">{row.suspicion_score}%</span>
              </div>
              <ProgressBar
                value={row.suspicion_score}
                tone={severity === "critical" || severity === "flagged" ? "rose" : severity === "warning" ? "amber" : "mint"}
              />
              <div className="mt-2">
                {severity === "normal" ? (
                  <Badge tone="mint">Normal</Badge>
                ) : severity === "warning" ? (
                  <Badge tone="amber">Needs attention</Badge>
                ) : (
                  <Badge tone="rose">{severity === "flagged" ? "Flagged" : "Critical"}</Badge>
                )}
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-ink-muted">Event timeline</p>
              {loading ? (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-10 rounded-[8px]" />
                  ))}
                </div>
              ) : recentEvents.length === 0 ? (
                <p className="text-[12.5px] text-ink-muted">No proctoring events recorded yet.</p>
              ) : (
                <ul className="max-h-[280px] space-y-2 overflow-y-auto pr-1">
                  {recentEvents.map((event) => (
                    <li key={event.id} className="flex items-start gap-2 rounded-[8px] border border-line bg-sunken/40 px-2.5 py-2">
                      <span
                        className={cx(
                          "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                          event.severity === "critical" ? "bg-rose" : event.severity === "warning" ? "bg-amber" : "bg-accent",
                        )}
                      />
                      <div className="min-w-0">
                        <p className="truncate text-[12.5px] font-medium text-ink">
                          {EVENT_LABEL[event.event_type] ?? event.event_type}
                        </p>
                        <p className="text-[11px] text-ink-muted">{formatDate(event.occurred_at)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}
