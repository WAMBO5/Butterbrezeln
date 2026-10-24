from pathlib import Path

from app.corpus.parser import iter_pages, normalize, paragraph_key, parse_regulation, squash

MINI = Path("tests/fixtures/mini_regulation.txt").read_text()


def by_label():
    return {p.paragraph: p for p in parse_regulation(MINI, "UN R999", "1.0.0", "base")}


def test_structure():
    by = by_label()
    assert by["5.1"].provision_id == "UN R999@1.0.0#5.1" and (by["5.1"].page_start, by["5.1"].page_end) == (2, 3)
    assert by["Annex 3 Part 1 1.2"].kind == "test_procedure"
    assert by["3.1"].kind == "requirement"
    assert all(p.kind == "form" for l, p in by.items() if l.startswith("Annex 1 "))
    assert "12" not in by and by["5.2"].text.endswith("(Reserved)")
    assert "field" in normalize(by["5.3"].text)
    assert "para:2.1" in by["5.1"].refs and "annex:3" in by["5.1"].refs
    assert all("version 1.0.0 | page" not in p.text for p in by.values())


def test_kinds_from_top_level_heading():
    by = by_label()
    assert by["1"].kind == "scope" and by["2.1"].kind == "definition"


def test_annex_headings_are_provisions():
    by = by_label()
    assert by["Annex 3"].heading_path == [] and "Annex 3 Part 1" in by
    assert by["Annex 3 Part 1 1.2"].heading_path[0].startswith("Annex 3")


def test_false_annex_lines_are_text():
    text = "=== PDF page 1 ===\n1. Scope\n1.1. The test shall follow\nAnnex 5 of this Regulation, and\nAnnex 3.and the rest.\n"
    by = {p.paragraph: p for p in parse_regulation(text, "UN R1", "1", "base")}
    assert set(by) == {"1", "1.1"} and "Annex 5 of this" in by["1.1"].text


def test_iter_pages_drops_header():
    pages = iter_pages(MINI)
    assert [n for n, _ in pages] == [1, 2, 3]
    assert not pages[1][1].startswith("UN R999, version")


def test_paragraph_key():
    assert paragraph_key("Annex 8, 2.1.") == paragraph_key("annex 8 2.1")
    assert paragraph_key("5.4.2.3") != paragraph_key("5.4.23")


def test_squash_ignores_whitespace_and_ligatures():
    assert squash("The ﬁeld  shall\nbe") == squash("the field shall be")
