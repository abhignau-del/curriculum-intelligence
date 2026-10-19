import { describe, expect, it } from "vitest";
import {
  basisCounts, byStatus, cellEvidence, checklistNotes, checklistSummary, checklistTiles, courseOnNote, coursesOnSentence,
  attainmentStatus, coverMark, cosByCourse, degreeOptions, fromForm, gapSentence, levelSegments, outcomesSummary,
  parseSavedPolicy, parseSavedRegulatory, RULE_STATUS, toForm,
  schemeBySemester, unservedPos, parseSaved, peerCourses, peersSplit, resolveSelection,
  selectionProblem, splitOnTerm, toSaved,
} from "./benchmarkops";
import type {
  BenchmarkResult, Checklist, CopoResult, CourseOn, OutcomesResult, Policy, ProgrammeSummary, RuleResult, SkillResult,
} from "./types";

const prog = (id: string, institution = `Inst ${id}`): ProgrammeSummary =>
  ({ id, institution, name: "B.Sc.", year: "", source: "", courses: 1, credits: 4, updated_at: "" });
const progs = [prog("a"), prog("b"), prog("c")];

const skill = (over: Partial<SkillResult> = {}): SkillResult => ({
  id: "python", name: "Python", area: "computational", status: "gap", priority: "High",
  own_level: "absent", own_evidence: [], peer_share: 0.75, peer_touched_share: 0,
  peer_levels: { P1: "covered", P2: "covered", P3: "covered", P4: "absent" },
  peer_evidence: {}, own_basis: null, peer_basis: {}, peer_core_share: 0,
  own_courses_on: [], own_course_basis: null, peer_courses_on: {}, peer_course_basis: {},
  peer_course_share: 0, peer_core_course_share: 0, ...over,
});

describe("selection", () => {
  it("defaults to the first programme against all the others", () => {
    expect(resolveSelection(null, progs)).toEqual({ own: "a", peers: ["b", "c"] });
  });

  it("restores a saved choice and includes programmes added since", () => {
    const saved = toSaved("b", ["c"], progs);           // a was unticked
    expect(saved).toEqual({ own: "b", excluded: ["a"] });
    expect(resolveSelection(saved, [...progs, prog("d")])).toEqual({ own: "b", peers: ["c", "d"] });
  });

  it("falls back when the saved programme was deleted", () => {
    expect(resolveSelection({ own: "gone", excluded: [] }, progs)).toEqual({ own: "a", peers: ["b", "c"] });
    expect(resolveSelection(null, [])).toEqual({ own: "", peers: [] });
  });

  it("ignores corrupt storage", () => {
    expect(parseSaved("{not json")).toBeNull();
    expect(parseSaved('{"own": 1, "excluded": []}')).toBeNull();
    expect(parseSaved('{"own": "a", "excluded": [2]}')).toBeNull();
    expect(parseSaved('{"own": "a", "excluded": ["b"]}')).toEqual({ own: "a", excluded: ["b"] });
  });

  it("explains selections that can't run", () => {
    expect(selectionProblem("", [], [])).toMatch(/Add a programme/);
    expect(selectionProblem("a", [], progs)).toMatch(/at least one peer/);
    const twins = [prog("a"), prog("b", "Same U"), prog("c", "Same U")];
    expect(selectionProblem("a", ["b", "c"], twins)).toMatch(/same institution \(Same U\)/);
    expect(selectionProblem("a", ["b"], twins)).toBeNull();
  });
});

