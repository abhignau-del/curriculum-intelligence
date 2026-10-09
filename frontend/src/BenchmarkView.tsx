import { useEffect, useMemo, useRef, useState } from "react";
import { api, download, saveBlob } from "./api";
import {
  byStatus, cellEvidence, courseOnNote, coverMark, gapSentence, parseSaved, pct, peerCourses, peersSplit, resolveSelection,
  selectionProblem, skillsByArea, splitOnTerm, toSaved,
} from "./benchmarkops";
import type { BenchmarkResult, Evidence, ProgrammeSummary, SkillResult, TaxonomyView } from "./types";

const STORAGE_KEY = "curintel.selection";

function loadSaved() {
  try { return parseSaved(localStorage.getItem(STORAGE_KEY)); } catch { return null; }
}

interface Props { programmes: ProgrammeSummary[]; taxonomy: TaxonomyView | null; onError: (msg: string) => void }

export default function BenchmarkView({ programmes, taxonomy, onError }: Props) {
  const initial = useMemo(() => resolveSelection(loadSaved(), programmes), []);
  const [own, setOwn] = useState(initial.own);
  const [peers, setPeers] = useState<string[]>(initial.peers);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [running, setRunning] = useState(false);
  const [cell, setCell] = useState<{ skill: SkillResult; peer: string | null } | null>(null);
  const request = useRef(0);

  // Keep the selection valid when the library changes (uploads, deletions).
  useEffect(() => {
    const ids = new Set(programmes.map(p => p.id));
    if (!ids.has(own)) {
      const next = resolveSelection(loadSaved(), programmes);
      setOwn(next.own); setPeers(next.peers);
    } else {
      setPeers(ps => {
        const kept = ps.filter(id => ids.has(id) && id !== own);
        return kept.length === ps.length ? ps : kept;
      });
    }
  }, [programmes]);

  const problem = selectionProblem(own, peers, programmes);

  useEffect(() => {
    try { if (own) localStorage.setItem(STORAGE_KEY, JSON.stringify(toSaved(own, peers, programmes))); } catch { /* private mode */ }
    if (problem) { setResult(null); return; }
    const mine = ++request.current;
    setRunning(true);
    api.benchmark({ own, peers })
      .then(r => { if (mine === request.current) setResult(r); })
      .catch(e => { if (mine === request.current) { setResult(null); onError(e.message); } })
      .finally(() => { if (mine === request.current) setRunning(false); });
  }, [own, peers.join(","), problem]);

  function chooseOwn(id: string) {
    // The previous programme under review becomes a peer; the new one stops being one.
    setPeers(ps => [...ps.filter(p => p !== id), ...(own && own !== id ? [own] : [])]);
    setOwn(id);
  }

  const toggle = (id: string) => setPeers(ps => ps.includes(id) ? ps.filter(p => p !== id) : [...ps, id]);
  const others = programmes.filter(p => p.id !== own);

  if (programmes.length === 0) {
    return <div className="empty"><h2>No programmes yet</h2>
      <p className="muted">Upload the programme you want to review and a few peer programmes, using the panel on the left.</p></div>;
  }

  return (
    <>
      <div className="card">
        <div className="select-grid">
          <label className="field"><span>Programme under review</span>
            <select value={own} onChange={e => chooseOwn(e.target.value)}>
              {programmes.map(p => <option key={p.id} value={p.id}>{p.institution} — {p.name}</option>)}
            </select>
          </label>
          <div className="field">
            <div className="row">
              <span className="muted small">Peers ({peers.length} of {others.length})</span>
              <button className="linkish" onClick={() => setPeers(others.map(p => p.id))}>all</button>
              <button className="linkish" onClick={() => setPeers([])}>none</button>
            </div>
            <div className="peers">
              {others.map(p => (
                <label key={p.id} title={p.name}>
                  <input type="checkbox" checked={peers.includes(p.id)} onChange={() => toggle(p.id)} />
                  {p.institution}
                </label>
              ))}
            </div>
          </div>
        </div>
        {problem && <p className="hint" role="status">{problem}</p>}
      </div>

      {running && !result && <p className="muted">Working…</p>}
      {result && !problem && <Results r={result} stale={running} onCell={(skill, peer) => setCell({ skill, peer })}
                                      onError={onError} selection={{ own, peers }} />}
      {cell && result && <EvidenceDialog r={result} skill={cell.skill} peer={cell.peer} onClose={() => setCell(null)}
                                   terms={taxonomy?.areas.flatMap(a => a.skills).find(s => s.id === cell.skill.id)?.terms ?? []} />}
    </>
  );
}

