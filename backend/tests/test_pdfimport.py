"""PDF import. Real PDFs are replaced by page text we control (read_pdf is patched),
so each profile option can be tested exactly; reading a real PDF is pdfplumber's job."""
import json
import textwrap

import pytest

from curintel import pdfimport
from curintel.cli import main
from curintel.importers import from_workbook, write_template
from curintel.pdfimport import (ProfileError, _page_set, extract, repair_split_words, topics_from,
                                vocabulary)
from conftest import prog


@pytest.fixture
def pages(monkeypatch):
    """Map file name -> list of page texts; read_pdf serves them (honouring `pages`)."""
    store: dict[str, list[str]] = {}

    def fake_read(path, spec=None):
        texts = store[path.name]
        wanted = _page_set(spec, len(texts))
        return [(i, t) for i, t in enumerate(texts, start=1) if i in wanted]

    monkeypatch.setattr(pdfimport, "read_pdf", fake_read)
    return store


def make(tmp_path, pages, yaml_text, docs):
    """Write a profile and empty stand-in PDFs; register their page texts."""
    for name, texts in docs.items():
        (tmp_path / name).write_bytes(b"%PDF-")
        pages[name] = [textwrap.dedent(t) for t in texts]
    prof = tmp_path / "profile.yaml"
    prof.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    return prof


BASIC = """\
institution: Test University
name: B.Sc. Mathematics
files:
  - {path: s.pdf, semester: I}
course_start: '^(?P<code>MAT\\d{3}):\\s*(?P<title>.+)$'
content_start: 'Course Contents:'
content_end: 'Books Recommended'
"""

DOC = ["""\
    MAT101: Calculus
    Course Contents:
    Limits and continuity, Mean value theorems; Taylor series.
    Books Recommended
    1. Apostol, Calculus (a book title that must not count)
    MAT102: LINEAR ALGEBRA
    Course Contents:
    Vector spaces, Eigenvalues and eigenvectors.
    Books Recommended
    1. Strang
    """]


def codes(draft):
    return [d.course.code for d in draft.courses]


# ----- text helpers ------------------------------------------------------

def test_page_set():
    assert _page_set(None, 3) == {1, 2, 3}
    assert _page_set("2-4, 7", 10) == {2, 3, 4, 7}
    assert _page_set("5-99", 6) == {5, 6}


def test_repair_split_words():
    vocab = {"gradient", "theorem", "double"}
    assert repair_split_words("Gradie nt of a scalar field", vocab) == "Gradient of a scalar field"
    assert repair_split_words("Green's T heorem", vocab) == "Green's Theorem"
    # both halves are words in their own right: leave alone
    assert repair_split_words("in to the set", {"in", "to", "into", "the", "set"}) == "in to the set"


def test_vocabulary_counts_words_seen_twice():
    v = vocabulary(["Gradient of field. Gradient vector", "field lines"], extra={"curl"})
    assert {"gradient", "field", "curl"} <= v
    assert "vector" not in v and "of" not in v


def test_topics_from_splits_and_strips():
    text = "Unit 1 (12 hours)\nLimits, Continuity; Differentia-\ntion 25%\n1.1 Taylor series\n• Maclaurin series"
    assert topics_from(text, []) == ["Limits", "Continuity", "Differentiation", "Taylor series", "Maclaurin series"]


def test_topics_from_extra_split_and_custom_strip():
    text = "Bisection method-Fixed point iteration- Newton's method (Sections: 2.1)"
    assert topics_from(text, [], extra_split=r"(?<=[a-z])-(?=[A-Z])|-\s") == \
        ["Bisection method", "Fixed point iteration", "Newton's method", "Sections"]
    assert topics_from(text, [r"\(Sections?:[^)]*\)"], extra_split=r"-\s|(?<=[a-z])-(?=[A-Z])")[-1] == "Newton's method"


# ----- profiles ----------------------------------------------------------

