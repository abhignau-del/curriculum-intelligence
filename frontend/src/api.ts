import type { BenchmarkResult, ProgrammeDetail, ProgrammeSummary, TaxonomyView } from "./types";

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

export interface Selection { own: string; peers: string[] }

export const api = {
  taxonomy: () => call<TaxonomyView>("/api/taxonomy"),
  programmes: () => call<ProgrammeSummary[]>("/api/programmes"),
  programme: (id: string) => call<ProgrammeDetail>(`/api/programmes/${id}`),
  remove: (id: string) => call<void>(`/api/programmes/${id}`, { method: "DELETE" }),
  upload: (file: File) =>
    call<ProgrammeSummary>(`/api/programmes/upload?filename=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file, headers: { "Content-Type": "application/octet-stream" } }),
  importAcadDoc: (institution: string, name: string, only: string, files: { name: string; text: string }[]) =>
    call<ProgrammeSummary>("/api/programmes/acaddoc", json("POST", { institution, name, only, files })),
  benchmark: (sel: Selection) => call<BenchmarkResult>("/api/benchmark", json("POST", sel)),
};

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
