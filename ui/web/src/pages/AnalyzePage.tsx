import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, BookOpen, FileUp, ImagePlus, Link2, Rocket, ShieldCheck } from "lucide-react";
import { api, ApiError } from "../api";
import type { CountryListing, Health } from "../types";
import { CountryPicker, type Scout } from "../components/CountryPicker";
import { PipelineLauncher } from "../components/PipelineLauncher";
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
  "dev-rear-lamp": "Rear lamp",
  "heldout-front-bumper": "Front bumper",
  "mock-front-bumper": "Bumper (practice case)",
  "fake-chmsl": "High-mounted stop lamp",
  "fake-headlamp": "Headlamp",
  "fake-side-indicator": "Side indicator",
};

const TRUST = [
  { icon: BookOpen, text: "50+ UN vehicle regulations" },
  { icon: Link2, text: "Every statement with its source" },
  { icon: ShieldCheck, text: "Audit log modelled on the EU AI Act" },
];

const isImage = (file: File) => file.type.startsWith("image/") || /\.(png|jpe?g)$/i.test(file.name);

function StepHeader({ n, title, text }: { n: number; title: string; text: string }) {
  return (
    <div className="animate-fade-up pt-6 text-center">
      <span className="tag">Step {n} of 3</span>
      <h2 className="mt-4 text-4xl sm:text-5xl">{title}</h2>
      <p className="mx-auto mt-3 max-w-xl text-mint-900/70">{text}</p>
    </div>
  );
}

