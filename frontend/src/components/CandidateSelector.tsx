"use client";

/**
 * Assign candidates to an exam.
 *
 * Two permissions are in play and they are not the same thing: an account can exist
 * without being allowed to sign in. A candidate whose login access is still pending
 * can be assigned - the exam simply waits for them - but the UI says so plainly,
 * because "I assigned them and they cannot see it" is otherwise a mystery.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Skeleton,
  Textarea,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { CandidateRow, EnrollmentRow, LoginAccessStatus } from "@/lib/types";

const ACCESS_TONE: Record<LoginAccessStatus, "mint" | "amber" | "rose"> = {
  approved: "mint",
  pending: "amber",
  rejected: "rose",
};

export interface CandidateSelectorProps {
  examId: string | null;
  /** Kept in step with the parent so the review step can show the count. */
  onChange?: (assignedCount: number) => void;
}

export function CandidateSelector({ examId, onChange }: CandidateSelectorProps) {
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [assigned, setAssigned] = useState<EnrollmentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [approvedOnly, setApprovedOnly] = useState(true);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [pasted, setPasted] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [roster, enrolled] = await Promise.all([
        api.get<CandidateRow[]>(
          `/admin/candidates${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`,
        ),
        examId
          ? api.get<EnrollmentRow[]>(`/exams/${examId}/enrollments`)
          : Promise.resolve([] as EnrollmentRow[]),
      ]);
      setCandidates(roster);
      setAssigned(enrolled);
      onChange?.(enrolled.length);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load candidates.");
    } finally {
      setLoading(false);
    }
    // onChange is a callback the parent recreates freely; depending on it would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId, search]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, search]);

  const assignedIds = useMemo(() => new Set(assigned.map((row) => row.candidate_id)), [assigned]);

  const shown = useMemo(
    () =>
      candidates.filter((candidate) => {
        if (assignedIds.has(candidate.id)) return false;
        if (approvedOnly && candidate.login_access !== "approved") return false;
        return true;
      }),
    [candidates, assignedIds, approvedOnly],
  );

  async function assign(ids: string[]) {
    if (!examId || !ids.length) return;
    setBusy(true);
    try {
      const response = await api.post<{ detail: string }>(`/exams/${examId}/enrollments`, {
        candidate_ids: ids,
      });
      toast(response.detail, "mint");
      setSelected([]);
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not assign those candidates.", "rose");
    } finally {
      setBusy(false);
    }
  }

  async function unassign(candidateId: string) {
    if (!examId) return;
    setBusy(true);
    try {
      await api.delete(`/exams/${examId}/enrollments/${candidateId}`);
      await load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not remove that candidate.", "rose");
    } finally {
      setBusy(false);
    }
  }

  /**
   * Assign from a pasted list of emails.
   *
   * Emails that match nothing are reported rather than ignored: a typo in a roster
   * paste is exactly the case where silence means a candidate misses their exam.
   */
  function assignPasted() {
    const wanted = pasted
      .split(/[\s,;]+/)
      .map((token) => token.trim().toLowerCase())
      .filter(Boolean);
    if (!wanted.length) return;

    const byEmail = new Map(candidates.map((c) => [c.email.toLowerCase(), c]));
    const matched: string[] = [];
    const unmatched: string[] = [];
    for (const email of wanted) {
      const found = byEmail.get(email);
      if (found) matched.push(found.id);
      else unmatched.push(email);
    }

    if (unmatched.length) {
      setError(
        `No candidate account for: ${unmatched.slice(0, 8).join(", ")}` +
          (unmatched.length > 8 ? ` and ${unmatched.length - 8} more` : ""),
      );
    } else {
      setError(null);
    }
    if (matched.length) void assign(matched);
  }

  if (!examId) {
    return (
      <Alert tone="amber" title="Save the draft first">
        Candidates are assigned to an exam, so the exam has to exist before anyone can
        be assigned to it.
      </Alert>
    );
  }

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------------------- assigned */}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-[15px] font-semibold tracking-tight text-ink">
              Assigned candidates
            </h3>
            <Badge tone={assigned.length ? "mint" : "amber"}>{assigned.length}</Badge>
          </div>
          {assigned.some((row) => row.login_access !== "approved") && (
            <span className="text-[12px] text-amber-ink">
              Some assigned candidates cannot sign in yet.
            </span>
          )}
        </div>

        {loading ? (
          <Skeleton className="h-20 rounded-[10px]" />
        ) : assigned.length === 0 ? (
          <EmptyState
            title="Nobody is assigned yet"
            body="Only assigned candidates ever see this exam."
          />
        ) : (
          <ul className="divide-y divide-line">
            {assigned.map((row) => (
              <li
                key={row.candidate_id}
                className="flex flex-wrap items-center justify-between gap-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-medium text-ink">{row.full_name}</p>
                  <p className="text-[12px] text-ink-muted">{row.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {row.login_access && (
                    <Badge tone={ACCESS_TONE[row.login_access]}>
                      {row.login_access === "approved"
                        ? "can sign in"
                        : row.login_access === "pending"
                          ? "login pending"
                          : "login rejected"}
                    </Badge>
                  )}
                  {row.has_attempted && <Badge tone="accent">has sat it</Badge>}
                  <span className="hidden text-[11.5px] text-ink-muted sm:inline">
                    {formatDate(row.assigned_at, false)}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy || row.has_attempted}
                    title={
                      row.has_attempted
                        ? "This candidate has already sat the exam, so their assignment stays."
                        : undefined
                    }
                    onClick={() => void unassign(row.candidate_id)}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* --------------------------------------------------------------- roster */}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[15px] font-semibold tracking-tight text-ink">Add candidates</h3>
          <Button size="sm" variant="secondary" onClick={() => setPasting((v) => !v)}>
            {pasting ? "Close list import" : "Paste a list"}
          </Button>
        </div>

        {pasting && (
          <div className="mb-4 space-y-2 rounded-[10px] border border-line bg-sunken/40 p-3">
            <Field
              label="Candidate emails"
              hint="One per line, or separated by commas. Emails with no account are reported."
            >
              <Textarea
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                rows={4}
                placeholder={"first@college.edu\nsecond@college.edu"}
              />
            </Field>
            <div className="flex justify-end">
              <Button size="sm" loading={busy} onClick={assignPasted}>
                Assign from list
              </Button>
            </div>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email"
          />
          <label className="flex items-center gap-2 text-[13px] text-ink-soft">
            <input
              type="checkbox"
              checked={approvedOnly}
              onChange={(e) => setApprovedOnly(e.target.checked)}
              className="h-4 w-4 rounded border-line-strong"
            />
            Approved candidates only
          </label>
        </div>

        {error && (
          <div className="mt-3">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-line bg-sunken/50 px-3 py-2">
          <label className="flex items-center gap-2 text-[13px] text-ink-soft">
            <input
              type="checkbox"
              checked={shown.length > 0 && selected.length === shown.length}
              disabled={shown.length === 0}
              onChange={() =>
                setSelected(
                  selected.length === shown.length ? [] : shown.map((c) => c.id),
                )
              }
              className="h-4 w-4 rounded border-line-strong"
            />
            {selected.length ? `${selected.length} selected` : `${shown.length} available`}
          </label>
          <Button
            size="sm"
            disabled={!selected.length}
            loading={busy}
            onClick={() => void assign(selected)}
          >
            Assign {selected.length || ""}
          </Button>
        </div>

        {loading ? (
          <div className="mt-3 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-[10px]" />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <div className="mt-3">
            <EmptyState
              title="Nobody left to assign"
              body={
                approvedOnly
                  ? "Everyone approved is already assigned. Untick the filter to see accounts still waiting on login access."
                  : "Every candidate account is already assigned to this exam."
              }
            />
          </div>
        ) : (
          <ul className="mt-3 space-y-2">
            {shown.map((candidate) => {
              const ticked = selected.includes(candidate.id);
              return (
                <li
                  key={candidate.id}
                  className={cx(
                    "flex flex-wrap items-center justify-between gap-3 rounded-[10px] border px-3 py-2 transition",
                    ticked ? "border-accent bg-accent-soft/30" : "border-line bg-surface",
                  )}
                >
                  <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      checked={ticked}
                      onChange={() =>
                        setSelected((current) =>
                          current.includes(candidate.id)
                            ? current.filter((id) => id !== candidate.id)
                            : [...current, candidate.id],
                        )
                      }
                      className="h-4 w-4 shrink-0 rounded border-line-strong"
                    />
                    <span className="min-w-0">
                      <span className="block truncate text-[13.5px] font-medium text-ink">
                        {candidate.full_name}
                      </span>
                      <span className="block text-[12px] text-ink-muted">{candidate.email}</span>
                    </span>
                  </label>
                  <div className="flex items-center gap-2">
                    {candidate.login_access ? (
                      <Badge tone={ACCESS_TONE[candidate.login_access]}>
                        {candidate.login_access === "approved"
                          ? "approved"
                          : candidate.login_access === "pending"
                            ? "login pending"
                            : "login rejected"}
                      </Badge>
                    ) : (
                      <Badge tone="neutral">no login request</Badge>
                    )}
                    {candidate.attempts > 0 && (
                      <span className="text-[11.5px] text-ink-muted">
                        {candidate.completed}/{candidate.attempts} completed
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
