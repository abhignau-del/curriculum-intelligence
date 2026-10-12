"""The benchmark report: one self-contained HTML file, plus the same data as JSON.

Every finding carries its evidence: which peers cover a skill and in which
course, and which syllabus line triggered a match here.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Optional

from . import __version__
from .analysis import Benchmark, SkillRow, unmapped_lines
from .mapping import MappingReport
from .outcomes import HIGHER_ORDER, OutcomeReport
from .overlap import OverlapPair
from .regulatory import Checklist

LEVEL_MARK = {"covered": ("✓", "Covered"), "touched": ("△", "Mentioned once"), "absent": ("·", "Not found")}
ELECTIVE_MARK = ("○", "Covered only by electives")
COURSE_MARK = ("●", "A core course on it")


def _mark(level: str, basis: str | None, course_basis: str | None = None) -> tuple[str, str, str]:
    """(glyph, label, css class) for one coverage cell."""
    if course_basis == "core":
        return (*COURSE_MARK, "c-course")
    note = " (an elective course on it)" if course_basis == "elective" else ""
    if level == "covered" and basis == "elective":
        return ELECTIVE_MARK[0], ELECTIVE_MARK[1] + note, "c-elective"
    glyph, label = LEVEL_MARK[level]
    return glyph, label + note, f"c-{level}"


def _peers_split(b: Benchmark) -> bool:
    """True when at least one peer records which of its courses are electives."""
    recorded = set(b.records_electives)
    return any(p.label in recorded for p in b.peers)


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0f}%"


def _num(x: float | None) -> str:
    return "–" if x is None else (f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}")


# ----- JSON --------------------------------------------------------------

def checklist_dict(cl: Checklist) -> dict:
    return {
        "id": cl.rules.id, "name": cl.rules.name, "source": cl.rules.source,
        "variant": cl.variant.id if cl.variant else None,
        "variant_name": cl.variant.name if cl.variant else None, "variant_basis": cl.variant_basis,
        "has_scheme": cl.has_scheme, "category_credits": cl.category_credits, "unmapped": cl.unmapped,
        "beyond": cl.beyond, "missing_semesters": cl.missing_semesters,
        "results": [{"id": r.rule.id, "kind": r.rule.kind, "text": r.rule.text, "page": r.rule.page,
                     "level": r.rule.level, "note": r.rule.note, "status": r.status, "found": r.found,
                     "expected": r.expected, "evidence": r.evidence} for r in cl.results],
    }


def outcomes_dict(rep: OutcomeReport) -> dict:
    return {
        "verb_list": rep.bloom.name,
        "levels": [{"level": lv.level, "id": lv.id, "name": lv.name} for lv in rep.bloom.levels],
        "outcomes": [{"course": r.course_code, "course_title": r.course_title, "semester": r.semester,
                      "text": r.text, "level": r.level, "verbs": r.verbs, "flags": r.flags} for r in rep.results],
        "without_outcomes": [{"course": c, "course_title": t} for c, t in rep.without_outcomes],
        "duplicates": [{"text": t, "courses": codes} for t, codes in rep.duplicates],
        "by_year": [{"year": y, "count": len(rs), "levels": {("none" if k is None else str(k)): v for k, v in rep.counts(rs).items()},
                     "higher_order_share": rep.higher_order_share(rs),
                     "vague": sum("vague" in r.flags for r in rs)} for y, rs in rep.by_year()],
        "higher_order_share": rep.higher_order_share(rep.results),
    }


def copo_dict(m: MappingReport) -> dict:
    return {
        "framework": {"id": m.framework.id, "name": m.framework.name, "source": m.framework.source},
        "pos": [{"code": po.code, "name": po.name, "text": po.text, "page": po.page, "courses": n, "mean": mean}
                for po, n, mean in m.po_summary()],
        "matrix": [{"course": code, "course_title": title, "cells": cells} for code, title, cells in m.course_matrix()],
        "cos": [{"course": co.course_code, "text": co.text, "level": co.level,
                 "links": [{"po": li.po, "strength": li.strength, "reasons": li.reasons} for li in co.links]}
                for co in m.cos],
        "unmapped": [{"course": co.course_code, "text": co.text} for co in m.unmapped],
    }


def to_dict(b: Benchmark, overlaps: list[OverlapPair], checklists: list[Checklist] = (),
            outcomes: Optional[OutcomeReport] = None, copo: Optional[MappingReport] = None) -> dict:
    def ev(e):
        return {"course": e.course_code, "course_title": e.course_title, "field": e.field,
                "line": e.line, "term": e.term}

    def on(cs):
        return [{"course": c.code, "course_title": c.title, "elective": c.elective, "by": c.by} for c in cs]
    return {
        "generated_by": f"curintel {__version__}",
        "programme": {"institution": b.own.institution, "name": b.own.name, "year": b.own.year},
        "peers": [{"institution": p.institution, "name": p.name, "year": p.year} for p in b.peers],
        "unmapped": [{"course": c, "line": line} for c, line in unmapped_lines(b.own, b.taxonomy)],
        "taxonomy": b.taxonomy.name,
        "alignment": b.alignment,
        "records_electives": b.records_electives,
        "areas": [{"id": a.area, "name": a.name, "alignment": a.alignment, "core_skills": a.core_skills}
                  for a in b.areas],
        "skills": [{
            "id": r.skill, "name": r.name, "area": r.area, "status": r.status, "priority": r.priority,
            "own_level": r.own.level, "own_evidence": [ev(e) for e in r.own.evidence],
            "peer_share": r.peer_share, "peer_touched_share": r.peer_touched_share,
            "peer_levels": r.peer_levels,
            "own_basis": r.own_basis, "peer_basis": r.peer_basis, "peer_core_share": r.peer_core_share,
            "own_courses_on": on(r.own.courses_on), "own_course_basis": r.own_course_basis,
            "peer_courses_on": {p: on(cs) for p, cs in r.peer_courses_on.items()},
            "peer_course_basis": r.peer_course_basis, "peer_course_share": r.peer_course_share,
            "peer_core_course_share": r.peer_core_course_share,
            "peer_evidence": {p: [ev(e) for e in evs] for p, evs in r.peer_evidence.items() if evs},
        } for r in b.rows],
        "overlaps": [o.__dict__ for o in overlaps],
        "structure": [s.__dict__ for s in b.structure],
        "regulatory": [checklist_dict(cl) for cl in checklists],
        "outcomes": outcomes_dict(outcomes) if outcomes else None,
        "copo": copo_dict(copo) if copo else None,
    }


# ----- HTML --------------------------------------------------------------

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d2430;--muted:#5d6675;--line:#e2e4e8;--accent:#2f5d8a;
--hi:#b4441f;--hi-bg:#fbe9e2;--md:#8a6d00;--md-bg:#fbf3d6;--ok:#2e7d4f;--ok-bg:#e3f2e8;--soft:#eef1f5}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1c2027;--ink:#e6e8eb;--muted:#9aa3b0;
--line:#2c323b;--accent:#7fb0e0;--hi:#f0906c;--hi-bg:#3a2219;--md:#e2c35a;--md-bg:#352d12;--ok:#7cc79a;
--ok-bg:#1b3125;--soft:#242a33}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 6px}h3{font-size:15px;margin:18px 0 6px}
p.lead,.muted{color:var(--muted)}p.lead{margin:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tile b{display:block;font-size:28px;line-height:1.2}.tile span{color:var(--muted);font-size:13px}
.tile.na b{font-size:15px;color:var(--muted);font-weight:500;padding:8px 0 3px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 16px;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;white-space:nowrap;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600}
.High{background:var(--hi-bg);color:var(--hi)}.Medium{background:var(--md-bg);color:var(--md)}
.ok{background:var(--ok-bg);color:var(--ok)}.soft{background:var(--soft);color:var(--muted)}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;min-width:120px}
.bar i{display:block;height:100%;background:var(--accent)}
details{margin:2px 0}summary{cursor:pointer;color:var(--accent);font-size:13px}
ul.ev{margin:6px 0 4px;padding-left:18px;font-size:13px;color:var(--muted)}ul.ev b{color:var(--ink);font-weight:600}
.say{margin:2px 0 4px}
table.matrix td,table.matrix th{padding:4px 5px;text-align:center;font-size:13px}
table.matrix td:first-child,table.matrix th:first-child{text-align:left;white-space:nowrap}
table.matrix th.peer{writing-mode:vertical-rl;transform:rotate(180deg);text-transform:none;letter-spacing:0;height:150px;font-weight:500}
table.matrix th.own{writing-mode:vertical-rl;transform:rotate(180deg);text-transform:none;letter-spacing:0;color:var(--ink)}
table.matrix tr.area td{background:var(--soft);font-weight:600;text-align:left}
.c-course{color:var(--ok);font-weight:700}.c-covered{color:var(--ok);font-weight:700}.c-elective{color:var(--ok)}.small{font-size:12px;white-space:nowrap}.c-touched{color:var(--md)}.c-absent{color:var(--line)}
td.ownc{background:var(--soft)}
@media (max-width:640px){table.gaps tr{display:grid;grid-template-columns:1fr auto auto;column-gap:8px}
table.gaps tr:first-child{display:none}table.gaps td{border:0;padding:6px 0}
table.gaps td.finding{grid-column:1/-1;order:4;padding-top:0}table.gaps tr+tr{border-top:1px solid var(--line);padding:6px 0}
table.matrix th.peer{height:120px}
table.rules tr{display:grid;grid-template-columns:1fr 1fr auto;column-gap:10px}table.rules tr:first-child{display:none}
table.rules td{border:0;padding:3px 0}table.rules td.req{grid-column:1/-1;font-weight:600;padding-top:8px}
table.rules tr+tr{border-top:1px solid var(--line);padding-bottom:6px}
table.rules td[data-label]::before{content:attr(data-label);display:block;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
a{color:var(--accent)}
code{font-size:13px}footer{margin-top:48px;color:var(--muted);font-size:13px}
:root{--b1:#c9d6e3;--b2:#9fb7cf;--b3:#6f93b8;--b4:#3f6e9c;--b5:#284f78;--b6:#163453;--b0:#e8e3d8}
@media (prefers-color-scheme:dark){:root{--b1:#2b3a4a;--b2:#3a5168;--b3:#4f6f8f;--b4:#6d93b8;--b5:#93b6d8;--b6:#c3daf0;--b0:#3a3428}}
.stack{display:flex;height:14px;border-radius:3px;overflow:hidden;min-width:160px;background:var(--soft)}
.stack i{display:block;height:100%}.lv{display:inline-block;min-width:22px;text-align:center;border-radius:3px;
font-size:11px;font-weight:700;padding:0 4px;margin-right:6px}.lv1,.lv2,.lv0{color:#1d2430}.lv3,.lv4,.lv5,.lv6{color:#fff}
@media (prefers-color-scheme:dark){.lv1,.lv2,.lv3,.lv0{color:#e6e8eb}.lv4,.lv5,.lv6{color:#14171c}}
.lv1{background:var(--b1)}.lv2{background:var(--b2)}.lv3{background:var(--b3)}.lv4{background:var(--b4)}
.lv5{background:var(--b5)}.lv6{background:var(--b6)}.lv0{background:var(--b0)}
ul.co{list-style:none;padding-left:0;margin:4px 0 10px;font-size:14px}ul.co li{margin:3px 0}
table.copo td,table.copo th{text-align:center;padding:4px 6px;font-size:13px}
table.copo td:first-child,table.copo th:first-child{text-align:left}
table.copo td.s1{background:var(--b1)}table.copo td.s2{background:var(--b3);color:#fff}table.copo td.s3{background:var(--b5);color:#fff}
@media (prefers-color-scheme:dark){table.copo td.s2,table.copo td.s3{color:#14171c}}
table.copo tr.sum td{background:var(--soft);font-weight:600}
.sw{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:baseline}
table.years td.lvls{min-width:220px}table.years td.lvls .small{white-space:normal}
@media (max-width:640px){table.years tr{display:grid;grid-template-columns:1fr auto auto auto;column-gap:12px}
table.years tr:first-child{display:none}table.years td{border:0;padding:3px 0;min-width:0}
table.years td.lvls{grid-column:1/-1;order:5}table.years tr+tr{border-top:1px solid var(--line);padding:6px 0}
table.years td[data-label]{min-width:max-content}table.years td[data-label]::before{content:attr(data-label);display:block;font-size:11px;color:var(--muted);
text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}}
"""


