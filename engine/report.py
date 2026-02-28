import json
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def generate_report(results: dict) -> str:
    """Generate a structured JSON report string from evaluation results."""
    report = {
        "summary": {},
        "clauses": {}
    }

    status_counts = {"COMPLIANT": 0, "PARTIAL": 0, "NON_COMPLIANT": 0}

    for clause_id, result in results.items():
        status = result["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

        report["clauses"][clause_id] = {
            "status": status,
            "clause_score": result["clause_score"],
            "block_scores": result["block_scores"],
            "mandatory_failures": result.get("mandatory_failures", []),
            "matched_evidence": result["matched_evidence"],
            "matched_snippets": result.get("matched_snippets", {}),
            "semantic_matches": result.get("semantic_matches", {}),
            "semantic_only_blocks": result.get("semantic_only_blocks", []),
            "decision_trace": result.get("decision_trace", ""),
            "intent": result.get("intent", ""),
        }

    report["summary"] = {
        "total_clauses": len(results),
        "compliant": status_counts["COMPLIANT"],
        "partial": status_counts["PARTIAL"],
        "non_compliant": status_counts["NON_COMPLIANT"],
    }

    return json.dumps(report, indent=2)


# ---------------------------------------------------------------------------
# PDF Report
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    "COMPLIANT": colors.HexColor("#27ae60"),
    "PARTIAL": colors.HexColor("#f39c12"),
    "NON_COMPLIANT": colors.HexColor("#e74c3c"),
}


