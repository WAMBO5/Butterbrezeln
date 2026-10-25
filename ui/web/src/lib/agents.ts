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
  reader: { name: "Reader", does: "reads your product description", color: "#0b7a70", icon: FileText },
  researcher: { name: "Researcher", does: "finds the regulations that apply", color: "#6d5bd0", icon: Search, magnifier: true },
  checker: { name: "Checker", does: "backs every requirement with its source", color: "#2f6fd6", icon: ShieldCheck },
  matcher: { name: "Matcher", does: "compares your product with each requirement", color: "#c2477f", icon: Scale },
  scout: { name: "Country agent", does: "rates every target market", color: "#0ebea9", icon: Globe, magnifier: true },
  assistant: { name: "Assistant", does: "answers your questions", color: "#4f63c9", icon: MessageCircle },
  human: { name: "Human", does: "reviews and decides", color: "#41736f", icon: User },
  system: { name: "Orchestrator", does: "coordinates the agents", color: "#709693", icon: Cog },
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
