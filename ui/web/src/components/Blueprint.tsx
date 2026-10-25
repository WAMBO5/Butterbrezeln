import { useEffect, useState } from "react";

/** A technical drawing shown as a glowing blueprint, optionally with a scan line passing over it. */
export function Blueprint({ src, file, scanning = false, className = "" }: { src?: string; file?: File | null; scanning?: boolean; className?: string }) {
  const [url, setUrl] = useState<string | undefined>(src);
  useEffect(() => {
    if (!file) {
      setUrl(src);
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file, src]);

  if (!url) return null;
  return (
    <div className={`dot-grid relative isolate overflow-hidden rounded-2xl border border-cyan-300/15 bg-ink-950 ${className}`}>
      {/* white paper -> dark sheet with light lines, then tinted teal */}
      <img src={url} alt="Technische Zeichnung" className="h-full w-full object-contain p-3 opacity-90 mix-blend-screen [filter:invert(1)]" />
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-teal-300 via-cyan-300 to-indigo-400 mix-blend-multiply" />
      {scanning && (
        <div className="pointer-events-none absolute inset-x-0 h-1/5 animate-scan bg-gradient-to-b from-transparent via-cyan-300/25 to-transparent">
          <div className="absolute inset-x-0 bottom-1/2 h-px bg-cyan-200 shadow-[0_0_12px_2px_rgba(103,232,249,0.8)]" />
        </div>
      )}
    </div>
  );
}
