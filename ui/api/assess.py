"""Spec-vs-requirement findings, per-country verdicts and per-country Q&A.

The LLM only classifies (finding status, effort of a fix); the traffic-light colour is computed by
`compute_status` so it is reproducible and explained in the trace.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import countries as country_data
from .llm import LLM, LLMError
from .models import (CountryVerdict, Effort, Finding, QAEntry, Regime, Requirement, RunResult, Source,
                     SpecNote, Suggestion, VerdictStatus)
from .sources import spec_source
from .spec import ParsedSpec
from .trace import TraceRecorder

EFFORT_LABEL = {
    "doku_kennzeichnung": "Unterlagen & Kennzeichnung",
    "pruefung_zertifizierung": "Prüfung & Zertifikat",
    "design": "Produktänderung",
}
STATUS_DE = {"green": "verkaufsbereit", "yellow": "fast verkaufsbereit", "red": "noch nicht verkaufsbereit",
             "grey": "ohne Daten"}


def compute_status(regime: Regime, efforts: list[Effort]) -> VerdictStatus:
    """grey: not covered; red: any fix needs a design change; yellow: only doc/marking or
    test/certification fixes; green: nothing to fix (open evidence does not change the colour)."""
    if regime == "not_covered":
        return "grey"
    if "design" in efforts:
        return "red"
    if efforts:
        return "yellow"
    return "green"


# --- spec assessment: rules ------------------------------------------------------------------

_NUMERIC = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:cd|mm|cm|°|degrees?|%|lx|nm|seconds?|minutes?|hours?|V\b|W\b|K\b)", re.IGNORECASE)
_MARKING = ("approval mark", "marking", "trade name", "trade mark", "legible", "indelible",
            "unique identifier", "approval number")
_RED = re.compile(r"\bred\b", re.IGNORECASE)
_WHITE = re.compile(r"\bwhite\b", re.IGNORECASE)
_REVERSING = re.compile(r"revers", re.IGNORECASE)


def _has_clear_zone(spec: ParsedSpec) -> bool:
    return spec.contains("white", "clear", "colourless", "colorless", "transparent")


def _rule_finding(req: Requirement, spec: ParsedSpec) -> tuple[str, str, list[int] | None]:
    text = req.text
    if _WHITE.search(text) and _REVERSING.search(text) and _RED.search(spec.text) and not _has_clear_zone(spec):
        return ("offen", "Das Rückfahrlicht muss weiß sein, die Produktbeschreibung nennt aber nur eine rot getönte "
                "Lichtscheibe – eine farblose Zone für den Rückfahrscheinwerfer fehlt.", spec.find("red-tinted", "red"))
    if _RED.search(text) and _RED.search(spec.text) and "colour" in text.lower():
        return "erfuellt", "Die Produktbeschreibung nennt eine rot getönte Lichtscheibe (Materialangabe).", spec.find("red")
    match = _NUMERIC.search(text)
    if match:
        return "offen", f"Grenzwert „{match.group(0).strip()}“: Messwert bzw. Prüfnachweis fehlt in der Produktbeschreibung.", None
    if any(k in text.lower() for k in _MARKING):
        return "offen", "Kennzeichnung bzw. Prüfzeichen ist in der Produktbeschreibung nicht beschrieben.", None
    return "offen", "Die Produktbeschreibung enthält dazu keine Angabe – im Rahmen der Typprüfung nachzuweisen.", None


def _rule_notes(spec: ParsedSpec, requirements: list[Requirement], trace_id: str) -> list[SpecNote]:
    notes: list[SpecNote] = []
    white_reversing = [r.id for r in requirements if _WHITE.search(r.text) and _REVERSING.search(r.text)]
    if _REVERSING.search(spec.text) and _RED.search(spec.text) and not _has_clear_zone(spec):
        notes.append(SpecNote(
            id="note-1",
            text=("Der Rückfahrscheinwerfer muss weißes Licht abgeben. Ihre Beschreibung nennt nur eine rot getönte "
                  "Lichtscheibe – ergänzen Sie unter „Materials“ eine farblose Zone für den Rückfahrscheinwerfer."),
            spec_lines=spec.find("red-tinted", "red"),
            requirement_ids=white_reversing,
            trace_ids=[trace_id],
        ))
    return notes


# --- spec assessment: LLM --------------------------------------------------------------------

_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["erfuellt", "offen", "konflikt"]},
                    "effort": {"type": "string", "enum": ["keine", "doku_kennzeichnung", "pruefung_zertifizierung", "design"]},
                    "first_line": {"type": "integer"},
                    "last_line": {"type": "integer"},
                    "explanation": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["requirement_id", "status", "effort", "first_line", "last_line", "explanation", "suggestion"],
                "additionalProperties": False,
            },
        },
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "first_line": {"type": "integer"},
                    "last_line": {"type": "integer"},
                    "requirement_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "first_line", "last_line", "requirement_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["findings", "notes"],
    "additionalProperties": False,
}

_FINDINGS_SYSTEM = """Du bist Homologationsingenieur für Fahrzeugbeleuchtung. Du vergleichst eine Produktspezifikation (spec.md, mit Zeilennummern) mit Anforderungen aus einer UN-Regelung.

