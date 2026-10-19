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
from .pdfimport import ProfileError
from .attainment import AttainmentError, Policy, compute, read_data, write_template as write_attainment_template
from .mapping import choose_framework, map_outcomes
from .outcomes import Bloom, analyse_outcomes
from .overlap import find_overlaps
from .regulatory import Rules, check
from .report import attainment_dict, copo_dict, outcomes_dict, render_html, render_outcomes_html, to_dict
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
    checklists = [check(own, Rules.resolve(r), tax, args.degree) for r in args.rules or []]
    outcomes = copo = None
    if any(c.outcomes for c in own.courses):
        outcomes = analyse_outcomes(own)
        copo = map_outcomes(own, choose_framework(args.framework, own, tax), tax)
    out = Path(args.output)
    out.write_text(render_html(b, overlaps, checklists, outcomes, copo), encoding="utf-8")
    print(f"Report written to {out}")
    if args.json:
        Path(args.json).write_text(json.dumps(to_dict(b, overlaps, checklists, outcomes, copo), indent=2),
                                   encoding="utf-8")
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


STATUS_WORD = {"met": "met", "partly": "partly", "not_met": "NOT MET", "not_checked": "not checked"}


def cmd_regcheck(args) -> None:
    """Check one programme against regulatory rules, without peers."""
    tax = _taxonomy(args.taxonomy)
    prog = load_programme(args.programme)
    for name in args.rules or ["ugc-ccfup-2022"]:
        cl = check(prog, Rules.resolve(name), tax, args.degree)
        print(f"{cl.rules.name}")
        if cl.variant:
            print(f"  as a {cl.variant.name} ({cl.variant_basis})")
        if any(r.status == "not_checked" for r in cl.results):
            print("  no credit scheme recorded: credit rules not checked")
        for r in cl.results:
            page = f" (p. {r.rule.page})" if r.rule.page else ""
            adv = " [advisory]" if r.rule.level == "advisory" else ""
            print(f"  [{STATUS_WORD[r.status]:<11}] {r.rule.text}{page}{adv}")
            print(f"                here: {r.found} | expected: {r.expected}")
        if cl.missing_semesters:
            print(f"  the credit scheme has no credits for semester(s) {', '.join(map(str, cl.missing_semesters))}: "
                  "credit totals are incomplete")
        for sem, credits in cl.beyond.items():
            print(f"  not counted for this degree: semester {sem} ({credits:g} credits)")
        for label, credits in cl.unmapped.items():
            print(f"  scheme label not matched to a category: {label} ({credits:g} credits)")
        print()


def cmd_outcomes(args) -> None:
    """Bloom's levels of a programme's course outcomes, and checks on them."""
    prog = load_programme(args.programme)
    rep = analyse_outcomes(prog, Bloom.load(args.verbs) if args.verbs else None)
    names = {lv.level: lv.name for lv in rep.bloom.levels}
    n = len(rep.results)
    print(f"{prog.institution} - {prog.name}: {n} outcomes in {rep.courses_with_outcomes} of {len(prog.courses)} courses")
    if n:
        share = rep.higher_order_share(rep.results)
        print(f"  higher-order (Analyse and above): {'-' if share is None else f'{share:.0%}'}; "
              f"vague: {len(rep.flagged('vague'))}; no action verb: {len(rep.flagged('no_verb'))}; "
              f"stated for more than one course: {len(rep.duplicates)}")
        for year, rs in rep.by_year():
            counts = rep.counts(rs)
            levels = ", ".join(f"{names[lv]} {c}" for lv, c in counts.items() if lv is not None and c)
            hs = rep.higher_order_share(rs)
            print(f"  {year or 'semester not recorded'}: {len(rs)} outcomes ({levels}"
                  f"{f', no level {counts[None]}' if counts[None] else ''}); "
                  f"higher-order {'-' if hs is None else f'{hs:.0%}'}")
    if rep.without_outcomes:
        print(f"  courses with no outcomes: {', '.join(c for c, _ in rep.without_outcomes)}")
    if args.output:
        Path(args.output).write_text(render_outcomes_html(rep), encoding="utf-8")
        print(f"Report written to {args.output}")
    if args.json:
        Path(args.json).write_text(json.dumps(outcomes_dict(rep), indent=2), encoding="utf-8")
        print(f"Data written to {args.json}")


