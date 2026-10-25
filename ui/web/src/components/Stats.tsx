import { useEffect, useState } from "react";
import { animate } from "motion/react";

/** A number that counts up when it appears or changes. */
export function CountUp({ value, duration = 1.1, className }: { value: number; duration?: number; className?: string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const controls = animate(0, value, { duration, ease: [0.22, 1, 0.36, 1], onUpdate: (v) => setShown(Math.round(v)) });
    return () => controls.stop();
  }, [value, duration]);
  return <span className={`tabular-nums ${className ?? ""}`}>{shown}</span>;
}