def _evidence_list(items: list[str]) -> str:
    return '<ul class="ev">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def _own_evidence(row: SkillRow) -> str:
    return _evidence_list([f"<b>{escape(e.course_title)}</b> ({escape(e.course_code)}, {e.field}): "
                           f"“{escape(e.line)}”" for e in row.own.evidence])


def _course_on_note(b: Benchmark, cs) -> str:
    """'a core course on it: Title', naming the core courses when there are any."""
    if not _peers_split(b):
        kind, titles = "", [c.title for c in cs]
    elif all(c.elective for c in cs):
        kind, titles = "elective ", [c.title for c in cs]
    else:
        kind, titles = "core ", [c.title for c in cs if not c.elective]
    article = "an" if kind.startswith("e") else "a"
    return f"{article} {kind}course on it: {', '.join(dict.fromkeys(titles))}"


def _peer_evidence(b: Benchmark, row: SkillRow) -> str:
    items = []
    for peer in b.peers:
        courses = row.peer_courses.get(peer.label)
        if not courses:
            continue
        notes = []
        if row.peer_levels[peer.label] != "covered":
            notes.append("mentioned once")
        elif row.peer_basis.get(peer.label) == "elective":
            notes.append("elective only")
        if peer.label in row.peer_courses_on:
            notes.append(_course_on_note(b, row.peer_courses_on[peer.label]))
        mark = f" <i>({escape('; '.join(notes))})</i>" if notes else ""
        items.append(f"<b>{escape(peer.label)}</b>{mark}: {escape(', '.join(courses))}")
    return _evidence_list(items)


