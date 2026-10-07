"""The programme record every analysis works from.

Deliberately lighter than an AcadDoc course: a peer university's published
syllabus rarely gives more than a title, credits and a list of topics, so
that is all a course needs. AcadDoc courses are converted into this shape by
`importers.from_acaddoc`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError


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


class Programme(_Model):
    institution: str = Field(min_length=1)
    name: str = Field(min_length=1)        # "B.Sc. Mathematics (Honours)"
    source: str = ""                       # where the syllabus came from
    year: str = ""                         # syllabus edition, e.g. "2024-25"
    courses: list[Course] = Field(min_length=1)

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
