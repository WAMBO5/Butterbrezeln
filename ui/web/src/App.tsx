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
  const editRun = async (run: RunResult, target: "product" | "markets") => {
    const image = run.has_image ? await api.runImage(run.run_id) : null;
    setDraft({ specFile: new File([run.spec_text], run.spec_name, { type: "text/markdown" }), specText: run.spec_text, image, selected: new Set(run.countries) });
    setHash("");
    setRunId(null);
    setStep(target);
  };
  const editMarkets = (run: RunResult) => editRun(run, "markets");
  /** Stepper click: jump back to an earlier step, restoring the run's inputs when leaving a result. */
  const goToStep = async (n: 1 | 2 | 3) => {
    const target = n === 1 ? "product" : "markets";
    if (runId) await editRun(await api.run(runId), target);
    else setStep(target);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-flat-white/80 backdrop-blur-md">
        <div className="mx-auto grid max-w-7xl grid-cols-[1fr_auto] items-center gap-4 px-4 py-3 sm:px-6 md:grid-cols-[1fr_auto_1fr]">
          <button type="button" className="group flex items-center gap-2.5 justify-self-start rounded-md text-left" onClick={goHome}>
            <span className="grid h-9 w-9 place-items-center rounded-md bg-mint-950 text-mint-300 transition-colors duration-300 group-hover:bg-mint-900">
              <Earth size={20} />
            </span>
            <span className="text-[17px] font-semibold tracking-tight text-mint-950">Market Approval Check</span>
          </button>
          <Stepper current={runId ? 3 : step === "markets" ? 2 : 1} onSelect={goToStep} />
          <div className="justify-self-end">
            {(runId || draft.specFile) && (
              <button type="button" className="btn-outline btn-sm" onClick={startOver}>
                <RotateCcw size={14} /> New check
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 pb-10 pt-4 sm:px-6">
        {runId ? (
          <ResultPage key={runId} runId={runId} replay={replayId === runId} onNew={startOver} onOpenRun={openRun} onEditMarkets={editMarkets} />
        ) : (
          <AnalyzePage step={step} onStep={setStep} draft={draft} onDraft={setDraft} onStarted={openRun} />
        )}
      </main>

      <footer className="mx-auto w-full max-w-7xl px-4 pb-8 pt-2 text-xs text-mint-900/50 sm:px-6">
        Prototype · Unreviewed AI draft — not for compliance use · Based on UN vehicle regulations (UNECE) and researched country profiles (draft)
      </footer>
    </div>
  );
}
