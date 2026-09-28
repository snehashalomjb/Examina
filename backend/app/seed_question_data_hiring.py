"""Quantitative, reasoning, verbal, architecture, and coding concept cards."""

from __future__ import annotations

from app.db.models import QuestionCategory as Q

from .seed_question_catalog import fact as F
from .seed_question_catalog import subject

SUBJECTS = (
    subject(
        "APT101",
        "Quantitative Aptitude",
        "Arithmetic, algebra, percentage, ratio, time, and quantitative reasoning.",
        Q.APTITUDE,
        (
            F("Percentage", "percentage change", "Percentage change compares a new value with the original value using the original as denominator.", "Equal percentage increase and decrease do not return to the original amount.", "Identifying the reference value prevents base-denominator errors."),
            F("Ratio and Proportion", "proportion", "A proportion states that two ratios are equal.", "Cross multiplication can solve a missing proportional term.", "Proportional reasoning transfers a known relationship to related quantities."),
            F("Time and Work", "combined work rate", "If people complete a job in t1, t2, and t3 times, their combined rate is 1/t1 + 1/t2 + 1/t3.", "Their combined completion time is the reciprocal of the summed rate.", "Rates add as work per unit time, while completion times generally do not."),
            F("Time, Speed and Distance", "average speed", "Average speed is total distance divided by total time.", "For equal distances, average speed is the harmonic mean of the two speeds.", "Correct time weighting matters whenever speed changes during a journey."),
            F("Profit and Loss", "profit percentage", "Profit percentage is profit divided by cost price, multiplied by 100.", "Selling price equals cost price multiplied by one plus the profit rate.", "The cost-price basis is central to comparing commercial gains and losses."),
            F("Data Interpretation", "pie-chart percentage", "A category's angle in a pie chart is its share of the total multiplied by 360 degrees.", "Shares represented by slices must sum to the whole.", "Relating share, angle, and count makes chart interpretation verifiable."),
        ),
    ),
    subject(
        "LOG101",
        "Logical Reasoning",
        "Deduction, set relations, truth tables, coding, ranking, and conditional reasoning.",
        Q.LOGICAL_REASONING,
        (
            F("Sets", "subset", "A set A is a subset of B when every element of A is also in B.", "Every set is a subset of itself under the non-strict definition.", "Subset relations underpin comparisons between categories and possible worlds."),
            F("Truth Tables", "contradiction", "A contradiction is a compound proposition false under every assignment.", "A formula true under every assignment is a tautology.", "Truth-value classification tests whether an argument is logically valid."),
            F("Syllogism", "valid syllogism", "A syllogism is valid when its conclusion follows necessarily from its premises.", "In a valid argument, true premises cannot produce a false conclusion.", "Validity concerns inference form rather than empirical truth."),
            F("Coding-Decoding", "coding key", "A monoalphabetic decoding key assigns each encoded symbol one consistent original item.", "A one-to-one key cannot map two plaintext symbols to one ciphertext symbol.", "Consistency constraints make encoded-pattern reasoning decidable."),
            F("Ranking", "ranking constraint", "A statement that one person is not last rules out only that single final position.", "Combining pairwise inequalities can determine a unique ordering.", "Rank puzzles are solved by applying only the stated order constraints."),
            F("Conditional Reasoning", "modus ponens", "From P and if P then Q, modus ponens licenses the conclusion Q.", "Denying the antecedent is a formal fallacy.", "Valid conditional rules distinguish sound inference from reversal errors."),
        ),
    ),
    subject(
        "VRB101",
        "Verbal Ability & English",
        "Grammar, syntax, reading inference, vocabulary, and authorial tone.",
        Q.VERBAL_ABILITY,
        (
            F("Grammar", "subject-verb agreement", "A singular subject normally takes a singular present-tense verb.", "The verb agrees with the grammatical subject rather than a nearby noun.", "Agreement errors can obscure who performs an action."),
            F("Voice", "active voice", "Active voice places the subject before the action verb.", "The doer is generally more direct in the active voice than in the passive voice.", "Voice changes can alter emphasis as well as grammatical structure."),
            F("Sentence Structure", "dangling modifier", "A dangling modifier lacks a clear subject and can accidentally attach to the wrong noun.", "Placing the subject immediately before the participial phrase prevents ambiguity.", "Modifier placement controls which actor receives the described action."),
            F("Reading", "textual inference", "A defensible inference follows from evidence stated or implied in a passage.", "A personal preference is not a textual inference.", "Inference questions test reasoning grounded in the text rather than outside assumptions."),
            F("Tone", "authorial tone", "Authorial tone is the attitude conveyed by word choice, detail, and sentence style.", "Diction and syntax provide evidence for identifying tone.", "Tone analysis distinguishes narrator attitude from literal subject matter."),
            F("Vocabulary", "context clue", "A context clue is a nearby word, example, contrast, or inference that signals a term's meaning.", "Eliminating meanings incompatible with the sentence can reveal an unfamiliar term.", "Contextual vocabulary strategies make meaning recoverable without memorisation alone."),
        ),
    ),
    subject(
        "TECH101",
        "Core Technical & System Design",
        "Web architecture, APIs, reliability, scalability, caching, and observability.",
        Q.TECHNICAL,
        (
            F("API Design", "idempotent request", "An idempotent request produces the same intended state when repeated.", "HTTP GET and PUT are designed to be idempotent.", "Idempotency makes retries safe in unreliable networks."),
            F("Scalability", "horizontal scaling", "Horizontal scaling adds application instances rather than resources to one machine.", "A load balancer can distribute requests across those instances.", "Horizontal growth often improves availability as well as capacity."),
            F("Caching", "cache invalidation", "Cache invalidation removes or refreshes stored data after the source changes.", "A time-to-live policy can expire entries without an explicit delete.", "Correct invalidation prevents stale data while preserving performance benefits."),
            F("Reliability", "retry with backoff", "Exponential backoff increases the delay between retries after failures.", "Retries should generally have a bound and often need jitter.", "Backoff reduces synchronized retry pressure on a recovering dependency."),
            F("Distributed Systems", "CAP trade-off", "During a network partition, a distributed system trades consistency against availability.", "CAP does not claim that a healthy system chooses only two of three properties forever.", "The partition trade-off guides database and service behaviour under failure."),
            F("Observability", "distributed trace", "A distributed trace follows a request across participating services.", "Trace context propagates correlation identifiers between service calls.", "Tracing helps locate latency and failures across service boundaries."),
        ),
    ),
    subject(
        "CODE101",
        "Programming Challenges",
        "Algorithmic implementation, data structures, complexity, and testing.",
        Q.CODING,
        (
            F("Complexity", "constant-time lookup", "A hash table provides average O(1) lookup by key.", "Hash-table lookup is amortised rather than guaranteed constant time for every key.", "Complexity analysis determines whether a lookup strategy scales."),
            F("Data Structures", "stack", "A stack returns the most recently pushed item first.", "A stack can be implemented with a dynamic array.", "LIFO structure models nested calls, undo history, and backtracking."),
            F("Algorithms", "recursion", "Recursion solves a problem through calls on smaller instances of the same problem.", "Every recursive solution needs a reachable base case.", "Recursion must balance decomposition against call-stack usage."),
            F("Algorithms", "dynamic programming", "Dynamic programming reuses results for overlapping subproblems.", "A bottom-up or top-down program can store those results.", "Memoisation turns exponential recomputation into polynomial work for suitable problems."),
            F("Testing", "boundary-value test", "A boundary-value test exercises values immediately around a documented range boundary.", "Equivalent partitions group inputs expected to receive the same handling.", "Boundary testing targets off-by-one and edge-case defects."),
            F("Debugging", "minimal reproduction", "A minimal reproduction contains the smallest reliable input and steps that still exhibit a defect.", "Isolating variables makes the failing condition easier to inspect.", "Focused reproductions improve diagnosis and enable regression tests."),
        ),
    ),
)
