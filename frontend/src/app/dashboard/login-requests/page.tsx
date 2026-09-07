"use client";

import { useCallback, useEffect, useState } from "react";

import { Hero } from "@/components/Hero";
import { Avatar } from "@/components/Avatar";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  SectionTitle,
  Skeleton,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { IconCheck, IconHourglass, IconAlert } from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { LoginAccessStatus, LoginRequestRow } from "@/lib/types";

const TABS: { key: LoginAccessStatus | "all"; label: string }[] = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
  { key: "all", label: "All" },
];

const TONE: Record<LoginAccessStatus, "amber" | "mint" | "rose"> = {
  pending: "amber",
  approved: "mint",
  rejected: "rose",
};

/**
 * Candidate login requests.
 *
 * Shown to administrators and examiners alike. The backend narrows the list before it
 * arrives: an administrator sees every candidate, an examiner sees only candidates
 * enrolled in one of their own exams, and the exams that grant that authority are shown
 * on each row so the basis for deciding is never a mystery.
 */
export default function LoginRequestsPage() {
  const { user } = useRequireAuth(["admin", "examiner"]);
  const [rows, setRows] = useState<LoginRequestRow[]>([]);
  const [tab, setTab] = useState<LoginAccessStatus | "all">("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const query = tab === "all" ? "" : `?status=${tab}`;
      setRows(await api.get<LoginRequestRow[]>(`/login-requests${query}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load login requests.");
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function decide(row: LoginRequestRow, approve: boolean) {
    setBusyId(row.id);
    try {
      await api.post(`/login-requests/${row.id}/${approve ? "approve" : "reject"}`, {
        note: notes[row.id]?.trim() || null,
      });
      toast(
        approve
          ? `${row.first_name} can now use the platform`
          : `${row.first_name}'s access was ${row.status === "approved" ? "revoked" : "refused"}`,
        approve ? "mint" : "amber",
      );
      setNotes((current) => ({ ...current, [row.id]: "" }));
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not record the decision", "rose");
    } finally {
      setBusyId(null);
    }
  }

  if (!user) return null;

  const pendingCount = rows.filter((r) => r.status === "pending").length;

  return (
    <div className="space-y-6">
      <Hero
        title="Candidate login requests"
        body={
          user.role === "admin"
            ? "Every candidate who has tried to sign in. Their account is already active — what you are deciding is whether they may use the platform."
            : "Candidates enrolled in your examinations. You can decide access for them; candidates outside your papers are an administrator's call."
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <div className="inline-flex rounded-[10px] border border-line bg-sunken p-1">
            {TABS.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => {
                  setLoading(true);
                  setTab(item.key);
                }}
                className={cx(
                  "rounded-[7px] px-3 py-1.5 text-[12.5px] font-medium transition",
                  tab === item.key
                    ? "bg-surface text-ink shadow-[var(--shadow-soft)]"
                    : "text-ink-muted hover:text-ink",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>

          {tab === "pending" && pendingCount > 0 && (
            <Badge tone="amber">
              <IconHourglass size={12} />
              {pendingCount} awaiting a decision
            </Badge>
          )}
        </div>

        <div className="p-4">
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-[12px]" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              title={tab === "pending" ? "Nothing waiting" : "Nothing here"}
              body={
                user.role === "examiner"
                  ? "Candidates appear once they are enrolled in one of your examinations and have tried to sign in."
                  : "Candidate login requests will appear here as people register and sign in."
              }
            />
          ) : (
            <ul className="space-y-3">
              {rows.map((row) => (
                <li
                  key={row.id}
                  className="rounded-[12px] border border-line p-4 transition hover:border-line-strong"
                >
                  <div className="flex flex-wrap items-start gap-3">
                    <Avatar name={row.full_name} size={40} />

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[14px] font-semibold text-ink">{row.full_name}</p>
                        <Badge tone={TONE[row.status]}>{row.status}</Badge>
                      </div>
                      <p className="mt-0.5 text-[12.5px] text-ink-muted">{row.email}</p>
                      <p className="mt-1 text-[12px] text-ink-muted">
                        Requested {formatDate(row.requested_at)}
                        {row.reviewed_at && row.reviewed_by_name && (
                          <> · decided by {row.reviewed_by_name} on {formatDate(row.reviewed_at)}</>
                        )}
                      </p>

                      {row.enrolled_exams.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {row.enrolled_exams.map((title) => (
                            <Badge key={title}>{title}</Badge>
                          ))}
                        </div>
                      )}

                      {row.review_note && (
                        <p className="mt-2 rounded-[8px] bg-sunken/70 px-3 py-2 text-[12.5px] text-ink-soft">
                          “{row.review_note}”
                        </p>
                      )}
                    </div>

                    <div className="w-full sm:w-auto sm:min-w-[260px]">
                      <Field label="Note (optional)">
                        <Input
                          value={notes[row.id] ?? ""}
                          onChange={(e) =>
                            setNotes((current) => ({ ...current, [row.id]: e.target.value }))
                          }
                          placeholder="Shown to the candidate"
                        />
                      </Field>
                      <div className="mt-2 flex justify-end gap-2">
                        {row.status !== "approved" && (
                          <Button
                            size="sm"
                            loading={busyId === row.id}
                            onClick={() => decide(row, true)}
                          >
                            <IconCheck size={14} />
                            Approve
                          </Button>
                        )}
                        {row.status !== "rejected" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            loading={busyId === row.id}
                            onClick={() => decide(row, false)}
                          >
                            <IconAlert size={14} />
                            {row.status === "approved" ? "Revoke" : "Reject"}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card>
        <SectionTitle title="How this works" hint="Two separate ideas, deliberately." />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-[11px] border border-line p-4">
            <p className="text-[13px] font-semibold text-ink">Account</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-soft">
              Created active the moment a candidate registers. Registration is open and
              needs nobody&apos;s approval.
            </p>
          </div>
          <div className="rounded-[11px] border border-line p-4">
            <p className="text-[13px] font-semibold text-ink">Login access</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-soft">
              Requested automatically at their first sign-in and decided here. Approved
              once, it stays approved for every later login unless it is revoked.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
