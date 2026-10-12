"""CO-PO mapping: which programme outcomes each course outcome serves, and how strongly.

Programme outcomes (POs, PSOs or graduate attributes) come from an *outcome framework*:
the built-in UGC LOCF Mathematics graduate attributes, a framework file of your own, or the
programme's own outcomes (``Programme.programme_outcomes``). Each PO has *indicators*:

* ``verbs``  - opening verbs of a course outcome (see ``outcomes``);
* ``skills`` - taxonomy skill ids, or whole areas written ``area:<id>``, found in the outcome;
* ``words``  - phrases anywhere in the outcome;
* ``level``  - the Bloom level the PO calls for (optional);
* ``via_course`` - when true, an outcome that names none of the PO's skills still serves it,
  slightly, if its course is on one of them (titles and topics, as in the benchmark).

A course outcome serves a PO when at least one indicator matches. The strength follows the
1-2-3 scale of NAAC and NBA articulation matrices (1 slight, 2 moderate, 3 substantial):

    1, plus 1 when indicators of two or more kinds match,
       plus 1 when the outcome's Bloom level reaches the PO's level.

A PO written in plain text, with no indicators, gets them from its own text: the action
verbs and taxonomy skills it names, and its distinctive words. Such *derived* indicators are
held to more: a generic verb (use, apply, handle, develop ...) does not make a link on its own
(an outcome that opens with "use" does not serve "use laboratory equipment"), though a specific
one does (an outcome that opens with "solve" serves "analyse and solve problems"); common words
("theory", "methods") are ignored, as is any word found in more than a fifth of the programme's
course outcomes. Every link records the
indicators that made it, so each cell of the matrix can be checked and argued with.

A course's strength for a PO is the rounded mean over those of its outcomes that serve the PO.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Optional

import yaml

from .outcomes import Bloom, OutcomeReport, analyse_outcomes
from .schema import Programme
from .taxonomy import Taxonomy, normalise

# Words too common in outcome statements to show that a CO serves a particular PO.
GENERIC = set("""
ability able about above across after again all also among an and any apply are area areas as at basic be
been being both but by can capability capable concept concepts course courses demonstrate develop different
do each effectively etc every field fields for from fundamental fundamentals gain general given good have
help how in including into is it its knowledge learn learner learners level made make many mathematical
mathematics may more most must new not of on one or other others outcome outcomes over programme program
relevant same should skill skills so some student students study subject such than that the their them these
they this those through to under understand understanding up use used using various ways well what when
which while who will with within work
theory theories problem problems method methods technique techniques importance important range variety
respective respectively situation situations include includes including large built leading clearly
thinking world various basic concepts concept results result properties property certain specific
""".split())


COMMON_SHARE = 0.2
# Verbs too general to show, on their own, that an outcome serves a derived PO.
GENERIC_VERBS = {"use", "apply", "handle", "develop", "utilize", "utilise", "make use of", "employ", "select",
                 "produce", "plan", "build", "obtain", "find", "perform", "execute", "operate", "write"}


class FrameworkError(ValueError):
    pass


@dataclass(frozen=True)
class PO:
    code: str
    name: str
    text: str
    page: str = ""
    verbs: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    words: tuple[str, ...] = ()
    level: Optional[int] = None
    via_course: bool = False
    derived: bool = False                  # indicators read from the PO's own text (stricter, see above)

    @property
    def label(self) -> str:
        return f"{self.code} {self.name}".strip() if self.name else self.code


@dataclass
class Framework:
    id: str
    name: str
    source: str
    outcomes: list[PO]

    @classmethod
    def from_dict(cls, data: dict, where: str = "framework") -> "Framework":
        try:
            pos = []
            for o in data["outcomes"]:
                pos.append(PO(str(o["code"]), str(o.get("name", "")), str(o.get("text", "")), str(o.get("page", "")),
                              tuple(normalise(v) for v in o.get("verbs") or []),
                              tuple(str(s) for s in o.get("skills") or []),
                              tuple(normalise(w) for w in o.get("words") or []),
                              None if o.get("level") is None else int(o["level"]), bool(o.get("via_course", False))))
            if len({p.code for p in pos}) != len(pos):
                raise FrameworkError(f"{where}: two outcomes share a code")
            return cls(str(data["id"]), str(data["name"]), str(data.get("source", "")), pos)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, FrameworkError):
                raise
            raise FrameworkError(f"{where}: missing or invalid field ({exc})") from None

    @classmethod
    def load(cls, path: str | Path) -> "Framework":
        path = Path(path)
        return cls.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")), path.name)

    @classmethod
    def builtin(cls, name: str = "ugc-locf-mathematics") -> "Framework":
        res = resources.files("curintel.frameworks").joinpath(f"{name}.yaml")
        if not res.is_file():
            raise FrameworkError(f"no built-in outcome framework named {name!r} "
                                 f"(available: {', '.join(builtin_frameworks())})")
        return cls.from_dict(yaml.safe_load(res.read_text(encoding="utf-8")), f"{name}.yaml")

    @classmethod
    def resolve(cls, arg: str) -> "Framework":
        return cls.load(arg) if arg.lower().endswith((".yaml", ".yml")) else cls.builtin(arg)

    @classmethod
    def from_programme(cls, programme: Programme, bloom: Bloom, taxonomy: Taxonomy) -> "Framework":
        """The programme's own POs/PSOs; plain-text ones get indicators from their own wording."""
        pos = []
        for o in programme.programme_outcomes:
            if o.verbs or o.skills or o.words:
                pos.append(PO(o.code, o.name, o.text, "", tuple(normalise(v) for v in o.verbs), tuple(o.skills),
                              tuple(normalise(w) for w in o.words), o.level))
            else:
                pos.append(derive_po(o.code, o.name, o.text, bloom, taxonomy))
        return cls(f"{programme.label} outcomes", f"{programme.institution}: programme outcomes",
                   programme.source, pos)


