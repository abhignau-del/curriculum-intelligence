from curintel.overlap import MODERATE, find_overlaps, terms_of
from curintel.schema import Course
from conftest import prog


def test_planted_overlaps_found_and_nothing_else(tax, riverside):
    pairs = {(p.a_title, p.b_title): p for p in find_overlaps(riverside, tax)}
    assert set(pairs) == {("Probability and Statistics", "Statistical Methods"),
                          ("Calculus II", "Vector Calculus")}
    stats = pairs[("Probability and Statistics", "Statistical Methods")]
    assert stats.level == "High"
    assert "Probability" in stats.shared_skills
    assert pairs[("Calculus II", "Vector Calculus")].level == "Moderate"


def test_peers_have_no_false_alarms(tax, peers):
    for p in peers:
        assert find_overlaps(p, tax) == [], p.label


def test_phrases_only_from_adjacent_words():
    bag = terms_of(Course(code="X", title="Stats", topics=["Tests of significance: t test"]))
    assert "test significance" not in bag     # 'of' sat between them
    assert "significance t" not in bag        # a colon sat between them
    assert "t test" in bag


def test_identical_courses_score_one_and_distinct_ones_none(tax):
    topics = ["Simplex method", "Duality", "Transportation problem"]
    p = prog("X", ("LP", topics), ("LP", topics), ("Topology", ["Compactness", "Connectedness"]))
    pairs = find_overlaps(p, tax)
    assert len(pairs) == 1
    assert pairs[0].similarity > 0.9 and pairs[0].level == "High"
    assert pairs[0].shared_skills == ["Optimisation"]


def test_theory_lab_pair_is_labelled(tax):
    topics = ["Bisection method", "Newton-Raphson method", "Simpson's rule"]
    p = prog("X", ("Numerical Methods", topics), ("Numerical Methods Lab", topics), ("Groups", ["Cosets"]))
    (pair,) = find_overlaps(p, tax)
    assert pair.theory_lab_pair


def test_threshold_is_respected(tax, riverside):
    assert all(p.similarity >= MODERATE for p in find_overlaps(riverside, tax))
    assert len(find_overlaps(riverside, tax, threshold=0.99)) == 0


def test_too_few_courses():
    assert find_overlaps(prog("X", ("Only", ["one"]))) == []
