"""Canned question templates for the offline stub generator.

Content, not logic: question bodies, options and explanations written as prose. They
live apart from `ai_generator` so that module stays pure generation code and keeps the
full line-length lint, while this file - where a question body simply is longer than a
hundred characters and cannot be split without editing the question - is exempt.

Nothing here is ever shown to a candidate unmarked: a stub run flags every draft
`source_grounded: False`, and an examiner reviews it before it can reach the bank.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Stub question templates — realistic enough to exercise the full review flow
# ---------------------------------------------------------------------------

MCQ_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "technical": [
        {
            "body": "Which of the following correctly describes the concept of polymorphism in OOP?",
            "options": [
                {
                    "text": "The ability of a class to inherit from multiple base classes",
                    "is_correct": False,
                },
                {
                    "text": "The ability of different objects to respond to the same interface in their own way",
                    "is_correct": True,
                },
                {
                    "text": "The process of hiding implementation details from the user",
                    "is_correct": False,
                },
                {"text": "A mechanism for allocating memory at runtime", "is_correct": False},
            ],
            "explanation": "Polymorphism allows objects of different types to be treated through a common interface, each responding according to its own implementation.",
        },
        {
            "body": "What is the time complexity of searching for an element in a balanced Binary Search Tree?",
            "options": [
                {"text": "O(1)", "is_correct": False},
                {"text": "O(log n)", "is_correct": True},
                {"text": "O(n)", "is_correct": False},
                {"text": "O(n log n)", "is_correct": False},
            ],
            "explanation": "A balanced BST has height log(n), so search, insert and delete all run in O(log n).",
        },
        {
            "body": "Which SQL clause is used to filter records after grouping?",
            "options": [
                {"text": "WHERE", "is_correct": False},
                {"text": "FILTER", "is_correct": False},
                {"text": "HAVING", "is_correct": True},
                {"text": "GROUP FILTER", "is_correct": False},
            ],
            "explanation": "HAVING filters groups produced by GROUP BY, whereas WHERE filters individual rows before grouping.",
        },
    ],
    "aptitude": [
        {
            "body": "A train travels 360 km in 4 hours. What is its speed in km/h?",
            "options": [
                {"text": "80 km/h", "is_correct": False},
                {"text": "90 km/h", "is_correct": True},
                {"text": "100 km/h", "is_correct": False},
                {"text": "72 km/h", "is_correct": False},
            ],
            "explanation": "Speed = Distance / Time = 360 / 4 = 90 km/h.",
        },
        {
            "body": "If 8 workers complete a job in 12 days, how many days would 6 workers take to complete the same job?",
            "options": [
                {"text": "14 days", "is_correct": False},
                {"text": "16 days", "is_correct": True},
                {"text": "18 days", "is_correct": False},
                {"text": "10 days", "is_correct": False},
            ],
            "explanation": "Workers × Days = constant. 8×12 = 96. 96/6 = 16 days.",
        },
    ],
    "verbal_ability": [
        {
            "body": "Choose the word most similar in meaning to 'Perspicacious'.",
            "options": [
                {"text": "Dull", "is_correct": False},
                {"text": "Shrewd", "is_correct": True},
                {"text": "Timid", "is_correct": False},
                {"text": "Verbose", "is_correct": False},
            ],
            "explanation": "Perspicacious means having a ready insight into things; shrewd is the closest synonym.",
        },
    ],
    "logical_reasoning": [
        {
            "body": "In a series 2, 6, 18, 54, ___, what is the next number?",
            "options": [
                {"text": "108", "is_correct": False},
                {"text": "162", "is_correct": True},
                {"text": "216", "is_correct": False},
                {"text": "81", "is_correct": False},
            ],
            "explanation": "Each term is multiplied by 3: 54 × 3 = 162.",
        },
    ],
    "academic": [
        {
            "body": "Which of the following is NOT a supervised learning algorithm?",
            "options": [
                {"text": "Linear Regression", "is_correct": False},
                {"text": "K-Means Clustering", "is_correct": True},
                {"text": "Decision Tree", "is_correct": False},
                {"text": "Support Vector Machine", "is_correct": False},
            ],
            "explanation": "K-Means is an unsupervised clustering algorithm; the others are supervised.",
        },
    ],
    "coding": [
        {
            "body": "What is the output of the following Python code?\n\n```python\nprint(type([]) is list)\n```",
            "options": [
                {"text": "True", "is_correct": True},
                {"text": "False", "is_correct": False},
                {"text": "TypeError", "is_correct": False},
                {"text": "None", "is_correct": False},
            ],
            "explanation": "`type([])` returns `<class 'list'>` which `is list` evaluates to True.",
        },
    ],
}

FILL_BLANK_TEMPLATES: list[dict[str, Any]] = [
    {
        "body": "The process of converting source code into machine code is called ___.",
        "spec": {
            "kind": "fill_blank",
            "accepted_answers": ["compilation", "compiling"],
            "case_sensitive": False,
        },
        "explanation": "Compilation translates high-level source code into machine-executable code.",
    },
    {
        "body": "In SQL, the ___ statement is used to retrieve data from a database.",
        "spec": {
            "kind": "fill_blank",
            "accepted_answers": ["SELECT", "select"],
            "case_sensitive": False,
        },
        "explanation": "SELECT is the primary DML statement for querying data.",
    },
]

NUMERICAL_TEMPLATES: list[dict[str, Any]] = [
    {
        "body": "What is the value of 2^10?",
        "spec": {"kind": "numerical", "answer": 1024, "tolerance": 0},
        "explanation": "2^10 = 1024.",
    },
    {
        "body": "A rectangle has length 12 cm and width 8 cm. What is its area in cm²?",
        "spec": {"kind": "numerical", "answer": 96, "tolerance": 0},
        "explanation": "Area = length × width = 12 × 8 = 96 cm².",
    },
]

TRUE_FALSE_TEMPLATES: list[dict[str, Any]] = [
    {
        "body": "Python is a statically typed programming language.",
        "options": [
            {"text": "True", "is_correct": False},
            {"text": "False", "is_correct": True},
        ],
        "explanation": "Python is dynamically typed — variable types are determined at runtime.",
    },
    {
        "body": "In a stack, the last element inserted is the first one to be removed.",
        "options": [
            {"text": "True", "is_correct": True},
            {"text": "False", "is_correct": False},
        ],
        "explanation": "Stack follows LIFO (Last In, First Out) order.",
    },
]

SHORT_ANSWER_TEMPLATES: list[dict[str, Any]] = [
    {
        "body": "In one or two sentences, explain what a primary key is in a relational database.",
        "model_answer": "A primary key is a column (or combination of columns) that uniquely identifies each row in a table. It must be unique and cannot contain NULL values.",
        "explanation": "Primary keys enforce entity integrity in relational databases.",
    },
]

CODING_TEMPLATES: list[dict[str, Any]] = [
    {
        "body": "Write a function `reverse_string(s: str) -> str` that returns the reverse of the input string.",
        "spec": {
            "kind": "coding",
            "languages": ["python", "java", "cpp", "javascript"],
            "default_language": "python",
            "input_format": "A single string s (1 ≤ len(s) ≤ 1000).",
            "output_format": "The reversed string.",
            "constraints": "No built-in reverse functions.",
            "sample_cases": [
                {"input": "hello", "output": "olleh"},
                {"input": "abcde", "output": "edcba"},
            ],
        },
        "model_answer": "def reverse_string(s: str) -> str:\n    return s[::-1]",
        "explanation": "Python slicing with step -1 reverses the string in O(n) time and space.",
    },
]
