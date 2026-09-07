"use client";

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
  const { user } = useRequireAuth(["admin"]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<UserRole | "">("");
  const [statusFilter, setStatusFilter] = useState<AccessStatus | "">("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    const query = new URLSearchParams();
    if (roleFilter) query.set("role", roleFilter);
    if (statusFilter) query.set("access_status", statusFilter);
    if (search.trim()) query.set("search", search.trim());
    try {
      setUsers(await api.get<AdminUser[]>(`/admin/users?${query.toString()}`));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load users.");
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
      toast(`${target.full_name} — access ${status}`, status === "approved" ? "mint" : "amber");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not change access", "rose");
    }
  }

  async function setActive(target: AdminUser, isActive: boolean) {
    try {
      await api.patch(`/admin/users/${target.id}/active?is_active=${isActive}`);
      toast(`${target.full_name} ${isActive ? "reactivated" : "deactivated"}`, "neutral");
      void load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not update the account", "rose");
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="Access control"
        body="Approval happens here and nowhere else. Examiners cannot author, grade or view proctoring — and candidates cannot see or sit an exam — until you approve them."
        action={
          <Button size="sm" onClick={() => setCreating((open) => !open)}>
            {creating ? "Close" : "Create user"}
          </Button>
        }
      />

      {creating && <CreateUserCard onCreated={() => { setCreating(false); void load(); }} />}

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <Field label="Search">
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Name or email"
              />
            </Field>
          </div>
          <div className="w-[170px]">
            <Field label="Role">
              <Select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as UserRole | "")}>
                <option value="">All roles</option>
                <option value="candidate">Candidate</option>
                <option value="examiner">Examiner</option>
                <option value="admin">Admin</option>
              </Select>
            </Field>
          </div>
          <div className="w-[170px]">
            <Field label="Access">
              <Select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as AccessStatus | "")}
              >
                <option value="">Any status</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="revoked">Revoked</option>
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
          <EmptyState title="No users match" body="Adjust the filters or clear the search." />
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-ink-muted">
                  <th className="pb-2 pr-3 font-medium">User</th>
                  <th className="pb-2 pr-3 font-medium">Role</th>
                  <th className="pb-2 pr-3 font-medium">Access</th>
                  <th className="pb-2 pr-3 font-medium">Activity</th>
                  <th className="pb-2 pr-3 font-medium">Last seen</th>
                  <th className="pb-2 text-right font-medium">Actions</th>
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
                        <Badge tone={row.role === "admin" ? "accent" : "neutral"}>{row.role}</Badge>
                      </td>
                      <td className="py-3 pr-3">
                        <Badge tone={ACCESS_TONE[row.access_status]}>{row.access_status}</Badge>
                        {row.access_changed_by_email && (
                          <p className="mt-0.5 text-[11px] text-ink-muted">
                            by {row.access_changed_by_email}
                          </p>
                        )}
                      </td>
                      <td className="py-3 pr-3 text-[12.5px] text-ink-soft">
                        {row.role === "candidate"
                          ? `${row.session_count} attempt${row.session_count === 1 ? "" : "s"}`
                          : `${row.exam_count} exam${row.exam_count === 1 ? "" : "s"}`}
                      </td>
                      <td className="py-3 pr-3 text-[12.5px] text-ink-muted">
                        {formatDate(row.last_login_at, false)}
                      </td>
                      <td className="py-3">
                        <div className="flex justify-end gap-1.5">
                          {row.role !== "admin" && row.access_status !== "approved" && (
                            <Button size="sm" onClick={() => setAccess(row, "approved")}>
                              Approve
                            </Button>
                          )}
                          {row.role !== "admin" && row.access_status === "approved" && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setAccess(row, "revoked")}
                            >
                              Revoke
                            </Button>
                          )}
                          {!self && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setActive(row, !row.is_active)}
                            >
                              {row.is_active ? "Deactivate" : "Reactivate"}
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
    </div>
  );
}

function CreateUserCard({ onCreated }: { onCreated: () => void }) {
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
      toast(`${fullName} created and approved`, "mint");
      setEmail("");
      setFullName("");
      setPassword("");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the user.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionTitle
        title="Create a user"
        hint="Accounts you create here are approved immediately. This is the only route to an administrator account."
      />
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name">
          <Input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} />
        </Field>
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label="Temporary password" hint="At least 8 characters, with a letter and a digit.">
          <Input
            type="text"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </Field>
        <Field label="Role">
          <Select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            <option value="examiner">Examiner</option>
            <option value="candidate">Candidate</option>
            <option value="admin">Admin</option>
          </Select>
        </Field>
        {error && (
          <div className="sm:col-span-2">
            <Alert tone="rose">{error}</Alert>
          </div>
        )}
        <div className="sm:col-span-2">
          <Button type="submit" loading={busy}>
            Create user
          </Button>
        </div>
      </form>
    </Card>
  );
}
