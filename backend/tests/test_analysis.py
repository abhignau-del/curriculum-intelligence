import pytest

from curintel.analysis import benchmark, profile, unmapped_lines
from conftest import prog


def test_levels(tax):
    p = prog("X",
             ("Python Programming", ["Loops"]),                     # title -> covered
             ("Algebra", ["Group theory", "Normal subgroups"]),     # 2 lines -> covered
             ("Misc", ["Monte Carlo methods"]))                     # 1 line -> touched
    pr = profile(p, tax)
    assert pr["python"].level == "covered"
    assert pr["abstract_algebra"].level == "covered"
    assert pr["scientific_computing"].level == "touched"
    assert pr["topology"].level == "absent"


def test_one_line_counts_once_even_with_two_terms(tax):
    p = prog("X", ("Misc", ["Groups, subgroups and cosets"]))
    cov = profile(p, tax)["abstract_algebra"]
    assert cov.level == "touched" and len(cov.evidence) == 1


def test_evidence_points_at_the_line(tax):
    p = prog("X", ("Numerical Analysis", ["Newton-Raphson method"]))
    ev = profile(p, tax)["numerical_methods"].evidence
    assert {(e.field, e.line) for e in ev} == {("title", "Numerical Analysis"), ("topic", "Newton-Raphson method")}


def _peers(n_with, n_without):
    return ([prog(f"P{i}", ("Linear Programming", [])) for i in range(n_with)]
            + [prog(f"Q{i}", ("Topology", [])) for i in range(n_without)])


@pytest.mark.parametrize("n_with,status,priority", [
    (7, "gap", "High"),      # 70%
    (6, "gap", "Medium"),    # 60%
    (5, "gap", "Medium"),    # 50%
    (4, "watch", None),      # 40%
    (3, "watch", None),      # 30%
    (2, "uncommon", None),   # 20%
])
def test_gap_thresholds(tax, n_with, status, priority):
    own = prog("Own", ("Calculus", []))
    b = benchmark(own, _peers(n_with, 10 - n_with), tax)
    row = next(r for r in b.rows if r.skill == "optimisation")
    assert (row.status, row.priority) == (status, priority)
    assert row.peer_share == pytest.approx(n_with / 10)


def test_touched_here_is_still_a_gap(tax):
    own = prog("Own", ("Calculus", ["Linear programming"]))
    row = next(r for r in benchmark(own, _peers(8, 2), tax).rows if r.skill == "optimisation")
    assert row.own.level == "touched" and row.status == "gap"


def test_distinctive_needs_peers_not_even_mentioning_it(tax):
    own = prog("Own", ("Mechanics", []))
    quiet = [prog(f"P{i}", ("Calculus", [])) for i in range(10)]
    mention = [prog(f"P{i}", ("Calculus", ["Projectile motion"] if i < 4 else [])) for i in range(10)]
    status = lambda peers: next(r for r in benchmark(own, peers, tax).rows if r.skill == "mechanics").status
    assert status(quiet) == "distinctive"
    assert status(mention) == "aligned"     # 40% mention it once


def test_alignment_counts_touched_as_half(tax):
    peers = [prog(f"P{i}", ("Linear Programming", []), ("Python", [])) for i in range(4)]
    full = prog("Own", ("Linear Programming", []), ("Python", []))
    half = prog("Own", ("Linear Programming", []), ("Misc", ["NumPy arrays"]))
    none = prog("Own", ("Calculus", []))
    assert benchmark(full, peers, tax).alignment == 100
    assert benchmark(half, peers, tax).alignment == 75
    assert benchmark(none, peers, tax).alignment == 0


def test_benchmark_needs_distinct_peers(tax):
    own = prog("Own", ("Calculus", []))
    with pytest.raises(ValueError):
        benchmark(own, [], tax)
    with pytest.raises(ValueError, match="same institution"):
        benchmark(own, [prog("P", ("A", [])), prog("P", ("B", []))], tax)


def test_samples_tell_the_intended_story(tax, riverside, peers):
    b = benchmark(riverside, peers, tax)
    gaps = {r.skill: r.priority for r in b.by_status("gap")}
    assert gaps["optimisation"] == "High" and gaps["python"] == "High"
    assert gaps["modelling"] == "Medium"
    distinctive = {r.skill for r in b.by_status("distinctive")}
    assert {"mechanics", "history_iks"} <= distinctive
    assert "regression" not in distinctive          # most peers mention it
    assert b.structure[0].label == riverside.institution


def test_unmapped_lines(tax):
    p = prog("X", ("Calculus", ["Limits and continuity", "Arrays and functions"]))
    assert unmapped_lines(p, tax) == [("C0", "Arrays and functions")]


def test_structure_credits_unknown_when_any_course_lacks_them(tax):
    from curintel.schema import Course, Programme
    full = prog("Full", ("Calculus", []), ("Algebra", []))
    part = Programme(institution="Part", name="B.Sc.", courses=[
        Course(code="A", title="Calculus", credits=4), Course(code="B", title="Algebra")])
    b = benchmark(full, [part, prog("Other", ("Topology", []))], tax)
    assert [s.credits for s in b.structure] == [8, None, 4]
    assert b.peer_median_credits == 4          # unknown totals are left out of the median
