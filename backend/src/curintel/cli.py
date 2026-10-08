"""Command line: `python -m curintel <command>`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from . import __version__
from .analysis import benchmark, profile, unmapped_lines
from .importers import ImportError_, from_acaddoc, write_template
from .overlap import find_overlaps
from .report import render_html, to_dict
from .schema import load_programme, save_programme
from .taxonomy import Taxonomy, TaxonomyError

PROGRAMME_SUFFIXES = (".json", ".xlsx")


def _taxonomy(arg: str | None) -> Taxonomy:
    return Taxonomy.load(arg) if arg else Taxonomy.builtin()


def _programme_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(sorted(f for f in p.iterdir()
                                if f.suffix.lower() in PROGRAMME_SUFFIXES and not f.name.startswith("~$")))
        else:
            files.append(p)
    return files


def cmd_report(args) -> None:
    tax = _taxonomy(args.taxonomy)
    own = load_programme(args.programme)
    peers = [load_programme(f) for f in _programme_files(args.peers)]
    b = benchmark(own, peers, tax)
    overlaps = find_overlaps(own, tax)
    out = Path(args.output)
    out.write_text(render_html(b, overlaps), encoding="utf-8")
    print(f"Report written to {out}")
    if args.json:
        Path(args.json).write_text(json.dumps(to_dict(b, overlaps), indent=2), encoding="utf-8")
        print(f"Data written to {args.json}")
    gaps = b.by_status("gap")
    print(f"Alignment with {len(peers)} peers: {b.alignment:.0f}%" if b.alignment is not None
          else f"No skill is shared by half of the {len(peers)} peers.")
    for r in gaps:
        print(f"  [{r.priority:<6}] {r.name}: {r.peer_share:.0%} of peers, {r.own.level} here")


def cmd_check(args) -> None:
    """Show what the taxonomy finds in each course, to review a programme file."""
    tax = _taxonomy(args.taxonomy)
    prog = load_programme(args.programme)
    prof = profile(prog, tax)
    print(f"{prog.institution} - {prog.name}: {len(prog.courses)} courses, {prog.total_credits:g} credits")
    for course in prog.courses:
        found = sorted({tax.skills[s].name for s, cov in prof.items()
                        for e in cov.evidence if e.course_code == course.code})
        print(f"  {course.code:<8} {course.title}")
        print(f"           {', '.join(found) if found else '(no skills recognised)'}")
    missing = unmapped_lines(prog, tax)
    if missing:
        print("\nTopic lines with no recognised skill (add terms to the taxonomy if they matter):")
        for code, line in missing:
            print(f"  {code}: {line}")


def cmd_import_acaddoc(args) -> None:
    prog = from_acaddoc([Path(p) for p in args.paths], args.institution, args.name, args.only)
    save_programme(prog, args.output)
    print(f"{len(prog.courses)} courses written to {args.output}")


def cmd_template(args) -> None:
    write_template(args.output)
    print(f"Blank programme workbook written to {args.output}")


def cmd_serve(args) -> None:
    import uvicorn

    from .api import create_app, seed
    from .store import DEFAULT_DB, Store

    store = Store(args.db or DEFAULT_DB)
    if args.seed and store.is_empty():
        print(f"Loaded {seed(store)} sample programmes")
    print(f"Curriculum Intelligence on http://{args.host}:{args.port}  (library: {store.path})")
    uvicorn.run(create_app(store, _taxonomy(args.taxonomy)), host=args.host, port=args.port,
                log_level="warning")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="curintel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"curintel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("report", help="benchmark a programme against peers and write an HTML report")
    p.add_argument("programme", help="the programme under review (.json or .xlsx)")
    p.add_argument("peers", nargs="+", help="peer programme files, or folders of them")
    p.add_argument("-o", "--output", default="benchmark-report.html")
    p.add_argument("--json", help="also write the findings as JSON to this file")
    p.add_argument("-t", "--taxonomy", help="taxonomy YAML (default: built-in mathematics)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("check", help="list the skills found in each course of a programme")
    p.add_argument("programme")
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("import-acaddoc", help="build a programme file from AcadDoc course JSON files")
    p.add_argument("paths", nargs="+", help="AcadDoc course .json files or folders")
    p.add_argument("--institution", required=True)
    p.add_argument("--name", required=True, help='programme name, e.g. "B.Sc. Mathematics"')
    p.add_argument("--only", help="keep only courses offered to this programme code")
    p.add_argument("-o", "--output", required=True)
    p.set_defaults(func=cmd_import_acaddoc)

    p = sub.add_parser("template", help="write a blank Excel workbook for entering a programme")
    p.add_argument("-o", "--output", default="programme-template.xlsx")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("serve", help="run the web interface")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1", help="no sign-in: keep 127.0.0.1 unless the network is trusted")
    p.add_argument("--db", help="library database file (default: backend/curintel.db)")
    p.add_argument("--seed", action="store_true", help="load the sample programmes into an empty library")
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ImportError_, TaxonomyError, ValueError, OSError) as exc:
        # ValidationError is a ValueError; show the first problem plainly.
        if isinstance(exc, ValidationError):
            err = exc.errors()[0]
            exc = f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
