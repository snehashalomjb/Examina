"""Seed 150+ SQL questions into the question bank for the SQL101 subject.

Covers:
- SELECT, WHERE, ORDER BY, LIMIT
- GROUP BY, HAVING, aggregate functions
- JOINs (INNER, LEFT, RIGHT, FULL, CROSS, SELF)
- Subqueries (correlated & non-correlated)
- Window functions (ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, PARTITION BY)
- DDL (CREATE, ALTER, DROP, TRUNCATE)
- DML (INSERT, UPDATE, DELETE, MERGE/UPSERT)
- Constraints (PRIMARY KEY, FOREIGN KEY, UNIQUE, NOT NULL, CHECK, DEFAULT)
- Indexes, Views, Stored Procedures, Triggers, Transactions, CTEs
- Normalisation (1NF, 2NF, 3NF, BCNF)
- ACID properties, Isolation levels
- Set operations (UNION, INTERSECT, EXCEPT)
- String, numeric, date functions
- Query optimisation, execution plans, NULL handling

Question types: MCQ (single choice), MULTI_SELECT, TRUE_FALSE, SHORT_ANSWER, LONG_ANSWER
Idempotent: checks existing count tagged with SEED_TAG before inserting.
"""

from __future__ import annotations

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

logger = get_logger("seed_sql")

SEED_TAG = "sql-seed-v1"
SQL101_CODE = "SQL101"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(
    *,
    subject: Subject,
    creator: User,
    qtype: QuestionType,
    topic: str,
    body: str,
    difficulty: Difficulty,
    marks: float,
    negative: float = 0.0,
    options: list[tuple[str, bool]] | None = None,
    model_answer: str | None = None,
    explanation: str | None = None,
    rubric: dict | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
) -> Question:
    q = Question(
        subject_id=subject.id,
        question_type=qtype,
        category=QuestionCategory.TECHNICAL,
        topic=topic,
        difficulty=difficulty,
        body=body,
        model_answer=model_answer,
        explanation=explanation,
        marks=marks,
        negative_marks=negative,
        rubric=rubric,
        min_words=min_words,
        max_words=max_words,
        created_by_id=creator.id,
        tags=[SEED_TAG, "sql101", topic.lower().replace(" ", "-")],
        status=QuestionStatus.PUBLISHED,
        is_active=True,
    )
    for idx, (text, correct) in enumerate(options or []):
        q.options.append(QuestionOption(text=text, is_correct=correct, order_index=idx))
    return q


MCQ = QuestionType.MCQ
MSEL = QuestionType.MULTI_SELECT
TF = QuestionType.TRUE_FALSE
SA = QuestionType.SHORT_ANSWER
LA = QuestionType.LONG_ANSWER
E = Difficulty.EASY
M = Difficulty.MEDIUM
H = Difficulty.HARD


# ---------------------------------------------------------------------------
# MCQ - Single Choice (60 questions)
# ---------------------------------------------------------------------------

