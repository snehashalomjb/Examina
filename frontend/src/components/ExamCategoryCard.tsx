"use client";

import React from "react";
import { Badge, Card, cx } from "@/components/ui";

export type ExamCategoryType = "academic" | "corporate";

interface ExamCategoryCardProps {
  category: ExamCategoryType;
  selected?: boolean;
  onSelect: (category: ExamCategoryType) => void;
}

export function ExamCategoryCard({
  category,
  selected = false,
  onSelect,
}: ExamCategoryCardProps) {
  const isAcademic = category === "academic";

  return (
    <div
      onClick={() => onSelect(category)}
      className={cx(
        "group relative flex flex-col justify-between rounded-2xl border p-6 transition-all duration-300 cursor-pointer",
        selected
          ? isAcademic
            ? "border-accent bg-accent-soft/30 shadow-lg shadow-accent/10 ring-2 ring-accent"
            : "border-purple-500 bg-purple-50/40 dark:bg-purple-950/20 shadow-lg shadow-purple-500/10 ring-2 ring-purple-500"
          : "border-line bg-surface hover:border-line-strong hover:shadow-md"
      )}
    >
      {/* Selected checkmark indicator */}
      {selected && (
        <div
          className={cx(
            "absolute top-4 right-4 flex h-6 w-6 items-center justify-center rounded-full text-white text-xs font-bold shadow",
            isAcademic ? "bg-accent" : "bg-purple-600"
          )}
        >
          ✓
        </div>
      )}

      <div>
        {/* Header with Icon and Badge */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className={cx(
              "flex h-12 w-12 items-center justify-center rounded-xl text-2xl shadow-sm transition-transform group-hover:scale-105",
              isAcademic
                ? "bg-accent-soft text-accent"
                : "bg-purple-100 text-purple-600 dark:bg-purple-900/40 dark:text-purple-300"
            )}
          >
            {isAcademic ? "🎓" : "💼"}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-ink">
                {isAcademic ? "Academic Exam" : "Corporate Hiring Exam"}
              </h3>
              <Badge tone={isAcademic ? "accent" : "purple"}>
                {isAcademic ? "Education" : "Recruitment"}
              </Badge>
            </div>
            <p className="text-xs text-ink-muted mt-0.5">
              {isAcademic
                ? "Colleges, Universities, Schools & Courses"
                : "Companies, Startups & Recruitment Drives"}
            </p>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-ink-muted leading-relaxed mb-5">
          {isAcademic
            ? "Designed for semester finals, mid-terms, subject quizzes, and laboratory exams with rich rubrics, essay evaluation, and negative marking."
            : "Engineered for talent acquisition with multi-section timing, aptitude filtering, live coding challenges, and candidate shortlisting."}
        </p>

        {/* Feature List */}
        <div className="space-y-2 border-t border-line/60 pt-4 mb-4">
          <div className="text-xs font-semibold text-ink-subtle uppercase tracking-wider mb-2">
            Key Capabilities
          </div>
          {(isAcademic
            ? [
                "Course, Department & Semester metadata",
                "Mixed question formats (MCQ, Short, Essay, Image upload)",
                "AI-assisted rubric grading with human-in-the-loop",
                "Speed quizzes with instant result auto-publishing",
                "6 Academic blueprint patterns included",
              ]
            : [
                "Company Name & Target Job Role binding",
                "Multi-section papers with individual timers & cutoffs",
                "Aptitude, Reasoning, Technical & Coding evaluation",
                "Candidate Shortlisting & Recruitment Ranking",
                "6 Corporate hiring blueprint patterns included",
              ]
          ).map((feature, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-ink">
              <span
                className={cx(
                  "font-bold mt-0.5",
                  isAcademic ? "text-accent" : "text-purple-600 dark:text-purple-400"
                )}
              >
                •
              </span>
              <span>{feature}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Button */}
      <div className="pt-2">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onSelect(category);
          }}
          className={cx(
            "w-full rounded-xl py-2.5 px-4 text-xs font-semibold tracking-wide transition-colors",
            selected
              ? isAcademic
                ? "bg-accent text-white shadow"
                : "bg-purple-600 text-white shadow"
              : "bg-surface-soft text-ink hover:bg-surface-elevated border border-line"
          )}
        >
          {selected
            ? `✓ Selected ${isAcademic ? "Academic" : "Corporate"} Mode`
            : `Select ${isAcademic ? "Academic" : "Corporate"} Mode`}
        </button>
      </div>
    </div>
  );
}