def test_basic_extraction(tmp_path, pages):
    d = extract(make(tmp_path, pages, BASIC, {"s.pdf": DOC}))
    assert codes(d) == ["MAT101", "MAT102"]
    calc, lin = (x.course for x in d.courses)
    assert calc.topics == ["Limits and continuity", "Mean value theorems", "Taylor series"]
    assert lin.title == "Linear Algebra"            # ALL CAPS titles are tidied
    assert calc.semester == "I"
    assert not any("Apostol" in t for t in calc.topics)
    assert d.programme.institution == "Test University"


def test_include_exclude_and_report(tmp_path, pages):
    y = BASIC + "include: '^MAT1'\nexclude: 'LINEAR'\n"
    d = extract(make(tmp_path, pages, y, {"s.pdf": DOC}))
    assert codes(d) == ["MAT101"]
    assert d.excluded == [("MAT102", "Linear Algebra", "matched exclude")]
    only = extract(make(tmp_path, pages, BASIC + "include: '^MAT101'\n", {"s.pdf": DOC}))
    assert codes(only) == ["MAT101"]
    assert only.excluded == [("MAT102", "Linear Algebra", "not matched by include")]


def test_warnings_when_markers_missing(tmp_path, pages):
    doc = ["MAT101: Calculus\nLimits, Derivatives\n"]
    d = extract(make(tmp_path, pages, BASIC, {"s.pdf": doc}))
    w = d.courses[0].warnings
    assert any("content start not found" in x for x in w)


def test_skip_lines_and_pages(tmp_path, pages):
    doc = ["Contents page\nMAT999: Not a course page",
           textwrap.dedent(DOC[0]).replace("Vector spaces", "RUNNING HEADER\nVector spaces")]
    y = BASIC.replace("{path: s.pdf, semester: I}", '{path: s.pdf, semester: I, pages: "2"}') + \
        "skip_lines: ['RUNNING HEADER']\n"
    d = extract(make(tmp_path, pages, y, {"s.pdf": doc}))
    assert codes(d) == ["MAT101", "MAT102"]
    assert not any("RUNNING" in t for t in d.courses[1].course.topics)


def test_parts_sharing_a_code_are_merged(tmp_path, pages):
    doc = ["MAT101: Calculus (Part-1)\nCourse Contents:\nLimits\nBooks Recommended\n"
           "MAT101: Calculus (Part-2)\nCourse Contents:\nIntegrals\nBooks Recommended\n"]
    d = extract(make(tmp_path, pages, BASIC, {"s.pdf": doc}))
    assert codes(d) == ["MAT101"]
    assert d.courses[0].course.topics == ["Limits", "Integrals"]
    assert d.merged and d.merged[0][0] == "MAT101"


def test_duplicates_number_keeps_alternatives(tmp_path, pages):
    doc = ["MAT501: Graph Theory\nCourse Contents:\nTrees\nBooks Recommended\n"
           "MAT501: Cryptography\nCourse Contents:\nRSA\nBooks Recommended\n"
           "MAT501: Topology\nCourse Contents:\nCompactness\nBooks Recommended\n"]
    d = extract(make(tmp_path, pages, BASIC + "duplicates: number\n", {"s.pdf": doc}))
    assert codes(d) == ["MAT501", "MAT501/2", "MAT501/3"]
    assert [x.course.title for x in d.courses] == ["Graph Theory", "Cryptography", "Topology"]


def test_bad_duplicates_value(tmp_path, pages):
    with pytest.raises(ProfileError, match="duplicates"):
        extract(make(tmp_path, pages, BASIC + "duplicates: drop\n", {"s.pdf": DOC}))


def test_aliases_titles_and_credits(tmp_path, pages):
    doc = ["MA101: CALCULUS\nTotal Credits 4\nCourse Contents:\nLimits\nBooks Recommended\n"]
    y = BASIC.replace("MAT\\d{3}", "MAT?\\d{3}") + textwrap.dedent("""\
        aliases: {MA101: MAT101}
        titles: {MAT101: Calculus I}
        credits: 'Total Credits\\s*(?P<credits>\\d+)'
        """)
    d = extract(make(tmp_path, pages, y, {"s.pdf": doc}))
    c = d.courses[0].course
    assert (c.code, c.title, c.credits) == ("MAT101", "Calculus I", 4)


