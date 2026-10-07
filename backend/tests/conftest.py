from pathlib import Path

import pytest

from curintel.schema import Course, Programme, load_programme
from curintel.taxonomy import Taxonomy

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


@pytest.fixture(scope="session")
def tax() -> Taxonomy:
    return Taxonomy.builtin()


@pytest.fixture(scope="session")
def riverside() -> Programme:
    return load_programme(SAMPLES / "riverside.json")


@pytest.fixture(scope="session")
def peers() -> list[Programme]:
    return [load_programme(p) for p in sorted((SAMPLES / "peers").glob("*.json"))]


def prog(name: str, *courses: tuple[str, list[str]]) -> Programme:
    """A programme from (title, topics) pairs."""
    return Programme(institution=name, name="B.Sc.",
                     courses=[Course(code=f"C{i}", title=t, credits=4, topics=tp)
                              for i, (t, tp) in enumerate(courses)])
