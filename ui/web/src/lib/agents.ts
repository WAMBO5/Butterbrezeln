import type { LucideIcon } from "lucide-react";
import { Cog, FileText, Globe, MessageCircle, Scale, Search, ShieldCheck, User } from "lucide-react";

/** The characters the jury sees; each maps to one or more logged pipeline steps. */
export type AgentKind = "reader" | "researcher" | "checker" | "matcher" | "scout" | "assistant" | "human" | "system";

export interface AgentInfo {
  name: string;
  does: string; // what it does, in one line
  color: string;
  icon: LucideIcon;
  magnifier?: boolean; // carries the magnifying glass
}

export const AGENTS: Record<AgentKind, AgentInfo> = {
  reader: { name: "Lese-Agent", does: "liest Ihre Produktbeschreibung", color: "#22d3ee", icon: FileText },
  researcher: { name: "Recherche-Agent", does: "sucht die passenden Vorschriften", color: "#a78bfa", icon: Search, magnifier: true },
  checker: { name: "Prüf-Agent", does: "belegt jede Anforderung mit ihrer Fundstelle", color: "#60a5fa", icon: ShieldCheck },
  matcher: { name: "Abgleich-Agent", does: "vergleicht Ihr Produkt mit jeder Anforderung", color: "#f472b6", icon: Scale },
  scout: { name: "Länder-Agent", does: "bewertet jedes Zielland", color: "#2dd4bf", icon: Globe, magnifier: true },
  assistant: { name: "Assistent", does: "beantwortet Ihre Fragen", color: "#818cf8", icon: MessageCircle },
  human: { name: "Mensch", does: "prüft und entscheidet", color: "#e2e8f0", icon: User },
  system: { name: "Ablaufsteuerung", does: "koordiniert die Agenten", color: "#94a3b8", icon: Cog },
};

/** The pipeline in the order the agents work. */
export const PIPELINE: AgentKind[] = ["reader", "researcher", "checker", "matcher", "scout"];

const BY_TRACE_AGENT: Record<string, AgentKind> = {
  orchestrator: "system",
  spec_parser: "reader",
  requirements_engine: "researcher",
  validator: "checker",
  spec_assessor: "matcher",
  country_assessor: "scout",
  qa_agent: "assistant",
  human_review: "human",
  // steps of a certivity pipeline run (BACKEND_MODE=runs)
  pipeline: "system",
  product_analyst: "reader",
  profile_verifier: "reader",
  scope_narrower: "researcher",
  recall_auditor: "researcher",
  obligation_extractor: "checker",
  output_auditor: "checker",
  requirement_matcher: "matcher",
  match_reviewer: "matcher",
};

/** Which character performed a logged step ("requirements_engine (mock)" is the research agent too). */
export function agentOf(traceAgent: string): AgentKind {
  return BY_TRACE_AGENT[traceAgent] ?? BY_TRACE_AGENT[traceAgent.split(" ")[0]] ?? "system";
}
