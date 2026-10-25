import { BookOpen, ExternalLink, FileText, Globe, Landmark } from "lucide-react";
import type { Source } from "../types";

function describe(source: Source): { icon: typeof BookOpen; text: string } {
  switch (source.kind) {
    case "un_regulation":
      return { icon: BookOpen, text: `${source.regulation ?? source.label}${source.page ? ` · Seite ${source.page}` : ""}` };
    case "spec":
      return {
        icon: FileText,
        text: source.spec_lines ? `Produktbeschreibung · Zeile ${source.spec_lines[0]}${source.spec_lines[1] !== source.spec_lines[0] ? `–${source.spec_lines[1]}` : ""}` : "Produktbeschreibung",
      };
    case "dataset":
      return { icon: Landmark, text: source.label };
    default:
      return { icon: Globe, text: source.label };
  }
}

/** A citation chip; opens the regulation PDF on the cited page or the external page. */
export function SourceLink({ source }: { source: Source }) {
  const { icon: Icon, text } = describe(source);
  const external = !source.in_certivity_corpus && (source.kind === "external" || source.kind === "country_profile");
  const tooltip = [source.label, source.title, source.paragraph ? `Abschnitt ${source.paragraph}` : null, source.version ? `Version ${source.version}` : null]
    .filter(Boolean)
    .join(" · ");
  const body = (
    <>
      <Icon size={13} className="shrink-0 text-cyan-300" />
      <span className="truncate">{text}</span>
      {external && <span className="shrink-0 rounded-full bg-amber-400/15 px-1.5 text-[10px] font-semibold text-amber-300">extern</span>}
      {source.href && <ExternalLink size={11} className="shrink-0 text-slate-500" />}
    </>
  );
  const cls = "inline-flex max-w-full items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.05] px-2.5 py-1 text-xs font-medium text-slate-300";
  return source.href ? (
    <a className={`${cls} transition hover:border-cyan-300/40 hover:bg-cyan-300/10 hover:text-white`} href={source.href} target="_blank" rel="noreferrer"
       title={external ? `${tooltip} – externe Quelle, nicht von Certivity geprüft` : tooltip}>
      {body}
    </a>
  ) : (
    <span className={cls} title={tooltip}>{body}</span>
  );
}

export function SourceList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {sources.map((s, i) => (
        <SourceLink key={`${s.label}-${i}`} source={s} />
      ))}
    </div>
  );
}