def _styles():
    """Build a stylesheet for the PDF report."""
    ss = getSampleStyleSheet()

    ss.add(ParagraphStyle(
        "ReportTitle",
        parent=ss["Title"],
        fontSize=20,
        spaceAfter=6 * mm,
        textColor=colors.HexColor("#2c3e50"),
    ))
    ss.add(ParagraphStyle(
        "SectionHead",
        parent=ss["Heading2"],
        fontSize=13,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        textColor=colors.HexColor("#2c3e50"),
    ))
    ss.add(ParagraphStyle(
        "ClauseHead",
        parent=ss["Heading3"],
        fontSize=11,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    ))
    ss.add(ParagraphStyle(
        "Body",
        parent=ss["Normal"],
        fontSize=9,
        leading=12,
    ))
    ss.add(ParagraphStyle(
        "SnippetText",
        parent=ss["Normal"],
        fontSize=7.5,
        leading=10,
        leftIndent=8 * mm,
        textColor=colors.HexColor("#555555"),
        fontName="Helvetica-Oblique",
    ))
    ss.add(ParagraphStyle(
        "TraceText",
        parent=ss["Normal"],
        fontSize=8,
        leading=10,
        leftIndent=4 * mm,
        textColor=colors.HexColor("#7f8c8d"),
    ))
    ss.add(ParagraphStyle(
        "SmallItalic",
        parent=ss["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.grey,
    ))
    ss.add(ParagraphStyle(
        "SemanticSnippet",
        parent=ss["Normal"],
        fontSize=7.5,
        leading=10,
        leftIndent=8 * mm,
        textColor=colors.HexColor("#6c3483"),
        fontName="Helvetica-Oblique",
    ))
    return ss


def generate_pdf_report(
    results: dict,
    source_filename: str,
    output_path: str,
    suggestions: dict = None,
) -> str:
    """
    Generate a professional PDF gap report with optional AI suggestions.

    Returns the output_path written to.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    ss = _styles()
    story = []

    # --- Title ---
    story.append(Paragraph("NABH Gap Analysis Report", ss["ReportTitle"]))
    story.append(Paragraph(
        f"Source document: <b>{source_filename}</b>", ss["Body"]
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ss["SmallItalic"]
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#bdc3c7")
    ))

    # --- Summary table ---
    story.append(Paragraph("Executive Summary", ss["SectionHead"]))

    status_counts = {"COMPLIANT": 0, "PARTIAL": 0, "NON_COMPLIANT": 0}
    for r in results.values():
        status_counts[r["status"]] += 1

    summary_data = [
        ["Total Clauses", str(len(results))],
        ["Compliant", str(status_counts["COMPLIANT"])],
        ["Partial", str(status_counts["PARTIAL"])],
        ["Non-Compliant", str(status_counts["NON_COMPLIANT"])],
    ]
    t = Table(summary_data, colWidths=[55 * mm, 30 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecf0f1")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(
        width="100%", thickness=0.5, color=colors.HexColor("#bdc3c7")
    ))

    # --- Per-clause detail ---
    story.append(Paragraph("Clause-wise Analysis", ss["SectionHead"]))

    for clause_id, result in results.items():
        status = result["status"]
        color = STATUS_COLORS.get(status, colors.black)

        story.append(Paragraph(
            f'{clause_id} — <font color="{color.hexval()}">{status}</font>'
            f'  (score: {result["clause_score"]})',
            ss["ClauseHead"],
        ))

        # Decision trace
        trace = result.get("decision_trace", "")
        if trace:
            story.append(Paragraph(
                f"<i>Decision: {trace}</i>", ss["TraceText"]
            ))

        # Mandatory failures
        mf = result.get("mandatory_failures", [])
        if mf:
            story.append(Paragraph(
                f'<font color="#e74c3c">Mandatory failures: {", ".join(mf)}</font>',
                ss["TraceText"],
            ))

        story.append(Spacer(1, 1.5 * mm))

        # Block scores table
        block_header = [
            Paragraph("<b>Evidence Block</b>", ss["Body"]),
            Paragraph("<b>Score</b>", ss["Body"]),
            Paragraph("<b>Matched Signals</b>", ss["Body"]),
        ]
        block_rows = [block_header]
        for block_name, score in result["block_scores"].items():
            matched = result["matched_evidence"].get(block_name, [])
            matched_str = ", ".join(matched) if matched else "—"
            block_rows.append([
                Paragraph(block_name, ss["Body"]),
                Paragraph(str(round(score, 2)), ss["Body"]),
                Paragraph(matched_str, ss["Body"]),
            ])

        bt = Table(block_rows, colWidths=[45 * mm, 20 * mm, 95 * mm])
        bt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(bt)

        # Evidence snippets (exact)
        snippets = result.get("matched_snippets", {})
        has_snippets = any(v for v in snippets.values())
        if has_snippets:
            story.append(Spacer(1, 1.5 * mm))
            story.append(Paragraph(
                "<b>Exact Evidence Snippets</b>", ss["Body"]
            ))
            for block_name, sents in snippets.items():
                if sents:
                    story.append(Paragraph(
                        f"<b>{block_name}:</b>", ss["SnippetText"]
                    ))
                    for s in sents[:3]:
                        safe = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        story.append(Paragraph(
                            f"\u2022 \u201c{safe}\u201d", ss["SnippetText"]
                        ))

        # Semantic evidence snippets (separate)
        sem_snippets = result.get("semantic_matches", {})
        has_sem = any(v for v in sem_snippets.values())
        if has_sem:
            story.append(Spacer(1, 1.5 * mm))
            sem_only = result.get("semantic_only_blocks", [])
            label = "Semantic Evidence"
            if sem_only:
                label += f' <font color="#e74c3c">(semantic-only: {", ".join(sem_only)})</font>'
            story.append(Paragraph(f"<b>{label}</b>", ss["Body"]))
            for block_name, sents in sem_snippets.items():
                if sents:
                    story.append(Paragraph(
                        f"<b>{block_name}:</b>", ss["SemanticSnippet"]
                    ))
                    for s in sents[:3]:
                        safe = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        story.append(Paragraph(
                            f"\u2022 \u201c{safe}\u201d", ss["SemanticSnippet"]
                        ))

        story.append(Spacer(1, 3 * mm))

    # --- Consultant Suggestions ---
    if suggestions:
        story.append(HRFlowable(
            width="100%", thickness=1, color=colors.HexColor("#2c3e50")
        ))
        story.append(Paragraph("Consultant Recommendations", ss["SectionHead"]))
        story.append(Paragraph(
            "The following actionable improvements are suggested based on the gaps identified above.",
            ss["Body"]
        ))
        story.append(Spacer(1, 4 * mm))

        for cid, sug in suggestions.items():
            if not sug or "improvement_summary" not in sug:
                continue
                
            story.append(Paragraph(f"<b>{cid} Improvement Plan</b>", ss["ClauseHead"]))
            story.append(Paragraph(sug["improvement_summary"], ss["Body"]))
            
            if sug.get("required_documents"):
                story.append(Paragraph("<i>Required Documents:</i>", ss["Body"]))
                for doc_item in sug["required_documents"]:
                    story.append(Paragraph(f"\u2022 {doc_item}", ss["Body"], bulletText="\u2022"))
            
            if sug.get("operational_controls"):
                story.append(Paragraph("<i>Operational Controls:</i>", ss["Body"]))
                for control in sug["operational_controls"]:
                    story.append(Paragraph(f"\u2022 {control}", ss["Body"]))
            
            if sug.get("audit_readiness_tip"):
                story.append(Paragraph(
                    f'<b>Audit Tip:</b> {sug["audit_readiness_tip"]}', 
                    ss["TraceText"]
                ))
            
            story.append(Spacer(1, 4 * mm))

    doc.build(story)
    return output_path