def _courses_on_sentence(b: Benchmark, r: SkillRow) -> str:
    """How many of the covering peers have a whole course on the skill."""
    if not r.peers_covering:
        return ""
    n = len(r.peer_courses_on)
    if n == 0:
        return " None of them has a course on it: they teach it inside other courses."
    has = "has" if n == 1 else "have"
    if not _peers_split(b):
        return f" {n} of them {has} a course on it."
    core = sum(v == "core" for v in r.peer_course_basis.values())
    if core == n:
        kind = "all core" if n > 1 else "core"
    elif core == 0:
        kind = "all elective" if n > 1 else "elective"
    else:
        kind = f"{core} core, {n - core} elective"
    return f" {n} of them {has} a course on it ({kind})."


def _gap_sentence(b: Benchmark, r: SkillRow) -> str:
    here = ("is mentioned in only one syllabus line here" if r.own.level == "touched"
            else "is not found in this curriculum")
    split = ""
    if _peers_split(b):
        split = f": in the core of {len(r.peers_core)}, only as an elective in {len(r.peers_elective_only)}"
    return (f"{escape(r.name)} is covered by {_pct(100 * r.peer_share)} of benchmarked programmes "
            f"({len(r.peers_covering)} of {len(b.peers)}{split}) but {here}."
            + _courses_on_sentence(b, r))


def _share_cell(b: Benchmark, r: SkillRow) -> str:
    if _peers_split(b):
        extra = (f"core {_pct(100 * r.peer_core_share)}"
                 f"<br>core course {_pct(100 * r.peer_core_course_share)}")
    else:
        extra = f"course {_pct(100 * r.peer_course_share)}"
    return f"<td class='n'>{_pct(100 * r.peer_share)}<br><span class='muted small'>{extra}</span></td>"


