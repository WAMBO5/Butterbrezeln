import { FlaskConical, KeyRound } from "lucide-react";

export type Mode = "demo" | "real";

/** Demo: the free scripted model, rules for questions. Real: the pipeline and the AI model with the API key from .env (paid). */
export function ModeToggle({ mode, realAvailable, reason, onChange }: { mode: Mode; realAvailable: boolean; reason?: string | null; onChange: (mode: Mode) => void }) {
  const item = (active: boolean) =>
    `flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-40 ${
      active ? "bg-mint-950 text-white" : "text-mint-900/70 enabled:hover:text-mint-950"
    }`;
  return (
    <div role="radiogroup" aria-label="Run mode" className="flex rounded-lg bg-white p-0.5 text-[13px] ring-1 ring-mint-900/[0.08]">
      <button type="button" role="radio" aria-checked={mode === "demo"} className={item(mode === "demo")} onClick={() => onChange("demo")}
              title="Free: a scripted stand-in model writes the requirements of new runs – not a real analysis. Country questions use rules.">
        <FlaskConical size={13} /> Demo
      </button>
      {/* a disabled button shows no tooltip, so the reason sits on its wrapper */}
      <span title={realAvailable ? "Real analysis: new pipeline runs and country questions use the AI model with the API key from .env – paid" : reason ?? "Not available"}>
        <button type="button" role="radio" aria-checked={mode === "real"} disabled={!realAvailable} className={item(mode === "real")} onClick={() => onChange("real")}>
          <KeyRound size={13} /> Real
        </button>
      </span>
    </div>
  );
}
