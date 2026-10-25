// Small DOM helpers shared by the pages (no framework).
type Child = Node | string | number | null | undefined | false;

export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K, attrs: Record<string, string | boolean | ((e: Event) => void) | undefined> = {}, ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === false) continue;
    if (typeof value === "function") el.addEventListener(key.replace(/^on/, ""), value as EventListener);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

export const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document) => root.querySelector(sel) as T;

export const usd = (n: number | undefined) => `$${(n ?? 0).toFixed(n && n < 0.1 ? 4 : 2)}`;
export const pct = (n: number) => `${Math.round(n * 100)}%`;
export const tokens = (n: number) => (n >= 10000 ? `${Math.round(n / 1000)}k` : String(n));

const STATE_TEXT: Record<string, string> = {
  applicable: "Applies", uncertain: "Uncertain", not_applicable: "Does not apply",
  met: "Met", not_met: "Not met", evidence_needed: "Evidence needed",
  done: "Finished", running: "Running", awaiting_review: "Waiting for review", stopped: "Stopped", failed: "Failed",
  ready: "Ready", blocked: "Blocked", not_covered: "Not covered",
};

/** A chip coloured like a vehicle lamp: stop red, indicator amber, position white, teal for met. */
export function chip(value: string, title?: string): HTMLElement {
  return h("span", { class: `chip chip-${value}`, title }, STATE_TEXT[value] ?? value);
}

export function citation(reg: string, page: number, paragraph: string | null): string {
  return `${reg}, p. ${page}${paragraph ? `, §${paragraph}` : ""}`;
}

export function message(target: HTMLElement, text: string, kind: "error" | "note" = "note") {
  target.replaceChildren(h("p", { class: `message message-${kind}`, role: kind === "error" ? "alert" : "status" }, text));
}

export function draftStamp(label: string | null) {
  const stamp = document.querySelector<HTMLElement>("[data-draft-stamp]");
  if (!stamp) return;
  stamp.hidden = !label;
  const text = stamp.querySelector("[data-draft-text]");
  if (text && label) text.textContent = label;
}
