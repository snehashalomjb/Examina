"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Hero } from "@/components/Hero";
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
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { CandidateAttempt, CandidateRow } from "@/lib/types";

export default function CandidatesPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [candidates, setCandidates] = useState<CandidateRow[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<CandidateRow | null>(null);
  const [attempts, setAttempts] = useState<CandidateAttempt[]>([]);
  const [attemptsLoading, setAttemptsLoading] = useState(false);

  const load = useCallback(async () => {
    const query = search.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
    try {
      setCandidates(await api.get<CandidateRow[]>(`/admin/candidates${query}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load candidates.");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  async function openCandidate(candidate: CandidateRow) {
    setOpen(candidate);
    setAttemptsLoading(true);
    try {
      setAttempts(await api.get<CandidateAttempt[]>(`/candidates/${candidate.id}/attempts`));
    } catch {
      setAttempts([]);
    } finally {
      setAttemptsLoading(false);
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="Candidates"
        body="Everyone who can sit your papers, with their attempt history and how proctoring rated each sitting."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="mb-4 max-w-sm">
          <Field label="Search">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Name or email"
            />
          </Field>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-[12px]" />
            ))}
          </div>
        ) : candidates.length === 0 ? (
          <EmptyState title="No candidates found" body="Nobody matches that search." />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="pb-2 pr-3 font-medium">Candidate</th>
                  <th className="pb-2 pr-3 font-medium">Attempts</th>
                  <th className="pb-2 pr-3 font-medium">Completed</th>
                  <th className="pb-2 pr-3 font-medium">Average</th>
                  <th className="pb-2 pr-3 font-medium">Flags</th>
                  <th className="pb-2 pr-3 font-medium">Last seen</th>
                  <th className="pb-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {candidates.map((row) => (
                  <tr key={row.id} className={cx(!row.is_active && "opacity-55")}>
                    <td className="py-3 pr-3">
                      <p className="text-[13.5px] font-medium text-ink">{row.full_name}</p>
                      <p className="text-[12px] text-ink-muted">{row.email}</p>
                    </td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">{row.attempts}</td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">{row.completed}</td>
                    <td className="py-3 pr-3 text-[13px] text-ink-soft">
                      {row.average_percentage !== null ? `${row.average_percentage}%` : "—"}
                    </td>
                    <td className="py-3 pr-3">
                      {row.flagged_sessions > 0 ? (
                        <Badge tone="rose">{row.flagged_sessions}</Badge>
                      ) : (
                        <span className="text-[13px] text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-3 text-[12.5px] text-ink-muted">
                      {formatDate(row.last_login_at, false)}
                    </td>
                    <td className="py-3 text-right">
                      <Button size="sm" variant="secondary" onClick={() => openCandidate(row)}>
                        History
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {open && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-ink/40 px-5 backdrop-blur-sm"
          onClick={() => setOpen(null)}
        >
          <div
            className="w-full max-w-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <Card className="animate-rise max-h-[80vh] overflow-y-auto">
              <SectionTitle
                title={open.full_name}
                hint={open.email}
                action={
                  <Button size="sm" variant="secondary" onClick={() => setOpen(null)}>
                    Close
                  </Button>
                }
              />

              {attemptsLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 rounded-[10px]" />
                  ))}
                </div>
              ) : attempts.length === 0 ? (
                <EmptyState
                  title="No attempts"
                  body="This candidate has not sat any of your papers yet."
                />
              ) : (
                <ul className="divide-y divide-line">
                  {attempts.map((attempt) => (
                    <li key={attempt.session_id} className="flex flex-wrap items-center gap-3 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13.5px] font-medium text-ink">
                          {attempt.exam_title}
                        </p>
                        <p className="text-[12px] text-ink-muted">
                          {formatDate(attempt.started_at)} ·{" "}
                          {attempt.status.replace("_", " ")}
                        </p>
                      </div>

                      {attempt.percentage !== null && (
                        <Badge
                          tone={
                            attempt.percentage >= 70
                              ? "mint"
                              : attempt.percentage >= 40
                                ? "amber"
                                : "rose"
                          }
                        >
                          {attempt.percentage}%
                        </Badge>
                      )}
                      {attempt.is_flagged && <Badge tone="rose">flagged</Badge>}

                      <div className="flex gap-1.5">
                        <Link href={`/dashboard/proctoring/${attempt.session_id}`}>
                          <Button size="sm" variant="ghost">
                            Proctoring
                          </Button>
                        </Link>
                        {attempt.result_id && (
                          <Link href={`/results/${attempt.result_id}`}>
                            <Button size="sm" variant="secondary">
                              Result
                            </Button>
                          </Link>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
