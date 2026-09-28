"""Concept cards for the three legacy imported subjects in the live database."""

from __future__ import annotations

from app.db.models import QuestionCategory as Q

from .seed_question_catalog import fact as F
from .seed_question_catalog import subject

SUBJECTS = (
    subject(
        "QA-APTITUDE-3137",
        "Aptitude",
        "Legacy imported aptitude pool retained for backward-compatible filtering.",
        Q.APTITUDE,
        (
            F("Number System", "divisibility by 9", "An integer is divisible by 9 when its digit sum is divisible by 9.", "The digit-sum rule works in any decimal base.", "Modular digit tests reveal divisibility without long division."),
            F("Algebra", "zero product", "A product is zero when at least one factor is zero over the real numbers.", "The equation x(x - 3) = 0 has solutions 0 and 3.", "Factored equations can be solved by separating the possible zero factors."),
            F("Mensuration", "rectangle area", "A rectangle's area is its length multiplied by its width.", "Doubling both dimensions multiplies its area by four.", "Area formulas connect linear dimensions to two-dimensional capacity."),
            F("Number Series", "arithmetic progression", "In an arithmetic progression, consecutive terms have a constant difference.", "Its nth term can be written a + (n - 1)d.", "Recognising constant differences distinguishes linear numerical patterns."),
            F("Probability", "complementary events", "The complement of event A contains every outcome outside A.", "P(A) plus P(not A) equals one for an exhaustive sample space.", "Complements simplify counting and probability calculations."),
            F("Logical Reasoning", "valid contrapositive", "The contrapositive of if P then Q is if not Q then not P.", "A conditional and its contrapositive have the same truth value.", "Valid transformations preserve truth and expose hidden dependencies."),
        ),
        create_if_missing=False,
    ),
    subject(
        "QA-DBMS-57A3",
        "DBMS",
        "Legacy imported database pool retained for backward-compatible subject filtering.",
        Q.TECHNICAL,
        (
            F("Keys", "primary key", "A primary key uniquely identifies each relation row and rejects null key values.", "A composite primary key may use several columns together.", "Primary keys give rows stable identities for references and updates."),
            F("Keys", "foreign key", "A foreign key constrains referenced values to exist or explicitly be null under its rule.", "A foreign key can reference a candidate key or suitable unique key.", "Referential integrity protects consistency across related relations."),
            F("Normalisation", "third normal form", "Third normal form removes transitive dependencies of non-key attributes on candidate keys.", "A relation in 2NF has no partial dependency on a composite candidate key.", "Normalisation reduces update anomalies by making facts depend on the right key."),
            F("Joins", "inner join", "An inner join returns only row pairs whose join condition matches.", "LEFT JOIN preserves every row from the left relation.", "Join choice controls whether unmatched records are preserved or discarded."),
            F("Transactions", "atomicity", "Atomicity guarantees that all operations of a transaction commit or all are rolled back.", "Durability guarantees that committed changes survive failures.", "ACID properties protect correctness during failures and concurrent access."),
            F("Performance", "B-tree index", "A B-tree index maintains ordered keys and supports equality and range lookups.", "A hash index can provide efficient exact lookup when ordering is unnecessary.", "Index structure should match the query patterns it serves."),
        ),
        create_if_missing=False,
    ),
    subject(
        "QA-JAVA-BFC4",
        "Java",
        "Legacy imported Java pool retained for backward-compatible subject filtering.",
        Q.TECHNICAL,
        (
            F("Platform", "JVM", "The Java Virtual Machine executes platform-independent bytecode.", "The JVM manages memory and runtime services for Java programs.", "Bytecode enables Java source to run on any compatible JVM."),
            F("Object Orientation", "inheritance", "A subclass inherits accessible non-private members of its superclass.", "Java classes have single inheritance of class state and implementation.", "Inheritance supports reuse while encouraging careful hierarchy design."),
            F("Interfaces", "default method", "A default interface method supplies an implementation inherited by implementing classes.", "An implementing class may override a default method when needed.", "Default methods let interfaces evolve without forcing every implementation to change."),
            F("Collections", "HashMap", "HashMap provides average constant-time key lookup using hashing.", "HashMap permits one null key and multiple null values.", "Map operations should account for mutable or unsuitable keys."),
            F("Exceptions", "checked exception", "A checked Java exception must be declared or caught.", "Unchecked exceptions can occur without explicit declaration.", "Exception contracts make recoverable failure modes visible to callers."),
            F("Concurrency", "synchronised method", "A synchronised instance method locks on the receiving object.", "A synchronised static method locks on its declaring class object.", "Lock choice affects concurrency and must remain consistent across shared state."),
        ),
        create_if_missing=False,
    ),
)
