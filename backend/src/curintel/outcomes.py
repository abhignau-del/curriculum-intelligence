"""Course outcomes: the Bloom's level of each outcome, read from its action verbs, and checks on the set.

No AI: an outcome's level comes from the verbs that open it, looked up in a verb list
(``taxonomies/bloom.yaml``). With several opening verbs ("Identify and classify ...")
the highest level counts. Leading words are skipped ("Students will be able to", "CO2:"),
verbs are matched in their usual forms (solve, solves, solved, solving), and a verb that
a PDF fused to the next word ("Applyknowledgeof...") is still read.

Checks on each outcome:

* ``vague``     - opens with a verb that is hard to assess (understand, learn, appreciate);
* ``no_verb``   - no action verb was found at the start;
* ``duplicate`` - the same outcome, ignoring case and punctuation, is stated for another course.

For the programme: outcomes per level by year of study, the share of higher-order outcomes
(Analyse, Evaluate, Create), and the courses that state no outcomes.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

import yaml

from .regulatory import semester_number
from .schema import Programme

HIGHER_ORDER = 4                       # Analyse and above
FUSED_MIN = 15                         # "applyknowledgeof..." - long enough not to be a word ("knowledge")
CONNECTORS = {"and", "or", "&", "/", "then", "as", "well"}
LEAD = re.compile(
    r"^(?:c\s*o\s*-?\s*\d+\s*)?(?:\d+\s*)?(?:(?:the|a)\s+)?(?:students?|learners?|candidates?|they)?\s*"
    r"(?:will|shall|should|would|can|must)?\s*(?:be\s+(?:able|enabled)\s+to|have\s+the\s+ability\s+to)?\s*"
    r"(?:to\s+)?")


class BloomError(ValueError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _forms(verb: str) -> set[str]:
    """Usual inflections of a (one-word) verb: solve -> solves, solved, solving."""
    v = verb
    forms = {v, v + "s", v + "es", v + "ed", v + "d", v + "ing"}
    if v.endswith("y") and len(v) > 2 and v[-2] not in "aeiou":
        forms |= {v[:-1] + "ies", v[:-1] + "ied"}
    if v.endswith("e"):
        forms.add(v[:-1] + "ing")
    if len(v) >= 3 and v[-1] not in "aeiouwxy" and v[-2] in "aeiou" and v[-3] not in "aeiou":
        forms |= {v + v[-1] + "ed", v + v[-1] + "ing"}       # plot -> plotted, plotting
    return forms


@dataclass(frozen=True)
class Level:
    level: int
    id: str
    name: str


class Bloom:
    """The verb list: phrase (normalised words) -> (base verb, level or None, vague)."""

    def __init__(self, name: str, levels: list[Level], phrases: dict[tuple[str, ...], tuple[str, Optional[int], bool]]):
        self.name = name
        self.levels = levels
        self.phrases = phrases
        self.longest = max((len(p) for p in phrases), default=1)
        self.by_level = {lv.level: lv for lv in levels}
        self.single = sorted((p[0] for p in phrases if len(p) == 1 and len(p[0]) >= 4), key=len, reverse=True)

    @classmethod
    def from_dict(cls, data: dict) -> "Bloom":
        try:
            levels, phrases = [], {}
            for lv in data["levels"]:
                level = Level(int(lv["level"]), lv["id"], lv["name"])
                levels.append(level)
                for verb in lv["verbs"]:
                    words = tuple(_norm(verb).split())
                    if words in phrases:
                        raise BloomError(f"verb {verb!r} is listed under two levels")
                    phrases[words] = (" ".join(words), level.level, False)
            for verb, level in (data.get("vague") or {}).items():
                words = tuple(_norm(verb).split())
                phrases[words] = (" ".join(words), None if level is None else int(level), True)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, BloomError):
                raise
            raise BloomError(f"verb list is missing a field or has a bad value ({exc})") from None
        # Inflected forms of one-word verbs, without overriding a listed word.
        for words, info in list(phrases.items()):
            if len(words) == 1:
                for form in _forms(words[0]):
                    phrases.setdefault((form,), info)
        return cls(data.get("name", "Bloom's taxonomy"), sorted(levels, key=lambda lv: lv.level), phrases)

    @classmethod
    def builtin(cls) -> "Bloom":
        text = resources.files("curintel.taxonomies").joinpath("bloom.yaml").read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(text))

    @classmethod
    def load(cls, path: str | Path) -> "Bloom":
        return cls.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def _at(self, words: list[str], i: int):
        for n in range(min(self.longest, len(words) - i), 0, -1):
            hit = self.phrases.get(tuple(words[i:i + n]))
            if hit:
                return hit, n
        return None, 0

    def classify(self, text: str) -> tuple[Optional[int], list[str], bool]:
        """(level, opening verbs, vague) for one outcome."""
        norm = LEAD.sub("", _norm(text), count=1)
        words = norm.split()
        i = 0
        # an adverb before the verb ("effectively use"), but not a verb that ends in -ly ("apply")
        while i < len(words) and words[i].endswith("ly") and len(words[i]) > 4 and (words[i],) not in self.phrases:
            i += 1
        verbs: list[tuple[str, Optional[int], bool]] = []
        while i < len(words):
            hit, n = self._at(words, i)
            if hit:
                verbs.append(hit)
                i += n
            elif verbs and words[i] in CONNECTORS:
                i += 1
            else:
                break
        if not verbs and words and len(words[0]) >= FUSED_MIN:
            first = words[0]                 # a verb fused to the next words by the PDF
            for verb in self.single:
                if first.startswith(verb):
                    verbs.append(self.phrases[(verb,)])
                    break
        if not verbs:
            return None, [], False
        levels = [lv for _, lv, _ in verbs if lv is not None]
        vague = verbs[0][2]
        return (max(levels) if levels else None), [v for v, _, _ in verbs], vague


@dataclass
class OutcomeResult:
    course_code: str
    course_title: str
    semester: Optional[str]
    text: str
    level: Optional[int]
    verbs: list[str]
    flags: list[str] = field(default_factory=list)


@dataclass
class OutcomeReport:
    programme: Programme
    bloom: Bloom
    results: list[OutcomeResult]
    without_outcomes: list[tuple[str, str]]              # (code, title)
    duplicates: list[tuple[str, list[str]]]              # (outcome text, course codes)

    @property
    def courses_with_outcomes(self) -> int:
        return len({r.course_code for r in self.results})

    def flagged(self, flag: str) -> list[OutcomeResult]:
        return [r for r in self.results if flag in r.flags]

    def counts(self, results: Optional[list[OutcomeResult]] = None) -> dict[Optional[int], int]:
        out: dict[Optional[int], int] = {lv.level: 0 for lv in self.bloom.levels}
        out[None] = 0
        for r in self.results if results is None else results:
            out[r.level] = out.get(r.level, 0) + 1
        return out

    @staticmethod
    def higher_order_share(results: list[OutcomeResult]) -> Optional[float]:
        rated = [r for r in results if r.level is not None]
        return sum(r.level >= HIGHER_ORDER for r in rated) / len(rated) if rated else None

    def by_year(self) -> list[tuple[str, list[OutcomeResult]]]:
        """Outcomes grouped by year of study (semesters 1-2 are year 1), in order; '' when unknown."""
        groups: dict[str, list[OutcomeResult]] = defaultdict(list)
        for r in self.results:
            n = semester_number(r.semester)
            groups[f"Year {(n + 1) // 2}" if n else ""].append(r)
        return sorted(groups.items(), key=lambda kv: (kv[0] == "", kv[0]))


def analyse_outcomes(programme: Programme, bloom: Optional[Bloom] = None) -> OutcomeReport:
    bloom = bloom or Bloom.builtin()
    results: list[OutcomeResult] = []
    seen: dict[str, list[str]] = defaultdict(list)
    first_text: dict[str, str] = {}
    without = []
    for c in programme.courses:
        if not c.outcomes:
            without.append((c.code, c.title))
            continue
        for text in c.outcomes:
            level, verbs, vague = bloom.classify(text)
            flags = []
            if not verbs:
                flags.append("no_verb")
            elif vague:
                flags.append("vague")
            results.append(OutcomeResult(c.code, c.title, c.semester, text, level, verbs, flags))
            key = _norm(text)
            if c.code not in seen[key]:
                seen[key].append(c.code)
            first_text.setdefault(key, text)
    duplicates = [(first_text[k], codes) for k, codes in seen.items() if len(codes) > 1]
    dup_keys = {_norm(t) for t, _ in duplicates}
    for r in results:
        if _norm(r.text) in dup_keys:
            r.flags.append("duplicate")
    return OutcomeReport(programme, bloom, results, without, duplicates)
