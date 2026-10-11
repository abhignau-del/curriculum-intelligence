"""Regulatory checklist: rules files, the degree variant, credit rules on the credit scheme,
course rules on the courses, and how reports show it."""
import json
import textwrap

import pytest
from pydantic import ValidationError

from curintel.analysis import benchmark
from curintel.cli import main
from curintel.regulatory import Rules, RulesError, builtin_rules, check, semester_number
from curintel.report import render_html, to_dict
from curintel.schema import Course, Programme, SchemeItem, load_programme
from curintel.taxonomy import Taxonomy
from conftest import SAMPLES

TAX = Taxonomy.builtin()

UGC = Rules.builtin("ugc-ccfup-2022")
BASE = {
    "id": "t", "name": "Test Framework", "source": "https://example.org/rules.pdf",
    "variants": [{"id": "short", "name": "Short degree", "match": "short", "semesters": 2},
                 {"id": "long", "name": "Long degree", "match": "long", "semesters": 4}],
    "categories": [{"id": "proj", "name": "Project", "match": "project"},
                   {"id": "core", "name": "Core", "match": "core|major"}],
}


def rules(*rs, **over):
    return Rules.from_dict({**BASE, "rules": list(rs), **over})


def programme(scheme=(), degree="", courses=None, semesters=("1",)):
    courses = courses or [Course(code=f"C{s}", title="Calculus", semester=s) for s in semesters]
    return Programme(institution="U", name="B.Sc.", degree=degree, courses=courses,
                     scheme=[SchemeItem(category=c, credits=cr, semester=s) for c, cr, s in scheme])


def result(cl, rule_id):
    return next(r for r in cl.results if r.rule.id == rule_id)


# ----- rules files ---------------------------------------------------------

def test_builtin_rules_load_and_cite_pages():
    assert "ugc-ccfup-2022" in builtin_rules()
    assert [v.id for v in UGC.variants] == ["4-year-research", "4-year", "3-year"]
    assert all(r.page for r in UGC.rules) and all(r.text for r in UGC.rules)
    assert result_rule(UGC, "major-credits").minimum("3-year") == 60
    assert result_rule(UGC, "major-credits").minimum("4-year") == 80
    assert result_rule(UGC, "research-credits").minimum("4-year") is None   # only with research


def result_rule(rs, rid):
    return next(r for r in rs.rules if r.id == rid)


@pytest.mark.parametrize("bad,message", [
    ({"id": "x", "kind": "magic", "text": "t", "min": 1}, "unknown kind"),
    ({"id": "x", "kind": "category_credits", "category": "nope", "text": "t", "min": 1}, "unknown category"),
    ({"id": "x", "kind": "category_credits", "category": "core", "text": "t"}, "needs min"),
    ({"id": "x", "kind": "total_credits", "text": "t", "min": {"medium": 3}}, "unknown variant"),
    ({"id": "x", "kind": "course_on", "text": "t"}, "needs a skill"),
    ({"id": "x", "kind": "total_credits", "text": "t", "min": 1, "colour": "red"}, "missing or invalid"),
])
def test_bad_rules_are_explained(bad, message):
    with pytest.raises(RulesError, match=message):
        rules(bad)


def test_duplicate_ids_and_bad_patterns():
    r = {"id": "x", "kind": "total_credits", "text": "t", "min": 1}
    with pytest.raises(RulesError, match="share an id"):
        rules(r, r)
    with pytest.raises(RulesError, match="bad pattern"):
        rules(r, categories=[{"id": "c", "match": "(unclosed"}])


