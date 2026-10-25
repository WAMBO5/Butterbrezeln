import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { animate, type AnimationPlaybackControls } from "motion/react";
import { Minus, Plus } from "lucide-react";
import { geoCentroid, geoDistance, geoInterpolate, geoOrthographic, type GeoProjection } from "d3-geo";
import { ComposableMap, Graticule, Line, Marker, Sphere, useMapContext, type ProjectionFunction } from "react-simple-maps";
import { AGENTS, type AgentKind } from "../lib/agents";
import { COARSE_COUNTRY_SHAPES, COUNTRY_SHAPES, countryName, flag, type CountryShape } from "../lib/geo";
import { UNTESTED_FILL } from "../lib/labels";
import { AgentBot } from "./Agent";

export interface MapView {
  coordinates: [number, number]; // [lon, lat] facing the viewer
  zoom: number;
}

/** Places to frame instead of a fixed view. */
export interface Framing {
  fit: [number, number][];
  maxZoom?: number;
  inset?: { top: number; bottom: number }; // share of the frame to keep clear, e.g. under an overlay card
}

export type MapFocus = MapView | Framing;

export const WORLD_VIEW: MapView = { coordinates: [10, 22], zoom: 1 };
export const EUROPE_VIEW: MapView = { coordinates: [14, 51], zoom: 3.6 };

const MAP_WIDTH = 900;
const MAP_HEIGHT = 450;
const GLOBE_SIZE = 0.46; // globe radius at zoom 1, as share of the frame's shorter side
const MAX_ZOOM = 10;
const SPIN_SPEED = 6; // degrees per second while idle
const SPIN_UP_TO = 1.2; // no spinning once zoomed in further
const SETTLE_MS = 250; // still this long before the detailed outlines come back

const globeRadius = (height: number) => Math.min(MAP_WIDTH, height) * GLOBE_SIZE;
const wrapLon = (lon: number) => ((((lon + 180) % 360) + 360) % 360) - 180;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function globeProjection({ coordinates: [lon, lat], zoom }: MapView, height: number): GeoProjection {
  return geoOrthographic()
    .rotate([-lon, -lat])
    .scale(globeRadius(height) * zoom)
    .translate([MAP_WIDTH / 2, height / 2]);
}

/** Turn and zoom that frame the places in a map of the given height. */
export function fitView({ fit, maxZoom = 4, inset = { top: 0, bottom: 0 } }: Framing, height = MAP_HEIGHT): MapView {
  if (!fit.length) return WORLD_VIEW;
  const centre = geoCentroid({ type: "MultiPoint", coordinates: fit }) as [number, number];
  const flat = globeProjection({ coordinates: centre, zoom: 1 }, height);
  const points = fit.filter((p) => geoDistance(p, centre) < Math.PI / 2).map((p) => flat(p)!);
  if (!points.length) return { coordinates: centre, zoom: 1 };
  const pad = 36; // margin on screen, whatever the zoom
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const free = height * (1 - inset.top - inset.bottom);
  const zoom = clamp(Math.min(maxZoom, (MAP_WIDTH - 2 * pad) / Math.max(x1 - x0, 1), (free - 2 * pad) / Math.max(y1 - y0, 1)), 1, MAX_ZOOM);
  // turned so the places sit in the middle of the free band
  const [cx, cy] = [MAP_WIDTH / 2, height / 2];
  const look = globeProjection({ coordinates: centre, zoom }, height).invert?.([
    cx + ((x0 + x1) / 2 - cx) * zoom,
    cy + ((y0 + y1) / 2 - cy) * zoom + ((inset.bottom - inset.top) * height) / 2,
  ]);
  return { coordinates: look ?? centre, zoom };
}

const ZoomContext = createContext(1);

interface CountriesProps {
  shapes: CountryShape[];
  fillFor: (iso3: string) => string;
  selected?: string | null;
  clickable: boolean;
  onPick: (iso3: string) => void;
  onHover: (iso3: string | null) => void;
}

