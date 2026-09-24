"use client";

import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
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
  Modal,
  SectionTitle,
  Select,
  Skeleton,
  cx,
  formatDate,
  toast,
} from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { AccessStatus, AdminUser, UserRole } from "@/lib/types";

const ACCESS_TONE: Record<AccessStatus, "mint" | "amber" | "rose"> = {
  approved: "mint",
  pending: "amber",
  revoked: "rose",
};

export default function AccessControlPage() {
  const t = useTranslations("dashboard-detail");
  const ta = useTranslations("adminShell");
  const tc = useTranslations("common");
  const { user } = useRequireAuth(["admin"]);
  const searchParams = useSearchParams();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<UserRole | "">(
    () => (searchParams.get("role") as UserRole | null) ?? "",
  );
  const [statusFilter, setStatusFilter] = useState<AccessStatus | "">("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [resetting, setResetting] = useState<AdminUser | null>(null);

  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (roleFilter) query.set("role", roleFilter);
    if (statusFilter) query.set("access_status", statusFilter);
    if (search.trim()) query.set("search", search.trim());
    try {
      setUsers(await api.get<AdminUser[]>(`/admin/users?${query.toString()}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ta("error_load_users"));
    } finally {
      setLoading(false);
    }
  }, [roleFilter, statusFilter, search]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  async function setAccess(target: AdminUser, status: AccessStatus) {
    try {
      await api.patch(`/admin/users/${target.id}/access`, {
        access_status: status,
        note: `Set to ${status} by an administrator`,
      });
      toast(ta("toast_access_changed", { name: target.full_name, status: ta(`status_${status}`) }), status === "approved" ? "mint" : "amber");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_change_access"), "rose");
    }
  }

  async function setActive(target: AdminUser, isActive: boolean) {
    try {
      await api.patch(`/admin/users/${target.id}/active?is_active=${isActive}`);
      toast(ta(isActive ? "toast_reactivated" : "toast_deactivated", { name: target.full_name }), "neutral");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_update_account"), "rose");
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title={ta("users_hero_title")}
        body={ta("users_hero_body")}
        action={
          <Button size="sm" onClick={() => setCreating((open) => !open)}>
            {creating ? ta("close") : ta("create_user")}
          </Button>
        }
      />

      {creating && <CreateUserCard onCreated={() => { setCreating(false); void load(); }} />}

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <Field label={ta("search")}>
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("name_or_email_placeholder")}
              />
            </Field>
          </div>
          <div className="w-[170px]">
            <Field label={ta("role")}>
              <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as UserRole | "")}>
                <option value="">{t("all_roles")}</option>
                <option value="candidate">{t("candidate")}</option>
                <option value="examiner">{t("examiner")}</option>
                <option value="admin">{t("admin")}</option>
              </Select>
            </Field>
          </div>
          <div className="w-[170px]">
            <Field label={ta("access")}>
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as AccessStatus | "")}
              >
                <option value="">{t("any_status")}</option>
                <option value="pending">{t("pending")}</option>
                <option value="approved">{t("approved")}</option>
                <option value="revoked">{t("revoked")}</option>
              </Select>
            </Field>
          </div>
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-14 rounded-[12px]" />
            ))}
          </div>
        ) : users.length === 0 ? (
          <EmptyState title={ta("no_users_match")} body={ta("no_users_match_body")} />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="pb-2 pr-3 font-medium">{t("table_user")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("table_role")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("table_access")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("table_activity")}</th>
                  <th className="pb-2 pr-3 font-medium">{t("table_last_seen")}</th>
                  <th className="pb-2 text-right font-medium">{t("table_actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {users.map((row) => {
                  const self = row.id === user.id;
                  return (
                    <tr key={row.id} className={cx(!row.is_active && "opacity-55")}>
                      <td className="py-3 pr-3">
                        <p className="text-[13.5px] font-medium text-ink">{row.full_name}</p>
                        <p className="text-[12px] text-ink-muted">{row.email}</p>
                      </td>
                      <td className="py-3 pr-3">
                        <Badge tone={row.role === "admin" ? "accent" : "neutral"}>{tc(`role_${row.role}`)}</Badge>
                      </td>
                      <td className="py-3 pr-3">
                        <Badge tone={ACCESS_TONE[row.access_status]}>{ta(`status_${row.access_status}`)}</Badge>
                        {row.access_changed_by_email && (
                          <p className="mt-0.5 text-[11px] text-ink-muted">
                            {ta("by_name", { name: row.access_changed_by_email })}
                          </p>
                        )}
                      </td>
                      <td className="py-3 pr-3 text-[12.5px] text-ink-soft">
                        {row.role === "candidate"
                          ? ta("activity_attempts", { count: row.session_count })
                          : ta("activity_exams", { count: row.exam_count })}
                      </td>
                      <td className="py-3 pr-3 text-[12.5px] text-ink-muted">
                        {formatDate(row.last_login_at, false)}
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end gap-1.5">
                          {row.role !== "admin" && row.access_status !== "approved" && (
                            <Button size="sm" onClick={() => setAccess(row, "approved")}>
                              {ta("approve")}
                            </Button>
                          )}
                          {row.role !== "admin" && row.access_status === "approved" && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setAccess(row, "revoked")}
                            >
                              {ta("revoke")}
                            </Button>
                          )}
                          {!self && (
                            <Button size="sm" variant="ghost" onClick={() => setResetting(row)}>
                              {ta("reset_password")}
                            </Button>
                          )}
                          {!self && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setActive(row, !row.is_active)}
                            >
                              {row.is_active ? ta("deactivate") : ta("reactivate")}
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ResetPasswordModal target={resetting} onClose={() => setResetting(null)} />
    </div>
  );
}

function ResetPasswordModal({
  target,
  onClose,
}: {
  target: AdminUser | null;
  onClose: () => void;
}) {
  const ta = useTranslations("adminShell");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPassword("");
    setError(null);
  }, [target]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      await api.post(`/admin/users/${target.id}/reset-password`, { new_password: password });
      toast(ta("toast_password_reset", { name: target.full_name }), "mint");
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ta("error_reset_password"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={Boolean(target)} onClose={onClose} title={ta("reset_password")} size="sm">
      {target && (
        <form onSubmit={submit} className="space-y-4">
          <p className="text-[13px] text-ink-muted">
            {ta.rich("reset_password_body", {
              name: target.full_name,
              email: target.email,
              strong: (chunks) => <strong className="text-ink">{chunks}</strong>,
            })}
          </p>
          <Field label={ta("new_password")} hint={ta("password_hint")}>
            <Input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoFocus
            />
          </Field>
          {error && <Alert tone="rose">{error}</Alert>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              {ta("cancel")}
            </Button>
            <Button type="submit" loading={busy}>
              {ta("reset_password")}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function CreateUserCard({ onCreated }: { onCreated: () => void }) {
  const ta = useTranslations("adminShell");
  const tc = useTranslations("common");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("examiner");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/admin/users", {
        email: email.trim().toLowerCase(),
        full_name: fullName.trim(),
        password,
        role,
        access_status: "approved",
      });
      toast(ta("toast_user_created", { name: fullName }), "mint");
      setEmail("");
      setFullName("");
      setPassword("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ta("error_create_user"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        title={ta("create_user_title")}
        hint={ta("create_user_hint")}
      />
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label={ta("full_name")}>
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} />
        </Field>
        <Field label={ta("email")}>
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label={ta("temporary_password")} hint={ta("password_hint")}>
          <Input
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </Field>
        <Field label={ta("role")}>
          <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            <option value="examiner">{tc("role_examiner")}</option>
            <option value="candidate">{tc("role_candidate")}</option>
            <option value="admin">{tc("role_admin")}</option>
          </Select>
        </Field>
        {error && (
          <div className="sm:col-span-2">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}
        <div className="sm:col-span-2">
          <Button type="submit" loading={busy}>
            {ta("create_user")}
          </Button>
        </div>
      </form>
    </Card>
  );
}
