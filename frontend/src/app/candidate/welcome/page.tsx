"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { LowPoly, Mark } from "@/components/LowPoly";
import { Splash } from "@/components/Splash";
import { Badge, Button, Card } from "@/components/ui";
import { IconArrowRight, IconCheck, IconSignOut } from "@/components/icons";
import { useAuth } from "@/lib/auth";

/**
 * The landing after an approved sign-in.
 *
 * Deliberately not the dashboard: the candidate is greeted by name, told plainly that
 * their access is approved, and then chooses to go in. The name comes from the
 * authenticated user record, never from anything the client supplied.
 */

const QUOTES = [
  "Prepare with confidence. Perform with purpose.",
  "Preparation is the quiet work that makes the exam loud with answers.",
  "Steady hands, clear head — the paper is only what you have already practised.",
  "You are not being asked to be perfect. You are being asked to show what you know.",
  "Read twice, answer once.",
];

export default function CandidateWelcomePage() {
  const { user, loginAccess, booting, signOut } = useAuth();
  const router = useRouter();

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
    if (loginAccess === "pending") router.replace("/candidate/pending");
    if (loginAccess === "rejected") router.replace("/candidate/rejected");
  }, [user, loginAccess, booting, router]);

  // Stable for the life of this visit, so it does not flicker between re-renders.
  const quote = useMemo(() => QUOTES[Math.floor(Math.random() * QUOTES.length)], []);

  if (booting || !user) return <Splash />;

  const firstName = user.first_name || user.full_name.split(" ")[0];

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-10">
      <LowPoly variant="hero" className="absolute inset-0 h-full w-full opacity-80" animate />

      <Card className="animate-rise relative w-full max-w-xl">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Mark size={26} />
            <span className="text-[14.5px] font-semibold tracking-tight text-ink">Examina</span>
          </div>
          <Badge tone="mint">
            <IconCheck size={12} />
            Login access approved
          </Badge>
        </div>

        <h1 className="mt-8 text-[30px] font-semibold leading-tight tracking-tight text-ink">
          Welcome, {firstName} 👋
        </h1>

        <figure className="mt-5 border-l-2 border-accent pl-4">
          <blockquote className="text-[15px] italic leading-relaxed text-ink-soft">
            “{quote}”
          </blockquote>
        </figure>

        <p className="mt-6 text-[13.5px] leading-relaxed text-ink-soft">
          Your login access has been approved, so the platform is open to you. Your
          dashboard lists the examinations you have been assigned — each one shows its
          window, duration and what the proctoring will check before you begin.
        </p>

        <div className="mt-6 grid gap-2 rounded-[12px] border border-line bg-sunken/50 p-4">
          {[
            "Sit only the examinations assigned to you",
            "Every paper is generated for you alone",
            "Your camera and browser activity are monitored during a sitting",
          ].map((line) => (
            <div key={line} className="flex items-start gap-2.5">
              <span className="mt-0.5 text-mint">
                <IconCheck size={14} />
              </span>
              <span className="text-[13px] text-ink-soft">{line}</span>
            </div>
          ))}
        </div>

        <div className="mt-7 flex items-center justify-between gap-3">
          <Button variant="ghost" onClick={signOut}>
            <IconSignOut size={16} />
            Sign out
          </Button>
          <Link href="/dashboard/candidate">
            <Button>
              Go to Dashboard
              <IconArrowRight size={16} />
            </Button>
          </Link>
        </div>
      </Card>
    </main>
  );
}