describe("results", () => {
  it("sorts a status group by peer share, then name", () => {
    const rows = [skill({ name: "B", peer_share: 0.5 }), skill({ name: "A", peer_share: 0.5 }),
      skill({ name: "C", peer_share: 0.9 }), skill({ name: "D", status: "watch" })];
    expect(byStatus(rows, "gap").map(s => s.name)).toEqual(["C", "A", "B"]);
  });

  it("writes the gap sentence", () => {
    expect(gapSentence(skill(), 4)).toBe(
      "Python is covered by 75% of benchmarked programmes (3 of 4) but is not found in this curriculum."
      + " None of them has a course on it: they teach it inside other courses.");
    expect(gapSentence(skill({ own_level: "touched" }), 4)).toMatch(/only one syllabus line here\. None/);
  });

  it("finds the evidence behind a matrix cell", () => {
    const ev = { course: "X1", course_title: "Python Lab", field: "title" as const, line: "Python Lab", term: "python" };
    const s = skill({ own_evidence: [ev], own_level: "covered", peer_evidence: { P1: [ev] } });
    expect(cellEvidence(s, null)).toEqual({ level: "covered", basis: null, courseBasis: null, coursesOn: [], evidence: [ev] });
    expect(cellEvidence(s, "P1").evidence).toEqual([ev]);
    expect(cellEvidence(s, "P4")).toEqual({ level: "absent", basis: null, courseBasis: null, coursesOn: [], evidence: [] });
    expect(cellEvidence(s, "unknown").level).toBe("absent");
  });

  it("lists each peer's courses once, sorted", () => {
    const e = (title: string) => ({ course: "c", course_title: title, field: "topic" as const, line: "l", term: "t" });
    const s = skill({ peer_evidence: { P1: [e("Z"), e("A"), e("Z")], P2: [] } });
    expect(peerCourses(s)).toEqual([["P1", ["A", "Z"]]]);
  });
});

describe("splitOnTerm", () => {
  it("finds the normalised term in the original text", () => {
    expect(splitOnTerm("Green's theorem in the plane", "green s theorem")).toEqual(["", "Green's theorem", " in the plane"]);
    expect(splitOnTerm("Root finding: Newton-Raphson method", "newton raphson")).toEqual(["Root finding: ", "Newton-Raphson", " method"]);
    expect(splitOnTerm("Eigenvalues and eigenvectors", "eigenvalue")).toEqual(["", "Eigenvalues", " and eigenvectors"]);
  });
  it("respects word boundaries and misses gracefully", () => {
    expect(splitOnTerm("Engineering ring theory", "ring")).toEqual(["Engineering ", "ring", " theory"]);
    expect(splitOnTerm("Nothing here", "python")).toEqual(["Nothing here", "", ""]);
  });
});

describe("core and electives", () => {
  const s = skill({
    peer_levels: { P1: "covered", P2: "covered", P3: "touched", P4: "absent" },
    peer_basis: { P1: "core", P2: "elective" }, peer_share: 0.5, peer_core_share: 0.25,
  });

  it("counts peers by basis", () => {
    expect(basisCounts(s)).toEqual({ core: 1, elective: 1 });
  });

  it("adds the split to the gap sentence only when asked", () => {
    expect(gapSentence(s, 4)).toContain("(2 of 4) but");
    expect(gapSentence(s, 4, true)).toContain("(2 of 4: in the core of 1, only as an elective in 1) but");
  });

  it("marks elective-only coverage differently", () => {
    expect(coverMark("covered", "elective")).toEqual({ mark: "○", label: "Covered only by electives", css: "c-elective" });
    expect(coverMark("covered", "core").mark).toBe("✓");
    expect(coverMark("touched", "elective").mark).toBe("△");   // basis only matters when covered
    expect(cellEvidence(s, "P2").basis).toBe("elective");
    expect(cellEvidence(s, "P3").basis).toBeNull();
  });

  it("sorts equal peer shares by core share", () => {
    const a = skill({ name: "A", peer_share: 0.5, peer_core_share: 0.1 });
    const b = skill({ name: "B", peer_share: 0.5, peer_core_share: 0.4 });
    expect(byStatus([a, b], "gap").map(x => x.name)).toEqual(["B", "A"]);
  });

  it("knows whether any peer records electives", () => {
    const r = (records: string[]) => ({ peers: [{ id: "1", institution: "Peer U", name: "", year: "" }],
      records_electives: records } as unknown as BenchmarkResult);
    expect(peersSplit(r(["Peer U"]))).toBe(true);
    expect(peersSplit(r(["Own U"]))).toBe(false);     // only the programme under review records them
  });
});

