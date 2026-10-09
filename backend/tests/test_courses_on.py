"""Courses on a skill: telling a whole course on a skill from a few lines inside other courses."""
import json

import pytest

from curintel.analysis import benchmark, profile
from curintel.report import render_html, to_dict
from curintel.schema import Course, Programme
from curintel.taxonomy import Taxonomy

TAX = Taxonomy.builtin()
PROB = ["Probability axioms", "Random variable", "Binomial distribution", "Normal distribution"]
FILLER = ["Groups", "Rings", "Fields", "Vector spaces"]


def programme(name, *courses):
    """(title, topics, category) triples."""
    return Programme(institution=name, name="B.Sc.",
                     courses=[Course(code=f"{name}{i}", title=t, credits=4, topics=tp, category=cat)
                              for i, (t, tp, cat) in enumerate(courses)])




def on(p, skill, **kw):
    return [(c.code, c.by) for c in profile(p, TAX, **kw)[skill].courses_on]


def test_title_names_the_skill():
    p = programme("P", ("Python Programming", [], "Core"), ("Calculus", ["Limits"], "Core"))
    assert on(p, "python") == [("P0", "title")]


@pytest.mark.parametrize("topics,expected", [
    (PROB[:3], True),                     # 3 of 3
    (PROB[:3] + FILLER[:3], True),        # 3 of 6: exactly half
    (PROB[:3] + FILLER[:4], False),       # 3 of 7: under half
    (PROB[:2], False),                    # 2 of 2: all of them, but fewer than three lines
    (PROB + FILLER[:4], True),            # 4 of 8
])
def test_most_topic_lines(topics, expected):
    p = programme("P", ("Mathematics III", topics, "Core"))
    assert on(p, "probability") == ([("P0", "topics")] if expected else [])


def test_outcomes_do_not_count_towards_a_course_on_it():
    c = Course(code="X", title="Mathematics III", topics=FILLER[:2],
               outcomes=["Use probability", "Compute a random variable", "Apply a normal distribution"])
    assert profile(Programme(institution="P", name="B", courses=[c]), TAX)["probability"].courses_on == []


def test_core_only_profile_and_course_basis():
    p = programme("P", ("Probability", [], "Elective"), ("Mathematics III", PROB, "Core"))
    cov = profile(p, TAX)["probability"]
    assert [c.elective for c in cov.courses_on] == [True, False] and cov.course_basis == "core"
    assert on(p, "probability", core_only=True) == [("P1", "topics")]
    only_elective = programme("Q", ("Probability", [], "Elective"))
    assert profile(only_elective, TAX)["probability"].course_basis == "elective"
    assert profile(programme("R", ("Calculus", [], "Core")), TAX)["probability"].course_basis is None


def modelling_benchmark():
    own = programme("Own", ("Calculus", ["Limits"], "Core"))
    peers = [
        programme("A", ("Mathematical Modelling", ["Population model"], "Core")),
        programme("B", ("Mathematical Modelling", [], "Elective"), ("Algebra", FILLER, "Core")),
        # covered, by two lines inside a differential-equations course: no course on it
        programme("C", ("Differential Equations", ["Growth and decay: modelling", "Predator prey model",
                                                   "Linear equations", "Exact equations",
                                                   "Wronskian"], "Core")),
        programme("D", ("Topology", [], "Core"), ("Graph Theory", [], "Elective")),
    ]
    return benchmark(own, peers, TAX)


def test_benchmark_counts_courses_on_it():
    b = modelling_benchmark()
    r = next(r for r in b.rows if r.skill == "modelling")
    assert r.peers_covering == ["A", "B", "C"]
    assert sorted(r.peer_courses_on) == ["A", "B"]
    assert r.peer_course_basis == {"A": "core", "B": "elective"}
    assert r.peer_course_share == 0.5 and r.peer_core_course_share == 0.25
    assert r.peer_core_share == 0.5                          # A and C: core covers it either way
    assert (r.status, r.priority) == ("gap", "High")         # classification is unchanged


def test_gap_sentence_and_share_cell():
    html = render_html(modelling_benchmark(), [])
    assert ("(3 of 4: in the core of 2, only as an elective in 1) but is not found in this curriculum. "
            "2 of them have a course on it (1 core, 1 elective).") in html
    assert "core 50%<br>core course 25%" in html
    assert "<i>(a core course on it: Mathematical Modelling)</i>: Mathematical Modelling" in html
    assert "<b>C</b>: Differential Equations" in html        # no note for lines inside another course


