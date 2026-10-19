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
| ● a core course on it | a compulsory course is on the skill (see below) |
| ✓ covered | a course title names it, or two or more syllabus lines do |
| △ mentioned once | exactly one syllabus line |
| · not found | no evidence |

**Core and electives.** A course whose category names it an option
(elective, optional, choice, basket, DSE, GE) is an elective; anything else
counts as core. Each programme is analysed twice, all courses and core courses
only, so every covered skill has a basis: *core* (the compulsory courses alone
cover it) or *elective only* (marked ○ in the matrix). Gaps are judged on
everything a programme offers, and each finding states the split, e.g.
"covered by 83% of programmes (5 of 6: in the core of 4, only as an elective
in 1)". PDF profiles set categories with `category` / `categories` rules.

**Courses on a skill.** Covering a skill can mean a whole course on it, or a
few examples inside a course about something else (growth-and-decay models
in a differential-equations course are not a modelling course). A course
counts as *on* a skill when its title names the skill, or when the skill
appears in at least half of its topic lines (and in at least three). Each
gap then says how many of the covering peers have such a course, and whether
it is core: *"5 of them have a course on it (1 core, 4 elective)"*. A core
course on a skill is marked ● in the matrix. Like the core/elective split,
this is reported alongside the gap rules and does not change them.

Course overlap compares each pair of courses by the weighted vocabulary of
their titles and topics (TF‑IDF cosine). Pairs at 40% or more are flagged,
60% or more as High. Theory–lab pairs are labelled as expected.

These thresholds were tuned on the fictional samples. Expect to adjust them
on real syllabi.

