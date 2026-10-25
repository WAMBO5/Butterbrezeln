import { useEffect, useState } from "react";
import { Earth, RotateCcw } from "lucide-react";
import { api } from "./api";
import type { RunResult } from "./types";
import { AnalyzePage, type Draft } from "./pages/AnalyzePage";
import { ResultPage } from "./pages/ResultPage";
import { Stepper } from "./components/Stepper";

const DEFAULT_COUNTRIES = ["DEU", "FRA", "JPN", "CHN", "USA"];
const emptyDraft = (): Draft => ({ specFile: null, specText: "", image: null, selected: new Set(DEFAULT_COUNTRIES) });

function runFromHash(): string | null {
  const match = window.location.hash.match(/^#\/run\/([a-z0-9]+)/);
  return match ? match[1] : null;
}

function setHash(hash: string) {
  if (hash) window.location.hash = hash;
  else if (window.location.hash) history.pushState(null, "", window.location.pathname + window.location.search);
}

export default function App() {
  const [runId, setRunId] = useState<string | null>(runFromHash());
  const [replayId, setReplayId] = useState<string | null>(null);
  const [step, setStep] = useState<"product" | "markets">("product");
  const [draft, setDraft] = useState<Draft>(emptyDraft);

  useEffect(() => {
    const onHash = () => setRunId(runFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [runId, step]);

  const openRun = (id: string) => {
    setReplayId(id);
    setHash(`#/run/${id}`);
    setRunId(id);
  };
  const goHome = () => {
    setHash("");
    setRunId(null);
    setStep("product");
  };
  const startOver = () => {
    goHome();
    setDraft(emptyDraft());
  };
  const editMarkets = async (run: RunResult) => {
    const image = run.has_image ? await api.runImage(run.run_id) : null;
    setDraft({ specFile: new File([run.spec_text], run.spec_name, { type: "text/markdown" }), specText: run.spec_text, image, selected: new Set(run.countries) });
    setHash("");
    setRunId(null);
    setStep("markets");
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-ink-950/70 backdrop-blur-xl">
        <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto] items-center gap-4 px-4 py-3 sm:px-6 md:grid-cols-[1fr_auto_1fr]">
          <button type="button" className="group flex items-center gap-3 justify-self-start text-left" onClick={goHome}>
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-teal-300 via-cyan-300 to-indigo-400 text-ink-950 shadow-[0_0_24px_-4px_rgba(45,212,191,0.7)] transition group-hover:scale-105">
              <Earth size={22} />
            </span>
            <span>
              <span className="block font-display font-bold leading-tight text-white">Marktfreigabe-Check</span>
              <span className="hidden text-xs text-slate-500 sm:block">Was muss sich pro Zielland ändern?</span>
            </span>
          </button>
          <Stepper current={runId ? 3 : step === "markets" ? 2 : 1} />
          <div className="justify-self-end">
            {(runId || draft.specFile) && (
              <button type="button" className="btn-secondary" onClick={startOver}>
                <RotateCcw size={15} /> Neue Prüfung
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        {runId ? (
          <ResultPage key={runId} runId={runId} replay={replayId === runId} onNew={startOver} onOpenRun={openRun} onEditMarkets={editMarkets} />
        ) : (
          <AnalyzePage step={step} onStep={setStep} draft={draft} onDraft={setDraft} onStarted={openRun} />
        )}
      </main>

      <footer className="px-4 pb-8 pt-4 text-center text-xs text-slate-600">
        Prototyp · Unreviewed AI draft — not for compliance use · Grundlage: UN-Fahrzeugvorschriften (UNECE) und recherchierte Länderprofile (Entwurf)
      </footer>
    </div>
  );
}
