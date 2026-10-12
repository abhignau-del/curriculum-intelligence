import type {
  Basis, BenchmarkResult, Checklist, CopoResult, CourseOn, Evidence, Level, OutcomesResult, ProgrammeSummary, RuleStatus,
  SchemeItem, SkillResult, Status,
} from "./types";

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
    .sort((a, b) => b.peer_share - a.peer_share || b.peer_core_share - a.peer_core_share
      || b.peer_core_course_share - a.peer_core_course_share || a.name.localeCompare(b.name));
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
  return `${s.name} is covered by ${pct(100 * s.peer_share)} of benchmarked programmes (${covering} of ${peerCount}${detail}) but ${here}.`
    + coursesOnSentence(s, split);
}

/** How many of the covering peers have a whole course on the skill (same wording as the HTML report). */
export function coursesOnSentence(s: SkillResult, split = false): string {
  if (!Object.values(s.peer_levels).includes("covered")) return "";
  const n = Object.keys(s.peer_courses_on).length;
  if (n === 0) return " None of them has a course on it: they teach it inside other courses.";
  const has = n === 1 ? "has" : "have";
  if (!split) return ` ${n} of them ${has} a course on it.`;
  const core = Object.values(s.peer_course_basis).filter(b => b === "core").length;
  const kind = core === n ? (n > 1 ? "all core" : "core")
    : core === 0 ? (n > 1 ? "all elective" : "elective")
    : `${core} core, ${n - core} elective`;
  return ` ${n} of them ${has} a course on it (${kind}).`;
}

/** "a core course on it: Title", naming the core courses when there are any. */
export function courseOnNote(cs: CourseOn[], split = false): string {
  let kind = "", titles = cs.map(c => c.course_title);
  if (split && cs.every(c => c.elective)) kind = "elective ";
  else if (split) { kind = "core "; titles = cs.filter(c => !c.elective).map(c => c.course_title); }
  return `${kind === "elective " ? "an" : "a"} ${kind}course on it: ${[...new Set(titles)].join(", ")}`;
}

/** The evidence behind one matrix cell: this programme (column null) or a peer. */
export function cellEvidence(s: SkillResult, peer: string | null): {
  level: Level; basis: Basis | null; courseBasis: Basis | null; coursesOn: CourseOn[]; evidence: Evidence[];
} {
  if (peer === null) return { level: s.own_level, basis: s.own_basis, courseBasis: s.own_course_basis,
                              coursesOn: s.own_courses_on, evidence: s.own_evidence };
  return { level: s.peer_levels[peer] ?? "absent", basis: s.peer_basis[peer] ?? null,
           courseBasis: s.peer_course_basis[peer] ?? null, coursesOn: s.peer_courses_on[peer] ?? [],
           evidence: s.peer_evidence[peer] ?? [] };
}

/** Glyph, label and CSS class for a coverage mark: a core course on the skill and
 * elective-only coverage get their own. */
