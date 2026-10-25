import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { animate } from "motion/react";
import { Minus, Plus } from "lucide-react";
import { geoEqualEarth, geoPath } from "d3-geo";
import { ComposableMap, Graticule, Line, Marker, Sphere, ZoomableGroup, useMapContext } from "react-simple-maps";
import { AGENTS, type AgentKind } from "../lib/agents";
import { COUNTRY_SHAPES, countryName, flag } from "../lib/geo";
import { UNTESTED_FILL } from "../lib/labels";
import { AgentBot } from "./Agent";

export interface MapView {
  coordinates: [number, number];
  zoom: number;
}

/** Places to frame instead of a fixed view. */
export interface Framing {
  fit: [number, number][];
  maxZoom?: number;
  inset?: { top: number; bottom: number }; // share of the frame to keep clear, e.g. under an overlay card
}

export type MapFocus = MapView | Framing;

export const WORLD_VIEW: MapView = { coordinates: [8, 12], zoom: 1 };
export const EUROPE_VIEW: MapView = { coordinates: [14, 51], zoom: 3.6 };

const MAP_WIDTH = 900;
const MAP_HEIGHT = 450;
const MAP_SCALE = 168;
const projection = geoEqualEarth().scale(MAP_SCALE).translate([MAP_WIDTH / 2, MAP_HEIGHT / 2]);
const [[globeLeft, globeTop], [globeRight, globeBottom]] = geoPath(projection).bounds({ type: "Sphere" });

/** Centre and zoom that frame the places in a map of the given height. */
export function fitView({ fit, maxZoom = 4, inset = { top: 0, bottom: 0 } }: Framing, height = MAP_HEIGHT): MapView {
  const points = fit.map((p) => projection(p)).filter((p): p is [number, number] => !!p);
  if (!points.length) return WORLD_VIEW;
  const pad = 36; // margin on screen, whatever the zoom
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const free = height * (1 - inset.top - inset.bottom);
  const zoom = Math.min(maxZoom, (MAP_WIDTH - 2 * pad) / Math.max(x1 - x0, 1), (free - 2 * pad) / Math.max(y1 - y0, 1));
  if (zoom <= 1) return WORLD_VIEW;
  // shifted so the places sit in the middle of the free band
  const centre = projection.invert?.([(x0 + x1) / 2, (y0 + y1) / 2 + ((inset.bottom - inset.top) * height) / 2 / zoom]);
  return centre ? { coordinates: centre, zoom } : WORLD_VIEW;
}

/** Shifts a zoomed-in view so it does not show past the globe's edge where the frame allows. */
function keepOnGlobe(view: MapView, height: number): MapView {
  const at = view.zoom > 1 ? projection(view.coordinates) : null;
  if (!at) return view;
  const clamp = (c: number, half: number, lo: number, hi: number) => (hi - lo <= 2 * half ? (lo + hi) / 2 : Math.min(hi - half, Math.max(lo + half, c)));
  const centre = projection.invert?.([clamp(at[0], MAP_WIDTH / 2 / view.zoom, globeLeft, globeRight), clamp(at[1], height / 2 / view.zoom, globeTop, globeBottom)]);
  return centre ? { coordinates: centre, zoom: view.zoom } : view;
}

const ZoomContext = createContext(1);

// d3-zoom hands over the DOM event. Plain scrolling keeps scrolling the page; pinch or ⌘/Ctrl + scroll zooms.
const allowGesture = (event: unknown) => {
  const e = event as WheelEvent | null;
  if (!e) return false;
  return e.type === "wheel" ? e.ctrlKey || e.metaKey : !e.button;
};
const noGesture = () => false;

interface CountriesProps {
  fillFor: (iso3: string) => string;
  glowFor?: (iso3: string) => string | null;
  selected?: string | null;
  clickable: boolean;
  onPick: (iso3: string) => void;
  onHover: (iso3: string | null) => void;
}

