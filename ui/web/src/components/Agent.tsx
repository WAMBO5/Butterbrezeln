import { useId } from "react";
import { AGENTS, type AgentKind } from "../lib/agents";

interface BotProps {
  color: string;
  magnifier?: boolean;
  active?: boolean;
  size?: number;
  x?: number; // position when nested in another SVG (map markers)
  y?: number;
  className?: string;
}

/** The agent character: a small robot; the researching ones carry a magnifying glass. SVG + CSS animation only. */
export function AgentBot({ color, magnifier, active = true, size = 48, x, y, className }: BotProps) {
  const id = useId().replace(/:/g, "");
  return (
    <svg x={x} y={y} width={size} height={size} viewBox="0 0 64 64" fill="none" overflow="visible" className={className} aria-hidden>
      <defs>
        <linearGradient id={`shine${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.35" />
          <stop offset="0.55" stopColor="#fff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <g className={active ? "agent-bob" : undefined}>
        <line x1="32" y1="17" x2="32" y2="9.5" stroke={color} strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="32" cy="8" r="3.6" fill={color}>
          {active && <animate attributeName="opacity" values="1;0.35;1" dur="1.4s" repeatCount="indefinite" />}
        </circle>
        <rect x="7.5" y="27" width="6.5" height="12" rx="3.25" fill={color} opacity="0.85" />
        <rect x="50" y="27" width="6.5" height="12" rx="3.25" fill={color} opacity="0.85" />
        <rect x="12" y="16" width="40" height="34" rx="14" fill={color} />
        <rect x="12" y="16" width="40" height="34" rx="14" fill={`url(#shine${id})`} />
        <rect x="17" y="23" width="30" height="20" rx="9" fill="#02312f" />
        <g className={active ? "agent-blink" : undefined}>
          <rect x="23" y="29" width="5.5" height="8" rx="2.75" fill={color} />
          <rect x="35.5" y="29" width="5.5" height="8" rx="2.75" fill={color} />
        </g>
      </g>
      {magnifier && (
        <g className={active ? "agent-swing" : undefined}>
          <line x1="50.5" y1="52.5" x2="58.5" y2="60.5" stroke="#02312f" strokeWidth="4.6" strokeLinecap="round" />
          <circle cx="44" cy="46" r="9.5" fill="#ffffff" fillOpacity="0.7" stroke="#02312f" strokeWidth="3.2" />
          <path d="M39 44.5a5.5 5.5 0 0 1 4.5-4.5" stroke={color} strokeOpacity="0.9" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}
    </svg>
  );
}

/** An agent in its tinted tile; people and the orchestration get their icon instead of a robot. */
export function AgentAvatar({ kind, size = 44, active = false, className = "" }: { kind: AgentKind; size?: number; active?: boolean; className?: string }) {
  const a = AGENTS[kind];
  const Icon = a.icon;
  const tile = {
    width: size,
    height: size,
    background: `${a.color}14`,
    boxShadow: active ? `inset 0 0 0 1.5px ${a.color}` : `inset 0 0 0 1px ${a.color}2e`,
  };
  return (
    <span className={`grid shrink-0 place-items-center rounded-[28%] transition-shadow duration-300 ${className}`} style={tile} title={`${a.name} – ${a.does}`}>
      {kind === "human" || kind === "system" ? (
        <Icon size={size * 0.45} style={{ color: a.color }} />
      ) : (
        <AgentBot color={a.color} magnifier={a.magnifier} active={active} size={size * 0.84} />
      )}
    </span>
  );
}

/** Small "who did this" label. */
export function AgentTag({ kind, suffix }: { kind: AgentKind; suffix?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md bg-mint-900/[0.05] py-0.5 pl-0.5 pr-2 text-xs font-medium text-mint-900">
      <AgentAvatar kind={kind} size={20} />
      {AGENTS[kind].name}
      {suffix && <span className="text-mint-900/55">· {suffix}</span>}
    </span>
  );
}
