"""The programme record every analysis works from.

Deliberately lighter than an AcadDoc course: a peer university's published
syllabus rarely gives more than a title, credits and a list of topics, so
that is all a course needs. AcadDoc courses are converted into this shape by
`importers.from_acaddoc`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


# Category words that mark a course as an option rather than part of the compulsory core.
ELECTIVE = re.compile(r"elective|optional|choice|basket|\bDSE\b|\bGE\b", re.I)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Course(_Model):
    code: str = Field(min_length=1)
    title: str = Field(min_length=1)
    credits: Optional[float] = Field(default=None, ge=0)
    semester: Optional[str] = None
    category: str = ""                     # Core / Elective / Skill / ...
    topics: list[str] = Field(default_factory=list)    # one syllabus line each
    outcomes: list[str] = Field(default_factory=list)

    @property
    def is_elective(self) -> bool:
        """An option the student chooses, judged from `category`; anything else counts as core."""
        return bool(ELECTIVE.search(self.category))


class SchemeItem(_Model):
    """Credits a student earns in one category of course, as the programme's credit scheme sets out.

    The scheme is the university's own table of credits per category (Major, Minor, AEC, ...)
    and semester. Courses list what the department offers, including every elective
    alternative and none of other departments' courses, so credit rules read the scheme.
    """
    category: str = Field(min_length=1)    # the university's own label: "Major", "DSC", "AEC", ...
    credits: float = Field(ge=0)
    semester: Optional[str] = None
    note: str = ""


class ProgrammeOutcome(_Model):
    """A programme outcome (PO, PSO or graduate attribute), for CO-PO mapping.

    Plain text is enough: indicators are then read from the wording (see `mapping`).
    """
    code: str = Field(min_length=1)        # "PO1", "PSO2"
    text: str = Field(min_length=1)
    name: str = ""                         # short name, e.g. "Problem solving"
    verbs: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)     # taxonomy skill ids, or area:<id>
    words: list[str] = Field(default_factory=list)
    level: Optional[int] = Field(default=None, ge=1, le=6)


class Programme(_Model):
    institution: str = Field(min_length=1)
    name: str = Field(min_length=1)        # "B.Sc. Mathematics (Honours)"
    source: str = ""                       # where the syllabus came from
    year: str = ""                         # syllabus edition, e.g. "2024-25"
    degree: str = ""                       # "3-year", "4-year (Honours)", ...: picks the rules that apply
    courses: list[Course] = Field(min_length=1)
    scheme: list[SchemeItem] = Field(default_factory=list)
    programme_outcomes: list[ProgrammeOutcome] = Field(default_factory=list)

    @property
    def label(self) -> str:
        return self.institution

    @property
    def total_credits(self) -> float:
        return sum(c.credits or 0 for c in self.courses)


def load_programme(path: str | Path) -> Programme:
    """Read a programme from .json or .xlsx (see `importers`)."""
    path = Path(path)
    if path.suffix.lower() == ".xlsx":
        from .importers import from_workbook
        return from_workbook(path)
    try:
        return Programme.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name}: not valid JSON ({exc})") from None
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(map(str, err["loc"])) or "file"
        raise ValueError(f"{path.name}: {where}: {err['msg']}") from None


def save_programme(programme: Programme, path: str | Path) -> None:
    Path(path).write_text(
        programme.model_dump_json(indent=2, exclude_defaults=True) + "\n",
        encoding="utf-8",
    )
