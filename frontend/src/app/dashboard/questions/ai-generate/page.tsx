"use client";

/**
 * Stand-alone AI generation, outside the exam wizard.
 *
 * This is the same `AIGenerator` the wizard mounts for a specific exam - same subject
 * requirement, same multi-select review queue, same approve/reject/regenerate. The only
 * difference is that nothing here has an `examId`: every approval goes straight into the
 * question bank rather than into one exam's pool, for an examiner stocking the bank
 * ahead of time rather than building a paper right now.
 */

import { useEffect, useState } from "react";

import { AIGenerator } from "@/components/AIGenerator";
import { Hero } from "@/components/Hero";
import { Alert, Skeleton } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { Subject } from "@/lib/types";

export default function AiGeneratePage() {
  const { user } = useRequireAuth(["examiner", "admin"]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.get<Subject[]>("/subjects");
        if (!cancelled) setSubjects(data);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load subjects.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) return null;

  return (
    <div className="space-y-6">
      <Hero
        title="AI Question Generation"
        body="Pick a subject and the questions are generated for its syllabus, not in the abstract. Select as many drafts as you like and approve them together — nothing reaches the bank until you do."
      />

      {error && <Alert tone="rose">{error}</Alert>}

      {loading ? (
        <Skeleton className="h-[420px] rounded-[14px]" />
      ) : (
        <AIGenerator subjects={subjects} />
      )}
    </div>
  );
}
