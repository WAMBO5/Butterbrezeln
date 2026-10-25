import type { LucideIcon } from "lucide-react";
import { CircleCheck, CircleHelp, CircleX, Cog, FileText, FlaskConical, ListChecks, Sparkles, TriangleAlert, User, Wrench } from "lucide-react";
import type { Effort, FindingStatus, TraceEvent, VerdictStatus } from "../types";
import { AGENTS, agentOf } from "./agents";

interface StatusStyle {
  label: string;
  desc: string;
  color: string; // map fill, dots and glow
  soft: string; // tinted background
  ring: string;
  text: string;
  icon: LucideIcon;
}

export const STATUS: Record<VerdictStatus, StatusStyle> = {
  green: {
    label: "Verkaufsbereit",
    desc: "Ihr Produkt kann hier verkauft werden.",
    color: "#34d399",
    soft: "bg-emerald-400/10",
    ring: "ring-emerald-400/30",
    text: "text-emerald-300",
    icon: CircleCheck,
  },
  yellow: {
    label: "Fast verkaufsbereit",
    desc: "Fast geschafft – es fehlen nur Unterlagen, Kennzeichnung oder Prüfungen.",
    color: "#fbbf24",
    soft: "bg-amber-400/10",
    ring: "ring-amber-400/30",
    text: "text-amber-300",
    icon: TriangleAlert,
  },
  red: {
    label: "Produkt anpassen",
    desc: "Damit es hier verkauft werden darf, muss das Produkt selbst geändert werden.",
    color: "#fb7185",
    soft: "bg-rose-400/10",
    ring: "ring-rose-400/30",
    text: "text-rose-300",
    icon: CircleX,
  },
  grey: {
    label: "Keine Daten",
    desc: "Für dieses Land haben wir noch keine Daten.",
    color: "#64748b",
    soft: "bg-slate-400/10",
    ring: "ring-slate-400/20",
    text: "text-slate-300",
    icon: CircleHelp,
  },
};

export const STATUS_ORDER: VerdictStatus[] = ["green", "yellow", "red", "grey"];

/** Map fills outside the traffic light. */
export const UNTESTED_FILL = "#141d33";
export const KNOWN_FILL = "#1d2a47"; // we have data for this country
export const PENDING_FILL = "#25406b"; // chosen, not assessed yet
export const SELECTED_FILL = "#22d3ee";

/** What the colours mean, in one line each (map legend). */
export const RULE: Record<VerdictStatus, string> = {
  green: "Nichts zu ändern",
  yellow: "Nur Unterlagen oder Prüfungen",
  red: "Produkt muss geändert werden",
  grey: "Keine Daten",
};

export const EFFORT: Record<Effort, { label: string; desc: string; icon: LucideIcon; color: string; chip: string; iconBg: string }> = {
  doku_kennzeichnung: {
    label: "Unterlagen & Kennzeichnung",
    desc: "kleiner Aufwand",
    icon: FileText,
    color: "#38bdf8",
    chip: "bg-sky-400/10 text-sky-300 ring-sky-400/25",
    iconBg: "bg-sky-400/15 text-sky-300",
  },
  pruefung_zertifizierung: {
    label: "Prüfung & Zertifikat",
    desc: "mittlerer Aufwand",
    icon: FlaskConical,
    color: "#fbbf24",
    chip: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
    iconBg: "bg-amber-400/15 text-amber-300",
  },
  design: {
    label: "Produktänderung",
    desc: "großer Aufwand",
    icon: Wrench,
    color: "#fb7185",
    chip: "bg-rose-400/10 text-rose-300 ring-rose-400/25",
    iconBg: "bg-rose-400/15 text-rose-300",
  },
};

/** Biggest effort first: a product change is what blocks a market. */
export const EFFORT_ORDER: Effort[] = ["design", "pruefung_zertifizierung", "doku_kennzeichnung"];
export const byEffort = <T extends { effort: Effort }>(a: T, b: T) => EFFORT_ORDER.indexOf(a.effort) - EFFORT_ORDER.indexOf(b.effort);

export const FINDING: Record<FindingStatus, { label: string; chip: string; color: string }> = {
  erfuellt: { label: "Erfüllt", chip: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25", color: "#34d399" },
  offen: { label: "Nachweis nötig", chip: "bg-slate-400/10 text-slate-300 ring-slate-400/20", color: "#94a3b8" },
  konflikt: { label: "Widerspruch", chip: "bg-rose-400/10 text-rose-300 ring-rose-400/25", color: "#fb7185" },
};

/** How sure the pipeline is that a requirement applies; only the unsure case gets a badge. */
export const UNSURE = {
  label: "Gilt vielleicht",
  desc: "Ob diese Anforderung gilt, hängt von Angaben ab, die in Ihrer Beschreibung fehlen.",
  chip: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
};

/** How a logged step was done, in words a non-engineer understands. */
export function actorOf(e: TraceEvent): { label: string; icon: LucideIcon } {
  if (e.agent === "human_review") return { label: "Mensch", icon: User };
  if (e.model || e.tags.source === "pipeline") return { label: "KI", icon: Sparkles };
  if (e.status === "fallback" || e.agent === "spec_assessor" || e.agent === "country_assessor" || e.agent === "qa_agent")
    return { label: "Regelprüfung", icon: ListChecks };
  return { label: "Automatisch", icon: Cog };
}

export function agentLabel(agent: string): string {
  return `${AGENTS[agentOf(agent)].name}${agent.includes("(mock)") ? " (Demo)" : ""}`;
}

const REGULATION_DE: Record<string, string> = {
  "UN R3": "Rückstrahler",
  "UN R6": "Blinker",
  "UN R7": "Begrenzungs-, Brems- und Umrissleuchten",
  "UN R10": "Elektromagnetische Verträglichkeit",
  "UN R19": "Nebelscheinwerfer",
  "UN R23": "Rückfahrscheinwerfer",
  "UN R26": "Vorstehende Außenkanten",
  "UN R38": "Nebelschlussleuchten",
  "UN R42": "Stoßfänger vorn und hinten",
  "UN R43": "Sicherheitsglas",
  "UN R48": "Anbau der Beleuchtung am Fahrzeug",
  "UN R94": "Schutz beim Frontalaufprall",
  "UN R104": "Reflektierende Markierungen",
  "UN R123": "Adaptive Scheinwerfer",
  "UN R127": "Fußgängerschutz",
  "UN R128": "LED-Lichtquellen",
  "UN R148": "Signalleuchten (Schluss-, Brems-, Rückfahrlicht)",
  "UN R149": "Scheinwerfer",
  "UN R150": "Rückstrahler & Reflexmarkierungen",
  "UN R155": "Cybersicherheit",
  "UN R156": "Software-Updates",
  "UN GTR 9": "Fußgängerschutz (weltweite Regelung)",
};

/** Plain German name of a UN Regulation, falling back to its English title. */
export function regulationName(code: string | null | undefined, title?: string | null): string {
  if (!code) return title ?? "Vorschrift";
  return REGULATION_DE[code] ?? title ?? code;
}

const SECTION_DE: Record<string, string> = {
  "product type": "Produkttyp",
  "vehicle category": "Fahrzeugklasse",
  function: "Funktionen",
  functions: "Funktionen",
  "main parts": "Bauteile",
  parts: "Bauteile",
  materials: "Materialien",
};

export function sectionName(title: string): string {
  return SECTION_DE[title.toLowerCase()] ?? title;
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}
