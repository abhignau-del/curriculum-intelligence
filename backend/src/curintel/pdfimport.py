"""Draft a programme from syllabus PDFs, guided by a small per-document profile.

Universities lay syllabi out in very different ways, so there is no single
parser. A profile (YAML) says where each course starts, where its topic content
begins and ends, and which courses belong to the programme. The result is a
*draft*: write it to the Excel template, review it, then benchmark it.

    institution: Example University
    name: B.Sc. (Hons.) Mathematics
    source: https://example.edu/syllabus.pdf
    files:
      - {path: syllabus.pdf, pages: "3-60", semester: ""}
    course_start: '^(?P<code>MAT\\d{3}):\\s*(?P<title>.+)$'   # one line, per course
    content_start: 'Course Contents?:'
    content_end: 'Books Recommended|References'
    include: ''            # optional: keep only courses whose "code title" matches
    exclude: ''            # optional: drop courses whose "code title" matches

Optional keys:
  header_before        regex for a line just above the start line that belongs to the header
  header_lines_before  a fixed number of lines above the start line that belong to the
                       header (e.g. a title printed above the course code)
  title                regex with a `title` group, searched in the header
  title_strip          regexes removed from the header before reading the title
  title_end            where the title stops in the header
  credits, semester    regexes with a `credits` / `semester` group
  content_strip        extra regexes removed from topic text
  skip_lines           regexes for page furniture to drop (running headers, page numbers)
  split                an extra regex that separates topics (for syllabi that join them
                       with bare hyphens)
  aliases              code -> code, for typos in the source
  titles               code -> title, to correct a garbled title
  kind_codes           when course_start has `kind` and `num` groups instead of `code`:
                       kind -> prefix (CORE: DSC makes "DSC-13")
  duplicates           merge (default) or number - see below
  category             category given to every course (default: none, i.e. core)
  categories           rules [{match: regex on "code title", category: ...}], first match
                       wins; a category naming elective/optional/DSE/GE marks an elective
  extra_courses        courses typed in by hand (e.g. from scanned pages); give each a
                       `note` saying where it came from. A profile may consist of these
                       alone when the source has no usable syllabus pages.

Parts of one course that share a code (Part-1, Part-2) are merged; with
`duplicates: number` they are kept as separate courses (CODE, CODE/2, ...), for
documents that list elective alternatives under one label.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .schema import Course, Programme

DEFAULT_CONTENT_STRIP = [
    r"\(\s*\d+\s*(?:hours?|hrs?|lectures?|classes|L|periods)\s*\)",
    r"\b(?:UNIT|Unit|MODULE|Module)\s*[-–:]?\s*(?:[IVX]+|\d+)\b\s*[:.\-–]?",
    r"\b\d{1,3}\s?%",
    r"Weightage\*?|\(%\)|Description",
    r"\b(?:UNIT|Unit)\b",
    r"\b\d+\s*Marks\b",
]
SPLIT = re.compile(r"[,;:.•●▪]|\s[-–]\s|\(|\)")


class ProfileError(ValueError):
    pass


@dataclass
class DraftCourse:
    course: Course
    file: str
    page: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class Draft:
    programme: Programme
    courses: list[DraftCourse]
    excluded: list[tuple[str, str, str]]    # (code, title, reason)
    merged: list[tuple[str, str]] = field(default_factory=list)   # (code, where the extra part was)


# ----- text --------------------------------------------------------------

def read_pdf(path: Path, pages: Optional[str] = None) -> list[tuple[int, str]]:
    """(page number, text) for the selected pages; duplicate glyphs removed."""
    try:
        import pdfplumber
    except ImportError as exc:  # optional dependency
        raise ProfileError("PDF import needs pdfplumber: pip install -e \".[pdf]\"") from exc
    out = []
    with pdfplumber.open(path) as pdf:
        wanted = _page_set(pages, len(pdf.pages))
        for i, page in enumerate(pdf.pages, start=1):
            if i in wanted:
                out.append((i, page.dedupe_chars().extract_text() or ""))
    return out


def _page_set(spec: Optional[str], n: int) -> set[int]:
    if not spec:
        return set(range(1, n + 1))
    pages: set[int] = set()
    for part in str(spec).split(","):
        a, _, b = part.strip().partition("-")
        lo, hi = int(a), int(b or a)
        pages.update(range(max(1, lo), min(n, hi) + 1))
    return pages


WORD = re.compile(r"[A-Za-z]+")


def vocabulary(texts: list[str], extra: set[str] = frozenset()) -> set[str]:
    """Lower-case words seen at least twice, plus any extra words (e.g. taxonomy terms)."""
    counts = Counter(w.lower() for t in texts for w in WORD.findall(t))
    return {w for w, c in counts.items() if c >= 2 and len(w) > 2} | set(extra)


def repair_split_words(text: str, vocab: set[str]) -> str:
    """Rejoin words a PDF split with a stray space ("Gradie nt" -> "Gradient").

    Two adjacent fragments are merged when together they form a known word and
    at least one of them is not a word on its own.
    """
    def fix(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        joined = (a + b).lower()
        if joined in vocab and (a.lower() not in vocab or b.lower() not in vocab):
            return a + b
        return m.group(0)
    previous = None
    while previous != text:            # "T heor em" needs two passes
        previous = text
        text = re.sub(r"\b([A-Za-z]+) ([a-z]+)\b", fix, text)
    return text


def topics_from(text: str, strip: list[str], extra_split: str | None = None) -> list[str]:
    """Turn a block of syllabus content into short topic phrases."""
    text = re.sub(r"-\n(?=[a-z])", "", text)          # hyphenated line breaks
    # A line that starts with a list marker ("1.", "1.2", "•", "(a)") starts a new topic.
    text = re.sub(r"^\s*(?:\d{1,2}(?:\.\d{1,2})*\s*[.)]?|[•●▪◦]|\(?[a-z]\))\s+", " ; ", text, flags=re.M)
    for rx in [*DEFAULT_CONTENT_STRIP, *strip]:
        text = re.sub(rx, " ", text)
    text = re.sub(r"\s+", " ", text)
    phrases = []
    pieces = SPLIT.split(text)
    if extra_split:
        pieces = [q for piece in pieces for q in re.split(extra_split, piece)]
    for p in pieces:
        p = p.strip(" -–*&")
        if len(p) >= 3 and re.search(r"[A-Za-z]{3}", p):
            phrases.append(p)
    return list(dict.fromkeys(phrases))


# ----- profiles ----------------------------------------------------------

def _rx(profile: dict, key: str, flags: int = 0) -> Optional[re.Pattern]:
    value = profile.get(key)
    if not value:
        return None
    try:
        return re.compile(value, flags)
    except re.error as exc:
        raise ProfileError(f"profile key {key!r}: bad regular expression ({exc})") from None


def _clean_title(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip(" :-–")
    return t.title() if t.isupper() and len(t) > 4 else t


def extract(profile_path: str | Path, extra_vocab: set[str] = frozenset()) -> Draft:
    profile_path = Path(profile_path)
    try:
        prof = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ProfileError(f"{profile_path.name}: not valid YAML ({exc})") from None
    for key in ("institution", "name"):
        if not prof.get(key):
            raise ProfileError(f"{profile_path.name}: missing {key!r}")
    # A profile can be built by hand (extra_courses only) when the source has no usable syllabus pages.
    if prof.get("files") and not prof.get("course_start"):
        raise ProfileError(f"{profile_path.name}: missing 'course_start'")
    if not prof.get("files") and not prof.get("extra_courses"):
        raise ProfileError(f"{profile_path.name}: needs 'files' or 'extra_courses'")

    start = _rx(prof, "course_start", re.M)
    before = _rx(prof, "header_before")
    lines_before = int(prof.get("header_lines_before") or 0)
    duplicates = prof.get("duplicates", "merge")
    if duplicates not in ("merge", "number"):
        raise ProfileError(f"{profile_path.name}: duplicates must be merge or number")
    c_start = _rx(prof, "content_start", re.I)
    c_end = _rx(prof, "content_end", re.I)
    include = _rx(prof, "include", re.I)
    exclude = _rx(prof, "exclude", re.I)
    title_rx = _rx(prof, "title", re.S)
    title_end = _rx(prof, "title_end", re.I) or re.compile(r"Total Credits|Credits|$", re.I)
    credits_rx = _rx(prof, "credits", re.S | re.I)
    sem_rx = _rx(prof, "semester", re.S | re.I)
    title_strip = [re.compile(r, re.I) for r in prof.get("title_strip", [])]
    skip = [re.compile(r) for r in prof.get("skip_lines", [])]
    strip = list(prof.get("content_strip", []))
    extra_split = prof.get("split") or None
    aliases = {str(k): str(v) for k, v in (prof.get("aliases") or {}).items()}
    titles = {str(k): str(v) for k, v in (prof.get("titles") or {}).items()}
    kind_codes = {str(k).upper(): str(v) for k, v in (prof.get("kind_codes") or {}).items()}
    default_category = str(prof.get("category") or "")
    try:
        category_rules = [(re.compile(r["match"], re.I), str(r["category"])) for r in prof.get("categories") or []]
    except (KeyError, TypeError) as exc:
        raise ProfileError(f"{profile_path.name}: each 'categories' entry needs match and category ({exc})") from None
    except re.error as exc:
        raise ProfileError(f"{profile_path.name}: 'categories': bad regular expression ({exc})") from None

    def category_for(code: str, title: str) -> str:
        label = f"{code} {title}"
        return next((cat for rx, cat in category_rules if rx.search(label)), default_category)

    # Read every file first, so the split-word vocabulary covers the whole programme.
    files = []
    for entry in prof.get("files") or []:
        path = (profile_path.parent / entry["path"]).resolve()
        if not path.exists():
            raise ProfileError(f"{profile_path.name}: file not found: {entry['path']}")
        pages = read_pdf(path, entry.get("pages"))
        files.append((entry, path, pages))
    vocab = vocabulary([t for _, _, pages in files for _, t in pages], extra_vocab)

    drafts: list[DraftCourse] = []
    excluded: list[tuple[str, str, str]] = []
    merged: list[tuple[str, str]] = []
    by_code: dict[str, DraftCourse] = {}
    for entry, path, pages in files:
        # One list of (page, line), without page furniture.
        lines = [(n, line) for n, text in pages for line in text.splitlines()
                 if not any(rx.search(line) for rx in skip)]
        starts = [i for i, (_, line) in enumerate(lines) if start.search(line)]

        def head_of(i: int) -> int:
            """First line of the header: `lines_before` lines up, or one line matching header_before."""
            if lines_before:
                return max(0, i - lines_before)
            if before and i > 0 and before.search(lines[i - 1][1]):
                return i - 1
            return i

        heads = [head_of(i) for i in starts]
        for k, i in enumerate(starts):
            i_head = heads[k]
            # stop where the next course's header begins, not just its start line
            j = max(i + 1, heads[k + 1]) if k + 1 < len(starts) else len(lines)
            block = "\n".join(line for _, line in lines[i_head:j])
            m = start.search(lines[i][1])
            groups = m.groupdict()
            code = (groups.get("code") or "").strip()
            if not code and groups.get("num"):     # e.g. CORE + "13" -> DSC-13
                kind = (groups.get("kind") or "").strip()
                code = f"{kind_codes.get(kind.upper(), kind)}-{re.sub(r'\s+', '', groups['num'])}".strip("-")
            code = aliases.get(code, code)
            header = block[: c_start.search(block).start()] if c_start and c_start.search(block) else block[:600]

            title = (m.groupdict().get("title") or "").strip()
            if title_rx and (tm := title_rx.search(header)):
                title = tm.group("title")
            elif not title:
                h = header.replace(code, " ") if code else header
                for rx in title_strip:
                    h = rx.sub(" ", h)
                h = re.sub(r"\s+", " ", h)
                end = title_end.search(h)
                title = h[: end.start()] if end else h[:120]
            title = titles.get(code) or _clean_title(repair_split_words(title, vocab))
            label = f"{code} {title}".strip()

            if include and not include.search(label):
                excluded.append((code, title, "not matched by include"))
                continue
            if exclude and exclude.search(label):
                excluded.append((code, title, "matched exclude"))
                continue

            warnings = []
            content = block
            if c_start:
                cs = c_start.search(block)
                if cs:
                    content = block[cs.end():]
                else:
                    warnings.append("content start not found; used the whole block")
            if c_end:
                ce = c_end.search(content)
                if ce:
                    content = content[: ce.start()]
                else:
                    warnings.append("content end not found")
            topics = topics_from(repair_split_words(content, vocab), strip, extra_split)
            if not topics:
                warnings.append("no topics found")

            credits = None
            if credits_rx and (cm := credits_rx.search(header)):
                try:
                    credits = float(cm.group("credits"))
                except (ValueError, IndexError):
                    warnings.append("credits not a number")
            semester = entry.get("semester") or ""
            if not semester and sem_rx and (sm := sem_rx.search(block)):
                semester = sm.group("semester")

            if not code:
                code = f"C{len(drafts) + 1:02d}"
            if code in by_code and duplicates == "number":   # alternatives sharing a label
                n = 2
                while f"{code}/{n}" in by_code:
                    n += 1
                code = f"{code}/{n}"
            if code in by_code:              # another part of the same course
                first = by_code[code]
                first.course.topics = list(dict.fromkeys([*first.course.topics, *topics]))
                first.warnings.extend(warnings)
                merged.append((code, f"{path.name} p{lines[i][0]}"))
                continue
            try:
                course = Course(code=code, title=title or code, credits=credits,
                                semester=str(semester) or None, topics=topics,
                                category=category_for(code, title))
            except ValidationError as exc:
                excluded.append((code, title, f"invalid: {exc.errors()[0]['msg']}"))
                continue
            drafts.append(DraftCourse(course, path.name, lines[i][0], warnings))
            by_code[code] = drafts[-1]

    for extra in prof.get("extra_courses") or []:
        note = extra.pop("note", "typed in by hand")
        if "category" not in extra:
            extra["category"] = category_for(str(extra.get("code", "")), str(extra.get("title", "")))
        try:
            course = Course(**extra)
        except (ValidationError, TypeError) as exc:
            raise ProfileError(f"{profile_path.name}: extra course {extra.get('code')!r} is invalid ({exc})") from None
        if course.code in by_code:
            raise ProfileError(f"{profile_path.name}: extra course {course.code} was also found in the PDFs")
        drafts.append(DraftCourse(course, "(profile)", 0, [f"manual: {note}"]))
        by_code[course.code] = drafts[-1]

    if not drafts:
        raise ProfileError(f"{profile_path.name}: no courses found - check course_start and include")
    programme = Programme(institution=prof["institution"], name=prof["name"],
                          source=prof.get("source", ""), year=str(prof.get("year", "")),
                          courses=[d.course for d in drafts])
    return Draft(programme, drafts, excluded, merged)
