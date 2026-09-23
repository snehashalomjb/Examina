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

const ROLE_LABEL = {
  admin: "Admin",
  examiner: "Examiner",
  candidate: "Candidate",
} as const;

/** The signed-in user's own record, read from the authenticated session. */
export default function ProfilePage() {
  const t = useTranslations("profile");
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
      setSaveError("Enter your first name.");
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
      toast("Profile updated", "mint");
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  async function changePassword(event: React.FormEvent) {
    event.preventDefault();
    if (newPassword.length < 8 || !/[a-zA-Z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
      setPasswordError("New password must be at least 8 characters with a letter and a digit.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirm password don't match.");
      return;
    }

    setChangingPassword(true);
    setPasswordError(null);
    try {
      await api.post("/auth/change-password", {
        new_password: newPassword,
      });
      toast("Password updated", "mint");

      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "Could not change your password.");
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
      toast("Profile picture updated", "mint");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not upload that picture.", "rose");
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
              {uploadingAvatar ? "…" : "Change"}
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
            <Badge tone="accent">{ROLE_LABEL[user.role]}</Badge>
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
                login {loginAccess}
              </Badge>
            )}
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            title={t("details_card")}
            hint={editing ? "Change your name." : "From your user record."}
            action={
              editing ? undefined : (
                <Button variant="secondary" onClick={startEdit}>
                  Edit profile
                </Button>
              )
            }
          />

          {editing ? (
            <form onSubmit={saveProfile} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="First name">
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
                <Field label="Last name">
                  <Input
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder={t("last_name_placeholder")}
                    autoComplete="family-name"
                  />
                </Field>
              </div>

              <p className="text-[12px] leading-relaxed text-ink-muted">
                Your email is your sign-in identity and your role is an administrator&apos;s
                decision, so neither is edited here.
              </p>

              {saveError && <Alert tone="rose">{saveError}</Alert>}

              <div className="flex gap-2">
                <Button type="submit" loading={saving}>
                  Save changes
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setEditing(false);
                    setSaveError(null);
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <dl className="divide-y divide-line">
              <Row
                icon={<IconProfile size={15} />}
                label="First name"
                value={user.first_name || "—"}
              />
              <Row
                icon={<IconProfile size={15} />}
                label="Last name"
                value={user.last_name || "—"}
              />
              <Row label="Email" value={user.email} />
              <Row label="Role" value={ROLE_LABEL[user.role]} />
              <Row label="Registered" value={formatDate(user.created_at)} />
              <Row label="Last sign-in" value={formatDate(user.last_login_at)} />
            </dl>
          )}
        </Card>

        <Card>
          <SectionTitle
            title={t("access_card")}
            hint={
              user.role === "candidate"
                ? "Your account and your permission to use the platform are separate."
                : "What your role is allowed to reach."
            }
          />
          <dl className="divide-y divide-line">
            <Row
              icon={<IconShield size={15} />}
              label="Account"
              value={
                <Badge tone={user.is_active ? "mint" : "rose"}>
                  {user.is_active ? "active" : "deactivated"}
                </Badge>
              }
            />
            {user.role === "candidate" ? (
              <>
                <Row
                  label="Login access"
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
                      {loginAccess ?? "unknown"}
                    </Badge>
                  }
                />
                {access && <Row label="Requested" value={formatDate(access.requested_at)} />}
                {access?.reviewed_at && (
                  <Row label="Decided" value={formatDate(access.reviewed_at)} />
                )}
                {access?.review_note && <Row label="Reviewer note" value={access.review_note} />}
              </>
            ) : (
              <Row
                label="Account approval"
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
                    {user.access_status}
                  </Badge>
                }
              />
            )}
          </dl>

          {user.role === "candidate" && (
            <p className="mt-4 text-[12px] leading-relaxed text-ink-muted">
              Your account was created active when you registered. Permission to use the
              platform is granted separately by an administrator or an examiner who runs a
              paper you are enrolled in.
            </p>
          )}

          <div className="mt-4 border-t border-line pt-3">
            <Link
              href="/dashboard/settings"
              className="text-[12px] font-medium text-ink-muted hover:text-ink"
            >
              Account settings →
            </Link>
          </div>
        </Card>
      </div>

      <Card>
        <SectionTitle title={t("change_password_title")} hint={t("change_password_hint")} />
        <form onSubmit={changePassword} className="max-w-md space-y-4">

          <Field label="New password">
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
          <Field label="Confirm new password">
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
            Update password
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