@pytest.mark.parametrize("peers,expected", [
    ([("Probability", [], "Core"), ("Probability", [], "Core")], "2 of them have a course on it (all core)."),
    ([("Probability", [], "Elective"), ("Probability", [], "Elective")],
     "2 of them have a course on it (all elective)."),
    ([("Probability", [], "Core"), ("Mathematics III", PROB[:2] + FILLER, "Core")],
     "1 of them has a course on it (core)."),
    ([("Mathematics III", PROB[:2] + FILLER, "Core"), ("Mathematics IV", PROB[:2] + FILLER, "Elective")],
     "None of them has a course on it: they teach it inside other courses."),
])
def test_course_sentence_variants(peers, expected):
    own = programme("Own", ("Calculus", [], "Core"))
    # each peer also offers an unrelated elective, so the peers record electives
    b = benchmark(own, [programme(n, p, ("Graph Theory", [], "Elective")) for n, p in zip("AB", peers)], TAX)
    assert expected in render_html(b, [])


def test_without_recorded_electives_no_core_word():
    own = programme("Own", ("Calculus", [], ""))
    b = benchmark(own, [programme("A", ("Probability", [], "")), programme("B", ("Algebra", PROB[:2], ""))], TAX)
    html = render_html(b, [])
    assert "(2 of 2) but is not found in this curriculum. 1 of them has a course on it." in html
    gaps = html.split("<h2>Watch list")[0].split("<h2>Distinctive")[0]
    assert "course 50%" in gaps and "core" not in gaps.split("<h2>Priority gaps")[1]
    assert "<i>(a course on it: Probability)</i>" in html


def test_matrix_and_strength_marks_for_the_programme_itself():
    own = programme("Own", ("Python Programming", [], "Core"), ("Graph Theory", [], "Elective"),
                    ("Algebra", ["Lists in Python", "Python loops"] + FILLER, "Core"))
    peers = [programme("A", ("Calculus", [], "Core")), programme("B", ("Calculus", [], "Elective"))]
    html = render_html(benchmark(own, peers, TAX), [])
    assert "<td class='ownc c-course' title='A core course on it'>●</td>" in html
    assert ("<td class='ownc c-elective' title='Covered only by electives (an elective course on it)'>○</td>"
            in html)
    assert "<span class='c-course'>●</span> A core course on it" in html      # distinctive strengths


def test_core_course_breaks_ties_between_equal_gaps():
    own = programme("Own", ("Calculus", [], "Core"))
    # Both skills: covered in the core of both peers. Only Python has a course on it at B,
    # and MATLAB sorts first alphabetically, so only the core-course share puts Python ahead.
    peers = [programme("A", ("Algebra", ["MATLAB plots", "MATLAB loops", "Python lists", "Python loops"]
                         + FILLER * 2, "Core")),
             programme("B", ("Python Programming", ["MATLAB plots", "MATLAB loops"] + FILLER * 2, "Core"))]
    gaps = [r.skill for r in benchmark(own, peers, TAX).by_status("gap")]
    assert gaps.index("python") < gaps.index("matlab")


def test_json_carries_courses_on():
    d = to_dict(modelling_benchmark(), [])
    m = next(s for s in d["skills"] if s["id"] == "modelling")
    assert m["peer_courses_on"]["A"] == [{"course": "A0", "course_title": "Mathematical Modelling",
                                          "elective": False, "by": "title"}]
    assert m["peer_course_basis"] == {"A": "core", "B": "elective"}
    assert m["peer_course_share"] == 0.5 and m["peer_core_course_share"] == 0.25
    assert m["own_courses_on"] == [] and m["own_course_basis"] is None
    json.dumps(d)


def test_peer_with_core_and_elective_courses_on_it():
    own = programme("Own", ("Calculus", [], "Core"))
    peers = [programme("A", ("Probability Theory", [], "Elective"), ("Probability and Statistics", [], "Core")),
             programme("B", ("Algebra", [], "Core"))]
    b = benchmark(own, peers, TAX)
    r = next(r for r in b.rows if r.skill == "probability")
    assert r.peer_course_basis == {"A": "core"} and r.peer_core_course_share == 0.5
    html = render_html(b, [])
    assert "1 of them has a course on it (core)." in html
    # the note names the core course only
    assert "<i>(a core course on it: Probability and Statistics)</i>" in html
    assert "course on it: Probability Theory" not in html