def cmd_copo(args) -> None:
    """Map course outcomes to programme outcomes."""
    tax = _taxonomy(args.taxonomy)
    prog = load_programme(args.programme)
    m = map_outcomes(prog, choose_framework(args.framework, prog, tax), tax)
    print(f"{prog.institution} - {prog.name}: {len(m.cos)} course outcomes against {m.framework.name}")
    for po, n, mean in m.po_summary():
        print(f"  {po.code:<5} {po.name[:44]:<44} {n:>3} courses  mean {'-' if mean is None else f'{mean:.1f}'}")
    if m.unmapped:
        print(f"  {len(m.unmapped)} course outcomes serve no PO")
    if args.output:
        Path(args.output).write_text(render_outcomes_html(m.outcomes, m), encoding="utf-8")
        print(f"Report written to {args.output}")
    if args.json:
        Path(args.json).write_text(json.dumps(copo_dict(m), indent=2), encoding="utf-8")
        print(f"Data written to {args.json}")


def cmd_attainment_template(args) -> None:
    prog = load_programme(args.programme)
    if not any(c.outcomes for c in prog.courses):
        raise AttainmentError("the programme states no course outcomes to record attainment for")
    write_attainment_template(args.output, prog, args.batch or "")
    n = sum(len(c.outcomes) for c in prog.courses)
    print(f"Attainment workbook for {n} course outcomes written to {args.output}")


def cmd_attainment(args) -> None:
    """CO and PO attainment for a batch, from aggregated assessment results."""
    tax = _taxonomy(args.taxonomy)
    prog = load_programme(args.programme)
    data = read_data(args.data)
    policy = Policy.load(args.policy) if args.policy else Policy()
    mapping = map_outcomes(prog, choose_framework(args.framework, prog, tax), tax)
    rep = compute(mapping, data, policy)
    print(f"{prog.institution} - {prog.name}{', batch ' + data.batch if data.batch else ''}")
    print(f"  {len(rep.attained())} of {len(rep.assessed)} assessed course outcomes reached level "
          f"{policy.target_level:g}" + (f"; {len(rep.no_data)} not assessed" if rep.no_data else ""))
    for code, name, value, n in rep.po_values:
        shown = "no data" if value is None else f"{value:.2f}" + ("" if value >= policy.target_level - 1e-9 else "  below target")
        print(f"  {code:<5} {name[:44]:<44} {shown}")
    if rep.unknown:
        print(f"  left out (no such course outcome): {', '.join(rep.unknown)}")
    if args.output:
        Path(args.output).write_text(render_outcomes_html(mapping.outcomes, mapping, rep), encoding="utf-8")
        print(f"Report written to {args.output}")
    if args.json:
        Path(args.json).write_text(json.dumps(attainment_dict(rep), indent=2), encoding="utf-8")
        print(f"Data written to {args.json}")


def cmd_import_acaddoc(args) -> None:
    prog = from_acaddoc([Path(p) for p in args.paths], args.institution, args.name, args.only)
    save_programme(prog, args.output)
    print(f"{len(prog.courses)} courses written to {args.output}")


