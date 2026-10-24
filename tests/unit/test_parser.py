"""Parser behaviour on the failure modes found in review: annex heading shapes, wrapped numbers, table rows."""
import re

from pipeline.catalog.corpus import base_versions, page_text, provisions
from pipeline.catalog.parse import parse_text


def parse(body: str):
    return parse_text("=== PDF page 1 ===\n" + body, "UN R999", "base", "1.0.0")


def labels(provs):
    return [p.paragraph for p in provs if not p.rationale]


def test_annex_heading_shapes():
    provs = parse("""1. Scope
This Regulation applies to things, see
Annex 2 to this Regulation.
Annex 1, and giving a description of the technical
2. Definitions
2.1. A thing means something.
Annex 1a Information document
1. General
1.1. The make.
Annex 1b Information document
1. General
Annex 2a Communication
1. Remarks:
Annex 3
(reserved)
Annex 4 - Part I WEAR TEST
1. Method
Annex 4 - Part 2 OTHER TEST
Annex 5 Appendix 1 - Title
1. A
Annex 5 Appendix 2
1. B
""")
    got = labels(provs)
    for want in ("Annex 1A", "Annex 1A 1", "Annex 1A 1.1", "Annex 1B", "Annex 1B 1", "Annex 2A", "Annex 3", "Annex 4 Part 1",
                 "Annex 4 Part 1 1", "Annex 4 Part 2", "Annex 5 Appendix 1", "Annex 5 Appendix 2", "Annex 5 Appendix 2 1"):
        assert want in got, (want, got)
    assert got[:3] == ["1", "2", "2.1"]  # the body mentions of "Annex 2 to this Regulation." did not start an annex
    assert len(got) == len(set(got))     # no duplicate labels once annexes are recognised


def test_wrapped_numbers_and_table_rows_are_not_paragraphs():
    provs = parse("""1. Scope
2. Definitions
3. Requirements
3.1. The device shall do X, as measured in
1. The objective luminous flux of the device shall be measured in all of the positions given in the table below.
5 Functional hinge
8.
7. of this Regulation
3.2. The next paragraph.
4. Tests
""")
    assert labels(provs) == ["1", "2", "3", "3.1", "3.2", "4"]
    inner = next(p for p in provs if p.paragraph == "3.1").text
    assert "objective luminous flux" in inner and "Functional hinge" in inner  # swallowed by the paragraph they belong to


def test_unpunctuated_headings_are_accepted_only_as_the_next_number():
    provs = parse("""1 Scope
This Regulation applies to things.
2. Definitions
3. Requirements
3.1. First.
3.2. Second.
3.3 Grouped, combined or reciprocally incorporated lamps
3.3.1. Lamps may be grouped.
1 AAN
9 FAIL FAIL
""")
    got = labels(provs)
    assert got == ["1", "2", "3", "3.1", "3.2", "3.3", "3.3.1"]  # "1 AAN" and "9 FAIL FAIL" are table rows, not sections


def test_introduction_before_the_first_paragraph_is_kept_but_never_retrieved():
    provs = parse("Introduction (for information)\nThis Regulation combines the provisions of things.\n1. Scope\nText.\n")
    intro = next(p for p in provs if p.paragraph == "Introduction")
    assert intro.rationale and "combines the provisions" in intro.text
    assert labels(provs) == ["1"]


def test_every_annex_heading_is_detected_in_every_regulation():
    """Every line that looks like a strict annex heading ("Annex 4 - Part 1 TITLE", "Annex 1a ...") must open an annex."""
    strict = re.compile(r"^(?i:annex)\s+(\d{1,2})([A-Za-z]?)(?:\s*[-\u2010-\u2014]?\s*(?i:part|appendix)(?:\s+(?:\d+|[IVX]+)\b)?)?"
                        r"\s*[-\u2010-\u2014:]?\s*(?:[A-Z(][^\n]*)?$")
    header = re.compile(r"^.+, version [^|]+\| page \d+ of \d+$")
    problems = []
    for v in base_versions():
        lines = [ln.rstrip() for ln in page_text(v).splitlines() if ln.strip() and not ln.startswith("=== PDF")]
        wanted = set()
        for i, ln in enumerate(lines):
            m = strict.match(ln)
            if not m or ln.endswith((" x", ".", ",", ";", ")")) or "(values" in ln:
                continue
            prev = lines[i - 1] if i else ""
            if prev and not (header.match(prev) or prev.rstrip()[-1:] in ".:)]" or prev.startswith("Annex")):
                continue
            wanted.add(int(m.group(1)))
        found = {int(re.match(r"Annex (\d+)", p.paragraph).group(1)) for p in provisions(v.regulation, v.version_label)
                 if p.number == "" and p.paragraph.startswith("Annex")}
        if wanted - found:
            problems.append((v.regulation, sorted(wanted - found)))
    assert not problems, problems


