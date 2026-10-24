"""Parse page-marked regulation text into provisions without a model.

A provision starts at a UNECE paragraph number ("6.10.4.1.") or an annex heading. Lettered items stay inside their
paragraph. Inside an annex the citation label is "Annex 6 Part 4 4.1", matching the gold file's style.

Numbering is tracked per level: for every paragraph we remember the highest child number seen under it, so a number is
accepted when it is the next (or a near-next) child of a known parent. A wrapped line that happens to start with a number
("1. The objective luminous flux ...") or a table row ("5 Functional hinge") is therefore not mistaken for a paragraph, and
one stray match cannot derail the paragraphs that follow it. Every rule here came from a real defect found in review of the
56 base texts; tests/unit/test_parser.py pins them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline.catalog.normalise import normalise

PAGE_MARK = re.compile(r"^=== PDF page (\d+) ===$")
PAGE_HEADER = re.compile(r"^.+, version [^|]+\| page \d+ of \d+$")
PARA = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){0,6})\.(?:\s+(.*))?$")             # "6.10.4.1. In width: ..."
NO_DOT = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){0,6})\s+(\S.*)$")                 # "5.7 Grouped ...", "2.4 \"Floor line\" means", "1 Scope"
_DASH = "-‐‑‒–—"                                      # hyphen, non-breaking hyphen, en and em dash
ANNEX = re.compile(
    r"^Annex\s+(\d{1,2})([A-Za-z]?)"                                           # number and optional letter ("1a", "2B")
    rf"(?:\s*[{_DASH}]?\s*(Appendix|Part)(?:\s+(\d+|[IVX]+)\b)?)?"             # "- Part 1", "Appendix 2", "- Part I"
    rf"(?:\s*[{_DASH}:]?\s*(.*))?$", re.I)                                     # title; "ANNEX 1 COMMUNICATION" too (R32)
PART = re.compile(rf"^Part (\d{{1,2}})\s*[{_DASH}:]\s*(\S.*)$")                # "Part 4 - Resistance to corrosion"
APPENDIX = re.compile(rf"^Appendix\s+(\d{{1,2}})\s*[{_DASH}:]?\s*([A-Z].*)$")  # main-body "Appendix 3 Artificial networks" (R10, R49)
GTR_TEXT_START = re.compile(r"^II\.\s+Text of the Regulation", re.I)
LEADERS = re.compile(r"(?:\.\s?){6,}|…{2,}")                              # "Trade name or mark ........": a form field
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
# A numbered line that starts in lower case is a list item only if it is not one of these wrapped-reference openers.
_WRAP_WORDS = frozenset("above below of to and or need shall is are in for on at by with than as".split())
_QUOTES = "\"“‘'"


@dataclass
class Provision:
    provision_id: str
    regulation: str
    role: str
    version_label: str
    paragraph: str          # citation label, e.g. "6.10.4.1" or "Annex 6 Part 4 4.1"
    number: str             # bare number inside its segment, e.g. "6.10.4.1", "" for an annex heading
    section: str            # numbered heading used for section expansion, e.g. "6.10", "Annex 6 Part 4"
    heading_path: list[str]
    page: int
    page_end: int
    lines: list[str] = field(default_factory=list)
    line_pages: list[int] = field(default_factory=list)
    rationale: bool = False  # never retrieved or cited: GTR rationale, introduction, form fields with dot leaders

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()

    @property
    def text_norm(self) -> str:
        return normalise(self.text)


def _heading_like(rest: str) -> bool:
    """A short capitalised line that does not run on: what a section heading looks like (not a wrapped sentence)."""
    rest = rest.strip()
    return not rest or (len(rest) <= 90 and (rest[0].isupper() or rest[0] in "(“\"") and not rest.endswith((",", ";")))


class _Numbering:
    """Highest child seen under every accepted paragraph; decides whether a numbered line is the next paragraph."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.last_child: dict[tuple[int, ...], int] = {(): -1}
        self.known: set[tuple[int, ...]] = {()}

    def accept(self, nums: tuple[int, ...], rest: str, dotted: bool, in_annex: bool, prev_text: str) -> bool:
        parent, k, depth = nums[:-1], nums[-1], len(nums)
        first = rest[:1]
        nxt = self.last_child.get(parent, -1) + 1
        exact = k == nxt or (nxt == 0 and k == 1)       # the next child (children are numbered from 1, sometimes 0)
        prev = prev_text.rstrip()
        if (not rest or first == "(") and prev.lower().endswith(("paragraph", "paragraphs", "and", "to", ",")):
            return False                                      # "... see paragraphs\n5.2.3. (a)": a reference that wrapped
        if first.islower():
            # "3.1.2.1. the length and width" after "... accompanied by:" is a list item; "7.10.2.1. above" is a wrapped line
            word = rest.split()[0].lower().strip(",.;:")
            if not (dotted and depth >= 2 and exact and parent in self.known and prev[-1:] in ":;." and word not in _WRAP_WORDS):
                return False
        if depth == 1:
            if not rest or (in_annex and not dotted) or (not dotted and not _heading_like(rest)):
                return False                                  # a bare "8.", an annex table row "5 Hinge", a long dotless line
            if nxt == 0:                                      # the first section is numbered 0 or 1 (or 2 if 1 is a title page)
                return k <= 1 if not dotted else k <= 2
            if not dotted:
                return k == nxt                               # "1 Scope" style: exactly the next number, or table rows get in
            if not (nxt <= k <= nxt + 1):
                return False
            # a skipped number must look like a heading; the exact next one may be a long heading ("13. Names and addresses ... tests,")
            return in_annex or k == nxt and first.isupper() or _heading_like(rest)
        if parent not in self.known and not (parent[:-1] in self.known and k <= 6):
            return False                                      # under a paragraph we never saw (and no near-miss either)
        if not dotted:                                        # "2.4 \"Floor line\" means ...": exactly the next child, a capital or a quote
            return (exact and (first.isupper() or first in _QUOTES) and sum(c.isalpha() for c in rest) >= 3)
        return nxt <= k <= nxt + 4

    def commit(self, nums: tuple[int, ...]) -> None:
        for i in range(1, len(nums) + 1):
            self.known.add(nums[:i])
        parent = nums[:-1]
        self.last_child[parent] = max(self.last_child.get(parent, -1), nums[-1])