function Legend({ color, children }: { color: string; children: string }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-2.5 w-2.5 rounded-full ring-1 ring-inset ring-mint-900/10" style={{ background: color }} /> {children}
    </span>
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
  const [launch, setLaunch] = useState<NonNullable<Health["pipeline"]>["launch"] | null>(null);
  const [needsPipeline, setNeedsPipeline] = useState(false);

  useEffect(() => {
    api.countries().then(setListing).catch((e) => setError(String(e)));
    api.health().then((h) => setLaunch(h.pipeline?.launch ?? null)).catch(() => setLaunch(null));
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
  const tooltipFor = useCallback(
    (iso3: string) => (draft.selected.has(iso3) ? "Selected – click to remove" : known.has(iso3) ? "Click to select" : "Click to select · no country data yet"),
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
      // no finished pipeline run for this spec: offer to start one, or say why that is not possible
      if (e instanceof ApiError && e.status === 409 && launch?.available) setNeedsPipeline(true);
      else setError(e instanceof ApiError && e.status === 409 && launch?.reason ? `${e.detail} ${launch.reason}` : String(e));
      setBusy(false);
    }
  };
  const pipelineDone = useCallback(() => {
    setNeedsPipeline(false);
    start();
  }, [start]);

  const errorBox = error && <p className="mx-auto mt-4 max-w-3xl rounded-lg bg-rose-50 p-3 text-sm text-rose-700 ring-1 ring-inset ring-rose-600/20">{error}</p>;

  if (step === "product" && !draft.specFile) {
    return (
      <div className="space-y-20">
        <section className="band px-6 py-10 sm:px-10 sm:py-14 lg:px-14">
          <div className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-14">
            <div className="animate-fade-up">
              <p className="text-lg text-mint-300">Agent-based market approval</p>
              <h1 className="mt-3 text-huge text-white">Can your product be sold there?</h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-mint-50/75">
                Upload a product description and pick your target markets. Our agents check the regulations and show, country by country, whether you can sell – and what is still missing.
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
                className={`group mt-8 flex cursor-pointer items-center gap-4 rounded-xl border border-dashed p-4 transition-colors duration-300 focus-within:ring-2 focus-within:ring-mint-400 sm:p-5 ${
                  dragging ? "border-mint-300 bg-mint-400/15" : "border-mint-300/35 bg-white/[0.04] hover:border-mint-300/70 hover:bg-white/[0.08]"
                }`}
              >
                <input type="file" accept=".md,.markdown,.txt,.png,image/png,image/jpeg" multiple className="sr-only" onChange={(e) => takeFiles([...(e.target.files ?? [])])} />
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-md bg-mint-400 text-mint-950 transition-colors duration-300 group-hover:bg-mint-300">
                  <FileUp size={22} />
                </span>
                <span className="min-w-0">
                  <span className="block font-medium text-white">{dragging ? "Drop to upload" : "Drop your product description here"}</span>
                  <span className="block text-sm text-mint-50/60">or click to browse · spec.md, optionally with a drawing (PNG)</span>
                </span>
                <ArrowRight size={18} className="ml-auto hidden shrink-0 text-mint-300/60 transition group-hover:translate-x-0.5 group-hover:text-mint-300 sm:block" />
              </label>

              {examples.length > 0 && (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="text-sm text-mint-50/60">No document at hand?</span>
                  {examples.map((name) => (
                    <button key={name} type="button" className="btn-secondary btn-sm" onClick={() => loadExample(name)}>
                      Try example: {EXAMPLE_NAMES[name] ?? name}
                    </button>
                  ))}
                </div>
              )}
              {errorBox}
            </div>
            <div className="animate-fade-up [animation-delay:120ms]">
              <HeroVisual />
            </div>
          </div>

          <ul className="mt-12 grid gap-3 rounded-xl bg-gradient-to-r from-white/[0.06] to-white/[0.12] px-5 py-4 text-sm text-mint-50/85 backdrop-blur sm:grid-cols-3">
            {TRUST.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-2.5">
                <Icon size={16} className="shrink-0 text-mint-300" /> {text}
              </li>
            ))}
          </ul>
        </section>

        <section>
          <header className="mb-10 grid justify-items-center text-center">
            <span className="tag">How it works</span>
            <h2 className="mt-5 text-4xl sm:text-5xl">Five agents, one traceable result</h2>
            <p className="mt-4 max-w-2xl text-lg text-mint-900/70">Each agent handles one step, and every step is logged – so you can see later exactly who decided what, and on which basis.</p>
          </header>
          <AgentLineup />
        </section>
      </div>
    );
  }

  if (step === "product" && draft.specFile) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <StepHeader n={1} title="Your product at a glance" text="Does this look right? Next, you'll choose your target markets." />
        <ProductCard text={draft.specText} fileName={draft.specFile.name} image={draft.image} />
        {!draft.image && (
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-mint-900/20 px-4 py-3 text-sm text-mint-900/65 transition-colors focus-within:ring-2 focus-within:ring-mint-400 hover:border-mint-500 hover:bg-white hover:text-mint-900">
            <input type="file" accept=".png,image/png,image/jpeg" className="sr-only" onChange={(e) => takeFiles([...(e.target.files ?? [])])} />
            <ImagePlus size={16} /> Add a drawing (optional)
          </label>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button type="button" className="btn-ghost" onClick={() => onDraft({ ...draft, specFile: null, specText: "", image: null })}>
            <ArrowLeft size={16} /> Choose another file
          </button>
          <button type="button" className="btn-primary px-6" onClick={() => onStep("markets")}>
            Next: choose markets <ArrowRight size={16} />
          </button>
        </div>
        {errorBox}
      </div>
    );
  }

  const product = summarizeSpec(draft.specText).title;
  const selected = [...draft.selected];
  return (
    <div className="space-y-6">
      <StepHeader n={2} title="Where do you want to sell?" text="Search for a country, click the map, or use a quick pick." />
      <div className="grid animate-fade-up gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:items-start">
        <div className="card overflow-hidden">
          <WorldMap fillFor={fillFor} onSelect={toggle} tooltipFor={tooltipFor} focus={focus}>
            {scout && <AgentPin at={scoutAt} label={scout.phase === "found" ? `✓ ${countryName(scout.iso3)}` : `${countryName(scout.iso3)} …`} />}
          </WorldMap>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-mint-900/[0.06] px-4 py-3 text-xs text-mint-900/70">
            <Legend color={SELECTED_FILL}>Selected</Legend>
            <Legend color={KNOWN_FILL}>Country data available</Legend>
            <Legend color={UNTESTED_FILL}>No data yet</Legend>
            <span className="ml-auto hidden text-mint-900/45 sm:inline">Zoom: pinch or ⌘/Ctrl + scroll</span>
          </div>
        </div>
        <div className="card p-5">
          <CountryPicker listing={listing} selected={draft.selected} onChange={(next) => onDraft({ ...draft, selected: next })} onScout={search} />
        </div>
      </div>

      <div className="sticky bottom-4 z-20">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 rounded-xl bg-white/95 p-2 shadow-lift ring-1 ring-mint-900/10 backdrop-blur">
          <button type="button" className="btn-ghost" onClick={() => onStep("product")}>
            <ArrowLeft size={16} /> Back
          </button>
          <div className="hidden min-w-0 items-center gap-3 text-sm md:flex">
            <span className="truncate font-medium text-mint-950">{product}</span>
            <span className="text-mint-900/25">·</span>
            <span className="flex items-center gap-0.5 text-lg leading-none">
              <AnimatePresence initial={false}>
                {selected.slice(0, 8).map((iso3) => (
                  <motion.span key={iso3} initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} title={countryName(iso3)}>
                    {flag(iso3)}
                  </motion.span>
                ))}
              </AnimatePresence>
            </span>
            {selected.length > 8 && <span className="text-xs text-mint-900/60">+{selected.length - 8}</span>}
            <span className="whitespace-nowrap text-mint-900/60">
              {selected.length} {selected.length === 1 ? "market" : "markets"}
            </span>
          </div>
          <button type="button" className="btn-primary px-6" disabled={!draft.specFile || draft.selected.size === 0 || busy} onClick={start}>
            <Rocket size={16} /> {busy ? "Starting …" : "Start agents"}
          </button>
        </div>
        {errorBox}
      </div>
      {needsPipeline && draft.specFile && (
        <PipelineLauncher spec={draft.specFile} image={draft.image} fakeLlm={launch?.fake_llm ?? false} onDone={pipelineDone} onClose={() => setNeedsPipeline(false)} />
      )}
    </div>
  );
}
