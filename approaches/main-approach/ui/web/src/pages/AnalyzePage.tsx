import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, BookOpen, FileUp, ImagePlus, Link2, Rocket, ShieldCheck, Sparkles } from "lucide-react";
import { api } from "../api";
import type { CountryListing } from "../types";
import { CountryPicker, type Scout } from "../components/CountryPicker";
import { AgentLineup, HeroVisual } from "../components/Landing";
import { ProductCard } from "../components/ProductCard";
import { AgentPin, WORLD_VIEW, WorldMap, type MapView } from "../components/WorldMap";
import { centroid, countryName, flag, zoomFor } from "../lib/geo";
import { KNOWN_FILL, SELECTED_FILL, UNTESTED_FILL } from "../lib/labels";
import { summarizeSpec } from "../lib/specSummary";

export interface Draft {
  specFile: File | null;
  specText: string;
  image: File | null;
  selected: Set<string>;
}

interface Props {
  step: "product" | "markets";
  onStep: (step: "product" | "markets") => void;
  draft: Draft;
  onDraft: (draft: Draft) => void;
  onStarted: (runId: string) => void;
}

const EXAMPLE_NAMES: Record<string, string> = {
  "dev-rear-lamp": "Rückleuchte",
  "heldout-front-bumper": "Frontstoßfänger",
  "mock-front-bumper": "Stoßfänger (Übungsfall)",
};

const TRUST = [
  { icon: BookOpen, text: "Über 50 UN-Fahrzeugvorschriften" },
  { icon: Link2, text: "Jede Anforderung mit Fundstelle" },
  { icon: ShieldCheck, text: "Protokoll nach Vorbild des EU AI Act" },
];

const isImage = (file: File) => file.type.startsWith("image/") || /\.(png|jpe?g)$/i.test(file.name);

function StepHeader({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="animate-fade-up pt-4 text-center">
      <p className="eyebrow">Schritt {n} von 3</p>
      <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-slate-400">{text}</p>
    </div>
  );
}