const Countries = memo(function Countries({ shapes: source, fillFor, selected, clickable, onPick, onHover }: CountriesProps) {
  const { path } = useMapContext();
  const shapes = useMemo(() => source.map((s) => ({ ...s, d: path(s.feature) ?? "" })).filter((s) => s.d), [source, path]);
  return (
    <>
      {shapes.map((s) => (
        <path
          key={s.key}
          d={s.d}
          fill={s.iso3 ? fillFor(s.iso3) : UNTESTED_FILL}
          className="map-country"
          data-clickable={(clickable && !!s.iso3) || undefined}
          data-selected={(!!s.iso3 && s.iso3 === selected) || undefined}
          onMouseEnter={() => s.iso3 && onHover(s.iso3)}
          onMouseLeave={() => onHover(null)}
          onClick={() => s.iso3 && onPick(s.iso3)}
        />
      ))}
    </>
  );
});

interface Props {
  fillFor: (iso3: string) => string;
  onSelect?: (iso3: string) => void;
  selected?: string | null;
  tooltipFor?: (iso3: string) => ReactNode;
  focus?: MapFocus | null; // turn here whenever it changes
  interactive?: boolean; // drag, zoom and tooltip
  controls?: boolean;
  fill?: boolean; // cover the positioned parent instead of keeping the 2:1 shape
  className?: string;
  children?: ReactNode; // pins, agents and trails above the countries
}