def _section_gaps(b: Benchmark) -> str:
    gaps = b.by_status("gap")
    if not gaps:
        return "<h2>Priority gaps</h2><p class='muted'>None: every skill that half or more of the peers cover is covered here.</p>"
    rows = []
    for r in gaps:
        area = b.taxonomy.skills[r.skill].area
        area_name = next(a.name for a in b.taxonomy.areas if a.id == area)
        own = ""
        if r.own.evidence:
            own = f"<details><summary>The one line found here</summary>{_own_evidence(r)}</details>"
        rows.append(
            f"<tr><td><b>{escape(r.name)}</b><br><span class='muted'>{escape(area_name)}</span></td>"
            f"<td class='finding'><p class='say'>{_gap_sentence(b, r)}</p>{own}"
            f"<details><summary>Where peers cover it</summary>{_peer_evidence(b, r)}</details></td>"
            f"{_share_cell(b, r)}"
            f"<td><span class='pill {r.priority}'>{r.priority}</span></td></tr>")
    return ("<h2>Priority gaps</h2><p class='muted'>Skills that at least half of the peer programmes cover "
            "and this one does not. High = 70% or more of peers.</p><div class='card'><table class='gaps'>"
            "<tr><th>Skill</th><th>Finding</th><th class='n'>Peers</th><th>Priority</th></tr>"
            + "".join(rows) + "</table></div>")


def _section_list(b: Benchmark, status: str, title: str, intro: str, own_ev: bool) -> str:
    rows = b.by_status(status)  # type: ignore[arg-type]
    if not rows:
        return ""
    body = []
    for r in rows:
        detail = ""
        if r.own.evidence:
            label_ev = "Evidence here" if own_ev else "The one line found here"
            detail += f"<details><summary>{label_ev}</summary>{_own_evidence(r)}</details>"
        if not own_ev:
            detail += f"<details><summary>Where peers cover it</summary>{_peer_evidence(b, r)}</details>"
        mark, label, css = _mark(r.own.level, r.own_basis, r.own_course_basis)
        body.append(f"<tr><td><b>{escape(r.name)}</b>{detail}</td>"
                    f"<td><span class='{css}'>{mark}</span> {label}</td>"
                    f"{_share_cell(b, r)}"
                    f"<td class='n'>{_pct(100 * r.peer_touched_share)}</td></tr>")
    return (f"<h2>{title}</h2><p class='muted'>{intro}</p><div class='card'><table>"
            "<tr><th>Skill</th><th>Here</th><th class='n'>Peers covering</th><th class='n'>Peers mentioning once</th></tr>"
            + "".join(body) + "</table></div>")


def _section_overlap(overlaps: list[OverlapPair]) -> str:
    head = ("<h2>Course overlap</h2><p class='muted'>Pairs of courses in this programme whose topic lists "
            "share much of their vocabulary (cosine similarity of weighted terms, 0–100%). "
            "A committee can merge, differentiate or redistribute them. Theory–lab pairs are expected to overlap.</p>")
    if not overlaps:
        return head + "<p class='muted'>No pair reached the threshold.</p>"
    rows = []
    for o in overlaps:
        level = ("<span class='pill soft'>Theory–lab pair</span>" if o.theory_lab_pair
                 else f"<span class='pill {'High' if o.level == 'High' else 'Medium'}'>{o.level}</span>")
        skills = f"<br><span class='muted'>Shared skills: {escape(', '.join(o.shared_skills))}</span>" if o.shared_skills else ""
        rows.append(f"<tr><td><b>{escape(o.a_title)}</b> <span class='muted'>{escape(o.a)}</span><br>"
                    f"<b>{escape(o.b_title)}</b> <span class='muted'>{escape(o.b)}</span></td>"
                    f"<td class='n'>{100 * o.similarity:.0f}%</td><td>{level}</td>"
                    f"<td>{escape(', '.join(o.shared_terms))}{skills}</td></tr>")
    return (head + "<div class='card'><table><tr><th>Courses</th><th class='n'>Similarity</th><th>Level</th>"
            "<th>Strongest shared terms</th></tr>" + "".join(rows) + "</table></div>")


def _section_areas(b: Benchmark) -> str:
    rows = []
    for a in b.areas:
        bar = (f"<div class='bar'><i style='width:{a.alignment:.0f}%'></i></div>" if a.alignment is not None
               else "<span class='muted'>no skill shared by half the peers</span>")
        rows.append(f"<tr><td>{escape(a.name)}</td><td>{bar}</td><td class='n'>{_pct(a.alignment)}</td>"
                    f"<td class='n'>{a.core_skills}</td></tr>")
    return ("<h2>Alignment by area</h2><p class='muted'>Of the skills that at least half of the peers cover "
            "(“peer-core” skills), how many this programme covers. A skill mentioned only once here counts half.</p>"
            "<div class='card'><table><tr><th>Area</th><th></th><th class='n'>Alignment</th>"
            "<th class='n'>Peer-core skills</th></tr>" + "".join(rows) + "</table></div>")


