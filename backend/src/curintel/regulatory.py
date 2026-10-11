"""Regulatory checklist: one programme against the rules of a framework (e.g. UGC CCFUP 2022).

A rules file (YAML) names the framework and its source, its degree variants, the
categories it counts credits in, and the rules. Every rule carries the requirement
in words (`text`) and the page it comes from, so each line of the checklist can be
checked against the source document.

    id: ugc-ccfup-2022
    name: UGC Curriculum and Credit Framework for Undergraduate Programmes (2022)
    source: https://...
    variants:                       # first match on Programme.degree wins
      - {id: 3-year, name: 3-year UG degree, match: '\\b3\\b|three', semesters: 6}
    categories:                     # map a university's own labels onto the framework's
      - {id: major, name: Major (Core), match: 'major|\\bcore\\b|\\bDSC\\b'}
    rules:
      - {id: total, kind: total_credits, min: {3-year: 120}, page: 10, text: ...}

Rule kinds:

* ``total_credits``    - the credit scheme adds up to at least ``min``;
* ``category_credits`` - at least ``min`` credits in ``category`` (``range`` is shown
                         alongside when the framework gives one, e.g. "6-8");
* ``category_share``   - at least ``min`` (a fraction) of all credits in ``category``;
* ``course_on``        - a course on taxonomy skill ``skill`` (see ``analysis``); with
                         ``core: true`` (the default) it must be a core course.

``min`` is a number or a mapping of variant id to number; a rule with no ``min`` for
the programme's variant does not apply to it. ``level`` is ``required`` (default) or
``advisory`` (a model curriculum, say, rather than a regulation).

Credit rules read the programme's credit scheme (``Programme.scheme``). A course list
usually holds one department's courses and every elective alternative, so without a
scheme these rules are reported as *not checked* rather than guessed. A variant with
``semesters`` counts only the scheme's credits up to that semester (a 3-year check leaves
out semesters 7 and 8), and the checklist names any of its semesters the scheme lacks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Literal, Optional, Union

import yaml

from .analysis import profile
from .schema import Programme
from .taxonomy import Taxonomy

Status = Literal["met", "partly", "not_met", "not_checked"]
Kind = Literal["total_credits", "category_credits", "category_share", "course_on"]
KINDS = ("total_credits", "category_credits", "category_share", "course_on")
CREDIT_KINDS = ("total_credits", "category_credits", "category_share")
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Variant:
    id: str
    name: str
    match: Optional[re.Pattern[str]]
    semesters: Optional[int]
    auto: bool = True                      # may be chosen from the number of semesters alone


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    match: re.Pattern[str]


@dataclass(frozen=True)
class Rule:
    id: str
    kind: Kind
    text: str
    page: str = ""
    level: Literal["required", "advisory"] = "required"
    category: str = ""
    skill: str = ""
    core: bool = True
    min: Union[float, dict[str, float], None] = None
    range: str = ""
    note: str = ""

    def minimum(self, variant: str) -> Optional[float]:
        if isinstance(self.min, dict):
            return self.min.get(variant)
        return self.min


@dataclass
class Rules:
    id: str
    name: str
    source: str
    variants: list[Variant]
    categories: list[Category]
    rules: list[Rule]

    @classmethod
    def from_dict(cls, data: dict, where: str = "rules") -> "Rules":
        def rx(text, what):
            try:
                return re.compile(text, re.I)
            except re.error as exc:
                raise RulesError(f"{where}: {what}: bad pattern {text!r} ({exc})") from None
        try:
            variants = [Variant(str(v["id"]), v.get("name", str(v["id"])),
                                rx(v["match"], f"variant {v['id']}") if v.get("match") else None,
                                v.get("semesters"), v.get("auto", True)) for v in data.get("variants") or []]
            categories = [Category(c["id"], c.get("name", c["id"]), rx(c["match"], f"category {c['id']}"))
                          for c in data.get("categories") or []]
            rules = []
            for r in data["rules"]:
                rule = Rule(**{k: (str(v) if k == "page" else v) for k, v in r.items()})
                if rule.kind not in KINDS:
                    raise RulesError(f"{where}: rule {rule.id}: unknown kind {rule.kind!r}")
                if rule.kind in ("category_credits", "category_share") and rule.category not in {c.id for c in categories}:
                    raise RulesError(f"{where}: rule {rule.id}: unknown category {rule.category!r}")
                if rule.kind == "course_on" and not rule.skill:
                    raise RulesError(f"{where}: rule {rule.id}: course_on needs a skill")
                if rule.kind != "course_on" and rule.min is None:
                    raise RulesError(f"{where}: rule {rule.id}: needs min")
                if isinstance(rule.min, dict) and (unknown := set(rule.min) - {v.id for v in variants}):
                    raise RulesError(f"{where}: rule {rule.id}: unknown variant {sorted(unknown)[0]!r}")
                rules.append(rule)
            if len({r.id for r in rules}) != len(rules):
                raise RulesError(f"{where}: two rules share an id")
            return cls(str(data["id"]), data["name"], data.get("source", ""), variants, categories, rules)
        except (KeyError, TypeError) as exc:
            raise RulesError(f"{where}: missing or invalid field ({exc})") from None

    @classmethod
    def load(cls, path: str | Path) -> "Rules":
        path = Path(path)
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise RulesError(f"{path.name}: not valid YAML ({exc})") from None
        return cls.from_dict(data, path.name)

    @classmethod
    def builtin(cls, name: str) -> "Rules":
        res = resources.files("curintel.rules").joinpath(f"{name}.yaml")
        if not res.is_file():
            raise RulesError(f"no built-in rules named {name!r} (available: {', '.join(builtin_rules())})")
        return cls.from_dict(yaml.safe_load(res.read_text(encoding="utf-8")), f"{name}.yaml")

    @classmethod
    def resolve(cls, arg: str) -> "Rules":
        """A rules file path, or the name of a built-in rules file."""
        return cls.load(arg) if arg.lower().endswith((".yaml", ".yml")) else cls.builtin(arg)

    def category_of(self, label: str) -> Optional[Category]:
        return next((c for c in self.categories if c.match.search(label)), None)


def builtin_rules() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files("curintel.rules").iterdir() if p.name.endswith(".yaml"))


def semester_number(text: Optional[str]) -> Optional[int]:
    """'VII', 'Sem 7', '7' -> 7."""
    if not text:
        return None
    t = text.strip().lower()
    if m := re.search(r"\d+", t):
        return int(m.group())
    word = re.sub(r"^(semester|sem)\.?\s*", "", t)
    return ROMAN.get(word)


@dataclass
class RuleResult:
    rule: Rule
    status: Status
    found: str                             # what the programme has, e.g. "74 credits"
    expected: str                          # e.g. "at least 80 credits"
    evidence: list[str] = field(default_factory=list)


@dataclass
class Checklist:
    rules: Rules
    programme: Programme
    variant: Optional[Variant]
    variant_basis: str                     # how the variant was chosen, in words
    results: list[RuleResult]
    category_credits: dict[str, float]     # framework category id -> credits in the scheme
    unmapped: dict[str, float]             # scheme labels no category matched -> credits
    beyond: dict[str, float] = field(default_factory=dict)   # semesters past the variant -> credits left out
    missing_semesters: list[int] = field(default_factory=list)   # the variant's semesters with no credits

    @property
    def has_scheme(self) -> bool:
        return bool(self.programme.scheme)

    def count(self, status: Status, level: Optional[str] = None) -> int:
        return sum(r.status == status and (level is None or r.rule.level == level) for r in self.results)

    @property
    def checked(self) -> list[RuleResult]:
        return [r for r in self.results if r.status != "not_checked"]


def _choose_variant(rules: Rules, programme: Programme, degree: Optional[str] = None
                    ) -> tuple[Optional[Variant], str]:
    if not rules.variants:
        return None, ""
    for text, how in ((degree, "the degree was given as"), (programme.degree, "the programme's degree is recorded as")):
        if not text:
            continue
        for v in rules.variants:
            if v.match and v.match.search(text):
                return v, f'{how} "{text}"'
        if text is degree:
            raise RulesError(f"degree {degree!r} matches none of {rules.name}'s variants "
                             f"({', '.join(v.name for v in rules.variants)})")
    sems = [n for n in (semester_number(c.semester) for c in programme.courses) if n]
    sems += [n for n in (semester_number(s.semester) for s in programme.scheme) if n]
    if sems:
        last = max(sems)
        fits = [v for v in rules.variants if v.auto and v.semesters and v.semesters >= last]
        if fits:
            v = min(fits, key=lambda v: v.semesters)
            return v, f"its courses run to semester {last}; set the programme's degree to choose another"
    v = rules.variants[0]
    return v, "assumed: the programme records no degree or semesters"


def _num(x: float) -> str:
    return f"{x:g}"


def check(programme: Programme, rules: Rules, taxonomy: Taxonomy, degree: Optional[str] = None) -> Checklist:
    """Check `programme` against `rules`; `degree` overrides the programme's recorded degree."""
    variant, basis = _choose_variant(rules, programme, degree)
    vid = variant.id if variant else ""
    limit = variant.semesters if variant else None
    by_cat: dict[str, float] = {c.id: 0.0 for c in rules.categories}
    items_by_cat: dict[str, list[str]] = {c.id: [] for c in rules.categories}
    unmapped: dict[str, float] = {}
    beyond: dict[str, float] = {}
    scheme = []
    for item in programme.scheme:
        n = semester_number(item.semester)
        if limit and n and n > limit:
            beyond[item.semester] = beyond.get(item.semester, 0) + item.credits
        else:
            scheme.append(item)
    present = {semester_number(i.semester) for i in scheme}
    missing = ([n for n in range(1, limit + 1) if n not in present]
               if limit and scheme and present - {None} else [])
    for item in scheme:
        where = f"{item.category}{', semester ' + item.semester if item.semester else ''}: {_num(item.credits)}"
        cat = rules.category_of(item.category)
        if cat:
            by_cat[cat.id] += item.credits
            items_by_cat[cat.id].append(where)
        else:
            unmapped[item.category] = unmapped.get(item.category, 0) + item.credits
    total = sum(s.credits for s in scheme)
    names = {c.id: c.name for c in rules.categories}
    prof = None

    results = []
    for rule in rules.rules:
        need = rule.minimum(vid)
        if rule.kind != "course_on" and need is None:
            continue                       # does not apply to this variant
        if rule.kind in CREDIT_KINDS and not programme.scheme:
            expected = (f"at least {need:.0%} of credits" if rule.kind == "category_share"
                        else f"at least {_num(need)} credits")
            results.append(RuleResult(rule, "not_checked", "no credit scheme recorded", expected))
            continue
        if rule.kind == "total_credits":
            status: Status = "met" if total >= need else ("partly" if total else "not_met")
            results.append(RuleResult(rule, status, f"{_num(total)} credits", f"at least {_num(need)} credits"))
        elif rule.kind == "category_credits":
            got = by_cat[rule.category]
            status = "met" if got >= need else ("partly" if got else "not_met")
            expected = f"at least {_num(need)} credits" + (f" ({rule.range})" if rule.range else "")
            results.append(RuleResult(rule, status, f"{_num(got)} credits in {names[rule.category]}",
                                      expected, items_by_cat[rule.category]))
        elif rule.kind == "category_share":
            got = by_cat[rule.category]
            share = got / total if total else 0.0
            status = "met" if total and share >= need else "not_met"
            results.append(RuleResult(rule, status, f"{share:.0%} ({_num(got)} of {_num(total)} credits)",
                                      f"at least {need:.0%} of credits in {names[rule.category]}"))
        else:
            if rule.skill not in taxonomy.skills:
                raise RulesError(f"rule {rule.id}: skill {rule.skill!r} is not in the {taxonomy.name} taxonomy")
            prof = prof or profile(programme, taxonomy)
            cov = prof[rule.skill]
            skill = taxonomy.skills[rule.skill].name
            core_on = [c for c in cov.courses_on if not c.elective]
            expected = f"a {'core ' if rule.core else ''}course on {skill}"
            if core_on or (cov.courses_on and not rule.core):
                on = core_on or cov.courses_on
                results.append(RuleResult(rule, "met", f"{len(on)} course{'s' if len(on) > 1 else ''} on it",
                                          expected, [f"{c.code} {c.title}" for c in on]))
            elif cov.courses_on:
                results.append(RuleResult(rule, "partly", "only an elective course on it", expected,
                                          [f"{c.code} {c.title} (elective)" for c in cov.courses_on]))
            elif cov.level == "covered":
                courses = list(dict.fromkeys(f"{e.course_code} {e.course_title}" for e in cov.evidence))
                results.append(RuleResult(rule, "partly", "taught inside other courses", expected, courses))
            else:
                found = "mentioned once" if cov.level == "touched" else "not found"
                results.append(RuleResult(rule, "not_met", found, expected,
                                          [f"{e.course_code}: “{e.line}”" for e in cov.evidence]))
    return Checklist(rules, programme, variant, basis, results, by_cat, unmapped, beyond, missing)
