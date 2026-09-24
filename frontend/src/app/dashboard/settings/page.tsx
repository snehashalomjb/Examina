"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Hero } from "@/components/Hero";
import {
  Alert,
  Button,
  Card,
  Field,
  Input,
  SectionTitle,
  Skeleton,
  toast,
} from "@/components/ui";
import { IconSignOut } from "@/components/icons";
import { ApiError, api } from "@/lib/api";
import { useAuth, useRequireAuth } from "@/lib/auth";

export default function SettingsPage() {
  const t = useTranslations("profile");
  const ta = useTranslations("adminShell");
  const { user } = useRequireAuth();
  const { signOut } = useAuth();

  if (!user) return <Skeleton className="h-64 rounded-[14px]" />;

  return (
    <div className="space-y-6">
      <Hero title={t("settings_title")} body={t("settings_subtitle")} />

      <div className="grid gap-5 lg:grid-cols-2">
        <ChangePasswordCard email={user.email} />

        <Card>
          <SectionTitle title={t("session_title")} hint={t("session_hint")} />
          <p className="text-[13.5px] leading-relaxed text-ink-soft">
            {ta("session_body")}
          </p>
          <div className="mt-5">
            <Button variant="secondary" onClick={signOut}>
              <IconSignOut size={16} />
              {t("sign_out")}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

/**
 * Password change, routed through the existing reset flow.
 *
 * There is no mail transport in this deployment, so `forgot-password` returns the reset
 * token inline in development. Reusing that flow means there is exactly one code path
 * that can change a password, rather than a second one to keep secure.
 */
function ChangePasswordCard({ email }: { email: string }) {
  const t = useTranslations("profile");
  const ta = useTranslations("adminShell");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirm) {
      setError(ta("error_passwords_no_match"));
      return;
    }

    setBusy(true);
    try {
      const issued = await api.post<{ detail: string }>(
        "/auth/forgot-password",
        { email },
        { auth: false },
      );
      const token = issued.detail.split("reset_token=")[1];
      if (!token) {
        setError(ta("reset_link_issued"));
        return;
      }
      await api.post(
        "/auth/reset-password",
        { token: token.trim(), new_password: newPassword },
        { auth: false },
      );
      toast(ta("password_updated"), "mint");
      setNewPassword("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : ta("error_change_the_password"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionTitle title={t("change_password_title")} hint={t("settingsChangePasswordHint")} />
      <form onSubmit={submit} className="space-y-4">
        <Field label={ta("new_password")}>
          <Input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
          />
        </Field>
        <Field label={ta("confirm_new_password")}>
          <Input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
          />
        </Field>
        {error && <Alert tone="rose">{error}</Alert>}
        <Button type="submit" loading={busy}>
          {ta("update_password")}
        </Button>
      </form>
    </Card>
  );
}
