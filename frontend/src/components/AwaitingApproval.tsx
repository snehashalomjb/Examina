"use client";

import { Hero } from "@/components/Hero";
import { Alert, Card, SectionTitle } from "@/components/ui";
import { IconAlert, IconHourglass } from "@/components/icons";
import { useTranslations } from "next-intl";
import type { AccessStatus, UserRole } from "@/lib/types";

/**
 * Shown to any self-registered account an administrator has not yet approved.
 *
 * Both examiners and candidates land here: approval is an administrator-only action, so
 * neither can be let in by a peer. Showing an explanation beats a dashboard full of 403s.
 */

/** "adminShell" message keys for what each role can do once approved. */
const CAPABILITIES: Record<Exclude<UserRole, "admin">, string[]> = {
  examiner: ["cap_examiner_1", "cap_examiner_2", "cap_examiner_3", "cap_examiner_4"],
  candidate: ["cap_candidate_1", "cap_candidate_2", "cap_candidate_3", "cap_candidate_4"],
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
  const t = useTranslations("dashboard-detail");
  const ta = useTranslations("adminShell");
  const revoked = status === "revoked";

  return (
    <div className="space-y-6">
      <Hero
        title={revoked ? ta("awaiting_revoked_title") : ta("awaiting_title")}
        body={revoked ? ta("awaiting_revoked_body") : ta(`awaiting_body_${role}`)}
      />

      <Card className="max-w-2xl">
        <div className="flex items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/10 text-accent border border-accent/20">
            {revoked ? <IconAlert size={22} className="text-rose" /> : <IconHourglass size={22} className="text-accent" />}
          </div>
          <div>
            <p className="text-[14px] font-semibold text-ink">
              {revoked ? ta("what_this_means") : ta("what_happens_next")}
            </p>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-soft">
              {revoked ? ta("awaiting_revoked_detail") : ta(`awaiting_next_${role}`)}
            </p>
            {note && (
              <div className="mt-4">
                <Alert tone={revoked ? "rose" : "amber"} title={t("admin_note_title")}>
                  {note}
                </Alert>
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card className="max-w-2xl">
        <SectionTitle
          title={t("awaiting_approval_heading")}
          hint={ta(`awaiting_hint_${role}`)}
        />
        <ul className="space-y-2.5">
          {CAPABILITIES[role].map((item) => (
            <li key={item} className="flex gap-2.5 text-[13.5px] text-ink-soft">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rotate-45 bg-line-strong" />
              {ta(item)}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
