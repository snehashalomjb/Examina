"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

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

// Tab labels are loaded dynamically from translations
const TAB_KEYS = ["pending", "approved", "rejected", "all"] as const;

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
  const t = useTranslations("dashboard-detail");
  const ta = useTranslations("adminShell");
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
      setError(err instanceof ApiError ? err.message : ta("error_load_login_requests"));
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
          ? ta("toast_can_use_platform", { name: row.first_name })
          : ta(row.status === "approved" ? "toast_access_was_revoked" : "toast_access_was_refused", {
              name: row.first_name,
            }),
        approve ? "mint" : "amber",
      );
      setNotes((current) => ({ ...current, [row.id]: "" }));
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_record_decision"), "rose");
    } finally {
      setBusyId(null);
    }
  }

  if (!user) return null;

  const pendingCount = rows.filter((r) => r.status === "pending").length;

  return (
    <div className="space-y-6">
      <Hero
        title={t("hero_login_requests")}
        body={
          user.role === "admin"
            ? t("body_login_requests_admin")
            : t("body_login_requests_examiner")
        }
      />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card padded={false} className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <div className="inline-flex rounded-[10px] border border-line bg-sunken p-1">
            {TAB_KEYS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => {
                  setLoading(true);
                  setTab(key);
                }}
                className={cx(
                  "rounded-[7px] px-3 py-1.5 text-[12.5px] font-medium transition",
                  tab === key
                    ? "bg-surface text-ink shadow-[var(--shadow-soft)]"
                    : "text-ink-muted hover:text-ink",
                )}
              >
                {t(`tab_${key}`)}
              </button>
            ))}
          </div>

          {tab === "pending" && pendingCount > 0 && (
            <Badge tone="amber">
              <IconHourglass size={12} />
              {t("badge_awaiting_decision", { count: pendingCount })}
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
              title={tab === "pending" ? t("empty_nothing_waiting") : t("empty_nothing_here")}
              body={
                user.role === "examiner"
                  ? t("empty_body_examiner")
                  : t("empty_body_admin")
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
                        <Badge tone={TONE[row.status]}>{ta(`status_${row.status}`)}</Badge>
                      </div>
                      <p className="mt-0.5 text-[12.5px] text-ink-muted">{row.email}</p>
                      <p className="mt-1 text-[12px] text-ink-muted">
                        {ta("requested_on", { date: formatDate(row.requested_at) })}
                        {row.reviewed_at && row.reviewed_by_name && (
                          <>
                            {" · "}
                            {ta("decided_by_on", {
                              name: row.reviewed_by_name,
                              date: formatDate(row.reviewed_at),
                            })}
                          </>
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
                      <Field label={t("field_note_optional")}>
                        <Input
                          value={notes[row.id] ?? ""}
                          onChange={(e) =>
                            setNotes((current) => ({ ...current, [row.id]: e.target.value }))
                          }
                          placeholder={t("placeholder_shown_to_candidate")}
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
                            {t("button_approve")}
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
                            {row.status === "approved" ? t("button_revoke") : t("button_reject")}
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
        <SectionTitle title={t("section_how_this_works")} hint={t("section_hint_two_separate_ideas")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-[11px] border border-line p-4">
            <p className="text-[13px] font-semibold text-ink">{t("label_account")}</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-soft">
              {t("text_account_description")}
            </p>
          </div>
          <div className="rounded-[11px] border border-line p-4">
            <p className="text-[13px] font-semibold text-ink">{t("label_login_access")}</p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-ink-soft">
              {t("text_login_access_description")}
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