def _annex_heading(m: re.Match, prev_text: str, annex_rank: tuple[int, str, int]) -> tuple[str, tuple[int, str, int]] | None:
    """(segment label, rank) when the line is an annex heading, else None.

    Headings read "Annex 1a Information document", "ANNEX 1 COMMUNICATION", "Annex 4 - Part 1", "Annex 6 Appendix 2 - Title",
    "Annex 8 (reserved)" or a bare "Annex 5". Body text mentions annexes too ("Annex 2 to this Regulation.", "Annex 10
    (values in"): a heading needs a capitalised title, and annexes only advance, by at most two numbers at a time."""
    num, letter, kind, ident, title = int(m.group(1)), m.group(2), m.group(3), m.group(4), (m.group(5) or "").strip()
    kind = kind.capitalize() if kind else None
    reserved = title.lower().startswith("(reserved")
    if kind is None and not title:                           # bare "Annex 5": the next annex, after the end of a sentence
        if not (num == annex_rank[0] + 1 and not letter and (not prev_text.strip() or prev_text.strip()[-1] in ".:)]")):
            return None
    elif not title:
        pass                                                 # "Annex 4 - Appendix 1" (title on no line or the next)
    elif not (title[0].isupper() or reserved):
        return None
    sub = 0
    if kind == "Part":
        sub = int(ident) if ident and ident.isdigit() else _ROMAN.get((ident or "I").upper(), 1)
    elif kind == "Appendix":
        sub = 100 + (int(ident) if ident and ident.isdigit() else 1)
    rank = (num, letter.lower(), sub)
    if not (rank > annex_rank and num <= max(annex_rank[0], 0) + 2):
        return None
    label = f"Annex {num}{letter.upper()}"
    if kind == "Part":
        label += f" Part {sub}"
    elif kind == "Appendix":
        label += f" Appendix {sub - 100}"
    return label, rank


def _section(segment: str, nums: tuple[int, ...]) -> str:
    if segment:
        return segment
    return ".".join(str(n) for n in nums[:2])