function Results({ r, stale, onCell, onError, selection }: {
  r: BenchmarkResult; stale: boolean; selection: { own: string; peers: string[] };
  onCell: (s: SkillResult, peer: string | null) => void; onError: (m: string) => void;
}) {
  const gaps = byStatus(r.skills, "gap");
  const watch = byStatus(r.skills, "watch");
  const distinctive = byStatus(r.skills, "distinctive");
  const flagged = r.overlaps.filter(o => !o.theory_lab_pair);
  const n = r.peers.length;
  const split = peersSplit(r);

  return (
    <div style={{ opacity: stale ? 0.6 : 1, display: "flex", flexDirection: "column", gap: 14 }}>
      <nav className="toolbar" aria-label="Sections">
        <a href="#gaps">Gaps</a><a href="#watch">Watch</a><a href="#strengths">Strengths</a>
        <a href="#overlap">Overlap</a><a href="#areas">Areas</a><a href="#structure">Structure</a><a href="#matrix">Matrix</a>
        <span className="spacer" />
        <button className="btn small" onClick={() => download("/api/benchmark/report", "benchmark.html", selection).catch(e => onError(e.message))}>
          Download report (.html)
        </button>
        <button className="btn small" onClick={() => saveBlob(new Blob([JSON.stringify(r, null, 2)], { type: "application/json" }), "benchmark.json")}>
          Data (.json)
        </button>
      </nav>

      <div className="tiles">
        <div className="tile"><b>{pct(r.alignment)}</b><span>Peer benchmark alignment</span></div>
        <div className="tile"><b>{gaps.length}</b><span>Priority gaps ({gaps.filter(g => g.priority === "High").length} high)</span></div>
        <div className="tile"><b>{distinctive.length}</b><span>Distinctive strengths</span></div>
        <div className="tile"><b>{flagged.length}</b><span>Course pairs flagged for overlap</span></div>
        <div className="tile na"><b>Not yet analysed</b><span>Regulatory &amp; industry alignment</span></div>
      </div>

      <Section id="gaps" title="Priority gaps" hint="Skills that at least half of the peers cover and this programme does not. High = 70% or more of peers." />
      <div className="card">
        {gaps.length === 0 && <p className="muted">None: every skill that half or more of the peers cover is covered here.</p>}
        {gaps.map(s => (
          <div className="gap" key={s.id}>
            <div>
              <b>{s.name}</b>
              <p>{gapSentence(s, n, split)}</p>
              {s.own_evidence.length > 0 && (
                <details><summary>The one line found here</summary><EvidenceList evidence={s.own_evidence} /></details>
              )}
              <details><summary>Where peers cover it</summary><PeerCourses s={s} split={split} /></details>
            </div>
            <div style={{ textAlign: "right" }}>
              <span className={`pill ${s.priority}`}>{s.priority}</span>
              <div className="muted small">{pct(100 * s.peer_share)} of peers</div>
              <ShareDetail s={s} split={split} />
            </div>
          </div>
        ))}
      </div>

      <Section id="watch" title="Watch list" hint="Covered by 30–49% of peers and not here: not yet a norm, but worth discussing." />
      <SkillTable rows={watch} empty="Nothing on the watch list." onCell={onCell} split={split} />

      <Section id="strengths" title="Distinctive strengths" hint="Covered here, and fewer than 30% of peers even mention it." />
      <SkillTable rows={distinctive} empty="No distinctive strengths." onCell={onCell} split={split} />

      <Section id="overlap" title="Course overlap"
               hint="Pairs of this programme's courses whose topic lists share much of their vocabulary. Flagged at 40%, High at 60%. Theory–lab pairs are expected to overlap." />
      <div className="card flush">
        {r.overlaps.length === 0 ? <p className="muted">No pair reached the threshold.</p> : (
          <table>
            <thead><tr><th>Courses</th><th className="n">Similarity</th><th>Level</th><th>Strongest shared terms</th></tr></thead>
            <tbody>{r.overlaps.map(o => (
              <tr key={o.a + o.b}>
                <td><b>{o.a_title}</b> <span className="muted">{o.a}</span><br /><b>{o.b_title}</b> <span className="muted">{o.b}</span></td>
                <td className="n">{Math.round(100 * o.similarity)}%</td>
                <td>{o.theory_lab_pair ? <span className="pill soft">Theory–lab pair</span> : <span className={`pill ${o.level}`}>{o.level}</span>}</td>
                <td>{o.shared_terms.join(", ")}
                  {o.shared_skills.length > 0 && <div className="muted small">Shared skills: {o.shared_skills.join(", ")}</div>}</td>
              </tr>))}
            </tbody>
          </table>
        )}
      </div>

      <Section id="areas" title="Alignment by area"
               hint="Of the skills that at least half of the peers cover, how many this programme covers. A skill mentioned only once here counts half." />
      <div className="card flush">
        <table>
          <thead><tr><th>Area</th><th></th><th className="n">Alignment</th><th className="n">Peer-core skills</th></tr></thead>
          <tbody>{r.areas.map(a => (
            <tr key={a.id}>
              <td>{a.name}</td>
              <td>{a.alignment === null ? <span className="muted small">no skill shared by half the peers</span>
                : <div className="bar"><i style={{ width: `${a.alignment}%` }} /></div>}</td>
              <td className="n">{pct(a.alignment)}</td>
              <td className="n">{a.core_skills}</td>
            </tr>))}
          </tbody>
        </table>
      </div>

      <Section id="structure" title="Programme structure"
               hint="Everything listed for each programme, including every elective alternative, so these are not the credits a student earns. A dash means some courses have no credits recorded." />
      <div className="card flush">
        <table>
          <thead><tr><th>Programme</th><th className="n">Courses offered</th><th className="n">Credits offered</th></tr></thead>
          <tbody>{r.structure.map((s, i) => (
            <tr key={s.label}><td>{s.label}{i === 0 && <b> (under review)</b>}</td><td className="n">{s.courses}</td><td className="n">{s.credits ?? "–"}</td></tr>))}
          </tbody>
        </table>
      </div>

      <Section id="matrix" title="Coverage matrix"
               hint="● a core course on it · ✓ covered (a course title, or two or more syllabus lines) · ○ covered, but only by elective courses · △ mentioned in one line · · not found. Click any mark to see the syllabus lines behind it." />
      <div className="card flush matrix-wrap">
        <table className="matrix">
          <thead><tr>
            <th>Skill</th><th className="vert own">{r.programme.institution}</th>
            {r.peers.map(p => <th key={p.id} className="vert">{p.institution}</th>)}
            <th className="n">Peers</th>
          </tr></thead>
          <tbody>
            {skillsByArea(r).map(area => [
              <tr key={area.id} className="area"><td colSpan={n + 3}>{area.name}</td></tr>,
              ...area.skills.map(s => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td><MatrixCell s={s} peer={null} onCell={onCell} own /></td>
                  {r.peers.map(p => <td key={p.id}><MatrixCell s={s} peer={p.institution} onCell={onCell} /></td>)}
                  <td className="n">{pct(100 * s.peer_share)}</td>
                </tr>
              )),
            ])}
          </tbody>
        </table>
      </div>

      {r.unmapped.length > 0 && (
        <details className="card">
          <summary>{r.unmapped.length} syllabus line{r.unmapped.length > 1 ? "s" : ""} in the programme under review with no recognised skill</summary>
          <ul className="ev">{r.unmapped.map((u, i) => <li key={i}><b>{u.course}</b>: {u.line}</li>)}</ul>
        </details>
      )}
      <p className="muted small">{r.generated_by} · taxonomy: {r.taxonomy}. Matching is by listed syllabus phrases, not AI;
        a gap is a question for the committee, not a verdict.</p>
    </div>
  );
}

