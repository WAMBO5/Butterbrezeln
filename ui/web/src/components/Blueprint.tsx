import { useEffect, useState } from "react";

/** A technical drawing on a dotted sheet, optionally with a scan line passing over it. */
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
    <div className={`dot-grid relative isolate overflow-hidden rounded-xl bg-mint-50/60 ring-1 ring-mint-900/[0.08] ${className}`}>
      <img src={url} alt="Technical drawing" className="h-full w-full object-contain p-3 mix-blend-multiply" />
      {scanning && (
        <div className="pointer-events-none absolute inset-x-0 h-1/5 animate-scan bg-gradient-to-b from-transparent via-mint-400/20 to-transparent">
          <div className="absolute inset-x-0 bottom-1/2 h-px bg-mint-500" />
        </div>
      )}
    </div>
  );
}