def builtin_frameworks() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files("curintel.frameworks").iterdir() if p.name.endswith(".yaml"))


def _verbs_in(text: str, bloom: Bloom) -> list[str]:
    """Every listed action verb in a PO's text, written in its base form ("apply", not the noun
    "programming" or "modelling"); vague verbs are left out."""
    words = normalise(text).split()
    found, i = [], 0
    while i < len(words):
        hit, n = bloom._at(words, i)
        if hit and not hit[2] and hit[0] == " ".join(words[i:i + n]):
            found.append(hit[0])
            i += n
        else:
            i += 1
    return list(dict.fromkeys(found))


def derive_po(code: str, name: str, text: str, bloom: Bloom, taxonomy: Taxonomy) -> PO:
    """Indicators read from a PO's own wording: its verbs, its skills and its distinctive words."""
    verbs = tuple(_verbs_in(text, bloom))
    hits = taxonomy.match(text)
    skills = tuple(dict.fromkeys(h.skill for h in hits))
    in_skills = {w for h in hits for w in h.term.split()}       # one piece of evidence, counted once
    words = tuple(dict.fromkeys(w for w in normalise(text).split()
                                if len(w) >= 6 and w not in GENERIC and w not in in_skills
                                and (w,) not in bloom.phrases))
    levels = [bloom.phrases[tuple(v.split())][1] for v in verbs if bloom.phrases[tuple(v.split())][1]]
    return PO(code, name, text, "", verbs, skills, words, max(levels) if levels else None, derived=True)


@dataclass
class Link:
    po: str                                    # PO code
    strength: int                              # 1, 2 or 3
    reasons: list[str]                         # "verb: prove", "skill: Python", "words: real life"


@dataclass
class COMap:
    course_code: str
    course_title: str
    semester: Optional[str]
    text: str
    level: Optional[int]
    links: list[Link] = field(default_factory=list)


@dataclass
class MappingReport:
    programme: Programme
    framework: Framework
    outcomes: OutcomeReport
    cos: list[COMap]

    def course_matrix(self) -> list[tuple[str, str, dict[str, int]]]:
        """(course code, title, PO code -> strength) per course with outcomes, in programme order."""
        rows: dict[str, tuple[str, dict[str, list[int]]]] = {}
        for co in self.cos:
            title, cells = rows.setdefault(co.course_code, (co.course_title, {}))
            for link in co.links:
                cells.setdefault(link.po, []).append(link.strength)
        return [(code, title, {po: int(sum(v) / len(v) + 0.5) for po, v in cells.items()})
                for code, (title, cells) in rows.items()]

    def po_summary(self) -> list[tuple[PO, int, Optional[float]]]:
        """(PO, number of courses serving it, mean strength over those courses)."""
        matrix = self.course_matrix()
        out = []
        for po in self.framework.outcomes:
            vals = [cells[po.code] for _, _, cells in matrix if po.code in cells]
            out.append((po, len(vals), sum(vals) / len(vals) if vals else None))
        return out

    @property
    def unmapped(self) -> list[COMap]:
        return [co for co in self.cos if not co.links]


