"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { LowPoly, Mark } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import { Badge, Button, Card, formatDate } from "@/components/ui";
import { IconHourglass, IconSignOut } from "@/components/icons";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LoginAccess } from "@/lib/types";

/**
 * Login Access Pending.
 *
 * The candidate's account exists and is active — registration needed no approval. What
 * they are waiting on is permission to *use* the platform, decided by an administrator or
 * an examiner who is authorised over them.
 *
 * This page polls quietly so an approval that lands while they are sitting here takes
 * effect without them guessing when to reload.
 */
const POLL_MS = 15_000;

export default function LoginPendingPage() {
  const { user, loginAccess, booting, signOut, refreshUser } = useAuth();
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
    if (loginAccess === "approved") {
      router.replace("/candidate/welcome");
      return;
    }
    if (loginAccess === "rejected") {
      router.replace("/candidate/rejected");
    }
  }, [user, loginAccess, booting, router]);

  useEffect(() => {
    if (!user || user.role !== "candidate") return;
    let cancelled = false;

    async function check() {
      try {
        const access = await api.get<LoginAccess>("/auth/login-access");
        if (cancelled) return;
        setDetail(access);
        // A decision landed while they waited - pick it up without a manual reload.
        if (access.status !== "pending") void refreshUser();
      } catch {
        /* transient - the next poll will catch up */
      }
    }

    void check();
    const timer = window.setInterval(() => void check(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [user, refreshUser]);

  if (booting || !user) return <Splash />;

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-10">
      <LowPoly variant="hero" className="absolute inset-0 h-full w-full opacity-70" animate />

      <Card className="animate-rise relative w-full max-w-xl">
        <div className="flex items-center gap-2.5">
          <Mark size={26} />
          <span className="text-[14.5px] font-semibold tracking-tight text-ink">Examina</span>
        </div>

        <div className="mt-7 flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-amber-soft text-amber">
            <IconHourglass size={22} />
          </span>
          <div>
            <h1 className="text-[21px] font-semibold tracking-tight text-ink">
              Login access pending
            </h1>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink-soft">
              Your account has been created successfully. Your login access request is
              waiting for approval from an administrator or examiner.
            </p>
          </div>
        </div>

        <dl className="mt-6 divide-y divide-line rounded-[12px] border border-line">
          <Row label="Name" value={user.first_name || user.full_name} />
          <Row label="Email" value={user.email} />
          <Row
            label="Account"
            value={<Badge tone="mint">active</Badge>}
          />
          <Row
            label="Login access"
            value={<Badge tone="amber">pending approval</Badge>}
          />
          {detail && (
            <Row label="Requested" value={formatDate(detail.requested_at)} />
          )}
        </dl>

        <p className="mt-5 text-[12.5px] leading-relaxed text-ink-muted">
          This page checks for a decision every few seconds — you do not need to refresh.
          Once you are approved you will be taken straight through.
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