_MCQ_DATA: list[tuple[str, list[tuple[str, bool]], Difficulty, str, str]] = [
    # (body, options [(text, is_correct)], difficulty, topic, explanation)

    # --- Basic SELECT ---
    (
        "Which SQL clause is used to filter rows AFTER aggregation?",
        [("HAVING", True), ("WHERE", False), ("GROUP BY", False), ("FILTER", False)],
        E, "Aggregation & Grouping",
        "WHERE filters rows before aggregation; HAVING filters groups after GROUP BY.",
    ),
    (
        "Which keyword removes duplicate rows from a SELECT result?",
        [("DISTINCT", True), ("UNIQUE", False), ("NODUPE", False), ("FILTER", False)],
        E, "Basic SELECT",
        "DISTINCT eliminates duplicate rows in the result set.",
    ),
    (
        "What does SELECT * FROM employees LIMIT 5 return?",
        [("The first 5 rows", True), ("The last 5 rows", False), ("5 random rows", False), ("5 rows ordered by primary key", False)],
        E, "Basic SELECT",
        "LIMIT 5 returns the first 5 rows of the result in the default storage order.",
    ),
    (
        "Which SQL clause specifies the table(s) to query?",
        [("FROM", True), ("SELECT", False), ("WHERE", False), ("TABLE", False)],
        E, "Basic SELECT",
        "The FROM clause identifies the source table(s) for the query.",
    ),
    (
        "What is the correct order of SQL clauses in a SELECT statement?",
        [("SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY", True),
         ("FROM, SELECT, WHERE, GROUP BY, HAVING, ORDER BY", False),
         ("SELECT, WHERE, FROM, GROUP BY, ORDER BY, HAVING", False),
         ("SELECT, FROM, HAVING, WHERE, GROUP BY, ORDER BY", False)],
        M, "Basic SELECT",
        "The logical order of a SELECT query is: SELECT, FROM, WHERE, GROUP BY, HAVING, ORDER BY.",
    ),
    (
        "Which clause controls the order of output rows in a SELECT query?",
        [("ORDER BY", True), ("SORT BY", False), ("GROUP BY", False), ("ARRANGE BY", False)],
        E, "Basic SELECT",
        "ORDER BY sorts the result set; ASC is the default direction.",
    ),
    (
        "Which SQL keyword is used to give a column or table a temporary name in a query?",
        [("AS (alias)", True), ("RENAME", False), ("LABEL", False), ("NAME", False)],
        E, "Basic SELECT",
        "AS provides an alias -- e.g., SELECT salary * 12 AS annual_salary FROM employees.",
    ),
    (
        "What does BETWEEN do in SQL?",
        [("Filters rows where a column value is within an inclusive range", True),
         ("Filters rows exclusive of boundary values", False),
         ("Joins two tables based on a range condition", False),
         ("Computes the difference between two values", False)],
        E, "Basic SELECT",
        "BETWEEN a AND b is equivalent to col >= a AND col <= b (inclusive of both boundaries).",
    ),
    (
        "Which SQL operator tests whether a value matches any value in a list?",
        [("IN", True), ("ANY", False), ("LIKE", False), ("BETWEEN", False)],
        E, "Basic SELECT",
        "IN checks whether a value matches any value in the specified list.",
    ),
    (
        "What does the LIKE operator with pattern '%sql%' match?",
        [("Any string containing 'sql' anywhere", True),
         ("Strings that start with 'sql'", False),
         ("Strings that end with 'sql'", False),
         ("Strings that are exactly 'sql'", False)],
        E, "Basic SELECT",
        "The % wildcard matches zero or more characters; '%sql%' matches any string containing 'sql'.",
    ),

    # --- JOINs ---
    (
        "Which JOIN returns all rows from the left table and matching rows from the right table, with NULLs for non-matches?",
        [("LEFT JOIN", True), ("INNER JOIN", False), ("RIGHT JOIN", False), ("FULL OUTER JOIN", False)],
        E, "JOINs",
        "LEFT JOIN returns every row from the left table; NULL fills columns of the right table when no match exists.",
    ),
    (
        "Which type of JOIN produces a Cartesian product of both tables?",
        [("CROSS JOIN", True), ("FULL OUTER JOIN", False), ("NATURAL JOIN", False), ("SELF JOIN", False)],
        E, "JOINs",
        "CROSS JOIN returns every combination of rows from both tables -- the Cartesian product.",
    ),
    (
        "A SELF JOIN is a join of a table with itself.",
        [("True -- a table joined to itself using aliases", True),
         ("False -- it joins two related tables", False),
         ("False -- it joins a table to a view", False),
         ("True -- but only for tables with foreign keys", False)],
        M, "JOINs",
        "A SELF JOIN joins a table to itself, typically using different aliases to distinguish the two copies.",
    ),
    (
        "Which JOIN returns only rows where there is a match in BOTH tables?",
        [("INNER JOIN", True), ("LEFT JOIN", False), ("RIGHT JOIN", False), ("FULL OUTER JOIN", False)],
        E, "JOINs",
        "INNER JOIN returns only rows where the join condition is satisfied in both tables.",
    ),
    (
        "How many rows does a CROSS JOIN of a 3-row table and a 4-row table produce?",
        [("12", True), ("7", False), ("1", False), ("Depends on the ON clause", False)],
        M, "JOINs",
        "CROSS JOIN produces 3 x 4 = 12 rows -- the Cartesian product.",
    ),

    # --- Subqueries ---
    (
        "A correlated subquery is one that references a column from the outer query.",
        [("True -- it is re-evaluated for each outer row", True),
         ("False -- it is independent of the outer query", False),
         ("False -- it uses GROUP BY internally", False),
         ("True -- but only in the HAVING clause", False)],
        M, "Subqueries",
        "A correlated subquery references a column from the outer query and is re-evaluated for each outer row.",
    ),
    (
        "Which keyword is used to check whether a subquery returns any rows?",
        [("EXISTS", True), ("ANY", False), ("IN", False), ("SOME", False)],
        E, "Subqueries",
        "EXISTS returns TRUE if the subquery returns at least one row.",
    ),
    (
        "What does NOT IN return when the subquery result contains a NULL value?",
        [("No rows (empty result set)", True), ("All rows", False), ("An error", False), ("Only non-NULL matching rows", False)],
        H, "Subqueries",
        "If the subquery contains NULL, NOT IN comparisons with NULL are UNKNOWN, so no rows satisfy the condition.",
    ),
    (
        "A scalar subquery must return exactly how many rows and columns?",
        [("Exactly one row and one column", True),
         ("One or more rows and one column", False),
         ("One row and multiple columns", False),
         ("Any number of rows", False)],
        M, "Subqueries",
        "A scalar subquery must return exactly one row and one column; otherwise the database raises an error.",
    ),

    # --- Aggregate Functions ---
    (
        "Which aggregate function counts rows including NULL values?",
        [("COUNT(*)", True), ("COUNT(column)", False), ("SUM(column)", False), ("AVG(column)", False)],
        E, "Aggregate Functions",
        "COUNT(*) counts all rows including those with NULLs; COUNT(column) ignores NULLs.",
    ),
    (
        "AVG(salary) ignores rows where salary IS NULL.",
        [("True", True), ("False -- it treats NULL as 0", False), ("False -- it raises an error", False), ("False -- it counts NULL rows in the denominator", False)],
        E, "Aggregate Functions",
        "Aggregate functions (SUM, AVG, MIN, MAX, COUNT(col)) all ignore NULL values.",
    ),
    (
        "Which function returns the number of DISTINCT non-NULL values in a column?",
        [("COUNT(DISTINCT column)", True), ("DISTINCT COUNT(column)", False), ("COUNT(*)", False), ("UNIQUE COUNT(column)", False)],
        M, "Aggregate Functions",
        "COUNT(DISTINCT column) counts unique non-NULL values in the specified column.",
    ),

    # --- Window Functions ---
    (
        "Which window function assigns a unique sequential integer to each row within a partition with no gaps or ties?",
        [("ROW_NUMBER()", True), ("RANK()", False), ("DENSE_RANK()", False), ("NTILE()", False)],
        M, "Window Functions",
        "ROW_NUMBER() assigns a unique integer (1, 2, 3...) with no gaps or ties.",
    ),
    (
        "What is the key difference between RANK() and DENSE_RANK()?",
        [("RANK() leaves gaps after ties; DENSE_RANK() does not", True),
         ("DENSE_RANK() leaves gaps after ties; RANK() does not", False),
         ("They are identical", False),
         ("RANK() uses PARTITION BY; DENSE_RANK() does not", False)],
        M, "Window Functions",
        "RANK() skips the next rank number after a tie (e.g., 1,1,3); DENSE_RANK() never skips (e.g., 1,1,2).",
    ),
    (
        "The OVER() clause in a window function specifies the window frame -- how rows are partitioned and ordered.",
        [("True", True), ("False -- OVER() specifies a filter", False), ("False -- OVER() defines an aggregation", False), ("False -- OVER() defines a subquery", False)],
        M, "Window Functions",
        "OVER(PARTITION BY ... ORDER BY ...) defines the window of rows the function sees.",
    ),
    (
        "Which window function returns the value of a column from the PREVIOUS row in the partition?",
        [("LAG()", True), ("LEAD()", False), ("FIRST_VALUE()", False), ("PREV()", False)],
        M, "Window Functions",
        "LAG(col, 1) returns the value of col from one row before the current row in the partition.",
    ),
    (
        "NTILE(4) divides the result set into 4 roughly equal buckets numbered 1 through 4.",
        [("True", True), ("False -- it returns 4 rows per bucket", False), ("False -- it uses 0-based numbering", False), ("False -- it requires an explicit partition", False)],
        H, "Window Functions",
        "NTILE(n) distributes rows into n buckets as evenly as possible and assigns each row a bucket number 1..n.",
    ),

    # --- DDL ---
    (
        "Which SQL command removes a table and ALL its data permanently?",
        [("DROP TABLE", True), ("DELETE FROM", False), ("TRUNCATE TABLE", False), ("REMOVE TABLE", False)],
        E, "DDL",
        "DROP TABLE removes the table definition and all its data. TRUNCATE removes only data. DELETE removes rows conditionally.",
    ),
    (
        "Which DDL command is used to add a new column to an existing table?",
        [("ALTER TABLE ... ADD COLUMN", True),
         ("UPDATE TABLE ... ADD COLUMN", False),
         ("CREATE COLUMN", False),
         ("INSERT COLUMN", False)],
        E, "DDL",
        "ALTER TABLE tablename ADD COLUMN colname datatype; adds a new column to an existing table.",
    ),
    (
        "TRUNCATE TABLE differs from DELETE in that TRUNCATE cannot be filtered with WHERE and is often non-transactional.",
        [("True", True), ("False -- TRUNCATE supports WHERE", False), ("False -- TRUNCATE fires row-level triggers", False), ("False -- DELETE is faster than TRUNCATE", False)],
        M, "DDL",
        "TRUNCATE is a DDL operation that quickly removes all rows, resets identity counters, and cannot be filtered.",
    ),

    # --- Constraints ---
    (
        "Which constraint ensures no two rows in a column have the same value?",
        [("UNIQUE", True), ("NOT NULL", False), ("PRIMARY KEY", False), ("CHECK", False)],
        E, "Constraints",
        "UNIQUE constraint ensures all values in the column (or column set) are distinct across rows.",
    ),
    (
        "A FOREIGN KEY constraint enforces referential integrity between tables.",
        [("True", True), ("False -- it enforces uniqueness", False), ("False -- it prevents NULLs", False), ("False -- it speeds up JOINs", False)],
        E, "Constraints",
        "A FOREIGN KEY ensures every value in the referencing column exists as a PRIMARY KEY in the referenced table.",
    ),
    (
        "A table can have how many PRIMARY KEY constraints?",
        [("Exactly one", True), ("As many as needed", False), ("Up to two", False), ("One per column", False)],
        E, "Constraints",
        "A table has exactly one PRIMARY KEY, though it can span multiple columns (composite key).",
    ),
    (
        "What does the CHECK constraint do?",
        [("Validates that column values satisfy a boolean expression", True),
         ("Checks referential integrity", False),
         ("Ensures column uniqueness", False),
         ("Prevents NULL values", False)],
        M, "Constraints",
        "CHECK (expr) accepts only rows where the expression evaluates to TRUE.",
    ),

    # --- Indexes ---
    (
        "Which type of index physically sorts the table rows to match the index order?",
        [("Clustered index", True), ("Non-clustered index", False), ("Bitmap index", False), ("Hash index", False)],
        M, "Indexes",
        "A clustered index determines the physical storage order of the table; a table can have only one.",
    ),
    (
        "Indexes speed up SELECT queries but can slow down INSERT, UPDATE, and DELETE operations.",
        [("True", True), ("False -- indexes speed up all operations", False), ("False -- indexes only affect SELECT", False), ("False -- the impact on writes is negligible", False)],
        M, "Indexes",
        "Every write operation must also update all indexes on the table, adding overhead.",
    ),
    (
        "A composite index on (A, B) can be used efficiently for queries filtering on column A alone.",
        [("True -- the leftmost-prefix rule applies", True),
         ("False -- only queries on both A and B benefit", False),
         ("False -- composite indexes are for aggregation only", False),
         ("True -- but only when B is also selected", False)],
        H, "Indexes",
        "Composite indexes follow the leftmost-prefix rule; queries on A alone can use this index.",
    ),

    # --- Views ---
    (
        "A database VIEW stores a saved query definition, not the actual data.",
        [("True", True), ("False -- a view always stores data", False), ("False -- a view stores an index", False), ("False -- a view is the same as a table", False)],
        E, "Views",
        "A view is a virtual table defined by a SELECT statement; no data is stored unless it is a materialized view.",
    ),
    (
        "A view is updatable when it is a simple, single-table view without DISTINCT, aggregates, or GROUP BY.",
        [("True", True), ("False -- all views are updatable", False), ("False -- no views are updatable", False), ("True -- but only in Oracle", False)],
        H, "Views",
        "SQL standard restricts view updates to simple, single-table views free of aggregation, DISTINCT, or GROUP BY.",
    ),

    # --- Transactions & ACID ---
    (
        "Which ACID property ensures that once a transaction is committed, it remains committed even after a system failure?",
        [("Durability", True), ("Atomicity", False), ("Consistency", False), ("Isolation", False)],
        E, "Transactions & ACID",
        "Durability guarantees that committed data is persisted to durable storage.",
    ),
    (
        "Which isolation level prevents dirty reads, non-repeatable reads, AND phantom reads?",
        [("SERIALIZABLE", True), ("READ COMMITTED", False), ("REPEATABLE READ", False), ("READ UNCOMMITTED", False)],
        M, "Transactions & ACID",
        "SERIALIZABLE is the strictest level; it prevents all three anomalies at the cost of the highest locking overhead.",
    ),
    (
        "A dirty read occurs when a transaction reads uncommitted data written by another transaction.",
        [("True", True), ("False -- a dirty read is reading committed data", False), ("False -- a dirty read involves phantom rows", False), ("True -- but only in READ COMMITTED", False)],
        M, "Transactions & ACID",
        "A dirty read means reading data that has not yet been committed and may be rolled back.",
    ),
    (
        "SAVEPOINT is used in transactions to mark a point to which partial rollback is possible.",
        [("True", True), ("False -- SAVEPOINT permanently commits changes", False), ("False -- SAVEPOINT creates a table backup", False), ("True -- but only in PostgreSQL", False)],
        M, "Transactions & ACID",
        "SAVEPOINT lets you roll back to a specific point without rolling back the entire transaction.",
    ),

    # --- Normalisation ---
    (
        "A table is in First Normal Form (1NF) if all columns contain atomic values and there are no repeating groups.",
        [("True", True), ("False -- 1NF only requires a primary key", False), ("False -- 1NF requires no transitive dependencies", False), ("True -- and also no transitive dependencies", False)],
        M, "Normalisation",
        "1NF requires atomic column values, a primary key, and no repeating groups.",
    ),
    (
        "Which normal form eliminates partial dependencies on a composite primary key?",
        [("Second Normal Form (2NF)", True), ("Third Normal Form (3NF)", False), ("BCNF", False), ("1NF", False)],
        M, "Normalisation",
        "2NF eliminates partial dependencies -- non-key columns must depend on the WHOLE primary key.",
    ),
    (
        "Boyce-Codd Normal Form (BCNF) requires that every determinant must be a candidate key.",
        [("True", True), ("False -- BCNF only requires 3NF", False), ("False -- BCNF eliminates multi-valued dependencies", False), ("True -- but only when overlapping candidate keys exist", False)],
        H, "Normalisation",
        "BCNF requires that for every functional dependency X->Y, X is a superkey.",
    ),

    # --- Set Operations ---
    (
        "Which set operation returns rows that appear in the first query but NOT in the second?",
        [("EXCEPT (or MINUS)", True), ("INTERSECT", False), ("UNION", False), ("DIFFERENCE", False)],
        E, "Set Operations",
        "EXCEPT (MINUS in Oracle) returns rows from the first query that are absent from the second.",
    ),
    (
        "UNION ALL retains duplicate rows whereas UNION removes them.",
        [("True", True), ("False -- both remove duplicates", False), ("False -- UNION ALL requires ORDER BY", False), ("False -- UNION is faster than UNION ALL", False)],
        E, "Set Operations",
        "UNION removes duplicates; UNION ALL keeps all rows including duplicates and is faster.",
    ),
    (
        "For UNION to work, the two SELECT statements must have the same number of columns with compatible data types.",
        [("True", True), ("False -- they can have different column counts", False), ("False -- only data types must match", False), ("True -- and they must reference the same table", False)],
        E, "Set Operations",
        "UNION requires the same column count and compatible data types in each corresponding column.",
    ),

    # --- SQL Functions ---
    (
        "What does COALESCE(NULL, NULL, 5, 10) return?",
        [("5", True), ("NULL", False), ("10", False), ("Error", False)],
        E, "SQL Functions",
        "COALESCE returns the first non-NULL argument, which is 5 here.",
    ),
    (
        "What does NULL = NULL evaluate to in SQL?",
        [("NULL (UNKNOWN), not TRUE", True), ("TRUE", False), ("FALSE", False), ("Error", False)],
        M, "NULL Handling",
        "Any comparison with NULL yields UNKNOWN (NULL), not TRUE or FALSE. Use IS NULL to test for nullability.",
    ),
    (
        "Which operator correctly tests whether a column value is NULL?",
        [("IS NULL", True), ("= NULL", False), ("== NULL", False), ("EQUALS NULL", False)],
        E, "NULL Handling",
        "IS NULL is the correct SQL syntax; = NULL never evaluates to TRUE.",
    ),

    # --- CTEs ---
    (
        "What does CTE stand for in SQL?",
        [("Common Table Expression", True), ("Computed Table Entity", False), ("Conditional Table Expression", False), ("Correlated Table Expansion", False)],
        E, "CTEs",
        "CTE stands for Common Table Expression, defined using the WITH keyword.",
    ),
    (
        "A recursive CTE allows a query to reference itself to traverse hierarchical data.",
        [("True", True), ("False -- CTEs cannot be recursive", False), ("False -- recursive CTEs are only in Oracle", False), ("True -- but only for parent-child tables", False)],
        M, "CTEs",
        "A recursive CTE has a base case and a recursive member that references the CTE itself.",
    ),

    # --- Query Optimisation ---
    (
        "What does an EXPLAIN (or EXPLAIN PLAN) statement show?",
        [("The query execution plan chosen by the optimizer", True),
         ("The query result with timing info", False),
         ("All indexes on the referenced tables", False),
         ("The estimated row count for the table", False)],
        M, "Query Optimisation",
        "EXPLAIN reveals how the database plans to execute the query -- useful for diagnosing slow queries.",
    ),
    (
        "An index seek is generally preferred over a full table scan when the query is highly selective.",
        [("True", True), ("False -- full scans are always faster", False), ("False -- index seeks are only for primary keys", False), ("True -- but only when the table has more than 1000 rows", False)],
        H, "Query Optimisation",
        "Index seeks are advantageous for highly selective queries; for low selectivity, a full scan may be faster.",
    ),

    # --- Stored Procedures & Triggers ---
    (
        "A stored procedure in SQL is a precompiled set of SQL statements stored in the database and executed by name.",
        [("True", True), ("False -- a stored procedure is a view", False), ("False -- a stored procedure is a constraint", False), ("True -- but only callable externally", False)],
        E, "Stored Procedures & Triggers",
        "Stored procedures encapsulate logic in the database; they can accept parameters and be called by name.",
    ),
    (
        "A BEFORE INSERT trigger fires before the new row is written to the table.",
        [("True", True), ("False -- BEFORE triggers fire after the operation", False), ("False -- triggers only fire on UPDATE", False), ("True -- but only in MySQL", False)],
        M, "Stored Procedures & Triggers",
        "BEFORE triggers fire prior to the DML operation, allowing you to modify or validate the data first.",
    ),
]