def test_resolve_file_or_builtin(tmp_path):
    f = tmp_path / "mine.yaml"
    f.write_text(json.dumps({**BASE, "rules": [{"id": "x", "kind": "total_credits", "text": "t", "min": 4}]}))
    assert Rules.resolve(str(f)).id == "t"
    assert Rules.resolve("ugc-ccfup-2022").id == "ugc-ccfup-2022"
    with pytest.raises(RulesError, match="no built-in rules named 'nope'"):
        Rules.resolve("nope")
    (tmp_path / "broken.yaml").write_text("rules: [")
    with pytest.raises(RulesError, match="not valid YAML"):
        Rules.load(tmp_path / "broken.yaml")


@pytest.mark.parametrize("text,n", [("VII", 7), ("Semester IV", 4), ("Sem. vi", 6), ("7", 7),
                                    ("Semester 3", 3), ("", None), (None, None), ("summer", None)])
def test_semester_number(text, n):
    assert semester_number(text) == n


# ----- the degree variant ---------------------------------------------------

@pytest.mark.parametrize("degree,semesters,expected", [
    ("4-year (Honours)", ("1",), "4-year"),
    ("Four year honours", ("1",), "4-year"),
    ("4-year Honours with Research", ("1",), "4-year-research"),
    ("3-year", ("I", "VIII"), "3-year"),            # a recorded degree beats the semesters
    ("", ("I", "VI"), "3-year"),
    ("", ("I", "VII"), "4-year"),                    # past semester 6: the 4-year degree
    ("", ("I", "VIII"), "4-year"),                   # never Honours with Research unless stated
])
def test_variant(degree, semesters, expected):
    cl = check(programme(degree=degree, semesters=semesters), UGC, TAX)
    assert cl.variant.id == expected


def test_variant_fallback_says_it_was_assumed():
    p = Programme(institution="U", name="B", courses=[Course(code="C", title="Calculus")])
    cl = check(p, UGC, TAX)
    assert cl.variant.id == "4-year-research"          # the first listed, as nothing else says
    assert cl.variant_basis.startswith("assumed")


# ----- credit rules ----------------------------------------------------------

def test_credit_rules_not_checked_without_a_scheme():
    cl = check(programme(), UGC, TAX)
    assert not cl.has_scheme
    assert {r.status for r in cl.results} == {"not_checked"}
    r = result(cl, "major-credits")
    assert (r.found, r.expected) == ("no credit scheme recorded", "at least 60 credits")   # semester 1: 3-year


@pytest.mark.parametrize("credits,status", [(10, "met"), (12, "met"), (9.5, "partly"), (0, "not_met")])
def test_category_credits_boundaries(credits, status):
    rs = rules({"id": "core", "kind": "category_credits", "category": "core", "text": "t", "min": 10})
    cl = check(programme([("Major", credits, "1"), ("Other", 1, "1")]), rs, TAX)
    assert result(cl, "core").status == status


def test_category_mapping_first_match_and_unmapped_labels():
    rs = rules({"id": "proj", "kind": "category_credits", "category": "proj", "text": "t", "min": 4},
               {"id": "core", "kind": "category_credits", "category": "core", "text": "t", "min": 6},
               {"id": "total", "kind": "total_credits", "text": "t", "min": 12})
    # "Core project" matches both patterns: the first category listed (proj) wins
    cl = check(programme([("Core project", 4, "1"), ("Major", 3, "1"), ("Major", 3, "2"),
                          ("Sports", 2, "2")]), rs, TAX)
    assert cl.category_credits == {"proj": 4, "core": 6}
    assert cl.unmapped == {"Sports": 2}
    assert [r.status for r in cl.results] == ["met", "met", "met"]       # unmapped still counts in the total
    assert result(cl, "core").evidence == ["Major, semester 1: 3", "Major, semester 2: 3"]


def test_per_variant_minimums_and_rules_that_do_not_apply():
    rs = rules({"id": "total", "kind": "total_credits", "text": "t", "min": {"short": 10, "long": 20}},
               {"id": "proj", "kind": "category_credits", "category": "proj", "text": "t", "min": {"long": 2}})
    short = check(programme([("Major", 12, "1")], degree="short"), rs, TAX)
    assert [r.rule.id for r in short.results] == ["total"] and short.results[0].status == "met"
    long_ = check(programme([("Major", 12, "1")], degree="long"), rs, TAX)
    assert [(r.rule.id, r.status) for r in long_.results] == [("total", "partly"), ("proj", "not_met")]


