export type Level = "covered" | "touched" | "absent";
export type Status = "gap" | "watch" | "distinctive" | "aligned" | "uncommon";
/** How a covered skill is covered: by compulsory courses, or only by electives. */
export type Basis = "core" | "elective";

export interface ProgrammeSummary {
  id: string; institution: string; name: string; year: string; source: string;
  courses: number; credits: number; updated_at: string;
}

export interface Course {
  code: string; title: string; credits?: number | null; semester?: string | null; category?: string;
  topics: string[]; outcomes: string[];
}

/** Credits a student earns in one category of course, from the programme's regulations. */
export interface SchemeItem { category: string; credits: number; semester?: string | null; note?: string }

export interface ProgrammeOutcome { code: string; name?: string; text: string }

export interface Programme {
  institution: string; name: string; source: string; year: string; courses: Course[];
  degree?: string; scheme?: SchemeItem[]; programme_outcomes?: ProgrammeOutcome[];
}

export interface ProgrammeDetail {
  id: string;
  programme: Programme;
  course_skills: Record<string, string[]>;   // course code -> skill ids
  levels: Record<string, Level>;
  unmapped: { course: string; line: string }[];
}

export interface Skill { id: string; name: string; terms: string[] }
export interface Area { id: string; name: string; skills: Skill[] }
export interface TaxonomyView { name: string; areas: Area[] }

export interface Evidence {
  course: string; course_title: string; field: "title" | "topic" | "outcome"; line: string; term: string;
}

/** A course whose subject is the skill: its title names it, or most of its topic lines do. */
export interface CourseOn { course: string; course_title: string; elective: boolean; by: "title" | "topics" }

export interface SkillResult {
  id: string; name: string; area: string; status: Status; priority: "High" | "Medium" | null;
  own_level: Level; own_evidence: Evidence[];
  peer_share: number; peer_touched_share: number;
  peer_levels: Record<string, Level>;           // peer institution -> level
  peer_evidence: Record<string, Evidence[]>;
  own_basis: Basis | null;
  peer_basis: Record<string, Basis>;          // peers that cover it -> basis
  peer_core_share: number;
  own_courses_on: CourseOn[];
  own_course_basis: Basis | null;
  peer_courses_on: Record<string, CourseOn[]>;   // peers with a course on it
  peer_course_basis: Record<string, Basis>;      // core if one of those courses is core
  peer_course_share: number;
  peer_core_course_share: number;
}

export interface Overlap {
  a: string; b: string; a_title: string; b_title: string; similarity: number;
  level: "High" | "Moderate"; shared_terms: string[]; shared_skills: string[]; theory_lab_pair: boolean;
}

export interface BenchmarkResult {
  generated_by: string;
  programme: { id: string; institution: string; name: string; year: string };
  peers: { id: string; institution: string; name: string; year: string }[];
  unmapped: { course: string; line: string }[];
  taxonomy: string;
  alignment: number | null;
  records_electives: string[];               // programmes that mark any course as elective
  areas: { id: string; name: string; alignment: number | null; core_skills: number }[];
  skills: SkillResult[];
  overlaps: Overlap[];
  structure: { label: string; courses: number; credits: number | null }[];
  regulatory: Checklist[];                   // one per rules set asked for
  outcomes: OutcomesResult | null;           // when the programme under review states course outcomes
  copo: CopoResult | null;                   // CO-PO mapping, likewise
}

/** Course outcomes mapped to programme outcomes (see backend mapping.py). */
export interface CopoResult {
  framework: { id: string; name: string; source: string };
  pos: { code: string; name: string; text: string; page: string; courses: number; mean: number | null }[];
  matrix: { course: string; course_title: string; cells: Record<string, number> }[];
  cos: { course: string; text: string; level: number | null; links: { po: string; strength: number; reasons: string[] }[] }[];
  unmapped: { course: string; text: string }[];
}

/** Bloom's levels of the programme's course outcomes (see backend outcomes.py). */
export interface OutcomesResult {
  verb_list: string;
  levels: { level: number; id: string; name: string }[];
  outcomes: { course: string; course_title: string; semester: string | null; text: string;
              level: number | null; verbs: string[]; flags: string[] }[];
  without_outcomes: { course: string; course_title: string }[];
  duplicates: { text: string; courses: string[] }[];
  by_year: { year: string; count: number; levels: Record<string, number>; higher_order_share: number | null; vague: number }[];
  higher_order_share: number | null;
}

export type RuleStatus = "met" | "partly" | "not_met" | "not_checked";

export interface RuleResult {
  id: string; kind: string; text: string; page: string; level: "required" | "advisory"; note: string;
  status: RuleStatus; found: string; expected: string; evidence: string[];
}

export interface Checklist {
  id: string; name: string; source: string;
  variant: string | null; variant_name: string | null; variant_basis: string;
  has_scheme: boolean;
  category_credits: Record<string, number>;
  unmapped: Record<string, number>;          // scheme labels no category matched -> credits
  beyond: Record<string, number>;            // later semesters left out -> credits
  missing_semesters: number[];
  results: RuleResult[];
}

/** A built-in rules set the server can check against. */
export interface RulesInfo { id: string; name: string; source: string; variants: { id: string; name: string }[] }
