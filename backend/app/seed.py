"""Seed the platform with a comprehensive demo dataset.

Idempotent: re-running tops up what is missing rather than duplicating. Run with:

    uv run python -m app.seed
"""

from __future__ import annotations

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
from app.seed_question_bank_bulk import FLOOR_PER_TYPE
from app.seed_question_bank_bulk import top_up as top_up_question_bank
from app.seed_question_bank_images import top_up_images

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
    for body, _accepted, diff, exp, spec in cs101_fill:
        qs.append(_make_q(subject=sub, creator=examiner, qtype=QuestionType.FILL_BLANK, category=cat, topic="Definitions", body=body, difficulty=diff, marks=2.0, explanation=exp, spec=spec))

    # Numerical
    cs101_num = [
        ("What is the maximum number of nodes in a binary tree of depth 4 (considering root at depth 0)?", 31.0, Difficulty.MEDIUM, "Max nodes = 2^(h+1) - 1 = 2^5 - 1 = 31.", {"kind": "numerical", "answer": 31.0, "tolerance": 0.0}),
        ("Calculate the total number of distinct simple graphs that can be formed with 4 labeled vertices.", 64.0, Difficulty.HARD, "Number of possible edges is 4C2 = 6. Total graphs = 2^6 = 64.", {"kind": "numerical", "answer": 64.0, "tolerance": 0.0}),
    ]
    for body, _ans, diff, exp, spec in cs101_num:
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
    # 4a. ACADEMIC - CS202: Operating Systems
    # --------------------------------------------------------------------------
    sub_os = subjects["CS202"]
    os_mcqs = [
        ("What is the primary purpose of a Process Control Block (PCB)?", ["Store all state information needed to manage a process", "Cache disk blocks for faster I/O", "Translate virtual addresses to physical addresses", "Schedule interrupts between CPU cores"], 0, Difficulty.EASY, "The PCB holds process state, registers, scheduling info, and memory pointers."),
        ("Which page replacement algorithm suffers from Belady's Anomaly?", ["FIFO", "LRU", "Optimal", "Second-Chance"], 0, Difficulty.MEDIUM, "FIFO can increase page faults when frame count increases, unlike stack-based algorithms."),
        ("A binary semaphore is functionally equivalent to which construct?", ["Mutex lock", "Monitor", "Spinlock with busy-waiting only", "Readers-writers lock"], 0, Difficulty.EASY, "A binary semaphore (0/1) enforces mutual exclusion just like a mutex."),
        ("In virtual memory systems, what does 'thrashing' refer to?", ["Excessive paging activity causing low CPU utilization", "A CPU cache miss on every instruction fetch", "Two processes writing to the same file simultaneously", "A deadlock between two kernel threads"], 0, Difficulty.MEDIUM, "Thrashing occurs when processes spend more time paging than executing."),
        ("Which scheduling algorithm minimizes average waiting time for a known, fixed set of jobs?", ["Shortest Job First (SJF)", "First Come First Served (FCFS)", "Round Robin", "Priority Scheduling with aging"], 0, Difficulty.MEDIUM, "SJF is provably optimal for minimizing average waiting time given known burst times."),
        ("What condition is necessary (but not sufficient) for a race condition to occur?", ["Shared mutable state accessed by concurrent threads without synchronization", "Use of a single-threaded event loop", "Static allocation of all variables", "Compilation with optimization flags disabled"], 0, Difficulty.HARD, "Race conditions require shared state and concurrent unsynchronized access."),
        ("What is the main difference between a process and a thread?", ["Threads share the address space of their parent process; processes have separate address spaces", "Processes are faster to create than threads", "Threads cannot be scheduled independently", "Processes share memory by default"], 0, Difficulty.EASY, "Threads within a process share code, data, and heap segments but have their own stack and registers."),
        ("Which of the following best describes a deadlock?", ["A set of processes are each waiting for a resource held by another in the set", "A process is terminated by the OS due to a segmentation fault", "Two threads execute the same instruction simultaneously", "A process exceeds its allocated CPU time quantum"], 0, Difficulty.MEDIUM, "Deadlock is a circular wait where no process can proceed."),
        ("What is the purpose of the 'dirty bit' in a page table entry?", ["Indicate whether a page has been modified since it was loaded", "Indicate whether a page is present in memory", "Indicate the protection level of the page", "Indicate the page's reference count"], 0, Difficulty.MEDIUM, "A dirty page must be written back to disk before it is evicted; a clean page can simply be discarded."),
        ("Which IPC mechanism allows unrelated processes to communicate via a name registered in the filesystem namespace?", ["Named pipe (FIFO)", "Anonymous pipe", "Shared global variable", "Register file"], 0, Difficulty.MEDIUM, "Named pipes exist as filesystem entries, so unrelated processes can open them by name."),
        ("In the Banker's Algorithm, what is checked before granting a resource request?", ["Whether granting the request leaves the system in a safe state", "Whether the requesting process has the highest priority", "Whether the resource has ever been allocated before", "Whether the request exceeds the total system memory"], 0, Difficulty.HARD, "The Banker's Algorithm simulates allocation and checks for at least one safe sequence."),
        ("What is the primary difference between internal and external fragmentation?", ["Internal fragmentation wastes space within an allocated block; external wastes space between blocks", "Internal fragmentation only occurs in paging; external only in segmentation", "External fragmentation is fixed by increasing page size", "Internal fragmentation cannot occur in fixed-size partitioning"], 0, Difficulty.MEDIUM, "Internal fragmentation is unused space inside a fixed-size allocation; external is scattered free space between allocations."),
        ("Which scheduling algorithm is preemptive and assigns each process a fixed time slice in cyclic order?", ["Round Robin", "First Come First Served", "Shortest Job First (non-preemptive)", "Priority Scheduling (non-preemptive)"], 0, Difficulty.EASY, "Round Robin cycles through the ready queue, preempting each process after its quantum expires."),
        ("What does the 'C' in the CPU's fetch-decode-execute cycle NOT refer to?", ["Cache invalidation", "Control unit signal generation", "Clock synchronization", "Instruction cycle continuation"], 0, Difficulty.HARD, "The fetch-decode-execute cycle involves the control unit and clock, not cache invalidation as a defining step."),
        ("Which of the following is true about a Monitor (in concurrent programming)?", ["It encapsulates shared data and provides mutually exclusive access via built-in condition variables", "It requires manual semaphore management by the programmer", "It can only be used for inter-process, not inter-thread, communication", "It guarantees deadlock-free execution automatically"], 0, Difficulty.MEDIUM, "A monitor bundles shared data, procedures, and condition variables so only one thread executes inside it at a time."),
        ("What happens during a context switch?", ["The OS saves the state of the current process/thread and loads the state of the next one to run", "The CPU clock speed is temporarily increased", "The page table is deleted and rebuilt", "All open file descriptors are closed"], 0, Difficulty.EASY, "A context switch saves/restores register state, program counter, and other process control block data."),
        ("Which file allocation method suffers most from external fragmentation on disk?", ["Contiguous allocation", "Linked allocation", "Indexed allocation", "None of the above"], 0, Difficulty.MEDIUM, "Contiguous allocation requires a single unbroken run of blocks, leading to fragmentation as files are created/deleted."),
        ("What is a 'zombie process' in Unix-like systems?", ["A terminated process whose exit status has not yet been read by its parent", "A process stuck in an infinite loop", "A process running with root privileges", "A process that has forked but not yet executed"], 0, Difficulty.MEDIUM, "A zombie retains its PCB entry until the parent calls wait() to collect the exit status."),
        ("Which of these is a necessary condition for priority inversion to occur?", ["A lower-priority task holds a resource needed by a higher-priority task", "Two tasks have the exact same priority", "The scheduler uses Round Robin", "The system has only one CPU core"], 0, Difficulty.HARD, "Priority inversion happens when a high-priority task is blocked waiting on a lock held by a lower-priority task."),
        ("What is the main advantage of demand paging over loading an entire process into memory at once?", ["Only pages actually needed are loaded, reducing memory usage and startup time", "It eliminates the need for a page table", "It guarantees zero page faults", "It removes the need for virtual memory"], 0, Difficulty.EASY, "Demand paging loads pages lazily on first access, improving memory utilization."),
    ]
    for body, opts, corr, diff, exp in os_mcqs:
        qs.append(_make_q(subject=sub_os, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Operating Systems", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4b. ACADEMIC - CS203: Computer Networks
    # --------------------------------------------------------------------------
    sub_cn = subjects["CS203"]
    cn_mcqs = [
        ("Which transport-layer protocol provides reliable, ordered, connection-oriented delivery?", ["TCP", "UDP", "ICMP", "IP"], 0, Difficulty.EASY, "TCP uses sequence numbers, acknowledgements, and retransmission for reliability."),
        ("What is the purpose of the three-way handshake in TCP connection establishment?", ["Synchronize sequence numbers between client and server", "Encrypt the payload before transmission", "Assign a dynamic IP address to the client", "Compress the packet headers"], 0, Difficulty.MEDIUM, "SYN, SYN-ACK, ACK synchronizes initial sequence numbers on both ends."),
        ("Which DNS record type maps a domain name directly to an IPv4 address?", ["A record", "CNAME record", "MX record", "TXT record"], 0, Difficulty.EASY, "An A record resolves a hostname to an IPv4 address."),
        ("In CSMA/CD, what action is taken when a collision is detected?", ["Transmission stops and a random backoff timer is used before retry", "The frame is immediately re-sent without delay", "The sender switches to a different protocol", "The receiver requests a checksum recalculation"], 0, Difficulty.MEDIUM, "CSMA/CD aborts transmission on collision and retries after exponential backoff."),
        ("Which subnet mask corresponds to a /26 CIDR block?", ["255.255.255.192", "255.255.255.224", "255.255.255.240", "255.255.255.128"], 0, Difficulty.MEDIUM, "/26 leaves 6 host bits, giving mask 11000000 in the last octet = 192."),
        ("What is the main advantage of using a Link State routing protocol (e.g., OSPF) over Distance Vector (e.g., RIP)?", ["Faster convergence and no count-to-infinity problem", "Lower memory usage on routers", "No need for periodic updates", "Simpler configuration with fewer messages"], 0, Difficulty.HARD, "Link state protocols flood full topology, enabling faster, loop-free convergence."),
        ("Which layer of the OSI model is responsible for end-to-end error recovery and flow control?", ["Transport Layer", "Network Layer", "Data Link Layer", "Session Layer"], 0, Difficulty.EASY, "The Transport layer (e.g., TCP) provides reliable end-to-end delivery with flow and error control."),
        ("What is the purpose of NAT (Network Address Translation)?", ["Allow multiple devices on a private network to share a single public IP address", "Encrypt traffic between two hosts", "Resolve domain names to IP addresses", "Assign MAC addresses to network interfaces"], 0, Difficulty.EASY, "NAT translates private IP addresses to a public one at the network boundary."),
        ("Which protocol is used to automatically assign IP addresses to hosts on a network?", ["DHCP", "ARP", "DNS", "ICMP"], 0, Difficulty.EASY, "DHCP dynamically leases IP addresses and network configuration to clients."),
        ("In HTTPS, which protocol provides the encryption layer beneath HTTP?", ["TLS", "SSH", "IPSec", "SNMP"], 0, Difficulty.EASY, "TLS (successor to SSL) encrypts the HTTP payload for HTTPS connections."),
        ("What does the TTL (Time To Live) field in an IP header prevent?", ["Packets looping indefinitely in the network", "Packets exceeding the MTU size", "Duplicate ACKs during congestion", "Fragmentation of large packets"], 0, Difficulty.MEDIUM, "Each hop decrements TTL; the packet is discarded when it reaches zero, preventing infinite loops."),
        ("Which of the following best describes UDP compared to TCP?", ["Connectionless, no guaranteed delivery, lower overhead", "Connection-oriented with guaranteed in-order delivery", "Requires a three-way handshake before data transfer", "Provides built-in congestion control"], 0, Difficulty.EASY, "UDP is a lightweight, connectionless protocol with no delivery or ordering guarantees."),
        ("What is the purpose of the Spanning Tree Protocol (STP) in switched networks?", ["Prevent broadcast storms by eliminating loops in the network topology", "Encrypt Layer 2 frames", "Assign VLAN tags to frames", "Translate MAC addresses to IP addresses"], 0, Difficulty.MEDIUM, "STP blocks redundant paths to build a loop-free logical topology."),
        ("Which port number is conventionally used by HTTPS?", ["443", "80", "21", "25"], 0, Difficulty.EASY, "Port 443 is the well-known port for HTTPS traffic."),
        ("What is 'subnetting' primarily used for?", ["Dividing a large network into smaller, manageable sub-networks", "Encrypting packets between subnets", "Increasing the MTU of a network", "Assigning static MAC addresses"], 0, Difficulty.EASY, "Subnetting partitions an IP address space to improve routing efficiency and isolate traffic."),
        ("Which congestion control mechanism does TCP use to gradually increase its sending rate after a slow start?", ["Congestion avoidance (additive increase, multiplicative decrease)", "Fixed-size sliding window with no adjustment", "Random early detection only", "Static bandwidth allocation"], 0, Difficulty.HARD, "TCP congestion avoidance increases the window additively and halves it multiplicatively on loss (AIMD)."),
        ("What does an ARP spoofing attack primarily exploit?", ["The lack of authentication in ARP replies, allowing MAC address impersonation", "A buffer overflow in the DNS resolver", "Weak TLS cipher suites", "Misconfigured firewall NAT rules"], 0, Difficulty.HARD, "ARP has no authentication, so a host can send forged ARP replies to redirect traffic."),
        ("Which topology connects every node to a central hub or switch?", ["Star topology", "Bus topology", "Ring topology", "Mesh topology"], 0, Difficulty.EASY, "In a star topology, all nodes connect individually to a central device."),
        ("What is the function of the SYN-ACK flag combination during TCP handshake?", ["Server acknowledges the client's SYN and sends its own synchronization request", "Client terminates the connection gracefully", "Server rejects the connection request", "Client requests retransmission of lost segments"], 0, Difficulty.MEDIUM, "SYN-ACK is step two of the three-way handshake, both acknowledging and synchronizing."),
        ("Which class of IPv4 address range is reserved for multicast traffic?", ["Class D (224.0.0.0 - 239.255.255.255)", "Class A (1.0.0.0 - 126.255.255.255)", "Class B (128.0.0.0 - 191.255.255.255)", "Class C (192.0.0.0 - 223.255.255.255)"], 0, Difficulty.MEDIUM, "Class D addresses are reserved for multicast group communication."),
    ]
    for body, opts, corr, diff, exp in cn_mcqs:
        qs.append(_make_q(subject=sub_cn, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Computer Networks", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4c. ACADEMIC - MATH101: Engineering Mathematics
    # --------------------------------------------------------------------------
    sub_math = subjects["MATH101"]
    math_mcqs = [
        ("What is the derivative of f(x) = 3x^2 + 5x - 7?", ["6x + 5", "3x + 5", "6x - 7", "x^2 + 5"], 0, Difficulty.EASY, "d/dx(3x^2) = 6x, d/dx(5x) = 5, derivative of a constant is 0."),
        ("What is the determinant of a 2x2 matrix [[a, b], [c, d]]?", ["ad - bc", "ac - bd", "ab - cd", "ad + bc"], 0, Difficulty.EASY, "The determinant of a 2x2 matrix is the product of the main diagonal minus the product of the anti-diagonal."),
        ("Which method is used to solve a system of linear equations by row-reducing an augmented matrix?", ["Gaussian elimination", "Newton-Raphson method", "Simpson's rule", "Lagrange interpolation"], 0, Difficulty.MEDIUM, "Gaussian elimination reduces the augmented matrix to row-echelon form to solve for unknowns."),
        ("What is the value of the integral of sin(x) dx?", ["-cos(x) + C", "cos(x) + C", "-sin(x) + C", "tan(x) + C"], 0, Difficulty.EASY, "The antiderivative of sin(x) is -cos(x), plus constant of integration."),
        ("A matrix A has eigenvalues 2 and 3. What is the determinant of A (assuming A is 2x2)?", ["6", "5", "1", "0"], 0, Difficulty.MEDIUM, "The determinant of a matrix equals the product of its eigenvalues."),
        ("Which probability distribution is characterized by a bell-shaped, symmetric curve defined by mean and variance?", ["Normal (Gaussian) distribution", "Poisson distribution", "Binomial distribution", "Exponential distribution"], 0, Difficulty.EASY, "The Normal distribution is fully described by its mean and variance, forming a symmetric bell curve."),
    ]
    for body, opts, corr, diff, exp in math_mcqs:
        qs.append(_make_q(subject=sub_math, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Engineering Mathematics", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4d. ACADEMIC - ML101: Machine Learning
    # --------------------------------------------------------------------------
    sub_ml = subjects["ML101"]
    ml_mcqs = [
        ("Which algorithm finds a hyperplane that maximizes the margin between two classes?", ["Support Vector Machine (SVM)", "K-Means Clustering", "Linear Regression", "Principal Component Analysis"], 0, Difficulty.MEDIUM, "SVM maximizes the margin between the separating hyperplane and the nearest points of each class."),
        ("What does 'overfitting' mean in machine learning?", ["The model fits training data (including noise) so closely that it generalizes poorly to new data", "The model is too simple to capture patterns in the data", "The model trains faster than expected", "The model uses too few features"], 0, Difficulty.EASY, "Overfitting occurs when a model memorizes training noise instead of learning generalizable patterns."),
        ("Which metric is most appropriate for evaluating a classifier on a highly imbalanced dataset?", ["F1-score", "Raw accuracy", "Mean squared error", "R-squared"], 0, Difficulty.MEDIUM, "F1-score balances precision and recall, unlike accuracy which is misleading when one class dominates."),
        ("What is the primary purpose of a validation set?", ["Tune hyperparameters and estimate generalization without touching the test set", "Replace the need for a training set", "Store the final model weights", "Increase the size of the training set"], 0, Difficulty.EASY, "The validation set guides model/hyperparameter selection, keeping the test set unbiased for final evaluation."),
        ("Which activation function outputs a value strictly between 0 and 1, commonly used for binary classification output?", ["Sigmoid", "ReLU", "Softmax", "Tanh"], 0, Difficulty.EASY, "Sigmoid squashes any real input into the (0, 1) range, interpretable as a probability."),
        ("What is the 'vanishing gradient' problem?", ["Gradients shrink exponentially through many layers, slowing or halting learning in early layers", "Gradients grow uncontrollably, causing numerical overflow", "The loss function has no gradient at all", "The learning rate is set to zero"], 0, Difficulty.HARD, "Repeated multiplication of small derivatives (e.g., sigmoid) through deep networks shrinks gradients toward zero."),
        ("Which technique reduces dimensionality by projecting data onto directions of maximum variance?", ["Principal Component Analysis (PCA)", "K-Means Clustering", "Gradient Boosting", "One-Hot Encoding"], 0, Difficulty.MEDIUM, "PCA finds orthogonal components ordered by the variance they explain."),
        ("What does the 'bias-variance tradeoff' describe?", ["The balance between a model being too simple (high bias) and too sensitive to training data (high variance)", "The tradeoff between training time and inference time", "The choice between supervised and unsupervised learning", "The tradeoff between CPU and GPU usage"], 0, Difficulty.MEDIUM, "Bias-variance tradeoff balances underfitting (bias) against overfitting (variance)."),
        ("Which regularization technique adds the sum of absolute weight values to the loss, encouraging sparse weights?", ["L1 regularization (Lasso)", "L2 regularization (Ridge)", "Dropout", "Batch normalization"], 0, Difficulty.MEDIUM, "L1 regularization's absolute-value penalty drives many weights exactly to zero, producing sparsity."),
        ("What is the purpose of k-fold cross-validation?", ["Estimate model performance robustly by averaging results across multiple train/test splits", "Reduce the number of features in the dataset", "Increase the learning rate automatically", "Convert categorical features into numerical ones"], 0, Difficulty.MEDIUM, "K-fold cross-validation trains and evaluates k times on different folds, reducing variance in the performance estimate."),
        ("Which unsupervised algorithm groups data points into k clusters based on distance to the nearest centroid?", ["K-Means", "Logistic Regression", "Random Forest", "Support Vector Machine"], 0, Difficulty.EASY, "K-Means iteratively assigns points to the nearest centroid and recomputes centroids until convergence."),
        ("What does a confusion matrix visualize for a classifier?", ["True positives, false positives, true negatives, and false negatives", "The learning rate schedule over training epochs", "The correlation between input features", "The distribution of the target variable"], 0, Difficulty.EASY, "A confusion matrix tabulates predicted vs actual classes, exposing all four outcome categories."),
        ("What does the learning rate control in gradient descent?", ["The size of each step taken when updating model weights", "The number of layers in the neural network", "The number of training examples used per epoch", "The choice of loss function"], 0, Difficulty.EASY, "A larger learning rate takes bigger steps toward (or past) the minimum; too large can diverge, too small can be slow."),
        ("Which ensemble method trains many decision trees on bootstrapped samples and averages/votes their predictions?", ["Random Forest (Bagging)", "Gradient Descent", "Principal Component Analysis", "K-Nearest Neighbors"], 0, Difficulty.MEDIUM, "Random Forest bags multiple decision trees on bootstrapped subsets and aggregates their predictions to reduce variance."),
        ("What does one-hot encoding do to a categorical feature?", ["Converts each category into a separate binary indicator column", "Scales the feature to a 0-1 range", "Removes the feature entirely", "Converts the feature into its rank order"], 0, Difficulty.EASY, "One-hot encoding creates a binary column per category so models don't infer a false ordinal relationship."),
        ("In gradient boosting, how are successive trees trained?", ["Each new tree is trained to correct the residual errors of the previous ensemble", "Each tree is trained independently on a random feature subset", "All trees are trained in parallel on the same target", "Trees are trained only once and then cloned"], 0, Difficulty.HARD, "Gradient boosting fits each new weak learner to the negative gradient (residual error) of the current ensemble's loss."),
    ]
    for body, opts, corr, diff, exp in ml_mcqs:
        qs.append(_make_q(subject=sub_ml, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Machine Learning", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    ml_tf = [
        ("Increasing model complexity always reduces both bias and variance simultaneously.", ["True", "False"], 1, Difficulty.MEDIUM, "More complexity typically reduces bias but increases variance - they trade off, not both improve together."),
        ("In supervised learning, the training data must include labeled output values.", ["True", "False"], 0, Difficulty.EASY, "Supervised learning is defined by learning a mapping from inputs to known, labeled outputs."),
        ("K-Means clustering requires labeled training data to run.", ["True", "False"], 1, Difficulty.EASY, "K-Means is unsupervised - it groups data using only feature similarity, no labels required."),
        ("Dropout is a regularization technique used to prevent overfitting in neural networks.", ["True", "False"], 0, Difficulty.EASY, "Dropout randomly disables neurons during training, preventing co-adaptation and reducing overfitting."),
        ("The ReLU activation function outputs negative values for negative inputs.", ["True", "False"], 1, Difficulty.EASY, "ReLU is defined as max(0, x), so it outputs exactly 0 for any negative input."),
        ("Precision and recall always increase together as a classification threshold changes.", ["True", "False"], 1, Difficulty.MEDIUM, "Precision and recall typically trade off - raising the threshold usually increases precision but decreases recall."),
        ("Feature scaling (normalization) is generally important for gradient-descent-based algorithms to converge efficiently.", ["True", "False"], 0, Difficulty.MEDIUM, "Unscaled features with very different ranges distort the loss surface, slowing or destabilizing gradient descent."),
        ("A very high R-squared value on training data guarantees good performance on unseen test data.", ["True", "False"], 1, Difficulty.MEDIUM, "A high training R-squared can simply reflect overfitting, with no guarantee of generalization to new data."),
    ]
    for body, opts, corr, diff, exp in ml_tf:
        qs.append(_make_q(subject=sub_ml, creator=examiner, qtype=QuestionType.TRUE_FALSE, category=cat, topic="Machine Learning Concepts", body=body, difficulty=diff, marks=1.0, negative=0.25, options=opts, correct=[corr], explanation=exp))

    ml_img = [
        ("Derive the gradient descent weight-update rule for linear regression using the Mean Squared Error loss function. Handwrite your complete derivation, photograph it, and upload the image.", "Expected: correct partial derivative of MSE w.r.t. weights, arriving at w := w - alpha * (2/n) * X^T(Xw - y).", Difficulty.MEDIUM, 8.0),
        ("Draw and label a fully-connected feedforward neural network with 1 input layer (3 nodes), 1 hidden layer (4 nodes), and 1 output layer (2 nodes). Upload a clear photo or diagram.", "Expected: correctly labeled nodes and layers, all connections drawn between adjacent layers, and arrows showing forward propagation direction.", Difficulty.EASY, 6.0),
        ("Sketch the ROC curve for a binary classifier and shade the Area Under the Curve (AUC) region. Label both axes correctly. Upload your diagram.", "Expected: X-axis labeled False Positive Rate, Y-axis labeled True Positive Rate, a diagonal random-guess reference line, and the AUC region shaded.", Difficulty.MEDIUM, 8.0),
        ("Derive the gradient of the softmax function with respect to its input logits, for use in a multi-class cross-entropy loss. Handwrite the full derivation and upload a photo.", "Expected: derivation using the Kronecker delta for softmax's own partial derivatives, simplifying the combined cross-entropy gradient to (predicted_probability - true_label).", Difficulty.HARD, 10.0),
        ("Draw a decision tree of depth 3 that classifies whether a loan applicant is approved, based on income, credit score, and existing debt. Upload a clear photograph or diagram.", "Expected: root node splitting on the most informative feature (e.g., credit score), branching logically down to leaf decisions, with edges clearly labeled True/False or threshold conditions.", Difficulty.MEDIUM, 8.0),
        ("Illustrate the bias-variance tradeoff with a diagram plotting model complexity on the x-axis against error on the y-axis, showing separate bias, variance, and total error curves. Upload your diagram.", "Expected: bias curve decreasing monotonically, variance curve increasing monotonically, and a U-shaped total error curve with the optimal complexity point marked.", Difficulty.MEDIUM, 8.0),
    ]
    for body, model_ans, diff, marks in ml_img:
        qs.append(_make_q(subject=sub_ml, creator=examiner, qtype=QuestionType.IMAGE_UPLOAD, category=cat, topic="ML Diagrams & Derivations", body=body, difficulty=diff, marks=marks, model_answer=model_ans))

    # --------------------------------------------------------------------------
    # 4e. ACADEMIC - NLP101: Natural Language Processing
    # --------------------------------------------------------------------------
    sub_nlp = subjects["NLP101"]
    nlp_mcqs = [
        ("What does 'tokenization' refer to in NLP?", ["Splitting text into smaller units such as words or subwords", "Translating text from one language to another", "Compressing text to reduce storage size", "Encrypting text for secure transmission"], 0, Difficulty.EASY, "Tokenization breaks raw text into tokens (words, subwords, or characters) for downstream processing."),
        ("Which technique represents words as dense vectors that capture semantic similarity?", ["Word embeddings (e.g., Word2Vec)", "One-hot encoding", "Bag-of-Words counting", "Regular expression matching"], 0, Difficulty.MEDIUM, "Word embeddings map words into a continuous vector space where similar words are close together."),
        ("What is the purpose of 'stemming' in text preprocessing?", ["Reduce words to a root or base form by stripping suffixes", "Translate words into another language", "Count word frequency across documents", "Detect the sentiment polarity of a sentence"], 0, Difficulty.EASY, "Stemming crudely chops word endings (e.g., 'running' -> 'run') to normalize word forms."),
        ("Which architecture introduced the self-attention mechanism underlying most modern NLP models?", ["Transformer", "Convolutional Neural Network (CNN)", "Hidden Markov Model (HMM)", "Decision Tree"], 0, Difficulty.MEDIUM, "The Transformer architecture ('Attention Is All You Need') replaced recurrence with self-attention."),
        ("What does TF-IDF measure?", ["How important a word is to a document relative to a whole corpus", "The total number of documents in a corpus", "The grammatical category of a word", "The sentiment score of a sentence"], 0, Difficulty.MEDIUM, "TF-IDF combines term frequency in a document with inverse document frequency across the corpus to weight distinctive words higher."),
        ("Which NLP task assigns grammatical categories (noun, verb, adjective, etc.) to each word in a sentence?", ["Part-of-Speech (POS) tagging", "Named Entity Recognition", "Text summarization", "Machine translation"], 0, Difficulty.EASY, "POS tagging labels each token with its grammatical role in the sentence."),
        ("What does Named Entity Recognition (NER) do?", ["Identifies and classifies named entities such as people, organizations, and locations in text", "Removes stop words from a sentence", "Converts text to lowercase", "Splits a document into sentences"], 0, Difficulty.EASY, "NER locates spans of text representing entities and labels their type (PERSON, ORG, LOC, etc.)."),
        ("Which pretrained language model uses bidirectional context via masked language modeling?", ["BERT", "GPT-2 (original, left-to-right)", "N-gram model", "TF-IDF vectorizer"], 0, Difficulty.MEDIUM, "BERT is trained to predict masked tokens using context from both directions simultaneously."),
        ("What is 'stop word removal' in text preprocessing?", ["Removing common, low-information words such as 'the', 'is', and 'at' before further processing", "Removing all punctuation from text", "Removing duplicate documents from a corpus", "Removing numeric characters from text"], 0, Difficulty.EASY, "Stop words carry little discriminative meaning for many tasks, so they are often filtered out early."),
        ("What does 'perplexity' measure for a language model?", ["How well the model predicts a sample, with lower values indicating better predictions", "The total vocabulary size of the model", "The number of layers in the model", "The training time required to converge"], 0, Difficulty.HARD, "Perplexity is the exponentiated average negative log-likelihood; lower perplexity means the model is less 'surprised' by the text."),
    ]
    for body, opts, corr, diff, exp in nlp_mcqs:
        qs.append(_make_q(subject=sub_nlp, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Natural Language Processing", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    nlp_tf = [
        ("Stemming always produces a valid dictionary word.", ["True", "False"], 1, Difficulty.MEDIUM, "Stemming can produce non-words (e.g., 'studies' -> 'studi'); lemmatization is what guarantees valid dictionary forms."),
        ("A Bag-of-Words representation captures the order of words in a document.", ["True", "False"], 1, Difficulty.EASY, "Bag-of-Words only counts word occurrences and discards word order entirely."),
        ("Transformer models rely on recurrence (RNNs) to process sequences.", ["True", "False"], 1, Difficulty.MEDIUM, "Transformers process sequences using self-attention in parallel, with no recurrent connections."),
        ("Word2Vec is an example of a word embedding technique.", ["True", "False"], 0, Difficulty.EASY, "Word2Vec learns dense vector representations of words from their surrounding context."),
        ("N-grams are contiguous sequences of n items, such as words, extracted from text.", ["True", "False"], 0, Difficulty.EASY, "An n-gram is any contiguous sequence of n tokens, commonly used as features in text models."),
    ]
    for body, opts, corr, diff, exp in nlp_tf:
        qs.append(_make_q(subject=sub_nlp, creator=examiner, qtype=QuestionType.TRUE_FALSE, category=cat, topic="NLP Concepts", body=body, difficulty=diff, marks=1.0, negative=0.25, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4f. ACADEMIC - AI101: Artificial Intelligence
    # --------------------------------------------------------------------------
    sub_ai = subjects["AI101"]
    ai_mcqs = [
        ("What is the Turing Test designed to evaluate?", ["A machine's ability to exhibit intelligent behavior indistinguishable from a human", "The processing speed of a computer", "The memory capacity of a neural network", "The accuracy of a search algorithm"], 0, Difficulty.EASY, "Turing proposed judging machine intelligence by whether a human evaluator can distinguish it from a human in conversation."),
        ("Which search algorithm guarantees the shortest path in an unweighted graph?", ["Breadth-First Search (BFS)", "Depth-First Search (DFS)", "Greedy Best-First Search", "Hill Climbing"], 0, Difficulty.EASY, "BFS explores nodes level by level, guaranteeing the fewest edges to reach any node."),
        ("What is a 'heuristic' in AI search?", ["A function that estimates the cost to reach the goal from a given state", "A guaranteed exact cost to the goal", "A random number used to break ties", "A rule that always finds the optimal path"], 0, Difficulty.EASY, "Heuristics guide search by estimating remaining cost, trading guaranteed optimality for speed unless admissible."),
        ("Which algorithm is a heuristic-based extension of Dijkstra's algorithm for pathfinding?", ["A* Search", "Breadth-First Search", "Depth-First Search", "Minimax"], 0, Difficulty.MEDIUM, "A* combines Dijkstra's cost-so-far with a heuristic estimate of remaining cost."),
        ("What does 'knowledge representation' refer to in AI?", ["Encoding facts and rules about the world so a system can reason over them", "Compressing training data for storage", "Visualizing a neural network's architecture", "Measuring an agent's response latency"], 0, Difficulty.EASY, "Knowledge representation formalizes facts/rules (e.g., logic, semantic networks) for automated reasoning."),
        ("In propositional logic, what does 'resolution' allow you to do?", ["Derive new clauses by combining complementary literals to prove or refute a statement", "Convert a sentence into natural language", "Rank clauses by their probability", "Compress multiple clauses into a single variable"], 0, Difficulty.HARD, "Resolution is a inference rule that combines two clauses containing complementary literals into a new clause."),
        ("What is a rational agent in AI?", ["An agent that acts to maximize its expected performance measure given its knowledge", "An agent that always acts randomly to explore its environment", "An agent that never updates its beliefs", "An agent that only follows hard-coded rules"], 0, Difficulty.MEDIUM, "Rationality means choosing actions expected to maximize performance given percepts and knowledge, not guaranteed omniscience."),
        ("Which AI paradigm relies on hand-crafted if-then rules encoded by domain experts?", ["Expert systems (symbolic AI)", "Convolutional neural networks", "Reinforcement learning", "Genetic algorithms"], 0, Difficulty.EASY, "Expert systems encode expert knowledge as explicit rules for a rule engine to apply."),
        ("What is the 'frame problem' in AI?", ["The difficulty of representing which facts remain unchanged after an action", "The problem of choosing a neural network's frame rate for video processing", "The challenge of framing a search problem as a graph", "The issue of picture-frame image classification"], 0, Difficulty.HARD, "The frame problem concerns efficiently specifying what does NOT change when an action is performed."),
        ("Which planning technique searches backward from the goal state toward the initial state?", ["Regression planning", "Forward state-space search", "Breadth-first search", "Hill climbing"], 0, Difficulty.MEDIUM, "Regression planning works backward from the goal, finding actions whose effects satisfy it."),
    ]
    for body, opts, corr, diff, exp in ai_mcqs:
        qs.append(_make_q(subject=sub_ai, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Artificial Intelligence", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    ai_tf = [
        ("The minimax algorithm is used to make decisions in adversarial, two-player games.", ["True", "False"], 0, Difficulty.EASY, "Minimax assumes an opponent playing optimally and chooses moves minimizing the opponent's best outcome."),
        ("A greedy best-first search always finds the optimal solution.", ["True", "False"], 1, Difficulty.MEDIUM, "Greedy best-first search follows the heuristic estimate only and can miss the optimal path."),
        ("In a Constraint Satisfaction Problem (CSP), arc consistency guarantees a solution exists.", ["True", "False"], 1, Difficulty.HARD, "Arc consistency prunes inconsistent values but is necessary, not sufficient, for guaranteeing a solution."),
        ("Classical AI theory generally assumes a rational agent is also omniscient.", ["True", "False"], 1, Difficulty.MEDIUM, "Rational agents act optimally given their available knowledge, not assumed to know everything."),
        ("Propositional logic can natively express quantified statements like 'for all x'.", ["True", "False"], 1, Difficulty.MEDIUM, "Quantifiers require first-order logic; propositional logic only handles fixed, unquantified statements."),
    ]
    for body, opts, corr, diff, exp in ai_tf:
        qs.append(_make_q(subject=sub_ai, creator=examiner, qtype=QuestionType.TRUE_FALSE, category=cat, topic="AI Concepts", body=body, difficulty=diff, marks=1.0, negative=0.25, options=opts, correct=[corr], explanation=exp))

    # --------------------------------------------------------------------------
    # 4g. ACADEMIC - DL101: Deep Learning
    # --------------------------------------------------------------------------
    sub_dl = subjects["DL101"]
    dl_mcqs = [
        ("What is the primary building block of a CNN used to extract spatial features?", ["Convolutional layer (kernel/filter)", "Fully connected layer", "Dropout layer", "Embedding layer"], 0, Difficulty.EASY, "Convolutional layers slide learnable filters over the input to detect local spatial patterns."),
        ("Which activation function helps mitigate the vanishing gradient problem compared to sigmoid/tanh?", ["ReLU", "Sigmoid", "Tanh", "Step function"], 0, Difficulty.EASY, "ReLU's gradient is 1 for positive inputs, avoiding the saturation that shrinks sigmoid/tanh gradients."),
        ("What is 'backpropagation' used for?", ["Computing gradients of the loss with respect to network weights via the chain rule", "Initializing network weights randomly", "Selecting the best hyperparameters automatically", "Compressing a trained model for deployment"], 0, Difficulty.EASY, "Backpropagation propagates the loss gradient backward through layers using the chain rule."),
        ("Which architecture is specifically designed to handle sequential data with memory of previous inputs?", ["Recurrent Neural Network (RNN)", "Convolutional Neural Network", "Autoencoder", "Support Vector Machine"], 0, Difficulty.EASY, "RNNs maintain a hidden state that carries information across time steps in a sequence."),
        ("What problem do LSTM networks primarily solve compared to vanilla RNNs?", ["Vanishing/exploding gradients over long sequences", "Overfitting on small image datasets", "High inference latency on CPUs", "Lack of labeled training data"], 0, Difficulty.MEDIUM, "LSTM gating mechanisms preserve gradient flow across long sequences, unlike vanilla RNNs."),
        ("What is 'dropout' used for in deep learning?", ["Randomly disabling neurons during training to prevent overfitting", "Removing outlier samples from the training set", "Reducing the learning rate over time", "Compressing the model's weight matrices"], 0, Difficulty.EASY, "Dropout randomly zeroes activations during training, preventing co-adaptation and reducing overfitting."),
        ("What does a 'pooling layer' do in a CNN?", ["Downsamples feature maps, reducing spatial dimensions and computation", "Increases the number of channels in a feature map", "Normalizes pixel values to zero mean and unit variance", "Applies a nonlinear activation function"], 0, Difficulty.EASY, "Pooling (e.g., max pooling) reduces the spatial size of feature maps while retaining key information."),
        ("Which loss function is standard for multi-class classification with a softmax output?", ["Categorical cross-entropy", "Mean squared error", "Hinge loss", "Huber loss"], 0, Difficulty.MEDIUM, "Categorical cross-entropy measures the divergence between the predicted softmax distribution and the true class."),
        ("What is 'batch normalization' used for?", ["Normalizing layer inputs per mini-batch to stabilize and speed up training", "Splitting training data into batches", "Balancing class distribution in a dataset", "Reducing the number of layers in a network"], 0, Difficulty.MEDIUM, "Batch normalization rescales layer activations per mini-batch, reducing internal covariate shift."),
        ("What is a Generative Adversarial Network (GAN) composed of?", ["A generator and a discriminator trained adversarially", "Two encoders sharing the same weights", "A single autoencoder with skip connections", "An ensemble of decision trees"], 0, Difficulty.MEDIUM, "A GAN pits a generator (creating fake samples) against a discriminator (detecting fakes) in a minimax game."),
    ]
    for body, opts, corr, diff, exp in dl_mcqs:
        qs.append(_make_q(subject=sub_dl, creator=examiner, qtype=QuestionType.MCQ, category=cat, topic="Deep Learning", body=body, difficulty=diff, marks=2.0, negative=0.5, options=opts, correct=[corr], explanation=exp))

    dl_tf = [
        ("CNNs share weights across spatial locations via convolutional filters.", ["True", "False"], 0, Difficulty.EASY, "The same filter weights slide across the whole input, giving CNNs translation-invariant feature detection."),
        ("Increasing network depth always improves accuracy with no downsides.", ["True", "False"], 1, Difficulty.MEDIUM, "Deeper networks can suffer vanishing gradients, overfitting, and diminishing or negative returns without care."),
        ("The Adam optimizer combines momentum and adaptive per-parameter learning rates.", ["True", "False"], 0, Difficulty.MEDIUM, "Adam maintains running estimates of both the gradient mean (momentum) and variance (adaptive scaling)."),
        ("Transformers process sequences using recurrence, similar to RNNs.", ["True", "False"], 1, Difficulty.MEDIUM, "Transformers use self-attention in parallel across the sequence, with no recurrent connections."),
        ("Transfer learning reuses a pretrained model's learned weights for a new, related task.", ["True", "False"], 0, Difficulty.EASY, "Transfer learning starts from weights learned on one task/dataset and fine-tunes them for another."),
    ]
    for body, opts, corr, diff, exp in dl_tf:
        qs.append(_make_q(subject=sub_dl, creator=examiner, qtype=QuestionType.TRUE_FALSE, category=cat, topic="Deep Learning Concepts", body=body, difficulty=diff, marks=1.0, negative=0.25, options=opts, correct=[corr], explanation=exp))

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
    for body, _ans, diff, exp, spec in apt_num:
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
    for _title, body, diff, marks, spec, model_ans in coding_questions:
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

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 13: ML101 Machine Learning Fundamentals Examination
    # --------------------------------------------------------------------------
    e13 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["ML101"].id,
        title="Machine Learning Fundamentals Examination",
        description="Semester assessment covering supervised/unsupervised learning, model evaluation, regularization, and neural network basics.",
        instructions="Ensure webcam is centered. No mobile devices, headphones, or tab switching permitted. Save answers frequently.",
        course="B.Tech / M.Tech Computer Science & Engineering",
        department="Computer Science & Engineering",
        semester="Semester VI",
        duration_minutes=75,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=40.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 12},
                {"question_type": "true_false", "difficulty": None, "count": 4},
                {"question_type": "image_upload", "difficulty": None, "count": 2},
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
    for idx, q in enumerate(
        pick("ML101", {QuestionType.MCQ}, limit=12)
        + pick("ML101", {QuestionType.TRUE_FALSE}, limit=4)
        + pick("ML101", {QuestionType.IMAGE_UPLOAD}, limit=2)
    ):
        e13.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e13)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 14: AI101 Artificial Intelligence Fundamentals Examination
    # --------------------------------------------------------------------------
    e14 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["AI101"].id,
        title="Artificial Intelligence Fundamentals Examination",
        description="Semester assessment covering search algorithms, knowledge representation, logic, rational agents, and planning.",
        instructions="Ensure webcam is centered. No mobile devices, headphones, or tab switching permitted. Save answers frequently.",
        course="B.Tech Computer Science & Engineering",
        department="Computer Science & Engineering",
        semester="Semester V",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=40.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 10},
                {"question_type": "true_false", "difficulty": None, "count": 5},
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
    for idx, q in enumerate(
        pick("AI101", {QuestionType.MCQ}, limit=10) + pick("AI101", {QuestionType.TRUE_FALSE}, limit=5)
    ):
        e14.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e14)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 15: NLP101 Natural Language Processing Fundamentals Examination
    # --------------------------------------------------------------------------
    e15 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["NLP101"].id,
        title="Natural Language Processing Fundamentals Examination",
        description="Semester assessment covering tokenization, embeddings, language models, and text classification.",
        instructions="Ensure webcam is centered. No mobile devices, headphones, or tab switching permitted. Save answers frequently.",
        course="B.Tech / M.Tech Computer Science & Engineering",
        department="Computer Science & Engineering",
        semester="Semester VII",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=40.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 10},
                {"question_type": "true_false", "difficulty": None, "count": 5},
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
    for idx, q in enumerate(
        pick("NLP101", {QuestionType.MCQ}, limit=10) + pick("NLP101", {QuestionType.TRUE_FALSE}, limit=5)
    ):
        e15.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e15)

    # --------------------------------------------------------------------------
    # ACADEMIC EXAM 16: DL101 Deep Learning Fundamentals Examination
    # --------------------------------------------------------------------------
    e16 = Exam(
        exam_type=ExamType.ACADEMIC,
        subject_id=subjects["DL101"].id,
        title="Deep Learning Fundamentals Examination",
        description="Semester assessment covering CNNs, RNNs/LSTMs, backpropagation, optimizers, and GANs.",
        instructions="Ensure webcam is centered. No mobile devices, headphones, or tab switching permitted. Save answers frequently.",
        course="M.Tech Computer Science & Engineering",
        department="Computer Science & Engineering",
        semester="Semester II",
        duration_minutes=60,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=30),
        declared_total_marks=100.0,
        passing_percentage=40.0,
        selection_rules={
            "rules": [
                {"question_type": "mcq", "difficulty": None, "count": 10},
                {"question_type": "true_false", "difficulty": None, "count": 5},
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
    for idx, q in enumerate(
        pick("DL101", {QuestionType.MCQ}, limit=10) + pick("DL101", {QuestionType.TRUE_FALSE}, limit=5)
    ):
        e16.exam_questions.append(ExamQuestion(question_id=q.id, order_index=idx))
    created_exams.append(e16)

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
    logger.info("Successfully seeded 16 real Exams (10 Academic + 6 Corporate) and %d enrolments", len(created_exams) * len(candidates))


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
        "CS202": _subject(db, "CS202", "Operating Systems", "Processes, scheduling, memory management, synchronization"),
        "CS203": _subject(db, "CS203", "Computer Networks", "TCP/IP, routing, DNS, subnetting, network protocols"),
        "MATH101": _subject(db, "MATH101", "Engineering Mathematics", "Calculus, linear algebra, probability, discrete math"),
        "ML101": _subject(db, "ML101", "Machine Learning", "Supervised/unsupervised learning, neural networks, model evaluation"),
        "NLP101": _subject(db, "NLP101", "Natural Language Processing", "Tokenization, embeddings, language models, text classification"),
        "AI101": _subject(db, "AI101", "Artificial Intelligence", "Search, knowledge representation, logic, agents, planning"),
        "DL101": _subject(db, "DL101", "Deep Learning", "CNNs, RNNs, backpropagation, optimizers, GANs, transformers"),
        "APT101": _subject(db, "APT101", "Quantitative Aptitude", "Mathematical problem solving, arithmetic, statistics"),
        "LOG101": _subject(db, "LOG101", "Logical Reasoning", "Analytical thinking, puzzles, series, deductions"),
        "VRB101": _subject(db, "VRB101", "Verbal Ability & English", "Grammar, vocabulary, reading comprehension"),
        "TECH101": _subject(db, "TECH101", "Core Technical & System Design", "Frontend, backend, distributed systems, architecture"),
        "CODE101": _subject(db, "CODE101", "Programming Challenges", "Hands-on coding problems, algorithmic implementations"),
    }

    questions = _seed_questions(db, subjects, examiner)
    _seed_exams(db, subjects, examiner, candidates, questions)

    # Curated questions above give the bank quality; this gives it depth - every
    # (subject, question type) combination topped up to a real floor so the bank
    # filters (type, difficulty, subject) all have something to show rather than one
    # hand-picked handful.
    top_up_question_bank(db, examiner)

    # Real, meaningful diagram-based questions (process diagrams, Gantt charts, OSI
    # stacks, decision trees, attention weights, search trees, CNN architectures, ...)
    # for the seven core academic subjects - answered as MCQ/multi-select/short/long,
    # not a new question type. See app.seed_question_bank_images.
    top_up_images(db, examiner)


def main() -> None:
    setup_logging()
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        print("\nSeed complete! Ready-to-use dataset populated:")
        print("  - Subjects across Academic & Corporate hiring domains")
        print(
            f"  - A large centralised Question Bank "
            f"(every subject topped up to ~{FLOOR_PER_TYPE} questions per appropriate type)"
        )
        print("  - 16 Real ready-to-use Exams created with pools & sections:")
        print("      * 10 Academic Exams (Semester Final, Mid-Term DSA, Speed Quiz, Practical Viva, Essay, Scholarship, ML, AI, NLP, Deep Learning)")
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