# ---------------------------------------------------------------------------
# Multi-Select (20 questions)
# ---------------------------------------------------------------------------

_MSEL_DATA: list[tuple[str, list[tuple[str, bool]], Difficulty, str, str]] = [
    (
        "Which of the following are aggregate functions in SQL? (Select all that apply)",
        [("SUM()", True), ("COUNT()", True), ("AVG()", True), ("CONCAT()", False), ("MAX()", True)],
        E, "Aggregate Functions",
        "SUM, COUNT, AVG, MIN, MAX are aggregate functions. CONCAT is a string function.",
    ),
    (
        "Which join types can return rows where the other table has no match? (Select all that apply)",
        [("LEFT JOIN", True), ("RIGHT JOIN", True), ("FULL OUTER JOIN", True), ("INNER JOIN", False), ("CROSS JOIN", False)],
        M, "JOINs",
        "LEFT, RIGHT, and FULL OUTER JOINs can produce NULL-padded rows when one side has no match.",
    ),
    (
        "Which of the following are valid SQL constraints? (Select all that apply)",
        [("PRIMARY KEY", True), ("FOREIGN KEY", True), ("UNIQUE", True), ("CHECK", True), ("PARTIAL", False)],
        E, "Constraints",
        "PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK, NOT NULL, and DEFAULT are standard SQL constraints.",
    ),
    (
        "Which SQL set operations remove duplicate rows by default? (Select all that apply)",
        [("UNION", True), ("INTERSECT", True), ("EXCEPT", True), ("UNION ALL", False)],
        M, "Set Operations",
        "UNION, INTERSECT, and EXCEPT remove duplicates. UNION ALL retains them.",
    ),
    (
        "Which of these isolation levels prevent dirty reads? (Select all that apply)",
        [("READ COMMITTED", True), ("REPEATABLE READ", True), ("SERIALIZABLE", True), ("READ UNCOMMITTED", False)],
        M, "Transactions & ACID",
        "READ UNCOMMITTED allows dirty reads. READ COMMITTED, REPEATABLE READ, and SERIALIZABLE prevent them.",
    ),
    (
        "Which statements about NULL in SQL are TRUE? (Select all that apply)",
        [("NULL = NULL evaluates to UNKNOWN", True),
         ("NULL <> NULL evaluates to UNKNOWN", True),
         ("COUNT(*) includes NULL rows", True),
         ("AVG() includes NULL values in its denominator", False)],
        H, "NULL Handling",
        "NULL comparisons yield UNKNOWN. COUNT(*) counts nulls; AVG ignores NULLs in both numerator and denominator.",
    ),
    (
        "Which of the following can appear in a SELECT clause? (Select all that apply)",
        [("Column names", True), ("Aggregate functions", True), ("Window functions", True), ("Subqueries", True), ("HAVING expressions", False)],
        M, "Basic SELECT",
        "SELECT can contain columns, expressions, aggregates, window functions, and scalar subqueries.",
    ),
    (
        "Which DDL commands auto-commit the transaction in most databases? (Select all that apply)",
        [("CREATE TABLE", True), ("DROP TABLE", True), ("TRUNCATE TABLE", True), ("DELETE", False), ("INSERT", False)],
        M, "DDL",
        "DDL statements (CREATE, DROP, TRUNCATE, ALTER) implicitly commit in most RDBMS; DML does not.",
    ),
    (
        "Which normal forms must hold before a relation can be said to be in BCNF? (Select all that apply)",
        [("1NF", True), ("2NF", True), ("3NF", True), ("4NF", False)],
        H, "Normalisation",
        "BCNF implies 3NF, which implies 2NF, which implies 1NF -- all must hold.",
    ),
    (
        "Which of the following window functions require an ORDER BY inside OVER()? (Select all that apply)",
        [("RANK()", True), ("DENSE_RANK()", True), ("ROW_NUMBER()", True), ("SUM() used as plain aggregate", False)],
        M, "Window Functions",
        "Ranking functions (RANK, DENSE_RANK, ROW_NUMBER) require ORDER BY in the OVER clause.",
    ),
    (
        "Which clauses can appear inside a subquery? (Select all that apply)",
        [("SELECT", True), ("FROM", True), ("WHERE", True), ("ORDER BY", True), ("HAVING", True)],
        M, "Subqueries",
        "A subquery is a full SELECT statement and can contain all standard SELECT clauses.",
    ),
    (
        "Which statements about indexes are TRUE? (Select all that apply)",
        [("A table can have multiple non-clustered indexes", True),
         ("Indexes consume additional disk space", True),
         ("Indexes can slow down write operations", True),
         ("A table can have multiple clustered indexes", False)],
        M, "Indexes",
        "Multiple non-clustered indexes are allowed; only one clustered index per table is permitted.",
    ),
    (
        "Which of the following are ACID properties? (Select all that apply)",
        [("Atomicity", True), ("Consistency", True), ("Isolation", True), ("Durability", True), ("Availability", False)],
        E, "Transactions & ACID",
        "ACID stands for Atomicity, Consistency, Isolation, Durability. Availability is a CAP theorem concept.",
    ),
    (
        "Which SQL commands are classified as DML (Data Manipulation Language)? (Select all that apply)",
        [("INSERT", True), ("UPDATE", True), ("DELETE", True), ("SELECT", True), ("CREATE", False)],
        E, "DDL",
        "DML includes INSERT, UPDATE, DELETE, and SELECT. CREATE, DROP, ALTER are DDL.",
    ),
    (
        "Which of the following can be used to avoid SQL injection? (Select all that apply)",
        [("Parameterized queries / prepared statements", True),
         ("Input validation and sanitization", True),
         ("Stored procedures with parameters", True),
         ("Dynamic string concatenation of user input", False)],
        M, "Security",
        "Parameterized queries, input validation, and stored procedures with parameters mitigate SQL injection.",
    ),
    (
        "Which string functions are commonly available in SQL? (Select all that apply)",
        [("UPPER()", True), ("LOWER()", True), ("TRIM()", True), ("SUBSTRING()", True), ("SORT()", False)],
        E, "SQL Functions",
        "UPPER, LOWER, TRIM, SUBSTRING, CONCAT, LENGTH are standard SQL string functions.",
    ),
    (
        "Which of the following are advantages of using Views? (Select all that apply)",
        [("Simplify complex queries", True),
         ("Provide an abstraction layer over base tables", True),
         ("Restrict access to sensitive columns", True),
         ("Always improve query performance", False)],
        M, "Views",
        "Views simplify queries and can restrict access, but they do not always improve performance.",
    ),
    (
        "Which of the following statements about CTEs are TRUE? (Select all that apply)",
        [("CTEs improve readability of complex queries", True),
         ("A CTE can be referenced multiple times in the same query", True),
         ("Recursive CTEs can model hierarchical data", True),
         ("CTEs are always faster than equivalent subqueries", False)],
        M, "CTEs",
        "CTEs improve readability and support recursion. Performance vs subqueries depends on the database optimizer.",
    ),
    (
        "Which of the following are valid ways to handle NULL in comparisons? (Select all that apply)",
        [("IS NULL", True), ("IS NOT NULL", True), ("COALESCE(col, default)", True), ("= NULL", False)],
        E, "NULL Handling",
        "IS NULL, IS NOT NULL, COALESCE, NULLIF, and IFNULL are proper NULL-handling tools.",
    ),
    (
        "Which transaction commands are used to control transactions in SQL? (Select all that apply)",
        [("COMMIT", True), ("ROLLBACK", True), ("SAVEPOINT", True), ("BEGIN / START TRANSACTION", True), ("SYNC", False)],
        M, "Transactions & ACID",
        "COMMIT, ROLLBACK, SAVEPOINT, and BEGIN/START TRANSACTION are the standard transaction control commands.",
    ),
]


