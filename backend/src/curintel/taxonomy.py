"""Skill taxonomy and the rules that find skills in syllabus text.

No statistics and no AI: a skill is found when one of its listed terms
appears in the text. Every hit records the term and the line it came from,
so any number in a report can be traced back to a syllabus phrase.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import cached_property
from importlib import resources
from pathlib import Path

import yaml


def normalise(text: str) -> str:
    """Lower-case, strip accents, and turn punctuation into single spaces."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    area: str              # area id
    terms: tuple[str, ...]


@dataclass(frozen=True)
class Area:
    id: str
    name: str
    skills: tuple[Skill, ...]


@dataclass(frozen=True)
class Hit:
    skill: str             # skill id
    term: str              # the taxonomy term that matched (normalised)
    start: int             # span in the normalised text
    end: int


class TaxonomyError(ValueError):
    pass


class Taxonomy:
    def __init__(self, name: str, areas: list[Area]):
        self.name = name
        self.areas = areas
        self.skills: dict[str, Skill] = {}
        for area in areas:
            for skill in area.skills:
                if skill.id in self.skills:
                    raise TaxonomyError(f"skill id {skill.id!r} is used twice")
                self.skills[skill.id] = skill

    # ----- loading -------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "Taxonomy":
        try:
            areas = []
            for a in data["areas"]:
                skills = []
                for s in a["skills"]:
                    terms = tuple(dict.fromkeys(normalise(t) for t in s["terms"]))
                    if not terms or "" in terms:
                        raise TaxonomyError(f"skill {s['id']!r} has an empty term")
                    skills.append(Skill(s["id"], s["name"], a["id"], terms))
                areas.append(Area(a["id"], a["name"], tuple(skills)))
            return cls(data["name"], areas)
        except (KeyError, TypeError) as exc:
            raise TaxonomyError(f"taxonomy is missing a field: {exc}") from exc

    @classmethod
    def load(cls, path: str | Path) -> "Taxonomy":
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def builtin(cls, name: str = "mathematics") -> "Taxonomy":
        text = resources.files("curintel.taxonomies").joinpath(f"{name}.yaml").read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(text))

    # ----- matching ------------------------------------------------------
    @cached_property
    def _term_skills(self) -> dict[str, tuple[str, ...]]:
        owners: dict[str, list[str]] = {}
        for skill in self.skills.values():
            for term in skill.terms:
                owners.setdefault(term, []).append(skill.id)
        return {t: tuple(ids) for t, ids in owners.items()}

    @cached_property
    def _pattern(self) -> re.Pattern[str]:
        # Longest terms first, so at any position the longest phrase wins.
        terms = sorted(self._term_skills, key=len, reverse=True)
        alternation = "|".join(re.escape(t) for t in terms)
        return re.compile(rf"(?<![a-z0-9])({alternation})(?:e?s)?(?![a-z0-9])")

    def match(self, text: str) -> list[Hit]:
        """Skills mentioned in `text`; overlapping phrases resolve to the longest.

        At any one position the regex already prefers the longest term, but a
        shorter term that starts earlier could still hide a longer one that
        starts a word later. So candidates are collected from every word
        start, and the longest non-overlapping ones are kept.
        """
        norm = normalise(text)
        candidates: list[tuple[int, int, str]] = []
        pos = 0
        while True:
            m = self._pattern.search(norm, pos)
            if not m:
                break
            candidates.append((m.start(), m.end(), m.group(1)))
            # retry from the next word, to find terms starting inside this one
            nxt = norm.find(" ", m.start() + 1)
            if nxt == -1:
                break
            pos = nxt + 1
        candidates.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
        taken: list[tuple[int, int]] = []
        hits: list[Hit] = []
        for start, end, term in candidates:
            if any(start < e and s < end for s, e in taken):
                continue
            taken.append((start, end))
            for skill in self._term_skills[term]:
                hits.append(Hit(skill, term, start, end))
        hits.sort(key=lambda h: (h.start, h.skill))
        return hits
