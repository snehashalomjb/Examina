"use client";

import { useEffect, useState } from "react";

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
  const { user } = useRequireAuth();
  const { loginAccess, refreshUser } = useAuth();
  const [access, setAccess] = useState<LoginAccess | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

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

  return (
    <div className="space-y-6">
      <Hero title="Profile" body="Your account as the platform holds it." />

      {error && <Alert tone="rose">{error}</Alert>}

      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <Avatar name={user.full_name} size={56} />
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
            title="Details"
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
                    placeholder="Enter your first name"
                    autoComplete="given-name"
                    required
                  />
                </Field>
                <Field label="Last name">
                  <Input
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Enter your last name"
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
            title="Access"
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
        </Card>
      </div>
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
