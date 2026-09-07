"use client";

import { Hero } from "@/components/Hero";
import { Alert, Card, SectionTitle } from "@/components/ui";
import type { AccessStatus, UserRole } from "@/lib/types";

/**
 * Shown to any self-registered account an administrator has not yet approved.
 *
 * Both examiners and candidates land here: approval is an administrator-only action, so
 * neither can be let in by a peer. Showing an explanation beats a dashboard full of 403s.
 */

const CAPABILITIES: Record<Exclude<UserRole, "admin">, string[]> = {
  examiner: [
    "Author MCQ, multi-select, short, long and handwritten-upload questions",
    "Configure exams: duration, window, randomization and negative marking",
    "Review provisional scores on written answers and override them",
    "Watch live proctoring and inspect flagged sessions with snapshots",
  ],
  candidate: [
    "See the exams published for you and the window each one opens in",
    "Sit a randomized paper generated for you alone, with autosave throughout",
    "Upload photographed handwritten answers where a question asks for them",
    "Read your result with question-level feedback once it is published",
  ],
};

export function AwaitingApproval({
  role,
  status,
  note,
}: {
  role: Exclude<UserRole, "admin">;
  status: AccessStatus;
  note: string | null;
}) {
  const revoked = status === "revoked";
  const noun = role === "examiner" ? "examiner" : "candidate";

  return (
    <div className="space-y-6">
      <Hero
        title={revoked ? "Your access has been revoked" : "Waiting on an administrator"}
        body={
          revoked
            ? `An administrator has withdrawn your access to the platform.`
            : `Your ${noun} account exists, but an administrator has to approve it before you can use the platform.`
        }
      />

      <Card className="max-w-2xl">
        <div className="flex items-start gap-4">
          <div className="mt-0.5 h-9 w-9 shrink-0 rotate-12 rounded-[10px] border border-line-strong bg-sunken" />
          <div>
            <p className="text-[14px] font-semibold text-ink">
              {revoked ? "What this means" : "What happens next"}
            </p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-soft">
              {revoked
                ? "You can still sign in, but the platform will refuse every action. Contact your administrator if you believe this is a mistake."
                : `An administrator sees your request on their dashboard. Approval is theirs alone to give — no other ${noun} can grant it. Once they do, sign out and back in to pick up the change immediately.`}
            </p>
            {note && (
              <div className="mt-4">
                <Alert tone={revoked ? "rose" : "amber"} title="Administrator note">
                  {note}
                </Alert>
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card className="max-w-2xl">
        <SectionTitle
          title="What you will be able to do"
          hint={`Once an administrator approves your ${noun} account.`}
        />
        <ul className="space-y-2.5">
          {CAPABILITIES[role].map((item) => (
            <li key={item} className="flex gap-2.5 text-[13.5px] text-ink-soft">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-line-strong" />
              {item}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
