"""Skill profiles of programmes, and the benchmark of one programme against peers.

Coverage levels, per programme and skill:

* ``covered``  - a course is *about* it (the term is in a course title), or
                 it appears in two or more distinct syllabus lines;
* ``touched``  - it appears in exactly one syllabus line;
* ``absent``   - no evidence at all.

Peer share = fraction of peer programmes at ``covered``. Classification of
each skill for the programme under review:

* ``gap``         - not covered here, covered by at least half the peers
                    (priority High at 70%+, otherwise Medium);
* ``watch``       - not covered here, covered by 30-49% of peers;
* ``distinctive`` - covered here, and fewer than 30% of peers even mention it
                    (covered or touched);
* ``aligned``     - covered here, and mentioned by at least 30% of peers;
* ``uncommon``    - not covered here, and by fewer than 30% of peers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Literal, Optional

from .schema import Programme
from .taxonomy import Taxonomy

Level = Literal["covered", "touched", "absent"]
Status = Literal["gap", "watch", "distinctive", "aligned", "uncommon"]

GAP_SHARE = 0.5
HIGH_SHARE = 0.7
WATCH_SHARE = 0.3
LEVEL_SCORE = {"covered": 1.0, "touched": 0.5, "absent": 0.0}


@dataclass(frozen=True)
class Evidence:
    course_code: str
    course_title: str
    field: Literal["title", "topic", "outcome"]
    line: str
    term: str


@dataclass
class SkillCoverage:
    skill: str
    level: Level
    evidence: list[Evidence]

    @property
    def courses(self) -> list[str]:
        return list(dict.fromkeys(e.course_code for e in self.evidence))


def _lines(programme: Programme):
    for c in programme.courses:
        yield c, "title", c.title
        for t in c.topics:
            yield c, "topic", t
        for o in c.outcomes:
            yield c, "outcome", o


def profile(programme: Programme, taxonomy: Taxonomy) -> dict[str, SkillCoverage]:
    """Coverage of every taxonomy skill in one programme."""
    evidence: dict[str, list[Evidence]] = {s: [] for s in taxonomy.skills}
    for course, fld, line in _lines(programme):
        seen: set[str] = set()
        for hit in taxonomy.match(line):
            if hit.skill in seen:           # one piece of evidence per line
                continue
            seen.add(hit.skill)
            evidence[hit.skill].append(Evidence(course.code, course.title, fld, line, hit.term))
    result = {}
    for skill, ev in evidence.items():
        distinct_lines = {(e.course_code, e.field, e.line) for e in ev}
        if any(e.field == "title" for e in ev) or len(distinct_lines) >= 2:
            level: Level = "covered"
        elif ev:
            level = "touched"
        else:
            level = "absent"
        result[skill] = SkillCoverage(skill, level, ev)
    return result


def unmapped_lines(programme: Programme, taxonomy: Taxonomy) -> list[tuple[str, str]]:
    """Topic lines in which no skill was found: candidates for new taxonomy terms."""
    return [(c.code, line) for c, fld, line in _lines(programme)
            if fld == "topic" and not taxonomy.match(line)]


@dataclass
class SkillRow:
    skill: str
    name: str
    area: str
    own: SkillCoverage
    peer_levels: dict[str, Level]          # peer label -> level
    peer_share: float                      # fraction of peers at "covered"
    peer_touched_share: float              # fraction at "touched"
    status: Status
    priority: Optional[Literal["High", "Medium"]] = None
    peer_evidence: dict[str, list[Evidence]] = field(default_factory=dict)

    @property
    def peer_courses(self) -> dict[str, list[str]]:
        """Peer label -> titles of its courses with evidence (peers with none omitted)."""
        return {p: sorted({e.course_title for e in ev}) for p, ev in self.peer_evidence.items() if ev}

    @property
    def peers_covering(self) -> list[str]:
        return [p for p, lv in self.peer_levels.items() if lv == "covered"]


@dataclass
class AreaScore:
    area: str
    name: str
    alignment: Optional[float]             # None when peers share no core skill here
    core_skills: int


@dataclass
class StructureRow:
    label: str
    courses: int
    credits: Optional[float]                # None when any course has no credits recorded


@dataclass
class Benchmark:
    own: Programme
    peers: list[Programme]
    taxonomy: Taxonomy
    rows: list[SkillRow]
    areas: list[AreaScore]
    alignment: Optional[float]             # 0-100 over the peer-core skills
    structure: list[StructureRow] = field(default_factory=list)

    @property
    def peer_median_credits(self) -> Optional[float]:
        values = [s.credits for s in self.structure[1:] if s.credits is not None]
        return median(values) if values else None

    @property
    def peer_median_courses(self) -> Optional[float]:
        values = [s.courses for s in self.structure[1:]]
        return median(values) if values else None

    def by_status(self, status: Status) -> list[SkillRow]:
        rows = [r for r in self.rows if r.status == status]
        return sorted(rows, key=lambda r: (-r.peer_share, r.name))


def _classify(own: Level, share: float, mention_share: float) -> tuple[Status, Optional[str]]:
    if own == "covered":
        return ("aligned" if mention_share >= WATCH_SHARE else "distinctive"), None
    if share >= GAP_SHARE:
        return "gap", ("High" if share >= HIGH_SHARE else "Medium")
    if share >= WATCH_SHARE:
        return "watch", None
    return "uncommon", None


def _alignment(rows: list[SkillRow]) -> Optional[float]:
    core = [r for r in rows if r.peer_share >= GAP_SHARE]
    if not core:
        return None
    return 100 * sum(LEVEL_SCORE[r.own.level] for r in core) / len(core)


def benchmark(own: Programme, peers: list[Programme], taxonomy: Taxonomy) -> Benchmark:
    if not peers:
        raise ValueError("benchmarking needs at least one peer programme")
    labels = [p.label for p in peers]
    if len(set(labels)) != len(labels):
        raise ValueError("two peer programmes have the same institution name")
    own_profile = profile(own, taxonomy)
    peer_profiles = {p.label: profile(p, taxonomy) for p in peers}
    rows = []
    for skill in taxonomy.skills.values():
        levels = {label: prof[skill.id].level for label, prof in peer_profiles.items()}
        share = sum(lv == "covered" for lv in levels.values()) / len(peers)
        touched = sum(lv == "touched" for lv in levels.values()) / len(peers)
        status, priority = _classify(own_profile[skill.id].level, share, share + touched)
        evidence = {label: prof[skill.id].evidence for label, prof in peer_profiles.items()}
        rows.append(SkillRow(skill.id, skill.name, skill.area, own_profile[skill.id],
                             levels, share, touched, status, priority, evidence))
    areas = []
    for area in taxonomy.areas:
        area_rows = [r for r in rows if r.area == area.id]
        areas.append(AreaScore(area.id, area.name, _alignment(area_rows),
                               sum(r.peer_share >= GAP_SHARE for r in area_rows)))
    structure = [StructureRow(p.label, len(p.courses),
                              p.total_credits if all(c.credits is not None for c in p.courses) else None)
                 for p in [own, *peers]]
    return Benchmark(own, peers, taxonomy, rows, areas, _alignment(rows), structure)
