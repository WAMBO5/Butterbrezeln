"""Text normalisation for matching. Raw text stays the source of every quote; this copy is only compared."""

from __future__ import annotations

import re
import unicodedata

_HYPHEN_BREAK = re.compile(r"(?<=[a-z])-\n(?=[a-z])")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS_SPACE = re.compile("(?<=\\d)[   ](?=\\d{3}\\b)")
_GLUED_TO_LETTERS = re.compile(r"(?<=[A-Za-z])\d+(?:[.,]\d+)*")  # M1, N2, R148, S3: identifiers, not quantities
_SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_TO_DIGIT = str.maketrans(_SUP + "⁻", "0123456789-")
_DOT = "∙·"  # bullet operator and middle dot, both used as the multiplication dot in "3.00.10^2"
# [mantissa x] 10^exp, written with a caret ("10^3", "1.2 x 10^-2") or a superscript exponent ("3.00.10" + superscript 2)
_POWER = re.compile(f"(?:(\\d+(?:[.,]\\d+)?)\\s*[{_DOT}×x*]\\s*)?10\\s*(?:\\^\\s*(-?\\d+)|([{_SUP}⁻]+))")
_FLAT_POWER = re.compile(f"(\\d+(?:[.,]\\d+)?)\\s*[{_DOT}]\\s*10(-?\\d)(?!\\d)")  # exponent flattened by PDF extraction


def normalise(text: str) -> str:
    """NFKC (ligatures, superscripts), joined hyphenated line breaks, unified quotes, dashes and dots, collapsed whitespace."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _HYPHEN_BREAK.sub("", text)
    text = (text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
            .replace("–", "-").replace("—", "-").replace("−", "-").replace("∙", "·"))
    return " ".join(text.split()).casefold()


def _canon(token: str) -> str:
    """"1,200" -> "1200", "0,5" -> "0.5", "3.00" -> "3", "0.50" -> "0.5"; dotted labels such as "6.9.1" are kept."""
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
        token = token.replace(",", "")
    token = token.replace(",", ".").rstrip(".")
    if re.fullmatch(r"\d+\.\d+", token):
        token = token.rstrip("0").rstrip(".")
    return token


def _tokens(text: str) -> set[str]:
    return {_canon(t) for t in _NUMBER.findall(text)}


def _fmt(value: float) -> str:
    return _canon(f"{value:.12f}".rstrip("0").rstrip(".") if abs(value) < 1e15 else f"{value:g}")


def _power_value(mantissa: str | None, exp: str) -> float | None:
    try:
        return (float(mantissa.replace(",", ".")) if mantissa else 1.0) * 10 ** int(exp)
    except (ValueError, OverflowError):
        return None


def _evaluate_powers(raw: str) -> str:
    """Replace every power of ten by its value: "1.2 x 10^3" and 1.2 times 10 with a superscript 3 both become "1200"."""
    def sub(m: re.Match) -> str:
        exp = m.group(2) if m.group(2) is not None else m.group(3).translate(_SUP_TO_DIGIT)
        value = _power_value(m.group(1), exp)
        return m.group(0) if value is None else _fmt(value)
    return _POWER.sub(sub, raw)


def _power_values(raw: str) -> set[str]:
    """Evaluated powers found in evidence text, including the spelling PDF extraction produces ("6.0.101" for 6.0 x 10^1)."""
    out: set[str] = set()
    for m in _POWER.finditer(raw):
        exp = m.group(2) if m.group(2) is not None else m.group(3).translate(_SUP_TO_DIGIT)
        value = _power_value(m.group(1), exp)
        if value is not None:
            out.add(_fmt(value))
    for mant, exp in _FLAT_POWER.findall(raw):
        value = _power_value(mant, exp)
        if value is not None:
            out.add(_fmt(value))
    return out


def numbers(text: str, evidence: bool = False, join: bool = True) -> set[str]:
    """Canonical numeric tokens of a text.

    Drafts (evidence=False): a power of ten is evaluated first, and a digit run glued to letters (M1, N2, R148) is an
    identifier, not a quantity, so it is skipped. join=True joins a thousands space: "1 200" and "1200" are one number.

    Evidence (evidence=True) is widened, never narrowed: it also keeps the un-joined tokens (a table row "1 102 min" still
    yields "1" and "102"), the exponent digits, and the evaluated value of every power of ten, however it was spelled."""
    raw = text or ""
    if evidence:
        flat = unicodedata.normalize("NFKC", raw)
        out = _tokens(_THOUSANDS_SPACE.sub("", flat) if join else flat) | _tokens(flat) | _power_values(raw)
        out |= {m.translate(_SUP_TO_DIGIT) for m in re.findall(f"10([{_SUP}]+)", raw)}
        return out
    flat = unicodedata.normalize("NFKC", _evaluate_powers(raw))
    flat = _GLUED_TO_LETTERS.sub("", flat)
    return _tokens(_THOUSANDS_SPACE.sub("", flat) if join else flat)


def number_sequence(text: str) -> list[str]:
    """Canonical numeric tokens in reading order (a thousands space joined), to compare a quote with the text it copies."""
    flat = _THOUSANDS_SPACE.sub("", unicodedata.normalize("NFKC", text or ""))
    return [_canon(t) for t in _NUMBER.findall(flat)]


def is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(any(n == h for h in it) for n in needle)


_STOPWORDS = frozenset("shall that with from this have been which their where when than also such into only each other these "
                       "those they them will would should must does not for and the are was has its any all may can per one two".split())


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", normalise(text)) if w not in _STOPWORDS}


def paragraph_key(paragraph: object) -> str | None:
    """Same key as tools/score_local.py `_paragraph_key`."""
    text = str(paragraph or "").casefold().replace("§", " ")
    text = re.sub(r"[,;:()\[\]]", " ", text)
    text = re.sub(r"(?<![0-9a-z])\.|\.(?![0-9a-z])", " ", text)
    text = " ".join(text.split())
    text = re.sub(r"^(paragraphs?|para|par|section|clause)\s+", "", text)
    return text or None