describe("courses on a skill", () => {
  const on = (title: string, elective: boolean): CourseOn => ({ course: title.slice(0, 3), course_title: title, elective, by: "title" });
  const s = skill({
    peer_levels: { P1: "covered", P2: "covered", P3: "covered", P4: "absent" },
    peer_courses_on: { P1: [on("Modelling", false)], P2: [on("Modelling Lab", true)] },
    peer_course_basis: { P1: "core", P2: "elective" }, peer_course_share: 0.5, peer_core_course_share: 0.25,
  });

  it("says how many covering peers have a course on it", () => {
    expect(coursesOnSentence(s)).toBe(" 2 of them have a course on it.");
    expect(coursesOnSentence(s, true)).toBe(" 2 of them have a course on it (1 core, 1 elective).");
    const one = skill({ peer_courses_on: { P1: [on("Python", false)] }, peer_course_basis: { P1: "core" } });
    expect(coursesOnSentence(one, true)).toBe(" 1 of them has a course on it (core).");
    const allE = skill({ peer_courses_on: { P1: [on("A", true)], P2: [on("B", true)] },
                         peer_course_basis: { P1: "elective", P2: "elective" } });
    expect(coursesOnSentence(allE, true)).toBe(" 2 of them have a course on it (all elective).");
    expect(coursesOnSentence(skill({ peer_levels: { P1: "touched" } }))).toBe("");   // nobody covers it
    expect(gapSentence(s, 4, true)).toMatch(/curriculum\. 2 of them have a course on it \(1 core, 1 elective\)\.$/);
  });

  it("names the core courses in the note", () => {
    const mixed = [on("Probability Theory", true), on("Probability and Statistics", false), on("Probability and Statistics", false)];
    expect(courseOnNote(mixed, true)).toBe("a core course on it: Probability and Statistics");
    expect(courseOnNote([on("LaTeX", true)], true)).toBe("an elective course on it: LaTeX");
    expect(courseOnNote(mixed)).toBe("a course on it: Probability Theory, Probability and Statistics");
  });

  it("marks a core course on it with its own glyph", () => {
    expect(coverMark("covered", "core", "core")).toEqual({ mark: "●", label: "A core course on it", css: "c-course" });
    expect(coverMark("covered", "elective", "elective").label).toBe("Covered only by electives (an elective course on it)");
    expect(coverMark("covered", "core", "elective")).toEqual({ mark: "✓", label: "Covered (an elective course on it)", css: "c-covered" });
    expect(cellEvidence(s, "P1").courseBasis).toBe("core");
    expect(cellEvidence(s, "P2").coursesOn.map(c => c.course_title)).toEqual(["Modelling Lab"]);
    expect(cellEvidence(s, "P3").courseBasis).toBeNull();
  });

  it("breaks ties between equal gaps by core-course share", () => {
    const a = skill({ name: "A", peer_share: 0.5, peer_core_share: 0.4, peer_core_course_share: 0 });
    const b = skill({ name: "B", peer_share: 0.5, peer_core_share: 0.4, peer_core_course_share: 0.2 });
    expect(byStatus([a, b], "gap").map(x => x.name)).toEqual(["B", "A"]);
  });
});

