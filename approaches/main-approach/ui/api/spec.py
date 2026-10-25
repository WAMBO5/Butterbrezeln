"""Splits a spec.md into sections with line numbers so findings can cite spec lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Section:
    title: str
    first: int  # 1-based, heading line
    last: int


@dataclass
class ParsedSpec:
    name: str
    text: str
    lines: list[str]
    title: str
    sections: list[Section] = field(default_factory=list)

    def numbered(self) -> str:
        return "\n".join(f"{i:>3}| {line}" for i, line in enumerate(self.lines, start=1))

    def section(self, title: str) -> Section | None:
        wanted = title.lower()
        return next((s for s in self.sections if s.title.lower() == wanted), None)

    def find(self, *keywords: str) -> list[int] | None:
        """[line, line] of the first line containing any keyword (case-insensitive)."""
        pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
        for i, line in enumerate(self.lines, start=1):
            if pattern.search(line):
                return [i, i]
        return None

    def contains(self, *keywords: str) -> bool:
        low = self.text.lower()
        return any(k.lower() in low for k in keywords)


def parse_spec(name: str, text: str) -> ParsedSpec:
    lines = text.splitlines()
    title = name
    sections: list[Section] = []
    for i, line in enumerate(lines, start=1):
        heading = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if not heading:
            continue
        if len(heading.group(1)) == 1:
            title = re.sub(r"^spec:\s*", "", heading.group(2), flags=re.IGNORECASE)
            continue
        if sections:
            sections[-1].last = i - 1
        sections.append(Section(title=heading.group(2), first=i, last=len(lines)))
    return ParsedSpec(name=name, text=text, lines=lines, title=title, sections=sections)
