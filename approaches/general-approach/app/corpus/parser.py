"""Page-preserving parser for the challenge's regulation text files (design spec section 7).

A file is a sequence of `=== PDF page N ===` blocks, each starting with a footer line such as
`UN R148, version 1.6.0 | page 2 of 48`. Paragraph numbers are detected only when they are a
plausible next number, so table rows and wrapped references stay inside their paragraph.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.models import Provision

PAGE_RE = re.compile(r"^=== PDF page (\d+) ===$", re.M)
# the footer line, and the header line a text extracted from a sub-goal PDF has above it
HEADER_RE = re.compile(r"^(?:UN .+, version .+|sub-goal .+) \| page \d+ of \d+$")
PARA_RE = re.compile(r"^(\d+(?:\.\d+)*)(\.?)\s+(\S.*)$")
ANNEX_RE = re.compile(r"^Annex (\d+)([A-Z]?)(?:\s*[-–]\s*Appendix (\d+))?(?:\s+(\S.*))?$")
APPENDIX_RE = re.compile(r"^Appendix (\d+)(?:\s+(\S.*))?$")
PART_RE = re.compile(r"^Part (\d+|[A-Z])\b\s*[:.\-–]?\s*(.*)$")
# words that start a wrapped line such as "7. of this Regulation", which is not a new paragraph
CONTINUATION = {"of", "and", "or", "to", "above", "below", "in", "shall", "is", "are", "be", "for", "with",
                "apply", "applies", "this", "these", "which", "as", "has", "have", "must", "may", "at", "on"}
# A GTR opens with a numbered "Statement of technical rationale and justification" (Part I) and only then
# gives "II. Text of the Regulation", whose numbering starts again at 1: Part I goes into the Introduction.
RATIONALE_RE = re.compile(r"^I\.\s+Statement of technical rationale and justification\b", re.I)
REGULATION_TEXT_RE = re.compile(r"^II\.\s+Text of the (?:global technical )?regulation\b", re.I)
# Some UN Regulations (UN R171) number the paragraphs of their Introduction; the main text then starts
# again at "1. Scope", and what was numbered before it is the Introduction.
SCOPE_HEADING_RE = re.compile(r"^scope\b", re.I)
PARSER_VERSION = "p3"  # part of the corpus store's file key: a new version re-parses every file once
REF_PARA_RE = re.compile(r"paragraphs? (\d+(?:\.\d+)*)")
REF_ANNEX_RE = re.compile(r"Annex (\d+)")
REF_REG_RE = re.compile(r"(?:UN )?Regulation No\. ?(\d+)")
MODAL_RE = re.compile(r"\b(shall|must)\b", re.I)


def normalize(text: str) -> str:
    """NFKC (so `ﬁ` becomes `fi`), whitespace collapsed, stripped."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


def squash(text: str) -> str:
    """Case-folded NFKC text without any whitespace: the form quotes are compared in."""
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def paragraph_key(label: object) -> str | None:
    """The same rules as `tools/score_local.py::_paragraph_key`."""
    text = str(label or "").casefold().replace("§", " ")
    text = re.sub(r"[,;:()\[\]]", " ", text)
    text = re.sub(r"(?<![0-9a-z])\.|\.(?![0-9a-z])", " ", text)
    text = " ".join(text.split())
    text = re.sub(r"^(paragraphs?|para|par|section|clause)\s+", "", text)
    return text or None