def _section_structure(b: Benchmark) -> str:
    rows = "".join(f"<tr><td>{escape(s.label)}{' <b>(this programme)</b>' if i == 0 else ''}</td>"
                   f"<td class='n'>{s.courses}</td><td class='n'>{_num(s.credits)}</td></tr>"
                   for i, s in enumerate(b.structure))
    rows += (f"<tr><td><i>Peer median</i></td><td class='n'>{_num(b.peer_median_courses)}</td>"
             f"<td class='n'>{_num(b.peer_median_credits)}</td></tr>")
    return ("<h2>Programme structure</h2><p class='muted'>Everything listed for each programme, including every elective alternative, so these are not the credits a student earns. A dash means some courses have no credits recorded.</p><div class='card'><table><tr><th>Programme</th>"
            "<th class='n'>Courses offered</th><th class='n'>Credits offered</th></tr>" + rows + "</table></div>")


def _lv(level: Optional[int], names: dict[int, str]) -> str:
    if level is None:
        return "<span class='lv lv0' title='No level: vague or no action verb'>–</span>"
    return f"<span class='lv lv{level}' title='{escape(names[level])}'>{level}</span>"


def section_outcomes(rep: OutcomeReport) -> str:
    names = {lv.level: lv.name for lv in rep.bloom.levels}
    n, total_courses = len(rep.results), len(rep.programme.courses)
    head = ("<h2>Course outcomes</h2><p class='muted'>Each outcome's level in the revised Bloom's taxonomy, "
            "read from the verbs that open it (1 Remember, 2 Understand, 3 Apply, 4 Analyse, 5 Evaluate, "
            "6 Create). Higher-order means Analyse, Evaluate or Create. Outcomes that open with a verb hard "
            "to assess, such as <i>understand</i> or <i>learn</i>, are marked vague.</p>")
    if not n:
        return head + "<p class='muted'>No course in this programme states its outcomes.</p>"
    vague, no_verb = rep.flagged("vague"), rep.flagged("no_verb")
    share = rep.higher_order_share(rep.results)
    summary = (f"<p>{n} outcomes in {rep.courses_with_outcomes} of {total_courses} courses · "
               f"{_pct(None if share is None else 100 * share)} higher-order · {len(vague)} vague "
               f"({_pct(100 * len(vague) / n)}) · {len(no_verb)} with no action verb · "
               f"{len(rep.duplicates)} stated for more than one course.</p>")
    rows = []
    for year, rs in rep.by_year():
        counts = rep.counts(rs)
        bar = "".join(f"<i class='lv{lv}' style='width:{100 * c / len(rs):.1f}%' title='{escape(names[lv])}: {c}'></i>"
                      for lv, c in counts.items() if lv is not None and c)
        if counts[None]:
            bar += f"<i class='lv0' style='width:{100 * counts[None] / len(rs):.1f}%' title='No level: {counts[None]}'></i>"
        nums = " · ".join(f"<i class='sw lv{lv}'></i>{escape(names[lv])} {c}"
                          for lv, c in counts.items() if lv is not None and c)
        hs = rep.higher_order_share(rs)
        rows.append(f"<tr><td>{escape(year or 'Semester not recorded')}</td><td class='n' data-label='Outcomes'>{len(rs)}</td>"
                    f"<td class='lvls'><div class='stack'>{bar}</div><span class='muted small'>{nums}"
                    f"{f' · {counts[None]} no level' if counts[None] else ''}</span></td>"
                    f"<td class='n' data-label='Higher-order'>{_pct(None if hs is None else 100 * hs)}</td>"
                    f"<td class='n' data-label='Vague'>{sum('vague' in r.flags for r in rs)}</td></tr>")
    table = ("<div class='card'><table class='years'><tr><th>Year</th><th class='n'>Outcomes</th><th>Levels</th>"
             "<th class='n'>Higher-order</th><th class='n'>Vague</th></tr>" + "".join(rows) + "</table></div>")
    parts = []
    if vague:
        by_verb: dict[str, int] = {}
        for r in vague:
            by_verb[r.verbs[0]] = by_verb.get(r.verbs[0], 0) + 1
        verbs = ", ".join(f"<i>{escape(v)}</i> ({c})" for v, c in sorted(by_verb.items(), key=lambda kv: -kv[1]))
        parts.append(f"<details><summary>{len(vague)} vague outcome{'' if len(vague) == 1 else 's'}: {verbs}</summary>"
                     + _evidence_list([f"<b>{escape(r.course_code)}</b>: {escape(r.text)}" for r in vague]) + "</details>")
    if no_verb:
        parts.append(f"<details><summary>{len(no_verb)} outcome{'' if len(no_verb) == 1 else 's'} with no action verb at the start</summary>"
                     + _evidence_list([f"<b>{escape(r.course_code)}</b>: {escape(r.text)}" for r in no_verb]) + "</details>")
    if rep.duplicates:
        k = len(rep.duplicates)
        parts.append(f"<details><summary>{k} outcome{' is' if k == 1 else 's are'} stated for more than one course</summary>"
                     + _evidence_list([f"<b>{escape(', '.join(codes))}</b>: {escape(t)}" for t, codes in rep.duplicates])
                     + "</details>")
    if rep.without_outcomes:
        k = len(rep.without_outcomes)
        parts.append(f"<details><summary>{k} course{' states' if k == 1 else 's state'} no outcomes</summary>"
                     + _evidence_list([f"<b>{escape(c)}</b> {escape(t)}" for c, t in rep.without_outcomes]) + "</details>")
    courses: dict[str, list] = {}
    for r in rep.results:
        courses.setdefault(r.course_code, []).append(r)
    vague_note = " <span class='muted small'>(vague)</span>"
    per_course = "".join(
        f"<h3>{escape(rs[0].course_title)} <span class='muted small'>{escape(code)}"
        f"{' · semester ' + escape(rs[0].semester) if rs[0].semester else ''}</span></h3><ul class='co'>"
        + "".join(f"<li>{_lv(r.level, names)}{escape(r.text)}{vague_note if 'vague' in r.flags else ''}</li>"
                  for r in rs)
        + "</ul>" for code, rs in courses.items())
    parts.append(f"<details><summary>Every outcome, by course</summary>{per_course}</details>")
    return head + summary + table + "<div style='margin-top:10px'>" + "".join(parts) + "</div>"


