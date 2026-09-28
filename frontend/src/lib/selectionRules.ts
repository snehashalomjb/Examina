/**
 * Reading a selection rule's subject, and matching pool entries to a rule, the same way
 * the backend's paper generator does (`app/services/paper_generator.py::_matches`).
 *
 * Rules saved before `subject_id` was used carry the subject's *name* in `topic`; both
 * shapes resolve to the same subject here, and the backend accepts both.
 */
import type { PoolEntry, SelectionRule, Subject } from "@/lib/types";

const fold = (value: string | null | undefined) => (value ?? "").trim().toLowerCase();

/** The subject a legacy rule named in its `topic`, if that topic is a subject name. */
function legacySubject(rule: SelectionRule, subjects: Subject[]): Subject | undefined {
  if (!rule.topic) return undefined;
  return subjects.find((s) => {
    const names = [s.name, s.base_name].filter((value): value is string => Boolean(value));
    return names.some((name) => fold(name) === fold(rule.topic));
  });
}

/** The subject id a rule narrows to, or null for "any subject". */
export function ruleSubjectId(rule: SelectionRule, subjects: Subject[]): string | null {
  return rule.subject_id || legacySubject(rule, subjects)?.id || null;
}

/** The rule with its subject set (or cleared), dropping a legacy subject-name topic. */
export function withRuleSubject(
  rule: SelectionRule,
  subjectId: string | null,
  subjects: Subject[],
): SelectionRule {
  const topicWasSubject = !rule.subject_id && Boolean(legacySubject(rule, subjects));
  return { ...rule, subject_id: subjectId, topic: topicWasSubject ? null : rule.topic ?? null };
}

/** Whether a pooled question satisfies a rule - type, difficulty, category, subject, topic. */
export function entryMatchesRule(
  entry: PoolEntry,
  rule: SelectionRule,
  subjects: Subject[],
): boolean {
  if (entry.question_type !== rule.question_type) return false;
  if (rule.difficulty && entry.difficulty !== rule.difficulty) return false;
  if (rule.category && entry.category !== rule.category) return false;
  const subjectId = ruleSubjectId(rule, subjects);
  if (subjectId && entry.subject_id !== subjectId) return false;
  // A topic that is really a subject name was handled above; a real topic must match.
  if (rule.topic && !legacySubject(rule, subjects) && fold(entry.topic) !== fold(rule.topic)) {
    return false;
  }
  return true;
}
