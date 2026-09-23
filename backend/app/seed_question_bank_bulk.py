"""Top up the question bank so every subject has real depth to browse, per type.

The curated seed in ``app.seed`` writes a strong, hand-picked sample of every type but
stops well short of what a bank needs to feel like a bank - a handful of MCQs is a demo,
not something an examiner can build a real paper's rules against. This tops each
*(subject, question type)* combination up to a floor, generating genuinely distinct,
subject-appropriate questions (computed arithmetic, per-domain vocabularies, parametrised
coding problems) rather than repeating a small stub template.

Two things this module owns that earlier versions did not:

- **Per-subject type appropriateness.** A coding question never lands on Verbal Ability,
  a numerical question never lands on Grammar - see ``SUBJECT_PROFILES``. A subject with
  no profile gets a conservative generic set (no coding, no numerical, no passage) rather
  than every type indiscriminately.
- **Per-subject category.** Corporate section rules select on ``Question.category``
  (aptitude / verbal_ability / logical_reasoning / technical / coding), so every question
  this module writes is tagged with the category its subject actually belongs to, not a
  blanket ``academic``.

Idempotent like the rest of the seed: run it again and it only adds what a
(subject, type) combination is still short of, keyed off a count of questions already
carrying this module's tag.
"""

from __future__ import annotations

import random
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import (
    Difficulty,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionStatus,
    QuestionType,
    Subject,
    User,
)

logger = get_logger("seed_bulk")

#: Every (subject, question type) combination this module recognises gets topped up to
#: this many questions. "Approximately 200 questions per type per subject."
FLOOR_PER_TYPE = 200

#: Marks this function's own rows carry, so a re-run can tell "already topped up" from
#: "an examiner deleted some and it should top up again" without touching anyone else's
#: hand-written or AI-approved questions.
BULK_TAG = "bulk-seed"

_DIFFICULTIES = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD]

MCQ = QuestionType.MCQ
MSEL = QuestionType.MULTI_SELECT
TF = QuestionType.TRUE_FALSE
FB = QuestionType.FILL_BLANK
NUM = QuestionType.NUMERICAL
SA = QuestionType.SHORT_ANSWER
LA = QuestionType.LONG_ANSWER
IMG = QuestionType.IMAGE_UPLOAD
PASSAGE = QuestionType.PASSAGE
CODING = QuestionType.CODING


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % d for d in range(2, int(n**0.5) + 1))


def _make(
    *,
    subject: Subject,
    creator: User,
    qtype: QuestionType,
    category: QuestionCategory,
    topic: str,
    body: str,
    difficulty: Difficulty,
    marks: float,
    negative: float = 0.0,
    options: list[tuple[str, bool]] | None = None,
    model_answer: str | None = None,
    explanation: str | None = None,
    spec: dict[str, Any] | None = None,
    rubric: dict[str, Any] | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
) -> Question:
    question = Question(
        subject_id=subject.id,
        question_type=qtype,
        category=category,
        topic=topic,
        difficulty=difficulty,
        body=body,
        model_answer=model_answer,
        explanation=explanation,
        marks=marks,
        negative_marks=negative,
        spec=spec,
        rubric=rubric,
        min_words=min_words,
        max_words=max_words,
        created_by_id=creator.id,
        tags=[BULK_TAG, subject.code.lower(), topic.lower().replace(" ", "-")],
        status=QuestionStatus.PUBLISHED,
        is_active=True,
    )
    for index, (text, correct) in enumerate(options or []):
        question.options.append(QuestionOption(text=text, is_correct=correct, order_index=index))
    return question


# ===========================================================================
# Domain vocabularies - term -> one-line definition. Each subject's profile
# points at exactly one of these, so a Python question reads like Python and a
# Networks question reads like Networks, instead of one shared mad-lib.
# ===========================================================================

_DSA_VOCAB: list[tuple[str, str]] = [
    ("Hash table", "a structure that maps keys to values using a hash function for near O(1) average lookup"),
    ("Binary search tree", "a tree where every left descendant is smaller and every right descendant is larger than its parent"),
    ("Recursion", "a function solving a problem by calling itself on a smaller version of the same problem"),
    ("Time complexity", "a measure of how an algorithm's running time grows as its input size grows"),
    ("Space complexity", "a measure of how much extra memory an algorithm needs as its input size grows"),
    ("Greedy algorithm", "an approach that makes the locally optimal choice at each step, hoping it leads to a global optimum"),
    ("Dynamic programming", "solving a problem by breaking it into overlapping subproblems and caching their results"),
    ("Graph traversal", "systematically visiting every vertex of a graph, typically via breadth-first or depth-first search"),
    ("Amortised analysis", "averaging the cost of an operation over a sequence of operations, rather than the worst single case"),
    ("Big-O notation", "a way of describing an algorithm's growth rate as input size approaches infinity"),
    ("Linked list", "a sequence of nodes where each node points to the next, allowing O(1) insertion at a known position"),
    ("Queue", "a first-in, first-out data structure typically used to process items in arrival order"),
    ("Stack", "a last-in, first-out data structure used for things like function call tracking and undo history"),
    ("Binary heap", "a complete binary tree that keeps its minimum, or maximum, element at the root"),
    ("Hashing collision", "when two distinct keys map to the same slot in a hash table, requiring a resolution strategy"),
    ("Trie", "a tree that stores strings by sharing common prefixes among its branches"),
    ("Divide and conquer", "solving a problem by splitting it into independent subproblems, solving each, and combining the results"),
    ("Adjacency list", "a graph representation storing, for each vertex, the list of vertices it connects to"),
    ("Depth-first search", "a traversal that explores as far as possible along each branch before backtracking"),
    ("Breadth-first search", "a traversal that visits all neighbours of a vertex before moving to the next level"),
]

_DB_VOCAB: list[tuple[str, str]] = [
    ("Normalisation", "the process of organising database tables to reduce redundancy and avoid update anomalies"),
    ("Primary key", "a column, or set of columns, that uniquely identifies every row in a table"),
    ("Foreign key", "a column that references the primary key of another table, enforcing referential integrity"),
    ("ACID properties", "the atomicity, consistency, isolation and durability guarantees a database transaction provides"),
    ("Index", "a data structure that speeds up lookups on a column at the cost of extra storage and write overhead"),
    ("Transaction isolation level", "how strictly a database prevents one transaction from seeing another's uncommitted changes"),
    ("Composite key", "a primary key made up of two or more columns whose combination is unique"),
    ("Denormalisation", "deliberately introducing redundancy into a schema to speed up reads at the cost of write complexity"),
    ("Referential integrity", "the guarantee that a foreign key always points to a row that actually exists"),
    ("Candidate key", "any column, or set of columns, that could uniquely identify a row and so could serve as the primary key"),
    ("Entity-relationship model", "a diagrammatic way of describing a database's entities and how they relate to each other"),
    ("View", "a saved query that behaves like a virtual table, without storing the data itself"),
]

_OS_VOCAB: list[tuple[str, str]] = [
    ("Deadlock", "a state where two or more processes are each waiting on a resource the other holds"),
    ("Semaphore", "a synchronisation primitive that controls access to a shared resource using a counter"),
    ("Virtual memory", "an abstraction that gives each process its own address space backed by disk and RAM"),
    ("Paging", "a memory management scheme that divides memory into fixed-size frames to avoid external fragmentation"),
    ("Race condition", "a bug where the outcome depends on the unpredictable timing of concurrent operations"),
    ("Mutex", "a lock that ensures only one thread can access a critical section of code at a time"),
    ("Thread starvation", "when a thread is perpetually denied the resources it needs to make progress"),
    ("Garbage collection", "automatic reclamation of memory that a running program can no longer reach"),
    ("Context switch", "the act of saving one process's state and loading another's so the CPU can run it instead"),
    ("Scheduling algorithm", "a policy the OS uses to decide which ready process runs on the CPU next"),
    ("Fragmentation", "wasted memory left over as small, unusable gaps between allocated blocks"),
    ("Thrashing", "a state where a system spends more time swapping pages than doing useful work"),
]