def section_copo(m: MappingReport) -> str:
    fw = m.framework
    head = (f"<h2>CO–PO mapping: {escape(fw.name)}</h2><p class='muted'>Which programme outcomes each course "
            "outcome serves, on the 1–3 scale of NAAC and NBA matrices (1 slight, 2 moderate, 3 substantial). "
            "An outcome serves a PO when its verbs, the skills it names or its words match the PO's indicators; "
            "it maps more strongly when indicators of two kinds match, and when its Bloom level reaches the "
            "level the PO calls for. A course's cell is the rounded mean over its outcomes that serve the PO."
            + (f" Source: {escape(fw.source)}." if fw.source else "") + "</p>")
    if not m.cos:
        return head + "<p class='muted'>No course in this programme states its outcomes, so there is nothing to map.</p>"
    summary = m.po_summary()
    weak = [po for po, n, mean in summary if n == 0]
    notes = ""
    if weak:
        notes += ("<p>" + ", ".join(f"<b>{escape(po.code)}</b> {escape(po.name)}" for po in weak)
                  + (" is" if len(weak) == 1 else " are") + " served by no course outcome.</p>")
    po_rows = "".join(
        f"<tr><td><b>{escape(po.code)}</b></td><td>{escape(po.name)}<br><span class='muted small'>{escape(po.text)}"
        f"{' (p. ' + escape(po.page) + ')' if po.page else ''}</span></td><td class='n'>{n}</td>"
        f"<td class='n'>{'–' if mean is None else f'{mean:.1f}'}</td></tr>" for po, n, mean in summary)
    pos_table = ("<div class='card'><table><tr><th>PO</th><th>Outcome</th><th class='n'>Courses</th>"
                 "<th class='n'>Mean</th></tr>" + po_rows + "</table></div>")
    codes = [po.code for po in fw.outcomes]
    head_row = "<tr><th>Course</th>" + "".join(
        f"<th title='{escape(po.label)}'>{escape(po.code)}</th>" for po in fw.outcomes) + "</tr>"
    body = []
    for code, title, cells in m.course_matrix():
        tds = "".join(f"<td class='s{cells[c]}'>{cells[c]}</td>" if c in cells else "<td class='muted'>·</td>"
                      for c in codes)
        body.append(f"<tr><td><b>{escape(code)}</b> <span class='muted small'>{escape(title)}</span></td>{tds}</tr>")
    body.append("<tr class='sum'><td>Courses serving</td>" + "".join(f"<td>{n}</td>" for _, n, _ in summary) + "</tr>")
    matrix = ("<div class='card'><table class='copo'>" + head_row + "".join(body) + "</table></div>")
    per_co: dict[str, list] = {}
    for co in m.cos:
        per_co.setdefault(co.course_code, []).append(co)
    detail = "".join(
        f"<h3>{escape(cos[0].course_title)} <span class='muted small'>{escape(code)}</span></h3><ul class='ev'>"
        + "".join(f"<li>{escape(co.text)}<br>" + ("; ".join(f"<b>{escape(li.po)}</b> {li.strength} "
                                                              f"({escape(', '.join(li.reasons))})" for li in co.links)
                                                   or "<i>serves no PO</i>") + "</li>" for co in cos)
        + "</ul>" for code, cos in per_co.items())
    unmapped = ""
    if m.unmapped:
        unmapped = (f"<details><summary>{len(m.unmapped)} course outcome{'' if len(m.unmapped) == 1 else 's'} "
                    "serve no PO</summary>" + _evidence_list(
                        [f"<b>{escape(co.course_code)}</b>: {escape(co.text)}" for co in m.unmapped]) + "</details>")
    return (head + notes + pos_table + "<h3>Course articulation matrix</h3>" + matrix + unmapped
            + f"<details><summary>Why each outcome maps where it does</summary>{detail}</details>")


def render_outcomes_html(rep: OutcomeReport, copo: Optional[MappingReport] = None) -> str:
    """A page of its own for the outcomes analysis of one programme."""
    p = rep.programme
    title = f"{escape(p.name)}: Course Outcomes"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head>
