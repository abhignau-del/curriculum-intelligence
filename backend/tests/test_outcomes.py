"""Course outcomes: extraction from PDFs, Bloom's levels from verbs, checks, and reports."""
import json
import textwrap

import pytest

from curintel.cli import main
from curintel.outcomes import Bloom, BloomError, analyse_outcomes
from curintel.pdfimport import outcomes_from
from curintel.report import outcomes_dict, render_html, render_outcomes_html, to_dict
from curintel.schema import Course, Programme, load_programme
from conftest import SAMPLES

BLOOM = Bloom.builtin()


# ----- verbs and levels ------------------------------------------------------

@pytest.mark.parametrize("text,level,verbs,vague", [
    ("Solve linear differential equations", 3, ["solve"], False),
    ("Students will be able to prove Lagrange's theorem", 5, ["prove"], False),
    ("The learner will be able to define a group", 1, ["define"], False),
    ("CO2: Explain the concept of a ring", 2, ["explain"], False),
    ("Identify and classify an ordinary differential equation", 2, ["identify", "classify"], False),
    ("Apply, analyse and implement numerical methods", 4, ["apply", "analyse", "implement"], False),
    ("Solves equations", 3, ["solve"], False),                       # inflected forms
    ("Plotted graphs of functions", 3, ["plot", "graph"], False),
    ("Applies the chain rule", 3, ["apply"], False),
    ("Make use of tables", 3, ["make use of"], False),               # phrases before words
    ("Construct a model of population growth", 6, ["construct a model"], False),
    ("Construct a truth table", 3, ["construct"], False),
    ("Evaluate the integral by substitution", 3, ["evaluate the"], False),
    ("Evaluate competing models", 5, ["evaluate"], False),
    ("Effectively use Python", 3, ["use"], False),                    # an adverb before the verb
    ("Apply results of mechanics", 3, ["apply"], False),              # not an adverb, although -ly
    ("ApplyknowledgeofOrdinaryDifferentialEquations", 3, ["apply"], False),   # fused by the PDF
    ("Understand basic concepts of group theory", 2, ["understand"], True),
    ("Develop an understanding of cosets", 2, ["develop an understanding"], True),
    ("Develop a program for root finding", 6, ["develop"], False),
    ("Learn some Pandas code", None, ["learn"], True),
    ("Take up an intermediate course in graph theory", None, ["take up"], True),
    ("Knowledge of matrices in future courses", None, [], False),     # not "know" fused to a word
    ("Statements of the main theorems", None, [], False),
    ("", None, [], False),
])
def test_classify(text, level, verbs, vague):
    assert BLOOM.classify(text) == (level, verbs, vague)


def test_verb_list_checks():
    base = {"levels": [{"level": 1, "id": "r", "name": "R", "verbs": ["define"]},
                       {"level": 3, "id": "a", "name": "A", "verbs": ["define"]}]}
    with pytest.raises(BloomError, match="listed under two levels"):
        Bloom.from_dict(base)
    with pytest.raises(BloomError, match="missing a field"):
        Bloom.from_dict({"levels": [{"level": 1, "verbs": ["x"]}]})
    b = Bloom.from_dict({"name": "Mine", "levels": [{"level": 2, "id": "u", "name": "U", "verbs": ["explain"]}],
                         "vague": {"grasp": None}})
    assert b.classify("Explains rings") == (2, ["explain"], False) and b.classify("Grasp it") == (None, ["grasp"], True)


def test_builtin_list_has_six_levels_and_no_verb_twice():
    assert [lv.name for lv in BLOOM.levels] == ["Remember", "Understand", "Apply", "Analyse", "Evaluate", "Create"]


# ----- the programme ------------------------------------------------------------

def prog(*courses):
    """(code, semester, outcomes) triples."""
    return Programme(institution="U", name="B", courses=[
        Course(code=c, title=f"Course {c}", semester=s, outcomes=o) for c, s, o in courses])