describe("regulatory checklist", () => {
  const res = (id: string, status: RuleResult["status"], level: RuleResult["level"] = "required"): RuleResult =>
    ({ id, kind: "category_credits", text: id, page: "19", level, note: "", status, found: "", expected: "", evidence: [] });
  const cl = (over: Partial<Checklist> = {}): Checklist => ({
    id: "ugc", name: "UGC", source: "", variant: "3-year", variant_name: "3-year UG degree", variant_basis: "x",
    has_scheme: true, category_credits: {}, unmapped: {}, beyond: {}, missing_semesters: [],
    results: [res("a", "met"), res("b", "met"), res("c", "partly"), res("d", "not_met", "advisory")], ...over,
  });

  it("summarises by level, in status order", () => {
    expect(checklistSummary(cl())).toBe("Required (3): 2 met, 1 partly met; Advisory (1): 1 not met.");
    expect(checklistSummary(cl({ results: [] }))).toBe("");
  });

  it("makes tiles for required and advisory rules, and says when nothing could be checked", () => {
    expect(checklistTiles(cl())).toEqual([
      { value: "2 of 3", label: "Requirements met: ugc", na: false },
      { value: "0 of 1", label: "Advisory points met: ugc", na: false },
    ]);
    const unchecked = cl({ has_scheme: false, results: [res("a", "not_checked"), res("b", "not_checked")] });
    expect(checklistTiles(unchecked)).toEqual([{ value: "Not checked", label: "ugc: no credit scheme recorded", na: true }]);
    // advisory-only rules never claim a missing credit scheme
    expect(checklistTiles(cl({ results: [res("p", "met", "advisory")] }))).toEqual([
      { value: "1 of 1", label: "Advisory points met: ugc", na: false }]);
  });

  it("lists the caveats", () => {
    expect(checklistNotes(cl())).toEqual([]);
    const notes = checklistNotes(cl({ has_scheme: false, results: [res("a", "not_checked")], missing_semesters: [7, 8],
                                      beyond: { VII: 16 }, unmapped: { Sports: 2 } }));
    expect(notes[0]).toMatch(/^No credit scheme is recorded/);
    expect(notes[1]).toBe("The credit scheme has no credits for semesters 7, 8, so credit totals for this degree are incomplete.");
    expect(notes[2]).toBe("Not counted for this degree: credits in later semesters, VII (16 credits).");
    expect(notes[3]).toMatch(/count only towards the total: Sports \(2 credits\)\.$/);
    expect(checklistNotes(cl({ missing_semesters: [8] }))[0]).toMatch(/for semester 8,/);
  });

  it("offers each degree variant of the chosen rules once", () => {
    const rules = [{ id: "a", variants: [{ id: "3", name: "3-year" }, { id: "4", name: "4-year" }] },
                   { id: "b", variants: [{ id: "4", name: "4-year" }, { id: "5", name: "5-year" }] }];
    expect(degreeOptions(rules, ["a", "b"])).toEqual(["3-year", "4-year", "5-year"]);
    expect(degreeOptions(rules, ["b"])).toEqual(["4-year", "5-year"]);
    expect(degreeOptions(rules, [])).toEqual([]);
  });

  it("groups a credit scheme by semester", () => {
    const g = schemeBySemester([{ category: "Major", credits: 8, semester: "I" }, { category: "AEC", credits: 2, semester: "I" },
                                { category: "Major", credits: 12, semester: "II" }, { category: "Project", credits: 4 }]);
    expect(g.map(x => [x.semester, x.items.length, x.total])).toEqual([["I", 2, 10], ["II", 1, 12], ["", 1, 4]]);
  });

  it("reads saved choices defensively", () => {
    expect(parseSavedRegulatory('{"rules": ["ugc"], "degree": "3-year"}')).toEqual({ rules: ["ugc"], degree: "3-year" });
    expect(parseSavedRegulatory("{bad")).toEqual({ rules: [], degree: "" });
    expect(parseSavedRegulatory('{"rules": [1], "degree": ""}')).toEqual({ rules: [], degree: "" });
    expect(parseSavedRegulatory(null)).toEqual({ rules: [], degree: "" });
  });

  it("labels statuses like the HTML report", () => {
    expect(RULE_STATUS.not_met).toEqual({ label: "Not met", css: "High" });
    expect(RULE_STATUS.partly.css).toBe("Medium");
  });
});