_NET_VOCAB: list[tuple[str, str]] = [
    ("TCP three-way handshake", "the SYN, SYN-ACK, ACK exchange that establishes a reliable TCP connection"),
    ("Subnetting", "dividing a network into smaller sub-networks by borrowing bits from the host portion of an address"),
    ("DNS", "the system that translates human-readable domain names into IP addresses"),
    ("Load balancer", "a component that distributes incoming requests across multiple servers"),
    ("Horizontal scaling", "adding more machines to handle load, rather than making one machine more powerful"),
    ("Eventual consistency", "a guarantee that replicas converge to the same value given enough time without new writes"),
    ("CAP theorem", "the claim that a distributed system can guarantee at most two of consistency, availability and partition tolerance"),
    ("Firewall", "a system that filters network traffic based on a set of security rules"),
    ("Latency", "the time it takes for a single piece of data to travel from sender to receiver"),
    ("Bandwidth", "the maximum rate at which data can be transferred over a network link"),
    ("NAT", "network address translation, which lets many devices on a private network share one public IP address"),
    ("HTTP status code", "a three-digit code a server returns describing the outcome of a request, such as 200 or 404"),
]

_WEB_VOCAB: list[tuple[str, str]] = [
    ("Polymorphism", "the ability of different objects to respond to the same interface, each in its own way"),
    ("Encapsulation", "bundling data and the methods that operate on it, hiding internal state from outside access"),
    ("REST", "an architectural style for web APIs built around stateless requests and standard HTTP methods"),
    ("Idempotent request", "a request that produces the same server state no matter how many times it is repeated"),
    ("Caching", "storing the result of expensive work so a repeated request becomes a lookup instead"),
    ("Microservices", "an architecture where an application is built as a set of small, independently deployable services"),
    ("API rate limiting", "restricting how many requests a client may make in a given time window"),
    ("Continuous integration", "automatically building and testing every change merged into a shared codebase"),
    ("Version control", "a system that tracks changes to source code over time so past states can be recovered"),
    ("Responsive design", "building an interface that adapts its layout to the size of the screen it's viewed on"),
    ("Dependency injection", "supplying an object's dependencies from outside rather than having it construct them itself"),
    ("Middleware", "code that runs between receiving a request and producing a response, often for logging or auth"),
]

_ML_VOCAB: list[tuple[str, str]] = [
    ("Gradient descent", "an optimisation algorithm that iteratively adjusts parameters to minimise a loss function"),
    ("Backpropagation", "the algorithm that computes gradients of a neural network's loss with respect to its weights"),
    ("Overfitting", "when a model learns the training data's noise instead of its underlying pattern, hurting generalisation"),
    ("Regularisation", "a technique that penalises model complexity to reduce overfitting"),
    ("Supervised learning", "training a model on labelled examples so it learns to map inputs to known outputs"),
    ("Unsupervised learning", "finding structure in data with no labelled outputs to learn from"),
    ("Confusion matrix", "a table summarising a classifier's correct and incorrect predictions across each class"),
    ("Precision", "of everything a model labelled positive, the fraction that was actually positive"),
    ("Recall", "of everything that was actually positive, the fraction the model correctly labelled positive"),
    ("Bias-variance trade-off", "the tension between a model being too simple to fit the data and too complex to generalise"),
    ("Feature engineering", "transforming raw data into inputs that make a model's job of learning easier"),
    ("Cross-validation", "splitting data into folds and rotating which fold is held out, to estimate how a model generalises"),
]

_DL_VOCAB: list[tuple[str, str]] = [
    ("Convolutional layer", "a neural network layer that applies learned filters across spatial regions of its input"),
    ("Recurrent neural network", "a network architecture designed to process sequences by carrying a hidden state forward"),
    ("Attention mechanism", "a technique that lets a model weigh different parts of its input differently when producing an output"),
    ("Dropout", "a regularisation technique that randomly disables neurons during training to reduce overfitting"),
    ("Activation function", "a non-linear function applied to a neuron's output, letting a network learn non-linear patterns"),
    ("Batch normalisation", "a technique that normalises a layer's inputs to stabilise and speed up training"),
    ("Vanishing gradient", "when gradients shrink so much during backpropagation that early layers barely learn"),
    ("Transformer", "a neural architecture built entirely on attention, without recurrence or convolution"),
    ("Epoch", "one complete pass of the training algorithm over the entire training dataset"),
    ("Learning rate", "a hyperparameter controlling how large a step gradient descent takes at each update"),
]

_NLP_VOCAB: list[tuple[str, str]] = [
    ("Tokenisation", "splitting text into smaller units - words, subwords, or characters - for a language model to process"),
    ("Word embedding", "a dense vector representation of a word that captures some of its meaning and usage"),
    ("Attention mechanism", "a technique that lets a model weigh different parts of its input differently when producing an output"),
    ("Named entity recognition", "identifying and classifying spans of text as people, places, organisations, and similar"),
    ("Stemming", "reducing a word to a crude root form by chopping off common suffixes"),
    ("Lemmatisation", "reducing a word to its dictionary base form using vocabulary and grammar rules"),
    ("Bag of words", "a text representation counting word occurrences while ignoring order and grammar"),
    ("Language model", "a model that assigns a probability to a sequence of words, used to predict or generate text"),
    ("Stop words", "common words like 'the' or 'is' that are often filtered out before text analysis"),
    ("Part-of-speech tagging", "labelling each word in a sentence with its grammatical role, such as noun or verb"),
]

_AI_VOCAB: list[tuple[str, str]] = [
    ("Knowledge representation", "how an AI system encodes facts about the world so it can reason over them"),
    ("Heuristic search", "a search strategy that uses problem-specific knowledge to find good solutions faster"),
    ("Turing test", "a test of whether a machine's conversation is indistinguishable from a human's"),
    ("Agent", "an entity that perceives its environment through sensors and acts upon it through actuators"),
    ("A* search", "a search algorithm that finds the shortest path using both the cost so far and an estimated cost to goal"),
    ("Constraint satisfaction problem", "a problem defined by variables, their possible values, and constraints between them"),
    ("Expert system", "a program that emulates the decision-making of a human expert using a base of encoded rules"),
    ("Reinforcement learning", "training an agent to make decisions by rewarding or penalising the outcomes of its actions"),
]

_CORE_VOCAB: list[tuple[str, str]] = [
    ("Eventual consistency", "a guarantee that replicas converge to the same value given enough time without new writes"),
    ("CAP theorem", "the claim that a distributed system can guarantee at most two of consistency, availability and partition tolerance"),
    ("Public-key cryptography", "an encryption scheme using a public key to encrypt and a private key to decrypt"),
    ("Digital signature", "cryptographic proof that a message came from a specific sender and was not altered"),
    ("Symmetric encryption", "encryption that uses the same key for both encrypting and decrypting a message"),
    ("Compiler", "a program that translates source code written in one language into another, typically machine code"),
    ("Load balancer", "a component that distributes incoming requests across multiple servers"),
    ("Horizontal scaling", "adding more machines to handle load, rather than making one machine more powerful"),
    ("API rate limiting", "restricting how many requests a client may make in a given time window"),
    ("Message queue", "a component that lets services communicate asynchronously by passing messages through a buffer"),
    ("Circuit breaker", "a pattern that stops calling a failing dependency for a while, to let it recover"),
]