def test_analysis_flags_and_groups():
    p = prog(("A", "I", ["Define a limit", "Understand continuity", "Use mathematical software"]),
             ("B", "II", ["Use mathematical software.", "Prove the mean value theorem"]),
             ("C", "V", ["Analyse convergence", "Design an experiment", "Knowledge of series"]),
             ("D", "VI", []), ("E", None, ["Solve equations"]))
    rep = analyse_outcomes(p)
    assert len(rep.results) == 9 and rep.courses_with_outcomes == 4
    assert rep.without_outcomes == [("D", "Course D")]
    assert [r.text for r in rep.flagged("vague")] == ["Understand continuity"]
    assert [r.text for r in rep.flagged("no_verb")] == ["Knowledge of series"]
    assert rep.duplicates == [("Use mathematical software", ["A", "B"])]       # punctuation ignored
    assert {r.course_code for r in rep.flagged("duplicate")} == {"A", "B"}
    years = dict(rep.by_year())
    assert list(years) == ["Year 1", "Year 3", ""]                           # unknown semester last
    assert rep.higher_order_share(years["Year 1"]) == pytest.approx(1 / 5)   # prove, of 5 rated
    assert rep.higher_order_share(years["Year 3"]) == 1.0                    # the no-verb one is not rated
    assert rep.counts(years["Year 3"])[None] == 1
    assert rep.higher_order_share([]) is None


def test_same_outcome_twice_in_one_course_is_not_a_duplicate():
    rep = analyse_outcomes(prog(("A", "I", ["Solve equations", "Solve equations."])))
    assert rep.duplicates == []


# ----- extraction from PDFs ------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Having completed this course, the learner will be able to\n1. Students will realize the power of calculus.\n"
     "2. Students will be able to find areas using integrals.",
     ["Realize the power of calculus", "Find areas using integrals"]),
    ("CO1: Explain the concept of groups.\nCO2: Prove Lagrange theorem.\nCO3 - Solve problems on rings",
     ["Explain the concept of groups", "Prove Lagrange theorem", "Solve problems on rings"]),
    ("• Define a metric\n• Prove the\ncontraction mapping theorem", ["Define a metric", "Prove the contraction mapping theorem"]),
    ("After completion of the course, students will be able to compute limits of functions. They will prove "
     "standard theorems on continuity.", ["Compute limits of functions", "Prove standard theorems on continuity"]),
    ("1. Ok\n2. Solve linear systems", ["Solve linear systems"]),                # too short to be an outcome
])
def test_outcomes_from(text, expected):
    assert outcomes_from(text) == expected


def test_profile_reads_outcomes(tmp_path, monkeypatch):
    from curintel import pdfimport
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    monkeypatch.setattr(pdfimport, "read_pdf", lambda path, spec=None: [(1, (
        "MAC101: Calculus\nCourse Contents:\nLimits\nEnd\nCourse Outcomes:\n1. Compute limits of functions\n"
        "2. Prove the mean value theorem\nReferences\nBook\n"
        "MAC101: Calculus\nCourse Contents:\nSeries\nEnd\nCourse Outcomes:\n1. Test series for convergence\nReferences\n"
        "MAC102: Algebra\nCourse Contents:\nGroups\nEnd\n"))])
    prof = tmp_path / "p.yaml"
    prof.write_text(textwrap.dedent("""\
        institution: U
        name: P
        files: [{path: s.pdf}]
        course_start: '^(?P<code>MA[CES]\\d{3}):\\s*(?P<title>.+)$'
        content_start: 'Course Contents:'
        content_end: 'End'
        outcomes_start: 'Course Outcomes:'
        outcomes_end: 'References'
        """))
    d = pdfimport.extract(prof)
    calc, alg = d.courses
    assert calc.course.outcomes == ["Compute limits of functions", "Prove the mean value theorem",
                                    "Test series for convergence"]          # both parts merged
    assert calc.course.topics == ["Limits", "Series"]                       # outcomes kept out of topics
    assert alg.course.outcomes == [] and "no outcomes found" in alg.warnings