# ---------------------------------------------------------------------------
# True / False (30 questions)
# ---------------------------------------------------------------------------

_TF_DATA: list[tuple[str, bool, Difficulty, str, str]] = [
    # (body, is_true, difficulty, topic, explanation)
    ("An INNER JOIN returns all rows from both tables, including unmatched rows.", False, E, "JOINs", "INNER JOIN returns only matched rows; FULL OUTER JOIN returns all rows."),
    ("NULL values are ignored by aggregate functions like SUM and AVG.", True, E, "Aggregate Functions", "Aggregate functions skip NULL values in their calculations."),
    ("A primary key column can contain NULL values.", False, E, "Constraints", "PRIMARY KEY implies NOT NULL and UNIQUE; NULL is not allowed."),
    ("TRUNCATE TABLE can be rolled back in all SQL databases.", False, M, "DDL", "In most databases (e.g., MySQL, SQL Server), TRUNCATE is auto-committed and cannot be rolled back."),
    ("A view always stores a physical copy of the data.", False, E, "Views", "A standard view is a virtual table (stored query only); a MATERIALIZED view stores data."),
    ("SELECT DISTINCT eliminates duplicate rows from the result set.", True, E, "Basic SELECT", "DISTINCT filters duplicate rows."),
    ("The WHERE clause can reference column aliases defined in the SELECT clause.", False, M, "Basic SELECT", "WHERE is evaluated before SELECT, so aliases defined in SELECT are not yet available."),
    ("HAVING filters rows before they are grouped by GROUP BY.", False, M, "Aggregation & Grouping", "HAVING filters groups AFTER GROUP BY; WHERE filters rows BEFORE grouping."),
    ("COUNT(*) and COUNT(column_name) always return the same value.", False, E, "Aggregate Functions", "COUNT(*) includes NULL rows; COUNT(col) excludes NULL values."),
    ("A foreign key column can contain NULL values.", True, M, "Constraints", "Foreign key columns can be NULL (meaning the relationship is optional), unless explicitly constrained NOT NULL."),
    ("RANK() assigns consecutive integers with no gaps even when there are ties.", False, M, "Window Functions", "RANK() skips numbers after ties (e.g., 1,1,3). DENSE_RANK() has no gaps (1,1,2)."),
    ("EXISTS returns TRUE if the subquery returns at least one row.", True, E, "Subqueries", "EXISTS checks for the presence of any row in the subquery result."),
    ("UNION ALL is faster than UNION because it skips the duplicate elimination step.", True, M, "Set Operations", "UNION requires sorting and deduplication; UNION ALL simply concatenates the result sets."),
    ("A clustered index physically reorders the table data.", True, M, "Indexes", "A clustered index determines the physical storage order of the rows."),
    ("READ UNCOMMITTED isolation level allows dirty reads.", True, M, "Transactions & ACID", "READ UNCOMMITTED is the loosest level and permits dirty reads."),
    ("SERIALIZABLE isolation level completely prevents phantom reads.", True, H, "Transactions & ACID", "SERIALIZABLE prevents dirty reads, non-repeatable reads, and phantom reads."),
    ("A table in 3NF is always also in BCNF.", False, H, "Normalisation", "3NF and BCNF differ when a non-key attribute determines another non-key attribute; BCNF is stricter."),
    ("COALESCE(a, b) returns the first non-NULL argument.", True, E, "SQL Functions", "COALESCE returns the first argument that is not NULL."),
    ("Indexes always speed up every type of query.", False, M, "Indexes", "Indexes help range/equality lookups but add overhead for writes and may be skipped for low-selectivity queries."),
    ("A correlated subquery is evaluated once for the entire outer query.", False, H, "Subqueries", "A correlated subquery is re-evaluated once per row of the outer query."),
    ("The ON clause in a JOIN specifies the join condition.", True, E, "JOINs", "ON defines the predicate that must be true for rows from both tables to be combined."),
    ("LAG() returns the value of a column from the next row in the partition.", False, M, "Window Functions", "LAG() looks at the previous row; LEAD() looks at the next row."),
    ("A composite primary key is made up of two or more columns.", True, E, "Constraints", "Composite (compound) primary keys use multiple columns to uniquely identify each row."),
    ("INTERSECT returns all rows that appear in EITHER query result.", False, M, "Set Operations", "INTERSECT returns only rows that appear in BOTH query results. UNION returns rows from either."),
    ("The EXPLAIN keyword shows the actual rows returned by a query.", False, M, "Query Optimisation", "EXPLAIN shows the query PLAN; use EXPLAIN ANALYZE for actual execution stats."),
    ("A stored procedure can accept input parameters.", True, E, "Stored Procedures & Triggers", "Stored procedures support input, output, and input/output parameters."),
    ("In SQL, string comparison is always case-sensitive regardless of the database.", False, M, "SQL Functions", "Case sensitivity depends on the database and collation setting."),
    ("A trigger can be set to fire BEFORE or AFTER a DML operation.", True, E, "Stored Procedures & Triggers", "SQL supports BEFORE and AFTER triggers for INSERT, UPDATE, and DELETE events."),
    ("BETWEEN is inclusive of both boundary values.", True, E, "Basic SELECT", "col BETWEEN a AND b is equivalent to col >= a AND col <= b."),
    ("An index on a column with very low cardinality (e.g., a boolean flag) is almost always beneficial.", False, H, "Query Optimisation", "Low-cardinality indexes are often ignored by the optimizer because a full scan is cheaper."),
]