export function coverMark(level: Level, basis: Basis | null, courseBasis: Basis | null = null): { mark: string; label: string; css: string } {
  if (courseBasis === "core") return { mark: "●", label: "A core course on it", css: "c-course" };
  const note = courseBasis === "elective" ? " (an elective course on it)" : "";
  if (level === "covered" && basis === "elective") return { mark: "○", label: "Covered only by electives" + note, css: "c-elective" };
  return { mark: LEVEL_MARK[level], label: LEVEL_LABEL[level] + note, css: `c-${level}` };
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

// ----- regulatory checklist ------------------------------------------------

/** Label and pill class per status, as in the HTML report. */
export const RULE_STATUS: Record<RuleStatus, { label: string; css: string }> = {
  met: { label: "Met", css: "ok" }, partly: { label: "Partly met", css: "Medium" },
  not_met: { label: "Not met", css: "High" }, not_checked: { label: "Not checked", css: "soft" },
};

const num = (x: number) => String(Math.round(x * 100) / 100);

/** "Required (9): 7 met, 2 partly met; Advisory (1): 1 not met." - the report's summary line. */
export function checklistSummary(cl: Checklist): string {
  const parts: string[] = [];
  for (const level of ["required", "advisory"] as const) {
    const rs = cl.results.filter(r => r.level === level);
    if (!rs.length) continue;
    const counts = (Object.keys(RULE_STATUS) as RuleStatus[])
      .filter(st => rs.some(r => r.status === st))
      .map(st => `${rs.filter(r => r.status === st).length} ${RULE_STATUS[st].label.toLowerCase()}`);
    parts.push(`${level[0].toUpperCase()}${level.slice(1)} (${rs.length}): ${counts.join(", ")}`);
  }
  return parts.length ? parts.join("; ") + "." : "";
}

/** Tiles for the summary row: "7 of 9" requirements (or advisory points) met, per checklist. */
export function checklistTiles(cl: Checklist): { value: string; label: string; na: boolean }[] {
  const tiles = [];
  for (const [level, label] of [["required", "Requirements met"], ["advisory", "Advisory points met"]] as const) {
    const rs = cl.results.filter(r => r.level === level);
    const done = rs.filter(r => r.status !== "not_checked");
    if (done.length) tiles.push({ value: `${done.filter(r => r.status === "met").length} of ${done.length}`, label: `${label}: ${cl.id}`, na: false });
    else if (rs.length) tiles.push({ value: "Not checked", label: `${cl.id}: no credit scheme recorded`, na: true });
  }
  return tiles;
}

/** The caveats the report prints above a checklist. */
export function checklistNotes(cl: Checklist): string[] {
  const notes: string[] = [];
  if (!cl.has_scheme && cl.results.some(r => r.status === "not_checked"))
    notes.push("No credit scheme is recorded for this programme, so its credit rules are not checked. "
      + "Add the credits a student earns in each category (the Credit scheme sheet of the template).");
  if (cl.missing_semesters.length) {
    const s = cl.missing_semesters.length > 1 ? "s" : "";
    notes.push(`The credit scheme has no credits for semester${s} ${cl.missing_semesters.join(", ")}, so credit totals for this degree are incomplete.`);
  }
  const beyond = Object.entries(cl.beyond);
  if (beyond.length)
    notes.push(`Not counted for this degree: credits in later semesters, ${beyond.map(([k, v]) => `${k} (${num(v)} credits)`).join(", ")}.`);
  const unmapped = Object.entries(cl.unmapped);
  if (unmapped.length)
    notes.push("Credit scheme labels that match none of the framework's categories, so count only towards the total: "
      + unmapped.map(([k, v]) => `${k} (${num(v)} credits)`).join(", ") + ".");
  return notes;
}

/** Degree choices for the selected rules: every variant name once, in order. */
export function degreeOptions(rules: { id: string; variants: { id: string; name: string }[] }[], chosen: string[]): string[] {
  return [...new Set(rules.filter(r => chosen.includes(r.id)).flatMap(r => r.variants.map(v => v.name)))];
}

/** A credit scheme grouped by semester, in the order given, with each semester's total. */
export function schemeBySemester(scheme: SchemeItem[]): { semester: string; items: SchemeItem[]; total: number }[] {
  const groups = new Map<string, SchemeItem[]>();
  for (const item of scheme) {
    const key = item.semester ?? "";
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return [...groups].map(([semester, items]) => ({ semester, items, total: items.reduce((t, i) => t + i.credits, 0) }));
}

export interface SavedRegulatory { rules: string[]; degree: string }

export function parseSavedRegulatory(raw: string | null): SavedRegulatory {
  try {
    const v = JSON.parse(raw ?? "null");
    if (v && Array.isArray(v.rules) && v.rules.every((x: unknown) => typeof x === "string") && typeof v.degree === "string")
      return v;
  } catch { /* corrupt storage */ }
  return { rules: [], degree: "" };
}

// ----- course outcomes ---------------------------------------------------------

/** "77 outcomes in 23 of 23 courses · 20% higher-order · 16 vague (21%) · ..." as in the HTML report. */
export function outcomesSummary(o: OutcomesResult, courseCount: number): string {
  const n = o.outcomes.length;
  if (!n) return "No course in this programme states its outcomes.";
  const courses = new Set(o.outcomes.map(x => x.course)).size;
  const vague = o.outcomes.filter(x => x.flags.includes("vague")).length;
  const noVerb = o.outcomes.filter(x => x.flags.includes("no_verb")).length;
  return `${n} outcomes in ${courses} of ${courseCount} courses · ${pct(o.higher_order_share == null ? null : 100 * o.higher_order_share)} higher-order · `
    + `${vague} vague (${pct(100 * vague / n)}) · ${noVerb} with no action verb · ${o.duplicates.length} stated for more than one course.`;
}

/** Bar segments for one year: level (0 = no level), count and width in %. */
export function levelSegments(row: { count: number; levels: Record<string, number> }, levels: number[]): { level: number; count: number; width: number }[] {
  const segs = levels.map(lv => ({ level: lv, count: row.levels[String(lv)] ?? 0 }));
  segs.push({ level: 0, count: row.levels["none"] ?? 0 });
  return segs.filter(s => s.count > 0).map(s => ({ ...s, width: row.count ? 100 * s.count / row.count : 0 }));
}

// ----- CO-PO mapping -------------------------------------------------------------

/** The POs no course outcome serves, as in the HTML report's note. */
export function unservedPos(c: CopoResult): string[] {
  return c.pos.filter(p => p.courses === 0).map(p => `${p.code} ${p.name}`.trim());
}

/** Each course outcome with its links, grouped by course in order: [course, outcomes][]. */
export function cosByCourse(c: CopoResult): [string, CopoResult["cos"]][] {
  const groups = new Map<string, CopoResult["cos"]>();
  for (const co of c.cos) groups.set(co.course, [...(groups.get(co.course) ?? []), co]);
  return [...groups];
}
