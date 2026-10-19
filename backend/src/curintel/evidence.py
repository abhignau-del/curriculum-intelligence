"""An evidence pack for NAAC metric 2.6.1: a Word document per programme.

Metric 2.6.1 of NAAC's university manual asks that a programme's learning outcomes (programme
and course outcomes, or graduate attributes) are stated, integrated into assessment, made
public, and that their attainment is evaluated. The pack sets out what this tool knows, in the
order an assessor reads it:

1. programme outcomes - the programme's own POs/PSOs, or the framework it was mapped to;
2. course outcomes for every course, with each outcome's Bloom level;
3. the CO-PO articulation matrix and how it was built;
4. attainment for a batch (when results are given): the policy, PO and CO attainment;
5. actions for outcomes below target - a table for the department to complete;
6. points to settle before submission, found in the data (vague outcomes, courses with no
   outcomes, POs no outcome serves, outcomes not assessed ...).

It is a draft to review and complete, not a finished submission: the department adds what
only it knows (where outcomes are published, actions taken) and checks every figure.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from . import __version__
from .attainment import AttainmentReport
from .mapping import MappingReport
from .report import policy_words

LEVEL_NAMES = {1: "Remember", 2: "Understand", 3: "Apply", 4: "Analyse", 5: "Evaluate", 6: "Create"}
SHADE = {1: "D9E2EC", 2: "8FAACC", 3: "3F6E9C"}
MUTED = RGBColor(0x5A, 0x65, 0x74)
A4 = (Inches(8.27), Inches(11.69))
MARGIN = Inches(0.9)
PORTRAIT_WIDTH = 8.27 - 2 * 0.9                 # usable width, inches
LANDSCAPE_WIDTH = 11.69 - 2 * 0.9


def _page(section, landscape: bool = False) -> None:
    section.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    section.page_width, section.page_height = (A4[1], A4[0]) if landscape else A4
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, MARGIN)


def _shade(cell, hex_fill: str) -> None:
    pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    pr.append(shd)


def _table(doc, header: list[str], rows: list[list[str]], widths: Optional[list[float]] = None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for cell, text in zip(t.rows[0].cells, header):
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        _shade(cell, "E8ECF1")
    for row in rows:
        cells = t.add_row().cells
        for cell, text in zip(cells, row):
            cell.text = str(text)
    if widths:
        t.autofit = False
        for row in t.rows:
            for cell, w in zip(row.cells, widths):
                cell.width = Inches(w)
    t.rows[0].repeat_as_header = True
    tr_pr = t.rows[0]._tr.get_or_add_trPr()
    header_flag = OxmlElement("w:tblHeader")
    header_flag.set(qn("w:val"), "true")
    tr_pr.append(header_flag)
    return t


def _note(doc, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = True
    run.font.color.rgb = MUTED


def _fmt(x: Optional[float]) -> str:
    return "–" if x is None else f"{x:.2f}"


def build(mapping: MappingReport, attainment: Optional[AttainmentReport] = None) -> Document:
    prog = mapping.programme
    fw = mapping.framework
    rep = mapping.outcomes
    own_pos = fw.own
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)
    _page(doc.sections[0])

    # ----- title -----------------------------------------------------------------
    doc.add_heading(f"{prog.name}: learning outcomes and their attainment", level=0)
    doc.add_paragraph(f"{prog.institution}" + (f" · {prog.year}" if prog.year else "")
                      + (f" · batch {attainment.data.batch}" if attainment and attainment.data.batch else ""))
    _note(doc, "Evidence for NAAC metric 2.6.1 (university manual): learning outcomes stated, integrated into "
               "assessment and made public, and their attainment evaluated. Draft prepared with Curriculum "
               f"Intelligence {__version__} on {date.today().isoformat()}: review every figure and complete the "
               "sections marked for the department before submission.")

    # ----- points to settle --------------------------------------------------------
    issues = []
    if not own_pos:
        issues.append(f"The programme states no programme outcomes (POs/PSOs) of its own; course outcomes are mapped to "
                      f"{fw.name}. Adopt POs and PSOs for the programme, or confirm this framework as its graduate attributes.")
    if rep.without_outcomes:
        issues.append(f"{len(rep.without_outcomes)} course(s) state no course outcomes: "
                      + ", ".join(f"{c} {t}" for c, t in rep.without_outcomes) + ".")
    vague = rep.flagged("vague")
    if vague:
        issues.append(f"{len(vague)} of {len(rep.results)} course outcomes open with a verb that is hard to assess "
                      "(such as 'understand' or 'learn'); attainment is easier to evidence for outcomes that can be measured.")
    if rep.flagged("no_verb"):
        issues.append(f"{len(rep.flagged('no_verb'))} course outcome(s) have no action verb at the start.")
    if rep.duplicates:
        issues.append(f"{len(rep.duplicates)} course outcome(s) are stated word for word for more than one course.")
    unserved = [po for po, n, _ in mapping.po_summary() if n == 0]
    if unserved:
        issues.append("No course outcome serves " + ", ".join(f"{po.code} {po.name}".strip() for po in unserved) + ".")
    if attainment is None:
        issues.append("No attainment results were given: section 4 is empty. Upload a batch's results to complete it.")
    else:
        if attainment.no_data:
            issues.append(f"{len(attainment.no_data)} course outcome(s) were not assessed in this batch.")
        below = [c for c in attainment.assessed if c.overall < attainment.policy.target_level - 1e-9]
        if below:
            issues.append(f"{len(below)} course outcome(s) fell below the target level: record the actions taken in section 5.")
    issues.append("Add where the outcomes are published (website pages, handbooks, course files): NAAC asks that they "
                  "are made public.")
    doc.add_heading("Before submission", level=1)
    for item in issues:
        doc.add_paragraph(item, style="List Bullet")

    # ----- 1. programme outcomes ----------------------------------------------------
    doc.add_heading("1. Programme outcomes", level=1)
    if own_pos:
        doc.add_paragraph("The programme's stated programme outcomes and programme-specific outcomes.")
    else:
        doc.add_paragraph(f"The programme states no programme outcomes of its own. Its course outcomes were mapped to "
                          f"{fw.name}" + (f" ({fw.source})" if fw.source else "") + ".")
    _table(doc, ["Code", "Outcome"], [[po.code, (f"{po.name}: " if po.name else "") + po.text] for po in fw.outcomes],
           [0.8, PORTRAIT_WIDTH - 0.8])

    # ----- 2. course outcomes ---------------------------------------------------------
    doc.add_heading("2. Course outcomes", level=1)
    share = rep.higher_order_share(rep.results)
    doc.add_paragraph(f"{len(rep.results)} course outcomes are stated for {rep.courses_with_outcomes} of "
                      f"{len(prog.courses)} courses. Each outcome's level in the revised Bloom's taxonomy is read from "
                      "the verbs it opens with"
                      + (f"; {100 * share:.0f}% are at Analyse or above." if share is not None else "."))
    for c in prog.courses:
        if not c.outcomes:
            continue
        doc.add_heading(f"{c.code} {c.title}" + (f" (semester {c.semester})" if c.semester else ""), level=3)
        results = [r for r in rep.results if r.course_code == c.code]
        _table(doc, ["CO", "Outcome", "Bloom level"],
               [[f"CO{i}", r.text, f"{r.level} {LEVEL_NAMES[r.level]}" if r.level else
                 ("vague" if "vague" in r.flags else "–")] for i, r in enumerate(results, start=1)],
               [0.6, PORTRAIT_WIDTH - 1.9, 1.3])

    # ----- 3. CO-PO matrix ---------------------------------------------------------------
    codes = [po.code for po in fw.outcomes]
    landscape = len(codes) > 6
    _page(doc.add_section(), landscape)
    width = LANDSCAPE_WIDTH if landscape else PORTRAIT_WIDTH
    course_w = 2.4 if landscape else 1.8
    doc.add_heading("3. CO–PO articulation matrix", level=1)
    doc.add_paragraph("Strength of each course's contribution to each programme outcome: 1 slight, 2 moderate, "
                      "3 substantial. A course outcome serves a programme outcome when its verbs, the topics it names "
                      "or its wording match the programme outcome's indicators; it maps more strongly when two kinds "
                      "match and when its Bloom level reaches the one the programme outcome calls for. A course's value "
                      "is the rounded mean over its outcomes that serve the programme outcome.")
    matrix = mapping.course_matrix()
    t = _table(doc, ["Course", *codes], [[f"{code} {title}", *[str(cells.get(c, "")) for c in codes]]
                                         for code, title, cells in matrix],
               [course_w, *[(width - course_w) / max(1, len(codes))] * len(codes)])
    for row in t.rows[1:]:
        for cell in row.cells[1:]:
            if cell.text in ("1", "2", "3"):
                _shade(cell, SHADE[int(cell.text)])
                if cell.text == "3":
                    for run in cell.paragraphs[0].runs:
                        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    summary = mapping.po_summary()
    sums = t.add_row().cells
    sums[0].text = "Courses serving"
    for cell, (_, n, _) in zip(sums[1:], summary):
        cell.text = str(n)
    for cell, w in zip(sums, [course_w, *[(width - course_w) / max(1, len(codes))] * len(codes)]):
        cell.width = Inches(w)

    # ----- 4. attainment ---------------------------------------------------------------------
    _page(doc.add_section())
    doc.add_heading("4. Attainment" + (f": batch {attainment.data.batch}" if attainment and attainment.data.batch else ""),
                    level=1)
    if attainment is None:
        _note(doc, "No attainment results were given for this draft.")
    else:
        pol = attainment.policy
        words = policy_words(attainment)
        doc.add_paragraph(f"Policy: {pol.name}. {words[0].upper()}{words[1:]} A programme outcome's attainment is the "
                          "attainment of the course outcomes that serve it, weighted by their mapping strength.")
        doc.add_paragraph(f"{len(attainment.attained())} of {len(attainment.assessed)} assessed course outcomes reached "
                          f"the target level of {pol.target_level:g}.")
        doc.add_heading("Programme outcome attainment", level=3)
        _table(doc, ["PO", "Attainment", "Course outcomes", "Against target"],
               [[f"{code} {name}".strip(), _fmt(value), str(n),
                 "no data" if value is None else ("met" if value >= pol.target_level - 1e-9 else "below")]
                for code, name, value, n in attainment.po_values],
               [PORTRAIT_WIDTH - 3.6, 1.1, 1.3, 1.2])
        doc.add_heading("Course outcome attainment", level=3)

        def share_cell(c, kind):
            return f"{100 * c.shares[kind]:.0f}% → {c.levels[kind]}" if kind in c.levels else "–"
        _table(doc, ["CO", "Internal", "External", "Survey", "Overall"],
               [[c.label, share_cell(c, "internal"), share_cell(c, "external"), share_cell(c, "survey"),
                 _fmt(c.overall) + (f" ({'; '.join(c.notes)})" if c.notes else "")] for c in attainment.cos],
               [1.4, 1.15, 1.15, 1.15, PORTRAIT_WIDTH - 4.85])

    # ----- 5. actions ---------------------------------------------------------------------------
    doc.add_heading("5. Actions for outcomes below target", level=1)
    _note(doc, "For the department to complete: what was done for each outcome below the target level.")
    below = ([c for c in attainment.assessed if c.overall < attainment.policy.target_level - 1e-9]
             if attainment else [])
    rows = ([[c.label, _fmt(c.overall), "", "", ""] for c in sorted(below, key=lambda c: c.overall)]
            or [["", "", "", "", ""]])
    _table(doc, ["CO", "Attainment", "Action taken", "Responsible", "By when"], rows,
           [1.3, 1.0, PORTRAIT_WIDTH - 4.4, 1.2, 0.9])

    # ----- 6. method -------------------------------------------------------------------------------
    doc.add_heading("6. How this was prepared", level=1)
    doc.add_paragraph("Outcome levels come from a fixed list of action verbs for each level of the revised Bloom's "
                      "taxonomy; with several opening verbs the highest counts. The CO–PO mapping matches each outcome "
                      "against indicator verbs, topics and words for each programme outcome. Attainment follows the "
                      "policy in section 4, from counts of students assessed and students reaching the target in each "
                      "assessment. No AI is used: every figure can be traced to an outcome's wording or a count.")
    return doc


def to_bytes(doc: Document) -> bytes:
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
