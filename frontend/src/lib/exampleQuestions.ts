/**
 * A worked example for every question type.
 *
 * Examiners hit the same wall on every new type: they know what they want to ask, but
 * not what this particular type expects them to fill in. A "Numerical" question needs a
 * tolerance; a "Fill in the blank" needs every spelling a marker would accept; a coding
 * question needs sample cases. An empty form does not say any of that, and a blank
 * answer-key panel is where questions get saved wrong.
 *
 * So each example is a real, complete, publishable question - body, answer key, and the
 * type-specific configuration filled in the way it is meant to be filled in. It is a
 * starting point, not a template: it seeds a NEW question the examiner rewrites. None of
 * this is ever sent to a candidate; it is examiner-side scaffolding only.
 */

import type { Question, QuestionType } from "@/lib/types";

/**
 * Partial on purpose. An example has no id, no subject, no timestamps - those belong to
 * the exam and the examiner, and inventing them would make the seed look like a saved
 * question.
 */
export type ExampleQuestion = Partial<Question> & {
  /** One line on what this example is demonstrating about the type. */
  note: string;
};

function option(text: string, is_correct = false) {
  return { id: "", question_id: "", text, order_index: 0, is_correct };
}

export const EXAMPLE_QUESTIONS: Record<QuestionType, ExampleQuestion> = {
  mcq: {
    note: "Exactly one option is correct. The wrong options are plausible, not filler.",
    question_type: "mcq",
    body: "Which time complexity describes binary search on a sorted array of n elements?",
    marks: 2,
    topic: "Algorithms",
    explanation: "Each comparison halves the search space, giving log₂n comparisons.",
    options: [
      option("O(log n)", true),
      option("O(n)"),
      option("O(n log n)"),
      option("O(1)"),
    ],
  },

  multi_select: {
    note: "More than one option is correct, and the candidate must find all of them.",
    question_type: "multi_select",
    body: "Which of the following are valid HTTP methods that are idempotent?",
    marks: 3,
    topic: "Web Technologies",
    explanation:
      "GET, PUT and DELETE are idempotent — repeating them leaves the same server state. POST is not.",
    options: [
      option("GET", true),
      option("PUT", true),
      option("DELETE", true),
      option("POST"),
    ],
  },

  true_false: {
    note: "A single claim that is unambiguously true or false — no 'it depends'.",
    question_type: "true_false",
    body: "In a relational database, a primary key column may contain NULL values.",
    marks: 1,
    topic: "Databases",
    explanation: "A primary key is NOT NULL by definition; NULL cannot identify a row.",
    options: [option("True"), option("False", true)],
  },

  fill_blank: {
    note: "List every spelling a human marker would accept, one per line.",
    question_type: "fill_blank",
    body: "The process of organising database tables to reduce redundancy is called ______.",
    marks: 2,
    topic: "Databases",
    explanation: "Accepts the noun and its common variants, since spelling is not the skill tested.",
    spec: {
      kind: "fill_blank",
      accepted_answers: ["normalisation", "normalization", "normalising", "normalizing"],
      case_sensitive: false,
      normalise_whitespace: true,
    },
  },

  numerical: {
    note: "A number plus the tolerance you would accept — rounding is not a wrong answer.",
    question_type: "numerical",
    body:
      "A train travels 240 km in 3 hours. Calculate its average speed in km/h.",
    marks: 2,
    topic: "Quantitative Aptitude",
    explanation: "240 ÷ 3 = 80 km/h.",
    spec: { kind: "numerical", answer: 80, tolerance: 0.5, unit: "km/h" },
  },

  short_answer: {
    note: "Bounded in words, with a model answer and key points the marker looks for.",
    question_type: "short_answer",
    body: "Explain the difference between an index and a primary key in SQL.",
    marks: 5,
    topic: "Databases",
    min_words: 40,
    max_words: 120,
    model_answer:
      "A primary key uniquely identifies each row and enforces NOT NULL and uniqueness. "
      + "An index is a lookup structure that speeds up queries; it does not enforce identity, "
      + "may permit duplicates, and a table can have many indexes but only one primary key.",
    rubric: {
      key_points: [
        "Primary key enforces uniqueness and NOT NULL",
        "Index exists to speed up lookups",
        "One primary key per table, many indexes allowed",
        "Primary key is usually backed by an index automatically",
      ],
      scheme: "1 mark per key point, 1 mark for a clear worked contrast.",
    },
  },

  long_answer: {
    note: "A rubric matters more than a model answer here — the marker needs bands.",
    question_type: "long_answer",
    body:
      "Discuss the trade-offs between normalisation and denormalisation in database design. "
      + "Support your answer with an example of a system where each is the better choice.",
    marks: 10,
    topic: "Databases",
    min_words: 200,
    max_words: 600,
    rubric: {
      key_points: [
        "Normalisation reduces redundancy and update anomalies",
        "Denormalisation reduces join cost on read-heavy workloads",
        "Named trade-off: write consistency against read latency",
        "A concrete example on each side",
      ],
      scheme:
        "0-3 definitions only. 4-6 trade-offs stated but unsupported. "
        + "7-8 trade-offs with one sound example. 9-10 both examples, argued.",
    },
  },

  image_upload: {
    note: "The candidate writes on paper and uploads it; an examiner marks it by hand.",
    question_type: "image_upload",
    body:
      "Draw the ER diagram for a library system with Members, Books and Loans. "
      + "Label every relationship with its cardinality. Photograph your sheet and upload it.",
    marks: 8,
    topic: "Databases",
    rubric: {
      key_points: [
        "Three entities with sensible attributes",
        "Loan modelled as a relationship between Member and Book",
        "Cardinalities labelled and correct",
        "Legible and complete",
      ],
      scheme: "2 marks per key point.",
    },
  },

  passage: {
    note: "A container: write the passage here, then attach the questions that follow it.",
    question_type: "passage",
    body: "Read the passage and answer the questions that follow.",
    marks: 0,
    topic: "Reading Comprehension",
    spec: {
      kind: "passage",
      passage_text:
        "Caching trades memory for time. A cache holds the results of expensive work so "
        + "that repeating the work becomes a lookup. Its value depends entirely on the hit "
        + "rate: a cache that is missed more often than it is hit costs memory, adds a "
        + "lookup to every request, and returns nothing for either. Worse, a stale entry is "
        + "not a slow answer but a wrong one, which is why eviction policy and invalidation "
        + "are the hard parts of caching, not storage.",
      sticky: true,
    },
  },

  coding: {
    note: "Sample cases are shown to the candidate; hidden cases are what actually mark it.",
    question_type: "coding",
    body:
      "Given an array of integers and a target value, return the indices of the two "
      + "numbers that add up to the target. Each input has exactly one solution and you "
      + "may not use the same element twice.",
    marks: 15,
    topic: "Data Structures",
    spec: {
      kind: "coding",
      languages: ["python", "java", "cpp", "javascript"],
      default_language: "python",
      input_format:
        "Line 1: n, the number of elements.\nLine 2: n space-separated integers.\nLine 3: the target.",
      output_format: "Two space-separated indices in ascending order.",
      constraints: "2 ≤ n ≤ 10^5, -10^9 ≤ arr[i] ≤ 10^9. An O(n) solution is expected.",
      sample_cases: [
        { input: "4\n2 7 11 15\n9", output: "0 1", explanation: "arr[0] + arr[1] = 9." },
        { input: "3\n3 2 4\n6", output: "1 2", explanation: "arr[1] + arr[2] = 6." },
      ],
      time_limit_seconds: 2,
    },
  },
};

/** The example for a type, or the MCQ one — every exam has at least one of those. */
export function exampleFor(type: QuestionType): ExampleQuestion {
  return EXAMPLE_QUESTIONS[type] ?? EXAMPLE_QUESTIONS.mcq;
}