Gib für jede Anforderung genau ein Finding zurück:
- status "erfuellt": die Spec belegt ausdrücklich, dass die Anforderung erfüllt ist.
- status "offen": die Spec sagt dazu nichts oder nicht genug; ein Nachweis (Messung, Prüfung, Kennzeichnung) steht aus. Das ist der Normalfall bei fehlenden Messwerten.
- status "konflikt": die Spec widerspricht der Anforderung ausdrücklich.
- effort: nur bei "konflikt" einer von doku_kennzeichnung (nur Dokumentation/Kennzeichnung ändern), pruefung_zertifizierung (zusätzliche Prüfung/Zulassung), design (Funktion, Material, Farbe oder Geometrie des Produkts muss sich ändern); sonst "keine".
- first_line/last_line: die Spec-Zeilen, auf die du dich stützt; 0 wenn keine.
- explanation: ein kurzer Satz auf Deutsch, auch für Nicht-Fachleute verständlich.
- suggestion: bei "konflikt" die konkrete Änderung an der Spec (Deutsch, Infinitiv-Stil wie „Farblose Zone für den Rückfahrscheinwerfer ergänzen“); sonst "".

Unter notes nennst du höchstens drei Unklarheiten der Spec, die mehrere Anforderungen betreffen (z. B. widersprüchliche Materialangaben). Erfinde keine Fakten über das Produkt."""


def _llm_findings(spec: ParsedSpec, regulation: str, group: list[Requirement], llm: LLM) -> tuple[dict, dict]:
    listing = "\n".join(f"[{r.id}] ({r.source.label}) {r.text}" for r in group)
    user = f"spec.md:\n{spec.numbered()}\n\nAnforderungen aus {regulation}:\n{listing}"
    return llm.json(system=_FINDINGS_SYSTEM, user=user, schema=_FINDINGS_SCHEMA, effort="low")


def _lines(first: int, last: int, spec: ParsedSpec) -> list[int] | None:
    if first <= 0 or first > len(spec.lines):
        return None
    return [first, max(first, min(last, len(spec.lines)))]


def assess_spec(spec: ParsedSpec, requirements: list[Requirement], llm: LLM, trace: TraceRecorder,
                parent: str) -> tuple[list[Finding], list[SpecNote], str]:
    """(findings, spec notes, mode) where mode is 'llm', 'rules' or 'mixed'."""
    groups: OrderedDict[str, list[Requirement]] = OrderedDict()
    for r in requirements:
        groups.setdefault(r.source.regulation or "?", []).append(r)

    def run_group(regulation: str, group: list[Requirement]) -> tuple[list[Finding], list[SpecNote], str]:
        with trace.step("spec_assessor", f"Spec-Abgleich {regulation}", parent=parent,
                        inputs_summary=f"spec.md ({len(spec.lines)} Zeilen) × {len(group)} Anforderungen",
                        tags={"regulation": regulation}) as step:
            step.add_source(spec_source(spec.name, [1, len(spec.lines)]))
            by_id = {r.id: r for r in group}
            findings: list[Finding] = []
            notes: list[SpecNote] = []
            mode = "rules"
            try:
                data, meta = _llm_findings(spec, regulation, group, llm)
                step.set_llm(meta["model"], meta["prompt"], meta["tokens"])
                mode = "llm"
                for item in data["findings"]:
                    req = by_id.get(item["requirement_id"])
                    if req is None or any(f.requirement_id == req.id for f in findings):
                        continue
                    status = item["status"]
                    effort = item["effort"] if status == "konflikt" and item["effort"] != "keine" else None
                    findings.append(Finding(
                        id=f"fd-{req.id}", requirement_id=req.id, regulation=regulation, status=status,
                        effort=effort or ("design" if status == "konflikt" else None),
                        spec_lines=_lines(item["first_line"], item["last_line"], spec),
                        explanation=item["explanation"], suggestion=item["suggestion"] or None,
                        trace_ids=[step.id],
                    ))
                for n, item in enumerate(data["notes"], start=1):
                    notes.append(SpecNote(
                        id=f"note-{regulation}-{n}", text=item["text"],
                        spec_lines=_lines(item["first_line"], item["last_line"], spec),
                        requirement_ids=[i for i in item["requirement_ids"] if i in by_id], trace_ids=[step.id],
                    ))
            except LLMError as exc:
                step.fallback(str(exc))
            covered = {f.requirement_id for f in findings}
            missing = [r for r in group if r.id not in covered]
            for req in missing:
                status, explanation, lines = _rule_finding(req, spec)
                findings.append(Finding(id=f"fd-{req.id}", requirement_id=req.id, regulation=regulation,
                                        status=status, spec_lines=lines, explanation=explanation,
                                        trace_ids=[step.id]))
            if mode == "llm" and missing:
                mode = "mixed"
            counts = {s: sum(f.status == s for f in findings) for s in ("erfuellt", "offen", "konflikt")}
            step.output(f"erfüllt {counts['erfuellt']}, offen {counts['offen']}, Konflikt {counts['konflikt']}"
                        + (" (Regelwerk)" if mode == "rules" else ""))
            return findings, notes, mode

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda kv: run_group(*kv), groups.items()))

    findings = [f for fs, _, _ in results for f in fs]
    notes = [n for _, ns, _ in results for n in ns]
    modes = {m for _, _, m in results}
    if "llm" not in modes and "mixed" not in modes:
        notes = _rule_notes(spec, requirements, parent)
    mode = "llm" if modes == {"llm"} else "rules" if modes == {"rules"} else "mixed"
    return findings, notes, mode


# --- country verdicts ------------------------------------------------------------------------

def _check_applies(check: dict[str, Any] | None, spec: ParsedSpec) -> bool:
    check = check or {"type": "always"}
    kind = check.get("type", "always")
    keywords = check.get("keywords") or []
    if kind == "spec_missing":
        return not spec.contains(*keywords)
    if kind == "spec_contains":
        return spec.contains(*keywords)
    return True


def _profile_fits(covers: dict[str, Any], spec: ParsedSpec, cited: list[str]) -> bool:
    """A country profile is researched for one product: the spec's title must name it and the requirements
    must cite one of its regulations (a front bumper with side lamps cites UN R148 but is no rear lamp)."""
    products = [p.lower() for p in covers.get("products") or []]
    regulations = covers.get("regulations") or []
    return ((not products or any(p in spec.title.lower() for p in products))
            and (not regulations or bool(set(regulations) & set(cited))))


def _dataset_source(iso3: str, entry: dict[str, Any]) -> Source:
    url = entry.get("source_url")
    return Source(kind="dataset", label="Offizielle UN-Vertragsliste", title=f"data/countries.json: {iso3}",
                  url=url, href=url, in_certivity_corpus=False)


def _section_of(spec: ParsedSpec, lines: list[int] | None) -> str:
    if lines:
        for s in spec.sections:
            if s.first <= lines[0] <= s.last:
                return s.title
    return "Spec"


def assess_country(iso3: str, spec: ParsedSpec, requirements: list[Requirement], findings: list[Finding],
                   trace: TraceRecorder, parent: str) -> CountryVerdict:
    entry = country_data.country(iso3)
    prof = country_data.profile(iso3) if entry and entry.get("profile") else None
    name = (entry or {}).get("name_de") or (prof or {}).get("name_de") or iso3
    req_by_id = {r.id: r for r in requirements}
    cited = sorted({r.source.regulation for r in requirements if r.source.regulation})
    conflicts = [f for f in findings if f.status == "konflikt"]
    open_count = sum(f.status == "offen" for f in findings)

    with trace.step("country_assessor", f"Länderurteil {name}", parent=parent,
                    inputs_summary=f"{len(cited)} zitierte Regelungen, {len(conflicts)} Konflikte, {open_count} offene Nachweise",
                    tags={"country": iso3}) as step:
        reasons: list[str] = []
        suggestions: list[Suggestion] = []
        sources: list[Source] = []

        def suggest(**kw) -> None:
            suggestions.append(Suggestion(id=f"sg-{iso3}-{len(suggestions) + 1}", country=iso3,
                                          trace_ids=[step.id], **kw))

        covers = (prof or {}).get("covers") or {}
        if entry is None or (entry.get("regime") == "national" and prof is None):
            regime: Regime = "not_covered"
            reasons.append(f"Für {name} haben wir noch keine Daten – ohne Länderprofil ist keine verlässliche Aussage möglich.")
            if entry:
                sources.append(_dataset_source(iso3, entry))
        elif entry.get("regime") == "national" and not _profile_fits(covers, spec, cited):
            # the profile was researched for another product: its deviations would not fit this one
            regime = "not_covered"
            reasons.append(f"Unser Länderprofil für {name} ist bisher nur für {covers.get('product_de', 'andere Produkte')} "
                           "recherchiert – für dieses Produkt liegen noch keine Daten vor.")
            sources.append(_dataset_source(iso3, entry))
        elif entry.get("regime") == "unece_1958" or (prof or {}).get("accepts_un_approvals"):
            regime = "unece_1958"
            sources.append(_dataset_source(iso3, entry))
            reasons.append(f"{name} erkennt die internationalen UN-Fahrzeugvorschriften an (UNECE-Abkommen von 1958). "
                           "Eine UN-Zulassung gilt hier.")
            applied = entry.get("applied_regulations", "unverified")
            if isinstance(applied, list):
                researched = country_data.researched_regulations()
                for regulation in cited:
                    if regulation in researched and regulation not in applied:
                        suggest(spec_section="Zertifizierung",
                                change=f"Zulassungsweg für die Anforderungen aus {regulation} in {name} klären (nationale Prüfung statt UN-Genehmigung).",
                                reason=f"{name} wendet {regulation} laut UNECE-Statusdokument nicht an.",
                                effort="pruefung_zertifizierung", sources=[_dataset_source(iso3, entry)])
                unchecked = [r for r in cited if r not in researched]
                if unchecked:
                    reasons.append(f"Ob {name} auch {', '.join(unchecked)} anwendet, ist noch nicht geprüft – wir gehen davon aus.")
            elif applied == "unverified":
                reasons.append(f"Ob {name} jede einzelne der genannten Vorschriften anwendet, ist noch nicht geprüft – wir gehen davon aus.")
        else:
            regime = "national"
            sources.append(_dataset_source(iso3, entry))
            sources.append(Source(kind="country_profile", label=f"Recherchiertes Länderprofil {name}",
                                  title=f"data/country_profiles/{iso3}.json", in_certivity_corpus=False))
            if prof.get("summary_de"):
                reasons.append(prof["summary_de"])
            cert = prof.get("certification") or {}
            if cert.get("summary_de"):
                reasons.append(cert["summary_de"])
            for dev in prof.get("deviations", []):
                if dev.get("un_reference") and dev["un_reference"] not in cited:
                    continue  # deviates from a regulation this product does not fall under
                if not _check_applies(dev.get("check"), spec):
                    continue
                url = dev.get("source_url")
                src = Source(kind="external", label=f"{dev.get('id')}: {dev.get('topic_de', '')}".strip(),
                             url=url, href=url, in_certivity_corpus=False)
                if dev.get("un_reference"):
                    reason = f"{dev.get('national_requirement_de', '')} (Bezug: {dev['un_reference']})"
                else:
                    reason = dev.get("national_requirement_de", "")
                suggest(deviation_id=dev.get("id"), spec_section=dev.get("spec_section", "Spec"),
                        change=dev.get("suggestion_de", ""), reason=reason,
                        effort=dev.get("effort", "pruefung_zertifizierung"), sources=[src])
                if dev.get("verified") is False:
                    suggestions[-1].reason += " (Quelle nicht verifiziert)"

        if regime != "not_covered":
            for f in conflicts:
                req = req_by_id.get(f.requirement_id)
                ref = f"UN-Anforderung {req.source.label}" if req else f.requirement_id
                note = "" if regime == "unece_1958" else " UN-Anforderung als Referenz; gleichwertige nationale Norm prüfen."
                suggest(requirement_id=f.requirement_id, spec_section=_section_of(spec, f.spec_lines),
                        change=f.suggestion or f"Produkt so anpassen, dass {ref} erfüllt ist.",
                        reason=f.explanation + note, effort=f.effort or "design",
                        sources=[req.source] if req else [])

        efforts = [s.effort for s in suggestions]
        status = compute_status(regime, efforts)
        if status == "green":
            reasons.append(f"Keine Änderungen nötig. Wie bei jeder Zulassung sind {open_count} Prüfnachweise zu erbringen.")
        elif status != "grey":
            worst = "design" if "design" in efforts else "pruefung_zertifizierung" if "pruefung_zertifizierung" in efforts else "doku_kennzeichnung"
            steps = "1 Schritt" if len(suggestions) == 1 else f"{len(suggestions)} Schritte"
            reasons.append(f"{steps} bis zur Freigabe; größter Aufwand: {EFFORT_LABEL[worst]}.")
        for s in sources:
            step.add_source(s)
        step.output(f"Status {status} · {len(suggestions)} Vorschläge")
        return CountryVerdict(
            iso3=iso3, name_de=name, status=status, regime=regime, reasons=reasons,
            blocking_finding_ids=[f.id for f in conflicts] if regime != "not_covered" else [],
            open_evidence_count=open_count if regime != "not_covered" else 0,
            suggestions=suggestions, sources=sources, trace_ids=[step.id],
        )


# --- per-country questions -------------------------------------------------------------------

_ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "spec_section": {"type": "string"},
                    "change": {"type": "string"},
                    "reason": {"type": "string"},
                    "effort": {"type": "string", "enum": ["doku_kennzeichnung", "pruefung_zertifizierung", "design"]},
                    "requirement_id": {"type": "string"},
                    "deviation_id": {"type": "string"},
                },
                "required": ["spec_section", "change", "reason", "effort", "requirement_id", "deviation_id"],
                "additionalProperties": False,
            },
        },
        "cited_requirement_ids": {"type": "array", "items": {"type": "string"}},
        "cited_deviation_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "suggestions", "cited_requirement_ids", "cited_deviation_ids"],
    "additionalProperties": False,
}

_ASK_SYSTEM = """Du bist Homologationsexperte und beantwortest die Frage eines Engineers zu einem Zielland. Grundlage ist ausschließlich der Kontext: das Länderurteil, das Länderprofil (falls vorhanden), die Spezifikation und die abgeleiteten Anforderungen.

