"""Top up the Academic question bank with genuine image-based questions.

"Image-based" is not a new ``QuestionType`` - the architecture already supports a
question that shows a diagram via ``Question.image_key`` and is answered as any
ordinary type (single choice, multiple choice, short answer, long answer). This module
generates a real, meaningful SVG diagram per question (see ``app.services.diagram_gen``)
and derives the question and its correct answer *from the same parameters* used to draw
it, so the diagram is never decorative - the candidate must read it to answer.

Covers the seven core academic subjects at 10 easy + 10 medium + 10 hard image-based
questions each (30/subject, 210 total), split across MCQ, multi-select, short answer and
long answer so every one of those types gets image-based coverage.

Idempotent: a subject already carrying >= 30 rows tagged ``IMG_TAG`` is left alone.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.storage import put_object
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
from app.services import diagram_gen as dg

logger = get_logger("seed_images")

IMG_TAG = "image-bank"
PER_SUBJECT = 30
_DIFFS = [(Difficulty.EASY, "easy"), (Difficulty.MEDIUM, "medium"), (Difficulty.HARD, "hard")]
#: 4 MCQ, 2 multi-select, 2 short answer, 2 long answer per 10-question block.
_TYPE_CYCLE = ["mcq", "mcq", "mcq", "multi_select", "multi_select", "short_answer", "short_answer", "long_answer", "long_answer", "mcq"]


def _upload(svg: str, subject_code: str, tag: str) -> str:
    key = f"question-diagrams/{subject_code.lower()}/{tag}.svg"
    put_object(key=key, data=svg.encode("utf-8"), content_type="image/svg+xml")
    return key


def _q(
    subject: Subject,
    examiner: User,
    category: QuestionCategory,
    qtype: QuestionType,
    topic: str,
    body: str,
    difficulty: Difficulty,
    image_key: str,
    *,
    marks: float,
    negative: float = 0.0,
    options: list[tuple[str, bool]] | None = None,
    model_answer: str | None = None,
    explanation: str | None = None,
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
        image_key=image_key,
        model_answer=model_answer,
        explanation=explanation,
        marks=marks,
        negative_marks=negative,
        min_words=min_words,
        max_words=max_words,
        created_by_id=examiner.id,
        tags=[IMG_TAG, subject.code.lower(), "image-based"],
        status=QuestionStatus.PUBLISHED,
        is_active=True,
    )
    for index, (text, correct) in enumerate(options or []):
        question.options.append(QuestionOption(text=text, is_correct=correct, order_index=index))
    return question


# ===========================================================================
# Topic generators. Each returns a dict with the svg, a topic label, one
# fully-formed {body, options, correct} or {body, model_answer} per question
# type, and a shared explanation - all derived from the same drawn parameters.
# ===========================================================================

Ctx = dict[str, Any]

# --- Operating Systems -----------------------------------------------------

def _os_process_state(i: int, difficulty: str) -> Ctx:
    state_sets = [["New", "Ready", "Running", "Terminated"], ["Ready", "Running", "Waiting", "Terminated"]]
    states = state_sets[i % 2]
    highlight = i % 4
    svg = dg.os_process_state(states, highlight)
    return {
        "svg": svg,
        "topic_label": "Process States",
        "mcq": {"body": "The process-state diagram below shades one state. Which state is shaded?", "options": states, "correct": [highlight]},
        "multi_select": {"body": f"Based on the arrows in the diagram, which states have a direct transition arrow INTO '{states[1]}'?", "options": states, "correct": [0, 2]},
        "short_answer": {"body": "How many directed transition arrows are drawn in this process-state diagram in total?", "model_answer": "5 arrows are shown in the diagram."},
        "long_answer": {"body": f"Using only the arrows shown in the diagram, describe one valid full lifecycle path a process could follow from '{states[0]}' to '{states[3]}', naming every intermediate state.", "model_answer": f"{states[0]} -> {states[1]} -> {states[2]} -> {states[3]}, following the arrows shown from {states[0]} to {states[1]}, {states[1]} to {states[2]}, and {states[2]} to {states[3]}."},
        "explanation": "Read the shaded box and the arrows directly from the diagram; no information outside the image is needed.",
    }


def _os_gantt(i: int, difficulty: str) -> Ctx:
    n = 3 if difficulty == "easy" else (4 if difficulty == "medium" else 5)
    durs = [((i + k) % 4) + 2 for k in range(n)]
    procs = [(f"P{k + 1}", 0, durs[k]) for k in range(n)]
    svg = dg.os_gantt_chart(procs)
    completion, total = [], 0
    for _label, _s, d in procs:
        total += d
        completion.append(total)
    starts = [0] + completion[:-1]
    longest_idx = durs.index(max(durs))
    threshold = sorted(durs)[len(durs) // 2]
    above = [k for k, d in enumerate(durs) if d > threshold] or [longest_idx]
    avg_wait = sum(starts) / n
    return {
        "svg": svg,
        "topic_label": "CPU Scheduling",
        "mcq": {"body": "According to the Gantt chart, which process has the longest burst time (widest bar)?", "options": [p[0] for p in procs], "correct": [longest_idx]},
        "multi_select": {"body": f"Which processes have a burst time strictly greater than {threshold} time units, as shown in the chart?", "options": [p[0] for p in procs], "correct": above},
        "short_answer": {"body": "Using the Gantt chart (FCFS order, all processes arrive at time 0), compute the average waiting time across all processes.", "model_answer": f"Waiting times read from the chart are {starts}, so average waiting time = {sum(starts)}/{n} = {avg_wait:.2f} time units."},
        "long_answer": {"body": "Explain how this Gantt chart demonstrates First-Come-First-Served (FCFS) scheduling, and compute the turnaround time of the last process shown to finish.", "model_answer": f"Processes execute strictly in arrival order with no preemption, which is what FCFS does. The last process finishes at time {completion[-1]}; since it arrived at time 0, its turnaround time (completion - arrival) is {completion[-1]}."},
        "explanation": "All timing facts are read directly from the bar widths and order shown in the Gantt chart.",
    }


def _os_memory(i: int, difficulty: str) -> Ctx:
    n = 3 if difficulty == "easy" else (4 if difficulty == "medium" else 5)
    sizes = [((i + k) % 6 + 1) * 16 for k in range(n)]
    labels = [f"P{k + 1}" if k % 3 != 2 else "Free" for k in range(n)]
    blocks = list(zip(labels, sizes))
    svg = dg.os_memory_allocation(blocks)
    free_total = sum(s for label, s in blocks if label == "Free")
    largest_free = max([s for label, s in blocks if label == "Free"], default=0)
    largest_idx = sizes.index(max(sizes))
    return {
        "svg": svg,
        "topic_label": "Memory Management",
        "mcq": {"body": "Which memory block shown in the map is the largest?", "options": [f"{label} ({s}KB)" for label, s in blocks], "correct": [largest_idx]},
        "multi_select": {"body": "Which blocks shown in the memory map are labelled 'Free'?", "options": [f"{label} ({s}KB)" for label, s in blocks], "correct": [k for k, (label, _s) in enumerate(blocks) if label == "Free"]},
        "short_answer": {"body": "From the memory map, what is the total free memory available (sum of all 'Free' blocks), in KB?", "model_answer": f"Total free memory = {free_total}KB."},
        "long_answer": {"body": "Explain, using the memory map shown, whether a new process requiring the single largest free block's size could be allocated without compaction, and why.", "model_answer": f"The largest contiguous free block is {largest_free}KB, so a process needing up to {largest_free}KB can be placed directly there without compaction. A request larger than {largest_free}KB cannot be satisfied by any single free block even though total free memory ({free_total}KB) may be larger, since the free blocks shown are not contiguous."},
        "explanation": "Sizes and labels are read directly from the memory map diagram.",
    }


def _os_page_table(i: int, difficulty: str) -> Ctx:
    n = 4 if difficulty == "easy" else (5 if difficulty == "medium" else 6)
    entries = [(k, (i + k * 2) % 8, k % 3 != 1) for k in range(n)]
    svg = dg.os_page_table(entries)
    valid_count = sum(1 for _p, _f, v in entries if v)
    invalid_pages = [str(p) for p, _f, v in entries if not v]
    first_invalid = next((p for p, _f, v in entries if not v), None)
    return {
        "svg": svg,
        "topic_label": "Paging",
        "mcq": {"body": "How many page-table entries shown are marked valid (V=1)?", "options": [str(max(valid_count - 1, 0)), str(valid_count), str(valid_count + 1), str(max(valid_count - 2, 0)) + " "], "correct": [1]},
        "multi_select": {"body": "Which page numbers shown in the table are marked INVALID (V=0)?", "options": [str(p) for p, _f, _v in entries], "correct": [k for k, (_p, _f, v) in enumerate(entries) if not v]},
        "short_answer": {"body": "Which is the first (lowest-numbered) page marked invalid in the table? Referencing it would cause a page fault.", "model_answer": (f"Page {first_invalid} is the first invalid entry, so referencing it triggers a page fault." if first_invalid is not None else "All pages shown are valid; no page fault would occur.")},
        "long_answer": {"body": "Explain what happens when the CPU generates a memory reference to a page marked invalid in this table, referencing the specific page numbers from the diagram.", "model_answer": (f"Pages {', '.join(invalid_pages)} are marked invalid (V=0) in the table. A reference to any of these triggers a page fault: the MMU traps to the OS, which locates the page on disk, loads it into a free frame, updates that page-table entry to valid, and restarts the instruction." if invalid_pages else "Every page shown is valid, so no reference in this table would cause a page fault.")},
        "explanation": "Validity bits and frame numbers are read directly from the page-table diagram.",
    }


# --- Computer Networks -------------------------------------------------------

_OSI_TOP_DOWN = ["Application", "Presentation", "Session", "Transport", "Network", "Data Link", "Physical"]
_OSI_FUNC = {
    "Physical": "transmits raw bits over a physical medium",
    "Data Link": "provides node-to-node framing and error detection using MAC addresses",
    "Network": "routes packets across networks using logical (IP) addressing",
    "Transport": "provides end-to-end reliable or best-effort delivery (TCP/UDP)",
    "Session": "manages sessions/dialogues between communicating applications",
    "Presentation": "translates, encrypts and compresses data for the application layer",
    "Application": "provides network services directly to end-user applications",
}


def _net_osi(i: int, difficulty: str) -> Ctx:
    highlight = i % 7
    svg = dg.net_osi_layers(_OSI_TOP_DOWN, highlight)
    layer_name = _OSI_TOP_DOWN[highlight]
    layer_num = 7 - highlight
    below = [k for k in range(7) if k > highlight]
    above = [k for k in range(7) if k < highlight]
    ms_body = f"Which of these layers appear BELOW the highlighted layer ('{layer_name}') in the diagram?" if below else f"Which of these layers appear ABOVE the highlighted layer ('{layer_name}') in the diagram?"
    ms_correct = below if below else above
    below_name = _OSI_TOP_DOWN[highlight + 1] if highlight < 6 else "none - it is the lowest layer shown"
    return {
        "svg": svg,
        "topic_label": "OSI Model",
        "mcq": {"body": "Which OSI layer is highlighted (shaded) in the diagram?", "options": _OSI_TOP_DOWN, "correct": [highlight]},
        "multi_select": {"body": ms_body, "options": _OSI_TOP_DOWN, "correct": ms_correct},
        "short_answer": {"body": f"What is the numeric OSI layer number of the highlighted layer ('{layer_name}') shown in the diagram (1=Physical ... 7=Application)?", "model_answer": f"Layer {layer_num} ({layer_name})."},
        "long_answer": {"body": f"Explain the primary function of the highlighted layer ('{layer_name}') shown in the diagram and name the layer immediately below it in the stack.", "model_answer": f"The {layer_name} layer {_OSI_FUNC[layer_name]}. The layer immediately below it in the stack shown is {below_name}."},
        "explanation": "The layer stack, its order and the shaded layer are all read directly from the diagram.",
    }


def _net_topology(i: int, difficulty: str) -> Ctx:
    kinds = ["star", "ring", "bus"]
    kind = kinds[i % 3]
    nodes = 4 if difficulty == "easy" else (5 if difficulty == "medium" else 6)
    svg = dg.net_topology(kind, nodes)
    facts = {
        "star": ("a central switch/hub, with every host individually cabled to it", "the central switch/hub"),
        "ring": ("a closed loop where each host connects to exactly two neighbours", "any single link in the loop"),
        "bus": ("a single shared backbone cable that every host taps into", "the shared backbone cable"),
    }
    desc, spof = facts[kind]
    return {
        "svg": svg,
        "topic_label": "Network Topologies",
        "mcq": {"body": "What network topology is shown in the diagram?", "options": ["Star", "Ring", "Bus"], "correct": [kinds.index(kind)]},
        "multi_select": {"body": "Which of these statements are true of the topology shown in the diagram?", "options": [f"It uses {desc}", "It requires no cabling of any kind", f"Failure of {spof} disrupts connectivity for the other hosts", "It can only support two hosts"], "correct": [0, 2]},
        "short_answer": {"body": f"How many host nodes are shown connected in this {kind} topology diagram?", "model_answer": f"{nodes} host nodes are shown."},
        "long_answer": {"body": f"Describe the {kind} topology shown in the diagram and identify its single point of failure.", "model_answer": f"This is a {kind} topology: it uses {desc}. Its single point of failure is {spof}; if it fails, connectivity for the other hosts shown in the diagram is disrupted."},
        "explanation": "The wiring pattern and node count are both directly visible in the diagram.",
    }


def _net_packet(i: int, difficulty: str) -> Ctx:
    tcp_fields = [("Src Port", 2), ("Dst Port", 2), ("Seq No", 4), ("Ack No", 4), ("Flags", 1), ("Window", 2), ("Checksum", 2)]
    ip_fields = [("Version", 1), ("Header Len", 1), ("Total Len", 2), ("TTL", 1), ("Protocol", 1), ("Src IP", 4), ("Dst IP", 4)]
    proto, fields = ("TCP segment", tcp_fields) if i % 2 == 0 else ("IPv4 header", ip_fields)
    n = 4 if difficulty == "easy" else (6 if difficulty == "medium" else 7)
    fields = fields[:n]
    svg = dg.net_packet_structure(fields)
    total_bytes = sum(b for _name, b in fields)
    largest = max(fields, key=lambda f: f[1])
    min_size = min(f[1] for f in fields)
    return {
        "svg": svg,
        "topic_label": "Protocol Headers",
        "mcq": {"body": f"In this {proto} diagram, which field occupies the most bytes?", "options": [f[0] for f in fields], "correct": [fields.index(largest)]},
        "multi_select": {"body": f"Which fields shown are exactly {min_size} byte(s) wide?", "options": [f[0] for f in fields], "correct": [k for k, f in enumerate(fields) if f[1] == min_size]},
        "short_answer": {"body": f"What is the total size in bytes of the {proto} shown in the diagram (sum of all fields)?", "model_answer": f"{total_bytes} bytes."},
        "long_answer": {"body": f"List every field shown in this {proto} diagram in order with its size in bytes, and state the overall header size.", "model_answer": ", ".join(f"{name} ({sz}B)" for name, sz in fields) + f". Overall size = {total_bytes} bytes."},
        "explanation": "Field names and widths are read directly from the labelled boxes in the diagram.",
    }


def _net_routing(i: int, difficulty: str) -> Ctx:
    n = 3 if difficulty == "easy" else (4 if difficulty == "medium" else 5)
    dests = [f"10.0.{k}.0/24" for k in range(n)]
    hops = [f"R{(i + k) % 4 + 1}" for k in range(n)]
    metrics = [((i + k) % 5) + 1 for k in range(n)]
    entries = list(zip(dests, hops, metrics))
    svg = dg.net_routing_table(entries)
    best_idx = metrics.index(min(metrics))
    worst_idx = metrics.index(max(metrics))
    same_hop = [k for k, (_d, h, _m) in enumerate(entries) if h == hops[0]]
    return {
        "svg": svg,
        "topic_label": "Routing",
        "mcq": {"body": "According to the routing table shown, which destination has the LOWEST metric (best route)?", "options": dests, "correct": [best_idx]},
        "multi_select": {"body": f"Which destinations shown use next-hop '{hops[0]}'?", "options": dests, "correct": same_hop},
        "short_answer": {"body": "What is the metric value of the route with the HIGHEST metric shown in the table?", "model_answer": f"{max(metrics)} (destination {dests[worst_idx]})."},
        "long_answer": {"body": "Explain how a router would use this routing table to forward a packet destined for the network with the lowest metric, naming the destination and next hop involved.", "model_answer": f"The router looks up the destination network against the table and forwards using the matching entry's next hop. For {dests[best_idx]}, which has the lowest metric ({min(metrics)}), the packet is forwarded to next hop {hops[best_idx]}."},
        "explanation": "Destinations, next hops and metrics are all read directly from the routing table diagram.",
    }


# --- Engineering Mathematics --------------------------------------------------

def _math_matrix(i: int, difficulty: str) -> Ctx:
    size = 2 if difficulty != "hard" else 3
    vals = [[((i + r * size + c) % 9) + 1 for c in range(size)] for r in range(size)]
    svg = dg.math_matrix(vals)
    if size == 2:
        det = vals[0][0] * vals[1][1] - vals[0][1] * vals[1][0]
        det_expl = f"det(A) = ad - bc = {vals[0][0]}*{vals[1][1]} - {vals[0][1]}*{vals[1][0]} = {det}."
    else:
        (a, b, c), (d, e, f), (g, h, k) = vals
        det = a * (e * k - f * h) - b * (d * k - f * g) + c * (d * h - e * g)
        det_expl = f"Cofactor expansion along row 1: det(A) = a(ek-fh) - b(dk-fg) + c(dh-eg) = {det}."
    trace = sum(vals[r][r] for r in range(size))
    positions = [f"A[{r + 1}][{c + 1}]" for r in range(size) for c in range(size)]
    diag_idx = [r * size + r for r in range(size)]
    return {
        "svg": svg,
        "topic_label": "Matrices",
        "mcq": {"body": "What is the value of the trace (sum of diagonal elements) of matrix A shown in the diagram?", "options": [str(trace - 1), str(trace), str(trace + 1), str(trace + 2)], "correct": [1]},
        "multi_select": {"body": "Which positions shown belong to the main diagonal of matrix A?", "options": positions, "correct": diag_idx},
        "short_answer": {"body": "Compute the determinant of matrix A shown in the diagram.", "model_answer": f"det(A) = {det}."},
        "long_answer": {"body": "Show the full working to compute the determinant of matrix A shown in the diagram (state the formula used and substitute the actual values).", "model_answer": det_expl},
        "explanation": "All matrix entries needed for these computations are read directly from the diagram.",
    }


def _math_function_plot(i: int, difficulty: str) -> Ctx:
    b = (i % 5) - 2
    c = (i % 3) - 1
    xs = list(range(-3, 4))
    pts = [(float(x), float(x * x + b * x + c)) for x in xs]
    svg = dg.math_function_plot(pts, f"y = x^2 + {b}x + {c}")
    vertex_x = -b / 2
    vertex_y = vertex_x * vertex_x + b * vertex_x + c
    xmin = round(vertex_x)
    y0 = c
    less_idxs = [k for k, x in enumerate(xs) if (x * x + b * x + c) < y0]
    greater_idxs = [k for k, x in enumerate(xs) if (x * x + b * x + c) > y0]
    ms_body = f"Which of these x-values shown on the curve give a y-value LESS than the y-value at x=0?" if less_idxs else "Which of these x-values shown on the curve give a y-value GREATER than the y-value at x=0?"
    ms_correct = less_idxs if less_idxs else greater_idxs
    return {
        "svg": svg,
        "topic_label": "Calculus & Functions",
        "mcq": {"body": "From the plotted curve, at approximately which x-value does the function reach its minimum y-value?", "options": [str(xmin - 1), str(xmin), str(xmin + 1), str(xmin + 2)], "correct": [1]},
        "multi_select": {"body": ms_body, "options": [str(x) for x in xs], "correct": ms_correct},
        "short_answer": {"body": "Reading the curve, what is the equation's y-intercept (the value of y when x=0)?", "model_answer": f"y = c = {c}, since at x=0 the equation gives y = 0 + 0 + c = {c}."},
        "long_answer": {"body": "Using the plotted curve, determine the coordinates of the vertex (minimum point) of this parabola and explain how you identified it from the graph.", "model_answer": f"The vertex is the lowest point on the plotted curve, at x = -b/2a = -({b})/2 = {vertex_x:.1f}, giving y = {vertex_y:.2f}. This is visible on the graph as the point where the curve stops decreasing and starts increasing."},
        "explanation": "The vertex, intercepts and comparative heights are all read directly from the plotted curve.",
    }


def _math_geometry(i: int, difficulty: str) -> Ctx:
    base_sets = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25)]
    a, b, c = base_sets[i % 4]
    scale = 1 if difficulty == "easy" else (2 if difficulty == "medium" else 3)
    a, b, c = a * scale, b * scale, c * scale
    svg = dg.math_geometry_triangle((a, b, c))
    perimeter = a + b + c
    area = 0.5 * a * b
    return {
        "svg": svg,
        "topic_label": "Geometry",
        "mcq": {"body": "Which side labelled in the diagram is the LONGEST?", "options": ["a", "b", "c"], "correct": [2]},
        "multi_select": {"body": f"Which of these statements about the triangle shown are TRUE (a={a}, b={b}, c={c})?", "options": ["a^2 + b^2 = c^2 (it is a right triangle)", "All three sides are equal (equilateral)", f"The perimeter is {perimeter}", "It has no right angle"], "correct": [0, 2]},
        "short_answer": {"body": "Using the side lengths labelled in the diagram, compute the perimeter of the triangle.", "model_answer": f"Perimeter = a + b + c = {a} + {b} + {c} = {perimeter}."},
        "long_answer": {"body": "Using the side lengths labelled in the diagram, verify whether this triangle satisfies the Pythagorean theorem, and compute its area assuming sides a and b are the legs.", "model_answer": f"Check: a^2+b^2 = {a}^2+{b}^2 = {a * a + b * b}, and c^2 = {c}^2 = {c * c}. These are equal, confirming a right triangle. Area = (1/2) * a * b = (1/2) * {a} * {b} = {area}."},
        "explanation": "Side lengths are read directly from the labels in the diagram.",
    }


def _math_vectors(i: int, difficulty: str) -> Ctx:
    ux, uy = (i % 4) + 1, (i % 3) + 1
    vx, vy = -((i % 3) + 1), (i % 4) + 2
    svg = dg.math_vector_diagram([("u", ux, uy), ("v", vx, vy)])
    dot = ux * vx + uy * vy
    sumv = (ux + vx, uy + vy)
    mag = math.hypot(*sumv)
    return {
        "svg": svg,
        "topic_label": "Vector Calculus",
        "mcq": {"body": "Which vector shown in the diagram points into the region where x is negative and y is positive (the second quadrant)?", "options": ["u", "v"], "correct": [1]},
        "multi_select": {"body": "Which of these are true about vectors u and v shown in the diagram?", "options": [f"u = ({ux}, {uy})", f"v = ({vx}, {vy})", f"u + v = ({sumv[0]}, {sumv[1]})", "u and v are parallel"], "correct": [0, 1, 2]},
        "short_answer": {"body": "Using the vector components labelled in the diagram, compute the dot product u . v.", "model_answer": f"u.v = ({ux})({vx}) + ({uy})({vy}) = {dot}."},
        "long_answer": {"body": "Using the components shown in the diagram, compute the resultant vector u + v and state its magnitude.", "model_answer": f"u + v = ({ux}+{vx}, {uy}+{vy}) = ({sumv[0]}, {sumv[1]}). Magnitude = sqrt({sumv[0]}^2 + {sumv[1]}^2) = {mag:.2f}."},
        "explanation": "Both vectors' components are labelled directly on the diagram.",
    }


# --- Machine Learning ----------------------------------------------------------

def _ml_decision_tree(i: int, difficulty: str) -> Ctx:
    pool = [("Income > 50K?", "Credit Score > 700?"), ("Age > 40?", "Tenure > 5 years?"), ("GPA > 3.5?", "Test Score > 80?")]
    root, cond2 = pool[i % 3]
    children = [("Yes", cond2), ("No", "Reject")]
    leaves = ["Approve", "Reject", "Approve", "Reject"]
    svg = dg.ml_decision_tree(root, children, leaves)
    return {
        "svg": svg,
        "topic_label": "Decision Trees",
        "mcq": {"body": "What is the root (topmost) splitting condition shown in the decision tree diagram?", "options": [root, cond2, "Age > 30?", "Loan Amount > 10000?"], "correct": [0]},
        "multi_select": {"body": "Which of these leaf outcomes appear in the decision tree shown?", "options": ["Approve", "Reject", "Pending", "Escalate"], "correct": [0, 1]},
        "short_answer": {"body": f"According to the tree, what happens when '{root}' evaluates to No?", "model_answer": "The applicant is immediately classified as 'Reject', without evaluating any further condition, as shown by the 'No' branch."},
        "long_answer": {"body": f"Trace the decision path shown in the tree for an applicant where '{root}' is Yes and '{cond2}' is Yes, and state the final classification.", "model_answer": f"Starting at the root '{root}', the answer is Yes, so we follow the Yes branch to '{cond2}'. Since that is also Yes, we follow that branch to the leaf 'Approve', the final classification."},
        "explanation": "The splitting conditions and leaf labels are read directly from the tree diagram.",
    }


def _ml_scatter(i: int, difficulty: str) -> Ctx:
    k = 2 if difficulty == "easy" else (3 if difficulty == "medium" else 4)
    centers = [(2 + 3 * c, 2 + 3 * c) for c in range(k)]
    points = [(cx + (j - 1) * 0.5, cy + (j - 1) * 0.5, c) for c, (cx, cy) in enumerate(centers) for j in range(3)]
    svg = dg.ml_scatter_plot(points, k)
    counts = [sum(1 for p in points if p[2] == c) for c in range(k)]
    return {
        "svg": svg,
        "topic_label": "Clustering",
        "mcq": {"body": "How many distinct clusters (colours) are shown in the scatter plot?", "options": [str(k - 1), str(k), str(k + 1), str(k + 2)], "correct": [1]},
        "multi_select": {"body": "Which cluster indices shown contain more than 2 points?", "options": [f"Cluster {c}" for c in range(k)], "correct": [c for c in range(k) if counts[c] > 2]},
        "short_answer": {"body": "How many points in total are plotted in this scatter chart?", "model_answer": f"{len(points)} points."},
        "long_answer": {"body": "Describe the separation between clusters visible in the scatter plot and state how many points belong to each cluster.", "model_answer": "; ".join(f"Cluster {c} has {counts[c]} points" for c in range(k)) + ". The clusters are visually well separated, each occupying its own region of the plot with a distinct colour."},
        "explanation": "Cluster membership is read directly from the marker colour and position in the plot.",
    }


def _ml_confusion(i: int, difficulty: str) -> Ctx:
    tp, fp, fn, tn = 40 + i, 5 + (i % 4), 8 + (i % 3), 47 - (i % 5)
    svg = dg.ml_confusion_matrix(tp, fp, fn, tn)
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    f1 = 2 * precision * recall / (precision + recall)
    return {
        "svg": svg,
        "topic_label": "Model Evaluation",
        "mcq": {"body": "From the confusion matrix shown, which cell represents False Negatives?", "options": ["TP cell (top-left)", "FN cell (top-right)", "FP cell (bottom-left)", "TN cell (bottom-right)"], "correct": [1]},
        "multi_select": {"body": "Which of these values can be read directly from the confusion matrix shown?", "options": [f"TP = {tp}", f"FP = {fp}", f"Precision = {precision:.2f} (this is computed, not read directly)", f"TN = {tn}"], "correct": [0, 1, 3]},
        "short_answer": {"body": "Using the values shown in the confusion matrix, compute the model's precision.", "model_answer": f"Precision = TP/(TP+FP) = {tp}/({tp}+{fp}) = {precision:.3f}."},
        "long_answer": {"body": "Using the values shown in the confusion matrix, compute accuracy, recall and F1-score, showing your working.", "model_answer": f"Accuracy = (TP+TN)/(TP+FP+FN+TN) = ({tp}+{tn})/{tp + fp + fn + tn} = {accuracy:.3f}. Recall = TP/(TP+FN) = {tp}/{tp + fn} = {recall:.3f}. F1 = 2PR/(P+R) = 2*{precision:.3f}*{recall:.3f}/({precision:.3f}+{recall:.3f}) = {f1:.3f}."},
        "explanation": "TP, FP, FN and TN are read directly from the four labelled cells of the matrix.",
    }


def _ml_clustering(i: int, difficulty: str) -> Ctx:
    k = 2 if difficulty == "easy" else 3
    centroids = [(3 + 4 * c, 3 + 4 * c) for c in range(k)]
    points = [(cx + (j % 2), cy + (j // 2), c) for c, (cx, cy) in enumerate(centroids) for j in range(4)]
    svg = dg.ml_clustering(centroids, points)
    return {
        "svg": svg,
        "topic_label": "K-Means Clustering",
        "mcq": {"body": "How many centroids (marked as squares) are shown in the clustering diagram?", "options": [str(k - 1), str(k), str(k + 1), str(k + 2)], "correct": [1]},
        "multi_select": {"body": "Which of the following are shown as squares (centroids) in the diagram?", "options": [f"Centroid {c}" for c in range(k)] + ["A data point"], "correct": list(range(k))},
        "short_answer": {"body": "How many data points in total are assigned across all clusters shown in the diagram?", "model_answer": f"{len(points)} data points."},
        "long_answer": {"body": "Explain how the K-Means algorithm would have produced the centroid positions shown relative to their assigned points in the diagram.", "model_answer": "Each centroid (square) sits at the mean of the coordinates of its assigned data points (circles of the same colour), since K-Means repeatedly recomputes each centroid as the average position of its cluster's members until convergence."},
        "explanation": "Centroid and point positions/colours are read directly from the diagram.",
    }


# --- Natural Language Processing -----------------------------------------------

def _nlp_pipeline(i: int, difficulty: str) -> Ctx:
    steps_full = ["Raw Text", "Tokenization", "Stop-word Removal", "Stemming/Lemmatization", "Vectorization", "Model"]
    n = 3 if difficulty == "easy" else (4 if difficulty == "medium" else 6)
    steps = steps_full[:n]
    svg = dg.nlp_pipeline(steps)
    idx = steps.index("Tokenization") if "Tokenization" in steps else 0
    nxt = steps[idx + 1] if idx + 1 < len(steps) else steps[idx]
    return {
        "svg": svg,
        "topic_label": "NLP Pipeline",
        "mcq": {"body": "Which stage of the NLP pipeline shown comes immediately after 'Tokenization'?", "options": steps, "correct": [steps.index(nxt)]},
        "multi_select": {"body": "Which of these stages appear in the pipeline diagram shown?", "options": steps_full, "correct": [steps_full.index(s) for s in steps]},
        "short_answer": {"body": "How many stages are shown in this NLP pipeline diagram in total?", "model_answer": f"{len(steps)} stages."},
        "long_answer": {"body": "Describe, in order, what happens to the input text at each stage shown in the pipeline diagram.", "model_answer": " -> ".join(steps) + ". The raw text is transformed step by step, left to right, through each stage shown, ending ready for the model."},
        "explanation": "The stage names and their order are read directly from the diagram.",
    }


def _nlp_tokenization(i: int, difficulty: str) -> Ctx:
    sents = ["The cats are running quickly", "Natural language processing is fascinating", "She sells seashells by the seashore", "Deep learning models require large datasets"]
    sentence = sents[i % len(sents)]
    tokens = sentence.split()
    svg = dg.nlp_tokenization(sentence, tokens)
    return {
        "svg": svg,
        "topic_label": "Tokenization",
        "mcq": {"body": "How many tokens does the diagram show the sentence being split into?", "options": [str(len(tokens) - 1), str(len(tokens)), str(len(tokens) + 1), str(len(tokens) + 2)], "correct": [1]},
        "multi_select": {"body": "Which of these words appear as individual tokens in the diagram shown?", "options": [tokens[0], tokens[1], "banana", "computer"], "correct": [0, 1]},
        "short_answer": {"body": "What is the first token shown in the tokenization diagram?", "model_answer": f"'{tokens[0]}'."},
        "long_answer": {"body": "Explain what tokenization has done to the original sentence shown at the top of the diagram, listing the resulting tokens in order.", "model_answer": f"The sentence \"{sentence}\" has been split on whitespace into {len(tokens)} individual word tokens: {', '.join(tokens)}."},
        "explanation": "The original sentence and its resulting tokens are both shown directly in the diagram.",
    }


def _nlp_parse_tree(i: int, difficulty: str) -> Ctx:
    svg = dg.nlp_parse_tree("S", ["NP", "VP"], {"NP": ["Det", "N"], "VP": ["V", "NP"]})
    return {
        "svg": svg,
        "topic_label": "Syntax Parsing",
        "mcq": {"body": "What is the root node label of the parse tree shown?", "options": ["S", "NP", "VP", "N"], "correct": [0]},
        "multi_select": {"body": "Which of these are direct children of the root 'S' in the parse tree shown?", "options": ["NP", "VP", "Det", "V"], "correct": [0, 1]},
        "short_answer": {"body": "What are the two children of the 'NP' node shown in the parse tree?", "model_answer": "Det and N."},
        "long_answer": {"body": "Describe the full structure of the parse tree shown, from the root down to every leaf.", "model_answer": "The root S expands into NP and VP. NP expands into Det and N (a determiner followed by a noun). VP expands into V and NP (a verb followed by a noun phrase) - matching the simple grammar S -> NP VP shown."},
        "explanation": "Every node and edge needed is drawn explicitly in the parse tree.",
    }


def _nlp_attention(i: int, difficulty: str) -> Ctx:
    toks_full = ["The", "cat", "sat", "on", "the", "mat"]
    n = 4 if difficulty == "easy" else (5 if difficulty == "medium" else 6)
    tokens = toks_full[:n]
    weights = [round(0.1 + 0.15 * ((i + k) % 5), 2) for k in range(n)]
    svg = dg.nlp_attention_weights(tokens, weights)
    max_idx = weights.index(max(weights))
    median = sorted(weights)[len(weights) // 2]
    above = [k for k, w in enumerate(weights) if w > median]
    return {
        "svg": svg,
        "topic_label": "Attention Mechanism",
        "mcq": {"body": "Which token receives the HIGHEST attention weight in the diagram?", "options": tokens, "correct": [max_idx]},
        "multi_select": {"body": f"Which tokens shown have an attention weight ABOVE {median}?", "options": tokens, "correct": above},
        "short_answer": {"body": "What is the attention weight value shown for the token with the tallest bar?", "model_answer": f"{max(weights)} (token '{tokens[max_idx]}')."},
        "long_answer": {"body": "Explain what the bar heights in this attention diagram represent, and identify which token the model is 'focusing on' most, with its weight.", "model_answer": f"Each bar height represents the attention weight assigned to that token when computing the current representation - taller bars mean the model relies on that token more. Here the model focuses most on '{tokens[max_idx]}' with weight {max(weights)}."},
        "explanation": "Bar heights and the printed weight values are read directly from the diagram.",
    }


# --- Artificial Intelligence -----------------------------------------------

def _ai_search_tree(i: int, difficulty: str) -> Ctx:
    edges: list[tuple[str, str, int]] = [("A", "B", 4), ("A", "C", 2), ("B", "D", 5), ("B", "E", 1), ("C", "F", 3)]
    if difficulty != "easy":
        edges.append(("C", "G", 6))
    svg = dg.ai_search_tree("A", edges)
    children_of: dict[str, list[str]] = {}
    for p, c, _cost in edges:
        children_of.setdefault(p, []).append(c)
    leaves = [c for _p, c, _cost in edges if c not in children_of]

    def path_cost(leaf: str) -> int:
        for p, c, cost in edges:
            if c == leaf:
                for p2, c2, cost2 in edges:
                    if c2 == p:
                        return cost + cost2
                return cost
        return 0

    costs = {leaf: path_cost(leaf) for leaf in leaves}
    cheapest = min(costs, key=costs.get)
    ac_cost = next(cost for p, c, cost in edges if p == "A" and c == "C")
    return {
        "svg": svg,
        "topic_label": "Search Algorithms",
        "mcq": {"body": "What is the edge cost from node A to node C shown in the diagram?", "options": [str(ac_cost - 1), str(ac_cost), str(ac_cost + 1), str(ac_cost + 2)], "correct": [1]},
        "multi_select": {"body": "Which nodes shown are direct children of node A in the search tree?", "options": ["B", "C", "D", "E"], "correct": [0, 1]},
        "short_answer": {"body": f"What is the total path cost from A to {cheapest} shown in the diagram?", "model_answer": f"{costs[cheapest]} (sum of the edge costs along the path)."},
        "long_answer": {"body": "Using the edge costs shown in the diagram, determine which leaf node is reached by the cheapest path from A, and state that path's total cost.", "model_answer": f"Comparing all root-to-leaf path costs shown in the diagram, the cheapest path reaches '{cheapest}' with total cost {costs[cheapest]}."},
        "explanation": "Every edge cost needed is printed on the corresponding edge in the diagram.",
    }


def _ai_minimax(i: int, difficulty: str) -> Ctx:
    n = 4 if difficulty != "hard" else 8
    leaves = [((i + k) % 9) + 1 for k in range(n)]
    svg = dg.ai_minimax_tree(leaves, ("MAX", "MIN"))
    mins = [min(leaves[k:k + 2]) for k in range(0, len(leaves), 2)]
    maxv = max(mins)
    below = [k for k, v in enumerate(leaves) if v < maxv]
    return {
        "svg": svg,
        "topic_label": "Adversarial Search",
        "mcq": {"body": "What is the final MINIMAX value backed up to the root (MAX) node shown in the diagram?", "options": [str(maxv - 1), str(maxv), str(maxv + 1), str(maxv + 2)], "correct": [1]},
        "multi_select": {"body": "Which of these leaf values shown in the diagram are LESS than the final root value?", "options": [str(v) for v in leaves], "correct": below},
        "short_answer": {"body": "What is the minimum of the first pair of leaf values (leftmost two leaves) shown in the diagram?", "model_answer": f"{min(leaves[0], leaves[1])}."},
        "long_answer": {"body": "Explain how the MIN and MAX levels shown in the diagram combine to produce the final root value, using the actual leaf numbers.", "model_answer": f"At the MIN level, each pair of leaves is compared and the smaller value kept: {mins}. At the MAX (root) level, the largest of these MIN results is chosen: max({mins}) = {maxv}, the final minimax value."},
        "explanation": "Every leaf value and the resulting backed-up values are printed directly in the diagram.",
    }


def _ai_state_space(i: int, difficulty: str) -> Ctx:
    n = 5 if difficulty != "hard" else 7
    states = [f"S{k}" for k in range(n)]
    edges = [(k, (k + 1) % n) for k in range(n)]
    if difficulty != "easy":
        edges.append((0, n // 2))
    start, goal = 0, n - 1
    svg = dg.ai_state_space(states, edges, start, goal)
    adj: dict[int, list[int]] = {k: [] for k in range(n)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    neighbors = sorted(set(adj[start]))
    prev: dict[int, int | None] = {start: None}
    q = deque([start])
    while q:
        u = q.popleft()
        if u == goal:
            break
        for v in adj[u]:
            if v not in prev:
                prev[v] = u
                q.append(v)
    path = [goal]
    while prev.get(path[-1]) is not None:
        path.append(prev[path[-1]])
    path.reverse()
    return {
        "svg": svg,
        "topic_label": "State-Space Search",
        "mcq": {"body": "Which state is marked as the START state (distinct colour) in the diagram?", "options": states, "correct": [start]},
        "multi_select": {"body": "Which states shown have a direct edge connecting them to the START state?", "options": states, "correct": neighbors},
        "short_answer": {"body": "How many states in total are shown in this state-space diagram?", "model_answer": f"{n} states."},
        "long_answer": {"body": "Describe a path from the START state to the GOAL state using only the edges shown in the diagram.", "model_answer": " -> ".join(states[p] for p in path) + "."},
        "explanation": "Nodes, edges and the start/goal colouring are all directly visible in the diagram.",
    }


def _ai_knowledge_graph(i: int, difficulty: str) -> Ctx:
    pool = [("Socrates", "is_a", "Human"), ("Human", "is_a", "Mortal"), ("Python", "is_a", "Language"), ("Language", "used_for", "Programming")]
    n = 3 if difficulty == "easy" else 4
    triples = pool[:n]
    svg = dg.ai_knowledge_graph(triples)
    nodeset: list[str] = []
    for s, _p, o in triples:
        if s not in nodeset:
            nodeset.append(s)
        if o not in nodeset:
            nodeset.append(o)
    return {
        "svg": svg,
        "topic_label": "Knowledge Representation",
        "mcq": {"body": f"According to the knowledge graph shown, what relation connects '{triples[0][0]}' to '{triples[0][2]}'?", "options": [triples[0][1], "causes", "part_of", "located_in"], "correct": [0]},
        "multi_select": {"body": "Which of the following entities appear as nodes in the knowledge graph shown?", "options": nodeset + ["Elephant"], "correct": list(range(len(nodeset)))},
        "short_answer": {"body": "How many labelled relation edges (triples) are shown in this knowledge graph?", "model_answer": f"{len(triples)} triples."},
        "long_answer": {"body": "Using transitive reasoning over the relations shown in the graph, what can be inferred about the first entity, and via which chain of edges?", "model_answer": " -> ".join(f"{s} {p} {o}" for s, p, o in triples) + f". Chaining these relations, we can infer that {triples[0][0]} is ultimately {triples[-1][2]}, by transitivity through the intermediate edges shown."},
        "explanation": "Every entity and relation label needed is printed directly on the graph.",
    }


# --- Deep Learning -------------------------------------------------------------

def _dl_nn_arch(i: int, difficulty: str) -> Ctx:
    layer_sizes = [3, 4, 2] if difficulty == "easy" else ([4, 5, 4, 3] if difficulty == "medium" else [4, 6, 5, 3, 2])
    svg = dg.dl_nn_architecture(layer_sizes)
    total_neurons = sum(layer_sizes)
    n_layers = len(layer_sizes)
    return {
        "svg": svg,
        "topic_label": "Neural Network Architecture",
        "mcq": {"body": "How many layers (including input and output) are shown in the network architecture diagram?", "options": [str(n_layers - 1), str(n_layers), str(n_layers + 1), str(n_layers + 2)], "correct": [1]},
        "multi_select": {"body": "Which of these layer sizes are shown in the diagram?", "options": [str(s) for s in layer_sizes] + ["10", "1"], "correct": list(range(len(layer_sizes)))},
        "short_answer": {"body": "How many neurons are in the OUTPUT layer (rightmost) shown in the diagram?", "model_answer": f"{layer_sizes[-1]} neurons."},
        "long_answer": {"body": "Describe the architecture shown in the diagram layer by layer, and compute the total number of neurons across the whole network.", "model_answer": f"The network has {n_layers} layers with sizes {layer_sizes} from input to output. Total neurons = {' + '.join(str(s) for s in layer_sizes)} = {total_neurons}."},
        "explanation": "Every layer and its neuron count are drawn and labelled directly in the diagram.",
    }


def _dl_cnn_arch(i: int, difficulty: str) -> Ctx:
    layer_pool = [("input", "28x28x1"), ("conv", "24x24x6"), ("pool", "12x12x6"), ("conv", "8x8x16"), ("pool", "4x4x16"), ("fc", "120"), ("fc", "84"), ("output", "10")]
    n = 4 if difficulty == "easy" else (6 if difficulty == "medium" else 8)
    layers = layer_pool[:n]
    svg = dg.dl_cnn_architecture(layers)
    conv_count = sum(1 for k, _s in layers if k == "conv")
    all_kinds = ["conv", "pool", "fc", "input", "output"]
    present = list(dict.fromkeys(k for k, _s in layers))
    return {
        "svg": svg,
        "topic_label": "CNN Architecture",
        "mcq": {"body": "How many convolutional (CONV) layers are shown in the CNN architecture diagram?", "options": [str(max(conv_count - 1, 0)), str(conv_count), str(conv_count + 1), str(conv_count + 2)], "correct": [1]},
        "multi_select": {"body": "Which layer types appear in the CNN architecture shown?", "options": [k.upper() for k in all_kinds], "correct": [all_kinds.index(k) for k in present]},
        "short_answer": {"body": "What is the spatial size label shown for the INPUT layer in the diagram?", "model_answer": f"{layers[0][1]}."},
        "long_answer": {"body": "Trace the CNN architecture shown from input to output, describing how the spatial size changes at each stage.", "model_answer": " -> ".join(f"{k.upper()} ({s})" for k, s in layers) + ". Convolution and pooling progressively shrink the spatial dimensions while increasing depth/channels, until fully-connected layers flatten to the final output."},
        "explanation": "Layer types and their size labels are printed directly on each block in the diagram.",
    }


def _dl_convolution(i: int, difficulty: str) -> Ctx:
    size = 3 if difficulty == "easy" else (4 if difficulty == "medium" else 5)
    input_grid = [[((i + r + c) % 3) for c in range(size)] for r in range(size)]
    kernel = [[1, 0], [0, 1]] if difficulty != "hard" else [[1, 0, -1], [1, 0, -1], [1, 0, -1]]
    svg = dg.dl_convolution_operation(input_grid, kernel)
    ksz = len(kernel)
    out_size = size - ksz + 1
    conv_val = sum(input_grid[r][c] * kernel[r][c] for r in range(ksz) for c in range(ksz))
    flat = sorted({v for row in kernel for v in row})
    return {
        "svg": svg,
        "topic_label": "Convolution Operation",
        "mcq": {"body": f"Given the {size}x{size} input and {ksz}x{ksz} kernel shown (stride 1, no padding), what is the output feature map size (per side)?", "options": [str(out_size - 1), str(out_size), str(out_size + 1), str(size)], "correct": [1]},
        "multi_select": {"body": "Which of these values appear in the kernel shown in the diagram?", "options": [str(v) for v in flat] + ["9"], "correct": list(range(len(flat)))},
        "short_answer": {"body": "Compute the value at the top-left position of the output feature map, by sliding the kernel over the top-left corner of the input shown.", "model_answer": f"Sum of element-wise products = {conv_val}."},
        "long_answer": {"body": "Explain, step by step, how the kernel shown slides over the input grid to produce the output feature map, and state the resulting output size.", "model_answer": f"The {ksz}x{ksz} kernel is placed over each {ksz}x{ksz} region of the {size}x{size} input, multiplying element-wise and summing (e.g. the top-left position gives {conv_val}), then slides across with stride 1 and no padding, producing a {out_size}x{out_size} output feature map."},
        "explanation": "The exact grid and kernel values needed for the computation are printed in the diagram's cells.",
    }


def _dl_activation(i: int, difficulty: str) -> Ctx:
    name_fn: list[tuple[str, Callable[[float], float]]] = [
        ("Sigmoid", lambda x: 1 / (1 + math.exp(-x))),
        ("Tanh", lambda x: math.tanh(x)),
        ("ReLU", lambda x: max(0.0, x)),
    ]
    name, fn = name_fn[i % 3]
    xs = [x / 2 for x in range(-6, 7)]
    pts = [(x, fn(x)) for x in xs]
    svg = dg.dl_activation_graph(name, pts)
    y0 = fn(0.0)
    facts = {
        "Sigmoid": ["Output is bounded between 0 and 1", "The curve is monotonically increasing", "Output can be negative", "It is a step function"],
        "Tanh": ["Output is bounded between -1 and 1", "The curve is monotonically increasing", "Output is always positive", "It is a step function"],
        "ReLU": ["Output is 0 for all negative inputs", "The curve is non-decreasing", "Output is bounded above by 1", "It is a step function"],
    }[name]
    sa_ans = {
        "Sigmoid": "No - the sigmoid curve shown stays between 0 and 1 for all x.",
        "Tanh": "Yes - the tanh curve shown is negative for all x < 0.",
        "ReLU": "No - the ReLU curve shown is exactly 0 for x < 0 and never negative.",
    }[name]
    la_ans = {
        "Sigmoid": "The curve is an S-shape saturating near 0 for very negative x and near 1 for very positive x. Because the slope flattens at both extremes, gradients shrink toward zero there, contributing to the vanishing gradient problem in deep networks.",
        "Tanh": "The curve is an S-shape centred at zero, saturating near -1 and 1. It is zero-centred (unlike sigmoid), which helps optimisation, but it still saturates at the extremes, also causing vanishing gradients in deep networks.",
        "ReLU": "The curve is flat at zero for negative inputs and rises linearly for positive inputs. Because the gradient is a constant 1 for positive inputs, it avoids vanishing gradients there, but neurons stuck in the negative region can 'die' and stop learning.",
    }[name]
    return {
        "svg": svg,
        "topic_label": "Activation Functions",
        "mcq": {"body": f"From the plotted curve, what is the approximate output value of the {name} function at x = 0?", "options": [f"{y0 - 0.5:.1f}", f"{y0:.1f}", f"{y0 + 0.5:.1f}", f"{y0 + 1:.1f}"], "correct": [1]},
        "multi_select": {"body": "Which of these are true about the activation function curve shown?", "options": facts, "correct": [0, 1]},
        "short_answer": {"body": f"From the graph, does the {name} curve ever become negative? Answer yes or no and give the range where it is negative, if any.", "model_answer": sa_ans},
        "long_answer": {"body": f"Describe the overall shape of the {name} curve shown in the graph and explain one practical consequence of this shape for training deep networks.", "model_answer": la_ans},
        "explanation": "The curve's shape and its value at any x are read directly from the plotted graph.",
    }


_TOPIC_FUNCS: dict[str, list[Callable[[int, str], Ctx]]] = {
    "CS202": [_os_process_state, _os_gantt, _os_memory, _os_page_table],
    "CS203": [_net_osi, _net_topology, _net_packet, _net_routing],
    "MATH101": [_math_matrix, _math_function_plot, _math_geometry, _math_vectors],
    "ML101": [_ml_decision_tree, _ml_scatter, _ml_confusion, _ml_clustering],
    "NLP101": [_nlp_pipeline, _nlp_tokenization, _nlp_parse_tree, _nlp_attention],
    "AI101": [_ai_search_tree, _ai_minimax, _ai_state_space, _ai_knowledge_graph],
    "DL101": [_dl_nn_arch, _dl_cnn_arch, _dl_convolution, _dl_activation],
}


def _build_subject(subject: Subject, examiner: User, category: QuestionCategory, funcs: list[Callable[[int, str], Ctx]]) -> list[Question]:
    out: list[Question] = []
    for diff_enum, diff_str in _DIFFS:
        for i in range(10):
            ctx = funcs[i % 4](i, diff_str)
            qtype_str = _TYPE_CYCLE[i]
            key = _upload(ctx["svg"], subject.code, f"{diff_str}-{i:02d}-{qtype_str}")
            spec = ctx[qtype_str]
            explanation = ctx["explanation"]
            if qtype_str == "mcq":
                options = [(o, idx in spec["correct"]) for idx, o in enumerate(spec["options"])]
                out.append(_q(subject, examiner, category, QuestionType.MCQ, ctx["topic_label"], spec["body"], diff_enum, key, marks=2.0, negative=0.5, options=options, explanation=explanation))
            elif qtype_str == "multi_select":
                options = [(o, idx in spec["correct"]) for idx, o in enumerate(spec["options"])]
                out.append(_q(subject, examiner, category, QuestionType.MULTI_SELECT, ctx["topic_label"], spec["body"], diff_enum, key, marks=3.0, negative=1.0, options=options, explanation=explanation))
            elif qtype_str == "short_answer":
                out.append(_q(subject, examiner, category, QuestionType.SHORT_ANSWER, ctx["topic_label"], spec["body"], diff_enum, key, marks=5.0, model_answer=spec["model_answer"], min_words=3, max_words=120, explanation=explanation))
            else:
                out.append(_q(subject, examiner, category, QuestionType.LONG_ANSWER, ctx["topic_label"], spec["body"], diff_enum, key, marks=8.0, model_answer=spec["model_answer"], min_words=15, max_words=300, explanation=explanation))
    return out


#: Matches ``SUBJECT_PROFILES`` in ``app.seed_question_bank_bulk`` - these subjects'
#: MCQ/TF/fill-blank/etc. depth was already seeded under this category, so an image-based
#: question must carry the same category or an examiner filtering (Category, Topic, Type,
#: Difficulty) together would see a fragmented, inconsistent result set.
_CATEGORY_BY_CODE: dict[str, QuestionCategory] = {
    "CS202": QuestionCategory.TECHNICAL,
    "CS203": QuestionCategory.TECHNICAL,
    "MATH101": QuestionCategory.APTITUDE,
    "ML101": QuestionCategory.TECHNICAL,
    "NLP101": QuestionCategory.TECHNICAL,
    "AI101": QuestionCategory.TECHNICAL,
    "DL101": QuestionCategory.TECHNICAL,
}


def top_up_images(db: Session, examiner: User) -> int:
    """Bring every target academic subject up to ``PER_SUBJECT`` image-based questions."""
    added = 0
    for code, funcs in _TOPIC_FUNCS.items():
        subject = db.scalar(select(Subject).where(Subject.code == code))
        if subject is None:
            logger.warning("Subject %s not found, skipping image-based top-up", code)
            continue
        existing = db.scalar(
            select(func.count(Question.id)).where(
                Question.subject_id == subject.id,
                Question.tags.contains([IMG_TAG]),
            )
        ) or 0
        if existing >= PER_SUBJECT:
            logger.info("%s already has %d image-based questions", code, existing)
            continue
        new_questions = _build_subject(subject, examiner, _CATEGORY_BY_CODE[code], funcs)
        db.add_all(new_questions)
        db.flush()
        added += len(new_questions)
        logger.info("%s: added %d image-based questions", code, len(new_questions))
    return added