def test_category_share():
    rs = rules({"id": "share", "kind": "category_share", "category": "core", "text": "t", "min": 0.5})
    assert check(programme([("Major", 5, "1"), ("Other", 5, "1")]), rs, TAX).results[0].status == "met"
    r = check(programme([("Major", 4, "1"), ("Other", 6, "1")]), rs, TAX).results[0]
    assert r.status == "not_met" and r.found == "40% (4 of 10 credits)"


def test_riverside_sample_against_ugc():
    cl = check(load_programme(SAMPLES / "riverside.json"), UGC, TAX)
    assert cl.variant.id == "3-year"
    statuses = {r.rule.id: r.status for r in cl.results}
    assert statuses.pop("sec-credits") == "partly" and statuses.pop("vac-credits") == "partly"
    assert set(statuses.values()) == {"met"} and "research-credits" not in statuses
    assert result(cl, "vac-credits").expected == "at least 6 credits (6-8 in the framework)"


# ----- course rules ----------------------------------------------------------

COURSE_RULES = rules(
    {"id": "prob", "kind": "course_on", "skill": "probability", "text": "A probability course", "level": "advisory"},
    {"id": "any-py", "kind": "course_on", "skill": "python", "core": False, "text": "Any Python course"},
)


def course_check(*courses):
    p = Programme(institution="U", name="B", courses=[
        Course(code=f"C{i}", title=t, topics=tp, category=cat) for i, (t, tp, cat) in enumerate(courses)])
    return check(p, COURSE_RULES, TAX)


def test_course_rules():
    cl = course_check(("Probability Theory", [], "Core"), ("Python Lab", [], "Elective"))
    assert [(r.rule.id, r.status) for r in cl.results] == [("prob", "met"), ("any-py", "met")]
    assert result(cl, "prob").evidence == ["C0 Probability Theory"]
    assert result(cl, "prob").rule.level == "advisory"

    cl = course_check(("Probability Theory", [], "Elective"))
    assert result(cl, "prob").status == "partly" and result(cl, "prob").found == "only an elective course on it"

    cl = course_check(("Algebra", ["Probability axioms", "Bayes theorem", "Groups", "Rings", "Fields"], "Core"))
    r = result(cl, "prob")
    assert (r.status, r.found, r.evidence) == ("partly", "taught inside other courses", ["C0 Algebra"])

    cl = course_check(("Algebra", ["Probability axioms", "Groups"], "Core"))
    r = result(cl, "prob")
    assert (r.status, r.found) == ("not_met", "mentioned once") and r.evidence == ["C0: “Probability axioms”"]
    assert result(course_check(("Algebra", [], "Core")), "prob").found == "not found"


def test_course_rules_need_no_scheme_and_unknown_skills_fail():
    cl = course_check(("Probability", [], "Core"))
    assert not cl.has_scheme and result(cl, "prob").status == "met"
    bad = rules({"id": "x", "kind": "course_on", "skill": "alchemy", "text": "t"})
    with pytest.raises(RulesError, match="'alchemy' is not in"):
        check(programme(), bad, TAX)


# ----- schema and PDF profiles ------------------------------------------------

def test_scheme_items_are_validated():
    with pytest.raises(ValidationError):
        SchemeItem(category="Major", credits=-1)
    with pytest.raises(ValidationError):
        SchemeItem(category="", credits=4)