- Antworte auf Deutsch, konkret und knapp (höchstens 8 Sätze), in einfachen Worten ohne Fachjargon; sprich die Person mit „Sie“ an.
- Nenne, was sich an der Spezifikation oder am Zulassungsweg ändern muss, damit das Produkt im Land zulässig ist.
- Referenziere Anforderungen und Abweichungen nur über IDs aus dem Kontext (cited_requirement_ids, cited_deviation_ids). Erfinde keine Normen, Paragraphen oder Werte.
- Reicht der Kontext nicht aus, sag das ausdrücklich und nenne, welche Information fehlt.
- suggestions: nur neue, konkrete Änderungen, die noch nicht im Länderurteil stehen, im Infinitiv-Stil (z. B. „CCC-Zeichen im Gehäuse vorsehen“); requirement_id/deviation_id "" wenn keine passt."""


def _rule_answer(verdict: CountryVerdict, question: str) -> str:
    by_effort: dict[str, list[Suggestion]] = {}
    for s in verdict.suggestions:
        by_effort.setdefault(s.effort, []).append(s)
    if verdict.status == "grey":
        return (f"Für {verdict.name_de} haben wir noch keine Daten. "
                "Ohne Länderprofil können wir keine verlässliche Aussage machen.")
    parts = [f"{verdict.name_de}: Ihr Produkt ist {STATUS_DE[verdict.status]}."]
    if not verdict.suggestions:
        parts.append("Am Produkt muss nichts geändert werden. "
                     f"Wie bei jeder Zulassung sind {verdict.open_evidence_count} Prüfnachweise (Messungen, Tests) zu erbringen.")
    for effort in ("design", "pruefung_zertifizierung", "doku_kennzeichnung"):
        items = by_effort.get(effort, [])
        if items:
            parts.append(f"\n{EFFORT_LABEL[effort]}:\n" + "\n".join(f"{i + 1}. {s.change}" for i, s in enumerate(items)))
    parts.append("\n(Antwort aus den hinterlegten Regeln – der KI-Assistent ist nicht verbunden.)")
    return " ".join(parts)


def ask_country(run: RunResult, spec: ParsedSpec, iso3: str, question: str, llm: LLM,
                trace: TraceRecorder) -> QAEntry:
    verdict = run.verdicts[iso3]
    prof = country_data.profile(iso3)
    req_by_id = {r.id: r for r in run.requirements}
    with trace.step("qa_agent", f"Frage zu {verdict.name_de}", inputs_summary=question,
                    tags={"country": iso3}) as step:
        new_suggestions: list[Suggestion] = []
        sources: list[Source] = []
        try:
            context = {
                "land": {"iso3": iso3, "name": verdict.name_de, "status": verdict.status, "regime": verdict.regime,
                         "begruendung": verdict.reasons,
                         "vorschlaege": [s.model_dump(include={"change", "reason", "effort", "deviation_id", "requirement_id"})
                                         for s in verdict.suggestions]},
                "laenderprofil": prof,
                "anforderungen": [{"id": r.id, "quelle": r.source.label, "text": r.text} for r in run.requirements],
            }
            user = (f"Kontext (JSON):\n{json.dumps(context, ensure_ascii=False)}\n\nspec.md:\n{spec.numbered()}"
                    f"\n\nFrage des Engineers: {question}")
            data, meta = llm.json(system=_ASK_SYSTEM, user=user, schema=_ASK_SCHEMA, effort="low")
            step.set_llm(meta["model"], meta["prompt"], meta["tokens"])
            answer = data["answer"]
            deviations = {d.get("id"): d for d in (prof or {}).get("deviations", [])}
            for rid in data["cited_requirement_ids"]:
                if rid in req_by_id:
                    sources.append(req_by_id[rid].source)
            for did in data["cited_deviation_ids"]:
                dev = deviations.get(did)
                if dev:
                    sources.append(Source(kind="external", label=f"{did}: {dev.get('topic_de', '')}",
                                          url=dev.get("source_url"), href=dev.get("source_url")))
            for item in data["suggestions"]:
                req = req_by_id.get(item["requirement_id"])
                new_suggestions.append(Suggestion(
                    id=f"sg-{iso3}-{len(verdict.suggestions) + len(new_suggestions) + 1}", country=iso3,
                    requirement_id=req.id if req else None, deviation_id=item["deviation_id"] or None,
                    spec_section=item["spec_section"], change=item["change"], reason=item["reason"],
                    effort=item["effort"], sources=[req.source] if req else [], trace_ids=[step.id],
                ))
        except LLMError as exc:
            step.fallback(str(exc))
            answer = _rule_answer(verdict, question)
            sources = [src for s in verdict.suggestions for src in s.sources]
        for s in sources:
            step.add_source(s)
        step.output(answer[:280])
        verdict.suggestions.extend(new_suggestions)
        return QAEntry(id=f"qa-{len(run.qa) + 1}", country=iso3, question=question, answer=answer,
                       suggestion_ids=[s.id for s in new_suggestions], sources=sources, trace_ids=[step.id])
