"""
make_docs.py – writes SUPPORT_POLICY.pdf and SECURITY_ADVISORY.docx
into workspace/docs/ with the content from PLAN.md section 4.4.
"""
from __future__ import annotations

from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"
DOCS = WORKSPACE / "docs"


# ---------------------------------------------------------------------------
# SUPPORT_POLICY.pdf (reportlab)
# ---------------------------------------------------------------------------
def make_support_policy_pdf() -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    )
    from reportlab.lib.enums import TA_LEFT

    out = DOCS / "SUPPORT_POLICY.pdf"
    DOCS.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=3 * cm,
        rightMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title2",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=14,
    )
    heading_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=16,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body2",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        spaceAfter=8,
    )

    story = []

    # Title
    story.append(Paragraph("Support Policy", title_style))
    story.append(Paragraph(
        "Ledger Library — Effective 2026-01-01",
        body_style,
    ))
    story.append(Spacer(1, 0.4 * cm))

    # §1 Versions
    story.append(Paragraph("§1  Supported Versions", heading_style))
    story.append(Paragraph(
        "<b>3.x (main)</b> — Active support. All bug fixes and security fixes are "
        "applied immediately.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>2.x Maintenance</b> — Bug fixes and security fixes are backported until "
        "<b>2027-06-30</b>.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>1.x Security-only</b> — Security fixes only are backported until "
        "<b>2026-12-31</b>. Regular bug fixes are not backported to this branch.",
        body_style,
    ))
    story.append(Paragraph(
        "<b>0.9 End-of-life</b> — End-of-life since <b>2026-03-31</b>. No fixes of "
        "any kind will be backported. Users should upgrade.",
        body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # §2 Definitions
    story.append(Paragraph("§2  Definitions", heading_style))
    story.append(Paragraph(
        "A <b>security fix</b> is any commit whose subject line starts with "
        "<i>fix(security):</i> or whose body references an FSA advisory number "
        "(e.g. FSA-2026-001). Such fixes are eligible for backport to all "
        "Maintenance and Security-only branches within their support window.",
        body_style,
    ))
    story.append(Paragraph(
        "A <b>bug fix</b> is any commit whose subject starts with <i>fix:</i> and "
        "does not qualify as a security fix under the definition above.",
        body_style,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # §3 Backport process
    story.append(Paragraph("§3  Backport Process", heading_style))
    story.append(Paragraph(
        "Every backport must satisfy the following requirements:",
        body_style,
    ))
    story.append(Paragraph(
        "1. The port must include the <b>regression test</b> introduced by the "
        "original fix, adapted as needed for the target branch's API.",
        body_style,
    ))
    story.append(Paragraph(
        "2. The backport commit message must end with a "
        "<i>Backport of &lt;full SHA&gt;</i> trailer line.",
        body_style,
    ))
    story.append(Paragraph(
        "3. The full test suite on the target branch must pass after the backport "
        "is applied.",
        body_style,
    ))
    story.append(Paragraph(
        "4. If the target branch's code has diverged (e.g. renamed functions, "
        "restructured modules), the port must be adapted minimally to fit the "
        "target branch's existing style and signatures.",
        body_style,
    ))

    story.append(PageBreak())

    # Page 2 — version table summary
    story.append(Paragraph("Version Summary Table", heading_style))
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

    table_data = [
        ["Version", "Status", "Bug fixes", "Security fixes", "EOL date"],
        ["3.x (main)", "Active",        "✓", "✓", "—"],
        ["2.x",        "Maintenance",   "✓", "✓", "2027-06-30"],
        ["1.x",        "Security-only", "✗", "✓", "2026-12-31"],
        ["0.9",        "End-of-life",   "✗", "✗", "2026-03-31"],
    ]
    tbl = Table(table_data, colWidths=[3 * cm, 3.5 * cm, 2.5 * cm, 3.5 * cm, 3 * cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f2f2f2"), colors.white]),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN",      (2, 1), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        "<i>All data is synthetic. No personal information is contained herein.</i>",
        body_style,
    ))

    doc.build(story)
    print(f"  Written: {out}")


# ---------------------------------------------------------------------------
# SECURITY_ADVISORY.docx (python-docx)
# ---------------------------------------------------------------------------
def make_security_advisory_docx() -> None:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    out = DOCS / "SECURITY_ADVISORY.docx"
    DOCS.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Title
    title = doc.add_heading("Security Advisory: FSA-2026-001", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph("")  # spacer

    def add_section(doc, number: str, heading: str, body: str) -> None:
        h = doc.add_heading(f"{number}  {heading}", level=1)
        p = doc.add_paragraph(body)
        p.paragraph_format.space_after = Pt(6)

    def add_table_row(table, label: str, value: str) -> None:
        row = table.add_row()
        row.cells[0].text = label
        row.cells[1].text = value

    # Advisory summary table
    tbl = doc.add_table(rows=1, cols=2)
    tbl.style = "Table Grid"
    hdr = tbl.rows[0].cells
    hdr[0].text = "Field"
    hdr[1].text = "Value"
    # make header bold
    for cell in hdr:
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True

    rows = [
        ("Advisory ID",   "FSA-2026-001"),
        ("Title",         "Path Traversal in export_invoice"),
        ("Severity",      "High"),
        ("CVSSv3 Score",  "7.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)"),
        ("Affected",      "ledger 0.9.0 through 3.0.0"),
        ("Fixed in",      "1.4.3, 2.2.1, 3.0.1"),
        ("Not fixed in",  "0.9 (End-of-life — no patch available)"),
        ("Published",     "2026-04-15"),
    ]
    for label, value in rows:
        add_table_row(tbl, label, value)

    doc.add_paragraph("")

    # §1 Summary
    add_section(
        doc, "§1", "Summary",
        "A path traversal vulnerability exists in the export_invoice function of "
        "the ledger library. An attacker who can control the filename parameter "
        "may be able to write files outside the intended output directory, "
        "potentially overwriting system files or exfiltrating data.",
    )

    # §2 Affected versions
    add_section(
        doc, "§2", "Affected Versions",
        "All releases of the ledger library from version 0.9.0 through 3.0.0 "
        "(inclusive) are affected. The vulnerable code path exists in "
        "ledger/export.py (versions 0.9–2.x) and ledger/exporters/pdf.py "
        "(version 3.x).",
    )

    # §3 Fixed versions
    add_section(
        doc, "§3", "Fixed Versions",
        "The following releases contain the patch for FSA-2026-001:\n"
        "  • 1.4.3 — backported fix for release/1.x branch\n"
        "  • 2.2.1 — backported fix for release/2.x branch\n"
        "  • 3.0.1 — fix applied to main\n\n"
        "Version 0.9 is End-of-life (EOL since 2026-03-31) and will not "
        "receive a patch. Users on 0.9 should upgrade to a supported release.",
    )

    # §4 Workaround
    add_section(
        doc, "§4", "Workaround",
        "If upgrading immediately is not possible, callers should validate the "
        "filename argument before passing it to export_invoice:\n"
        "  1. Reject any filename that is an absolute path.\n"
        "  2. Reject any filename containing '..' path components.\n"
        "  3. Resolve the final path and confirm it is inside the intended "
        "output directory.",
    )

    # §5 References
    add_section(
        doc, "§5", "References",
        "  • Ferry demo repository — commit history for FSA-2026-001\n"
        "  • SUPPORT_POLICY.pdf §2 — definition of a security fix\n\n"
        "All data in this advisory is synthetic and for demonstration purposes "
        "only. No personal information is contained herein.",
    )

    doc.save(str(out))
    print(f"  Written: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    print("==> Generating SUPPORT_POLICY.pdf …")
    make_support_policy_pdf()
    print("==> Generating SECURITY_ADVISORY.docx …")
    make_security_advisory_docx()
    print("==> make_docs.py DONE")


if __name__ == "__main__":
    main()
