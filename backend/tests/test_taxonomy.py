import pytest

from curintel.taxonomy import Taxonomy, TaxonomyError, normalise


def skills(tax, text):
    return {h.skill for h in tax.match(text)}


def test_normalise_strips_case_punctuation_and_accents():
    assert normalise("  Green's Théorem—in the PLANE ") == "green s theorem in the plane"


def test_longest_phrase_wins(tax):
    assert skills(tax, "Partial differential equations") == {"pde"}
    assert skills(tax, "Linear programming and duality") == {"optimisation"}
    assert skills(tax, "Linear algebra") == {"linear_algebra"}         # not abstract algebra
    assert skills(tax, "Numerical integration") == {"numerical_methods"}  # not calculus


def test_longer_term_starting_later_beats_shorter_one_starting_earlier():
    tax = Taxonomy.from_dict({"name": "t", "areas": [{"id": "a", "name": "A", "skills": [
        {"id": "short", "name": "S", "terms": ["data"]},
        {"id": "long", "name": "L", "terms": ["data analysis pipeline"]},
        {"id": "mid", "name": "M", "terms": ["big data"]},
    ]}]})
    # "big data" starts first; "data analysis pipeline" is longer and overlaps it.
    assert skills(tax, "big data analysis pipeline") == {"long"}


def test_plural_and_word_boundaries(tax):
    assert skills(tax, "Eigenvalues and eigenvectors") == {"linear_algebra"}
    assert skills(tax, "Excellent results") == set()     # 'excel' inside a word
    assert skills(tax, "Grouped data") == set()          # 'group' inside a word
    assert skills(tax, "Engineering drawing") == set()   # 'ring' at the end of a word


def test_term_shared_by_two_skills(tax):
    assert skills(tax, "Plotting with Matplotlib") == {"python", "visualisation"}


def test_divergence_of_series_is_not_vector_calculus(tax):
    assert "vector_calculus" not in skills(tax, "Convergence and divergence of series")


def test_builtin_taxonomy_is_well_formed(tax):
    assert len(tax.skills) >= 40
    for skill in tax.skills.values():
        assert skill.terms and all(t == normalise(t) for t in skill.terms)


def test_duplicate_skill_id_rejected():
    data = {"name": "t", "areas": [{"id": "a", "name": "A", "skills": [
        {"id": "x", "name": "X", "terms": ["one"]}, {"id": "x", "name": "Y", "terms": ["two"]}]}]}
    with pytest.raises(TaxonomyError, match="used twice"):
        Taxonomy.from_dict(data)


def test_missing_field_rejected():
    with pytest.raises(TaxonomyError):
        Taxonomy.from_dict({"name": "t", "areas": [{"id": "a", "skills": []}]})


def test_terms_found_missing_in_real_syllabi(tax):
    # added after surveying eight real B.Sc. Mathematics syllabi (2026-10-08)
    assert "real_analysis" in skills(tax, "Ratio test and root test for infinite series")
    assert "linear_algebra" in skills(tax, "Eigen values and the Cayley-Hamilton theorem")
    assert "ode" in skills(tax, "Phase plane analysis of dynamical systems")
    assert "probability" in skills(tax, "Weak law of large numbers")