def cmd_extract_pdf(args) -> None:
    from .importers import write_template
    from .pdfimport import extract

    tax = _taxonomy(args.taxonomy)
    words = {w for s in tax.skills.values() for t in s.terms for w in t.split() if len(w) > 2}
    draft = extract(args.profile, extra_vocab=words)
    out = Path(args.output)
    if out.suffix.lower() == ".xlsx":
        write_template(out, draft.programme)
    else:
        save_programme(draft.programme, out)
    print(f"{len(draft.courses)} courses written to {out} - review before benchmarking")
    for d in draft.courses:
        flag = f"  ! {'; '.join(d.warnings)}" if d.warnings else ""
        print(f"  {d.course.code:<14} {d.course.title[:50]:<50} {len(d.course.topics):>3} topics  "
              f"({d.file} p{d.page}){flag}")
    for code, where in draft.merged:
        print(f"  (merged another part of {code} from {where})")
    if draft.excluded:
        print(f"\nLeft out ({len(draft.excluded)}):")
        for code, title, why in draft.excluded:
            print(f"  {code:<14} {title[:50]:<50} {why}")


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
    # Windows consoles default to a code page that cannot show every syllabus character.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="curintel", description=__doc__)
    parser.add_argument("--version", action="version", version=f"curintel {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("report", help="benchmark a programme against peers and write an HTML report")
    p.add_argument("programme", help="the programme under review (.json or .xlsx)")
    p.add_argument("peers", nargs="+", help="peer programme files, or folders of them")
    p.add_argument("-o", "--output", default="benchmark-report.html")
    p.add_argument("--json", help="also write the findings as JSON to this file")
    p.add_argument("-t", "--taxonomy", help="taxonomy YAML (default: built-in mathematics)")
    p.add_argument("-r", "--rules", action="append",
                   help="also check the programme against these rules: a built-in name such as "
                        "ugc-ccfup-2022, or a rules YAML file (repeatable)")
    p.add_argument("--degree", help='check as this degree, e.g. "3-year" (default: the one the programme records)')
    p.add_argument("--framework", help='programme outcomes for CO-PO mapping: a built-in name, a YAML file, or "own" '
                                       "(default: the programme's own, else ugc-locf-mathematics)")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("regcheck", help="check a programme against regulatory rules (default: ugc-ccfup-2022)")
    p.add_argument("programme")
    p.add_argument("-r", "--rules", action="append", help="built-in rules name or rules YAML file (repeatable)")
    p.add_argument("--degree", help='check as this degree, e.g. "3-year" (default: the one the programme records)')
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_regcheck)

    p = sub.add_parser("outcomes", help="Bloom's levels of a programme's course outcomes, with checks")
    p.add_argument("programme")
    p.add_argument("-o", "--output", help="write an HTML report to this file")
    p.add_argument("--json", help="write the analysis as JSON to this file")
    p.add_argument("--verbs", help="a Bloom verb list YAML (default: the built-in list)")
    p.set_defaults(func=cmd_outcomes)

    p = sub.add_parser("copo", help="map course outcomes to programme outcomes (CO-PO matrix)")
    p.add_argument("programme")
    p.add_argument("--framework", help='a built-in name, a framework YAML, or "own" '
                                       "(default: the programme's own outcomes, else ugc-locf-mathematics)")
    p.add_argument("-o", "--output", help="write an HTML report (outcomes and CO-PO) to this file")
    p.add_argument("--json", help="write the mapping as JSON to this file")
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_copo)

    p = sub.add_parser("attainment-template", help="write a workbook for entering a batch's results per course outcome")
    p.add_argument("programme")
    p.add_argument("-o", "--output", default="attainment.xlsx")
    p.add_argument("--batch", help='e.g. "2023-26"')
    p.set_defaults(func=cmd_attainment_template)

    p = sub.add_parser("attainment", help="CO and PO attainment for a batch, from aggregated results")
    p.add_argument("programme")
    p.add_argument("data", help="the filled-in attainment workbook (.xlsx) or JSON")
    p.add_argument("--policy", help="attainment policy YAML: thresholds, weights, target (default: common practice)")
    p.add_argument("--framework", help='programme outcomes: a built-in name, a YAML file, or "own"')
    p.add_argument("-o", "--output", help="write an HTML report (outcomes, CO-PO, attainment) to this file")
    p.add_argument("--json", help="write the attainment as JSON to this file")
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_attainment)

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

    p = sub.add_parser("extract-pdf", help="draft a programme from syllabus PDFs using a profile (review it after)")
    p.add_argument("profile", help="YAML profile describing the PDF layout (see pdfimport.py)")
    p.add_argument("-o", "--output", required=True, help=".xlsx (for review in Excel) or .json")
    p.add_argument("-t", "--taxonomy")
    p.set_defaults(func=cmd_extract_pdf)

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
    except (ImportError_, ProfileError, TaxonomyError, ValueError, OSError) as exc:
        # ValidationError is a ValueError; show the first problem plainly.
        if isinstance(exc, ValidationError):
            err = exc.errors()[0]
            exc = f"{'.'.join(map(str, err['loc']))}: {err['msg']}"
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