Skills are found in course titles and topic lines only. Course outcomes are
not counted as evidence of a skill: they often look ahead ("a foundation for
machine learning"), and not every syllabus states them.

### Course outcomes

`curintel outcomes PROGRAMME` reads each course outcome's level in the revised
Bloom's taxonomy from the verbs that open it: *Define* is Remember, *Solve* is
Apply, *Prove* is Evaluate, *Design* is Create. With several opening verbs
("Identify and classify") the highest counts. It reports:

- outcomes per level by year of study, and the share of **higher-order**
  outcomes (Analyse, Evaluate, Create), which usually rises through a programme;
- **vague** outcomes, which open with a verb that is hard to assess
  (*understand*, *learn*, *appreciate*);
- outcomes with **no action verb**, outcomes **stated for more than one
  course**, and courses that state none.

The benchmark report adds the same section when the programme under review
states its outcomes. The verb list is
[`taxonomies/bloom.yaml`](backend/src/curintel/taxonomies/bloom.yaml); pass your
own with `--verbs`. PDF profiles read outcomes with `outcomes_start` and
`outcomes_end`.

### CO–PO mapping

`curintel copo PROGRAMME` maps course outcomes (COs) to programme outcomes
(POs) and builds the course articulation matrix that NAAC and NBA ask for, on
their 1–3 scale (1 slight, 2 moderate, 3 substantial).

- **Which POs.** The programme's own POs and PSOs when it states them (JSON
  `programme_outcomes`, or the template's *Programme outcomes* sheet);
  otherwise the nine graduate attributes of UGC's LOCF for Mathematics
  (`--framework ugc-locf-mathematics`, built in). Any framework can be written
  in YAML ([`frameworks/`](backend/src/curintel/frameworks)).
- **How a CO serves a PO.** Each PO has indicators: opening verbs, skills (or
  whole skill areas) and words. A CO serves a PO when one matches; it maps
  more strongly when indicators of two kinds match and when its Bloom level
  reaches the level the PO calls for. A PO written in plain text gets its
  indicators from its own wording, and these are held to more: a generic verb
  (*use*, *apply*) does not make a link on its own, and common words
  (*theory*, *methods*, or any word in over a fifth of the programme's
  outcomes) are ignored. Every link lists the indicators behind it.
- **What it shows.** Courses serving each PO and their mean strength, the POs
  no course outcome serves, and the matrix, with the reasons for every cell.

The benchmark report and web app add this section when the programme under
review states course outcomes.

### Outcome attainment

`curintel attainment PROGRAMME RESULTS.xlsx` works out how far a batch attained
each course outcome and, through the CO–PO mapping, each programme outcome.

**[See a sample attainment report](https://abhignau-del.github.io/curriculum-intelligence/sample-attainment.html)**
(fictional batch).

1. `curintel attainment-template PROGRAMME -o results.xlsx --batch 2023-26`
   writes a workbook with one row per course outcome and kind of assessment
   (internal, external, exit survey).
2. Fill in, for each row, how many students were assessed on the outcome and
   how many reached the target mark. **Counts only**: no names or marks.
3. Run `curintel attainment` for the HTML report and JSON.

A **policy** file sets how counts become levels, and the report prints the
policy it used. The defaults follow common practice, not a regulation, so set
your institution's own (`--policy policy.yaml`):

```yaml
thresholds: [[0.7, 3], [0.6, 2], [0.5, 1]]   # share of students reaching the target -> level
weights: {internal: 0.3, external: 0.7}     # direct attainment
direct_share: 0.8                           # overall = direct 80 : exit survey 20
target_level: 2                             # an outcome is attained at this level
```

In the web app, the programme screen has an **Outcome attainment** panel: download
the entry sheet, upload the filled-in results, and adjust the policy in a small
form (remembered in your browser; *Reset to defaults* restores the values above).

A programme outcome's attainment is the attainment of the course outcomes that
serve it, weighted by their mapping strength.

### NAAC 2.6.1 evidence pack

`curintel evidence PROGRAMME [--attainment RESULTS] -o evidence.docx` (or the
*Download NAAC 2.6.1 evidence* button in the web app's attainment panel) writes
an editable Word document for NAAC's university-manual metric 2.6.1 (learning
outcomes stated, integrated into assessment, made public, and their attainment
evaluated):

1. programme outcomes, or the framework the course outcomes were mapped to;
2. every course's outcomes with their Bloom levels;
3. the CO–PO articulation matrix (landscape page) and how it was built;
4. attainment for the batch, when results are given;
5. a table of actions for outcomes below target, for the department to complete.

It opens with **Before submission**: what the data shows still needs doing
(no programme outcomes of its own, vague or copied outcomes, courses without
outcomes, programme outcomes nothing serves, outcomes not assessed, where the
outcomes are published). It is a draft to check and complete, not a finished
submission.

**[Download a sample evidence pack](docs/sample-evidence-2.6.1.docx)** (fictional college and batch). When an outcome lacks a kind of
assessment, the other weights are rescaled and the report says so.

### Regulatory checklist

`curintel regcheck PROGRAMME` checks a programme against the rules of a
framework. The built-in rules are UGC's *Curriculum and Credit Framework for
Undergraduate Programmes* (2022): total credits (120 for 3 years, 160 for 4),
the Table 2 minimums per category (Major, Minor, Multidisciplinary, AEC, SEC,
value-added, internship, research), and at least half of all credits from the
major. Each rule quotes the requirement and its page, and each result reads
*met*, *partly met*, *not met* or *not checked*. Add `--rules ugc-ccfup-2022`
to `report` to put the checklist in the benchmark report.

- **Credit rules read a credit scheme**, not the course list. A course list
  holds one department's courses and every elective alternative, so a
  programme records the credits a student earns per category and semester as
  its `scheme` (in the JSON, or in a PDF profile). The framework maps each
  university's own labels (DSC, MDC, IKS, …) onto its categories, and names any
  label it cannot place. Without a scheme, credit rules are *not checked*.
- **The degree decides which minimums apply.** Set it on the programme
  (`"degree": "3-year"`) or with `--degree`. Otherwise the checker goes by the
  number of semesters and says so. A 3-year check leaves out semesters 7 and 8,
  and a 4-year check names any semester the scheme lacks.
- **Course rules** ("a core course on probability") use the same course
  detection as the benchmark, so a model curriculum's core papers can be written
  as rules too. Mark such rules `level: advisory`.

Write your own rules file in YAML (format at the top of
[`regulatory.py`](backend/src/curintel/regulatory.py)) and pass it with
`--rules my-rules.yaml`.

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
  highlighted. Tick a regulatory framework to add its checklist (and pick the
  degree to check against). Download the HTML report or the JSON data.

There is no sign-in: it is meant to run on your own computer and listens on
127.0.0.1 only. Don't expose it on a network unless everyone who can reach it
may change the library.

For development, run `npm run dev` in `frontend/` (port 5173, proxies `/api`
to the server on port 8000).

### Commands

| Command | What it does |
|---|---|
| `curintel report OWN PEERS... [-o file.html] [--json file.json] [-t taxonomy.yaml] [-r RULES]` | the benchmark report; PEERS can be files or folders |
| `curintel regcheck PROGRAMME [-r RULES] [--degree 3-year]` | the regulatory checklist (default rules: `ugc-ccfup-2022`) |
| `curintel outcomes PROGRAMME [-o file.html] [--json file.json]` | Bloom's levels of the course outcomes, with checks |
| `curintel copo PROGRAMME [--framework NAME\|FILE\|own] [-o file.html] [--json file.json]` | CO–PO mapping and articulation matrix |
| `curintel attainment-template PROGRAMME [-o results.xlsx] [--batch B]` | a workbook for a batch's results per course outcome |
| `curintel attainment PROGRAMME RESULTS [--policy P] [-o file.html] [--json file.json]` | CO and PO attainment |
| `curintel evidence PROGRAMME [--attainment RESULTS] [-o file.docx]` | Word evidence pack for NAAC metric 2.6.1 |
| `curintel check PROGRAMME` | the skills found in each course, plus syllabus lines with no recognised skill (to spot missing taxonomy terms) |
| `curintel template -o peer.xlsx` | a blank Excel workbook for typing in a peer's syllabus |
| `curintel import-acaddoc FILES... --institution I --name N -o prog.json [--only CSE]` | turn [AcadDoc](https://github.com/abhignau-del/acaddoc) course files into a programme |
| `curintel extract-pdf PROFILE.yaml -o draft.xlsx` | draft a programme from syllabus PDFs (see below); review the draft before benchmarking |
| `curintel serve [--seed] [--port 8000] [--db FILE]` | run the web interface |

### Programme files

A programme is JSON (see `backend/samples/`) or an Excel workbook made from
`curintel template`: one row per course with code, title, semester, credits,
category, topics (one per line in the cell, or separated by `;`) and
optional outcomes. For the regulatory checklist, fill in the optional
*Credit scheme* sheet (semester, category, credits) and the *Degree* field.

### Importing syllabus PDFs

Every university lays out its syllabus differently, so there is no single
parser. Instead, a short **profile** (YAML) describes one document: where each
course starts, where its topic content begins and ends, and which courses
belong to the programme. `extract-pdf` turns the PDF into a draft, writes it to
the Excel template (or JSON), and lists every course it found or left out so
you can check it against the document. Install the PDF support first:
`pip install -e ".[pdf]"`.

```yaml
institution: Example University
name: B.Sc. (Hons.) Mathematics
source: https://example.edu/syllabus.pdf
files:
  - {path: syllabus.pdf, pages: "11-63"}
course_start: '^(?P<code>MA[CES]\d{3}):\s*(?P<title>.+)$'   # e.g. "MAC151: Real Analysis-1"
content_start: 'Course Contents:'
content_end: '(?m)^Books Recommended'
include: '^MA[CES]'          # leave out courses meant for other departments
```

Profiles can also merge parts of one course, number elective alternatives that
share a label, correct typos and garbled titles, drop page furniture, and add
courses typed in by hand (for scanned pages), each with a note saying where it
came from. The full list of options is at the top of
[`pdfimport.py`](backend/src/curintel/pdfimport.py).

Scanned PDFs (images without a text layer) are not read; type those courses in
by hand or use the Excel template.

### Taxonomy

The built-in taxonomy is `backend/src/curintel/taxonomies/mathematics.yaml`
(undergraduate mathematics, 48 skills in 6 areas, extended after a survey of real syllabi). Copy and extend it, or
write one for another discipline, and pass it with `-t`.

## Sample data

`backend/samples/` holds one programme under review (*Riverside College of
Science*) and eight peers. **All institutions are fictional**, and the
syllabi are typical of Indian B.Sc. Mathematics programmes but copied from
no real one. `backend/tools/make_samples.py` regenerates them. Keep real
institutional data in the git-ignored `private-data/` folder.

## Roadmap

1. **Benchmark, gaps, overlap** (v0.1).
2. **Web interface**: programmes library, interactive benchmark with evidence (v0.2).
3. **PDF import** with per-document profiles, tested on real syllabi (v0.3).
4. **Core vs elective coverage** (v0.4).
5. **Courses on a skill**: a whole course vs a few lines in other courses (v0.5).
6. **Regulatory checklist**: UGC credit framework rules, credit schemes, course rules (v0.6).
7. **Course outcomes**: Bloom's levels and checks (v0.7); CO–PO mapping (v0.8); attainment (v0.9); NAAC 2.6.1 evidence pack (v0.10).
8. Industry skill demand.
9. More discipline taxonomies.

## Licence

MIT