function Section({ id, title, hint }: { id: string; title: string; hint?: string }) {
  return <div className="section-head" id={id}><h2>{title}</h2>{hint && <p className="hint">{hint}</p>}</div>;
}

function MatrixCell({ s, peer, onCell, own }: { s: SkillResult; peer: string | null; onCell: Props2["onCell"]; own?: boolean }) {
  const { level, basis, courseBasis } = cellEvidence(s, peer);
  const m = coverMark(level, basis, courseBasis);
  return (
    <button className={`cell ${m.css} ${own ? "own" : ""}`} onClick={() => onCell(s, peer)}
            aria-label={`${s.name}, ${peer ?? "programme under review"}: ${m.label}`}>
      {m.mark}
    </button>
  );
}
type Props2 = { onCell: (s: SkillResult, peer: string | null) => void };

function SkillTable({ rows, empty, onCell, split }: { rows: SkillResult[]; empty: string; split: boolean } & Props2) {
  if (!rows.length) return <div className="card"><p className="muted">{empty}</p></div>;
  return (
    <div className="card flush">
      <table>
        <thead><tr><th>Skill</th><th>Here</th><th className="n">Peers covering</th><th className="n">Peers mentioning once</th></tr></thead>
        <tbody>{rows.map(s => (
          <tr key={s.id}>
            <td><b>{s.name}</b>
              {s.own_evidence.length > 0 && <details><summary>Evidence here</summary><EvidenceList evidence={s.own_evidence} /></details>}
              {s.status === "watch" && <details><summary>Where peers cover it</summary><PeerCourses s={s} split={split} /></details>}
            </td>
            <td><OwnMark s={s} onCell={onCell} /></td>
            <td className="n">{pct(100 * s.peer_share)}<ShareDetail s={s} split={split} /></td>
            <td className="n">{pct(100 * s.peer_touched_share)}</td>
          </tr>))}
        </tbody>
      </table>
    </div>
  );
}

