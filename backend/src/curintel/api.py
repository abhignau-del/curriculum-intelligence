"""HTTP API and the web interface.

    python -m curintel serve [--seed] [--port 8000] [--db FILE]

A single-user local tool: there is no sign-in, so bind it to 127.0.0.1 (the
default) unless everyone who can reach it may change the library.
"""
from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from . import __version__
from .analysis import benchmark, profile, unmapped_lines
from .importers import ImportError_, from_acaddoc_texts, from_workbook, write_template
from .overlap import find_overlaps
from .report import render_html, to_dict
from .schema import Programme
from .store import Store
from .taxonomy import Taxonomy

FRONTEND = Path(__file__).resolve().parents[3] / "frontend" / "dist"
MAX_UPLOAD = 10 * 1024 * 1024


class BenchmarkRequest(BaseModel):
    own: str
    peers: list[str] = Field(min_length=1)


class AcadDocFile(BaseModel):
    name: str
    text: str


class AcadDocImport(BaseModel):
    institution: str = Field(min_length=1)
    name: str = Field(min_length=1)
    only: Optional[str] = None
    files: list[AcadDocFile] = Field(min_length=1)


def _summary(pid: str, p: Programme, updated_at: str = "") -> dict:
    return {"id": pid, "institution": p.institution, "name": p.name, "year": p.year,
            "source": p.source, "courses": len(p.courses), "credits": p.total_credits,
            "updated_at": updated_at}


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(map(str, err["loc"]))
    return f"{where}: {err['msg']}" if where else err["msg"]


def _attachment(name: str) -> dict:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "file"
    return {"Content-Disposition": f'attachment; filename="{safe}"'}


def create_app(store: Store | None = None, taxonomy: Taxonomy | None = None) -> FastAPI:
    store = store or Store()
    tax = taxonomy or Taxonomy.builtin()
    app = FastAPI(title="Curriculum Intelligence", version=__version__)

    def get_or_404(pid: str) -> Programme:
        p = store.get(pid)
        if p is None:
            raise HTTPException(404, "No such programme")
        return p

    @app.exception_handler(ImportError_)
    async def import_error(_req, exc: ImportError_):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__}

    @app.get("/api/taxonomy")
    def taxonomy_view():
        return {"name": tax.name, "areas": [
            {"id": a.id, "name": a.name, "skills": [{"id": s.id, "name": s.name, "terms": list(s.terms)}
                                                    for s in a.skills]}
            for a in tax.areas]}

    # ----- library -----------------------------------------------------
    @app.get("/api/programmes")
    def list_programmes():
        return [_summary(pid, p, u) for pid, p, u in store.list()]

    @app.get("/api/programmes/{pid}")
    def programme_detail(pid: str):
        p = get_or_404(pid)
        prof = profile(p, tax)
        per_course: dict[str, set[str]] = {c.code: set() for c in p.courses}
        for skill, cov in prof.items():
            for e in cov.evidence:
                per_course[e.course_code].add(skill)
        return {
            "id": pid, "programme": p.model_dump(),
            "course_skills": {code: sorted(s, key=lambda k: tax.skills[k].name)
                              for code, s in per_course.items()},
            "levels": {s: cov.level for s, cov in prof.items()},
            "unmapped": [{"course": c, "line": line} for c, line in unmapped_lines(p, tax)],
        }

    @app.post("/api/programmes", status_code=201)
    def create_programme(p: Programme):
        return _summary(store.add(p), p)

    @app.put("/api/programmes/{pid}")
    def replace_programme(pid: str, p: Programme):
        get_or_404(pid)
        store.replace(pid, p)
        return _summary(pid, p)

    @app.delete("/api/programmes/{pid}", status_code=204)
    def delete_programme(pid: str):
        if not store.delete(pid):
            raise HTTPException(404, "No such programme")

    @app.post("/api/programmes/upload", status_code=201)
    async def upload(request: Request, filename: str):
        """Body: the raw bytes of a programme .json or a template .xlsx."""
        data = await request.body()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "File is larger than 10 MB")
        suffix = Path(filename).suffix.lower()
        if suffix == ".xlsx":
            p = from_workbook(data, filename)
        elif suffix == ".json":
            try:
                p = Programme.model_validate_json(data)
            except ValidationError as exc:
                raise HTTPException(400, f"{filename}: {_first_error(exc)}") from None
        else:
            raise HTTPException(400, f"{filename}: expected a .json programme or an .xlsx workbook")
        return _summary(store.add(p), p)

    @app.post("/api/programmes/acaddoc", status_code=201)
    def import_acaddoc(req: AcadDocImport):
        p = from_acaddoc_texts([(f.name, f.text) for f in req.files], req.institution, req.name,
                               req.only or None)
        return _summary(store.add(p), p)

    @app.get("/api/programmes/{pid}/download")
    def download_programme(pid: str):
        p = get_or_404(pid)
        body = p.model_dump_json(indent=2, exclude_defaults=True)
        return Response(body, media_type="application/json", headers=_attachment(f"{p.institution}.json"))

    @app.get("/api/template.xlsx")
    def template():
        buf = BytesIO()
        write_template(buf)
        return Response(buf.getvalue(), headers=_attachment("programme-template.xlsx"),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ----- analysis ----------------------------------------------------
    def run(req: BenchmarkRequest):
        if req.own in req.peers:
            raise HTTPException(400, "The programme under review can't also be one of its peers")
        own = get_or_404(req.own)
        peers = [get_or_404(pid) for pid in dict.fromkeys(req.peers)]
        try:
            b = benchmark(own, peers, tax)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        return b, find_overlaps(own, tax)

    @app.post("/api/benchmark")
    def run_benchmark(req: BenchmarkRequest):
        b, overlaps = run(req)
        out = to_dict(b, overlaps)
        out["programme"]["id"] = req.own
        for peer, pid in zip(out["peers"], dict.fromkeys(req.peers)):
            peer["id"] = pid
        return out

    @app.post("/api/benchmark/report")
    def benchmark_report(req: BenchmarkRequest):
        b, overlaps = run(req)
        return Response(render_html(b, overlaps), media_type="text/html; charset=utf-8",
                        headers=_attachment(f"{b.own.institution} benchmark.html"))

    if FRONTEND.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


def seed(store: Store) -> int:
    """Load the fictional sample programmes into an empty library."""
    samples = Path(__file__).resolve().parents[2] / "samples"
    files = [samples / "riverside.json", *sorted((samples / "peers").glob("*.json"))]
    for f in files:
        store.add(Programme.model_validate(json.loads(f.read_text(encoding="utf-8"))))
    return len(files)