# ---------------------------------------------------------------------------
# Short Answer (20 questions)
# ---------------------------------------------------------------------------

_SA_DATA: list[tuple[str, Difficulty, str, str, str]] = [
    # (body, difficulty, topic, model_answer, rubric_scheme)
    (
        "Explain the difference between WHERE and HAVING in SQL.",
        E, "Aggregation & Grouping",
        "WHERE filters individual rows before grouping; HAVING filters groups produced by GROUP BY after aggregation.",
        "2 marks for mentioning WHERE filters rows before aggregation; 2 marks for HAVING filters groups after aggregation.",
    ),
    (
        "What is a primary key and what constraints does it enforce?",
        E, "Constraints",
        "A primary key uniquely identifies each row in a table. It enforces NOT NULL and UNIQUE -- no two rows can share the same primary key value, and the column cannot be NULL.",
        "2 marks for uniqueness; 2 marks for NOT NULL; note: only one per table.",
    ),
    (
        "In one or two sentences, explain what a LEFT JOIN does.",
        E, "JOINs",
        "A LEFT JOIN returns all rows from the left table and the matching rows from the right table. When no match is found in the right table, NULL values are filled in for the right table's columns.",
        "2 marks for 'all rows from left table'; 2 marks for 'NULL for no match on right'.",
    ),
    (
        "What is a foreign key and why is it important?",
        E, "Constraints",
        "A foreign key is a column (or set of columns) in one table that references the primary key of another table. It enforces referential integrity -- ensuring no orphaned records exist.",
        "2 marks for definition; 2 marks for referential integrity.",
    ),
    (
        "Describe what ACID properties mean for database transactions.",
        M, "Transactions & ACID",
        "ACID stands for Atomicity (all-or-nothing), Consistency (valid state before and after), Isolation (transactions do not interfere), and Durability (committed data persists through failures).",
        "1 mark per ACID property correctly defined (4 total).",
    ),
    (
        "What is the difference between UNION and UNION ALL?",
        E, "Set Operations",
        "UNION combines two result sets and removes duplicate rows. UNION ALL combines them without removing duplicates, making it faster.",
        "2 marks for duplicate removal by UNION; 2 marks for UNION ALL keeping duplicates and being faster.",
    ),
    (
        "Explain what a window function is and how PARTITION BY works.",
        M, "Window Functions",
        "A window function performs a calculation across a set of rows related to the current row without collapsing them into a single output row. PARTITION BY divides the rows into groups (windows); the function is applied independently within each partition.",
        "2 marks for 'no row collapse'; 2 marks for PARTITION BY explanation.",
    ),
    (
        "What is a CTE (Common Table Expression) and how is it defined?",
        M, "CTEs",
        "A CTE is a temporary named result set defined within a WITH clause that can be referenced in the following SELECT, INSERT, UPDATE, or DELETE statement. Example: WITH cte AS (SELECT ...) SELECT * FROM cte;",
        "2 marks for WITH clause definition; 2 marks for temporary/scoped nature.",
    ),
    (
        "Explain what normalisation is and why it is performed.",
        M, "Normalisation",
        "Normalisation is the process of organising a relational database to reduce data redundancy and avoid update anomalies. It applies a series of rules (normal forms) that progressively decompose tables to eliminate partial and transitive dependencies.",
        "2 marks for reducing redundancy; 2 marks for avoiding anomalies.",
    ),
    (
        "What is the difference between RANK() and DENSE_RANK()?",
        M, "Window Functions",
        "RANK() assigns the same rank to tied rows but skips the next rank values (e.g., 1, 1, 3). DENSE_RANK() also assigns the same rank to ties but never skips ranks (e.g., 1, 1, 2).",
        "2 marks for ties treated equally by both; 2 marks for the gap distinction.",
    ),
    (
        "What does the COALESCE function do? Give an example.",
        E, "SQL Functions",
        "COALESCE(expr1, expr2, ...) returns the first non-NULL expression. Example: COALESCE(phone, mobile, 'N/A') returns phone if not NULL, otherwise mobile, otherwise 'N/A'.",
        "2 marks for first non-NULL description; 2 marks for a correct example.",
    ),
    (
        "Explain what an index is and the trade-off of adding one.",
        M, "Indexes",
        "An index is a data structure (typically a B-tree) that speeds up data retrieval for queries. The trade-off is that indexes require extra storage and must be maintained on every INSERT, UPDATE, or DELETE, adding write overhead.",
        "2 marks for speed-up; 2 marks for write overhead/storage cost.",
    ),
    (
        "What is a correlated subquery? How does it differ from a non-correlated subquery?",
        H, "Subqueries",
        "A correlated subquery references a column from the outer query and is re-executed for every row of the outer query. A non-correlated subquery is independent of the outer query and is executed once.",
        "2 marks for outer query reference; 2 marks for per-row execution vs once.",
    ),
    (
        "What is a SQL trigger? Name one common use case.",
        M, "Stored Procedures & Triggers",
        "A trigger is a stored procedure that runs automatically in response to INSERT, UPDATE, or DELETE events on a table. A common use case is maintaining an audit log of all changes to sensitive data.",
        "2 marks for automatic execution; 2 marks for a valid use case.",
    ),
    (
        "Explain the difference between a clustered and a non-clustered index.",
        M, "Indexes",
        "A clustered index physically reorders the table rows to match the index order; only one is allowed per table. A non-clustered index creates a separate structure pointing to the data rows; multiple can exist per table.",
        "2 marks for physical order distinction; 2 marks for one vs many restriction.",
    ),
    (
        "What does SELECT DISTINCT do? When would you use it?",
        E, "Basic SELECT",
        "SELECT DISTINCT removes duplicate rows from the result set. Use it when you want unique values -- for example, listing all unique departments in an employee table.",
        "2 marks for duplicate removal; 2 marks for a valid use case.",
    ),
    (
        "What is Second Normal Form (2NF)?",
        M, "Normalisation",
        "A table is in 2NF if it is in 1NF and every non-key attribute is fully functionally dependent on the whole primary key (no partial dependency). This applies only when the primary key is composite.",
        "2 marks for 1NF prerequisite; 2 marks for no partial dependency.",
    ),
    (
        "What is a transaction savepoint?",
        M, "Transactions & ACID",
        "A SAVEPOINT marks a point within a transaction to which you can partially roll back without aborting the entire transaction. Syntax: SAVEPOINT sp1; ... ROLLBACK TO SAVEPOINT sp1;",
        "2 marks for partial rollback capability; 2 marks for syntax or context.",
    ),
    (
        "What is the difference between DELETE and TRUNCATE?",
        M, "DDL",
        "DELETE removes rows one at a time, fires row-level triggers, supports a WHERE clause, and can be rolled back. TRUNCATE removes all rows at once, does not fire row-level triggers, cannot be filtered, and is often non-transactional.",
        "2 marks for WHERE clause/selective deletion; 2 marks for trigger and rollback differences.",
    ),
    (
        "Explain what an SQL VIEW is and how it differs from a table.",
        E, "Views",
        "A view is a named, stored SELECT statement that acts like a virtual table. Unlike a base table, a view does not store data itself (unless materialized). It provides an abstraction layer and can simplify complex queries.",
        "2 marks for virtual/no stored data; 2 marks for abstraction/simplification purpose.",
    ),
]


