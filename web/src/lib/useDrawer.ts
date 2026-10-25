import { useEffect, useRef } from "react";

const openDrawers: { current: () => void }[] = [];
let locks = 0;

if (typeof window !== "undefined") {
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") openDrawers[openDrawers.length - 1]?.current();
  });
}

/** Drawer behaviour: the page behind does not scroll, Escape closes the topmost drawer. */
export function useDrawer(onClose: () => void) {
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    openDrawers.push(close);
    if (locks++ === 0) document.body.style.overflow = "hidden";
    return () => {
      openDrawers.splice(openDrawers.indexOf(close), 1);
      if (--locks === 0) document.body.style.overflow = "";
    };
  }, []);
}
