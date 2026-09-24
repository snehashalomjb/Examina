"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import { Avatar } from "@/components/Avatar";
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  Input,
  SectionTitle,
  Skeleton,
  formatDate,
  toast,
} from "@/components/ui";
import { IconProfile, IconShield } from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";
import type { LoginAccess } from "@/lib/types";

/** The signed-in user's own record, read from the authenticated session. */
export default function ProfilePage() {
  const t = useTranslations("profile");
  const ta = useTranslations("adminShell");
  const loginStatusLabel = (status: string) =>
    ta.has(`status_${status}`) ? ta(`status_${status}`) : status;
  const { user } = useRequireAuth();
  const { loginAccess, refreshUser } = useAuth();
  const [access, setAccess] = useState<LoginAccess | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);


  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const [uploadingAvatar, setUploadingAvatar] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!user || user.role !== "candidate") return;
      try {
        const data = await api.get<LoginAccess>("/auth/login-access");
        if (!cancelled) setAccess(data);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return <Skeleton className="h-64 rounded-[14px]" />;

  function startEdit() {
    // Seed the form from the record every time, so a cancelled edit leaves nothing behind.
    setFirstName(user?.first_name ?? "");
    setLastName(user?.last_name ?? "");
    setSaveError(null);
    setEditing(true);
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!firstName.trim()) {
      setSaveError(ta("error_enter_first_name"));
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      await api.patch("/auth/me", {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
      });
      // Re-read the session so the header, sidebar and avatar follow the new name.
      await refreshUser();
      toast(ta("toast_profile_updated"), "mint");
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : ta("error_save_profile"));
    } finally {
      setSaving(false);
    }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    if (newPassword.length < 8 || !/[a-zA-Z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setPasswordError(ta("error_password_rule"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError(ta("error_password_mismatch"));
      return;
    }

    setChangingPassword(true);
    setPasswordError(null);
    try {
      await api.post("/auth/change-password", {
        new_password: newPassword,
      });
      toast(ta("password_updated"), "mint");

      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : ta("error_change_your_password"));
    } finally {
      setChangingPassword(false);
    }
  }

  async function uploadAvatar(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setUploadingAvatar(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await api.upload("/auth/avatar", form);
      await refreshUser();
      toast(ta("toast_avatar_updated"), "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : ta("error_avatar_upload"), "rose");
    } finally {
      setUploadingAvatar(false);
    }
  }

  return (
    <div className="space-y-6">
      <Hero title={t("profile_title")} body={t("profile_subtitle")} />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <label className="group relative cursor-pointer">
            <Avatar name={user.full_name} src={user.avatar_url} size={56} />
            <span className="absolute inset-0 flex items-center justify-center rounded-[10px] bg-ink/50 text-[9px] font-semibold text-white opacity-0 transition-opacity group-hover:opacity-100">
              {uploadingAvatar ? "…" : ta("avatar_change")}
            </span>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              disabled={uploadingAvatar}
              onChange={uploadAvatar}
            />
          </label>
          <div className="min-w-0">
            <p className="text-[19px] font-semibold tracking-tight text-ink">
              {user.full_name}
            </p>
            <p className="text-[13px] text-ink-muted">{user.email}</p>
          </div>
          <div className="ml-auto flex flex-wrap gap-2">
            <Badge tone="accent">{ta(`role_${user.role}`)}</Badge>
            {user.role === "candidate" && loginAccess && (
              <Badge
                tone={
                  loginAccess === "approved"
                    ? "mint"
                    : loginAccess === "pending"
                      ? "amber"
                      : "rose"
                }
              >
                {ta("login_status_badge", { status: loginStatusLabel(loginAccess) })}
              </Badge>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            title={t("details_card")}
            hint={editing ? ta("details_hint_editing") : ta("details_hint")}
            action={
              editing ? undefined : (
                <Button variant="secondary" onClick={startEdit}>
                  {ta("edit_profile")}
                </Button>
              )
            }
          />

          {editing ? (
            <form onSubmit={saveProfile} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={ta("first_name")}>
                  <Input
                    value={firstName}
                    onChange={(e) => {
                      setFirstName(e.target.value);
                      setSaveError(null);
                    }}
                    placeholder={t("first_name_placeholder")}
                    autoComplete="given-name"
                    required
                  />
                </Field>
                <Field label={ta("last_name")}>
                  <Input
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder={t("last_name_placeholder")}
                    autoComplete="family-name"
                  />
                </Field>
              </div>

              <p className="text-[12px] leading-relaxed text-ink-muted">
                {ta("identity_note")}
              </p>

              {saveError && <Alert tone="rose">{saveError}</Alert>}

              <div className="flex gap-2">
                <Button type="submit" loading={saving}>
                  {ta("save_changes")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setEditing(false);
                    setSaveError(null);
                  }}
                >
                  {ta("cancel")}
                </Button>
              </div>
            </form>
          ) : (
            <dl className="divide-y divide-line">
              <Row
                icon={<IconProfile size={15} />}
                label={ta("first_name")}
                value={user.first_name || "—"}
              />
              <Row
                icon={<IconProfile size={15} />}
                label={ta("last_name")}
                value={user.last_name || "—"}
              />
              <Row label={ta("email")} value={user.email} />
              <Row label={ta("role")} value={ta(`role_${user.role}`)} />
              <Row label={ta("registered")} value={formatDate(user.created_at)} />
              <Row label={ta("last_sign_in")} value={formatDate(user.last_login_at)} />
            </dl>
          )}
        </Card>

        <Card>
          <SectionTitle
            title={t("access_card")}
            hint={
              user.role === "candidate"
                ? ta("access_hint_candidate")
                : ta("access_hint_other")
            }
          />
          <dl className="divide-y divide-line">
            <Row
              icon={<IconShield size={15} />}
              label={ta("account")}
              value={
                <Badge tone={user.is_active ? "mint" : "rose"}>
                  {user.is_active ? ta("account_active") : ta("account_deactivated")}
                </Badge>
              }
            />
            {user.role === "candidate" ? (
              <>
                <Row
                  label={ta("login_access")}
                  value={
                    <Badge
                      tone={
                        loginAccess === "approved"
                          ? "mint"
                          : loginAccess === "pending"
                            ? "amber"
                            : "rose"
                      }
                    >
                      {loginAccess ? loginStatusLabel(loginAccess) : ta("unknown")}
                    </Badge>
                  }
                />
                {access && <Row label={ta("requested")} value={formatDate(access.requested_at)} />}
                {access?.reviewed_at && (
                  <Row label={ta("decided")} value={formatDate(access.reviewed_at)} />
                )}
                {access?.review_note && <Row label={ta("reviewer_note")} value={access.review_note} />}
              </>
            ) : (
              <Row
                label={ta("account_approval")}
                value={
                  <Badge
                    tone={
                      user.access_status === "approved"
                        ? "mint"
                        : user.access_status === "pending"
                          ? "amber"
                          : "rose"
                    }
                  >
                    {ta(`status_${user.access_status}`)}
                  </Badge>
                }
              />
            )}
          </dl>

          {user.role === "candidate" && (
            <p className="mt-4 text-[12px] leading-relaxed text-ink-muted">
              {ta("candidate_access_note")}
            </p>
          )}

          <div className="mt-4 border-t border-line pt-3">
            <Link
              href="/dashboard/settings"
              className="text-[12px] font-medium text-ink-muted hover:text-ink"
            >
              {ta("account_settings_link")}
            </Link>
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle title={t("change_password_title")} hint={t("change_password_hint")} />
        <form onSubmit={changePassword} className="max-w-md space-y-4">

          <Field label={ta("new_password")}>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => {
                setNewPassword(e.target.value);
                setPasswordError(null);
              }}
              autoComplete="new-password"
              required
            />
          </Field>
          <Field label={ta("confirm_new_password")}>
            <Input
              type="password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setPasswordError(null);
              }}
              autoComplete="new-password"
              required
            />
          </Field>

          {passwordError && <Alert tone="rose">{passwordError}</Alert>}

          <Button type="submit" loading={changingPassword}>
            {ta("update_password")}
          </Button>
        </form>
      </Card>
    </div>
  );
}

function Row({
  label,
  value,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <dt className="flex items-center gap-2 text-[12.5px] text-ink-muted">
        {icon}
        {label}
      </dt>
      <dd className="text-right text-[13.5px] font-medium text-ink">{value}</dd>
    </div>
  );
}
