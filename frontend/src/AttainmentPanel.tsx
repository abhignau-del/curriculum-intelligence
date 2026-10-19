import { useEffect, useState } from "react";
import { api, attainmentPath, download, downloadPost, evidencePath } from "./api";
import { attainmentStatus, fromForm, parseSavedPolicy, toForm } from "./benchmarkops";
import type { PolicyForm } from "./benchmarkops";
import type { AttainmentResult } from "./types";

const POLICY_KEY = "curintel.policy";

function loadSavedPolicy() {
  try { return parseSavedPolicy(localStorage.getItem(POLICY_KEY)); } catch { return null; }
}

interface Props { id: string; institution: string; onError: (msg: string) => void }

/** Outcome attainment for a batch: the entry sheet, the policy, the upload and the results. */
export default function AttainmentPanel({ id, institution, onError }: Props) {
  const [batch, setBatch] = useState("");
  const [form, setForm] = useState<PolicyForm | null>(loadSavedPolicy);
  const [defaults, setDefaults] = useState<PolicyForm | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AttainmentResult | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.defaultPolicy().then(p => { const f = toForm(p); setDefaults(f); setForm(cur => cur ?? f); }, e => onError(e.message));
  }, []);
  useEffect(() => { setResult(null); setFile(null); }, [id]);

  const policy = form ? fromForm(form) : null;
  const problem = typeof policy === "string" ? policy : null;

  function update(key: keyof PolicyForm, value: string) {
    if (!form) return;
    const next = { ...form, [key]: Number(value) };
    setForm(next);
    try { localStorage.setItem(POLICY_KEY, JSON.stringify(next)); } catch { /* private mode */ }
  }

  async function run(f: File) {
    if (!policy || typeof policy === "string") return;
    setFile(f); setBusy(true);
    try { setResult(await api.attainment(id, f, policy)); }
    catch (e) { setResult(null); onError((e as Error).message); }
    finally { setBusy(false); }
  }

  // re-run when the policy changes after an upload
  useEffect(() => { if (file && policy && typeof policy !== "string") run(file); }, [JSON.stringify(form)]);

  const num = (key: keyof PolicyForm, label: string, step = 1, max = 100) => (
    <label className="field small-field"><span>{label}</span>
      <input type="number" min={0} max={max} step={step} value={form?.[key] ?? ""} onChange={e => update(key, e.target.value)} />
    </label>
  );

  return (
    <div className="card" id="attainment">
      <h3>Outcome attainment</h3>
      <p className="hint">How far a batch attained each course outcome, and through the CO–PO mapping each programme outcome.
        Enter counts only: for each outcome and assessment, how many students were assessed and how many reached the target mark.</p>

      <div className="row wrap-row">
        <label className="field small-field"><span>Batch</span>
          <input value={batch} onChange={e => setBatch(e.target.value)} placeholder="e.g. 2023-26" />
        </label>
        <button className="btn" onClick={() => download(`/api/programmes/${id}/attainment-template.xlsx?batch=${encodeURIComponent(batch)}`,
                                                        "attainment.xlsx").catch(e => onError(e.message))}>
          Download entry sheet (.xlsx)
        </button>
        <button className="btn" disabled={busy || !policy || typeof policy === "string"} onClick={() => {
          if (!policy || typeof policy === "string") return;
          downloadPost(evidencePath(id, result ? file : null, policy), result ? file : null, `${institution} NAAC 2.6.1 evidence.docx`)
            .catch(e => onError(e.message));
        }} title={result ? "Includes the uploaded batch's attainment" : "Upload results first to include attainment"}>
          Download NAAC 2.6.1 evidence (.docx)
        </button>
        <label className="btn">
          Upload results…
          <input type="file" accept=".xlsx,.json" hidden disabled={busy || !!problem}
                 onChange={e => { const f = e.target.files?.[0]; e.target.value = ""; if (f) run(f); }} />
        </label>
      </div>

      <details>
        <summary>Policy: how counts become levels</summary>
        {form && (
          <div className="policy-grid">
            {num("l3", "Level 3 at % reaching target")}
            {num("l2", "Level 2 at %")}
            {num("l1", "Level 1 at %")}
            {num("internal", "Internal weight %")}
            {num("external", "External weight %")}
            {num("direct", "Direct share % (rest: survey)")}
            {num("target", "Target level", 0.1, 3)}
            <button className="linkish" onClick={() => {
              if (!defaults) return;
              setForm(defaults);
              try { localStorage.removeItem(POLICY_KEY); } catch { /* private mode */ }
            }}>Reset to defaults</button>
          </div>
        )}
        <p className="hint">Defaults follow common practice; set your institution's own. Your settings are remembered in this browser.</p>
      </details>
      {problem && <p className="alert" role="alert">{problem}</p>}

      {busy && <p className="muted">Working…</p>}
      {result && !busy && file && policy && typeof policy !== "string" && (
        <AttainmentResults r={result} onDownload={() =>
          downloadPost(attainmentPath(id, file, policy, "html"), file, `${institution} attainment.html`).catch(e => onError(e.message))} />
      )}
    </div>
  );
}