<body><main>
<h1>{escape(p.name)}</h1>
<p class="lead">{escape(p.institution)}{' · ' + escape(p.year) if p.year else ''} · course outcomes</p>
{section_outcomes(rep)}
{section_copo(copo) if copo else ""}
<footer>Generated {date.today().isoformat()} by Curriculum Intelligence {__version__}. Verb list: {escape(rep.bloom.name)}.</footer>
</main></body></html>"""


STATUS_PILL = {"met": ("Met", "ok"), "partly": ("Partly met", "Medium"),
               "not_met": ("Not met", "High"), "not_checked": ("Not checked", "soft")}


def _section_checklist(cl: Checklist) -> str:
    src = (f" Source: <a href='{escape(cl.rules.source)}'>{escape(cl.rules.source)}</a>."
           if cl.rules.source.startswith("http") else
           (f" Source: {escape(cl.rules.source)}." if cl.rules.source else ""))
    variant = (f"Checked as a <b>{escape(cl.variant.name)}</b> ({escape(cl.variant_basis)})."
               if cl.variant else "")
    counts = []
    for level in ("required", "advisory"):
        rs = [r for r in cl.results if r.rule.level == level]
        if rs:
            parts = [f"{sum(r.status == st for r in rs)} {STATUS_PILL[st][0].lower()}"
                     for st in STATUS_PILL if any(r.status == st for r in rs)]
            counts.append(f"{level.capitalize()} ({len(rs)}): {', '.join(parts)}")
    notes = []
    if not cl.has_scheme and any(r.status == "not_checked" for r in cl.results):
        notes.append("No credit scheme is recorded for this programme, so its credit rules are not checked. "
                     "Add the credits a student earns in each category (from the programme's regulations) "
                     "as the programme's <code>scheme</code>.")
    if cl.missing_semesters:
        sems = ", ".join(map(str, cl.missing_semesters))
        notes.append(f"The credit scheme has no credits for semester{'s' if len(cl.missing_semesters) > 1 else ''} "
                     f"{sems}, so credit totals for this degree are incomplete.")
    if cl.beyond:
        sems = ", ".join(f"{escape(k)} ({_num(v)} credits)" for k, v in cl.beyond.items())
        notes.append(f"Not counted for this degree: credits in later semesters, {sems}.")
    if cl.unmapped:
        labels = ", ".join(f"{escape(k)} ({_num(v)} credits)" for k, v in cl.unmapped.items())
        notes.append(f"Credit scheme labels that match none of the framework's categories, so count only "
                     f"towards the total: {labels}.")
    rows = []
    for r in cl.results:
        label, css = STATUS_PILL[r.status]
        page = f" <span class='muted small'>p. {escape(r.rule.page)}</span>" if r.rule.page else ""
        level = " <span class='pill soft'>Advisory</span>" if r.rule.level == "advisory" else ""
        note = f"<br><span class='muted small'>{escape(r.rule.note)}</span>" if r.rule.note else ""
        ev = (f"<details><summary>Evidence</summary>{_evidence_list([escape(e) for e in r.evidence])}</details>"
              if r.evidence else "")
        rows.append(f"<tr><td class='req'>{escape(r.rule.text)}{page}{level}{note}</td>"
                    f"<td data-label='This programme'>{escape(r.found)}{ev}</td>"
                    f"<td data-label='Expected'>{escape(r.expected)}</td>"
                    f"<td><span class='pill {css}'>{label}</span></td></tr>")
    return (f"<h2>Regulatory checklist: {escape(cl.rules.name)}</h2><p class='muted'>{variant}{src}</p>"
            + "".join(f"<p class='muted'>{n}</p>" for n in notes)
            + (f"<p>{'; '.join(counts)}.</p>" if counts else "")
            + "<div class='card'><table class='rules'><tr><th>Requirement</th><th>This programme</th>"
              "<th>Expected</th><th>Status</th></tr>" + "".join(rows) + "</table></div>")


def _section_matrix(b: Benchmark) -> str:
    head = ("<tr><th>Skill</th><th class='own'>This programme</th>"
            + "".join(f"<th class='peer' title='{escape(p.label)}'>{escape(p.label)}</th>" for p in b.peers)
            + "<th class='n'>Peers</th></tr>")
    body = []
    for area in b.taxonomy.areas:
        body.append(f"<tr class='area'><td colspan='{len(b.peers) + 3}'>{escape(area.name)}</td></tr>")
        for r in [r for r in b.rows if r.area == area.id]:
            g, lab, css = _mark(r.own.level, r.own_basis, r.own_course_basis)
            cells = [f"<td class='ownc {css}' title='{lab}'>{g}</td>"]
            for p in b.peers:
                g, lab, css = _mark(r.peer_levels[p.label], r.peer_basis.get(p.label),
                                    r.peer_course_basis.get(p.label))
                cells.append(f"<td class='{css}' title='{escape(p.label)}: {lab}'>{g}</td>")
            body.append(f"<tr><td>{escape(r.name)}</td>{''.join(cells)}<td class='n'>{_pct(100 * r.peer_share)}</td></tr>")
    return ("<h2>Coverage matrix</h2><p class='muted'><span class='c-course'>●</span> a core course on it · "
            "✓ covered (a course title, or two or more syllabus lines) · "
            "<span class='c-elective'>○</span> covered, but only by elective courses · "
            "△ mentioned in one line · <span class='c-absent'>·</span> not found.</p>"
            "<div class='card'><table class='matrix'>" + head + "".join(body) + "</table></div>")


def _section_method(b: Benchmark, regulatory: bool = False) -> str:
    unmapped = unmapped_lines(b.own, b.taxonomy)
    um = ""
    if unmapped:
        um = ("<h3>Syllabus lines with no recognised skill</h3><p class='muted'>Either the line is generic, "
              "or the taxonomy is missing a term. Worth a look before trusting a “not found”.</p>"
              + _evidence_list([f"<b>{escape(c)}</b>: “{escape(line)}”" for c, line in unmapped]))
    return f"""<h2>How this was worked out</h2>