# ---------------------------------------------------------------------------
# Long Answer (20 questions)
# ---------------------------------------------------------------------------

_LA_DATA: list[tuple[str, Difficulty, str, str, str]] = [
    # (body, difficulty, topic, model_answer_summary, rubric_scheme)
    (
        "Compare INNER JOIN, LEFT JOIN, RIGHT JOIN, and FULL OUTER JOIN. Explain each with an example and describe when you would choose one over another.",
        M, "JOINs",
        "INNER JOIN: only matched rows. LEFT JOIN: all left rows, NULLs for unmatched right. RIGHT JOIN: mirror of LEFT. FULL OUTER JOIN: all rows from both, NULLs where no match. Use LEFT JOIN when you need all records from the primary table regardless of a match.",
        "2-3 marks each for accurate description + example (8 marks); 2 marks for use-case justification.",
    ),
    (
        "Explain the four ACID properties of database transactions with examples of what could go wrong without each.",
        M, "Transactions & ACID",
        "Atomicity: all or nothing -- without it a bank transfer could debit without crediting. Consistency: valid states -- without it constraints could be violated. Isolation: no interference -- without it dirty reads or lost updates occur. Durability: committed data survives crashes.",
        "2-3 marks per ACID property with correct example (capped at 10).",
    ),
    (
        "Discuss the process of database normalisation up to BCNF. Use a concrete example to illustrate each normal form.",
        H, "Normalisation",
        "1NF: atomic values, no repeating groups. 2NF: eliminate partial dependencies on composite PK. 3NF: eliminate transitive dependencies. BCNF: every determinant is a candidate key. Example: unnormalised order table split into Customers, Products, Orders, OrderItems.",
        "2-3 marks per normal form with example; 1 mark for BCNF distinction from 3NF.",
    ),
    (
        "Explain window functions in SQL. Compare ROW_NUMBER(), RANK(), DENSE_RANK(), LAG(), and LEAD() with examples.",
        M, "Window Functions",
        "Window functions compute over a set of rows without collapsing them. ROW_NUMBER: unique integers, no ties. RANK: ties same rank, gaps follow. DENSE_RANK: ties same rank, no gaps. LAG: previous row value. LEAD: next row value.",
        "2 marks per function with example (10 marks).",
    ),
    (
        "What are indexes in SQL? Discuss clustered vs non-clustered indexes, how they work internally, and when to use each.",
        M, "Indexes",
        "Index: B-tree data structure speeding up lookups at cost of storage and write overhead. Clustered: physically sorts data rows; one per table. Non-clustered: separate structure with pointers; multiple per table. Use clustered for range queries; non-clustered for point lookups and composite queries.",
        "3 marks clustered; 3 marks non-clustered; 2 marks internal B-tree; 2 marks when to use.",
    ),
    (
        "Explain transaction isolation levels in SQL (READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ, SERIALIZABLE). Describe the anomalies each prevents.",
        H, "Transactions & ACID",
        "READ UNCOMMITTED: dirty reads possible. READ COMMITTED: prevents dirty reads. REPEATABLE READ: prevents dirty + non-repeatable reads. SERIALIZABLE: prevents all anomalies including phantom reads. Higher isolation reduces concurrency.",
        "2 marks per level + anomaly prevented; 2 marks for trade-off discussion.",
    ),
    (
        "Discuss SQL subqueries: correlated vs non-correlated, scalar subqueries, and IN vs EXISTS. When would you choose EXISTS over IN?",
        H, "Subqueries",
        "Non-correlated: executed once. Correlated: executed per outer row -- slower but necessary for row-dependent logic. Scalar subquery: returns exactly one value. Prefer EXISTS when checking large subquery results or when NULLs in the list could cause issues with NOT IN.",
        "2 marks correlated; 2 marks non-correlated; 2 marks scalar; 2 marks IN vs EXISTS with NULL caveat; 2 marks performance note.",
    ),
    (
        "Explain what Common Table Expressions (CTEs) are in SQL, including recursive CTEs. Provide an example of using a recursive CTE to traverse a hierarchy.",
        M, "CTEs",
        "CTE: WITH name AS (SELECT...) -- temporary named result for the rest of the query. Benefits: readability, no repeated subqueries, enables recursion. Recursive CTE: base case UNION ALL recursive member referencing itself. Example: employee-manager hierarchy traversal.",
        "2 marks CTE definition; 2 marks benefits; 3 marks recursive structure; 3 marks valid example.",
    ),
    (
        "Describe SQL triggers: what they are, when they fire (BEFORE vs AFTER, row-level vs statement-level), and provide a practical use case with sample syntax.",
        M, "Stored Procedures & Triggers",
        "Trigger: automatic stored procedure on DML events. BEFORE fires before the operation (validation/modification); AFTER fires after. Row-level: once per affected row. Statement-level: once per statement. Use case: audit log on UPDATE of salary.",
        "2 marks definition; 2 marks BEFORE/AFTER distinction; 2 marks row vs statement; 4 marks use case + syntax.",
    ),
    (
        "Compare DELETE, TRUNCATE, and DROP in SQL. Discuss their differences in terms of performance, transaction rollback, triggers, and use cases.",
        M, "DDL",
        "DELETE: row-by-row removal, WHERE supported, fires triggers, transactional. TRUNCATE: fast bulk removal of all rows, no WHERE, no row triggers, often non-transactional, resets identity. DROP: removes table definition plus data. Use DELETE for selective removal; TRUNCATE for resetting; DROP for schema changes.",
        "3 marks DELETE; 3 marks TRUNCATE; 2 marks DROP; 2 marks use-case guidance.",
    ),
    (
        "Explain SQL views: standard views vs materialized views, updateability constraints, and security use cases.",
        M, "Views",
        "Standard view: stored SELECT query, no data stored, always reflects current base table data. Materialized view: stores a snapshot, needs refresh, faster for expensive queries. Updateability: simple single-table views without DISTINCT/GROUP BY/aggregates can be updatable. Security: expose only permitted columns.",
        "3 marks standard view; 3 marks materialized view; 2 marks updateability; 2 marks security use case.",
    ),
    (
        "Discuss SQL set operations: UNION, UNION ALL, INTERSECT, and EXCEPT. Explain their behavior with NULLs and performance considerations.",
        M, "Set Operations",
        "UNION: deduplicates (NULLs treated as equal). UNION ALL: concatenates without deduplication -- faster. INTERSECT: rows in both sets. EXCEPT/MINUS: rows in first but not second. Performance: UNION ALL cheapest; UNION, INTERSECT, EXCEPT require sort/hash for deduplication.",
        "2 marks per operator with NULL behavior; 2 marks performance discussion.",
    ),
    (
        "Describe SQL query optimisation strategies. What role does EXPLAIN play and how do you interpret a full table scan vs an index seek?",
        H, "Query Optimisation",
        "EXPLAIN shows the query execution plan: tables accessed, join order, index usage. Full table scan: all rows read -- fast only when selectivity is low. Index seek: B-tree traversal -- fast for high-selectivity queries. Strategies: add selective indexes, rewrite correlated subqueries as JOINs, avoid functions on indexed columns in WHERE, use covering indexes.",
        "2 marks EXPLAIN interpretation; 3 marks full scan vs index seek; 5 marks optimisation strategies.",
    ),
    (
        "Explain how NULL is handled in SQL. Cover NULL in comparisons, aggregate functions, JOINs, and the use of IS NULL, COALESCE, and NULLIF.",
        M, "NULL Handling",
        "NULL is UNKNOWN -- any comparison with NULL returns UNKNOWN. Aggregates (SUM, AVG, MIN, MAX) ignore NULLs; COUNT(*) includes them. JOINs: NULL columns do not match any value so NULL-FK rows are excluded from INNER JOIN. IS NULL/IS NOT NULL: correct test. COALESCE: first non-NULL value. NULLIF: returns NULL if two values are equal.",
        "2 marks comparisons; 2 marks aggregates; 2 marks JOINs; 2 marks IS NULL; 2 marks COALESCE/NULLIF.",
    ),
    (
        "What is SQL injection? How do parameterized queries prevent it? Discuss with an example of a vulnerable and a safe query.",
        M, "Security",
        "SQL injection: attacker inserts malicious SQL through unvalidated user input. Vulnerable: SELECT * FROM users WHERE name = '' + input + ''; -- input like ' OR 1=1 bypasses auth. Parameterized query: SELECT * FROM users WHERE name = ?; value bound separately. Also: stored procedures with parameters, input validation, least-privilege DB users.",
        "2 marks definition + example; 4 marks vulnerable vs safe query; 2 marks parameterized explanation; 2 marks additional defenses.",
    ),
    (
        "Explain stored procedures in SQL: what they are, their advantages over ad-hoc queries, how parameters work, and potential drawbacks.",
        M, "Stored Procedures & Triggers",
        "Stored procedure: precompiled SQL block stored in the database, callable by name. Advantages: precompilation (execution plan cached), reduced network round trips, encapsulation, reusability, security. Parameters: IN (input), OUT (output), INOUT. Drawbacks: harder to version-control, logic buried in DB, not portable across RDBMS.",
        "2 marks definition; 3 marks advantages; 2 marks parameters; 3 marks drawbacks.",
    ),
    (
        "Describe the GROUP BY clause in SQL. How does it interact with SELECT, HAVING, and aggregate functions? Give an example.",
        E, "Aggregation & Grouping",
        "GROUP BY groups rows sharing the same value(s). In SELECT, only GROUP BY columns and aggregate expressions are allowed. HAVING filters groups after aggregation. Example: SELECT department, COUNT(*), AVG(salary) FROM employees GROUP BY department HAVING COUNT(*) > 5;",
        "2 marks GROUP BY mechanics; 2 marks SELECT restriction; 2 marks HAVING; 4 marks example.",
    ),
    (
        "Compare correlated and non-correlated subqueries in terms of execution, performance, and when to use each. Rewrite a correlated subquery as a JOIN.",
        H, "Subqueries",
        "Non-correlated: executes once, efficient. Correlated: references outer query column, re-executes per outer row -- can be O(n^2). Rewrite: SELECT e.name FROM employees e WHERE salary > (SELECT AVG(salary) FROM employees WHERE department = e.department) can become a JOIN with an aggregated inline view.",
        "3 marks correlated vs non-correlated; 3 marks performance; 4 marks correct rewrite.",
    ),
    (
        "Explain the MERGE (UPSERT) statement in SQL. What problem does it solve and how does it work?",
        H, "DDL",
        "MERGE combines INSERT, UPDATE, and DELETE in a single statement against a target using a source. Solves insert-or-update without separate queries and race conditions. Syntax: MERGE target USING source ON condition WHEN MATCHED THEN UPDATE ... WHEN NOT MATCHED THEN INSERT ... Use cases: data warehouse loads, synchronising staging to production.",
        "3 marks problem statement; 3 marks syntax and mechanics; 4 marks use case examples.",
    ),
    (
        "Discuss SQL string functions commonly used in data cleaning and transformation. Include TRIM, UPPER/LOWER, SUBSTRING, REPLACE, and CONCAT with examples.",
        E, "SQL Functions",
        "TRIM: removes leading/trailing whitespace. UPPER/LOWER: case conversion. SUBSTRING: extracts part of a string. REPLACE: substitutes occurrences. CONCAT: joins strings. Each function is illustrated with a concrete example.",
        "2 marks per function with correct example (10 marks).",
    ),
]