def test_profile_passes_degree_and_scheme(tmp_path, monkeypatch):
    from curintel import pdfimport
    prof = tmp_path / "p.yaml"
    prof.write_text(textwrap.dedent("""\
        institution: U
        name: P
        degree: 4-year (Honours)
        scheme:
          - {category: Major, credits: 8, semester: I}
          - {category: AEC, credits: 2, semester: I}
        extra_courses:
          - {code: M1, title: Calculus, topics: []}
        """))
    p = pdfimport.extract(prof).programme
    assert p.degree == "4-year (Honours)" and [s.credits for s in p.scheme] == [8, 2]
    prof.write_text(prof.read_text().replace("credits: 2", "credits: -2"))
    with pytest.raises(pdfimport.ProfileError, match="scheme.1.credits"):
        pdfimport.extract(prof)


# ----- reports and the command line -------------------------------------------

def test_report_section_tiles_and_json(riverside, peers, tax):
    cl = check(riverside, UGC, tax)
    b = benchmark(riverside, peers, tax)
    html = render_html(b, [], [cl])
    assert "<h2>Regulatory checklist: UGC Curriculum and Credit Framework" in html
    assert "Checked as a <b>3-year UG degree</b>" in html
    assert "<b>7 of 9</b><span>Requirements met: ugc-ccfup-2022</span>" in html
    assert "Required (9): 7 met, 2 partly met." in html
    assert "<span class='pill Medium'>Partly met</span>" in html
    assert "p. 19" in html and "6-8 in the framework" in html
    assert "Not yet analysed: industry skill demand." in html
    assert "Regulatory &amp; industry alignment" not in html
    d = to_dict(b, [], [cl])
    reg = d["regulatory"][0]
    assert reg["variant"] == "3-year" and reg["has_scheme"] and reg["category_credits"]["major"] == 66
    sec = next(r for r in reg["results"] if r["id"] == "sec-credits")
    assert (sec["status"], sec["page"], sec["found"]) == ("partly", "20", "6 credits in Skill enhancement courses (SEC)")
    json.dumps(d)
    plain = render_html(b, [])
    assert "Regulatory checklist" not in plain and "Regulatory &amp; industry alignment" in plain
    assert to_dict(b, [])["regulatory"] == []


def test_report_notes_missing_scheme_and_unmapped_labels(tax):
    p = programme([("Major", 8, "1"), ("Sports <b>", 2, "1")])
    html = render_html(benchmark(p, [programme()], tax), [], [check(p, UGC, tax)])
    assert "Sports &lt;b&gt; (2 credits)" in html                 # escaped
    q = programme()
    html = render_html(benchmark(q, [programme()], tax), [], [check(q, UGC, tax)])
    assert "No credit scheme is recorded" in html
    assert "<b>Not checked</b>" in html


def test_cli_regcheck_and_report_rules(tmp_path, capsys):
    assert main(["regcheck", str(SAMPLES / "riverside.json")]) == 0
    out = capsys.readouterr().out
    assert "as a 3-year UG degree" in out and "[partly     ] Table 2: Skill Enhancement" in out
    out_html = tmp_path / "r.html"
    assert main(["report", str(SAMPLES / "riverside.json"), str(SAMPLES / "peers"), "-o", str(out_html),
                 "--rules", "ugc-ccfup-2022", "--json", str(tmp_path / "r.json")]) == 0
    assert "Regulatory checklist" in out_html.read_text(encoding="utf-8")
    assert json.loads((tmp_path / "r.json").read_text())["regulatory"][0]["id"] == "ugc-ccfup-2022"
    assert main(["regcheck", str(SAMPLES / "riverside.json"), "--rules", "nope"]) == 1
    assert "no built-in rules named 'nope'" in capsys.readouterr().err


