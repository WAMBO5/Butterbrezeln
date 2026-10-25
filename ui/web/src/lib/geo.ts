import countries from "i18n-iso-countries";
import de from "i18n-iso-countries/langs/de.json";
import { geoArea, geoBounds, geoCentroid } from "d3-geo";
import type { Feature, FeatureCollection, Geometry, Polygon } from "geojson";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";
import world from "world-atlas/countries-50m.json";

countries.registerLocale(de);

/** world-atlas features carry ISO 3166-1 numeric ids ("276"); the API speaks alpha-3 ("DEU"). */
export function numericToIso3(id: string | number | undefined): string | undefined {
  if (id === undefined || id === null || id === "") return undefined;
  return countries.numericToAlpha3(String(id).padStart(3, "0"));
}

export function countryName(iso3: string, fallback?: string): string {
  return countries.getName(iso3, "de") ?? fallback ?? iso3;
}

/** Every ISO country with its German name, for search. */
export function allCountries(): { iso3: string; name: string }[] {
  return Object.entries(countries.getNames("de", { select: "official" }))
    .map(([alpha2, name]) => ({ iso3: countries.alpha2ToAlpha3(alpha2) ?? alpha2, name }))
    .sort((a, b) => a.name.localeCompare(b.name, "de"));
}

/** Emoji flag from regional-indicator letters, e.g. DEU -> 🇩🇪. */
export function flag(iso3: string): string {
  const alpha2 = countries.alpha3ToAlpha2(iso3);
  if (!alpha2) return "🏳️";
  return String.fromCodePoint(...[...alpha2.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

export interface CountryShape {
  key: string;
  iso3?: string;
  feature: Feature<Geometry>;
}

const topology = world as unknown as Topology<{ countries: GeometryCollection }>;

export const COUNTRY_SHAPES: CountryShape[] = (feature(topology, topology.objects.countries) as FeatureCollection).features.map((f, i) => ({
  key: String(f.id ?? `x${i}`),
  iso3: numericToIso3(f.id),
  feature: f,
}));

/** Centre, area and bounds of the largest landmass, so France sits in Europe and not off French Guiana. */
function mainland(f: Feature<Geometry>): { centre: [number, number]; area: number; bounds: [[number, number], [number, number]] } {
  const g = f.geometry;
  if (g?.type === "MultiPolygon") {
    let best: Polygon | null = null;
    let bestArea = -1;
    for (const coordinates of g.coordinates) {
      const polygon: Polygon = { type: "Polygon", coordinates };
      const area = geoArea(polygon);
      if (area < 2 * Math.PI && area > bestArea) {
        best = polygon;
        bestArea = area;
      }
    }
    if (best) return { centre: geoCentroid(best) as [number, number], area: bestArea, bounds: geoBounds(best) };
  }
  return { centre: geoCentroid(f) as [number, number], area: geoArea(f), bounds: geoBounds(f) };
}

const MAINLAND = new Map(COUNTRY_SHAPES.filter((s) => s.iso3).map((s) => [s.iso3!, mainland(s.feature)]));

/** [longitude, latitude] to pin markers and agents on a country. */
export function centroid(iso3: string): [number, number] | undefined {
  return MAINLAND.get(iso3)?.centre;
}

/** Corners of the largest landmass, to frame whole countries on the map rather than their centres. */
export function corners(iso3: string): [number, number][] {
  const bounds = MAINLAND.get(iso3)?.bounds;
  if (!bounds) return [];
  const [[west, south], [east, north]] = bounds;
  return [[west, south], [east, south], [west, north], [east, north]];
}

/** Map zoom that frames a country: Russia ~1.8, Germany ~4.5, small states capped. */
export function zoomFor(iso3: string): number {
  const area = MAINLAND.get(iso3)?.area;
  if (!area) return 3;
  return Math.min(6, Math.max(1.8, 1.4 * Math.pow(area, -0.25)));
}

/** Geneva, home of the UNECE working party that writes the UN vehicle regulations. */
export const GENEVA: [number, number] = [6.14, 46.2];