export function AnalyzePage({ step, onStep, draft, onDraft, onStarted }: Props) {
  const [listing, setListing] = useState<CountryListing | null>(null);
  const [examples, setExamples] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scout, setScout] = useState<Scout>(null);
  const [target, setTarget] = useState<string | null>(null); // the map follows the search, not clicks on the map
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.countries().then(setListing).catch((e) => setError(String(e)));
    api.examples().then(setExamples).catch(() => setExamples([]));
  }, []);

  // the agent shows "found" briefly, then the map returns to the world view
  useEffect(() => {
    if (scout?.phase !== "found") return;
    const t = setTimeout(() => {
      setScout(null);
      setTarget(null);
    }, 1800);
    return () => clearTimeout(t);
  }, [scout]);
  const search = useCallback((next: Scout) => {
    setScout(next);
    setTarget(next?.iso3 ?? null);
  }, []);

  const known = useMemo(() => new Set(listing?.countries.map((c) => c.iso3) ?? []), [listing]);

  const takeFiles = async (files: File[]) => {
    let next = { ...draft };
    for (const file of files) {
      if (isImage(file)) next = { ...next, image: file };
      else next = { ...next, specFile: file, specText: await file.text() };
    }
    onDraft(next);
  };

  const loadExample = async (name: string) => {
    try {
      const [text, image] = await Promise.all([api.example(name), api.exampleImage(name).catch(() => null)]);
      onDraft({ ...draft, specFile: new File([text], `${name}.spec.md`, { type: "text/markdown" }), specText: text, image });
    } catch (e) {
      setError(String(e));
    }
  };

  const toggle = useCallback(
    (iso3: string) => {
      const next = new Set(draft.selected);
      if (next.has(iso3)) next.delete(iso3);
      else {
        next.add(iso3);
        setScout({ iso3, phase: "found" });
      }
      onDraft({ ...draft, selected: next });
    },
    [draft, onDraft],
  );

  const fillFor = useCallback((iso3: string) => (draft.selected.has(iso3) ? SELECTED_FILL : known.has(iso3) ? KNOWN_FILL : UNTESTED_FILL), [draft.selected, known]);
  const glowFor = useCallback((iso3: string) => (draft.selected.has(iso3) ? SELECTED_FILL : null), [draft.selected]);
  const tooltipFor = useCallback(
    (iso3: string) => (draft.selected.has(iso3) ? "Ausgewählt – Klick entfernt" : known.has(iso3) ? "Klick wählt aus" : "Klick wählt aus · noch keine Länderdaten"),
    [draft.selected, known],
  );

  const scoutAt = scout ? centroid(scout.iso3) : undefined;
  const focus: MapView = useMemo(() => {
    const at = target ? centroid(target) : undefined;
    return target && at ? { coordinates: at, zoom: zoomFor(target) } : WORLD_VIEW;
  }, [target]);

  const start = async () => {
    if (!draft.specFile) return;
    setBusy(true);
    setError(null);
    try {
      const { run_id } = await api.startRun(draft.specFile, [...draft.selected], draft.image);
      onStarted(run_id);
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  };

  const errorBox = error && <p className="mx-auto mt-4 max-w-3xl rounded-2xl border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{error}</p>;

  if (step === "product" && !draft.specFile) {
    return (
      <div className="space-y-20 pb-8">
        <section className="grid items-center gap-12 pt-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:pt-14">
          <div className="animate-fade-up">
            <span className="inline-flex items-center gap-2 rounded-full border border-teal-300/20 bg-teal-300/[0.07] px-3 py-1 text-xs font-semibold text-teal-200">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-300 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-300" />
              </span>
              Agentenbasierte Marktfreigabe
            </span>
            <h1 className="mt-6 text-[2.75rem] font-bold leading-[1.05] tracking-tight sm:text-6xl">
              Was braucht Ihr Produkt <span className="gradient-text">in jedem Zielland?</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-400">
              Produktbeschreibung hochladen, Zielmärkte wählen – unsere Agenten prüfen die Vorschriften und zeigen pro Land, was sich am Produkt ändern muss und welche Nachweise noch fehlen.
            </p>

            <label
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                takeFiles([...e.dataTransfer.files]);
              }}
              className={`glass beam-border group mt-8 flex cursor-pointer items-center gap-5 p-5 transition duration-300 hover:bg-white/[0.06] ${dragging ? "scale-[1.02] bg-teal-300/10" : ""}`}
            >
              <input type="file" accept=".md,.markdown,.txt,.png,image/png,image/jpeg" multiple className="hidden" onChange={(e) => takeFiles([...(e.target.files ?? [])])} />
              <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-teal-300 to-cyan-400 text-ink-950 shadow-[0_0_40px_-6px_rgba(45,212,191,0.8)] transition group-hover:scale-105">
                <FileUp size={26} />
              </span>
              <span className="min-w-0">
                <span className="block text-lg font-semibold text-white">Produktbeschreibung hierher ziehen</span>
                <span className="block text-sm text-slate-400">oder klicken · spec.md, optional mit Zeichnung (PNG)</span>
              </span>
              <ArrowRight size={20} className="ml-auto hidden shrink-0 text-slate-500 transition group-hover:translate-x-1 group-hover:text-teal-300 sm:block" />
            </label>

            {examples.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-sm text-slate-500">Kein Dokument zur Hand?</span>
                {examples.map((name) => (
                  <button key={name} type="button" className="btn-secondary" onClick={() => loadExample(name)}>
                    <Sparkles size={15} className="text-teal-300" /> Beispiel laden: {EXAMPLE_NAMES[name] ?? name}
                  </button>
                ))}
              </div>
            )}

            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-400">
              {TRUST.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2">
                  <Icon size={15} className="text-teal-300" /> {text}
                </li>
              ))}
            </ul>
            {errorBox}
          </div>
          <div className="animate-fade-up [animation-delay:150ms]">
            <HeroVisual />
          </div>
        </section>

        <section>
          <div className="mb-10 text-center">
            <p className="eyebrow">Das Team hinter dem Ergebnis</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">So arbeiten unsere Agenten</h2>
            <p className="mx-auto mt-2 max-w-2xl text-slate-400">Fünf spezialisierte Agenten übernehmen je einen Schritt. Jeder Schritt wird protokolliert – Sie sehen später genau, wer was auf welcher Grundlage entschieden hat.</p>
          </div>
          <AgentLineup />
        </section>
      </div>
    );
  }

  if (step === "product" && draft.specFile) {
    return (
      <div className="mx-auto max-w-5xl space-y-6 pb-8">
        <StepHeader n={1} title="Ihr Produkt im Überblick" text="Stimmt das so? Dann wählen Sie im nächsten Schritt Ihre Zielmärkte." />
        <ProductCard text={draft.specText} fileName={draft.specFile.name} image={draft.image} />
        {!draft.image && (
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-2xl border border-dashed border-white/10 px-4 py-3 text-sm text-slate-400 transition hover:border-teal-300/40 hover:text-teal-200">
            <input type="file" accept=".png,image/png,image/jpeg" className="hidden" onChange={(e) => takeFiles([...(e.target.files ?? [])])} />
            <ImagePlus size={16} /> Zeichnung hinzufügen (optional)
          </label>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button type="button" className="btn-ghost" onClick={() => onDraft({ ...draft, specFile: null, specText: "", image: null })}>
            <ArrowLeft size={16} /> Andere Datei wählen
          </button>
          <button type="button" className="btn-primary px-6 py-3 text-base" onClick={() => onStep("markets")}>
            Weiter: Märkte wählen <ArrowRight size={18} />
          </button>
        </div>
        {errorBox}
      </div>
    );
  }

  const product = summarizeSpec(draft.specText).title;
  const selected = [...draft.selected];
  return (
    <div className="space-y-6 pb-4">
      <StepHeader n={2} title="Wo möchten Sie verkaufen?" text="Suchen Sie ein Land, klicken Sie auf die Karte oder nutzen Sie die Schnellauswahl." />
      <div className="grid animate-fade-up gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
        <div className="glass overflow-hidden p-2">
          <WorldMap fillFor={fillFor} glowFor={glowFor} onSelect={toggle} tooltipFor={tooltipFor} focus={focus} className="rounded-[20px]">
            {scout && <AgentPin at={scoutAt} label={scout.phase === "found" ? `✓ ${countryName(scout.iso3)}` : `${countryName(scout.iso3)} …`} />}
          </WorldMap>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 text-xs text-slate-400">
            <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full shadow-[0_0_8px_#22d3ee]" style={{ background: SELECTED_FILL }} /> ausgewählt</span>
            <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full ring-1 ring-white/20" style={{ background: KNOWN_FILL }} /> Länderdaten vorhanden</span>
            <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full ring-1 ring-white/10" style={{ background: UNTESTED_FILL }} /> noch keine Daten</span>
            <span className="ml-auto hidden text-slate-500 sm:inline">Zoomen: Pinch oder ⌘ + Scrollen</span>
          </div>
        </div>
        <div className="glass p-5">
          <CountryPicker listing={listing} selected={draft.selected} onChange={(next) => onDraft({ ...draft, selected: next })} onScout={search} />
        </div>
      </div>

      <div className="sticky bottom-4 z-20">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 rounded-full border border-white/10 bg-ink-900/80 p-2 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.9)] backdrop-blur-xl">
          <button type="button" className="btn-ghost" onClick={() => onStep("product")}>
            <ArrowLeft size={16} /> Zurück
          </button>
          <div className="hidden min-w-0 items-center gap-3 text-sm md:flex">
            <span className="truncate font-semibold text-white">{product}</span>
            <span className="text-slate-600">·</span>
            <span className="flex items-center gap-0.5 text-lg leading-none">
              <AnimatePresence initial={false}>
                {selected.slice(0, 8).map((iso3) => (
                  <motion.span key={iso3} initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} title={countryName(iso3)}>
                    {flag(iso3)}
                  </motion.span>
                ))}
              </AnimatePresence>
            </span>
            {selected.length > 8 && <span className="text-xs text-slate-400">+{selected.length - 8}</span>}
            <span className="whitespace-nowrap text-slate-400">{selected.length} {selected.length === 1 ? "Markt" : "Märkte"}</span>
          </div>
          <button type="button" className="btn-primary px-6 py-3 text-base" disabled={!draft.specFile || draft.selected.size === 0 || busy} onClick={start}>
            <Rocket size={18} /> {busy ? "Startet …" : "Agenten starten"}
          </button>
        </div>
        {errorBox}
      </div>
    </div>
  );
}