# ---------------------------------------------------------------------------
# Public seeder entry point
# ---------------------------------------------------------------------------

def seed_sql_questions(db: Session, examiner: User) -> int:
    """Insert 150 SQL questions into the SQL101 subject.

    Idempotent: checks whether any questions with SEED_TAG already exist for
    SQL101 and skips if the bank already has enough.
    """
    # Resolve the SQL101 subject
    sql_subject = db.scalar(select(Subject).where(Subject.code == SQL101_CODE))
    if sql_subject is None:
        logger.warning("SQL101 subject not found -- creating it now.")
        sql_subject = Subject(
            code=SQL101_CODE,
            name="SQL & Databases",
            description="Structured Query Language: DDL, DML, joins, aggregations, window functions, normalisation, transactions.",
        )
        db.add(sql_subject)
        db.flush()

    # Check idempotency
    existing = (
        db.scalar(
            select(func.count(Question.id)).where(
                Question.subject_id == sql_subject.id,
                Question.tags.contains([SEED_TAG]),  # type: ignore[arg-type]
            )
        )
        or 0
    )
    target = len(_MCQ_DATA) + len(_MSEL_DATA) + len(_TF_DATA) + len(_SA_DATA) + len(_LA_DATA)

    if existing >= target:
        logger.info("SQL questions already seeded (%d / %d found) -- skipping.", existing, target)
        return 0

    questions: list[Question] = []

    # MCQ
    for body, opts, diff, topic, explanation in _MCQ_DATA:
        questions.append(_q(
            subject=sql_subject, creator=examiner, qtype=MCQ,
            topic=topic, body=body, difficulty=diff, marks=2.0, negative=0.5,
            options=opts, explanation=explanation,
        ))

    # Multi-Select
    for body, opts, diff, topic, explanation in _MSEL_DATA:
        questions.append(_q(
            subject=sql_subject, creator=examiner, qtype=MSEL,
            topic=topic, body=body, difficulty=diff, marks=3.0, negative=1.0,
            options=opts, explanation=explanation,
        ))

    # True / False
    for body, is_true, diff, topic, explanation in _TF_DATA:
        questions.append(_q(
            subject=sql_subject, creator=examiner, qtype=TF,
            topic=topic, body=body, difficulty=diff, marks=1.0, negative=0.25,
            options=[("True", is_true), ("False", not is_true)],
            explanation=explanation,
        ))

    # Short Answer
    for body, diff, topic, model_ans, scheme in _SA_DATA:
        questions.append(_q(
            subject=sql_subject, creator=examiner, qtype=SA,
            topic=topic, body=body, difficulty=diff, marks=4.0,
            model_answer=model_ans,
            min_words=20, max_words=100,
            rubric={"key_points": [model_ans[:80]], "scheme": scheme},
        ))

    # Long Answer
    for body, diff, topic, model_ans, scheme in _LA_DATA:
        questions.append(_q(
            subject=sql_subject, creator=examiner, qtype=LA,
            topic=topic, body=body, difficulty=diff, marks=10.0,
            model_answer=model_ans,
            min_words=150, max_words=600,
            rubric={"key_points": [model_ans[:120]], "scheme": scheme},
        ))

    db.add_all(questions)
    db.flush()
    logger.info(
        "Seeded %d SQL questions for %s (MCQ=%d, MSEL=%d, TF=%d, SA=%d, LA=%d).",
        len(questions), SQL101_CODE,
        len(_MCQ_DATA), len(_MSEL_DATA), len(_TF_DATA), len(_SA_DATA), len(_LA_DATA),
    )
    return len(questions)
