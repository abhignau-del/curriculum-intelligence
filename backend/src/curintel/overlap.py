"""Find pairs of courses in one programme whose content substantially overlaps.

Each course becomes a bag of words and two-word phrases from its title and
topics (outcomes are left out: their verbs - "apply", "solve" - make every
course look alike). Words that most courses use get little weight (TF-IDF),
and pairs are compared by cosine similarity. A pair is reported with the
phrases that drove the score, so a committee can judge it.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from .schema import Course, Programme
from .taxonomy import Taxonomy, normalise

HIGH = 0.6
MODERATE = 0.4
LAB_WORDS = ("lab", "laboratory", "practical", "practicals", "workshop", "exercises", "tutorial")

# English function words, plus words every syllabus uses.
STOPWORDS = frozenset("""
a an and are as at be by for from in into is it its of on or the to with without via
their this that these those its using use used based between through upon over under
introduction introductory basic basics elementary fundamental fundamentals concept concepts
advanced simple general various types type application applications applied example
examples problem problems properties property theorem theorems definition definitions
result results method methods technique techniques unit module part study course
theory principle principles overview topic topics standard important related simple
i ii iii iv v vi 1 2 3 4 5 6 s
""".split())


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies") and word != "series":
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def terms_of(course: Course) -> Counter[str]:
    bag: Counter[str] = Counter()
    for line in [course.title, *course.topics]:
        # Phrases only from words that are adjacent in the text, so removing
        # "of" in "tests of significance" doesn't invent "test significance".
        runs: list[list[str]] = []
        for clause in re.split(r"[,:;.()/\-–]", line):
            runs.append([])
            for w in normalise(clause).split():
                if w in STOPWORDS:
                    runs.append([])
                else:
                    runs[-1].append(_stem(w))
        for run in runs:
            bag.update(run)
            bag.update(f"{a} {b}" for a, b in zip(run, run[1:]))
    return bag


@dataclass
class OverlapPair:
    a: str                      # course codes
    b: str
    a_title: str
    b_title: str
    similarity: float           # 0-1
    level: Literal["High", "Moderate"]
    shared_terms: list[str]     # strongest shared phrases
    shared_skills: list[str]    # skill names found in both courses
    theory_lab_pair: bool       # one is the other's lab: overlap is expected


def find_overlaps(programme: Programme, taxonomy: Taxonomy | None = None,
                  threshold: float = MODERATE) -> list[OverlapPair]:
    courses = [c for c in programme.courses if c.topics]
    if len(courses) < 2:
        return []
    bags = [terms_of(c) for c in courses]
    df: Counter[str] = Counter()
    for bag in bags:
        df.update(bag.keys())
    n = len(courses)
    # Smoothed IDF; a term in every course still keeps a little weight.
    idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
    vectors = []
    for bag in bags:
        vec = {t: (1 + math.log(tf)) * idf[t] for t, tf in bag.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({t: v / norm for t, v in vec.items()})

    skills = None
    if taxonomy is not None:
        skills = [{h.skill for line in [c.title, *c.topics] for h in taxonomy.match(line)}
                  for c in courses]

    pairs = []
    for i, j in combinations(range(n), 2):
        vi, vj = vectors[i], vectors[j]
        shared = sorted(vi.keys() & vj.keys())
        contributions = {t: vi[t] * vj[t] for t in shared}
        sim = sum(contributions.values())
        if sim < threshold:
            continue
        # Phrases first, then single words; skip a term that shares a word
        # with one already listed, so fragments like "rule simpson" drop out.
        top = sorted(contributions, key=lambda t: (" " not in t, -round(contributions[t], 9), t))
        listed: list[str] = []
        used: set[str] = set()
        for t in top:
            words = set(t.split())
            if words & used:
                continue
            listed.append(t)
            used |= words
            if len(listed) == 6:
                break
        shared_skills = []
        if skills is not None:
            shared_skills = sorted(taxonomy.skills[s].name for s in skills[i] & skills[j])
        is_lab = [any(w in normalise(c.title).split() for w in LAB_WORDS)
                  for c in (courses[i], courses[j])]
        pairs.append(OverlapPair(
            courses[i].code, courses[j].code, courses[i].title, courses[j].title,
            round(sim, 3), "High" if sim >= HIGH else "Moderate", listed, shared_skills,
            is_lab[0] != is_lab[1]))
    pairs.sort(key=lambda p: -p.similarity)
    return pairs
