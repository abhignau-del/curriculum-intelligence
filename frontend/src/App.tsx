import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import BenchmarkView from "./BenchmarkView";
import ProgrammeView from "./ProgrammeView";
import type { ProgrammeSummary, TaxonomyView } from "./types";

type View = { kind: "benchmark" } | { kind: "programme"; id: string };

export default function App() {
  const [programmes, setProgrammes] = useState<ProgrammeSummary[] | null>(null);
  const [taxonomy, setTaxonomy] = useState<TaxonomyView | null>(null);
  const [view, setView] = useState<View>({ kind: "benchmark" });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [acaddocOpen, setAcaddocOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const reload = useCallback(async () => {
    try { setProgrammes(await api.programmes()); } catch (e) { setError(String((e as Error).message)); }
  }, []);

  useEffect(() => {
    reload();
    api.taxonomy().then(setTaxonomy, e => setError(String(e.message)));
  }, [reload]);

  async function uploadFiles(files: FileList | null) {
    if (!files?.length) return;
    const added: string[] = [], failed: string[] = [];
    for (const f of Array.from(files)) {
      try { added.push((await api.upload(f)).institution); } catch (e) { failed.push((e as Error).message); }
    }
    if (fileInput.current) fileInput.current.value = "";
    await reload();
    setNotice(added.length ? `Added: ${added.join(", ")}` : "");
    setError(failed.join("\n"));
  }

  const skillName = (id: string) =>
    taxonomy?.areas.flatMap(a => a.skills).find(s => s.id === id)?.name ?? id;

  return (
    <div className="app">
      <header>
        <h1>Curriculum Intelligence</h1>
        <span className="muted">Benchmark a curriculum against its peers</span>
      </header>

      <aside>
        <button className={`nav ${view.kind === "benchmark" ? "active" : ""}`} onClick={() => setView({ kind: "benchmark" })}>
          Benchmark
        </button>
        <div className="side-title">
          <h2>Programmes</h2>
          <span className="muted small">{programmes?.length ?? ""}</span>
        </div>
        {programmes && programmes.length === 0 && <p className="hint">The library is empty. Add programmes below.</p>}
        <ul className="prog-list">
          {programmes?.map(p => (
            <li key={p.id}>
              <button className={view.kind === "programme" && view.id === p.id ? "active" : ""}
                      onClick={() => setView({ kind: "programme", id: p.id })}>
                {p.institution}
                <small>{p.name} · {p.courses} courses</small>
              </button>
            </li>
          ))}
        </ul>
        <div className="add-box">
          <h3>Add programmes</h3>
          <input ref={fileInput} type="file" accept=".json,.xlsx" multiple hidden
                 onChange={e => uploadFiles(e.target.files)} />
          <button className="btn" onClick={() => fileInput.current?.click()}>Upload .xlsx or .json…</button>
          <button className="btn" onClick={() => setAcaddocOpen(true)}>Import AcadDoc courses…</button>
          <p className="hint">
            Enter a peer's syllabus in the <a href="/api/template.xlsx" download>blank Excel template</a>, one course
            per row, then upload it.
          </p>
        </div>
      </aside>

      <main>
        {error && <div className="alert" role="alert"><span>{error}</span><button aria-label="Dismiss" onClick={() => setError("")}>×</button></div>}
        {notice && <div className="note" role="status"><span>{notice}</span><button aria-label="Dismiss" onClick={() => setNotice("")}>×</button></div>}
        {programmes && view.kind === "benchmark" &&
          <BenchmarkView programmes={programmes} taxonomy={taxonomy} onError={setError} />}
        {view.kind === "programme" &&
          <ProgrammeView key={view.id} id={view.id} skillName={skillName} onError={setError}
                         onDeleted={async () => { await reload(); setView({ kind: "benchmark" }); }} />}
      </main>

      {acaddocOpen && <AcadDocDialog onClose={() => setAcaddocOpen(false)}
        onDone={async name => { setAcaddocOpen(false); await reload(); setNotice(`Added: ${name}`); setError(""); }} />}
    </div>
  );
}

function AcadDocDialog({ onClose, onDone }: { onClose: () => void; onDone: (name: string) => void }) {
  const [institution, setInstitution] = useState("");
  const [name, setName] = useState("");
  const [only, setOnly] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true); setError("");
    try {
      const texts = await Promise.all(files.map(async f => ({ name: f.name, text: await f.text() })));
      const p = await api.importAcadDoc(institution.trim(), name.trim(), only.trim(), texts);
      onDone(p.institution);
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal card" role="dialog" aria-label="Import AcadDoc courses" onClick={e => e.stopPropagation()}>
        <h2>Import AcadDoc courses</h2>
        <p className="hint">Choose the course .json files exported from AcadDoc. They become one programme.</p>
        <label className="field"><span>Institution</span><input value={institution} onChange={e => setInstitution(e.target.value)} /></label>
        <label className="field"><span>Programme name</span><input value={name} placeholder="B.Sc. Mathematics" onChange={e => setName(e.target.value)} /></label>
        <label className="field"><span>Only courses offered to programme code (optional)</span><input value={only} placeholder="e.g. CSE" onChange={e => setOnly(e.target.value)} /></label>
        <label className="field"><span>Course files</span>
          <input type="file" accept=".json" multiple onChange={e => setFiles(Array.from(e.target.files ?? []))} /></label>
        {error && <div className="alert">{error}</div>}
        <div className="row">
          <span className="spacer" />
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={busy || !institution.trim() || !name.trim() || !files.length} onClick={submit}>
            Import {files.length ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}
          </button>
        </div>
      </div>
    </div>
  );
}
