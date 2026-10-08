import type { Basis, BenchmarkResult, Evidence, Level, ProgrammeSummary, SkillResult, Status } from "./types";

/** What the user picked last time. Peers are stored as exclusions, so programmes
 * added later are included by default. */
export interface SavedSelection { own: string; excluded: string[] }

export function resolveSelection(saved: SavedSelection | null, programmes: ProgrammeSummary[]) {
  const ids = programmes.map(p => p.id);
  const own = saved && ids.includes(saved.own) ? saved.own : (ids[0] ?? "");
  const excluded = new Set(saved?.excluded ?? []);
  return { own, peers: ids.filter(id => id !== own && !excluded.has(id)) };
}

export function toSaved(own: string, peers: string[], programmes: ProgrammeSummary[]): SavedSelection {
  const chosen = new Set(peers);
  return { own, excluded: programmes.map(p => p.id).filter(id => id !== own && !chosen.has(id)) };
}

export function parseSaved(raw: string | null): SavedSelection | null {
  try {
    const v = JSON.parse(raw ?? "null");
    if (v && typeof v.own === "string" && Array.isArray(v.excluded) && v.excluded.every((x: unknown) => typeof x === "string"))
      return v;
  } catch { /* corrupt storage */ }
  return null;
}

/** Why this selection can't be benchmarked, or null if it can. */
export function selectionProblem(own: string, peers: string[], programmes: ProgrammeSummary[]): string | null {
  if (!own) return "Add a programme to review.";
  if (peers.length === 0) return "Tick at least one peer programme.";
  const byId = new Map(programmes.map(p => [p.id, p]));
  const seen = new Map<string, number>();
  for (const id of peers) {
    const inst = byId.get(id)?.institution ?? "";
    seen.set(inst, (seen.get(inst) ?? 0) + 1);
  }
  const dup = [...seen].filter(([, n]) => n > 1).map(([inst]) => inst);
  if (dup.length) return `Two ticked peers have the same institution (${dup.join(", ")}). Untick one.`;
  return null;
}

export function byStatus(skills: SkillResult[], status: Status): SkillResult[] {
  return skills.filter(s => s.status === status)
    .sort((a, b) => b.peer_share - a.peer_share || b.peer_core_share - a.peer_core_share || a.name.localeCompare(b.name));
}

export const pct = (x: number | null | undefined) => (x == null ? "–" : `${Math.round(x)}%`);

/** True when at least one peer records which of its courses are electives. */
export function peersSplit(r: BenchmarkResult): boolean {
  return r.peers.some(p => r.records_electives.includes(p.institution));
}

export function basisCounts(s: SkillResult): { core: number; elective: number } {
  const b = Object.values(s.peer_basis);
  return { core: b.filter(x => x === "core").length, elective: b.filter(x => x === "elective").length };
}

export function gapSentence(s: SkillResult, peerCount: number, split = false): string {
  const covering = Object.values(s.peer_levels).filter(l => l === "covered").length;
  const here = s.own_level === "touched" ? "is mentioned in only one syllabus line here" : "is not found in this curriculum";
  const { core, elective } = basisCounts(s);
  const detail = split ? `: in the core of ${core}, only as an elective in ${elective}` : "";
  return `${s.name} is covered by ${pct(100 * s.peer_share)} of benchmarked programmes (${covering} of ${peerCount}${detail}) but ${here}.`;
}

/** The evidence behind one matrix cell: this programme (column null) or a peer. */
export function cellEvidence(s: SkillResult, peer: string | null): { level: Level; basis: Basis | null; evidence: Evidence[] } {
  if (peer === null) return { level: s.own_level, basis: s.own_basis, evidence: s.own_evidence };
  return { level: s.peer_levels[peer] ?? "absent", basis: s.peer_basis[peer] ?? null, evidence: s.peer_evidence[peer] ?? [] };
}

/** Glyph, label and CSS class for a coverage mark; elective-only coverage gets its own. */
export function coverMark(level: Level, basis: Basis | null): { mark: string; label: string; css: string } {
  if (level === "covered" && basis === "elective") return { mark: "○", label: "Covered only by electives", css: "c-elective" };
  return { mark: LEVEL_MARK[level], label: LEVEL_LABEL[level], css: `c-${level}` };
}

/** Course titles per peer that carry evidence for a skill. */
export function peerCourses(s: SkillResult): [string, string[]][] {
  return Object.entries(s.peer_evidence)
    .map(([peer, ev]) => [peer, [...new Set(ev.map(e => e.course_title))].sort()] as [string, string[]])
    .filter(([, titles]) => titles.length > 0);
}

export function skillsByArea(r: BenchmarkResult): { id: string; name: string; skills: SkillResult[] }[] {
  return r.areas.map(a => ({ id: a.id, name: a.name, skills: r.skills.filter(s => s.area === a.id) }));
}

export const LEVEL_LABEL: Record<Level, string> = { covered: "Covered", touched: "Mentioned once", absent: "Not found" };
export const LEVEL_MARK: Record<Level, string> = { covered: "✓", touched: "△", absent: "·" };

/** Split a syllabus line around the (normalised) term that matched, for highlighting.
 * "green s theorem" must find "Green's theorem"; a plural ending is included. */
export function splitOnTerm(line: string, term: string): [string, string, string] {
  const words = term.split(" ").filter(Boolean).map(w => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!words.length) return [line, "", ""];
  const re = new RegExp(`(?<![A-Za-z0-9])${words.join("[^A-Za-z0-9]+")}(?:e?s)?(?![A-Za-z0-9])`, "i");
  const m = re.exec(line);
  if (!m) return [line, "", ""];
  return [line.slice(0, m.index), m[0], line.slice(m.index + m[0].length)];
}