def test_no_regulation_has_a_provision_that_swallows_its_neighbours():
    """The bumper regulations were the worst hit by the old parser (R26: one 10.9k-character provision)."""
    for reg, limit in (("UN R26", 4000), ("UN R42", 4000), ("UN R127", 4000), ("UN R48", 4000), ("UN R148", 4000), ("UN R150", 4000)):
        v = next(x for x in base_versions() if x.regulation == reg)
        biggest = max((p for p in provisions(reg, v.version_label) if not p.rationale), key=lambda p: len(p.text))
        assert len(biggest.text) < limit, (reg, biggest.paragraph, len(biggest.text))
    gtr = next(x for x in base_versions() if x.regulation == "UN GTR 9")
    top = [p.number for p in provisions("UN GTR 9", gtr.version_label)
           if not p.rationale and p.number and "." not in p.number and not p.paragraph.startswith("Annex")]
    assert top == [str(n) for n in range(1, 9)]  # 1 PURPOSE ... 8 CERTIFICATION OF IMPACTORS


def test_capitalised_annex_headings_and_non_breaking_hyphens():
    provs = parse("""1. Scope
2. Definitions
ANNEX 1 COMMUNICATION
1. Remarks:
ANNEX 2 PROCEDURE FOR REAR-END IMPACT TEST
1. General
ANNEX 3 ‑ APPENDIX 1 TITLE
1. Data
""")
    got = labels(provs)
    for want in ("Annex 1", "Annex 1 1", "Annex 2", "Annex 3 Appendix 1", "Annex 3 Appendix 1 1"):
        assert want in got, (want, got)


def test_dotless_definitions_and_lettered_list_items_are_paragraphs():
    provs = parse("""1. Scope
2. Definitions
2.1. First term means something.
2.2. Second term means something else.
2.3 "Third term" means yet another thing, which is a dotless paragraph.
2.4 Fourth term means the last one and the line is long enough to run past ninety characters in the source text.
3. Application
3.1. The application shall be accompanied by:
3.1.1. a detailed description of the device;
3.1.2. the length and width of the device;
3.1.3. above
3.2. Next paragraph.
""")
    got = labels(provs)
    assert "2.3" in got and "2.4" in got                       # dotless, quoted or long: still the next paragraph
    assert "3.1.1" in got and "3.1.2" in got                   # lower-case list items after "accompanied by:"
    assert "3.1.3" not in got and "3.2" in got                 # "above" is a wrapped reference, not a paragraph


def test_main_body_appendices_are_their_own_segments():
    provs = parse("""1. Scope
2. Definitions
3. Names and addresses
Appendix 1 List of standards
1. First standard
Appendix 2 Limits for radiated emission
1. Limit
Annex 1 Communication
""")
    got = labels(provs)
    for want in ("3", "Appendix 1", "Appendix 1 1", "Appendix 2", "Appendix 2 1", "Annex 1"):
        assert want in got, (want, got)


def test_form_fields_and_wrapped_references_are_not_retrieved_as_provisions():
    provs = parse("""1. Scope
2. Definitions
2.1. Trade name or mark ..........................................
2.2. A real paragraph, see paragraphs
2.3. (a) wrapped after the word paragraphs
2.4. Another real paragraph.
""")
    by = {p.paragraph: p for p in provs}
    assert by["2.1"].rationale                                   # a form field with dot leaders: kept, never retrieved
    assert "2.3" not in by and "(a) wrapped" in by["2.2"].text   # a number that follows "paragraphs" is a reference
    assert not by["2.4"].rationale


def test_unpunctuated_numbers_and_annexes_in_the_bumper_regulations():
    for reg, annexes in (("UN R32", 4), ("UN R26", 1), ("UN R42", 2)):
        v = next(x for x in base_versions() if x.regulation == reg)
        found = [p for p in provisions(reg, v.version_label) if p.number == "" and p.paragraph.startswith("Annex")]
        assert len({p.paragraph.split()[1] for p in found}) >= annexes, (reg, [p.paragraph for p in found])
    r26 = {p.paragraph for p in provisions("UN R26", next(x for x in base_versions() if x.regulation == "UN R26").version_label)}
    assert "2.4" in r26                                          # 2.4 "Floor line" means ... (dotless in the source)