describe("course outcomes", () => {
  const o: OutcomesResult = {
    verb_list: "v", levels: [1, 2, 3, 4, 5, 6].map(l => ({ level: l, id: String(l), name: String(l) })),
    outcomes: [
      { course: "A", course_title: "A", semester: "I", text: "Understand x", level: 2, verbs: ["understand"], flags: ["vague"] },
      { course: "A", course_title: "A", semester: "I", text: "Prove y", level: 5, verbs: ["prove"], flags: [] },
      { course: "B", course_title: "B", semester: "II", text: "Knowledge of z", level: null, verbs: [], flags: ["no_verb"] },
    ],
    without_outcomes: [{ course: "C", course_title: "C" }], duplicates: [],
    by_year: [{ year: "Year 1", count: 3, levels: { "2": 1, "5": 1, none: 1 }, higher_order_share: 0.5, vague: 1 }],
    higher_order_share: 0.5,
  };
  it("summarises like the HTML report", () => {
    expect(outcomesSummary(o, 3)).toBe("3 outcomes in 2 of 3 courses · 50% higher-order · 1 vague (33%) · 1 with no action verb · 0 stated for more than one course.");
    expect(outcomesSummary({ ...o, outcomes: [] }, 3)).toBe("No course in this programme states its outcomes.");
  });
  it("makes bar segments in level order, unrated last", () => {
    expect(levelSegments(o.by_year[0], [1, 2, 3, 4, 5, 6]).map(s => [s.level, s.count, Math.round(s.width)]))
      .toEqual([[2, 1, 33], [5, 1, 33], [0, 1, 33]]);
  });
});

describe("CO-PO mapping", () => {
  const c: CopoResult = {
    framework: { id: "f", name: "F", source: "" },
    pos: [{ code: "P1", name: "Knowledge", text: "", page: "", courses: 2, mean: 2 },
          { code: "P2", name: "Ethics", text: "", page: "", courses: 0, mean: null }],
    matrix: [], unmapped: [],
    cos: [{ course: "A", text: "x", level: 3, links: [] }, { course: "B", text: "y", level: 2, links: [] },
          { course: "A", text: "z", level: 1, links: [] }],
  };
  it("names the POs no outcome serves", () => { expect(unservedPos(c)).toEqual(["P2 Ethics"]); });
  it("groups outcomes by course, in order", () => {
    expect(cosByCourse(c).map(([k, cos]) => [k, cos.map(x => x.text)])).toEqual([["A", ["x", "z"]], ["B", ["y"]]]);
  });
});

describe("attainment policy form", () => {
  const policy: Policy = { name: "d", thresholds: [[0.7, 3], [0.6, 2], [0.5, 1]], weights: { internal: 0.3, external: 0.7 },
                           direct_share: 0.8, target_level: 2 };
  it("round-trips the policy through the form", () => {
    const f = toForm(policy);
    expect(f).toEqual({ l3: 70, l2: 60, l1: 50, internal: 30, external: 70, direct: 80, target: 2 });
    expect(fromForm(f, "d")).toEqual(policy);
  });
  it("explains a form that can't be used", () => {
    const f = toForm(policy);
    expect(fromForm({ ...f, l2: 75 })).toMatch(/level 3 must be above level 2/);
    expect(fromForm({ ...f, internal: 0, external: 0 })).toMatch(/can't both be 0/);
    expect(fromForm({ ...f, direct: 120 })).toMatch(/between 0 and 100/);
    expect(fromForm({ ...f, target: 4 })).toMatch(/target level/);
  });
  it("reads saved settings defensively", () => {
    expect(parseSavedPolicy(JSON.stringify(toForm(policy)))).toEqual(toForm(policy));
    expect(parseSavedPolicy('{"l3": "70"}')).toBeNull();
    expect(parseSavedPolicy("{bad")).toBeNull();
  });
  it("labels attainment against the target", () => {
    expect(attainmentStatus(2, 2)).toEqual({ label: "Met", css: "ok" });
    expect(attainmentStatus(1.99, 2)).toEqual({ label: "Below", css: "High" });
    expect(attainmentStatus(null, 2)).toEqual({ label: "No data", css: "soft" });
  });
});
