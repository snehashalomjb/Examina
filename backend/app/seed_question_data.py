"""Subject-specific concept cards for the question-bank fixture seed.

The six cards in each subject are ordered easy, easy, medium, medium, hard,
hard. ``seed_question_catalog`` expands them into 18 questions per subject.
"""

from __future__ import annotations

from app.db.models import QuestionCategory as Q

from .seed_question_catalog import fact as F
from .seed_question_catalog import subject


def S(code, name, description, category, *concepts, create_if_missing=True):
    return subject(
        code,
        name,
        description,
        category,
        concepts,
        create_if_missing=create_if_missing,
    )


SUBJECTS = (
    S(
        "PY101", "Python", "Python fundamentals, data types, functions, OOP, I/O, and concurrency.", Q.TECHNICAL,
        F("Data Types", "immutable string", "A str value cannot be changed by assigning through an index.", "Slicing a str creates a new string value.", "Immutable values are safer to share because callers cannot alter their internal state."),
        F("Control Flow", "range stop value", "range excludes its stop value.", "A negative step can be used to traverse a range backwards.", "Off-by-one errors often come from treating range like an inclusive endpoint."),
        F("Functions", "mutable default argument", "A mutable default object is evaluated once when a function is defined.", "Using None as a sentinel lets a function create a fresh object per call.", "Mutable defaults can leak state between otherwise independent calls."),
        F("Object-Oriented Programming", "__init__ method", "__init__ initialises a newly constructed instance.", "self refers to the instance on which the method is called.", "Initialisation logic belongs in the object so every instance starts consistently."),
        F("Decorators", "closure", "A closure retains access to variables in its enclosing function's scope.", "A decorator commonly returns a wrapper that extends the original callable.", "Closures let wrappers carry configuration without exposing global mutable state."),
        F("AsyncIO", "await expression", "await suspends a coroutine until an awaited operation is ready.", "create_task schedules a coroutine as an independent asyncio task.", "Non-blocking suspension is what allows one event loop to serve many connections."),
    ),
    S(
        "CS101", "Computer Science Fundamentals", "Core computing, algorithms, architecture, memory, operating systems, and theory.", Q.TECHNICAL,
        F("Number Systems", "binary bit", "A bit represents one of two values: 0 or 1.", "Binary notation is base 2 and uses positional place values.", "Binary encoding underlies storage, networking, and digital logic."),
        F("Algorithms", "algorithm termination", "An algorithm must halt for every valid finite input under its stated rules.", "An algorithm is more precise than a program, which is one concrete implementation.", "Termination guarantees make algorithmic analysis meaningful."),
        F("Computer Architecture", "instruction set architecture", "An instruction set architecture defines the programming interface between software and a processor.", "An ISA specifies instructions, registers, and execution semantics.", "An ISA lets software and hardware evolve while preserving compatibility."),
        F("Compilers", "compiler", "A compiler translates source code into another program representation, often machine code.", "A compiler can optimise a whole program before execution.", "Compilation makes systematic optimisation possible."),
        F("Complexity", "Big-O notation", "Big-O notation bounds resource growth as input size increases.", "Big-O discards constant factors and lower-order growth terms.", "Asymptotic analysis supports comparisons that remain meaningful as inputs grow."),
        F("Concurrency", "race condition", "A race condition occurs when correctness depends on uncontrolled ordering of concurrent operations.", "Proper synchronisation can prevent data races in shared state.", "Concurrency reasoning is essential for reliable parallel programs."),
    ),
    S(
        "CS102", "Data Structures & Algorithms", "Linear and non-linear structures, graph traversal, and algorithm analysis.", Q.TECHNICAL,
        F("Arrays", "array indexing", "Array indexing at a valid position is constant time because positions are addressable.", "A contiguous array stores elements next to one another in memory.", "Direct addressing makes arrays efficient for repeated indexed access."),
        F("Linked Lists", "linked-list traversal", "Following a singly linked list from its head to a node can take linear time.", "A linked-list node stores data and a reference to its next node.", "Pointer chasing makes linked lists less cache-friendly than contiguous arrays."),
        F("Stacks", "LIFO stack", "A stack removes the most recently pushed item first.", "A stack can be implemented with an array or a linked list.", "LIFO behaviour models nested calls, undo history, and backtracking."),
        F("Trees", "binary search tree", "A binary search tree orders keys so smaller keys follow one child and larger keys the other.", "A tree can be traversed in preorder, inorder, or postorder.", "The ordering invariant supports logarithmic search on balanced trees."),
        F("Hash Tables", "hash-table lookup", "A hash table provides average constant-time lookup by key.", "Collisions require a collision-resolution strategy such as chaining or probing.", "Hashing trades ordering for fast key-based access."),
        F("Graphs", "breadth-first search", "BFS explores vertices in increasing distance from a start vertex in an unweighted graph.", "A queue is the usual worklist for BFS.", "BFS therefore finds a shortest unweighted path when one exists."),
    ),
    S(
        "CS201", "Database Management Systems", "Relational design, SQL joins, transactions, indexing, and normalisation.", Q.TECHNICAL,
        F("Keys", "primary key", "A primary key uniquely identifies each relation row and rejects null key values.", "A composite primary key can use several columns together.", "Primary keys give rows stable identities for references and updates."),
        F("Keys", "foreign key", "A foreign key constrains referenced values to exist or explicitly be null under its rule.", "A foreign key can reference a candidate key or suitable unique key.", "Referential integrity protects consistency across related relations."),
        F("Normalisation", "third normal form", "Third normal form removes transitive dependencies of non-key attributes on candidate keys.", "A relation in 2NF has no partial dependency on a composite candidate key.", "Normalisation reduces update anomalies by making facts depend on the right key."),
        F("Joins", "inner join", "An inner join returns only row pairs whose join condition matches.", "LEFT JOIN preserves every row from the left relation.", "Join choice controls whether unmatched records are preserved or discarded."),
        F("Transactions", "atomicity", "Atomicity guarantees that all operations of a transaction commit or all are rolled back.", "Durability guarantees that committed changes survive failures.", "ACID properties protect correctness during failures and concurrent access."),
        F("Performance", "B-tree index", "A B-tree index maintains ordered keys and supports equality and range lookups.", "A hash index can provide efficient exact-key lookup when ordering is unnecessary.", "Index structure should match the query patterns it serves."),
    ),
    S(
        "CS202", "Operating Systems", "Processes, threads, scheduling, synchronisation, memory, and file systems.", Q.TECHNICAL,
        F("Processes", "process versus thread", "Threads in one process share an address space, while processes have separate address spaces.", "A process is an executing program instance with its own resources.", "The distinction determines isolation and communication costs."),
        F("Scheduling", "preemptive scheduling", "Preemptive scheduling can pause a running process so another process receives the CPU.", "A time slice is one common reason for a preemption.", "Preemption improves responsiveness but introduces synchronisation concerns."),
        F("Synchronisation", "mutex", "A mutex allows only one holder to enter a critical section at a time.", "A semaphore can represent multiple available permits.", "Correct locking protects shared invariants without unnecessarily serialising work."),
        F("Deadlocks", "deadlock", "A deadlock is a set of blocked processes that each wait for an event only another can provide.", "Breaking one wait-for edge is a standard way to recover from deadlock.", "Deadlock analysis exposes circular dependencies in resource protocols."),
        F("Virtual Memory", "page fault", "A page fault occurs when a referenced virtual page is not resident in physical memory.", "The operating system can satisfy a fault by loading the page from secondary storage.", "Demand paging lets a process use an address space larger than resident memory."),
        F("File Systems", "file descriptor", "A file descriptor is an integer handle through which a process references an open file.", "Opening a file creates a descriptor that can be used for subsequent reads and writes.", "Descriptor-based interfaces let the kernel manage shared open-file state."),
    ),
    S(
        "CS203", "Computer Networks", "Layered networking, TCP/IP, addressing, routing, DNS, and congestion control.", Q.TECHNICAL,
        F("Layered Networking", "OSI layer responsibility", "The network layer routes packets between networks, while the transport layer provides end-to-end process delivery.", "Each layer serves the layer above through a defined service.", "Layering localises protocol changes and clarifies troubleshooting."),
        F("Transport", "TCP handshake", "TCP establishes a connection with a SYN, SYN-ACK, and ACK exchange.", "TCP provides reliable ordered delivery over an unreliable packet network.", "The handshake negotiates connection state before application data flows."),
        F("IP Addressing", "CIDR prefix", "A CIDR prefix states how many leading bits of an address form its network portion.", "A longer prefix describes a smaller network.", "Prefix length determines routing aggregation and subnet boundaries."),
        F("DNS", "DNS resolver", "A DNS resolver translates a domain name into address records for a client.", "DNS responses can be cached until their time-to-live expires.", "Caching reduces lookup latency but requires careful expiry handling."),
        F("Routing", "longest-prefix match", "A router forwards a packet using the most specific matching destination prefix.", "A default route is used when no more-specific route matches.", "Longest-prefix matching supports both aggregate and specific routes."),
        F("Congestion Control", "TCP congestion window", "TCP limits in-flight data with a congestion window that reflects observed network congestion.", "Packet loss and delay signals can cause the window to shrink.", "Feedback-based control adapts sending rate without overwhelming the network."),
    ),
    S(
        "CS301", "Web & Software Engineering", "HTTP, REST, browser behaviour, security, delivery, and maintainable web design.", Q.TECHNICAL,
        F("HTTP", "safe HTTP method", "GET is a safe HTTP method because reading a resource should not change server state.", "HEAD requests metadata without returning the full representation.", "Using the correct method makes caching and safety expectations explicit."),
        F("REST", "stateless request", "A stateless REST request carries the information needed to interpret it without relying on hidden server conversation state.", "Resources are commonly addressed by stable URLs.", "Statelessness improves horizontal scaling and retry behaviour."),
        F("Browser Security", "CORS", "CORS controls whether browser JavaScript from one origin may read a response from another origin.", "CORS is enforced by browsers rather than by the server-side database.", "Explicit cross-origin policy prevents unintended data sharing."),
        F("DOM", "event bubbling", "A DOM event can bubble from a target through its ancestors.", "Event delegation can handle many descendants with one listener.", "Understanding propagation helps design predictable interactive components."),
        F("CSS", "box model", "The CSS box model separates content, padding, border, and margin.", "box-sizing changes whether padding and border are included in a declared width.", "The box model explains most spacing and sizing surprises in layouts."),
        F("Web Security", "XSS", "Cross-site scripting executes attacker-controlled script in a victim's browser context.", "Context-aware output encoding is one defence against HTML-context XSS.", "Treating text as data rather than markup is a core web-security principle."),
    ),
    S(
        "MATH101", "Engineering Mathematics", "Calculus, algebra, linear algebra, probability, and discrete mathematics.", Q.APTITUDE,
        F("Calculus", "power rule", "The derivative of x^n with respect to x is n times x raised to n minus one.", "A constant differentiates to zero.", "The power rule makes many polynomial derivatives routine."),
        F("Calculus", "fundamental theorem", "The fundamental theorem of calculus connects differentiation and integration through accumulation.", "An antiderivative's derivative recovers the original function on an interval.", "The theorem links local rates of change to accumulated quantities."),
        F("Linear Algebra", "determinant", "A square matrix is invertible exactly when its determinant is nonzero.", "The determinant changes sign when two rows are swapped.", "Determinants encode both invertibility and oriented volume scaling."),
        F("Linear Algebra", "eigenvalue", "An eigenvector of a square matrix is a nonzero vector unchanged up to scalar multiplication by the matrix.", "An eigenvalue is the scalar associated with an eigenvector.", "Eigenstructure exposes invariant directions in a linear transformation."),
        F("Probability", "complementary probability", "The complement of event A contains every outcome outside A.", "For an exhaustive sample space, P(A) plus P(not A) equals one.", "Complements simplify counting and probability calculations."),
        F("Probability", "conditional probability", "Conditional probability restricts a sample space to the event that is known to have occurred.", "P(A given B) is not generally equal to P(B given A).", "Conditioning changes the information set and therefore the relevant denominator."),
    ),
    S(
        "SQL101", "SQL & Databases", "SQL querying, joins, aggregation, transactions, indexing, and database design.", Q.TECHNICAL,
        F("Selection", "WHERE clause", "WHERE filters rows before grouped aggregation in a SELECT query.", "ORDER BY controls output order and does not filter rows.", "Predicate placement changes which rows participate in later clauses."),
        F("Aggregation", "HAVING clause", "HAVING filters groups produced by GROUP BY.", "COUNT with a grouped column can summarise rows sharing that column value.", "HAVING is the correct filter for aggregate results rather than individual rows."),
        F("Joins", "LEFT JOIN", "LEFT JOIN preserves every row from the left relation and adds matching right-side values.", "An inner join can remove left rows with no match.", "Outer joins make missing relationships explicit instead of silently dropping them."),
        F("Subqueries", "common table expression", "A common table expression names a query result so another statement can reference it.", "Recursive CTEs can traverse hierarchical data.", "Named intermediate results can make complex SQL easier to read and test."),
        F("Window Functions", "window function", "A window function computes across a set of rows related to the current row without collapsing the result into groups.", "ROW_NUMBER can assign an ordering within each partition.", "Window functions preserve row-level detail while adding analytical context."),
        F("Transactions", "transaction isolation", "Transaction isolation controls which uncommitted or concurrent changes a transaction can observe.", "Stronger isolation can reduce anomalies at the cost of concurrency.", "The chosen isolation level is part of an application's correctness design."),
    ),
)
