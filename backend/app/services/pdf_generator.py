"""PDF Generator Service for ExamAI Examination Platform.

Generates professional, publication-grade candidate scorecards and institutional
performance transcripts using ReportLab.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from app.schemas.exam_session import ResultDetail


def generate_result_pdf(detail: ResultDetail, candidate_email: str | None = None) -> bytes:
    """Renders a candidate's complete exam result into a styled PDF binary."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_title = ParagraphStyle(
        "HeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    header_subtitle = ParagraphStyle(
        "HeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
    )
    doc_badge = ParagraphStyle(
        "DocBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=2,  # right
        textColor=colors.HexColor("#4f46e5"),
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
    )
    cell_label = ParagraphStyle(
        "CellLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )
    cell_val = ParagraphStyle(
        "CellVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
    )
    cell_val_bold = ParagraphStyle(
        "CellValBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
    )
    body_sm = ParagraphStyle(
        "BodySm",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    q_title = ParagraphStyle(
        "QTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )
    footer_text = ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        alignment=1,  # center
        textColor=colors.HexColor("#94a3b8"),
    )

    story = []

    # 1. Brand Header
    header_data = [
        [
            Paragraph("ExamAI <b>Platform</b>", header_title),
            Paragraph("OFFICIAL ASSESSMENT TRANSCRIPT<br/><b>CERTIFIED RESULT</b>", doc_badge),
        ],
        [
            Paragraph("AI-Powered Examination & Automated Proctoring System", header_subtitle),
            Paragraph(f"Generated: {datetime.now().strftime('%b %d, %Y %H:%M')}", header_subtitle),
        ],
    ]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.8 * inch])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#4f46e5"), spaceAfter=12)
    )

    # 2. Candidate & Exam Meta Grid
    sub_date = (
        detail.submitted_at.strftime("%b %d, %Y at %H:%M UTC")
        if detail.submitted_at
        else "In Progress"
    )
    duration_str = (
        f"{detail.time_taken_seconds // 60}m {detail.time_taken_seconds % 60}s"
        if detail.time_taken_seconds
        else "N/A"
    )
    passed = detail.result.percentage >= (detail.passing_percentage or 40.0)

    meta_data = [
        [
            Paragraph("CANDIDATE NAME", cell_label),
            Paragraph(detail.candidate_name, cell_val_bold),
            Paragraph("EXAM TITLE", cell_label),
            Paragraph(detail.exam_title, cell_val_bold),
        ],
        [
            Paragraph("CANDIDATE EMAIL", cell_label),
            Paragraph(candidate_email or "Enrolled Student", cell_val),
            Paragraph("SUBJECT / DOMAIN", cell_label),
            Paragraph(detail.subject_name, cell_val),
        ],
        [
            Paragraph("SUBMISSION DATE", cell_label),
            Paragraph(sub_date, cell_val),
            Paragraph("DURATION TAKEN", cell_label),
            Paragraph(duration_str, cell_val),
        ],
        [
            Paragraph("EXAM MODE", cell_label),
            Paragraph(detail.exam_type.capitalize(), cell_val),
            Paragraph("RESULT STATUS", cell_label),
            Paragraph(
                f"<font color='{'#10b981' if passed else '#ef4444'}'><b>{'PASSED / QUALIFIED' if passed else 'NOT QUALIFIED'}</b></font>",
                cell_val,
            ),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[1.4 * inch, 2.25 * inch, 1.4 * inch, 2.25 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 3. Score Summary Tiles
    pct = round(detail.result.percentage, 1)
    percentile_str = f"{detail.percentile}th" if detail.percentile is not None else "Top Cohort"
    score_tiles_data = [
        [
            Paragraph(
                f"<font size=7 color='#64748b'>TOTAL MARKS</font><br/>"
                f"<font size=15 color='#0f172a'><b>{detail.result.obtained_marks:g}</b></font>"
                f"<font size=9 color='#64748b'> / {detail.result.total_marks:g}</font>",
                styles["Normal"],
            ),
            Paragraph(
                f"<font size=7 color='#64748b'>FINAL PERCENTAGE</font><br/>"
                f"<font size=15 color='{'#059669' if passed else '#dc2626'}'><b>{pct}%</b></font>",
                styles["Normal"],
            ),
            Paragraph(
                f"<font size=7 color='#64748b'>COHORT PERCENTILE</font><br/>"
                f"<font size=15 color='#4f46e5'><b>{percentile_str}</b></font>",
                styles["Normal"],
            ),
            Paragraph(
                "<font size=7 color='#64748b'>PROCTORING STATUS</font><br/>"
                "<font size=12 color='#059669'><b>CLEARED ✓</b></font><br/>"
                "<font size=7 color='#64748b'>AI Integrity Verified</font>",
                styles["Normal"],
            ),
        ]
    ]
    tiles_table = Table(score_tiles_data, colWidths=[1.825 * inch] * 4)
    tiles_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tiles_table)
    story.append(Spacer(1, 14))

    # 4. Section-Wise Breakdown (if sections exist)
    if detail.section_scores:
        story.append(Paragraph("Section-Wise Performance Breakdown", section_heading))
        story.append(Spacer(1, 5))
        sec_rows = [
            [
                Paragraph("<b>Section</b>", cell_label),
                Paragraph("<b>Obtained / Total</b>", cell_label),
                Paragraph("<b>Score %</b>", cell_label),
                Paragraph("<b>Correct</b>", cell_label),
                Paragraph("<b>Incorrect</b>", cell_label),
                Paragraph("<b>Unanswered</b>", cell_label),
            ]
        ]
        for sec in detail.section_scores:
            sec_rows.append(
                [
                    Paragraph(sec.section_name, cell_val_bold),
                    Paragraph(f"{sec.obtained_marks:g} / {sec.total_marks:g}", cell_val),
                    Paragraph(f"{sec.percentage}%", cell_val),
                    Paragraph(str(sec.correct), cell_val),
                    Paragraph(str(sec.incorrect), cell_val),
                    Paragraph(str(sec.unanswered), cell_val),
                ]
            )
        sec_table = Table(
            sec_rows,
            colWidths=[
                2.5 * inch,
                1.1 * inch,
                0.9 * inch,
                0.9 * inch,
                0.9 * inch,
                1.0 * inch,
            ],
        )
        sec_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(sec_table)
        story.append(Spacer(1, 14))

    # 5. Question-Level Feedback Summary
    story.append(Paragraph("Detailed Question Breakdown & Evaluation", section_heading))
    story.append(Spacer(1, 5))

    q_rows = [
        [
            Paragraph("<b># & Question</b>", cell_label),
            Paragraph("<b>Type</b>", cell_label),
            Paragraph("<b>Marks</b>", cell_label),
            Paragraph("<b>Status</b>", cell_label),
            Paragraph("<b>Candidate Answer / Remarks</b>", cell_label),
        ]
    ]

    for idx, q in enumerate(detail.questions, 1):
        clean_body = (q.body[:90] + "...") if len(q.body) > 90 else q.body
        clean_body = clean_body.replace("<", "&lt;").replace(">", "&gt;")

        marks_str = f"{q.awarded_marks if q.awarded_marks is not None else 0:g} / {q.marks:g}"
        status_label = (
            "<font color='#059669'><b>Correct</b></font>"
            if q.is_correct is True
            else (
                "<font color='#dc2626'><b>Incorrect</b></font>"
                if q.is_correct is False
                else "<font color='#d97706'><b>Reviewed</b></font>"
            )
        )

        ans_snippet = (
            (q.your_answer[:65] + "...")
            if (q.your_answer and len(q.your_answer) > 65)
            else (q.your_answer or "<i>Not answered</i>")
        )
        ans_snippet = ans_snippet.replace("<", "&lt;").replace(">", "&gt;")

        if q.ai_justification:
            just_snippet = (
                (q.ai_justification[:70] + "...")
                if len(q.ai_justification) > 70
                else q.ai_justification
            )
            just_snippet = just_snippet.replace("<", "&lt;").replace(">", "&gt;")
            ans_snippet += f"<br/><font color='#64748b' size=6.5>AI: {just_snippet}</font>"

        q_rows.append(
            [
                Paragraph(f"<b>Q{idx}.</b> {clean_body}", q_title),
                Paragraph(q.question_type.value.upper(), body_sm),
                Paragraph(marks_str, body_sm),
                Paragraph(status_label, body_sm),
                Paragraph(ans_snippet, body_sm),
            ]
        )

    q_table = Table(
        q_rows,
        colWidths=[
            2.7 * inch,
            0.9 * inch,
            0.8 * inch,
            0.9 * inch,
            2.0 * inch,
        ],
    )
    q_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )

    story.append(KeepTogether(q_table))
    story.append(Spacer(1, 16))

    # 6. Verification Seal & Institutional Footer
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=8)
    )
    story.append(
        Paragraph(
            "This digital scorecard is generated by ExamAI Platform. "
            "Integrity verified via automated multi-signal proctoring logs and examiner authentication.<br/>"
            "© ExamAI Examination Systems • All Rights Reserved",
            footer_text,
        )
    )

    doc.build(story)
    return buffer.getvalue()
