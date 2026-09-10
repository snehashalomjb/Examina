"use client";

/**
 * The live operations console.
 *
 * Deliberately its own dark, dense screen rather than another panel on the examiner
 * dashboard: this is a monitoring wall you leave open on a second display during a
 * sitting, and it refreshes itself every 15 seconds. The dashboard is for deciding what
 * to do next; this is for watching what is happening now.
 *
 * Everything it shows is read from the database. Where there is nothing, it says so.
 */

import { AwaitingApproval } from "@/components/AwaitingApproval";
import { LiveOperationsDashboard } from "@/components/LiveOperationsDashboard";
import { useRequireAuth } from "@/lib/auth";

export default function LiveOperationsPage() {
  const { user } = useRequireAuth(["examiner", "admin"]);

  if (!user) return null;

  const approved = user.access_status === "approved" || user.role === "admin";
  if (!approved) {
    return (
      <AwaitingApproval role="examiner" status={user.access_status} note={user.access_note} />
    );
  }

  return (
    <LiveOperationsDashboard
      role={user.role === "admin" ? "admin" : "examiner"}
      userFullName={user.full_name}
    />
  );
}
