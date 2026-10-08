# Curriculum Intelligence

Benchmark a programme's curriculum against peer programmes and find out, with
evidence, where it is behind, where it stands out, and which of its own
courses repeat each other.

Give it your programme and 5–10 peer programmes. It reports:

- **Priority gaps.** Skills that at least half of the peers cover and you
  don't, for example *"Python is covered by 75% of benchmarked programmes
  (6 of 8) but is not found in this curriculum"*, with the peer courses that
  cover it.
- **Watch list.** Skills that 30–49% of peers have picked up.
- **Distinctive strengths.** Skills you cover that few peers even mention.
- **Course overlap.** Pairs of your own courses whose topic lists largely
  repeat each other, with the shared phrases.
- **Alignment by area**, programme structure (courses, credits), and a full
  coverage matrix.

**[See the sample report](https://abhignau-del.github.io/curriculum-intelligence/sample-report.html)**
(fictional data; source in [`docs/sample-report.html`](docs/sample-report.html)).

## No AI, by design

Skills are found by a curated **taxonomy**: each skill lists the syllabus
phrases that count as evidence for it (`numerical methods` ← "Newton-Raphson",
"Simpson's rule", "Runge-Kutta", …). Matching ignores case and punctuation,
and the longest phrase wins: "partial differential equations" counts for
PDEs, not ODEs. Every mark in a report points back to the syllabus line that
produced it, so a committee can check any finding and argue with it.

Coverage levels for a skill in a programme:

| Level | Rule |
|---|---|
| ✓ covered | a course title names it, or two or more syllabus lines do |
| △ mentioned once | exactly one syllabus line |
| · not found | no evidence |

Course overlap compares each pair of courses by the weighted vocabulary of
their titles and topics (TF‑IDF cosine). Pairs at 40% or more are flagged,
60% or more as High. Theory–lab pairs are labelled as expected.

These thresholds were tuned on the fictional samples. Expect to adjust them
on real syllabi.

## Getting started

Requires Python 3.11+ and, for the web interface, Node.js 20+.

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m curintel report samples/riverside.json samples/peers -o report.html
```

### Web interface

```bash
cd frontend
npm install
npm run build
cd ../backend
python -m curintel serve --seed     # then open http://127.0.0.1:8000
```

`--seed` loads the sample programmes into an empty library. The library is
kept in `backend/curintel.db` (`--db` to use another file).

- **Programmes**: upload `.xlsx` (from the template) or `.json` programmes, or
  import AcadDoc course files; open one to see the skills found in each course
  and the syllabus lines nothing matched.
- **Benchmark**: pick the programme under review and tick its peers; the
  results update as you change the selection. Click any mark in the coverage
  matrix to see the syllabus lines behind it, with the matched phrase
  highlighted. Download the HTML report or the JSON data.

There is no sign-in: it is meant to run on your own computer and listens on
127.0.0.1 only. Don't expose it on a network unless everyone who can reach it
may change the library.

For development, run `npm run dev` in `frontend/` (port 5173, proxies `/api`
to the server on port 8000).

### Commands

| Command | What it does |
|---|---|
| `curintel report OWN PEERS... [-o file.html] [--json file.json] [-t taxonomy.yaml]` | the benchmark report; PEERS can be files or folders |
| `curintel check PROGRAMME` | the skills found in each course, plus syllabus lines with no recognised skill (to spot missing taxonomy terms) |
| `curintel template -o peer.xlsx` | a blank Excel workbook for typing in a peer's syllabus |
| `curintel import-acaddoc FILES... --institution I --name N -o prog.json [--only CSE]` | turn [AcadDoc](https://github.com/abhignau-del/acaddoc) course files into a programme |
| `curintel serve [--seed] [--port 8000] [--db FILE]` | run the web interface |

### Programme files

A programme is JSON (see `backend/samples/`) or an Excel workbook made from
`curintel template`: one row per course with code, title, semester, credits,
category, topics (one per line in the cell, or separated by `;`) and
optional outcomes.

### Taxonomy

The built-in taxonomy is `backend/src/curintel/taxonomies/mathematics.yaml`
(undergraduate mathematics, 48 skills in 6 areas). Copy and extend it, or
write one for another discipline, and pass it with `-t`.

## Sample data

`backend/samples/` holds one programme under review (*Riverside College of
Science*) and eight peers. **All institutions are fictional**, and the
syllabi are typical of Indian B.Sc. Mathematics programmes but copied from
no real one. `backend/tools/make_samples.py` regenerates them. Keep real
institutional data in the git-ignored `private-data/` folder.

## Roadmap

1. **Benchmark, gaps, overlap** (v0.1).
2. **Web interface**: programmes library, interactive benchmark with evidence.
3. CO/PO and outcome mapping.
4. Regulatory alignment: NEP/UGC requirements as machine-readable rules.
5. Industry skill demand.
6. More discipline taxonomies.

## Licence

MIT