def test_kind_and_num_groups_make_codes(tmp_path, pages):
    doc = ["DISCIPLINE SPECIFIC CORE COURSE - 13: METRIC SPACES\nSYLLABUS OF DSC-13\nOpen balls\nEssential Readings\n"
           "DISCIPLINE SPECIFIC ELECTIVE COURSE - 3(i): DATA SCIENCE\nSYLLABUS OF DSE\nPython\nEssential Readings\n"]
    y = textwrap.dedent("""\
        institution: U
        name: P
        files: [{path: s.pdf}]
        course_start: '^DISCIPLINE SPECIFIC (?P<kind>CORE|ELECTIVE) COURSE\\s*-\\s*(?P<num>\\d+\\s*(?:\\([ivx]+\\))?)\\s*:\\s*(?P<title>.*)$'
        kind_codes: {CORE: DSC, ELECTIVE: DSE}
        content_start: 'SYLLABUS OF'
        content_end: 'Essential Readings'
        """)
    d = extract(make(tmp_path, pages, y, {"s.pdf": doc}))
    assert codes(d) == ["DSC-13", "DSE-3(i)"]


def test_header_before_brings_in_title_line(tmp_path, pages):
    doc = ["Course Code Title of the MULTIVARIATE CALCULUS\nUS03MAMTH02\nTotal Credits 4\n"
           "Course Content\nGradient, Divergence\nTeaching\n"]
    y = textwrap.dedent("""\
        institution: U
        name: P
        files: [{path: s.pdf}]
        course_start: '^(?P<code>US\\d{2}MAMTH\\d{2})\\b'
        header_before: '^Course Code'
        title_strip: ['Course Code', 'Title of the']
        title_end: 'Total Credits'
        content_start: 'Course Content'
        content_end: 'Teaching'
        """)
    c = extract(make(tmp_path, pages, y, {"s.pdf": doc})).courses[0].course
    assert (c.code, c.title, c.topics) == ("US03MAMTH02", "Multivariate Calculus", ["Gradient", "Divergence"])


def test_header_lines_before_does_not_leak_into_previous_course(tmp_path, pages):
    doc = ["Calculus\nSemester : 1 Credits : 5+1*=6\nCore Course-1 Full Marks : 100\nUnit-1 : Limits,\nDerivatives\n"
           "Algebra\nSemester : 1 Credits : 6\nCore Course-2 Full Marks : 100\nUnit-1 : Groups\n"]
    y = textwrap.dedent("""\
        institution: U
        name: P
        files: [{path: s.pdf}]
        course_start: '^(?P<code>Core Course-\\d+)\\s*Full Marks'
        header_lines_before: 2
        title: '\\A(?P<title>[^\\n]+)'
        credits: 'Credits\\s*:\\s*(?:[\\d+*]+=)?(?P<credits>\\d+)'
        semester: 'Semester\\s*:\\s*(?P<semester>\\d)'
        content_start: '(?m)^Unit'
        """)
    d = extract(make(tmp_path, pages, y, {"s.pdf": doc}))
    calc, alg = (x.course for x in d.courses)
    assert (calc.title, calc.credits, calc.semester) == ("Calculus", 6, "1")
    assert (alg.title, alg.credits) == ("Algebra", 6)
    assert "Algebra" not in calc.topics            # next course's title line stays with it
    assert calc.topics == ["Limits", "Derivatives"]


def test_extra_courses_and_hand_built_profile(tmp_path, pages):
    y = BASIC + textwrap.dedent("""\
        extra_courses:
          - {code: MAT900, title: Cryptography, topics: [RSA], note: typed from scanned page 9}
        """)
    d = extract(make(tmp_path, pages, y, {"s.pdf": DOC}))
    extra = d.courses[-1]
    assert extra.course.code == "MAT900" and extra.warnings == ["manual: typed from scanned page 9"]

    hand = tmp_path / "hand.yaml"
    hand.write_text("institution: U\nname: P\nextra_courses:\n  - {code: X1, title: Calculus, topics: []}\n")
    assert codes(extract(hand)) == ["X1"]