# ----- reports ------------------------------------------------------------------

def test_sample_programme_outcomes():
    rep = analyse_outcomes(load_programme(SAMPLES / "riverside.json"))
    assert len(rep.results) == 77 and not rep.without_outcomes
    assert len(rep.flagged("vague")) == 16 and len(rep.duplicates) == 1
    shares = [rep.higher_order_share(rs) for _, rs in rep.by_year()]
    assert shares == [0.0, 0.0, pytest.approx(2 / 3)]


def test_outcomes_report_and_json():
    rep = analyse_outcomes(prog(("A", "I", ["Understand <b>limits</b>", "Prove theorems"]), ("B", "III", [])))
    html = render_outcomes_html(rep)
    assert "<h2>Course outcomes</h2>" in html and "Understand &lt;b&gt;limits&lt;/b&gt;" in html
    assert "2 outcomes in 1 of 2 courses · 50% higher-order · 1 vague (50%)" in html
    assert "1 course states no outcomes" in html
    assert "<b>B</b> Course B" in html                                      # courses without outcomes
    d = outcomes_dict(rep)
    assert d["by_year"][0]["year"] == "Year 1" and d["by_year"][0]["levels"]["5"] == 1
    assert d["outcomes"][0]["flags"] == ["vague"] and d["without_outcomes"][0]["course"] == "B"
    json.dumps(d)
    empty = render_outcomes_html(analyse_outcomes(prog(("A", "I", []))))
    assert "No course in this programme states its outcomes." in empty


def test_benchmark_report_includes_outcomes_only_when_stated(riverside, peers, tax, tmp_path):
    from curintel.analysis import benchmark
    b = benchmark(riverside, peers, tax)
    rep = analyse_outcomes(riverside)
    assert "<h2>Course outcomes</h2>" in render_html(b, [], [], rep)
    assert "<h2>Course outcomes</h2>" not in render_html(b, [])
    assert to_dict(b, [], [], rep)["outcomes"]["higher_order_share"] == pytest.approx(rep.higher_order_share(rep.results))
    assert to_dict(b, [])["outcomes"] is None
    # the command line adds it by itself when the programme states outcomes
    out = tmp_path / "r.html"
    assert main(["report", str(SAMPLES / "riverside.json"), str(SAMPLES / "peers"), "-o", str(out)]) == 0
    assert "<h2>Course outcomes</h2>" in out.read_text(encoding="utf-8")


def test_cli_outcomes(tmp_path, capsys):
    assert main(["outcomes", str(SAMPLES / "riverside.json"), "-o", str(tmp_path / "o.html"),
                 "--json", str(tmp_path / "o.json")]) == 0
    out = capsys.readouterr().out
    assert "77 outcomes in 23 of 23 courses" in out and "Year 3: 21 outcomes" in out
    assert "<h2>Course outcomes</h2>" in (tmp_path / "o.html").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "o.json").read_text())["higher_order_share"] > 0
    verbs = tmp_path / "v.yaml"
    verbs.write_text("levels: [{level: 1, id: r, name: R, verbs: [state]}]\n")
    assert main(["outcomes", str(SAMPLES / "riverside.json"), "--verbs", str(verbs)]) == 0


def test_years_come_out_in_order_whatever_the_course_order():
    rep = analyse_outcomes(prog(("A", "V", ["Prove theorems"]), ("B", None, ["Solve equations"]),
                                ("C", "I", ["Define limits"]), ("D", "IV", ["Explain series"])))
    assert [y for y, _ in rep.by_year()] == ["Year 1", "Year 2", "Year 3", ""]


def test_json_counts_outcomes_without_a_level_under_none():
    d = outcomes_dict(analyse_outcomes(prog(("A", "I", ["Learn limits", "Prove theorems"]))))
    assert d["by_year"][0]["levels"]["none"] == 1 and d["by_year"][0]["levels"]["5"] == 1