/** Light globe: spins while idle, turns to its focus, drag to rotate, pins that keep their size while zooming. */
export function WorldMap({ fillFor, onSelect, selected, tooltipFor, focus, interactive = true, controls = interactive, fill = false, className = "", children }: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(MAP_HEIGHT);
  useEffect(() => {
    const box = boxRef.current;
    if (!fill || !box) return;
    // match the drawing to the box, so the map covers it without letterboxing
    const observer = new ResizeObserver(([entry]) => {
      const { width, height: h } = entry.contentRect;
      if (width > 0 && h > 0) setHeight(Math.round((MAP_WIDTH * h) / width));
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, [fill]);
  const heightRef = useRef(height);
  heightRef.current = height;

  const target = !focus ? null : "fit" in focus ? fitView(focus, height) : focus;
  const [view, setView] = useState<MapView>(target ?? WORLD_VIEW);
  const [hover, setHover] = useState<string | null>(null);
  const [settled, setSettled] = useState(true);
  const viewRef = useRef(view);
  viewRef.current = view;
  const tipRef = useRef<HTMLDivElement | null>(null);
  const mouse = useRef({ x: 0, y: 0 });
  const flight = useRef<AnimationPlaybackControls | null>(null);
  const settleTimer = useRef<ReturnType<typeof setTimeout>>();
  const pointerInside = useRef(false);
  const drag = useRef<{ x: number; y: number; from: MapView } | null>(null);
  const dragged = useRef(false);

  // every motion goes through here: rough outlines while turning, detailed ones once still
  const move = useCallback((next: MapView) => {
    viewRef.current = next;
    setView(next);
    setSettled(false);
    clearTimeout(settleTimer.current);
    settleTimer.current = setTimeout(() => setSettled(true), SETTLE_MS);
  }, []);
  useEffect(() => () => clearTimeout(settleTimer.current), []);

  const land = () => {
    flight.current?.stop();
    flight.current = null;
  };

  const flyTo = useCallback(
    (to: MapView, duration = 1.1) => {
      flight.current?.stop();
      const from = viewRef.current;
      const along = geoInterpolate(from.coordinates, to.coordinates); // great circle, the short way round
      const controls = animate(0, 1, {
        duration,
        ease: [0.22, 1, 0.36, 1],
        onUpdate: (t) => move({ coordinates: along(t), zoom: from.zoom * Math.pow(to.zoom / from.zoom, t) }),
        onComplete: () => {
          if (flight.current === controls) flight.current = null;
        },
      });
      flight.current = controls;
      return controls;
    },
    [move],
  );

  const fx = target?.coordinates[0];
  const fy = target?.coordinates[1];
  const fz = target?.zoom;
  useEffect(() => {
    if (fx === undefined || fy === undefined || fz === undefined) return;
    const controls = flyTo({ coordinates: [fx, fy], zoom: fz });
    return () => {
      controls.stop();
      if (flight.current === controls) flight.current = null;
    };
  }, [fx, fy, fz, flyTo]);

  // spin slowly while nothing is in focus and nobody is pointing at the globe
  const idle = !focus || (!("fit" in focus) && focus.zoom <= 1);
  const idleRef = useRef(idle);
  idleRef.current = idle;
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(now - last, 100) / 1000;
      last = now;
      const v = viewRef.current;
      if (idleRef.current && !pointerInside.current && !drag.current && !flight.current && v.zoom <= SPIN_UP_TO) {
        move({ coordinates: [wrapLon(v.coordinates[0] - SPIN_SPEED * dt), v.coordinates[1]], zoom: v.zoom });
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [move]);

  // drag to turn the globe; the window keeps listening so a drag may leave the frame
  useEffect(() => {
    if (!interactive) return;
    const onMove = (e: PointerEvent) => {
      const d = drag.current;
      const box = boxRef.current?.getBoundingClientRect();
      if (!d || !box) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      if (!dragged.current && Math.hypot(dx, dy) < 4) return;
      dragged.current = true;
      const degPerPx = (MAP_WIDTH / box.width) * (180 / Math.PI) / (globeRadius(heightRef.current) * d.from.zoom);
      move({ coordinates: [wrapLon(d.from.coordinates[0] - dx * degPerPx), clamp(d.from.coordinates[1] + dy * degPerPx, -85, 85)], zoom: d.from.zoom });
    };
    const onUp = () => {
      drag.current = null;
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [interactive, move]);

  // plain scrolling keeps scrolling the page; pinch or ⌘/Ctrl + scroll zooms
  useEffect(() => {
    const box = boxRef.current;
    if (!interactive || !box) return;
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      land();
      const v = viewRef.current;
      move({ ...v, zoom: clamp(v.zoom * Math.exp(-e.deltaY * 0.002), 1, MAX_ZOOM) });
    };
    box.addEventListener("wheel", onWheel, { passive: false });
    return () => box.removeEventListener("wheel", onWheel);
  }, [interactive, move]);

  const projection = useMemo(() => globeProjection(view, height), [view, height]);
  const radius = globeRadius(height) * view.zoom;

  const placeTip = () => {
    const box = boxRef.current?.getBoundingClientRect();
    const tip = tipRef.current;
    if (!box || !tip) return;
    const flip = mouse.current.x > box.width - 260;
    tip.style.transform = `translate(${flip ? mouse.current.x - tip.offsetWidth - 16 : mouse.current.x + 16}px, ${mouse.current.y + 16}px)`;
  };

  const pick = useCallback(
    (iso3: string) => {
      if (!dragged.current) onSelect?.(iso3); // a drag that ends on a country is not a click
    },
    [onSelect],
  );
  const hoverCountry = useCallback(
    (iso3: string | null) => {
      if (interactive) setHover(iso3);
    },
    [interactive],
  );
  const zoomBtn = "grid h-8 w-8 place-items-center text-mint-900 transition-colors hover:bg-mint-50";

  return (
    <div
      ref={boxRef}
      className={`${fill ? "absolute inset-0" : "relative"} overflow-hidden ${interactive ? "cursor-grab active:cursor-grabbing" : ""} ${className}`}
      style={interactive ? { touchAction: "pan-y" } : undefined}
      onPointerEnter={() => (pointerInside.current = interactive)}
      onPointerLeave={() => (pointerInside.current = false)}
      onPointerDown={(e) => {
        if (!interactive || e.button !== 0) return;
        land();
        drag.current = { x: e.clientX, y: e.clientY, from: viewRef.current };
        dragged.current = false;
      }}
      onMouseMove={(e) => {
        const box = boxRef.current?.getBoundingClientRect();
        if (!box) return;
        mouse.current = { x: e.clientX - box.left, y: e.clientY - box.top };
        placeTip();
      }}
    >
      <ComposableMap projection={projection as unknown as ProjectionFunction} width={MAP_WIDTH} height={height} className={fill ? "h-full w-full" : "h-auto w-full"}>
        <defs>
          <radialGradient id="map-ocean" cx="40%" cy="35%" r="75%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="100%" stopColor="#e3eeec" />
          </radialGradient>
          <radialGradient id="map-shade" cx="36%" cy="30%" r="75%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity={0.25} />
            <stop offset="55%" stopColor="#02312f" stopOpacity={0} />
            <stop offset="100%" stopColor="#02312f" stopOpacity={0.14} />
          </radialGradient>
          <radialGradient id="map-atmosphere">
            <stop offset={radius / (radius + 22)} stopColor="#27dac2" stopOpacity={0.18} />
            <stop offset="100%" stopColor="#27dac2" stopOpacity={0} />
          </radialGradient>
        </defs>
        <circle cx={MAP_WIDTH / 2} cy={height / 2} r={radius + 22} fill="url(#map-atmosphere)" pointerEvents="none" />
        <Sphere id="map-sphere" fill="url(#map-ocean)" stroke="rgba(17,80,75,0.12)" strokeWidth={0.6} />
        <Graticule stroke="rgba(17,80,75,0.06)" strokeWidth={0.5} />
        <Countries shapes={settled ? COUNTRY_SHAPES : COARSE_COUNTRY_SHAPES} fillFor={fillFor} selected={selected} clickable={!!onSelect} onPick={pick} onHover={hoverCountry} />
        <Sphere id="map-sphere-shade" fill="url(#map-shade)" stroke="none" strokeWidth={0} pointerEvents="none" />
        <ZoomContext.Provider value={view.zoom}>{children}</ZoomContext.Provider>
      </ComposableMap>

      {controls && (
        <div className="absolute right-3 top-3 flex items-center gap-2" onPointerDown={(e) => e.stopPropagation()}>
          <div className="flex overflow-hidden rounded-md bg-white text-xs font-medium text-mint-900 shadow-card ring-1 ring-mint-900/10">
            <button type="button" className="px-3 py-1.5 transition-colors hover:bg-mint-50" onClick={() => flyTo(WORLD_VIEW)}>
              World
            </button>
            <button type="button" className="border-l border-mint-900/10 px-3 py-1.5 transition-colors hover:bg-mint-50" onClick={() => flyTo(EUROPE_VIEW)}>
              Europe
            </button>
          </div>
          <div className="flex overflow-hidden rounded-md bg-white shadow-card ring-1 ring-mint-900/10">
            <button type="button" className={zoomBtn} aria-label="Zoom in" onClick={() => flyTo({ ...viewRef.current, zoom: Math.min(viewRef.current.zoom * 1.6, MAX_ZOOM) }, 0.4)}>
              <Plus size={14} />
            </button>
            <button type="button" className={`${zoomBtn} border-l border-mint-900/10`} aria-label="Zoom out" onClick={() => flyTo({ ...viewRef.current, zoom: Math.max(viewRef.current.zoom / 1.6, 1) }, 0.4)}>
              <Minus size={14} />
            </button>
          </div>
        </div>
      )}

      {hover && (
        <div
          ref={(el) => {
            tipRef.current = el;
            if (el) placeTip();
          }}
          className="pointer-events-none absolute left-0 top-0 z-10 min-w-40 rounded-lg bg-white px-3.5 py-2.5 shadow-lift ring-1 ring-mint-900/10"
        >
          <div className="flex items-center gap-2 font-semibold text-mint-950">
            <span className="text-xl leading-none">{flag(hover)}</span>
            {countryName(hover)}
          </div>
          {tooltipFor && <div className="mt-1 text-xs text-mint-900/65">{tooltipFor(hover)}</div>}
        </div>
      )}
    </div>
  );
}

/** Anything pinned to a place; hidden on the far side of the globe, shrinks back while zooming so pins stay readable. */
export function MapPin({ at, children, onClick, className }: { at?: [number, number]; children: ReactNode; onClick?: () => void; className?: string }) {
  const zoom = useContext(ZoomContext);
  const { projection } = useMapContext();
  if (!at) return null;
  const [lon, lat] = projection.rotate();
  if (geoDistance(at, [-lon, -lat]) > Math.PI / 2 - 0.03) return null;
  return (
    <Marker coordinates={at} onClick={onClick} className={className}>
      <g transform={`scale(${1 / Math.sqrt(zoom)})`}>{children}</g>
    </Marker>
  );
}

/** An agent at work on the map: robot with magnifying glass over radar ripples. */
export function AgentPin({ at, kind = "scout", label }: { at?: [number, number]; kind?: AgentKind; label?: string }) {
  const a = AGENTS[kind];
  return (
    <MapPin at={at}>
      <circle r={10} fill={a.color} opacity={0.45} className="svg-ripple" />
      <circle r={10} fill={a.color} opacity={0.3} className="svg-ripple" style={{ animationDelay: "1.1s" }} />
      <circle r={3.2} fill={a.color} />
      <AgentBot color={a.color} magnifier={a.magnifier} size={46} x={-23} y={-54} />
      {label && (
        <text y={22} textAnchor="middle" fontSize={10.5} fontWeight={600} fill="#02312f" stroke="#ffffff" strokeWidth={3.5} paintOrder="stroke" fontFamily="Hanken Grotesk, sans-serif">
          {label}
        </text>
      )}
    </MapPin>
  );
}

/** Flag in a ring of the status colour. */
export function FlagPin({ iso3, color, onClick, small }: { iso3: string; color: string; onClick?: () => void; small?: boolean }) {
  const r = small ? 9 : 12;
  return (
    <>
      <circle r={r + 3} fill="#ffffff" opacity={0.9} />
      <circle r={r} fill="#ffffff" stroke={color} strokeWidth={2.4} style={{ cursor: onClick ? "pointer" : undefined }} onClick={onClick} />
      <text textAnchor="middle" dominantBaseline="central" fontSize={small ? 10 : 13} y={0.5} style={{ pointerEvents: "none" }}>
        {flag(iso3)}
      </text>
    </>
  );
}

/** Dashed route the agent travelled. */
export function Trail({ from, to, color }: { from?: [number, number]; to?: [number, number]; color: string }) {
  if (!from || !to) return null;
  return <Line from={from} to={to} stroke={color} strokeWidth={1.4} strokeLinecap="round" strokeDasharray="3 5" className="animate-dash" fill="none" opacity={0.8} />;
}

/** Tween between two [lon, lat] positions so an agent glides instead of jumping. */
export function useGlide(target?: [number, number], duration = 0.55): [number, number] | undefined {
  const [pos, setPos] = useState(target);
  const current = useRef(target);
  const tx = target?.[0];
  const ty = target?.[1];
  useEffect(() => {
    if (tx === undefined || ty === undefined) {
      current.current = undefined;
      setPos(undefined);
      return;
    }
    const from = current.current;
    if (!from) {
      current.current = [tx, ty];
      setPos([tx, ty]);
      return;
    }
    const controls = animate(0, 1, {
      duration,
      ease: "easeInOut",
      onUpdate: (t) => {
        const p: [number, number] = [from[0] + (tx - from[0]) * t, from[1] + (ty - from[1]) * t];
        current.current = p;
        setPos(p);
      },
    });
    return () => controls.stop();
  }, [tx, ty, duration]);
  return pos;
}