const Countries = memo(function Countries({ fillFor, glowFor, selected, clickable, onPick, onHover }: CountriesProps) {
  const { path } = useMapContext();
  const shapes = useMemo(() => COUNTRY_SHAPES.map((s) => ({ ...s, d: path(s.feature) ?? "" })), [path]);
  return (
    <>
      {glowFor && (
        <g filter="url(#map-glow)" opacity={0.85}>
          {shapes.map((s) => {
            const colour = s.iso3 ? glowFor(s.iso3) : null;
            return colour ? <path key={s.key} d={s.d} fill={colour} /> : null;
          })}
        </g>
      )}
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
  glowFor?: (iso3: string) => string | null;
  onSelect?: (iso3: string) => void;
  selected?: string | null;
  tooltipFor?: (iso3: string) => ReactNode;
  focus?: MapFocus | null; // fly here whenever it changes
  interactive?: boolean; // pan, zoom and tooltip
  controls?: boolean;
  fill?: boolean; // cover the positioned parent instead of keeping the 2:1 shape
  className?: string;
  children?: ReactNode; // pins, agents and trails above the countries
}

/** Dark world map: glowing countries, smooth fly-to, pins that keep their size while zooming. */
export function WorldMap({ fillFor, glowFor, onSelect, selected, tooltipFor, focus, interactive = true, controls = interactive, fill = false, className = "", children }: Props) {
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

  const target = !focus ? null : keepOnGlobe("fit" in focus ? fitView(focus, height) : focus, height);
  const [view, setView] = useState<MapView>(target ?? WORLD_VIEW);
  const [liveZoom, setLiveZoom] = useState(view.zoom);
  const [hover, setHover] = useState<string | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const tipRef = useRef<HTMLDivElement | null>(null);
  const mouse = useRef({ x: 0, y: 0 });

  const flyTo = useCallback((target: MapView, duration = 1.1) => {
    const from = viewRef.current;
    return animate(0, 1, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (t) => {
        const zoom = from.zoom * Math.pow(target.zoom / from.zoom, t);
        setView({
          coordinates: [
            from.coordinates[0] + (target.coordinates[0] - from.coordinates[0]) * t,
            from.coordinates[1] + (target.coordinates[1] - from.coordinates[1]) * t,
          ],
          zoom,
        });
        setLiveZoom(zoom);
      },
    });
  }, []);

  const fx = target?.coordinates[0];
  const fy = target?.coordinates[1];
  const fz = target?.zoom;
  useEffect(() => {
    if (fx === undefined || fy === undefined || fz === undefined) return;
    const controls = flyTo({ coordinates: [fx, fy], zoom: fz });
    return () => controls.stop();
  }, [fx, fy, fz, flyTo]);

  const placeTip = () => {
    const box = boxRef.current?.getBoundingClientRect();
    const tip = tipRef.current;
    if (!box || !tip) return;
    const flip = mouse.current.x > box.width - 260;
    tip.style.transform = `translate(${flip ? mouse.current.x - tip.offsetWidth - 16 : mouse.current.x + 16}px, ${mouse.current.y + 16}px)`;
  };

  const pick = useCallback((iso3: string) => onSelect?.(iso3), [onSelect]);
  const hoverCountry = useCallback(
    (iso3: string | null) => {
      if (interactive) setHover(iso3);
    },
    [interactive],
  );
  // stable handlers: react-simple-maps rebuilds its d3 zoom behaviour whenever they change
  const onMove = useCallback(({ zoom }: { zoom: number }) => setLiveZoom(zoom), []);
  const onMoveEnd = useCallback(({ coordinates, zoom }: { coordinates: [number, number]; zoom: number }) => setView({ coordinates, zoom }), []);
  const zoomBtn = "grid h-8 w-8 place-items-center text-slate-300 transition hover:bg-white/10 hover:text-white";

  return (
    <div
      ref={boxRef}
      className={`${fill ? "absolute inset-0" : "relative"} overflow-hidden ${className}`}
      onMouseMove={(e) => {
        const box = boxRef.current?.getBoundingClientRect();
        if (!box) return;
        mouse.current = { x: e.clientX - box.left, y: e.clientY - box.top };
        placeTip();
      }}
    >
      <ComposableMap projection="geoEqualEarth" projectionConfig={{ scale: MAP_SCALE }} width={MAP_WIDTH} height={height} className={fill ? "h-full w-full" : "h-auto w-full"}>
        <defs>
          <radialGradient id="map-ocean" cx="50%" cy="42%" r="70%">
            <stop offset="0%" stopColor="#0f1d3a" />
            <stop offset="100%" stopColor="#060b16" />
          </radialGradient>
          <filter id="map-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="5" />
          </filter>
        </defs>
        <ZoomableGroup
          key={fill ? height : undefined} // its transform only follows centre and zoom, so start afresh when the frame changes
          center={view.coordinates}
          zoom={view.zoom}
          minZoom={1}
          maxZoom={10}
          filterZoomEvent={interactive ? allowGesture : noGesture}
          onMove={onMove}
          onMoveEnd={onMoveEnd}
        >
          <Sphere id="map-sphere" fill="url(#map-ocean)" stroke="rgba(148,163,184,0.2)" strokeWidth={0.6} />
          <Graticule stroke="rgba(148,163,184,0.07)" strokeWidth={0.5} />
          <Countries fillFor={fillFor} glowFor={glowFor} selected={selected} clickable={!!onSelect} onPick={pick} onHover={hoverCountry} />
          <ZoomContext.Provider value={liveZoom}>{children}</ZoomContext.Provider>
        </ZoomableGroup>
      </ComposableMap>

      {controls && (
        <div className="absolute right-3 top-3 flex items-center gap-2">
          <div className="flex overflow-hidden rounded-full border border-white/10 bg-ink-900/80 text-xs font-semibold text-slate-300 backdrop-blur">
            <button type="button" className="px-3 py-1.5 transition hover:bg-white/10 hover:text-white" onClick={() => flyTo(WORLD_VIEW)}>
              Welt
            </button>
            <button type="button" className="border-l border-white/10 px-3 py-1.5 transition hover:bg-white/10 hover:text-white" onClick={() => flyTo(EUROPE_VIEW)}>
              Europa
            </button>
          </div>
          <div className="flex overflow-hidden rounded-full border border-white/10 bg-ink-900/80 backdrop-blur">
            <button type="button" className={zoomBtn} aria-label="Hineinzoomen" onClick={() => flyTo({ ...viewRef.current, zoom: Math.min(viewRef.current.zoom * 1.6, 10) }, 0.4)}>
              <Plus size={14} />
            </button>
            <button type="button" className={`${zoomBtn} border-l border-white/10`} aria-label="Herauszoomen" onClick={() => flyTo({ ...viewRef.current, zoom: Math.max(viewRef.current.zoom / 1.6, 1) }, 0.4)}>
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
          className="pointer-events-none absolute left-0 top-0 z-10 min-w-40 rounded-2xl border border-white/10 bg-ink-900/90 px-3.5 py-2.5 shadow-2xl backdrop-blur-xl"
        >
          <div className="flex items-center gap-2 font-semibold text-white">
            <span className="text-xl leading-none">{flag(hover)}</span>
            {countryName(hover)}
          </div>
          {tooltipFor && <div className="mt-1 text-xs text-slate-400">{tooltipFor(hover)}</div>}
        </div>
      )}
    </div>
  );
}

/** Anything pinned to a place; shrinks back while zooming so pins stay readable. */
export function MapPin({ at, children, onClick, className }: { at?: [number, number]; children: ReactNode; onClick?: () => void; className?: string }) {
  const zoom = useContext(ZoomContext);
  if (!at) return null;
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
        <text y={22} textAnchor="middle" fontSize={10.5} fontWeight={700} fill="#f1f5f9" stroke="#03060d" strokeWidth={3.5} paintOrder="stroke" fontFamily="Inter, sans-serif">
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
      <circle r={r + 4} fill={color} opacity={0.18} />
      <circle r={r} fill="#060b16" stroke={color} strokeWidth={2.2} style={{ cursor: onClick ? "pointer" : undefined }} onClick={onClick} />
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
