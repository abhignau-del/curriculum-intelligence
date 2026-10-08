"""The benchmark report: one self-contained HTML file, plus the same data as JSON.

Every finding carries its evidence: which peers cover a skill and in which
course, and which syllabus line triggered a match here.
"""
from __future__ import annotations

from datetime import date
from html import escape

from . import __version__
from .analysis import Benchmark, SkillRow, unmapped_lines
from .overlap import OverlapPair

LEVEL_MARK = {"covered": ("✓", "Covered"), "touched": ("△", "Mentioned once"), "absent": ("·", "Not found")}


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0f}%"


def _num(x: float | None) -> str:
    return "–" if x is None else (f"{x:.0f}" if float(x).is_integer() else f"{x:.1f}")


# ----- JSON --------------------------------------------------------------

def to_dict(b: Benchmark, overlaps: list[OverlapPair]) -> dict:
    def ev(e):
        return {"course": e.course_code, "course_title": e.course_title, "field": e.field,
                "line": e.line, "term": e.term}
    return {
        "generated_by": f"curintel {__version__}",
        "programme": {"institution": b.own.institution, "name": b.own.name, "year": b.own.year},
        "peers": [{"institution": p.institution, "name": p.name, "year": p.year} for p in b.peers],
        "unmapped": [{"course": c, "line": line} for c, line in unmapped_lines(b.own, b.taxonomy)],
        "taxonomy": b.taxonomy.name,
        "alignment": b.alignment,
        "areas": [{"id": a.area, "name": a.name, "alignment": a.alignment, "core_skills": a.core_skills}
                  for a in b.areas],
        "skills": [{
            "id": r.skill, "name": r.name, "area": r.area, "status": r.status, "priority": r.priority,
            "own_level": r.own.level, "own_evidence": [ev(e) for e in r.own.evidence],
            "peer_share": r.peer_share, "peer_touched_share": r.peer_touched_share,
            "peer_levels": r.peer_levels,
            "peer_evidence": {p: [ev(e) for e in evs] for p, evs in r.peer_evidence.items() if evs},
        } for r in b.rows],
        "overlaps": [o.__dict__ for o in overlaps],
        "structure": [s.__dict__ for s in b.structure],
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
.c-covered{color:var(--ok);font-weight:700}.c-touched{color:var(--md)}.c-absent{color:var(--line)}
td.ownc{background:var(--soft)}
@media (max-width:640px){table.gaps tr{display:grid;grid-template-columns:1fr auto auto;column-gap:8px}
table.gaps tr:first-child{display:none}table.gaps td{border:0;padding:6px 0}
table.gaps td.finding{grid-column:1/-1;order:4;padding-top:0}table.gaps tr+tr{border-top:1px solid var(--line);padding:6px 0}
table.matrix th.peer{height:120px}}
code{font-size:13px}footer{margin-top:48px;color:var(--muted);font-size:13px}
"""


def _evidence_list(items: list[str]) -> str:
    return '<ul class="ev">' + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def _own_evidence(row: SkillRow) -> str:
    return _evidence_list([f"<b>{escape(e.course_title)}</b> ({escape(e.course_code)}, {e.field}): "
                           f"“{escape(e.line)}”" for e in row.own.evidence])


def _peer_evidence(b: Benchmark, row: SkillRow) -> str:
    items = []
    for peer in b.peers:
        courses = row.peer_courses.get(peer.label)
        if not courses:
            continue
        mark = "" if row.peer_levels[peer.label] == "covered" else " <i>(mentioned once)</i>"
        items.append(f"<b>{escape(peer.label)}</b>{mark}: {escape(', '.join(courses))}")
    return _evidence_list(items)


def _gap_sentence(b: Benchmark, r: SkillRow) -> str:
    here = ("is mentioned in only one syllabus line here" if r.own.level == "touched"
            else "is not found in this curriculum")
    return (f"{escape(r.name)} is covered by {_pct(100 * r.peer_share)} of benchmarked programmes "
            f"({len(r.peers_covering)} of {len(b.peers)}) but {here}.")


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
            f"<td class='n'>{_pct(100 * r.peer_share)}</td>"
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
        mark, label = LEVEL_MARK[r.own.level]
        body.append(f"<tr><td><b>{escape(r.name)}</b>{detail}</td>"
                    f"<td><span class='c-{r.own.level}'>{mark}</span> {label}</td>"
                    f"<td class='n'>{_pct(100 * r.peer_share)}</td>"
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


def _section_matrix(b: Benchmark) -> str:
    head = ("<tr><th>Skill</th><th class='own'>This programme</th>"
            + "".join(f"<th class='peer' title='{escape(p.label)}'>{escape(p.label)}</th>" for p in b.peers)
            + "<th class='n'>Peers</th></tr>")
    body = []
    for area in b.taxonomy.areas:
        body.append(f"<tr class='area'><td colspan='{len(b.peers) + 3}'>{escape(area.name)}</td></tr>")
        for r in [r for r in b.rows if r.area == area.id]:
            cells = [f"<td class='ownc c-{r.own.level}' title='{LEVEL_MARK[r.own.level][1]}'>{LEVEL_MARK[r.own.level][0]}</td>"]
            for p in b.peers:
                lv = r.peer_levels[p.label]
                cells.append(f"<td class='c-{lv}' title='{escape(p.label)}: {LEVEL_MARK[lv][1]}'>{LEVEL_MARK[lv][0]}</td>")
            body.append(f"<tr><td>{escape(r.name)}</td>{''.join(cells)}<td class='n'>{_pct(100 * r.peer_share)}</td></tr>")
    return ("<h2>Coverage matrix</h2><p class='muted'>✓ covered (a course title, or two or more syllabus lines) · "
            "△ mentioned in one line · <span class='c-absent'>·</span> not found.</p>"
            "<div class='card'><table class='matrix'>" + head + "".join(body) + "</table></div>")


def _section_method(b: Benchmark) -> str:
    unmapped = unmapped_lines(b.own, b.taxonomy)
    um = ""
    if unmapped:
        um = ("<h3>Syllabus lines with no recognised skill</h3><p class='muted'>Either the line is generic, "
              "or the taxonomy is missing a term. Worth a look before trusting a “not found”.</p>"
              + _evidence_list([f"<b>{escape(c)}</b>: “{escape(line)}”" for c, line in unmapped]))
    return f"""<h2>How this was worked out</h2>
<p>Every course title, topic line and outcome was searched for the terms listed under each skill in the
<b>{escape(b.taxonomy.name)}</b> taxonomy ({len(b.taxonomy.skills)} skills). Matching ignores case and
punctuation, and the longest phrase wins (“partial differential equations” counts for PDEs, not ODEs). No
AI or statistics are involved: each mark in this report traces back to a phrase in a syllabus.</p>
<p>Limits: a syllabus can teach a skill without naming it, and naming it does not show depth. Treat a gap as a
question for the committee, not a verdict. Peer findings are only as good as the peer syllabi supplied.</p>
<p class="muted">Not yet analysed: regulatory (NEP/UGC) alignment and industry skill demand.</p>{um}"""


def render_html(b: Benchmark, overlaps: list[OverlapPair]) -> str:
    gaps = b.by_status("gap")
    high = sum(r.priority == "High" for r in gaps)
    flagged = [o for o in overlaps if not o.theory_lab_pair]
    tiles = f"""<div class="tiles">
<div class="tile"><b>{_pct(b.alignment)}</b><span>Peer benchmark alignment</span></div>
<div class="tile"><b>{len(gaps)}</b><span>Priority gaps ({high} high)</span></div>
<div class="tile"><b>{len(b.by_status('distinctive'))}</b><span>Distinctive strengths</span></div>
<div class="tile"><b>{len(flagged)}</b><span>Course pairs flagged for overlap</span></div>
<div class="tile na"><b>Not yet analysed</b><span>Regulatory &amp; industry alignment</span></div>
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
{_section_method(b)}
<footer>Generated {date.today().isoformat()} by Curriculum Intelligence {__version__}.</footer>
</main></body></html>"""
