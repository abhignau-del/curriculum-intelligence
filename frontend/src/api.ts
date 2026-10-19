import type { AttainmentResult, BenchmarkResult, Policy, ProgrammeDetail, ProgrammeSummary, RulesInfo, TaxonomyView } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function toError(r: Response): Promise<ApiError> {
  let body: { detail?: unknown } = {};
  try { body = await r.json(); } catch { /* not JSON */ }
  const d = body.detail;
  const msg = typeof d === "string" ? d
    : Array.isArray(d) ? d.map((e: { loc?: unknown[]; msg?: string }) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`).join("; ")
    : `Request failed (${r.status})`;
  return new ApiError(r.status, msg);
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw await toError(r);
  return (r.status === 204 ? undefined : await r.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

/** What to benchmark; `rules` and `degree` add regulatory checklists for the programme under review. */
export interface Selection { own: string; peers: string[]; rules?: string[]; degree?: string }

export const api = {
  taxonomy: () => call<TaxonomyView>("/api/taxonomy"),
  rules: () => call<RulesInfo[]>("/api/rules"),
  programmes: () => call<ProgrammeSummary[]>("/api/programmes"),
  programme: (id: string) => call<ProgrammeDetail>(`/api/programmes/${id}`),
  remove: (id: string) => call<void>(`/api/programmes/${id}`, { method: "DELETE" }),
  upload: (file: File) =>
    call<ProgrammeSummary>(`/api/programmes/upload?filename=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } }),
  importAcadDoc: (institution: string, name: string, only: string, files: { name: string; text: string }[]) =>
    call<ProgrammeSummary>("/api/programmes/acaddoc", json("POST", { institution, name, only, files })),
  benchmark: (sel: Selection) => call<BenchmarkResult>("/api/benchmark", json("POST", sel)),
  defaultPolicy: () => call<Policy>("/api/attainment/policy"),
  attainment: (id: string, file: File, policy: Policy) =>
    call<AttainmentResult>(attainmentPath(id, file, policy),
      { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } }),
};

/** The upload address for a batch's results; `format=html` asks for the report instead. */
export function attainmentPath(id: string, file: File, policy: Policy, format: "json" | "html" = "json"): string {
  const q = new URLSearchParams({ filename: file.name, policy: JSON.stringify(policy), format });
  return `/api/programmes/${id}/attainment?${q}`;
}

/** Post a file and hand the response to the browser as a download (the attainment report). */
export async function downloadPost(path: string, file: File, fallbackName: string): Promise<void> {
  const r = await fetch(BASE + path, { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } });
  if (!r.ok) throw await toError(r);
  const name = /filename="?([^"]+)"?/.exec(r.headers.get("content-disposition") ?? "")?.[1] ?? fallbackName;
  saveBlob(await r.blob(), name);
}

/** Fetch a file (GET, or POST with a JSON body) and hand it to the browser as a download. */
export async function download(path: string, fallbackName: string, body?: unknown): Promise<void> {
  const init: RequestInit = body === undefined ? {} : { ...json("POST", body), headers: { "Content-Type": "application/json" } };
  const r = await fetch(BASE + path, init);
  if (!r.ok) throw await toError(r);
  const name = /filename="?([^"]+)"?/.exec(r.headers.get("content-disposition") ?? "")?.[1] ?? fallbackName;
  saveBlob(await r.blob(), name);
}

export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
