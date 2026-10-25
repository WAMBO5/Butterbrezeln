import { BookOpen, ExternalLink, FileText, Globe, Landmark } from "lucide-react";
import type { Source } from "../types";

function describe(source: Source): { icon: typeof BookOpen; text: string } {
  switch (source.kind) {
    case "un_regulation":
      return { icon: BookOpen, text: `${source.regulation ?? source.label}${source.page ? ` · p. ${source.page}` : ""}` };
    case "spec":
      return {
        icon: FileText,
        text: source.spec_lines ? `Product description · line ${source.spec_lines[0]}${source.spec_lines[1] !== source.spec_lines[0] ? `–${source.spec_lines[1]}` : ""}` : "Product description",
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
  const tooltip = [source.label, source.title, source.paragraph ? `Section ${source.paragraph}` : null, source.version ? `Version ${source.version}` : null]
    .filter(Boolean)
    .join(" · ");
  const body = (
    <>
      <Icon size={13} className="shrink-0 text-mint-600" />
      <span className="truncate">{text}</span>
      {external && <span className="shrink-0 rounded bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-800">external</span>}
      {source.href && <ExternalLink size={11} className="shrink-0 text-mint-900/40" />}
    </>
  );
  const cls = "inline-flex max-w-full items-center gap-1.5 rounded-md bg-white px-2 py-1 text-xs font-medium text-mint-900 ring-1 ring-inset ring-mint-900/[0.12]";
  return source.href ? (
    <a className={`${cls} transition-colors hover:bg-mint-50 hover:ring-mint-500/50`} href={source.href} target="_blank" rel="noreferrer"
       title={external ? `${tooltip} – external source, not verified by Certivity` : tooltip}>
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
