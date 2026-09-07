"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { LowPoly, Mark } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import { Alert, Badge, Button, Card, formatDate } from "@/components/ui";
import { IconAlert, IconSignOut } from "@/components/icons";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LoginAccess } from "@/lib/types";

/** Shown when login access was refused, or an existing approval was revoked. */
export default function LoginRejectedPage() {
  const { user, loginAccess, booting, signOut } = useAuth();
  const router = useRouter();
  const [detail, setDetail] = useState<LoginAccess | null>(null);

  useEffect(() => {
    if (booting) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "candidate") {
      router.replace("/dashboard");
      return;
    }
    if (loginAccess === "approved") router.replace("/candidate/welcome");
    if (loginAccess === "pending") router.replace("/candidate/pending");
  }, [user, loginAccess, booting, router]);

  useEffect(() => {
    if (!user || user.role !== "candidate") return;
    api
      .get<LoginAccess>("/auth/login-access")
      .then(setDetail)
      .catch(() => setDetail(null));
  }, [user]);

  if (booting || !user) return <Splash />;

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-10">
      <LowPoly variant="hero" className="absolute inset-0 h-full w-full opacity-60" />

      <Card className="animate-rise relative w-full max-w-xl">
        <div className="flex items-center gap-2.5">
          <Mark size={26} />
          <span className="text-[14.5px] font-semibold tracking-tight text-ink">Examina</span>
        </div>

        <div className="mt-7 flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-rose-soft text-rose">
            <IconAlert size={22} />
          </span>
          <div>
            <h1 className="text-[21px] font-semibold tracking-tight text-ink">
              Login access not granted
            </h1>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink-soft">
              Your account exists, but a reviewer has not granted you access to the
              platform. You cannot open the dashboard or sit examinations until that
              decision is changed.
            </p>
          </div>
        </div>

        <dl className="mt-6 divide-y divide-line rounded-[12px] border border-line">
          <Row label="Name" value={user.first_name || user.full_name} />
          <Row label="Email" value={user.email} />
          <Row label="Login access" value={<Badge tone="rose">rejected</Badge>} />
          {detail?.reviewed_at && (
            <Row label="Decided" value={formatDate(detail.reviewed_at)} />
          )}
        </dl>

        {detail?.review_note && (
          <div className="mt-5">
            <Alert tone="rose" title="Reviewer's note">
              {detail.review_note}
            </Alert>
          </div>
        )}

        <p className="mt-5 text-[12.5px] leading-relaxed text-ink-muted">
          If you believe this is a mistake, contact your administrator or the examiner
          running your course. They can reopen your access from the login-request queue.
        </p>

        <div className="mt-6 flex justify-end">
          <Button variant="secondary" onClick={signOut}>
            <IconSignOut size={16} />
            Sign out
          </Button>
        </div>
      </Card>
    </main>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3">
      <dt className="text-[12.5px] text-ink-muted">{label}</dt>
      <dd className="text-[13.5px] font-medium text-ink">{value}</dd>
    </div>
  );
}
