"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { useNotifications, type AppNotification } from "@/lib/useNotifications";

function BellIcon({ size = 16, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/**
 * The submission-notification bell shown to examiners and admins. Separate from the
 * "Login Requests" bell icon already in the header - that one is a static shortcut to a
 * dedicated page, this one is a live, per-recipient list backed by `useNotifications`.
 */
export function NotificationBell() {
  const { items, unreadCount, markRead } = useNotifications(true);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (open && rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function openSubmission(notification: AppNotification) {
    if (!notification.is_read) void markRead(notification.id);
    setOpen(false);
    if (notification.result_id) {
      router.push(`/results/${notification.result_id}`);
    }
  }

  return (
    <div ref={rootRef} className="relative hidden lg:block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        title="Notifications"
        aria-haspopup="menu"
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center rounded-full transition hover:bg-white/5"
        style={{ color: "var(--color-sidebar-text)" }}
      >
        <BellIcon size={16} />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold leading-none text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-11 z-50 w-80 overflow-hidden rounded-2xl border border-black/10 bg-white/95 shadow-2xl"
          style={{ backdropFilter: "blur(20px) saturate(160%)", WebkitBackdropFilter: "blur(20px) saturate(160%)" }}
        >
          <div className="border-b border-black/5 px-4 py-3 text-[13px] font-semibold text-ink">
            Notifications
          </div>
          <div className="max-h-96 overflow-y-auto p-1.5">
            {items.length === 0 && (
              <p className="px-4 py-6 text-center text-[13px] text-ink-muted">
                No notifications yet.
              </p>
            )}
            {items.map((notification) => (
              <button
                key={notification.id}
                type="button"
                onClick={() => openSubmission(notification)}
                className={cx(
                  "block w-full rounded-xl px-3.5 py-3 text-left transition hover:bg-black/[0.03]",
                  !notification.is_read && "bg-blue-50/60"
                )}
              >
                <p className="text-[13px] font-semibold text-ink">{notification.title}</p>
                <p className="mt-0.5 whitespace-pre-line text-[12px] text-ink-muted">
                  {notification.body}
                </p>
                <div className="mt-1.5 flex items-center justify-between">
                  <span className="text-[11px] text-ink-muted">
                    {timeAgo(notification.created_at)}
                  </span>
                  {notification.result_id && (
                    <span className="text-[11px] font-medium text-blue-600">
                      View Submission &rarr;
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