function AttainmentResults({ r, onDownload }: { r: AttainmentResult; onDownload: () => void }) {
  const target = r.policy.target_level;
  const below = r.cos.filter(c => c.overall != null && c.overall < target - 1e-9).sort((a, b) => (a.overall ?? 0) - (b.overall ?? 0));
  const pct = (x: number) => `${Math.round(100 * x)}%`;
  return (
    <div className="att-results">
      <div className="row">
        <p><b>{r.attained} of {r.assessed}</b> assessed course outcomes reached the target level of {target}
          {r.batch && <> · batch {r.batch}</>}{r.no_data.length > 0 && <> · {r.no_data.length} not assessed</>}.</p>
        <span className="spacer" />
        <button className="btn small" onClick={onDownload}>Download report (.html)</button>
      </div>
      {r.unknown.length > 0 && <p className="hint">Left out, as the programme has no such outcome: {r.unknown.join(", ")}.</p>}
      <table className="att">
        <thead><tr><th>Programme outcome</th><th className="n">Attainment</th><th className="n">COs</th><th></th></tr></thead>
        <tbody>{r.pos.map(p => {
          const s = attainmentStatus(p.attainment, target);
          return (
            <tr key={p.code}>
              <td><b>{p.code}</b> {p.name}</td>
              <td className="n">{p.attainment == null ? "–" : p.attainment.toFixed(2)}</td>
              <td className="n">{p.outcomes}</td>
              <td><span className={`pill ${s.css}`}>{s.label}</span></td>
            </tr>);
        })}</tbody>
      </table>
      {below.length > 0 && (
        <details><summary>{below.length} course outcome{below.length === 1 ? "" : "s"} below the target level</summary>
          <ul className="ev">{below.map(c => <li key={`${c.course}-${c.co}`}><b>{c.course} CO{c.co}</b> {c.overall?.toFixed(2)}: {c.text}</li>)}</ul>
        </details>
      )}
      <details><summary>Every course outcome</summary>
        <div className="matrix-wrap">
          <table>
            <thead><tr><th>CO</th><th>Outcome</th><th className="n">Internal</th><th className="n">External</th><th className="n">Survey</th><th className="n">Overall</th></tr></thead>
            <tbody>{r.cos.map(c => (
              <tr key={`${c.course}-${c.co}`}>
                <td><b>{c.course} CO{c.co}</b></td>
                <td>{c.text}{c.notes.length > 0 && <div className="muted small">{c.notes.join("; ")}</div>}</td>
                {(["internal", "external", "survey"] as const).map(k => (
                  <td key={k} className="n">{k in c.levels ? <>{pct(c.shares[k])} <span className="muted small">→ {c.levels[k]}</span></> : <span className="muted">–</span>}</td>
                ))}
                <td className="n"><b>{c.overall == null ? "–" : c.overall.toFixed(2)}</b></td>
              </tr>))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