def test_extra_course_clashing_with_pdf_course(tmp_path, pages):
    y = BASIC + "extra_courses:\n  - {code: MAT101, title: Dup, topics: []}\n"
    with pytest.raises(ProfileError, match="also found in the PDFs"):
        extract(make(tmp_path, pages, y, {"s.pdf": DOC}))


@pytest.mark.parametrize("yaml_text,message", [
    ("name: P\nfiles: [{path: s.pdf}]\ncourse_start: x\n", "missing 'institution'"),
    ("institution: U\nname: P\nfiles: [{path: s.pdf}]\n", "missing 'course_start'"),
    ("institution: U\nname: P\n", "needs 'files' or 'extra_courses'"),
    ("institution: U\nname: P\nfiles: [{path: s.pdf}]\ncourse_start: '(unclosed'\n", "bad regular expression"),
    ("institution: U\nname: P\nfiles: [{path: missing.pdf}]\ncourse_start: x\n", "file not found"),
    ("institution: [unclosed\n", "not valid YAML"),
])
def test_profile_errors(tmp_path, pages, yaml_text, message):
    (tmp_path / "s.pdf").write_bytes(b"%PDF-")
    pages["s.pdf"] = ["nothing"]
    prof = tmp_path / "p.yaml"
    prof.write_text(yaml_text)
    with pytest.raises(ProfileError, match=message):
        extract(prof)


def test_no_courses_found(tmp_path, pages):
    with pytest.raises(ProfileError, match="no courses found"):
        extract(make(tmp_path, pages, BASIC, {"s.pdf": ["Just a cover page"]}))


def test_split_word_repair_runs_on_titles_and_topics(tmp_path, pages):
    doc = ["MAT201: Vector Calc ulus\nCourse Contents:\nGradie nt, Diverg ence\nBooks Recommended\n"
           "MAT202: More\nCourse Contents:\nGradient fields, Divergence theorem, Calculus of variations,\n"
           "Gradient flows, Divergence free, Calculus on manifolds\nBooks Recommended\n"]
    d = extract(make(tmp_path, pages, BASIC, {"s.pdf": doc}))
    first = d.courses[0].course
    assert first.title == "Vector Calculus"
    assert first.topics == ["Gradient", "Divergence"]


# ----- writing the draft, and the command -------------------------------

def test_filled_template_round_trips(tmp_path):
    p = prog("Round Trip U", ("Calculus", ["Limits", "Derivatives"]), ("Algebra", ["Groups"]))
    path = tmp_path / "draft.xlsx"
    write_template(path, p)
    back = from_workbook(path)
    assert back.institution == "Round Trip U"
    assert [(c.code, c.title, c.topics) for c in back.courses] == [(c.code, c.title, c.topics) for c in p.courses]


def test_cli_extract_pdf(tmp_path, pages, capsys):
    prof = make(tmp_path, pages, BASIC + "exclude: LINEAR\n", {"s.pdf": DOC})
    out = tmp_path / "draft.json"
    assert main(["extract-pdf", str(prof), "-o", str(out)]) == 0
    assert [c["code"] for c in json.loads(out.read_text())["courses"]] == ["MAT101"]
    printed = capsys.readouterr().out
    assert "1 courses written" in printed and "Left out (1)" in printed

    xlsx = tmp_path / "draft.xlsx"
    assert main(["extract-pdf", str(prof), "-o", str(xlsx)]) == 0
    assert from_workbook(xlsx).courses[0].code == "MAT101"

    bad = tmp_path / "bad.yaml"
    bad.write_text("institution: U\nname: P\n")
    assert main(["extract-pdf", str(bad), "-o", str(out)]) == 1
    assert "needs 'files'" in capsys.readouterr().err
