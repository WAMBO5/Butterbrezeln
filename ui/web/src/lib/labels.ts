import type { LucideIcon } from "lucide-react";
import { CircleCheck, CircleHelp, CircleX, Cog, FileText, FlaskConical, ListChecks, Sparkles, TriangleAlert, User, Wrench } from "lucide-react";
import type { Effort, FindingStatus, TraceEvent, VerdictStatus } from "../types";
import { AGENTS, agentOf } from "./agents";

interface StatusStyle {
  label: string;
  desc: string;
  color: string; // map fill and dots
  soft: string; // tinted background
  ring: string;
  text: string;
  icon: LucideIcon;
}

export const STATUS: Record<VerdictStatus, StatusStyle> = {
  green: {
    label: "Ready to sell",
    desc: "Your product can be sold here.",
    color: "#1fb381",
    soft: "bg-emerald-50",
    ring: "ring-emerald-600/20",
    text: "text-emerald-700",
    icon: CircleCheck,
  },
  yellow: {
    label: "Almost ready",
    desc: "Nearly there – only documents, labelling or tests are missing.",
    color: "#f0b429",
    soft: "bg-amber-50",
    ring: "ring-amber-600/25",
    text: "text-amber-700",
    icon: TriangleAlert,
  },
  red: {
    label: "Change product",
    desc: "The product itself has to change before it may be sold here.",
    color: "#f2545b",
    soft: "bg-rose-50",
    ring: "ring-rose-600/20",
    text: "text-rose-700",
    icon: CircleX,
  },
  grey: {
    label: "No data",
    desc: "We have no data for this country yet.",
    color: "#a0b9b7",
    soft: "bg-mint-900/[0.05]",
    ring: "ring-mint-900/10",
    text: "text-mint-900/70",
    icon: CircleHelp,
  },
};

export const STATUS_ORDER: VerdictStatus[] = ["green", "yellow", "red", "grey"];

/** Map fills outside the traffic light. */
export const UNTESTED_FILL = "#dde6e5";
export const KNOWN_FILL = "#c2d4d2"; // we have data for this country
export const PENDING_FILL = "#93b6b2"; // chosen, not assessed yet
export const SELECTED_FILL = "#11504b";

/** What the colours mean, in one line each (map legend). */
export const RULE: Record<VerdictStatus, string> = {
  green: "Nothing to change",
  yellow: "Only documents or tests",
  red: "Product must change",
  grey: "No data",
};

export const EFFORT: Record<Effort, { label: string; desc: string; icon: LucideIcon; color: string; chip: string; iconBg: string }> = {
  documentation: {
    label: "Documents & labelling",
    desc: "small effort",
    icon: FileText,
    color: "#2f80c9",
    chip: "bg-sky-50 text-sky-700 ring-sky-600/20",
    iconBg: "bg-sky-100 text-sky-700",
  },
  testing: {
    label: "Testing & certificate",
    desc: "medium effort",
    icon: FlaskConical,
    color: "#d99a0b",
    chip: "bg-amber-50 text-amber-700 ring-amber-600/25",
    iconBg: "bg-amber-100 text-amber-700",
  },
  design: {
    label: "Product change",
    desc: "large effort",
    icon: Wrench,
    color: "#e0444c",
    chip: "bg-rose-50 text-rose-700 ring-rose-600/20",
    iconBg: "bg-rose-100 text-rose-700",
  },
};

/** Biggest effort first: a product change is what blocks a market. */
export const EFFORT_ORDER: Effort[] = ["design", "testing", "documentation"];
export const byEffort = <T extends { effort: Effort }>(a: T, b: T) => EFFORT_ORDER.indexOf(a.effort) - EFFORT_ORDER.indexOf(b.effort);

export const FINDING: Record<FindingStatus, { label: string; chip: string; color: string }> = {
  met: { label: "Met", chip: "bg-emerald-50 text-emerald-700 ring-emerald-600/20", color: "#1fb381" },
  open: { label: "Evidence needed", chip: "bg-mint-900/[0.05] text-mint-900/75 ring-mint-900/10", color: "#a0b9b7" },
  conflict: { label: "Conflict", chip: "bg-rose-50 text-rose-700 ring-rose-600/20", color: "#f2545b" },
};

/** How sure the pipeline is that a requirement applies; only the unsure case gets a badge. */
export const UNSURE = {
  label: "May apply",
  desc: "Whether this requirement applies depends on details missing from your description.",
  chip: "bg-amber-50 text-amber-700 ring-amber-600/25",
};

/** A logged human decision (runs saved by older versions logged it in German). */
export const isAccepted = (action: string) => /accepted|accepted/i.test(action);

/** How a logged step was done, in words a non-engineer understands. */
export function actorOf(e: TraceEvent): { label: string; icon: LucideIcon } {
  if (e.agent === "human_review") return { label: "Human", icon: User };
  if (e.model || e.tags.source === "pipeline") return { label: "AI", icon: Sparkles };
  if (e.status === "fallback" || e.agent === "spec_assessor" || e.agent === "country_assessor" || e.agent === "qa_agent")
    return { label: "Rule check", icon: ListChecks };
  return { label: "Automatic", icon: Cog };
}

export function agentLabel(agent: string): string {
  return `${AGENTS[agentOf(agent)].name}${agent.includes("(mock)") ? " (demo)" : ""}`;
}

const REGULATION_EN: Record<string, string> = {
  "UN R3": "Retro-reflectors",
  "UN R6": "Direction indicators",
  "UN R7": "Position, stop and end-outline lamps",
  "UN R10": "Electromagnetic compatibility",
  "UN R19": "Front fog lamps",
  "UN R23": "Reversing lamps",
  "UN R26": "External projections",
  "UN R38": "Rear fog lamps",
  "UN R42": "Front and rear protective devices",
  "UN R43": "Safety glazing",
  "UN R48": "Installation of lighting devices",
  "UN R94": "Frontal collision protection",
  "UN R104": "Retro-reflective markings",
  "UN R123": "Adaptive front-lighting systems",
  "UN R127": "Pedestrian safety",
  "UN R128": "LED light sources",
  "UN R148": "Light-signalling devices",
  "UN R149": "Road illumination devices",
  "UN R150": "Retro-reflective devices and markings",
  "UN R155": "Cyber security",
  "UN R156": "Software updates",
  "UN GTR 9": "Pedestrian safety (global regulation)",
};

/** Plain name of a UN Regulation, falling back to its official title. */
export function regulationName(code: string | null | undefined, title?: string | null): string {
  if (!code) return title ?? "Regulation";
  return REGULATION_EN[code] ?? title ?? code;
}

const SECTION_EN: Record<string, string> = {
  "product type": "Product type",
  "vehicle category": "Vehicle category",
  function: "Functions",
  functions: "Functions",
  "main parts": "Parts",
  parts: "Parts",
  materials: "Materials",
};

export function sectionName(title: string): string {
  return SECTION_EN[title.toLowerCase()] ?? title;
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}
