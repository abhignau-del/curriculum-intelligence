import { useEffect, useState } from "react";
import { api, download } from "./api";
import type { ProgrammeDetail } from "./types";

interface Props {
  id: string;
  skillName: (id: string) => string;
  onError: (msg: string) => void;
  onDeleted: () => void;
}

export default function ProgrammeView({ id, skillName, onError, onDeleted }: Props) {
  const [d, setD] = useState<ProgrammeDetail | null>(null);

  useEffect(() => { api.programme(id).then(setD, e => onError(e.message)); }, [id, onError]);

  if (!d) return <p className="muted">Loading…</p>;
  const p = d.programme;
  const credits = p.courses.reduce((t, c) => t + (c.credits ?? 0), 0);
  const recognised = Object.values(d.levels).filter(l => l === "covered").length;

  async function remove() {
    if (!confirm(`Delete ${p.institution} — ${p.name} from the library?`)) return;
    try { await api.remove(id); onDeleted(); } catch (e) { onError((e as Error).message); }
  }

  return (
    <>
      <div className="row">
        <div>
          <h2>{p.institution}</h2>
          <div className="muted">{[p.name, p.year, p.source].filter(Boolean).join(" · ")}</div>
        </div>
        <span className="spacer" />
        <button className="btn" onClick={() => download(`/api/programmes/${id}/download`, "programme.json").catch(e => onError(e.message))}>
          Download .json
        </button>
        <button className="btn danger" onClick={remove}>Delete</button>
      </div>

      <div className="tiles">
        <div className="tile"><b>{p.courses.length}</b><span>Courses</span></div>
        <div className="tile"><b>{credits || "–"}</b><span>Credits</span></div>
        <div className="tile"><b>{recognised}</b><span>Skills covered</span></div>
        <div className="tile"><b>{d.unmapped.length}</b><span>Lines with no recognised skill</span></div>
      </div>

      <div className="card flush">
        <table className="course-table">
          <thead><tr><th>Sem</th><th>Code</th><th>Course</th><th className="n">Credits</th><th>Skills found</th></tr></thead>
          <tbody>
            {p.courses.map(c => (
              <tr key={c.code}>
                <td>{c.semester ?? ""}</td>
                <td className="muted">{c.code}</td>
                <td>
                  {c.topics.length ? (
                    <details><summary style={{ color: "inherit" }}>{c.title}</summary>
                      <ul className="topics">{c.topics.map((t, i) => <li key={i}>{t}</li>)}</ul>
                    </details>
                  ) : c.title}
                </td>
                <td className="n">{c.credits ?? ""}</td>
                <td>
                  <div className="chips">
                    {(d.course_skills[c.code] ?? []).map(s => <span key={s} className="chip">{skillName(s)}</span>)}
                    {!(d.course_skills[c.code] ?? []).length && <span className="muted small">none recognised</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {d.unmapped.length > 0 && (
        <div className="card">
          <h3>Syllabus lines with no recognised skill</h3>
          <p className="hint">Either the line is generic, or the taxonomy is missing a term. Worth a look before trusting a “not found”.</p>
          <ul className="ev">{d.unmapped.map((u, i) => <li key={i}><b>{u.course}</b>: {u.line}</li>)}</ul>
        </div>
      )}
    </>
  );
}