def _has_phrase(norm_text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", norm_text) is not None


def map_outcomes(programme: Programme, framework: Framework, taxonomy: Taxonomy,
                 bloom: Optional[Bloom] = None) -> MappingReport:
    bloom = bloom or Bloom.builtin()
    rep = analyse_outcomes(programme, bloom)
    for po in framework.outcomes:
        for s in po.skills:
            area = s.removeprefix("area:")
            known = {a.id for a in taxonomy.areas} if s.startswith("area:") else set(taxonomy.skills)
            if area not in known:
                raise FrameworkError(f"{po.code}: {'area' if s.startswith('area:') else 'skill'} {area!r} "
                                     f"is not in the {taxonomy.name} taxonomy")
    # Words in more than COMMON_SHARE of the outcomes say little about any one PO (derived POs only).
    word_counts: dict[str, int] = {}
    for r in rep.results:
        for w in set(normalise(r.text).split()):
            word_counts[w] = word_counts.get(w, 0) + 1
    common = {w for w, n in word_counts.items() if len(rep.results) >= 10 and n > COMMON_SHARE * len(rep.results)}
    course_skills: dict[str, set[str]] = {}
    for c in programme.courses:
        course_skills[c.code] = {h.skill for line in [c.title, *c.topics] for h in taxonomy.match(line)}
    cos = []
    for r in rep.results:
        norm = normalise(r.text)
        skills = {h.skill for h in taxonomy.match(r.text)}
        areas = {taxonomy.skills[s].area for s in skills}
        co = COMap(r.course_code, r.course_title, r.semester, r.text, r.level)
        for po in framework.outcomes:
            reasons, kinds = [], set()
            verbs = [v for v in r.verbs if v in po.verbs]
            if verbs:
                reasons.append("verb: " + ", ".join(verbs))
                kinds.add("verb")
            def serves(found: set[str]) -> list[str]:
                return sorted({taxonomy.skills[k].name for k in found
                               if k in po.skills or f"area:{taxonomy.skills[k].area}" in po.skills})
            if names := serves(skills):
                reasons.append("skill: " + ", ".join(names))
                kinds.add("skill")
            elif po.via_course and (names := serves(course_skills.get(r.course_code, set()))):
                reasons.append("course: " + ", ".join(names))       # weak: not counted as a kind
            words = [w for w in po.words if _has_phrase(norm, w) and not (po.derived and w in common)]
            if words:
                reasons.append("words: " + ", ".join(words))
                kinds.add("words")
            if not reasons or (po.derived and kinds == {"verb"} and set(verbs) <= GENERIC_VERBS):
                continue
            if not kinds:                    # only through the course: slight
                co.links.append(Link(po.code, 1, reasons))
                continue
            strength = 1 + (len(kinds) >= 2) + (po.level is not None and r.level is not None and r.level >= po.level)
            co.links.append(Link(po.code, strength, reasons))
        cos.append(co)
    return MappingReport(programme, framework, rep, cos)


def choose_framework(arg: Optional[str], programme: Programme, taxonomy: Taxonomy,
                     bloom: Optional[Bloom] = None) -> Framework:
    """`arg`: a built-in name, a framework YAML, or "own". By default the programme's own
    outcomes when it states any, else the UGC LOCF Mathematics graduate attributes."""
    bloom = bloom or Bloom.builtin()
    if arg == "own" or (arg is None and programme.programme_outcomes):
        if not programme.programme_outcomes:
            raise FrameworkError("the programme states no programme outcomes of its own")
        return Framework.from_programme(programme, bloom, taxonomy)
    return Framework.resolve(arg or "ugc-locf-mathematics")
