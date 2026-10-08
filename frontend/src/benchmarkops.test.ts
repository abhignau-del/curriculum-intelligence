import { describe, expect, it } from "vitest";
import {
  byStatus, cellEvidence, gapSentence, parseSaved, peerCourses, resolveSelection, selectionProblem, splitOnTerm, toSaved,
} from "./benchmarkops";
import type { ProgrammeSummary, SkillResult } from "./types";

const prog = (id: string, institution = `Inst ${id}`): ProgrammeSummary =>
  ({ id, institution, name: "B.Sc.", year: "", source: "", courses: 1, credits: 4, updated_at: "" });
const progs = [prog("a"), prog("b"), prog("c")];

const skill = (over: Partial<SkillResult> = {}): SkillResult => ({
  id: "python", name: "Python", area: "computational", status: "gap", priority: "High",
  own_level: "absent", own_evidence: [], peer_share: 0.75, peer_touched_share: 0,
  peer_levels: { P1: "covered", P2: "covered", P3: "covered", P4: "absent" },
  peer_evidence: {}, ...over,
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
      "Python is covered by 75% of benchmarked programmes (3 of 4) but is not found in this curriculum.");
    expect(gapSentence(skill({ own_level: "touched" }), 4)).toMatch(/only one syllabus line here\.$/);
  });

  it("finds the evidence behind a matrix cell", () => {
    const ev = { course: "X1", course_title: "Python Lab", field: "title" as const, line: "Python Lab", term: "python" };
    const s = skill({ own_evidence: [ev], own_level: "covered", peer_evidence: { P1: [ev] } });
    expect(cellEvidence(s, null)).toEqual({ level: "covered", evidence: [ev] });
    expect(cellEvidence(s, "P1").evidence).toEqual([ev]);
    expect(cellEvidence(s, "P4")).toEqual({ level: "absent", evidence: [] });
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