function ShareDetail({ s, split }: { s: SkillResult; split: boolean }) {
  return split
    ? <><div className="muted small">core {pct(100 * s.peer_core_share)}</div>
        <div className="muted small">core course {pct(100 * s.peer_core_course_share)}</div></>
    : <div className="muted small">course {pct(100 * s.peer_course_share)}</div>;
}

function OwnMark({ s, onCell }: { s: SkillResult } & Props2) {
  const m = coverMark(s.own_level, s.own_basis, s.own_course_basis);
  return <><button className={`cell ${m.css}`} onClick={() => onCell(s, null)}>{m.mark}</button> {m.label}</>;
}

function PeerCourses({ s, split }: { s: SkillResult; split: boolean }) {
  return (
    <ul className="ev">{peerCourses(s).map(([peer, titles]) => {
      const notes = [];
      if (s.peer_levels[peer] === "touched") notes.push("mentioned once");
      else if (s.peer_basis[peer] === "elective") notes.push("elective only");
      if (s.peer_courses_on[peer]) notes.push(courseOnNote(s.peer_courses_on[peer], split));
      return <li key={peer}><b>{peer}</b>{notes.length > 0 && <i> ({notes.join("; ")})</i>}: {titles.join(", ")}</li>;
    })}</ul>
  );
}

function Highlighted({ e }: { e: Evidence }) {
  const [before, hit, after] = splitOnTerm(e.line, e.term);
  return <>“{before}{hit && <mark>{hit}</mark>}{after}”</>;
}

function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  return (
    <ul className="ev">{evidence.map((e, i) => (
      <li key={i}><b>{e.course_title}</b> <span className="small">({e.course}, {e.field})</span>: <Highlighted e={e} /></li>
    ))}</ul>
  );
}

function EvidenceDialog({ r, skill, peer, terms, onClose }: {
  r: BenchmarkResult; skill: SkillResult; peer: string | null; terms: string[]; onClose: () => void;
}) {
  const { level, basis, courseBasis, coursesOn, evidence } = cellEvidence(skill, peer);
  const m = coverMark(level, basis, courseBasis);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal card" role="dialog" aria-label="Evidence" onClick={e => e.stopPropagation()}>
        <div className="row"><h2>{skill.name}</h2><span className="spacer" /><button className="btn small" onClick={onClose} autoFocus>Close</button></div>
        <p><b>{peer ?? r.programme.institution}</b>{peer === null && " (under review)"}: <span className={m.css}>{m.mark}</span> {m.label}</p>
        {coursesOn.length > 0 && (
          <p className="small">Courses on it: {coursesOn.map(c =>
            `${c.course_title} (${c.course}${c.elective ? ", elective" : ""}; ${c.by === "title" ? "named in the title" : "most topic lines"})`).join("; ")}</p>
        )}
        {evidence.length ? <EvidenceList evidence={evidence} />
          : <p className="muted">No syllabus line names this skill. Phrases that would count: {terms.slice(0, 12).join(", ")}{terms.length > 12 ? ", …" : ""}.</p>}
      </div>
    </div>
  );
}
