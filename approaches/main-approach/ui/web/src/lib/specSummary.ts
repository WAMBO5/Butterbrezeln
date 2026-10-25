export interface SpecSection {
  title: string;
  text: string[];
  items: string[];
  rows: string[][]; // table body rows, header removed
}

export interface SpecSummary {
  title: string;
  sections: SpecSection[];
}

/** Turns a spec.md into a product card: title, bullet lists and table rows per section. */
export function summarizeSpec(markdown: string): SpecSummary {
  let title = "Ihr Produkt";
  const sections: SpecSection[] = [];
  let current: SpecSection | null = null;
  let tableHeaderSeen = false;

  for (const raw of markdown.split("\n")) {
    const line = raw.trim();
    const h1 = line.match(/^#\s+(.*)$/);
    if (h1) {
      title = h1[1].replace(/^spec:\s*/i, "");
      continue;
    }
    const heading = line.match(/^#{2,6}\s+(.*)$/);
    if (heading) {
      current = { title: heading[1], text: [], items: [], rows: [] };
      sections.push(current);
      tableHeaderSeen = false;
      continue;
    }
    if (!current || !line) continue;
    if (/^[-*]\s+/.test(line)) {
      current.items.push(line.replace(/^[-*]\s+/, ""));
    } else if (line.startsWith("|")) {
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.every((c) => /^:?-+:?$/.test(c))) continue; // separator row
      if (!tableHeaderSeen) {
        tableHeaderSeen = true; // first row is the header
        continue;
      }
      current.rows.push(cells);
    } else {
      current.text.push(line);
    }
  }
  return { title, sections };
}
