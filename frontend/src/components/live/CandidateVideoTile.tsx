"use client";

/**
 * One candidate's monitoring tile: real WebRTC video when connected, an honest
 * connecting/waiting/unavailable state otherwise. Never a static image dressed up as
 * "LIVE" - see `useLiveView`, which this only renders the state of.
 */

import { useEffect, useRef } from "react";

import { Badge, ProgressBar, cx } from "@/components/ui";
import { useLiveView } from "@/lib/useLiveView";
import type { LiveSessionRow } from "@/lib/types";

export function severityOf(row: LiveSessionRow): "critical" | "warning" | "flagged" | "normal" {
  if (row.is_flagged) return "flagged";
  if (row.suspicion_score >= 60) return "critical";
  if (row.suspicion_score >= 25) return "warning";
  return "normal";
}

function ConnectionChip({ state }: { state: ReturnType<typeof useLiveView>["state"] }) {
  const map = {
    connecting: { label: "Connecting…", dot: "bg-cyan-400 animate-pulse", text: "text-cyan-300" },
    "waiting-for-candidate": { label: "Waiting for camera", dot: "bg-slate-400", text: "text-slate-300" },
    connected: { label: "LIVE", dot: "bg-cyan-400 animate-pulse", text: "text-cyan-300" },
    reconnecting: { label: "Reconnecting…", dot: "bg-amber animate-pulse", text: "text-amber-300" },
    unavailable: { label: "Camera unavailable", dot: "bg-rose", text: "text-rose-300" },
  } as const;
  const s = map[state];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full bg-ink/70 px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide backdrop-blur-sm",
        s.text,
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}

export function CandidateVideoTile({
  row,
  monitor,
  onOpen,
}: {
  row: LiveSessionRow;
  /** Only establish a peer connection while the tile is actually on screen. */
  monitor: boolean;
  onOpen: () => void;
}) {
  const { state, stream } = useLiveView(row.session_id, monitor);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const severity = severityOf(row);

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream;
  }, [stream]);

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cx(
        "group relative flex flex-col overflow-hidden rounded-[14px] border bg-ink text-left shadow-sm transition hover:shadow-md",
        severity === "critical" || severity === "flagged" ? "border-rose ring-1 ring-rose/40" : "border-line",
      )}
    >
      <div className="relative aspect-[4/3] w-full overflow-hidden bg-slate-900">
        {stream && state === "connected" ? (
          <video ref={videoRef} autoPlay muted playsInline className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-[radial-gradient(circle_at_center,#1e293b,#0f172a)] text-slate-500">
            <CameraIcon />
            <span className="text-[11px] font-medium">
              {state === "unavailable" ? "Camera unavailable" : state === "waiting-for-candidate" ? "No camera yet" : "Connecting…"}
            </span>
          </div>
        )}

        {/* subtle technical grid overlay, not a gaming glow */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.06] [background-image:linear-gradient(to_right,white_1px,transparent_1px),linear-gradient(to_bottom,white_1px,transparent_1px)] [background-size:24px_24px]" />

        <div className="absolute left-2.5 top-2.5 flex items-center gap-1.5">
          <ConnectionChip state={state} />
        </div>
        {severity !== "normal" && (
          <div className="absolute right-2.5 top-2.5">
            <span
              className={cx(
                "rounded-full px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide backdrop-blur-sm",
                severity === "warning" ? "bg-amber/80 text-white" : "bg-rose/85 text-white",
              )}
            >
              {severity === "warning" ? "⚠ Warning" : "⚠ Flagged"}
            </span>
          </div>
        )}

        <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-end justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[12.5px] font-semibold text-white">{row.candidate_name}</p>
            <p className="truncate text-[10.5px] text-slate-300">#{row.session_id.slice(0, 8)}</p>
          </div>
          <span className="shrink-0 rounded-[6px] bg-black/50 px-1.5 py-0.5 font-mono text-[11px] text-white">
            {row.time_remaining_str}
          </span>
        </div>
      </div>

      <div className="space-y-2 bg-surface p-3">
        <p className="truncate text-[12px] text-ink-muted">
          {row.exam_title} · Q{row.answered_count}/{row.total_questions}
        </p>
        <div>
          <div className="mb-1 flex items-center justify-between text-[11px]">
            <span className="font-medium uppercase tracking-wide text-ink-muted">AI Suspicion</span>
            <span className="font-semibold text-ink">{row.suspicion_score}%</span>
          </div>
          <ProgressBar
            value={row.suspicion_score}
            size="xs"
            tone={severity === "critical" || severity === "flagged" ? "rose" : severity === "warning" ? "amber" : "mint"}
          />
        </div>
        <div>
          {severity === "normal" ? (
            <Badge tone="mint">Normal</Badge>
          ) : severity === "warning" ? (
            <Badge tone="amber">Needs attention</Badge>
          ) : (
            <Badge tone="rose">{severity === "flagged" ? "Flagged" : "Critical"}</Badge>
          )}
        </div>
      </div>
    </button>
  );
}

function CameraIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="6" width="15" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M17 10l5-3v10l-5-3" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}
