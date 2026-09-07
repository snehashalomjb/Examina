"use client";

import { useState } from "react";

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
  const { user } = useRequireAuth();
  const { signOut } = useAuth();

  if (!user) return <Skeleton className="h-64 rounded-[14px]" />;

  return (
    <div className="space-y-6">
      <Hero title="Settings" body="Your password and session." />

      <div className="grid gap-5 lg:grid-cols-2">
        <ChangePasswordCard email={user.email} />

        <Card>
          <SectionTitle title="Session" hint="Signing out clears the tokens held in this browser." />
          <p className="text-[13.5px] leading-relaxed text-ink-soft">
            You stay signed in on this device until you sign out or your refresh token
            expires. Sign out on any shared or public machine when you finish.
          </p>
          <div className="mt-5">
            <Button variant="secondary" onClick={signOut}>
              <IconSignOut size={16} />
              Sign out
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
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirm) {
      setError("The two passwords do not match.");
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
        setError(
          "A reset link was issued to your email address. Follow it to finish changing your password.",
        );
        return;
      }
      await api.post(
        "/auth/reset-password",
        { token: token.trim(), new_password: newPassword },
        { auth: false },
      );
      toast("Password updated", "mint");
      setNewPassword("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionTitle title="Change password" hint="At least 8 characters, with a letter and a digit." />
      <form onSubmit={submit} className="space-y-4">
        <Field label="New password">
          <Input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
            required
            autoComplete="new-password"
          />
        </Field>
        <Field label="Confirm new password">
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
          Update password
        </Button>
      </form>
    </Card>
  );
}