_PYTHON_VOCAB: list[tuple[str, str]] = [
    ("List comprehension", "a concise syntax for building a list by iterating over, and optionally filtering, an iterable"),
    ("Generator", "a function that yields values lazily one at a time using `yield`, instead of building a full list at once"),
    ("Decorator", "a function that wraps another function to extend its behaviour without modifying its source code"),
    ("GIL", "the Global Interpreter Lock, a mutex that lets only one thread execute Python bytecode at a time in CPython"),
    ("Duck typing", "a style where an object's suitability is judged by the methods and properties it has, not its declared type"),
    ("Context manager", "an object defining `__enter__` and `__exit__` so it can be used with the `with` statement"),
    ("Mutable default argument", "a common pitfall where a default argument like a list is created once and shared across calls"),
    ("Lambda", "a small anonymous function defined with the `lambda` keyword, limited to a single expression"),
    ("Slicing", "extracting a sub-sequence from a list or string using the `start:stop:step` syntax"),
    ("Virtual environment", "an isolated Python installation that keeps a project's dependencies separate from the system interpreter"),
    ("Dictionary comprehension", "a concise syntax for building a dict by iterating over, and optionally filtering, an iterable"),
    ("Iterator protocol", "the `__iter__` and `__next__` methods that let an object be looped over with a `for` loop"),
    ("Module", "a single `.py` file of Python definitions that can be imported and reused elsewhere"),
    ("List vs tuple", "a list is mutable and defined with `[]`; a tuple is immutable and defined with `()`"),
    ("args and kwargs", "syntax (`*args`, `**kwargs`) that lets a function accept an arbitrary number of positional and keyword arguments"),
]

_JAVA_VOCAB: list[tuple[str, str]] = [
    ("JVM", "the Java Virtual Machine, the runtime that executes compiled Java bytecode"),
    ("Garbage collection", "automatic reclamation of memory no longer referenced by a running Java program"),
    ("Interface", "a contract declaring methods a class must implement, without providing their implementation"),
    ("Abstract class", "a class that cannot be instantiated directly and may mix implemented and unimplemented methods"),
    ("Inheritance", "a mechanism where a subclass acquires the fields and methods of a superclass"),
    ("Polymorphism", "the ability for a superclass reference to invoke a subclass's overridden method at runtime"),
    ("Encapsulation", "bundling fields and methods together and restricting direct access to an object's internal state"),
    ("Collections framework", "Java's built-in library of data structures such as List, Set, and Map"),
    ("Multithreading", "running multiple threads concurrently within a single Java program"),
    ("Static keyword", "marks a field or method as belonging to the class itself rather than to any individual instance"),
    ("Constructor", "a special method invoked when an object is created, used to initialise its fields"),
    ("Generics", "a feature letting classes and methods operate on typed parameters, catching type errors at compile time"),
    ("Autoboxing", "Java's automatic conversion between a primitive type and its corresponding wrapper class"),
]

_SQL_VOCAB: list[tuple[str, str]] = [
    ("INNER JOIN", "returns only the rows that have matching values in both joined tables"),
    ("LEFT JOIN", "returns every row from the left table, with NULLs where no match exists in the right table"),
    ("GROUP BY", "groups rows sharing the same value in specified columns so aggregate functions can summarise each group"),
    ("HAVING", "filters groups produced by GROUP BY, the way WHERE filters individual rows"),
    ("Subquery", "a query nested inside another query, used to compute a value or a set the outer query needs"),
    ("View", "a saved query that behaves like a virtual table, without storing the data itself"),
    ("Trigger", "a stored procedure that runs automatically in response to an insert, update, or delete on a table"),
    ("UNION", "combines the result sets of two queries into one, removing duplicate rows by default"),
    ("DISTINCT", "removes duplicate rows from a query's result set"),
    ("Stored procedure", "a precompiled block of SQL statements saved in the database and invoked by name"),
    ("Window function", "a function that computes a value across a set of rows related to the current row without collapsing them"),
    ("Aggregate function", "a function like SUM, COUNT, AVG, MIN or MAX that computes a single value from a set of rows"),
]

_MATH_VOCAB: list[tuple[str, str]] = [
    ("Percentage", "a way of expressing a number as a fraction of 100"),
    ("Ratio", "a comparison of two quantities showing how many times one contains the other"),
    ("Profit and loss", "the difference between a selling price and a cost price, expressed as a gain or a shortfall"),
    ("Simple interest", "interest calculated only on the original principal for the whole loan period"),
    ("Compound interest", "interest calculated on the principal plus any interest already accumulated"),
    ("Time and work", "problems relating how long a task takes to the rate at which it is done"),
    ("Time, speed and distance", "problems relating distance travelled to speed and the time taken"),
    ("Permutation", "an arrangement of items where the order matters"),
    ("Combination", "a selection of items where the order does not matter"),
    ("Probability", "a measure, between 0 and 1, of how likely an event is to occur"),
    ("Average", "the sum of a set of values divided by how many values there are"),
    ("LCM", "the least common multiple, the smallest number divisible by every number in a given set"),
    ("HCF", "the highest common factor, the largest number that divides every number in a given set exactly"),
    ("Mixture and alligation", "a method for finding the ratio in which ingredients must be mixed to reach a desired result"),
    ("Data interpretation", "extracting and reasoning about numeric conclusions from a table, chart, or graph"),
    ("Standard deviation", "a measure of how spread out a set of values is around their mean"),
]

_VERBAL_VOCAB: list[tuple[str, str]] = [
    ("Abundant", "Plentiful"), ("Candid", "Frank"), ("Diligent", "Hardworking"),
    ("Eloquent", "Articulate"), ("Frugal", "Thrifty"), ("Genuine", "Authentic"),
    ("Hostile", "Antagonistic"), ("Immense", "Enormous"), ("Judicious", "Wise"),
    ("Keen", "Enthusiastic"), ("Lucid", "Clear"), ("Meticulous", "Careful"),
    ("Novice", "Beginner"), ("Obstinate", "Stubborn"), ("Pragmatic", "Practical"),
    ("Quaint", "Charming"), ("Reticent", "Reserved"), ("Superficial", "Shallow"),
    ("Tedious", "Tiresome"), ("Vivid", "Striking"), ("Wary", "Cautious"),
    ("Zealous", "Passionate"), ("Ambiguous", "Unclear"), ("Benevolent", "Kind-hearted"),
]

_ANTONYM_VOCAB: list[tuple[str, str]] = [
    ("Ancient", "Modern"), ("Brave", "Cowardly"), ("Cautious", "Reckless"),
    ("Deny", "Admit"), ("Expand", "Contract"), ("Fragile", "Sturdy"),
    ("Generous", "Stingy"), ("Humble", "Arrogant"), ("Include", "Exclude"),
    ("Joyful", "Sorrowful"), ("Kind", "Cruel"), ("Loyal", "Treacherous"),
    ("Modest", "Vain"), ("Optimistic", "Pessimistic"), ("Permanent", "Temporary"),
    ("Rigid", "Flexible"),
]


def _cs_fund_vocab() -> list[tuple[str, str]]:
    return _DSA_VOCAB[:6] + _DB_VOCAB[:4] + _OS_VOCAB[:4] + _NET_VOCAB[:4]


# ===========================================================================
# Generic (vocabulary-driven) generators - used by every technical/CS domain.
# Each takes the domain's own vocab list, so the same generator produces
# Python-flavoured, Networks-flavoured, or ML-flavoured content depending on
# what it's handed.
# ===========================================================================