def parse_text(text: str, regulation: str, role: str, version_label: str) -> list[Provision]:
    provisions: list[Provision] = []
    preamble: list[tuple[str, int]] = []
    page = 1
    segment = ""             # "" for the main body, "Appendix 3" in the main body, "Annex 6" / "Annex 6 Part 4" inside annexes
    annex_rank = (0, "", 0)
    appendix_no = 0
    numbering = _Numbering()
    headings: dict[int, str] = {}
    rationale = regulation.startswith("UN GTR")  # GTRs open with a long rationale part before the text
    seen_ids: dict[str, int] = {}
    current: Provision | None = None
    prev_text = ""

    def start(paragraph: str, number: str, nums: tuple[int, ...], first_line: str) -> Provision:
        base = f"{regulation}|{version_label}|{paragraph}"
        seen_ids[base] = seen_ids.get(base, 0) + 1
        pid = base if seen_ids[base] == 1 else f"{base}#{seen_ids[base]}"
        path = [headings[d] for d in sorted(headings) if d < len(nums)]
        prov = Provision(pid, regulation, role, version_label, paragraph, number,
                         _section(segment, nums) if nums else segment,
                         ([segment] if segment else []) + path, page, page, [first_line], [page], rationale)
        provisions.append(prov)
        return prov

    for raw in text.splitlines():
        line = raw.rstrip()
        mark = PAGE_MARK.match(line)
        if mark:
            page = int(mark.group(1))
            continue
        if PAGE_HEADER.match(line):
            prev_text = ""
            continue
        if not line.strip():
            continue
        if rationale and GTR_TEXT_START.match(line):
            rationale = False
            numbering.reset()
            headings, current = {}, None
            prev_text = line
            continue

        annex = ANNEX.match(line)
        if annex and not line.endswith(" x"):
            found = _annex_heading(annex, prev_text, annex_rank)
            if found:
                segment, annex_rank = found
                appendix_no = 0
                numbering.reset()
                headings = {}
                current = start(segment, "", (), line)
                current.section = segment
                prev_text = line
                continue

        part = PART.match(line)
        if part and segment.startswith("Annex"):
            segment = re.sub(r" Part \d+$", "", segment) + f" Part {int(part.group(1))}"
            numbering.reset()
            headings = {}
            current = start(segment, "", (), line)
            current.section = segment
            prev_text = line
            continue

        appendix = APPENDIX.match(line)
        if appendix and not segment.startswith("Annex"):     # a main-body appendix; inside an annex it is that annex's own
            n = int(appendix.group(1))
            if n == appendix_no + 1 or (appendix_no == 0 and n <= 2):
                appendix_no = n
                segment = f"Appendix {n}"
                numbering.reset()
                headings = {}
                current = start(segment, "", (), line)
                current.section = segment
                prev_text = line
                continue

        para = PARA.match(line)
        dotted = para is not None
        para = para or NO_DOT.match(line)
        if para:
            number = para.group(1)
            nums = tuple(int(x) for x in number.split("."))
            rest = (para.group(2) or "").strip()
            if numbering.accept(nums, rest, dotted, bool(segment), prev_text):
                numbering.commit(nums)
                if rest and len(rest) < 90 and not rest.endswith(".") and rest[:1].isupper():
                    headings[len(nums) - 1] = f"{number} {rest}"
                    headings = {d: h for d, h in headings.items() if d <= len(nums) - 1}
                label = f"{segment} {number}" if segment else number
                current = start(label, number, nums, line)
                prev_text = line
                continue

        if current is not None:
            current.lines.append(line)
            current.line_pages.append(page)
            current.page_end = page
        else:
            preamble.append((line, page))
        prev_text = line

    for p in provisions:  # form fields ("Trade name or mark ........") are noise for retrieval and for the judge
        if not p.rationale and len(p.text) < 300 and LEADERS.search(p.text):
            p.rationale = True
    if preamble:  # introduction before the first paragraph: kept for the regulation card, never retrieved or cited
        intro = Provision(f"{regulation}|{version_label}|Introduction", regulation, role, version_label, "Introduction", "",
                          "Introduction", [], preamble[0][1], preamble[-1][1], [ln for ln, _ in preamble],
                          [pg for _, pg in preamble], True)
        provisions.insert(0, intro)
    return provisions