def test_tile_counts_required_rules_only_and_not_met_is_flagged(tax):
    rs = rules({"id": "total", "kind": "total_credits", "text": "Enough credits", "min": 10},
               {"id": "proj", "kind": "category_credits", "category": "proj", "text": "A project", "min": 2},
               {"id": "prob", "kind": "course_on", "skill": "probability", "text": "Probability", "level": "advisory"})
    p = programme([("Major", 12, "1")])
    html = render_html(benchmark(p, [programme()], tax), [], [check(p, rs, tax)])
    assert "<b>1 of 2</b><span>Requirements met: t</span>" in html     # the advisory rule is left out
    assert "<span class='pill High'>Not met</span>" in html
    assert "Required (2): 1 met, 1 not met; Advisory (1): 1 not met." in html
    assert "<span class='pill soft'>Advisory</span>" in html


def test_degree_override_and_semesters_outside_the_degree(tax):
    # Six semesters of 20 credits plus a seventh: checked as 3-year, semester VII is left out.
    p = programme([("Major", 20, s) for s in ("I", "II", "III", "IV", "V", "VI", "VII")])
    cl = check(p, UGC, tax, degree="3-year")
    assert cl.variant.id == "3-year" and cl.variant_basis == 'the degree was given as "3-year"'
    assert cl.beyond == {"VII": 20} and cl.missing_semesters == []
    assert result(cl, "total-credits").found == "120 credits"
    # As a 4-year degree, every semester counts, and semester 8 is reported missing.
    cl4 = check(p, UGC, tax)
    assert cl4.variant.id == "4-year" and cl4.beyond == {} and cl4.missing_semesters == [8]
    assert result(cl4, "total-credits").status == "partly"
    html = render_html(benchmark(p, [programme()], tax), [], [cl, cl4])
    assert "Not counted for this degree: credits in later semesters, VII (20 credits)." in html
    assert "no credits for semester 8, so credit totals for this degree are incomplete" in html
    d = to_dict(benchmark(p, [programme()], tax), [], [cl4])["regulatory"][0]
    assert d["missing_semesters"] == [8] and d["beyond"] == {}
    with pytest.raises(RulesError, match="matches none of"):
        check(p, UGC, tax, degree="diploma")


def test_scheme_without_semesters_is_not_called_incomplete(tax):
    cl = check(programme([("Major", 120, None)], degree="3-year"), UGC, tax)
    assert cl.missing_semesters == [] and result(cl, "total-credits").status == "met"


def test_cli_degree_option(capsys):
    assert main(["regcheck", str(SAMPLES / "riverside.json"), "--degree", "4-year"]) == 0
    out = capsys.readouterr().out
    assert "as a 4-year UG degree (Honours)" in out
    assert "no credits for semester(s) 7, 8" in out


@pytest.mark.parametrize("label,category", [
    ("Multi / Inter Disciplinary", "multidisciplinary"), ("Multidisciplinary", "multidisciplinary"),
    ("Inter-disciplinary", "multidisciplinary"), ("MDC", "multidisciplinary"), ("Major", "major"),
    ("Honours Major", "major"), ("DSC", "major"), ("Minor", "minor"), ("Vocational", "minor"),
    ("AEC", "aec"), ("SEC", "sec"), ("Skill enhancement (elective basket)", "sec"),
    ("Value Added / IKS", "vac"), ("IKS", "vac"), ("Internship (in the SEC slot)", "internship"),
    ("Research Project", "research"), ("Dissertation", "research"), ("Elective", None), ("Sports", None),
])
def test_ugc_category_labels(label, category):
    c = UGC.category_of(label)
    assert (c.id if c else None) == category


def test_tiles_for_advisory_only_rules(tax):
    rs = rules({"id": "prob", "kind": "course_on", "skill": "probability", "text": "P", "level": "advisory"},
               {"id": "calc", "kind": "course_on", "skill": "calculus", "text": "C", "level": "advisory"})
    p = programme()                                     # one course, "Calculus"; no scheme
    html = render_html(benchmark(p, [programme()], tax), [], [check(p, rs, tax)])
    assert "<b>1 of 2</b><span>Advisory points met: t</span>" in html
    assert "no credit scheme recorded" not in html and "Requirements met" not in html