def _mk_fill_blank(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        term, definition = vocab[(start + i) % len(vocab)]
        out.append(_make(
            subject=subject, creator=examiner, qtype=FB, category=category,
            topic=subject.name,
            body=f"___ is {definition}.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0,
            explanation=f"{term} — {definition}.",
            spec={"kind": "fill_blank", "accepted_answers": [term, term.lower(), term.upper()], "case_sensitive": False},
        ))
    return out


def _mk_short_answer(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        term, definition = vocab[(start + i) % len(vocab)]
        out.append(_make(
            subject=subject, creator=examiner, qtype=SA, category=category,
            topic=subject.name,
            body=f"In one or two sentences, explain what {term.lower()} is.",
            difficulty=_DIFFICULTIES[i % 3], marks=4.0,
            model_answer=f"{term} is {definition}.",
            min_words=15, max_words=80,
            rubric={"key_points": [f"Names {term.lower()} correctly", "Gives an accurate one-line definition"],
                    "scheme": "2 marks for identifying the concept, 2 marks for an accurate explanation."},
        ))
    return out


def _mk_long_answer(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        term, _ = vocab[(start + i) % len(vocab)]
        term2, _ = vocab[(start + i + 7) % len(vocab)]
        if term2 == term:
            term2, _ = vocab[(start + i + 3) % len(vocab)]
        out.append(_make(
            subject=subject, creator=examiner, qtype=LA, category=category,
            topic=subject.name,
            body=(f"Compare {term.lower()} and {term2.lower()}. Discuss how they differ, "
                  "where each is used, and give one concrete example of each in practice."),
            difficulty=_DIFFICULTIES[(i + 1) % 3], marks=10.0,
            min_words=150, max_words=500,
            rubric={"key_points": [f"Correctly defines {term.lower()}", f"Correctly defines {term2.lower()}",
                                    "States at least one genuine difference", "Gives a concrete example for each"],
                    "scheme": "Up to 2-3 marks per key point, capped at 10."},
        ))
    return out


def _mk_image_upload(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        term, definition = vocab[(start + i) % len(vocab)]
        out.append(_make(
            subject=subject, creator=examiner, qtype=IMG, category=category,
            topic=subject.name,
            body=f"On paper, sketch a labelled diagram illustrating {term.lower()} ({definition}). Photograph your sheet and upload it.",
            difficulty=_DIFFICULTIES[i % 3], marks=6.0,
            rubric={"key_points": ["Diagram is labelled", "Structure/flow is correct", "Legible and complete"],
                    "scheme": "2 marks per key point."},
        ))
    return out


def _mk_passage(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        a = vocab[(start + i) % len(vocab)]
        b = vocab[(start + i + 1) % len(vocab)]
        c = vocab[(start + i + 2) % len(vocab)]
        passage_text = (
            f"{a[0]} refers to {a[1]}. Related to it is {b[0].lower()}, which is {b[1]}. "
            f"A third, often confused concept is {c[0].lower()}: {c[1]}. Understanding how "
            f"these three relate is central to {subject.name.lower()}."
        )
        out.append(_make(
            subject=subject, creator=examiner, qtype=PASSAGE, category=category,
            topic=subject.name,
            body="Read the passage and answer the questions that follow.",
            difficulty=_DIFFICULTIES[i % 3], marks=0.0,
            spec={"kind": "passage", "passage_text": passage_text, "sticky": True},
        ))
    return out


def _mk_mcq_concept(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    """"Which of the following best defines X?" - one correct definition, three wrong
    ones borrowed from other terms in the same domain."""
    out = []
    for i in range(needed):
        term, correct_def = vocab[(start + i) % len(vocab)]
        wrong_defs = []
        offset = 1
        while len(wrong_defs) < 3:
            _, d = vocab[(start + i + offset) % len(vocab)]
            if d != correct_def and d not in wrong_defs:
                wrong_defs.append(d)
            offset += 1
            if offset > len(vocab) + 5:
                break
        while len(wrong_defs) < 3:
            wrong_defs.append(correct_def + " (variant)")
        choices = [(correct_def.capitalize(), True)] + [(d.capitalize(), False) for d in wrong_defs]
        random.Random(f"mcqc-{subject.code}-{i}").shuffle(choices)
        out.append(_make(
            subject=subject, creator=examiner, qtype=MCQ, category=category,
            topic=subject.name,
            body=f"Which of the following best describes '{term}'?",
            difficulty=_DIFFICULTIES[i % 3], marks=2.0, negative=0.5,
            explanation=f"{term} — {correct_def}.",
            options=choices,
        ))
    return out


def _mk_true_false_concept(subject: Subject, examiner: User, category: QuestionCategory, vocab, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        term, correct_def = vocab[(start + i) % len(vocab)]
        is_true = i % 2 == 0
        if is_true:
            claim_def = correct_def
        else:
            _, claim_def = vocab[(start + i + 5) % len(vocab)]
            if claim_def == correct_def:
                _, claim_def = vocab[(start + i + 9) % len(vocab)]
        out.append(_make(
            subject=subject, creator=examiner, qtype=TF, category=category,
            topic=subject.name,
            body=f"{term} is {claim_def}.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0, negative=0.25,
            explanation=f"{term} — {correct_def}.",
            options=[("True", is_true), ("False", not is_true)],
        ))
    return out


def _mk_multi_select_numeric(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    """Which of these numbers are prime? - numeric, works for any technical/aptitude
    subject and is genuinely unambiguous (a clearly defined correct set)."""
    out = []
    for i in range(needed):
        base = 2 + (i * 17) % 90
        numbers = [base, base + 1, base + 2, base + 3]
        correct_mask = [_is_prime(n) for n in numbers]
        if not any(correct_mask):
            correct_mask[0] = True
        out.append(_make(
            subject=subject, creator=examiner, qtype=MSEL, category=category,
            topic=subject.name,
            body=f"Which of the following numbers are prime? {', '.join(str(n) for n in numbers)}",
            difficulty=_DIFFICULTIES[i % 3], marks=3.0, negative=1.0,
            explanation="A number is prime if it has no divisors other than 1 and itself.",
            options=[(str(n), c) for n, c in zip(numbers, correct_mask, strict=True)],
        ))
    return out


def _mk_numerical_arith(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    ops = [("+", lambda a, b: a + b), ("-", lambda a, b: a - b), ("*", lambda a, b: a * b)]
    for i in range(needed):
        a = 3 + (start + i * 7) % 977
        b = 2 + (start + i * 11) % 431
        symbol, fn = ops[i % 3]
        answer = fn(a, b)
        out.append(_make(
            subject=subject, creator=examiner, qtype=NUM, category=category,
            topic=subject.name,
            body=f"What is {a} {symbol} {b}?",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0,
            explanation=f"{a} {symbol} {b} = {answer}.",
            spec={"kind": "numerical", "answer": answer, "tolerance": 0},
        ))
    return out


def _mk_mcq_arith(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        a = 4 + (start + i * 13) % 883
        b = 2 + (start + i * 7) % 337
        correct = a * b
        offsets = [a, b, a + b]
        wrongs = sorted({correct + o for o in offsets if o != 0} - {correct})[:3]
        while len(wrongs) < 3:
            wrongs.append(correct + len(wrongs) + 1)
        choices = [(str(correct), True)] + [(str(w), False) for w in wrongs[:3]]
        random.Random(f"mcq-{subject.code}-{i}").shuffle(choices)
        out.append(_make(
            subject=subject, creator=examiner, qtype=MCQ, category=category,
            topic=subject.name,
            body=f"What is {a} × {b}?",
            difficulty=_DIFFICULTIES[i % 3], marks=2.0, negative=0.5,
            explanation=f"{a} × {b} = {correct}.",
            options=choices,
        ))
    return out


def _mk_true_false_arith(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        a = 2 + (start + i * 5) % 889
        b = 3 + (start + i * 3) % 441
        if i % 2 == 0:
            claim_value = a + b
            is_true = True
        else:
            claim_value = a + b + 1
            is_true = False
        out.append(_make(
            subject=subject, creator=examiner, qtype=TF, category=category,
            topic=subject.name,
            body=f"{a} + {b} = {claim_value}.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0, negative=0.25,
            explanation=f"{a} + {b} = {a + b}, so the claim is {'true' if is_true else 'false'}.",
            options=[("True", is_true), ("False", not is_true)],
        ))
    return out


# ===========================================================================
# Logical Reasoning - number-sequence pattern questions, not vocabulary.
# ===========================================================================


def _sequence(i: int) -> tuple[list[int], int, str]:
    """Returns (shown terms, next term, the rule in words) for a small family of
    arithmetic/geometric/square-number sequences, parametrised by i."""
    kind = i % 4
    start = 2 + (i % 40)
    if kind == 0:
        step = 2 + (i % 7)
        terms = [start + step * k for k in range(4)]
        nxt = start + step * 4
        rule = f"add {step} each time"
    elif kind == 1:
        step = 2 + (i % 5)
        terms = [start + step * 3, start + step * 2, start + step, start]
        nxt = start - step
        rule = f"subtract {step} each time"
    elif kind == 2:
        ratio = 2 + (i % 3)
        base = 1 + (i % 5)
        terms = [base * (ratio**k) for k in range(4)]
        nxt = base * (ratio**4)
        rule = f"multiply by {ratio} each time"
    else:
        base = 1 + (i % 12)
        terms = [(base + k) ** 2 for k in range(4)]
        nxt = (base + 4) ** 2
        rule = "each term is the next whole number, squared"
    return terms, nxt, rule


def _mk_mcq_logical(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        terms, nxt, _rule = _sequence(start + i)
        wrongs = sorted({nxt + d for d in (1, -1, 2) if nxt + d != nxt})[:3]
        while len(wrongs) < 3:
            wrongs.append(nxt + len(wrongs) + 3)
        choices = [(str(nxt), True)] + [(str(w), False) for w in wrongs[:3]]
        random.Random(f"logic-{subject.code}-{i}").shuffle(choices)
        out.append(_make(
            subject=subject, creator=examiner, qtype=MCQ, category=category,
            topic=subject.name,
            body=f"What is the next number in the series: {', '.join(str(t) for t in terms)}, ?",
            difficulty=_DIFFICULTIES[i % 3], marks=2.0, negative=0.5,
            explanation=f"The next term is {nxt}.",
            options=choices,
        ))
    return out


def _mk_true_false_logical(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        terms, nxt, _rule = _sequence(start + i)
        is_true = i % 2 == 0
        claim = nxt if is_true else nxt + 1
        out.append(_make(
            subject=subject, creator=examiner, qtype=TF, category=category,
            topic=subject.name,
            body=f"In the series {', '.join(str(t) for t in terms)}, ..., the next term is {claim}.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0, negative=0.25,
            explanation=f"The next term is {nxt}.",
            options=[("True", is_true), ("False", not is_true)],
        ))
    return out


def _mk_fill_blank_logical(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        terms, nxt, _rule = _sequence(start + i)
        out.append(_make(
            subject=subject, creator=examiner, qtype=FB, category=category,
            topic=subject.name,
            body=f"Series: {', '.join(str(t) for t in terms)}, ___.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0,
            explanation=f"The next term is {nxt}.",
            spec={"kind": "fill_blank", "accepted_answers": [str(nxt)], "case_sensitive": False},
        ))
    return out


def _mk_short_answer_logical(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        terms, nxt, rule = _sequence(start + i)
        out.append(_make(
            subject=subject, creator=examiner, qtype=SA, category=category,
            topic=subject.name,
            body=f"State the rule of the series {', '.join(str(t) for t in terms)}, ... and give the next term.",
            difficulty=_DIFFICULTIES[i % 3], marks=3.0,
            model_answer=f"The rule is: {rule}. The next term is {nxt}.",
            min_words=8, max_words=50,
            rubric={"key_points": ["States the correct rule", "Gives the correct next term"],
                    "scheme": "Half marks for the rule, half for the number."},
        ))
    return out


# ===========================================================================
# Verbal Ability & English
# ===========================================================================


def _mk_mcq_verbal(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        use_antonym = i % 2 == 1
        pool = _ANTONYM_VOCAB if use_antonym else _VERBAL_VOCAB
        word, related = pool[(start + i) % len(pool)]
        distractors = []
        offset = 1
        while len(distractors) < 3:
            _, d = pool[(start + i + offset) % len(pool)]
            if d != related and d not in distractors:
                distractors.append(d)
            offset += 1
        choices = [(related, True)] + [(d, False) for d in distractors]
        random.Random(f"verbal-{i}").shuffle(choices)
        kind = "antonym" if use_antonym else "synonym"
        out.append(_make(
            subject=subject, creator=examiner, qtype=MCQ, category=category,
            topic=subject.name,
            body=f"Choose the {kind} of '{word}'.",
            difficulty=_DIFFICULTIES[i % 3], marks=1.0, negative=0.25,
            explanation=f"The {kind} of '{word}' is '{related}'.",
            options=choices,
        ))
    return out


def _mk_true_false_verbal(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    return _mk_true_false_concept(subject, examiner, category, _VERBAL_VOCAB, start, needed)


def _mk_multi_select_verbal(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        word, synonym = _VERBAL_VOCAB[(start + i) % len(_VERBAL_VOCAB)]
        distractors = []
        offset = 1
        while len(distractors) < 3:
            cand, _ = _VERBAL_VOCAB[(start + i + offset) % len(_VERBAL_VOCAB)]
            if cand != word and cand not in distractors:
                distractors.append(cand)
            offset += 1
        options = [(synonym, True)] + [(d, False) for d in distractors]
        random.Random(f"verbalms-{i}").shuffle(options)
        out.append(_make(
            subject=subject, creator=examiner, qtype=MSEL, category=category,
            topic=subject.name,
            body=f"Which of the following words is a synonym of '{word}'?",
            difficulty=_DIFFICULTIES[i % 3], marks=2.0, negative=0.5,
            explanation=f"'{synonym}' is the synonym of '{word}' among the choices.",
            options=options,
        ))
    return out


# ===========================================================================
# Coding - generic function-writing templates (parametrised widely by index so
# a single subject's 200 coding questions stay largely distinct), an ML/NLP/DL
# flavoured extra set, and a dedicated SQL query-writing set.
# ===========================================================================

_WORDS = ["python", "hello", "world", "algorithm", "keyboard", "language", "compute",
          "network", "database", "internet", "software", "mountain", "elephant",
          "sunlight", "victory", "harmony", "journey", "picture", "diamond", "freedom"]


def _t_sum_to_n(i: int) -> dict[str, Any]:
    n = 3 + i
    total = n * (n + 1) // 2
    return {"body": f"Write a function `sum_to_n(n: int) -> int` that returns the sum of all integers from 1 to n, for n = {n}.",
            "cases": [{"input": str(n), "output": str(total)}], "constraints": "1 ≤ n ≤ 10^6."}


def _t_factorial(i: int) -> dict[str, Any]:
    n = i % 16
    fact = 1
    for k in range(2, n + 1):
        fact *= k
    return {"body": f"Write a function `factorial(n: int) -> int` returning n! (n factorial), for n = {n}.",
            "cases": [{"input": str(n), "output": str(fact)}], "constraints": "0 ≤ n ≤ 20."}


def _t_fibonacci(i: int) -> dict[str, Any]:
    n = i % 30
    fib = [0, 1]
    while len(fib) <= max(n, 1):
        fib.append(fib[-1] + fib[-2])
    return {"body": f"Write a function `nth_fibonacci(n: int) -> int` returning the n-th Fibonacci number (0-indexed), for n = {n}.",
            "cases": [{"input": str(n), "output": str(fib[n])}], "constraints": "0 ≤ n ≤ 40."}


def _t_gcd(i: int) -> dict[str, Any]:
    import math
    a = 12 + i
    b = 18 + ((i * 3) % 97)
    return {"body": f"Write a function `gcd(a: int, b: int) -> int` returning the greatest common divisor, for a = {a}, b = {b}.",
            "cases": [{"input": f"{a}, {b}", "output": str(math.gcd(a, b))}], "constraints": "1 ≤ a, b ≤ 10^9."}


def _t_is_prime(i: int) -> dict[str, Any]:
    n = 90 + i * 7
    return {"body": f"Write a function `is_prime(n: int) -> bool` returning whether n is a prime number, for n = {n}.",
            "cases": [{"input": str(n), "output": "true" if _is_prime(n) else "false"}], "constraints": "1 ≤ n ≤ 10^7."}


def _t_reverse_string(i: int) -> dict[str, Any]:
    word = _WORDS[i % len(_WORDS)] + str(i // len(_WORDS))
    return {"body": "Write a function `reverse_string(s: str) -> str` that returns the reverse of the input string.",
            "cases": [{"input": word, "output": word[::-1]}], "constraints": "1 ≤ len(s) ≤ 1000."}


def _t_is_palindrome(i: int) -> dict[str, Any]:
    base = _WORDS[i % len(_WORDS)]
    s = base if i % 2 == 0 else base + "x"
    return {"body": "Write a function `is_palindrome(s: str) -> bool` returning whether a string reads the same forwards and backwards.",
            "cases": [{"input": s, "output": "true" if s == s[::-1] else "false"}], "constraints": "1 ≤ len(s) ≤ 1000."}


def _t_count_vowels(i: int) -> dict[str, Any]:
    sentence = " ".join(_WORDS[(i + k) % len(_WORDS)] for k in range(3))
    count = sum(1 for c in sentence.lower() if c in "aeiou")
    return {"body": "Write a function `count_vowels(s: str) -> int` that counts the vowels (case-insensitive) in a string.",
            "cases": [{"input": sentence, "output": str(count)}], "constraints": "1 ≤ len(s) ≤ 10^4."}


def _t_max_in_array(i: int) -> dict[str, Any]:
    nums = [(i * 7 + k * 13) % 500 - 100 for k in range(5)]
    return {"body": "Write a function `max_in_array(nums: list[int]) -> int` returning the largest element, without using a built-in max.",
            "cases": [{"input": str(nums), "output": str(max(nums))}], "constraints": "1 ≤ len(nums) ≤ 10^5."}


def _t_remove_duplicates(i: int) -> dict[str, Any]:
    base = [(i + k) % 6 for k in range(6)]
    seen: list[int] = []
    for x in base:
        if x not in seen:
            seen.append(x)
    return {"body": "Write a function `remove_duplicates(nums: list[int]) -> list[int]` returning `nums` with duplicates removed, preserving first-seen order.",
            "cases": [{"input": str(base), "output": str(seen)}], "constraints": "1 ≤ len(nums) ≤ 10^5."}


def _t_two_sum(i: int) -> dict[str, Any]:
    target = 20 + (i % 50)
    a = 2 + (i % 30)
    b = target - a
    nums = [a, 1000 + i, b, 2000 + i]
    return {"body": f"Write a function `two_sum(nums: list[int], target: int) -> list[int]` returning the indices of the two numbers that add up to target, for target = {target}.",
            "cases": [{"input": f"{nums}, {target}", "output": "[0, 2]"}], "constraints": "2 ≤ len(nums) ≤ 10^5. Exactly one valid answer exists."}


def _t_word_frequency(i: int) -> dict[str, Any]:
    sentence = " ".join(_WORDS[(i + k) % 5] for k in range(6))
    freq: dict[str, int] = {}
    for w in sentence.split():
        freq[w] = freq.get(w, 0) + 1
    return {"body": "Write a function `word_frequency(text: str) -> dict[str, int]` returning a count of each lowercase word in the text.",
            "cases": [{"input": sentence, "output": str(freq)}], "constraints": "Words are separated by single spaces."}


def _t_count_divisible(i: int) -> dict[str, Any]:
    k = 2 + (i % 9)
    nums = [(i + j * 3) % 60 + 1 for j in range(6)]
    count = sum(1 for x in nums if x % k == 0)
    return {"body": f"Write a function `count_divisible(nums: list[int], k: int) -> int` counting how many elements are divisible by k, for k = {k}.",
            "cases": [{"input": f"{nums}, {k}", "output": str(count)}], "constraints": "1 ≤ len(nums) ≤ 10^5, k ≥ 1."}


def _t_is_anagram(i: int) -> dict[str, Any]:
    a = _WORDS[i % len(_WORDS)]
    b = "".join(sorted(a)) if i % 2 == 0 else a[::-1] + "z"
    is_ana = sorted(a) == sorted(b)
    return {"body": "Write a function `is_anagram(a: str, b: str) -> bool` returning whether two strings are anagrams of each other.",
            "cases": [{"input": f"{a}, {b}", "output": "true" if is_ana else "false"}], "constraints": "1 ≤ len(a), len(b) ≤ 1000."}


def _t_digit_sum(i: int) -> dict[str, Any]:
    n = 100 + i * 13
    return {"body": f"Write a function `digit_sum(n: int) -> int` returning the sum of the digits of n, for n = {n}.",
            "cases": [{"input": str(n), "output": str(sum(int(c) for c in str(n)))}], "constraints": "0 ≤ n ≤ 10^12."}


def _t_power(i: int) -> dict[str, Any]:
    base = 2 + (i % 9)
    exp = 1 + (i % 12)
    return {"body": f"Write a function `power(base: int, exp: int) -> int` returning base raised to exp, without using the `**` operator, for base = {base}, exp = {exp}.",
            "cases": [{"input": f"{base}, {exp}", "output": str(base**exp)}], "constraints": "0 ≤ exp ≤ 20."}


_CODING_TEMPLATES: list[Callable[[int], dict[str, Any]]] = [
    _t_sum_to_n, _t_factorial, _t_fibonacci, _t_gcd, _t_is_prime, _t_reverse_string,
    _t_is_palindrome, _t_count_vowels, _t_max_in_array, _t_remove_duplicates,
    _t_two_sum, _t_word_frequency, _t_count_divisible, _t_is_anagram, _t_digit_sum, _t_power,
]


def _t_ml_mean(i: int) -> dict[str, Any]:
    nums = [(i + k * 3) % 40 + 1 for k in range(5)]
    mean = round(sum(nums) / len(nums), 2)
    return {"body": "Write a function `compute_mean(nums: list[float]) -> float` returning the average of a list, rounded to 2 decimal places.",
            "cases": [{"input": str(nums), "output": str(mean)}], "constraints": "1 ≤ len(nums) ≤ 10^5."}


def _t_ml_normalize(i: int) -> dict[str, Any]:
    nums = sorted({(i + k * 5) % 50 for k in range(4)})
    if len(nums) < 2:
        nums = [nums[0], nums[0] + 1]
    lo, hi = min(nums), max(nums)
    norm = [round((x - lo) / (hi - lo), 2) for x in nums]
    return {"body": "Write a function `normalize_minmax(nums: list[float]) -> list[float]` scaling values to the 0-1 range using min-max normalisation, rounded to 2 decimals.",
            "cases": [{"input": str(nums), "output": str(norm)}], "constraints": "2 ≤ len(nums) ≤ 10^4, values not all equal."}


def _t_ml_dot(i: int) -> dict[str, Any]:
    a = [(i + k) % 10 for k in range(4)]
    b = [(i + k * 2) % 10 for k in range(4)]
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return {"body": "Write a function `dot_product(a: list[float], b: list[float]) -> float` returning the dot product of two equal-length vectors.",
            "cases": [{"input": f"{a}, {b}", "output": str(dot)}], "constraints": "1 ≤ len(a) = len(b) ≤ 10^4."}


def _t_ml_count_above(i: int) -> dict[str, Any]:
    nums = [(i + k * 4) % 100 for k in range(6)]
    t = 30 + (i % 40)
    count = sum(1 for x in nums if x > t)
    return {"body": f"Write a function `count_above_threshold(nums: list[float], t: float) -> int` counting values greater than t, for t = {t}.",
            "cases": [{"input": f"{nums}, {t}", "output": str(count)}], "constraints": "1 ≤ len(nums) ≤ 10^5."}


def _t_ml_one_hot(i: int) -> dict[str, Any]:
    categories = ["cat", "dog", "bird", "fish"]
    idx = i % len(categories)
    vec = [1 if k == idx else 0 for k in range(len(categories))]
    return {"body": f"Write a function `one_hot_encode(category: str, vocabulary: list[str]) -> list[int]` returning the one-hot vector for a category, for category = '{categories[idx]}', vocabulary = {categories}.",
            "cases": [{"input": f"'{categories[idx]}', {categories}", "output": str(vec)}], "constraints": "category is guaranteed to be in vocabulary."}


_ML_CODING_TEMPLATES: list[Callable[[int], dict[str, Any]]] = [
    _t_ml_mean, _t_ml_normalize, _t_ml_dot, _t_ml_count_above, _t_ml_one_hot,
]


def _mk_coding(subject: Subject, examiner: User, category: QuestionCategory, templates: list[Callable[[int], dict[str, Any]]], start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        template = templates[i % len(templates)]
        item = template(start + i)
        out.append(_make(
            subject=subject, creator=examiner, qtype=CODING, category=category,
            topic=subject.name,
            body=item["body"],
            difficulty=_DIFFICULTIES[i % 3], marks=8.0,
            spec={"kind": "coding", "languages": ["python", "java", "cpp", "javascript"],
                  "default_language": "python", "input_format": "See the sample cases.",
                  "output_format": "See the sample cases.", "constraints": item["constraints"],
                  "sample_cases": item["cases"]},
        ))
    return out


_DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Finance", "Support", "HR", "Operations", "Legal"]


def _t_sql_dept(i: int) -> str:
    dept = _DEPARTMENTS[i % len(_DEPARTMENTS)]
    return f"Write a SQL query to find all employees in the '{dept}' department from the `employees` table."


def _t_sql_top_paid(i: int) -> str:
    n = 3 + (i % 20)
    return f"Write a SQL query to find the top {n} highest-paid employees from the `employees` table."


def _t_sql_group_orders(i: int) -> str:
    return "Write a SQL query to count the number of orders placed by each customer in the `orders` table, grouped by customer_id."


def _t_sql_min_orders(i: int) -> str:
    n = 2 + (i % 15)
    return f"Write a SQL query to find customers who placed more than {n} orders."


def _t_sql_price_above(i: int) -> str:
    p = 100 + i * 5
    return f"Write a SQL query to list products with a price greater than {p} from the `products` table."


def _t_sql_avg_salary(i: int) -> str:
    return "Write a SQL query to find the average salary per department from the `employees` table."


def _t_sql_year_orders(i: int) -> str:
    year = 2015 + (i % 11)
    return f"Write a SQL query to list all orders placed in the year {year}."


def _t_sql_join(i: int) -> str:
    return "Write a SQL query using an INNER JOIN to list the order id and customer name from the `orders` and `customers` tables."


def _t_sql_second_highest(i: int) -> str:
    return "Write a SQL query to find the second-highest salary from the `employees` table."


def _t_sql_join_left(i: int) -> str:
    return "Write a SQL query using a LEFT JOIN to list every customer together with any orders they have placed, including customers with no orders."


_SQL_TEMPLATES: list[Callable[[int], str]] = [
    _t_sql_dept, _t_sql_top_paid, _t_sql_group_orders, _t_sql_min_orders, _t_sql_price_above,
    _t_sql_avg_salary, _t_sql_year_orders, _t_sql_join, _t_sql_second_highest, _t_sql_join_left,
]


def _mk_coding_sql(subject: Subject, examiner: User, category: QuestionCategory, start: int, needed: int) -> list[Question]:
    out = []
    for i in range(needed):
        template = _SQL_TEMPLATES[i % len(_SQL_TEMPLATES)]
        body = template(start + i)
        out.append(_make(
            subject=subject, creator=examiner, qtype=CODING, category=category,
            topic=subject.name,
            body=body,
            difficulty=_DIFFICULTIES[i % 3], marks=8.0,
            spec={"kind": "coding", "languages": ["sql"], "default_language": "sql",
                  "input_format": "A standard employees/orders/customers/products schema, as described in the problem.",
                  "output_format": "A single SQL query producing the requested result set.",
                  "constraints": "Assume standard column names (id, name, department, salary, customer_id, price, order_date).",
                  "sample_cases": [{"input": "See the schema description in the problem.", "output": "A syntactically valid SQL query answering it."}]},
        ))
    return out


# ===========================================================================
# Subject profiles: which types are appropriate, which category they carry,
# and which content domain (vocab / generator family) to draw from.
# ===========================================================================


class Profile:
    __slots__ = ("category", "domain")

    def __init__(self, category: QuestionCategory, domain: str) -> None:
        self.category = category
        self.domain = domain


#: Keyed by Subject.code, which is stable even if an examiner renames the subject.
SUBJECT_PROFILES: dict[str, Profile] = {
    "CS101": Profile(QuestionCategory.TECHNICAL, "cs_fund"),
    "CS102": Profile(QuestionCategory.TECHNICAL, "dsa"),
    "CS201": Profile(QuestionCategory.TECHNICAL, "db"),
    "CS301": Profile(QuestionCategory.TECHNICAL, "web"),
    "CS202": Profile(QuestionCategory.TECHNICAL, "os"),
    "CS203": Profile(QuestionCategory.TECHNICAL, "net"),
    "MATH101": Profile(QuestionCategory.APTITUDE, "math"),
    "ML101": Profile(QuestionCategory.TECHNICAL, "ml"),
    "NLP101": Profile(QuestionCategory.TECHNICAL, "nlp"),
    "AI101": Profile(QuestionCategory.TECHNICAL, "ai"),
    "DL101": Profile(QuestionCategory.TECHNICAL, "dl"),
    "APT101": Profile(QuestionCategory.APTITUDE, "aptitude"),
    "LOG101": Profile(QuestionCategory.LOGICAL_REASONING, "logical"),
    "VRB101": Profile(QuestionCategory.VERBAL_ABILITY, "verbal"),
    "TECH101": Profile(QuestionCategory.TECHNICAL, "core"),
    "CODE101": Profile(QuestionCategory.CODING, "dsa"),
    "PY101": Profile(QuestionCategory.TECHNICAL, "python"),
    "SQL101": Profile(QuestionCategory.TECHNICAL, "sql"),
}

#: A subject whose exact code isn't in the map above (an examiner-created subject, or a
#: legacy import-generated one like the standalone "Aptitude"/"Java"/"DBMS" leftovers)
#: falls back to matching by name, then to a conservative generic profile.
_NAME_FALLBACK: dict[str, str] = {
    "aptitude": "aptitude",
    "java": "java",
    "dbms": "db",
    "python": "python",
    "sql": "sql",
    "computer networks": "net",
    "data structures": "dsa",
    "reading comprehension": "verbal",
    "vocabulary": "verbal",
    "grammar": "verbal",
    "sentence correction": "verbal",
    "synonyms": "verbal",
    "antonyms": "verbal",
    "data interpretation": "aptitude",
}

_DOMAIN_VOCAB: dict[str, list[tuple[str, str]]] = {
    "cs_fund": _cs_fund_vocab(), "dsa": _DSA_VOCAB, "db": _DB_VOCAB, "web": _WEB_VOCAB,
    "os": _OS_VOCAB, "net": _NET_VOCAB, "ml": _ML_VOCAB, "nlp": _NLP_VOCAB, "ai": _AI_VOCAB,
    "dl": _DL_VOCAB, "core": _CORE_VOCAB, "python": _PYTHON_VOCAB, "java": _JAVA_VOCAB,
    "sql": _SQL_VOCAB, "math": _MATH_VOCAB, "aptitude": _MATH_VOCAB,
}

#: Types allowed per domain. A domain not listed here (shouldn't happen given the
#: fallback below) gets the generic set.
_GENERIC_TYPES = {MCQ, MSEL, TF, FB, SA, LA}
_DOMAIN_TYPES: dict[str, set[QuestionType]] = {
    "cs_fund": _GENERIC_TYPES | {NUM, CODING, IMG},
    "dsa": _GENERIC_TYPES | {NUM, CODING},
    "db": _GENERIC_TYPES | {NUM},
    "web": _GENERIC_TYPES | {CODING},
    "os": _GENERIC_TYPES | {NUM},
    "net": _GENERIC_TYPES | {NUM},
    "ml": _GENERIC_TYPES | {NUM, CODING},
    "nlp": _GENERIC_TYPES | {NUM, CODING},
    "ai": _GENERIC_TYPES | {CODING},
    "dl": _GENERIC_TYPES | {NUM, CODING},
    "core": _GENERIC_TYPES | {CODING},
    "python": _GENERIC_TYPES | {NUM, CODING},
    "java": _GENERIC_TYPES | {CODING},
    "sql": _GENERIC_TYPES | {CODING},
    "math": _GENERIC_TYPES | {NUM},
    "aptitude": _GENERIC_TYPES | {NUM},
    "logical": {MCQ, MSEL, TF, FB, SA},
    "verbal": {MCQ, MSEL, TF, FB, SA, LA, PASSAGE},
}


def _profile_for(subject: Subject) -> Profile:
    hit = SUBJECT_PROFILES.get(subject.code)
    if hit is not None:
        return hit
    domain = _NAME_FALLBACK.get(subject.name.strip().lower())
    if domain is not None:
        category = {
            "aptitude": QuestionCategory.APTITUDE, "sql": QuestionCategory.TECHNICAL,
            "java": QuestionCategory.TECHNICAL, "db": QuestionCategory.TECHNICAL,
            "python": QuestionCategory.TECHNICAL, "net": QuestionCategory.TECHNICAL,
            "dsa": QuestionCategory.TECHNICAL, "verbal": QuestionCategory.VERBAL_ABILITY,
        }.get(domain, QuestionCategory.ACADEMIC)
        return Profile(category, domain)
    # A subject an examiner just created: safe generic academic set, no coding/numerical
    # until someone deliberately decides this subject is technical or quantitative.
    return Profile(QuestionCategory.ACADEMIC, "generic")


def _category_for(profile: Profile, qtype: QuestionType) -> QuestionCategory:
    # Coding is its own corporate-round bucket regardless of which subject it's filed
    # under - a corporate "coding round" section rule pulls on category=coding.
    if qtype is CODING:
        return QuestionCategory.CODING
    return profile.category


def _generate(subject: Subject, examiner: User, qtype: QuestionType, profile: Profile, start: int, needed: int) -> list[Question]:
    category = _category_for(profile, qtype)
    domain = profile.domain

    if domain == "logical":
        return {
            MCQ: _mk_mcq_logical, TF: _mk_true_false_logical, FB: _mk_fill_blank_logical,
            SA: _mk_short_answer_logical, MSEL: lambda s, e, c, st, n: _mk_multi_select_numeric(s, e, c, st, n),
        }[qtype](subject, examiner, category, start, needed)

    if domain == "verbal":
        vocab = _VERBAL_VOCAB
        return {
            MCQ: _mk_mcq_verbal, TF: _mk_true_false_verbal, MSEL: _mk_multi_select_verbal,
            FB: lambda s, e, c, st, n: _mk_fill_blank(s, e, c, vocab, st, n),
            SA: lambda s, e, c, st, n: _mk_short_answer(s, e, c, vocab, st, n),
            LA: lambda s, e, c, st, n: _mk_long_answer(s, e, c, vocab, st, n),
            PASSAGE: lambda s, e, c, st, n: _mk_passage(s, e, c, vocab, st, n),
        }[qtype](subject, examiner, category, start, needed)

    if domain in ("math", "aptitude"):
        vocab = _DOMAIN_VOCAB[domain]
        return {
            MCQ: _mk_mcq_arith, TF: _mk_true_false_arith, NUM: _mk_numerical_arith,
            MSEL: _mk_multi_select_numeric,
            FB: lambda s, e, c, st, n: _mk_fill_blank(s, e, c, vocab, st, n),
            SA: lambda s, e, c, st, n: _mk_short_answer(s, e, c, vocab, st, n),
            LA: lambda s, e, c, st, n: _mk_long_answer(s, e, c, vocab, st, n),
        }[qtype](subject, examiner, category, start, needed)

    if domain == "sql":
        vocab = _SQL_VOCAB
        return {
            MCQ: lambda s, e, c, st, n: _mk_mcq_concept(s, e, c, vocab, st, n),
            TF: lambda s, e, c, st, n: _mk_true_false_concept(s, e, c, vocab, st, n),
            MSEL: _mk_multi_select_numeric,
            FB: lambda s, e, c, st, n: _mk_fill_blank(s, e, c, vocab, st, n),
            SA: lambda s, e, c, st, n: _mk_short_answer(s, e, c, vocab, st, n),
            LA: lambda s, e, c, st, n: _mk_long_answer(s, e, c, vocab, st, n),
            CODING: lambda s, e, c, st, n: _mk_coding_sql(s, e, c, st, n),
        }[qtype](subject, examiner, category, start, needed)

    # Every other technical domain (cs_fund/dsa/db/web/os/net/ml/nlp/ai/dl/core/python/
    # java) and the plain "generic" fallback share the same shape: vocab-driven concept
    # questions, arithmetic numerics, parametrised coding.
    vocab = _DOMAIN_VOCAB.get(domain) or _cs_fund_vocab()
    coding_templates = _ML_CODING_TEMPLATES + _CODING_TEMPLATES if domain in ("ml", "nlp", "dl", "ai") else _CODING_TEMPLATES
    return {
        MCQ: lambda s, e, c, st, n: _mk_mcq_concept(s, e, c, vocab, st, n),
        TF: lambda s, e, c, st, n: _mk_true_false_concept(s, e, c, vocab, st, n),
        MSEL: _mk_multi_select_numeric,
        FB: lambda s, e, c, st, n: _mk_fill_blank(s, e, c, vocab, st, n),
        SA: lambda s, e, c, st, n: _mk_short_answer(s, e, c, vocab, st, n),
        LA: lambda s, e, c, st, n: _mk_long_answer(s, e, c, vocab, st, n),
        IMG: lambda s, e, c, st, n: _mk_image_upload(s, e, c, vocab, st, n),
        NUM: _mk_numerical_arith,
        CODING: lambda s, e, c, st, n: _mk_coding(s, e, c, coding_templates, st, n),
    }[qtype](subject, examiner, category, start, needed)


def top_up(db: Session, examiner: User, *, floor: int = FLOOR_PER_TYPE, subjects: dict[str, Subject] | None = None) -> int:
    """Bring every (subject, appropriate question type) combination up to ``floor``.

    ``subjects`` is accepted for backward compatibility with older call sites but is
    unused - every subject in the database is topped up, not just the ones a caller
    happens to have a handle on, so a subject an examiner created themselves still gets
    real depth.
    """
    all_subjects = list(db.scalars(select(Subject).order_by(Subject.code)))
    added = 0

    for subject in all_subjects:
        profile = _profile_for(subject)
        allowed = _DOMAIN_TYPES.get(profile.domain, _GENERIC_TYPES)

        for qtype in allowed:
            existing = (
                db.scalar(
                    select(func.count(Question.id)).where(
                        Question.subject_id == subject.id, Question.question_type == qtype
                    )
                )
                or 0
            )
            shortfall = floor - existing
            if shortfall <= 0:
                continue

            new_questions = _generate(subject, examiner, qtype, profile, existing, shortfall)
            db.add_all(new_questions)
            db.flush()
            added += len(new_questions)
            logger.info(
                "%s / %s: added %d (%d -> %d)",
                subject.code, qtype.value, len(new_questions), existing, existing + len(new_questions),
            )

    return added