def iter_pages(text: str) -> list[tuple[int, str]]:
    """(page number, page text without its footer and header lines), in file order."""
    pages: list[tuple[int, str]] = []
    matches = list(PAGE_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        lines = text[m.end():end].strip("\n").split("\n")
        while lines and HEADER_RE.match(lines[0].strip()):
            lines = lines[1:]
        pages.append((int(m.group(1)), "\n".join(lines).strip("\n")))
    return pages


def _plausible(prev: tuple[int, ...] | None, new: tuple[int, ...]) -> bool:
    if prev is None:
        return new[0] <= 2 and len(new) <= 2 and all(n <= 3 for n in new)
    if new == prev + (1,):
        return True
    for level in range(len(prev)):
        base = prev[:level]
        if len(new) == level + 1 and new[:level] == base and 1 <= new[level] - prev[level] <= 3:
            return True
    return False


def _part_plausible(current: str | None, part: str) -> bool:
    if part.isdigit():
        if current is None or not current.isdigit():
            return int(part) <= 2
        return 1 <= int(part) - int(current) <= 2
    if current is None or current.isdigit():
        return part in "AB"
    return 1 <= ord(part) - ord(current) <= 2


def _annex_plausible(current: tuple[int, str] | None, number: int, letter: str) -> bool:
    if current is None:
        return number <= 2
    cur_n, cur_letter = current
    if number == cur_n:
        return bool(letter) and letter > cur_letter
    return 1 <= number - cur_n <= 3


@dataclass
class _Open:
    label: str
    numeric: str | None
    heading_path: list[str]
    page_start: int
    page_end: int
    lines: list[str] = field(default_factory=list)
    annex_heading: str | None = None
    top_heading: str | None = None
    kind: str | None = None  # set for a GTR rationale, which holds no obligations


def _kind(text: str, heading_path: list[str], annex_heading: str | None, top_heading: str | None) -> str:
    path = " / ".join(heading_path).casefold()
    if annex_heading and "communication" in annex_heading.casefold():
        return "form"
    if annex_heading is None and top_heading:
        top = top_heading.casefold()
        if "scope" in top:
            return "scope"
        if "definition" in top:
            return "definition"
    modal = bool(MODAL_RE.search(text))
    if "transitional provisions" in path or (top_heading and "transitional provisions" in top_heading.casefold()):
        return "transitional"
    if modal and "test" in path:
        return "test_procedure"
    if "conformity of production" in path or (top_heading and "conformity of production" in top_heading.casefold()):
        return "conformity"
    if modal:
        return "requirement"
    if "administrative" in path or "approval" in path:
        return "administrative"
    return "other"


def _refs(text: str) -> list[str]:
    refs: list[str] = []
    for m in REF_PARA_RE.finditer(text):
        refs.append(f"para:{m.group(1)}")
    for m in REF_ANNEX_RE.finditer(text):
        refs.append(f"annex:{m.group(1)}")
    for m in REF_REG_RE.finditer(text):
        refs.append(f"reg:UN R{m.group(1)}")
    return list(dict.fromkeys(refs))


def parse_regulation(
    text: str, regulation: str, version_label: str, role: Literal["base", "latest"]
) -> list[Provision]:
    """Every provision of one regulation version, with labels such as `5.4.2`, `Annex 8 2.1` or
    `Annex 4 Part 1 1.2`, and `provision_id = f"{regulation}@{version_label}#{label}"`."""
    provisions: list[Provision] = []
    seen: dict[str, int] = {}
    headings: dict[str, str] = {}  # numeric label -> its heading, in the current scope
    scope_prefix = ""  # "" in the main body, "Annex 3 " / "Annex 3 Part 1 " inside annexes
    scope_path: list[str] = []  # annex / part headings
    annex: tuple[int, str] | None = None
    part: str | None = None
    annex_heading: str | None = None
    prev: tuple[int, ...] | None = None
    current: _Open | None = None
    rationale = False  # inside a GTR's Part I, until "II. Text of the Regulation"
    scope_read = False  # the main text's "1. Scope" was read

    def close() -> None:
        nonlocal current
        if current is None:
            return
        body = "\n".join(current.lines).strip()
        label = current.label
        if label in seen:
            seen[label] += 1
            label = f"{label}~{seen[label]}"
        else:
            seen[label] = 1
        provisions.append(
            Provision(
                provision_id=f"{regulation}@{version_label}#{label}",
                regulation=regulation,
                version_label=version_label,
                role=role,
                paragraph=label,
                heading_path=current.heading_path,
                page_start=current.page_start,
                page_end=current.page_end,
                text=body,
                kind=current.kind or _kind(body, current.heading_path, current.annex_heading, current.top_heading),  # type: ignore[arg-type]
                refs=_refs(body),
            )
        )
        current = None

    def open_scope(label: str, heading: str, page: int) -> None:
        nonlocal current
        close()
        current = _Open(label=label, numeric=None, heading_path=list(scope_path[:-1]), page_start=page,
                        page_end=page, lines=[heading], annex_heading=annex_heading)

    def number_introduction() -> None:
        """Relabel the numbered paragraphs read so far (`10` becomes `Introduction 10`)."""
        for i, p in enumerate(provisions):
            if p.paragraph == "Introduction":
                continue
            seen.pop(p.paragraph, None)
            label = f"Introduction {p.paragraph}"
            seen[label] = 1
            provisions[i] = p.model_copy(update={
                "provision_id": f"{regulation}@{version_label}#{label}", "paragraph": label,
                "heading_path": ["Introduction"], "kind": _kind(p.text, ["Introduction"], None, None)})

    for page, page_text in iter_pages(text):
        for raw in page_text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            plain = unicodedata.normalize("NFKC", line)
            if rationale and current is not None:
                if REGULATION_TEXT_RE.match(plain):
                    close()
                    rationale, prev, headings = False, None, {}
                    continue
                current.lines.append(line)
                current.page_end = page
                continue
            if prev is None and annex is None and RATIONALE_RE.match(plain):
                if current is None or current.label != "Introduction":
                    close()
                    current = _Open(label="Introduction", numeric=None, heading_path=[], page_start=page,
                                    page_end=page)
                current.kind, rationale = "other", True
                current.lines.append(line)
                current.page_end = page
                continue
            m_annex = ANNEX_RE.match(line)
            if m_annex and (m_annex.group(4) is None or m_annex.group(4)[0].isupper()):
                number, letter, appendix = int(m_annex.group(1)), m_annex.group(2), m_annex.group(3)
                name = f"{number}{letter}"
                if appendix is not None and annex is not None and annex[0] == number:
                    annex_heading = annex_heading or line
                    scope_prefix = f"Annex {name} Appendix {appendix} "
                    scope_path = [annex_heading, line]
                    prev, headings = None, {}
                    open_scope(scope_prefix.strip(), line, page)
                    continue
                if appendix is None and _annex_plausible(annex, number, letter):
                    annex, annex_heading, part = (number, letter), line, None
                    scope_prefix = f"Annex {name} "
                    scope_path = [line]
                    prev, headings = None, {}
                    open_scope(f"Annex {name}", line, page)
                    continue
            if annex is not None:
                m_app = APPENDIX_RE.match(line)
                if m_app and (m_app.group(2) is None or m_app.group(2)[0].isupper()):
                    scope_prefix = f"Annex {annex[0]}{annex[1]} Appendix {m_app.group(1)} "
                    scope_path = [annex_heading or "", line]
                    prev, headings = None, {}
                    open_scope(scope_prefix.strip(), line, page)
                    continue
                m_part = PART_RE.match(line)
                if (m_part and (not m_part.group(2) or m_part.group(2)[0].isupper())
                        and _part_plausible(part, m_part.group(1))):
                    part = m_part.group(1)
                    scope_prefix = f"Annex {annex[0]}{annex[1]} Part {m_part.group(1)} "
                    scope_path = [annex_heading or "", line]
                    prev, headings = None, {}
                    open_scope(scope_prefix.strip(), line, page)
                    continue
            m_para = PARA_RE.match(line)
            if m_para:
                numeric, dot, rest = m_para.group(1), m_para.group(2), m_para.group(3)
                ids = tuple(int(n) for n in numeric.split("."))
                starts_scope = ids == (1,) and bool(dot) and scope_prefix == "" and bool(SCOPE_HEADING_RE.match(rest))
                if (starts_scope and prev is not None and not _plausible(prev, ids) and annex is None
                        and not scope_read):
                    close()
                    number_introduction()
                    prev, headings = None, {}
                accept = _plausible(prev, ids)
                first_word = re.split(r"[\s,;]", rest, maxsplit=1)[0]
                if accept and (len(ids) == 1 and not rest[0].isupper() or first_word in CONTINUATION):
                    accept = False
                if accept and not dot:
                    starts_ok = rest[0].isupper() or rest[0] in "\"“'("
                    accept = starts_ok and (len(ids) > 1 or not re.search(r"\d", rest))
                if accept:
                    close()
                    prev, scope_read = ids, scope_read or starts_scope
                    parents = [".".join(map(str, ids[:k])) for k in range(1, len(ids))]
                    path = list(scope_path) + [f"{p} {headings[p]}" for p in parents if p in headings]
                    headings[numeric] = rest[:120]
                    top = headings.get(str(ids[0])) if scope_prefix == "" else None
                    current = _Open(label=f"{scope_prefix}{numeric}", numeric=numeric, heading_path=path,
                                    page_start=page, page_end=page, lines=[rest], annex_heading=annex_heading,
                                    top_heading=top)
                    continue
            if current is None:
                current = _Open(label="Introduction", numeric=None, heading_path=[], page_start=page, page_end=page)
            current.lines.append(line)
            current.page_end = page
    close()
    return provisions
