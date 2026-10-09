"""Core vs elective coverage: what counts as an elective, the basis of each covered skill,
and how reports present the split."""
import json
import textwrap

import pytest

from curintel.analysis import benchmark, profile
from curintel.report import render_html, to_dict
from curintel.schema import Course, Programme


def programme(name, *courses):
    """(title, topics, category) triples."""
    return Programme(institution=name, name="B.Sc.",
                     courses=[Course(code=f"C{i}", title=t, credits=4, topics=tp, category=cat)
                              for i, (t, tp, cat) in enumerate(courses)])


@pytest.mark.parametrize("category,elective", [
    ("Core", False), ("", False), ("Project", False), ("Generic", False),
    ("Elective", True), ("DSE (elective)", True), ("DSE", True), ("GE", True),
    ("Skill enhancement (elective basket)", True), ("Optional paper", True), ("Choice based", True),
])
def test_is_elective(category, elective):
    assert Course(code="X", title="T", category=category).is_elective is elective


def test_core_only_profile_ignores_electives(tax):
    p = programme("P", ("Calculus", [], "Core"), ("Python", [], "Elective"))
    assert profile(p, tax)["python"].level == "covered"
    assert profile(p, tax, core_only=True)["python"].level == "absent"


def test_basis_and_core_share(tax):
    own = programme("Own", ("Calculus", [], "Core"), ("Graph Theory", [], "DSE"))
    peers = [
        programme("A", ("Python Programming", [], "Core")),
        programme("B", ("Python Programming", [], "Elective")),
        # core courses mention it once and an elective once: covered overall, but not by the core alone
        programme("C", ("Algebra", ["NumPy arrays"], "Core"), ("Lab", ["Matplotlib plots"], "Elective")),
        programme("D", ("Topology", [], "Core")),
    ]
    b = benchmark(own, peers, tax)
    py = next(r for r in b.rows if r.skill == "python")
    assert py.peer_basis == {"A": "core", "B": "elective", "C": "elective"}
    assert py.peer_core_share == 0.25 and py.peer_share == 0.75
    assert (py.status, py.priority) == ("gap", "High")      # classification still uses everything offered
    assert sorted(py.peers_core) == ["A"] and sorted(py.peers_elective_only) == ["B", "C"]
    graph = next(r for r in b.rows if r.skill == "graph_theory")
    assert graph.own_basis == "elective"
    assert next(r for r in b.rows if r.skill == "calculus").own_basis == "core"
    assert next(r for r in b.rows if r.skill == "topology").own_basis is None
    assert b.records_electives == ["Own", "B", "C"]


def test_reports_show_the_split(tax):
    own = programme("Own", ("Calculus", [], "Core"))
    peers = [programme("A", ("Python Programming", [], "Core")), programme("B", ("Python Programming", [], "Elective"))]
    b = benchmark(own, peers, tax)
    html = render_html(b, [])
    assert "(2 of 2: in the core of 1, only as an elective in 1)" in html
    assert "<i>(elective only; an elective course on it: Python Programming)</i>" in html
    # the cell itself, not the legend (which always shows ○)
    assert ("<td class='c-elective' title='B: Covered only by electives (an elective course on it)'>○</td>"
            in html)
    assert "<td class='c-course' title='A: A core course on it'>●</td>" in html
    assert "Programmes that record no electives" in html and "Own, A" in html
    d = to_dict(b, [])
    py = next(s for s in d["skills"] if s["id"] == "python")
    assert py["peer_basis"] == {"A": "core", "B": "elective"} and py["peer_core_share"] == 0.5
    assert d["records_electives"] == ["B"]
    json.dumps(d)                                            # still serialisable


def test_equal_gaps_sort_by_core_share(tax):
    own = programme("Own", ("Calculus", [], "Core"))
    # MATLAB and Python: each covered by both peers, but MATLAB only as an elective in one.
    # Alphabetically MATLAB comes first, so only the core share can put Python ahead.
    peers = [programme("A", ("MATLAB Lab", [], "Elective"), ("Python Programming", [], "Core")),
             programme("B", ("MATLAB Lab", [], "Core"), ("Python Programming", [], "Core"))]
    gaps = [r.skill for r in benchmark(own, peers, tax).by_status("gap")]
    assert gaps.index("python") < gaps.index("matlab")


def test_no_split_when_no_peer_records_electives(tax):
    own = programme("Own", ("Calculus", [], "Core"), ("Graph Theory", [], "Elective"))
    peers = [programme("A", ("Python Programming", [], "")), programme("B", ("Python Programming", [], "Core"))]
    html = render_html(benchmark(own, peers, tax), [])
    assert "(2 of 2) but" in html and "in the core of" not in html
    assert "core 100%" not in html


def test_profile_category_rules(tmp_path, monkeypatch):
    from curintel import pdfimport
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    monkeypatch.setattr(pdfimport, "read_pdf", lambda path, spec=None: [(1, (
        "MAC101: Calculus\nCourse Contents:\nLimits\nEnd\n"
        "MAE201: Graph Theory\nCourse Contents:\nTrees\nEnd\n"
        "MAS301: Python\nCourse Contents:\nLists\nEnd\n"))])
    prof = tmp_path / "p.yaml"
    prof.write_text(textwrap.dedent("""\
        institution: U
        name: P
        files: [{path: s.pdf}]
        course_start: '^(?P<code>MA[CES]\\d{3}):\\s*(?P<title>.+)$'
        content_start: 'Course Contents:'
        content_end: 'End'
        category: Core
        categories:
          - {match: '^MAE', category: Discipline elective}
          - {match: 'python', category: Skill (elective)}
        extra_courses:
          - {code: MAE999, title: Cryptography, topics: []}
          - {code: MAC998, title: Seminar, topics: [], category: Project}
        """))
    d = pdfimport.extract(prof)
    cats = {c.course.code: c.course.category for c in d.courses}
    assert cats == {"MAC101": "Core", "MAE201": "Discipline elective", "MAS301": "Skill (elective)",
                    "MAE999": "Discipline elective", "MAC998": "Project"}

    prof.write_text(prof.read_text().replace("- {match: '^MAE', category: Discipline elective}", "- {category: X}"))
    with pytest.raises(pdfimport.ProfileError, match="needs match and category"):
        pdfimport.extract(prof)