<p>Every course title and topic line was searched for the terms listed under each skill in the
<b>{escape(b.taxonomy.name)}</b> taxonomy ({len(b.taxonomy.skills)} skills). Course outcomes are not counted
as evidence of a skill: they often look ahead to later study, and not every syllabus states them. Matching ignores case and
punctuation, and the longest phrase wins (“partial differential equations” counts for PDEs, not ODEs). No
AI or statistics are involved: each mark in this report traces back to a phrase in a syllabus.</p>
<p>Limits: a syllabus can teach a skill without naming it, and naming it does not show depth. Treat a gap as a
question for the committee, not a verdict. Peer findings are only as good as the peer syllabi supplied.</p>
<p>{_electives_note(b)}</p>
<p>Courses on a skill: a course counts as <i>on</i> a skill when its title names the skill, or when the skill
appears in at least half of its topic lines (and in at least three). A programme without one teaches the skill
inside courses about something else, which may mean a few examples rather than a unit of study.</p>
<p class="muted">Not yet analysed: {"industry skill demand" if regulatory else "regulatory (NEP/UGC) alignment and industry skill demand"}.</p>{um}"""


def _electives_note(b: Benchmark) -> str:
    base = ("Core and electives: a skill counts as <i>core</i> for a programme when its compulsory courses "
            "alone cover it, and as <i>elective only</i> when it depends on courses a student may choose. "
            "Gaps are judged on everything a programme offers; the split shows how firmly each peer teaches it.")
    recorded = b.records_electives
    if not recorded:
        return base + " None of these programmes records which courses are electives, so all coverage counts as core."
    missing = [p.label for p in [b.own, *b.peers] if p.label not in recorded]
    tail = (f" Programmes that record no electives (all their coverage counts as core): "
            f"{escape(', '.join(missing))}." if missing else "")
    return base + tail


def _regulatory_tiles(checklists) -> str:
    if not checklists:
        return '<div class="tile na"><b>Not yet analysed</b><span>Regulatory &amp; industry alignment</span></div>'
    tiles = []
    for cl in checklists:
        for level, label in (("required", "Requirements met"), ("advisory", "Advisory points met")):
            rs = [r for r in cl.results if r.rule.level == level]
            done = [r for r in rs if r.status != "not_checked"]
            if done:
                tiles.append(f'<div class="tile"><b>{sum(r.status == "met" for r in done)} of {len(done)}</b>'
                             f'<span>{label}: {escape(cl.rules.id)}</span></div>')
            elif rs:
                tiles.append(f'<div class="tile na"><b>Not checked</b><span>{escape(cl.rules.id)}: '
                             f'no credit scheme recorded</span></div>')
    return "".join(tiles) + '<div class="tile na"><b>Not yet analysed</b><span>Industry alignment</span></div>'


def render_html(b: Benchmark, overlaps: list[OverlapPair], checklists: list[Checklist] = (),
                outcomes: Optional[OutcomeReport] = None, copo: Optional[MappingReport] = None) -> str:
    gaps = b.by_status("gap")
    high = sum(r.priority == "High" for r in gaps)
    flagged = [o for o in overlaps if not o.theory_lab_pair]
    tiles = f"""<div class="tiles">
<div class="tile"><b>{_pct(b.alignment)}</b><span>Peer benchmark alignment</span></div>
<div class="tile"><b>{len(gaps)}</b><span>Priority gaps ({high} high)</span></div>
<div class="tile"><b>{len(b.by_status('distinctive'))}</b><span>Distinctive strengths</span></div>
<div class="tile"><b>{len(flagged)}</b><span>Course pairs flagged for overlap</span></div>
{_regulatory_tiles(checklists)}
</div>"""
    peers = ", ".join(escape(p.label) for p in b.peers)
    title = f"{escape(b.own.name)}: Curriculum Benchmark"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head>
<body><main>
<h1>{escape(b.own.name)}</h1>
<p class="lead">{escape(b.own.institution)}{' · ' + escape(b.own.year) if b.own.year else ''} ·
benchmarked against {len(b.peers)} peer programmes</p>
<p class="muted" style="font-size:13px;margin-top:4px">Peers: {peers}</p>
{tiles}
{_section_gaps(b)}
{_section_list(b, "watch", "Watch list", "Covered by 30–49% of peers and not here: not yet a norm, but worth discussing.", False)}
{_section_list(b, "distinctive", "Distinctive strengths", "Covered here, and fewer than 30% of peers even mention it.", True)}
{_section_overlap(overlaps)}
{_section_areas(b)}
{_section_structure(b)}
{_section_matrix(b)}
{"".join(_section_checklist(cl) for cl in checklists)}
{section_outcomes(outcomes) if outcomes else ""}
{section_copo(copo) if copo else ""}
{_section_method(b, bool(checklists))}
<footer>Generated {date.today().isoformat()} by Curriculum Intelligence {__version__}.</footer>
</main></body></html>"""
