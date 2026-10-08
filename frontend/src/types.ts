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

export interface Programme {
  institution: string; name: string; source: string; year: string; courses: Course[];
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

export interface SkillResult {
  id: string; name: string; area: string; status: Status; priority: "High" | "Medium" | null;
  own_level: Level; own_evidence: Evidence[];
  peer_share: number; peer_touched_share: number;
  peer_levels: Record<string, Level>;           // peer institution -> level
  peer_evidence: Record<string, Evidence[]>;
  own_basis: Basis | null;
  peer_basis: Record<string, Basis>;          // peers that cover it -> basis
  peer_core_share: number;
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
}
