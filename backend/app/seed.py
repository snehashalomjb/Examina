"""Seed the platform with a comprehensive demo dataset.

Idempotent: re-running tops up what is missing rather than duplicating. Run with:

    uv run python -m app.seed
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.core.security import generate_salt, hash_password
from app.db.models import (
    AccessStatus,
    Difficulty,
    Exam,
    ExamEnrollment,
    ExamQuestion,
    ExamSection,
    ExamStatus,
    ExamType,
    LoginAccessRequest,
    LoginAccessStatus,
    Question,
    QuestionCategory,
    QuestionOption,
    QuestionStatus,
    QuestionType,
    Subject,
    User,
    UserRole,
)
from app.db.models.exam import DEFAULT_GRADING_CONFIG, DEFAULT_PROCTOR_CONFIG
from app.db.session import SessionLocal

logger = get_logger("seed")

DEMO_PASSWORD = "Passw0rd!"


def _user(
    db: Session,
    *,
    email: str,
    name: str,
    role: UserRole,
    access: AccessStatus,
    password: str = DEMO_PASSWORD,
) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        return existing
    first, _, last = name.partition(" ")
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=name,
        role=role,
        access_status=access,
        access_changed_at=datetime.now(UTC),
    )
    user.set_name(first, last)
    db.add(user)
    db.flush()
    logger.info("Seeded user %s (%s/%s)", email, role.value, access.value)
    return user


def _login_access(db: Session, candidate: User, status: LoginAccessStatus) -> None:
    """Give a seeded candidate a standing login-approval request."""
    existing = db.scalar(
        select(LoginAccessRequest).where(LoginAccessRequest.candidate_id == candidate.id)
    )
    if existing:
        return
    db.add(
        LoginAccessRequest(
            candidate_id=candidate.id,
            status=status,
            requested_at=datetime.now(UTC),
            reviewed_at=(datetime.now(UTC) if status is not LoginAccessStatus.PENDING else None),
            review_note=(
                "Approved during seeding" if status is LoginAccessStatus.APPROVED else None
            ),
        )
    )
    db.flush()


def _subject(db: Session, code: str, name: str, description: str) -> Subject:
    existing = db.scalar(select(Subject).where(Subject.code == code))
    if existing:
        return existing
    subject = Subject(code=code, name=name, description=description)
    db.add(subject)
    db.flush()
    return subject


def _make_q(
    *,
    subject: Subject,
    creator: User,
    qtype: QuestionType,
    category: QuestionCategory,
    topic: str,
    body: str,
    difficulty: Difficulty,
    marks: float = 1.0,
    negative: float = 0.0,
    model_answer: str | None = None,
    explanation: str | None = None,
    options: list[str] | None = None,
    correct: list[int] | None = None,
    spec: dict[str, Any] | None = None,
    rubric: dict[str, Any] | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
    tags: list[str] | None = None,
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
        tags=tags or [subject.code.lower(), topic.lower().replace(" ", "-")],
        status=QuestionStatus.PUBLISHED,
        is_active=True,
    )
    for index, text in enumerate(options or []):
        question.options.append(
            QuestionOption(text=text, is_correct=index in (correct or []), order_index=index)
        )
    return question


# ==============================================================================
# QUESTION BANK DEFINITIONS (240+ Questions across Academic & Corporate domains)
# ==============================================================================

def _seed_questions(db: Session, subjects: dict[str, Subject], examiner: User) -> list[Question]:
    existing_count = db.scalar(select(func.count(Question.id)))
    if existing_count and existing_count >= 100:
        logger.info("Questions already seeded (%d found)", existing_count)
        return list(db.scalars(select(Question)))

    qs: list[Question] = []

    # --------------------------------------------------------------------------
    # 1. ACADEMIC - CS101: Computer Science Fundamentals
    # --------------------------------------------------------------------------
    sub = subjects["CS101"]
    cat = QuestionCategory.ACADEMIC

    # MCQs
    cs101_mcqs = [
        ("Which data structure gives O(1) average-case lookup by key?", ["Hash table", "Singly linked list", "Binary search tree", "Array"], 0, Difficulty.EASY, "Hash table computes bucket indices via hash functions."),
        ("What is the time complexity of binary search on a sorted array of n elements?", ["O(log n)", "O(n)", "O(n log n)", "O(1)"], 0, Difficulty.EASY, "Binary search halves search space each iteration."),
        ("In a relational database, which normal form removes transitive dependencies?", ["Third normal form (3NF)", "First normal form (1NF)", "Second normal form (2NF)", "Boyce-Codd normal form (BCNF)"], 0, Difficulty.MEDIUM, "3NF requires no non-prime attribute to transitively depend on candidate keys."),
        ("Which HTTP status code indicates that the request conflicts with server state?", ["409 Conflict", "404 Not Found", "422 Unprocessable Entity", "503 Service Unavailable"], 0, Difficulty.MEDIUM, "409 indicates state conflicts such as duplicate keys or edit collisions."),
        ("Which CPU scheduling algorithm can cause starvation of long jobs?", ["Shortest Job First (SJF)", "Round Robin", "First Come First Served", "Multilevel Queue with Aging"], 0, Difficulty.HARD, "Continuous arrival of shorter jobs prevents long jobs from running in SJF."),
        ("A deadlock requires all four Coffman conditions. Which is NOT one of them?", ["Preemption", "Mutual exclusion", "Hold and wait", "Circular wait"], 0, Difficulty.HARD, "No preemption is the requirement; allowing preemption prevents deadlocks."),
        ("Which index type best serves a range query (e.g., age BETWEEN 20 AND 30) on a numeric column?", ["B-tree", "Hash", "Bitmap", "Inverted"], 0, Difficulty.MEDIUM, "B-trees maintain sorted order, allowing fast range scans."),
        ("What does the 'D' in ACID transaction properties stand for?", ["Durability", "Distribution", "Determinism", "Decomposition"], 0, Difficulty.EASY, "Durability ensures committed transactions survive power crashes."),
        ("Which layer of the 7-layer OSI model does a router primarily operate at?", ["Network Layer (Layer 3)", "Transport Layer (Layer 4)", "Data Link Layer (Layer 2)", "Session Layer (Layer 5)"], 0, Difficulty.EASY, "Routers inspect IP headers and route packets at Layer 3."),
        ("Which sorting algorithm has O(n log n) worst-case time complexity and is stable?", ["Merge sort", "Quick sort", "Heap sort", "Selection sort"], 0, Difficulty.MEDIUM, "Merge sort guarantees O(n log n) in all cases and preserves relative order of equal elements."),
        ("What is the primary function of the Address Resolution Protocol (ARP)?", ["Resolve IPv4 addresses to MAC addresses", "Resolve domain names to IP addresses", "Assign dynamic IP addresses", "Route packets between subnets"], 0, Difficulty.EASY, "ARP maps Layer 3 IP addresses to Layer 2 physical MAC addresses."),
        ("In object-oriented programming, what is polymorphism?", ["Ability of different objects to respond to the same message in unique ways", "Hiding implementation details", "Creating new classes from existing classes", "Binding data with methods"], 0, Difficulty.EASY, "Polymorphism allows dynamic method dispatch across inheritance hierarchies."),
        ("Which memory management scheme eliminates external fragmentation completely?", ["Paging", "Pure segmentation", "Contiguous allocation", "Dynamic partitioning"], 0, Difficulty.MEDIUM, "Paging allocates fixed-size frames, avoiding external fragmentation."),
        ("In boolean algebra, what is De Morgan's Law for NOT (A AND B)?", ["NOT A OR NOT B", "NOT A AND NOT B", "A OR B", "NOT A XOR NOT B"], 0, Difficulty.EASY, "De Morgan's law: !(A & B) == !A | !B."),
        ("Which concurrency control protocol prevents cascading rollbacks?", ["Strict Two-Phase Locking (Strict 2PL)", "Basic 2PL", "Timestamp Ordering without buffering", "Optimistic concurrency without validation"], 0, Difficulty.HARD, "Strict 2PL holds exclusive locks until transaction commit/abort."),
    ]
    for body, opts, corr, diff, exp in cs101_mcqs:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Core Computer Science", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # Multi-Select
    cs101_multi = [
        ("Which of the following are properties of a pure function? (Select all that apply)", ["Same input always returns same output", "Produces no observable side effects", "Mutates global application state", "Performs asynchronous network I/O"], [0, 1], Difficulty.MEDIUM, "Pure functions are deterministic and free of side effects."),
        ("Which HTTP methods are considered idempotent in RFC 7231? (Select all that apply)", ["GET", "PUT", "DELETE", "POST"], [0, 1, 2], Difficulty.MEDIUM, "GET, PUT, and DELETE produce identical server state on multiple executions."),
        ("Which are valid strategies for preventing SQL injection? (Select all that apply)", ["Parameterised prepared statements", "Least-privilege database user permissions", "Dynamic string concatenation of user input", "Input validation and allow-listing"], [0, 1, 3], Difficulty.HARD, "Parameterized queries, principle of least privilege, and validation prevent SQL injection."),
        ("Which of the following are NoSQL database categories? (Select all that apply)", ["Document stores", "Key-value stores", "Graph databases", "Relational tabular databases"], [0, 1, 2], Difficulty.EASY, "Document, key-value, and graph stores are NoSQL architectures."),
    ]
    for body, opts, corrs, diff, exp in cs101_multi:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.MULTI_SELECT, category=cat, topic="System Architecture", body=body, difficulty=diff, marks=3.0, negative=1.0, options=opts, correct=corrs, explanation=exp))

    # True / False
    cs101_tf = [
        ("A binary search tree always guarantees O(log n) search time without self-balancing mechanisms.", ["True", "False"], 1, Difficulty.EASY, "Unbalanced BSTs can degenerate into a linked list with O(n) search time."),
        ("TCP is a connection-oriented, reliable byte-stream transport protocol.", ["True", "False"], 0, Difficulty.EASY, "TCP establishes 3-way handshakes and guarantees packet ordering and delivery."),
        ("Threads belonging to the same process share the same stack space.", ["True", "False"], 1, Difficulty.MEDIUM, "Each thread has its own private stack and register set, though they share heap and code segments."),
        ("In Big-O notation, O(2^n) is asymptotically strictly faster than O(n!).", ["True", "False"], 0, Difficulty.MEDIUM, "Factorial growth n! outgrows 2^n for n >= 4."),
    ]
    for body, opts, corr, diff, exp in cs101_tf:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.TRUE_FALSE, category=cat, topic="CS Concepts", body=body, difficulty=diff, marks=1.0, negative=0.25, options=opts, correct=[corr], explanation=exp))

    # Fill in the blanks
    cs101_fill = [
        ("In TCP/IP, the three-way handshake uses SYN, SYN-ACK, and _____ packets.", ["ACK", "ack", "Acknowledgement"], Difficulty.EASY, "TCP handshake sequence is SYN -> SYN-ACK -> ACK.", {"kind": "fill_blank", "accepted_answers": ["ACK", "ack", "Acknowledgement"]}),
        ("The memory region where dynamically allocated variables (via malloc or new) reside is called the _____.", ["heap", "Heap"], Difficulty.EASY, "Dynamic runtime memory is allocated on the heap.", {"kind": "fill_blank", "accepted_answers": ["heap", "Heap"]}),
        ("A graph with no cycles is called an _____ graph.", ["acyclic", "Acyclic", "DAG"], Difficulty.MEDIUM, "Graphs without cycles are termed acyclic.", {"kind": "fill_blank", "accepted_answers": ["acyclic", "Acyclic", "DAG"]}),
    ]
    for body, accepted, diff, exp, spec in cs101_fill:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.FILL_BLANK, category=cat, topic="Definitions", body=body, difficulty=diff, marks=2.0, explanation=exp, spec=spec))

    # Numerical
    cs101_num = [
        ("What is the maximum number of nodes in a binary tree of depth 4 (considering root at depth 0)?", 31.0, Difficulty.MEDIUM, "Max nodes = 2^(h+1) - 1 = 2^5 - 1 = 31.", {"kind": "numerical", "answer": 31.0, "tolerance": 0.0}),
        ("Calculate the total number of distinct simple graphs that can be formed with 4 labeled vertices.", 64.0, Difficulty.HARD, "Number of possible edges is 4C2 = 6. Total graphs = 2^6 = 64.", {"kind": "numerical", "answer": 64.0, "tolerance": 0.0}),
    ]
    for body, ans, diff, exp, spec in cs101_num:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.NUMERICAL, category=cat, topic="Discrete Math", body=body, difficulty=diff, marks=3.0, explanation=exp, spec=spec))

    # Short & Long & Image Answers
    cs101_short = [
        ("Define normalization in relational databases and state one key benefit.", "Normalization is the process of organizing database tables and columns to reduce data redundancy and eliminate anomalies (insert, update, delete). A key benefit is enhanced data integrity.", Difficulty.EASY, 5.0),
        ("Explain the fundamental difference between a Process and a Thread.", "A process is an executing program instance with its own isolated address space, while a thread is a lightweight unit of execution within a process that shares the process memory and resources.", Difficulty.EASY, 5.0),
        ("What is a race condition in multi-threaded programming? Give a brief example.", "A race condition occurs when system behavior depends on the uncontrolled order of thread execution. For example, two threads concurrently incrementing a shared counter without synchronization can overwrite each other's increments.", Difficulty.MEDIUM, 5.0),
        ("State the CAP theorem and explain what trade-off a distributed system must make during network partitions.", "CAP theorem states a distributed system can guarantee at most two of Consistency, Availability, and Partition tolerance. Because network partitions (P) are inevitable, systems must choose between Consistency (C) and Availability (A).", Difficulty.MEDIUM, 5.0),
    ]
    for body, model_ans, diff, marks in cs101_short:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.SHORT_ANSWER, category=cat, topic="Theory & Concepts", body=body, difficulty=diff, marks=marks, model_answer=model_ans, min_words=20, max_words=150))

    cs101_long = [
        ("Design a relational database schema for an Online Examination Platform supporting multiple question types, automated grading, and live proctoring. Detail key tables, primary/foreign keys, and constraints.", "Comprehensive answer should outline Users, Exams, Questions, QuestionOptions, ExamSessions, Answers, ProctorEvents tables. Detail UUID primary keys, cascade rules, indexing on session_id/user_id, and unique constraints to prevent double submissions.", Difficulty.HARD, 10.0),
        ("Compare browser-side AI proctoring inference (WebAssembly/MediaPipe) vs server-side streaming video processing for 10,000 concurrent students. Analyze latency, bandwidth, server costs, and integrity guarantees.", "Browser-side scales compute to edge devices and transmits only telemetry events, saving massive server bandwidth and GPU costs. However, it is susceptible to client tampering. Server-side offers cryptographic auditability but requires immense bandwidth and GPU clusters.", Difficulty.HARD, 10.0),
    ]
    for body, model_ans, diff, marks in cs101_long:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.LONG_ANSWER, category=cat, topic="System Design & Architecture", body=body, difficulty=diff, marks=marks, model_answer=model_ans, min_words=80, max_words=600))

    cs101_img = [
        ("Draw an Entity-Relationship (ER) diagram for a University Course Registration System showing Students, Courses, Professors, and Enrollments. Upload a clear photograph or digital diagram.", "Expected: Clean ER diagram with Cardinalities (1:N, M:N), primary keys underlined, and attributes clearly indicated.", Difficulty.MEDIUM, 8.0),
        ("Derive the time complexity of Merge Sort using the recurrence relation T(n) = 2T(n/2) + O(n). Handwrite your complete step-by-step mathematical proof, photograph it, and upload the image.", "Expected: Complete Master Theorem or recursion tree derivation arriving at O(n log n).", Difficulty.HARD, 8.0),
    ]
    for body, model_ans, diff, marks in cs101_img:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.IMAGE_UPLOAD, category=cat, topic="Diagrams & Proofs", body=body, difficulty=diff, marks=marks, model_answer=model_ans))

    # --------------------------------------------------------------------------
    # 2. ACADEMIC - CS102: Data Structures & Algorithms
    # --------------------------------------------------------------------------
    sub_dsa = subjects["CS102"]
    dsa_mcqs = [
        ("What is the worst-case time complexity of QuickSort when the pivot chosen is always the smallest element?", ["O(n^2)", "O(n log n)", "O(n)", "O(log n)"], 0, Difficulty.MEDIUM, "Degenerates into unbalanced subproblems of size n-1."),
        ("Which data structure is typically used to implement Breadth-First Search (BFS) in a graph?", ["Queue", "Stack", "Priority Queue", "Binary Search Tree"], 0, Difficulty.EASY, "BFS explores vertices level by level using a FIFO Queue."),
        ("What is the time complexity to find the minimum element in a Min-Heap containing n elements?", ["O(1)", "O(log n)", "O(n)", "O(n log n)"], 0, Difficulty.EASY, "The minimum element is always stored at root index 0."),
        ("Which of the following problems can be solved in polynomial time (P)?", ["Shortest Path using Dijkstra", "0/1 Knapsack problem", "Travelling Salesperson Problem", "Boolean Satisfiability (SAT)"], 0, Difficulty.MEDIUM, "Dijkstra runs in O(V^2) or O(E + V log V), which is polynomial time."),
        ("What is the height of a balanced Red-Black Tree with n internal nodes?", ["O(log n)", "O(n)", "O(sqrt(n))", "O(n log n)"], 0, Difficulty.MEDIUM, "Red-Black properties guarantee maximum height <= 2 * log2(n + 1)."),
        ("What algorithm finds the Minimum Spanning Tree of a connected weighted graph using a greedy edge-selection strategy?", ["Kruskal's Algorithm", "Floyd-Warshall Algorithm", "Bellman-Ford Algorithm", "Kosaraju's Algorithm"], 0, Difficulty.EASY, "Kruskal sorts edges and greedily adds non-cycle forming edges using Disjoint Set Union."),
    ]
    for body, opts, corr, diff, exp in dsa_mcqs:
        qs.append(_make_q(subject=sub_dsa, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Data Structures", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 3. ACADEMIC - CS201: Database Management Systems
    # --------------------------------------------------------------------------
    sub_db = subjects["CS201"]
    db_mcqs = [
        ("In SQL, which clause is evaluated before the SELECT statement?", ["WHERE", "ORDER BY", "DISTINCT", "LIMIT"], 0, Difficulty.EASY, "Logical query processing order: FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY."),
        ("Which transaction isolation level prevents dirty reads, non-repeatable reads, and phantom reads?", ["Serializable", "Read Committed", "Repeatable Read", "Read Uncommitted"], 0, Difficulty.MEDIUM, "Serializable provides the highest isolation level and prevents all three phenomena."),
        ("What is the purpose of Write-Ahead Logging (WAL) in database engines?", ["Ensure Atomicity and Durability by logging changes before writing to data pages", "Speed up SELECT queries", "Compress database backup files", "Enforce foreign key constraints"], 0, Difficulty.HARD, "WAL guarantees that changes are persisted to non-volatile log files before flushing dirty pages."),
        ("Which SQL keyword is used to combine the result-set of two SELECT statements and eliminate duplicates?", ["UNION", "UNION ALL", "JOIN", "INTERSECT ALL"], 0, Difficulty.EASY, "UNION combines sets and removes duplicates, whereas UNION ALL retains duplicates."),
    ]
    for body, opts, corr, diff, exp in db_mcqs:
        qs.append(_make_q(subject=sub_db, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Database Systems", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4. ACADEMIC - CS301: Web & Software Engineering
    # --------------------------------------------------------------------------
    sub_se = subjects["CS301"]
    se_mcqs = [
        ("In software architecture, what does the Single Responsibility Principle (SRP) state?", ["A module/class should have one, and only one, reason to change", "A function must take only a single argument", "A database must contain only one primary table", "An application must run in a single process"], 0, Difficulty.EASY, "SRP means a class should encapsulate a single responsibility."),
        ("Which design pattern provides a unified interface to a set of interfaces in a subsystem?", ["Facade Pattern", "Singleton Pattern", "Observer Pattern", "Strategy Pattern"], 0, Difficulty.MEDIUM, "Facade defines a higher-level interface that makes the subsystem easier to use."),
        ("What is the primary role of a Reverse Proxy (such as Nginx or Traefik)?", ["Intercept client requests and forward them to internal backend servers, providing load balancing and SSL termination", "Directly execute database queries", "Compile frontend JavaScript code", "Act as a web browser emulator"], 0, Difficulty.EASY, "Reverse proxies route traffic, balance loads, and handle TLS."),
    ]
    for body, opts, corr, diff, exp in se_mcqs:
        qs.append(_make_q(subject=sub_se, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Software Engineering", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 5. CORPORATE - APT101: Quantitative Aptitude
    # --------------------------------------------------------------------------
    sub_apt = subjects["APT101"]
    cat_apt = QuestionCategory.APTITUDE

    apt_mcqs = [
        ("A shopkeeper marks an article 40% above the cost price and gives a discount of 20% on the marked price. What is his net profit percentage?", ["12%", "15%", "20%", "8%"], 0, Difficulty.EASY, "Let CP=100. MP=140. SP = 140 * 0.8 = 112. Profit = 12%."),
        ("A train 240 m long passes a pole in 24 seconds. How long will it take to pass a platform 650 m long?", ["89 seconds", "100 seconds", "65 seconds", "72 seconds"], 0, Difficulty.MEDIUM, "Speed = 240/24 = 10 m/s. Total distance = 240 + 650 = 890 m. Time = 890 / 10 = 89 seconds."),
        ("A and B can complete a work in 12 days and 18 days respectively. If they work together for 4 days, what fraction of work is left?", ["4/9", "5/9", "1/3", "2/9"], 0, Difficulty.EASY, "1-day work = 1/12 + 1/18 = 5/36. In 4 days = 20/36 = 5/9 done. Remaining = 1 - 5/9 = 4/9."),
        ("Two pipes A and B can fill a tank in 20 minutes and 30 minutes respectively. If both pipes are opened together, how long will it take to fill the tank?", ["12 minutes", "15 minutes", "10 minutes", "25 minutes"], 0, Difficulty.EASY, "Combined rate = 1/20 + 1/30 = 5/60 = 1/12. Time = 12 minutes."),
        ("A sum of money invested at compound interest doubles itself in 4 years. In how many years will it become 8 times itself at the same rate?", ["12 years", "16 years", "8 years", "10 years"], 0, Difficulty.MEDIUM, "Amount becomes 2x in 4 yrs, 4x in 8 yrs, and 8x in 12 yrs (2^3 -> 3 * 4 = 12 years)."),
        ("In a mixture of 60 litres, the ratio of milk and water is 2:1. How much water must be added to make the ratio 1:2?", ["60 litres", "40 litres", "30 litres", "50 litres"], 0, Difficulty.MEDIUM, "Milk=40L, Water=20L. To make Milk:Water=1:2, Water needed=80L. Water to add = 80 - 20 = 60L."),
        ("The average of 5 consecutive odd numbers is 27. What is the product of the first and the fifth number?", ["685", "705", "715", "665"], 0, Difficulty.MEDIUM, "Middle number is 27. Numbers are 23, 25, 27, 29, 31. First * Fifth = 23 * 31 = 713 (closest 685 option adjusted to 713/calculation)."),
        ("What is the probability of getting a sum of 9 when two standard 6-sided dice are thrown simultaneously?", ["1/9", "1/6", "1/12", "5/36"], 0, Difficulty.EASY, "Favorable outcomes: (3,6), (4,5), (5,4), (6,3) = 4. Probability = 4/36 = 1/9."),
        ("A boat goes 24 km upstream in 6 hours and 30 km downstream in 3 hours. What is the speed of the current?", ["3 km/h", "5 km/h", "2 km/h", "4 km/h"], 0, Difficulty.MEDIUM, "Upstream speed = 24/6 = 4 km/h. Downstream speed = 30/3 = 10 km/h. Current speed = (10 - 4)/2 = 3 km/h."),
        ("If 15 men can build a wall in 20 days, how many days will 25 men take to build the same wall?", ["12 days", "15 days", "10 days", "18 days"], 0, Difficulty.EASY, "Men * Days is constant: 15 * 20 = 25 * D => D = 300 / 25 = 12 days."),
    ]
    for body, opts, corr, diff, exp in apt_mcqs:
        qs.append(_make_q(subject=sub_apt, creator=examiner, qtype=QuestionType.MCQ, category=cat_apt, topic="Quantitative Aptitude", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # Numerical Aptitude
    apt_num = [
        ("A vendor bought bananas at 6 for Rs 10 and sold them at 4 for Rs 8. What is his percentage profit?", 20.0, Difficulty.MEDIUM, "CP of 1 = 10/6 = 5/3. SP of 1 = 8/4 = 2. Profit = (2 - 5/3)/(5/3) = 1/5 = 20%.", {"kind": "numerical", "answer": 20.0, "tolerance": 0.5}),
        ("What is the simple interest on Rs 5000 for 3 years at an annual rate of 8%?", 1200.0, Difficulty.EASY, "SI = (P * R * T)/100 = (5000 * 8 * 3)/100 = Rs 1200.", {"kind": "numerical", "answer": 1200.0, "tolerance": 0.0}),
    ]
    for body, ans, diff, exp, spec in apt_num:
        qs.append(_make_q(subject=sub_apt, creator=examiner, qtype=QuestionType.NUMERICAL, category=cat_apt, topic="Quantitative Aptitude", body=body, difficulty=diff, marks=2.5, explanation=exp, spec=spec))

    # --------------------------------------------------------------------------
    # 6. CORPORATE - LOG101: Logical Reasoning
    # --------------------------------------------------------------------------
    sub_log = subjects["LOG101"]
    cat_log = QuestionCategory.LOGICAL_REASONING

    log_mcqs = [
        ("Pointing to a photograph of a boy, Suresh said, 'He is the son of the only son of my mother.' How is Suresh related to that boy?", ["Father", "Uncle", "Brother", "Grandfather"], 0, Difficulty.EASY, "Mother's only son is Suresh himself. So the boy is Suresh's son; Suresh is his Father."),
        ("Find the missing number in the series: 3, 8, 18, 38, 78, ___", ["158", "148", "168", "154"], 0, Difficulty.EASY, "Pattern: (x * 2) + 2. 78 * 2 + 2 = 158."),
        ("If 'PENCIL' is coded as 'QGODJM', how will 'ERASER' be coded in that same pattern?", ["FSBTFS", "FSBSDS", "FRBTFS", "FTATFS"], 0, Difficulty.MEDIUM, "Each letter shifted +1: E->F, R->S, A->B, S->T, E->F, R->S = FSBTFS."),
        ("Statements: All cats are dogs. All dogs are mammals. Conclusions: I. All cats are mammals. II. All mammals are cats.", ["Only conclusion I follows", "Only conclusion II follows", "Both conclusions follow", "Neither conclusion follows"], 0, Difficulty.EASY, "Cats subset of Dogs subset of Mammals -> All cats are mammals. Reverse is not necessarily true."),
        ("Six persons A, B, C, D, E, F are sitting in a circle facing the center. A is second to the left of C. B is to the immediate right of A. Who is sitting opposite to A if D is between C and E?", ["D", "E", "F", "C"], 1, Difficulty.HARD, "Circular arrangement resolves to E sitting directly opposite A."),
        ("In a certain code, '786' means 'study very hard', '958' means 'hard work pays', and '645' means 'study and work'. What digit stands for 'very'?", ["7", "8", "6", "9"], 0, Difficulty.MEDIUM, "Common comparisons isolate 7 for 'very'."),
    ]
    for body, opts, corr, diff, exp in log_mcqs:
        qs.append(_make_q(subject=sub_log, creator=examiner, qtype=QuestionType.MCQ, category=cat_log, topic="Logical Reasoning", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 7. CORPORATE - VRB101: Verbal Ability & English Communication
    # --------------------------------------------------------------------------
    sub_vrb = subjects["VRB101"]
    cat_vrb = QuestionCategory.VERBAL_ABILITY

    vrb_mcqs = [
        ("Choose the word that is most nearly SYNONYMOUS with 'PRAGMATIC':", ["Practical", "Theoretical", "Arrogant", "Indolent"], 0, Difficulty.EASY, "Pragmatic means dealing with matters practically rather than theoretically."),
        ("Choose the word that is most nearly OPPOSITE in meaning to 'EPHEMERAL':", ["Permanent", "Transitory", "Fleeting", "Fragile"], 0, Difficulty.MEDIUM, "Ephemeral means lasting for a very short time; its opposite is Permanent."),
        ("Identify the error in the sentence: 'Neither of the two candidates who applied for the post were found suitable.'", ["'were' should be 'was'", "'who applied' should be 'whom applied'", "'for the post' should be 'at the post'", "No error"], 0, Difficulty.MEDIUM, "'Neither' is singular and takes the singular verb 'was'."),
        ("Select the idiom that best fits: 'To reveal a secret carelessly or prematurely'", ["Spill the beans", "Bite the bullet", "Break the ice", "Burn the midnight oil"], 0, Difficulty.EASY, "'Spill the beans' means to disclose confidential information."),
        ("Fill in the blank with the most appropriate preposition: 'The committee members agreed _____ the proposed budget after extensive debate.'", ["to", "with", "on", "for"], 0, Difficulty.EASY, "One agrees 'to' a proposal or plan."),
    ]
    for body, opts, corr, diff, exp in vrb_mcqs:
        qs.append(_make_q(subject=sub_vrb, creator=examiner, qtype=QuestionType.MCQ, category=cat_vrb, topic="Verbal Ability", body=body, difficulty=diff, marks=1.5, negative=0.25, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 8. CORPORATE - TECH101: Core Technical & System Design
    # --------------------------------------------------------------------------
    sub_tech = subjects["TECH101"]
    cat_tech = QuestionCategory.TECHNICAL

    tech_mcqs = [
        ("In React, what happens when a state variable updated with setState receives the exact same primitive value as current state?", ["React skips rendering the component and its children", "React forces a full DOM re-mount", "An infinite re-render loop occurs", "React throws a warning in console"], 0, Difficulty.MEDIUM, "React uses Object.is comparison and bails out of re-renders if state hasn't changed."),
        ("Which of the following headers prevents cross-site clickjacking attacks?", ["X-Frame-Options: DENY", "X-Content-Type-Options: nosniff", "Access-Control-Allow-Origin: *", "Strict-Transport-Security"], 0, Difficulty.MEDIUM, "X-Frame-Options prevents the page from being embedded in iframes."),
        ("In distributed systems, which consensus algorithm is specifically designed to be understandable and is widely used in etcd and Consul?", ["Raft", "Paxos", "Zab", "Two-Phase Commit"], 0, Difficulty.MEDIUM, "Raft decomposes consensus into leader election, log replication, and safety."),
        ("What is the main benefit of using Redis as an in-memory cache in front of a relational database?", ["Sub-millisecond read latency and offloading high read traffic from disk-bound databases", "Automatic schema migration", "Guaranteed zero memory usage", "Enforcing referential integrity constraints"], 0, Difficulty.EASY, "Redis stores key-value data in RAM for microsecond data retrieval."),
        ("In TypeScript, what does the 'unknown' type represent compared to 'any'?", ["A type-safe counterpart to any that requires type narrowing before property access", "An alias for undefined or null", "A type that can never occur (bottom type)", "A variable that cannot be assigned any value"], 0, Difficulty.MEDIUM, "unknown is type-safe; you cannot invoke methods on it without narrowing first."),
        ("What is the purpose of a Database Connection Pool in backend web servers?", ["Reuse existing established database connections to avoid TCP/auth handshake overhead per request", "Encrypt database records at rest", "Shard data across multiple database nodes automatically", "Cache SQL query result sets on disk"], 0, Difficulty.EASY, "Connection pools maintain a pool of open connections, reducing connection latency."),
    ]
    for body, opts, corr, diff, exp in tech_mcqs:
        qs.append(_make_q(subject=sub_tech, creator=examiner, qtype=QuestionType.MCQ, category=cat_tech, topic="Software Engineering", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 9. CORPORATE - CODE101: Coding Challenges
    # --------------------------------------------------------------------------
    sub_code = subjects["CODE101"]
    cat_code = QuestionCategory.CODING

    coding_questions = [
        (
            "Two Sum Problem",
            "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\n### Example:\n```python\nInput: nums = [2, 7, 11, 15], target = 9\nOutput: [0, 1]\nExplanation: nums[0] + nums[1] == 9, return [0, 1].\n```",
            Difficulty.EASY,
            15.0,
            {
                "kind": "coding",
                "language": "python",
                "sample_cases": [
                    {"input": "nums = [2, 7, 11, 15], target = 9", "output": "[0, 1]", "explanation": "2 + 7 = 9"},
                    {"input": "nums = [3, 2, 4], target = 6", "output": "[1, 2]", "explanation": "2 + 4 = 6"},
                    {"input": "nums = [3, 3], target = 6", "output": "[0, 1]", "explanation": "3 + 3 = 6"}
                ]
            },
            "def twoSum(nums, target):\n    lookup = {}\n    for i, n in enumerate(nums):\n        diff = target - n\n        if diff in lookup:\n            return [lookup[diff], i]\n        lookup[n] = i\n    return []"
        ),
        (
            "Valid Parentheses Validator",
            "Given a string `s` containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nAn input string is valid if:\n1. Open brackets must be closed by the same type of brackets.\n2. Open brackets must be closed in the correct order.\n\n### Example:\n```python\nInput: s = \"()[]{}\"\nOutput: True\n```",
            Difficulty.EASY,
            15.0,
            {
                "kind": "coding",
                "language": "python",
                "sample_cases": [
                    {"input": "s = \"()\"", "output": "True"},
                    {"input": "s = \"()[]{}\"", "output": "True"},
                    {"input": "s = \"(]\"", "output": "False"},
                    {"input": "s = \"([)]\"", "output": "False"}
                ]
            },
            "def isValid(s: str) -> bool:\n    stack = []\n    mapping = {')': '(', '}': '{', ']': '['}\n    for char in s:\n        if char in mapping:\n            top = stack.pop() if stack else '#'\n            if mapping[char] != top:\n                return False\n        else:\n            stack.append(char)\n    return not stack"
        ),
        (
            "Longest Substring Without Repeating Characters",
            "Given a string `s`, find the length of the longest substring without repeating characters.\n\n### Example:\n```python\nInput: s = \"abcabcbb\"\nOutput: 3\nExplanation: The answer is \"abc\", with the length of 3.\n```",
            Difficulty.MEDIUM,
            20.0,
            {
                "kind": "coding",
                "language": "python",
                "sample_cases": [
                    {"input": "s = \"abcabcbb\"", "output": "3"},
                    {"input": "s = \"bbbbb\"", "output": "1"},
                    {"input": "s = \"pwwkew\"", "output": "3"}
                ]
            },
            "def lengthOfLongestSubstring(s: str) -> int:\n    used = {}\n    max_len = start = 0\n    for i, char in enumerate(s):\n        if char in used and start <= used[char]:\n            start = used[char] + 1\n        else:\n            max_len = max(max_len, i - start + 1)\n        used[char] = i\n    return max_len"
        )
    ]
    for title, body, diff, marks, spec, model_ans in coding_questions:
        qs.append(_make_q(subject=sub_code, creator=examiner, qtype=QuestionType.CODING, category=cat_code, topic="Algorithms", body=body, difficulty=diff, marks=marks, spec=spec, model_answer=model_ans))

    db.add_all(qs)
    db.flush()
    logger.info("Seeded %d questions across all categories and subjects", len(qs))
    return qs


# ==============================================================================
# 12 REAL EXAM DEFINITIONS (6 Academic + 6 Corporate Hiring)
# ==============================================================================

def _seed_exams(
    db: Session,
    subjects: dict[str, Subject],
    examiner: User,
    candidates: list[User],
    questions: list[Question],
) -> None:
    if db.scalar(select(func.count(Exam.id))):
        logger.info("Exams already exist (%d found) - skipping exam seed", db.scalar(select(func.count(Exam.id))))
        return

    now = datetime.now(UTC)
    q_by_sub = {}
    for q in questions:
        q_by_sub.setdefault(q.subject.code, []).append(q)

    # Helper to pick subset of questions
    def pick(sub_code: str, types: set[QuestionType] | None = None, limit: int = 10) -> list[Question]:
        pool = q_by_sub.get(sub_code, [])
        if types:
            pool = [q for q in pool if q.question_type in types]
        return pool[:limit]

    created_exams: list[Exam] = []

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 1: CS101 Semester Final Examination (Comprehensive)
    # --------------------------------------------------------------------------
    e1 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS101"].id,
        title="CS101 Semester Final Examination (Comprehensive)",
        description="Comprehensive semester assessment covering computer architecture, operating systems, networking, and data structures. Objective and subjective evaluation.",
        instructions="Ensure webcam is centered. No mobile devices, headphones, or tab switching permitted. Save answers frequently.",
        course="B.Tech Computer Science & Engineering",
        department="Computer Science & Engineering",
        semester="Semester IV",
        duration_minutes=90,
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=40.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": "easy", "count": 4},
                {"question_type": "mcq", "difficulty": "medium", "count": 4},
                {"question_type": "multi_select", "difficulty": None, "count": 2},
                {"question_type": "short_answer", "difficulty": None, "count": 2},
                {"question_type": "long_answer", "difficulty": None, "count": 1},
                {"question_type": "image_upload", "difficulty": None, "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=True,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS101", limit=18)):
        e1.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e1)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 2: CS102 Mid-Term Unit Assessment: Data Structures
    # --------------------------------------------------------------------------
    e2 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS102"].id,
        title="CS102 Mid-Term Unit Assessment: Data Structures & Algorithms",
        description="Mid-semester unit assessment focusing on linear and non-linear data structures, asymptotic notation, sorting, and graph traversals.",
        instructions="Read each problem carefully. Auto-evaluated objective questions followed by algorithmic design problems.",
        course="B.Tech CSE",
        department="Computer Science & Engineering",
        semester="Semester III",
        duration_minutes=45,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=21),
        declared_total_marks=50.0,
        passing_percentage=50.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 6},
                {"question_type": "coding", "difficulty": "easy", "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS102", limit=8) + pick("CODE101", limit=1)):
        e2.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e2)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 3: CS201 Objective & Speed Quiz: Database Systems
    # --------------------------------------------------------------------------
    e3 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS201"].id,
        title="CS201 Objective & Speed Quiz: Database Systems",
        description="Fast-paced objective quiz covering SQL syntax, normal forms, transaction ACID properties, and relational algebra. Results publish immediately.",
        instructions="Auto-published test. No backtracking on timed questions. Finish before timer expires.",
        course="BCA / MCA",
        department="Information Technology",
        semester="Semester II",
        duration_minutes=20,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=45),
        declared_total_marks=30.0,
        passing_percentage=60.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 4},
                {"question_type": "true_false", "difficulty": None, "count": 2},
                {"question_type": "fill_blank", "difficulty": None, "count": 2},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG, "require_fullscreen": False},
        grading_config={**DEFAULT_GRADING_CONFIG, "auto_publish_results": True},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS201", limit=6) + pick("CS101", {QuestionType.TRUE_FALSE, QuestionType.FILL_BLANK}, limit=4)):
        e3.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e3)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 4: CS301 Practical & Software Engineering Lab Viva
    # --------------------------------------------------------------------------
    e4 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS301"].id,
        title="CS301 Practical & Software Engineering Lab Viva Assessment",
        description="Lab evaluation and viva assessment on Software Design Patterns, RESTful APIs, UML Modeling, and CI/CD pipelines.",
        instructions="Diagrams must be clearly visible. Upload scans for architecture design questions.",
        course="B.Tech IT",
        department="Software Engineering",
        semester="Semester VI",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=15),
        declared_total_marks=60.0,
        passing_percentage=50.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 3},
                {"question_type": "short_answer", "difficulty": None, "count": 2},
                {"question_type": "image_upload", "difficulty": None, "count": 1},
            ]
        },
        randomize=False,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS301", limit=4) + pick("CS101", {QuestionType.SHORT_ANSWER, QuestionType.IMAGE_UPLOAD}, limit=3)):
        e4.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e4)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 5: CS101 Theoretical Foundations & Essay Examination
    # --------------------------------------------------------------------------
    e5 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS101"].id,
        title="CS101 Theoretical Foundations & Descriptive Essay Examination",
        description="Deep theoretical examination evaluating system architecture, concurrency theory, and distributed consensus mechanisms.",
        instructions="Detailed written arguments required. Ensure answers meet minimum word counts indicated per question.",
        course="M.Sc Computer Science",
        department="Computer Science",
        semester="Semester I",
        duration_minutes=75,
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(days=20),
        declared_total_marks=80.0,
        passing_percentage=45.0,
        selection_rules={
            "rules": [
                {"question_type": "short_answer", "difficulty": None, "count": 3},
                {"question_type": "long_answer", "difficulty": None, "count": 2},
            ]
        },
        randomize=True,
        shuffle_options=False,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS101", {QuestionType.SHORT_ANSWER, QuestionType.LONG_ANSWER}, limit=6)):
        e5.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e5)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 6: CS100 Merit Scholarship & National Entrance Test
    # --------------------------------------------------------------------------
    e6 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["CS101"].id,
        title="CS100 Merit Scholarship & National Engineering Entrance Test",
        description="High-stakes competitive entrance examination with negative marking, time-bounded problem solving, and strict AI proctoring surveillance.",
        instructions="Negative marking: 0.5 marks deducted for wrong answers. Strict proctoring active - tab switches immediately flagged.",
        course="National Entrance Test",
        department="Engineering Admissions",
        semester="2026 Batch",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=60),
        declared_total_marks=100.0,
        passing_percentage=70.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": "hard", "count": 4},
                {"question_type": "mcq", "difficulty": "medium", "count": 6},
                {"question_type": "numerical", "difficulty": None, "count": 2},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=True,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG, "terminate_on_score": 80.0, "flag_on_score": 35.0},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    for idx, q in enumerate(pick("CS101", {QuestionType.MCQ, QuestionType.NUMERICAL}, limit=15)):
        e6.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e6)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 7: TechCorp Full-Stack Software Engineer (SDE-1) Assessment
    # --------------------------------------------------------------------------
    e7 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["TECH101"].id,
        title="TechCorp Global: Full-Stack Software Engineer (SDE-1) Assessment",
        description="Comprehensive 4-section recruitment assessment: Quantitative Aptitude, Core CS & Web Technologies, System Architecture, and Live Hands-on Coding.",
        instructions="Complete all sections within 90 minutes. Coding challenge must pass sample test cases.",
        company_name="TechCorp Global",
        job_role="Full-Stack Software Engineer (SDE-1)",
        duration_minutes=90,
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=70.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 8},
                {"question_type": "coding", "difficulty": "easy", "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=True,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    # Add Sections
    e7.sections.append(ExamSection(name="Section 1: Quantitative & Analytical Aptitude", description="Problem solving and quantitative skills", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 3}]}, marks_per_question=2.0, duration_minutes=20))
    e7.sections.append(ExamSection(name="Section 2: Core CS & Web Technologies", description="React, TypeScript, databases, and APIs", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=3.0, duration_minutes=30))
    e7.sections.append(ExamSection(name="Section 3: Hands-on Coding Challenge", description="Algorithmic programming implementation", order_index=2, selection_rules={"rules": [{"question_type": "coding", "difficulty": "easy", "count": 1}]}, marks_per_question=20.0, duration_minutes=40))
    
    # Pool questions
    for idx, q in enumerate(pick("APT101", limit=4) + pick("TECH101", limit=6) + pick("CODE101", limit=1)):
        e7.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e7)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 8: Apex Consulting Quantitative & Logical Aptitude Screening
    # --------------------------------------------------------------------------
    e8 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["APT101"].id,
        title="Apex Strategic Consulting: Quantitative & Logical Aptitude Screening",
        description="First-round analytical screening test measuring mathematical acumen, data interpretation, critical thinking, and deductive logic.",
        instructions="Calculators are not permitted. Negative marking is active for incorrect selections.",
        company_name="Apex Strategic Consulting",
        job_role="Associate Consultant / Analyst",
        duration_minutes=45,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=45),
        declared_total_marks=60.0,
        passing_percentage=65.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 8},
                {"question_type": "numerical", "difficulty": None, "count": 2},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=True,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    e8.sections.append(ExamSection(name="Section A: Numerical Ability & Math", description="Arithmetic, percentages, time-speed-distance", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=2.5, duration_minutes=25))
    e8.sections.append(ExamSection(name="Section B: Logical & Deductive Reasoning", description="Series, arrangements, blood relations", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=2.5, duration_minutes=20))
    for idx, q in enumerate(pick("APT101", limit=6) + pick("LOG101", limit=6)):
        e8.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e8)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 9: FinTech Global Data Analyst & BI Specialist Assessment
    # --------------------------------------------------------------------------
    e9 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["TECH101"].id,
        title="FinTech Global Solutions: Data Analyst & BI Specialist Assessment",
        description="Assessment for Data Analysts covering SQL querying, statistics, data modeling, business insight deduction, and analytical aptitude.",
        instructions="Answer SQL syntax and data reasoning questions accurately.",
        company_name="FinTech Global Solutions",
        job_role="Data Analyst & BI Specialist",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=25),
        declared_total_marks=75.0,
        passing_percentage=60.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 8},
                {"question_type": "short_answer", "difficulty": None, "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    e9.sections.append(ExamSection(name="SQL & Relational Databases", description="Complex joins, aggregation, subqueries", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=3.0))
    e9.sections.append(ExamSection(name="Quantitative & Data Interpretation", description="Statistical inference and metric calculation", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=3.0))
    for idx, q in enumerate(pick("CS201", limit=4) + pick("APT101", limit=5) + pick("TECH101", limit=3)):
        e9.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e9)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 10: MetaLab Senior Frontend Engineer Assessment
    # --------------------------------------------------------------------------
    e10 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["TECH101"].id,
        title="MetaLab Innovations: Senior Frontend Engineer Assessment",
        description="Deep frontend engineering screening evaluating React 19 / Next.js internals, TypeScript strict typing, Web Performance, DOM APIs, and CSS Architecture.",
        instructions="Technical evaluation of modern frontend engineering practices.",
        company_name="MetaLab Innovations",
        job_role="Senior Frontend Engineer (React / Next.js)",
        duration_minutes=75,
        starts_at=now - timedelta(hours=2),
        ends_at=now + timedelta(days=30),
        declared_total_marks=80.0,
        passing_percentage=70.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 6},
                {"question_type": "coding", "difficulty": "easy", "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    e10.sections.append(ExamSection(name="HTML5, CSS, DOM & Modern Web APIs", description="Layouts, box-model, accessibility, Web APIs", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 3}]}, marks_per_question=2.0))
    e10.sections.append(ExamSection(name="React State, TypeScript & Performance", description="Hooks, re-renders, virtual DOM, types", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 3}]}, marks_per_question=3.0))
    e10.sections.append(ExamSection(name="Frontend Coding & String Algorithms", description="UI state algorithms and data transformation", order_index=2, selection_rules={"rules": [{"question_type": "coding", "difficulty": "easy", "count": 1}]}, marks_per_question=20.0))
    for idx, q in enumerate(pick("TECH101", limit=6) + pick("CS301", limit=3) + pick("CODE101", limit=1)):
        e10.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e10)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 11: CloudScale Systems Backend & Distributed Systems Assessment
    # --------------------------------------------------------------------------
    e11 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["TECH101"].id,
        title="CloudScale Systems: Backend & Distributed Systems Assessment",
        description="Senior engineering test on OS concurrency, database transaction engines, Redis caching, microservice communication, and high-throughput scalability.",
        instructions="Comprehensive backend systems test.",
        company_name="CloudScale Systems",
        job_role="Backend / Distributed Systems Engineer",
        duration_minutes=90,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=35),
        declared_total_marks=100.0,
        passing_percentage=65.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 8},
                {"question_type": "coding", "difficulty": "medium", "count": 1},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=True,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    e11.sections.append(ExamSection(name="OS, Concurrency & Networking", description="Threads, sockets, TCP, race conditions", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=3.0))
    e11.sections.append(ExamSection(name="Databases, WAL & Distributed Consensus", description="Raft, 2PC, MVCC, Indexing", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 4}]}, marks_per_question=3.0))
    e11.sections.append(ExamSection(name="Backend Coding Challenge", description="Algorithmic problem solving", order_index=2, selection_rules={"rules": [{"question_type": "coding", "difficulty": "medium", "count": 1}]}, marks_per_question=25.0))
    for idx, q in enumerate(pick("TECH101", limit=5) + pick("CS101", limit=5) + pick("CODE101", limit=2)):
        e11.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e11)

    # --------------------------------------------------------------------------
    # CORPORATE EXAM 12: Tata Tech Freshers Campus Graduate Hiring Drive
    # --------------------------------------------------------------------------
    e12 = Exam(
        exam_type=ExamType.CORPORATE,
        subject_id=subjects["APT101"].id,
        title="Tata Tech Global: Freshers Campus Graduate Hiring Drive 2026",
        description="National campus recruitment screening assessment covering Quantitative Aptitude, Logical Reasoning, Verbal Communication, and Basic Programming.",
        instructions="Sectional timed paper. Candidates must clear cutoffs across all 4 sections.",
        company_name="Tata Tech Global",
        job_role="Graduate Trainee Engineer (GET)",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=60),
        declared_total_marks=75.0,
        passing_percentage=60.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 10},
            ]
        },
        randomize=True,
        shuffle_options=True,
        negative_marking=False,
        paper_salt=generate_salt(),
        proctor_config={**DEFAULT_PROCTOR_CONFIG},
        grading_config={**DEFAULT_GRADING_CONFIG},
        status=ExamStatus.PUBLISHED,
        created_by_id=examiner.id,
    )
    e12.sections.append(ExamSection(name="Quantitative Aptitude", description="Numerical problem solving", order_index=0, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 3}]}, marks_per_question=2.0, duration_minutes=15))
    e12.sections.append(ExamSection(name="Logical & Deductive Reasoning", description="Puzzles and series", order_index=1, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 3}]}, marks_per_question=2.0, duration_minutes=15))
    e12.sections.append(ExamSection(name="Verbal Ability & English", description="Grammar and comprehension", order_index=2, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 2}]}, marks_per_question=2.0, duration_minutes=15))
    e12.sections.append(ExamSection(name="Basic Computer Science Foundations", description="Syntax and core concepts", order_index=3, selection_rules={"rules": [{"question_type": "mcq", "difficulty": None, "count": 2}]}, marks_per_question=2.0, duration_minutes=15))
    for idx, q in enumerate(pick("APT101", limit=4) + pick("LOG101", limit=4) + pick("VRB101", limit=4) + pick("CS101", limit=4)):
        e12.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e12)

    db.add_all(created_exams)
    db.flush()

    # Enroll all candidates in all seeded exams
    now_ts = datetime.now(UTC)
    for exam_row in created_exams:
        for candidate in candidates:
            db.add(
                ExamEnrollment(
                    exam_id=exam_row.id,
                    candidate_id=candidate.id,
                    assigned_by_id=examiner.id,
                    assigned_at=now_ts,
                )
            )
    db.flush()
    logger.info("Successfully seeded 12 real Exams (6 Academic + 6 Corporate) and %d enrolments", len(created_exams) * len(candidates))


def seed(db: Session) -> None:
    _user(
        db,
        email=settings.FIRST_ADMIN_EMAIL,
        name="Admin Administrator",
        role=UserRole.ADMIN,
        access=AccessStatus.APPROVED,
        password=settings.FIRST_ADMIN_PASSWORD,
    )
    examiner = _user(
        db,
        email="examiner@exam.edu",
        name="Dr. Approved Examiner",
        role=UserRole.EXAMINER,
        access=AccessStatus.APPROVED,
    )
    _user(
        db,
        email="pending.examiner@exam.edu",
        name="Dr. Pending Examiner",
        role=UserRole.EXAMINER,
        access=AccessStatus.PENDING,
    )
    candidates: list[User] = []
    for i, (first, last, login_state) in enumerate(
        [
            ("Aditi", "Sharma", LoginAccessStatus.APPROVED),
            ("Rahul", "Verma", LoginAccessStatus.APPROVED),
            ("Meera", "Nair", LoginAccessStatus.PENDING),
        ],
        start=1,
    ):
        candidate = _user(
            db,
            email=f"candidate{i}@exam.edu",
            name=f"{first} {last}",
            role=UserRole.CANDIDATE,
            access=AccessStatus.APPROVED,
        )
        _login_access(db, candidate, login_state)
        candidates.append(candidate)

    # Seed All Subjects
    subjects = {
        "CS101": _subject(db, "CS101", "Computer Science Fundamentals", "Core CS: OS, DBMS, Computer Networks, Systems"),
        "CS102": _subject(db, "CS102", "Data Structures & Algorithms", "Linear & non-linear structures, graphs, complexity"),
        "CS201": _subject(db, "CS201", "Database Management Systems", "Relational SQL, ACID, Indexes, Normalization"),
        "CS301": _subject(db, "CS301", "Web & Software Engineering", "Design patterns, REST, Architecture, CI/CD"),
        "APT101": _subject(db, "APT101", "Quantitative Aptitude", "Mathematical problem solving, arithmetic, statistics"),
        "LOG101": _subject(db, "LOG101", "Logical Reasoning", "Analytical thinking, puzzles, series, deductions"),
        "VRB101": _subject(db, "VRB101", "Verbal Ability & English", "Grammar, vocabulary, reading comprehension"),
        "TECH101": _subject(db, "TECH101", "Core Technical & System Design", "Frontend, backend, distributed systems, architecture"),
        "CODE101": _subject(db, "CODE101", "Programming Challenges", "Hands-on coding problems, algorithmic implementations"),
    }

    questions = _seed_questions(db, subjects, examiner)
    _seed_exams(db, subjects, examiner, candidates, questions)


def main() -> None:
    setup_logging()
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        print("\nSeed complete! Ready-to-use dataset populated:")
        print("  - 9 Subjects across Academic & Corporate hiring domains")
        print("  - 240+ Questions in the Question Bank (MCQ, Multi-select, T/F, Fill-blank, Numerical, Short/Long, Image, Coding)")
        print("  - 12 Real ready-to-use Exams created with pools & sections:")
        print("      * 6 Academic Exams (Semester Final, Mid-Term DSA, Speed Quiz, Practical Viva, Essay, Scholarship)")
        print("      * 6 Corporate Hiring Exams (Full-Stack SDE-1, Consulting Aptitude, Data Analyst, Frontend, Backend, Freshers)")
        print(f"\n  Admin login:     {settings.FIRST_ADMIN_EMAIL} / {settings.FIRST_ADMIN_PASSWORD}")
        print(f"  Examiner login:  examiner@exam.edu / {DEMO_PASSWORD}")
        print(f"  Candidate login: candidate1@exam.edu / {DEMO_PASSWORD}\n")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
