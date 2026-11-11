import { useMemo, useRef, useState } from "react";
import type { Hallazgo, Imagen, Punto } from "../types/caso";
import { urlImagen } from "../api";

// Pares COCO-17 que forman el esqueleto y el segmento REBA al que pertenecen
export const ARISTAS: { a: number; b: number; segmento: string }[] = [
  { a: 5, b: 6, segmento: "tronco" }, { a: 11, b: 12, segmento: "tronco" },
  { a: 5, b: 11, segmento: "tronco" }, { a: 6, b: 12, segmento: "tronco" },
  { a: 5, b: 7, segmento: "brazo" }, { a: 6, b: 8, segmento: "brazo" },
  { a: 7, b: 9, segmento: "antebrazo" }, { a: 8, b: 10, segmento: "antebrazo" },
  { a: 11, b: 13, segmento: "piernas" }, { a: 13, b: 15, segmento: "piernas" },
  { a: 12, b: 14, segmento: "piernas" }, { a: 14, b: 16, segmento: "piernas" },
  { a: 3, b: 5, segmento: "cuello" }, { a: 4, b: 6, segmento: "cuello" },
  // Nudillo medio (17 izq, 18 der): solo en casos analizados con RTMPose WholeBody-133
  { a: 9, b: 17, segmento: "muneca" }, { a: 10, b: 18, segmento: "muneca" },
];

interface Props {
  imagen: Imagen;
  editable?: boolean;
  onCommit?: (puntos: Punto[]) => void; // se llama al soltar un punto
  colorSegmento?: (segmento: string) => string;
  cajas?: Hallazgo[]; // recuadros de objetos detectados
  confianzaMinima?: number;
  mostrar?: boolean;
}

export function SkeletonEditor({
  imagen, editable = true, onCommit, colorSegmento, cajas = [], confianzaMinima = 0.4, mostrar = false,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [puntos, setPuntos] = useState<Punto[]>(imagen.puntos);
  const puntosRef = useRef(puntos);
  const [arrastrando, setArrastrando] = useState<number | null>(null);
  // Comparar valores, no referencias: un refetch idéntico no debe borrar una edición local.
  const origen = JSON.stringify([imagen.url, imagen.vista, imagen.ancho, imagen.alto, imagen.persona_seleccionada,
    imagen.puntos.map(p => [p.id, p.x, p.y, p.confianza, p.corregido])]);
  const [origenAnterior, setOrigenAnterior] = useState(origen);
  if (origen !== origenAnterior) {
    setOrigenAnterior(origen);
    setPuntos(imagen.puntos);
    puntosRef.current = imagen.puntos;
    setArrastrando(null);
  }

  const dentroDeImagen = (p: Punto) => Number.isFinite(p.x) && Number.isFinite(p.y)
    && p.x >= 0 && p.y >= 0 && p.x <= imagen.ancho && p.y <= imagen.alto;
  const fiable = (p: Punto) => p.corregido || (Number.isFinite(p.confianza)
    && p.confianza >= confianzaMinima && p.confianza <= 1);
  const todas = !!imagen.personas?.length && !imagen.persona_seleccionada;
  const puedeEditar = editable && mostrar && !todas;
  const grupos = todas ? imagen.personas! : [{ id: imagen.persona_seleccionada ?? 'legacy', puntos }];
  const porPersona = useMemo(() => grupos.map(persona => ({ ...persona,
    puntos: persona.puntos.filter(p => dentroDeImagen(p) && fiable(p)
      && !persona.puntos.some(q => q.id !== p.id && dentroDeImagen(q) && fiable(q)
        && Math.abs(p.x - q.x) <= 1 && Math.abs(p.y - q.y) <= 1)),
  })), [grupos, confianzaMinima, imagen.ancho, imagen.alto]);
  const r = Math.max(imagen.ancho, imagen.alto) * 0.008;

  const actualizar = (siguiente: Punto[]) => {
    puntosRef.current = siguiente;
    setPuntos(siguiente);
  };

  const aCoordenadasImagen = (e: React.PointerEvent) => {
    const ctm = svgRef.current?.getScreenCTM();
    if (!ctm) return null;
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(ctm.inverse());
    return {
      x: Math.round(Math.min(Math.max(p.x, 0), imagen.ancho)),
      y: Math.round(Math.min(Math.max(p.y, 0), imagen.alto)),
    };
  };

  const alMover = (e: React.PointerEvent) => {
    if (!puedeEditar || arrastrando === null) return;
    const p = aCoordenadasImagen(e);
    if (!p) return;
    actualizar(puntosRef.current.map(k => (k.id === arrastrando ? { ...k, ...p, corregido: true } : k)));
  };

  const alSoltar = () => {
    if (arrastrando === null) return;
    setArrastrando(null);
    if (puedeEditar) onCommit?.(puntosRef.current);
  };

  const alTecla = (e: React.KeyboardEvent, k: Punto) => {
    if (!puedeEditar) return;
    const direccion: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
    };
    const delta = direccion[e.key];
    if (!delta) return;
    e.preventDefault();
    const paso = e.shiftKey ? 10 : 1;
    actualizar(puntosRef.current.map(p => p.id === k.id ? {
      ...p,
      x: Math.min(imagen.ancho, Math.max(0, p.x + delta[0] * paso)),
      y: Math.min(imagen.alto, Math.max(0, p.y + delta[1] * paso)),
      corregido: true,
    } : p));
    onCommit?.(puntosRef.current);
  };

  return (
    <svg
      ref={svgRef}
      className="esqueleto"
      viewBox={`0 0 ${imagen.ancho} ${imagen.alto}`}
      onPointerMove={alMover}
      onPointerUp={alSoltar}
      onPointerCancel={alSoltar}
    >
      <image href={urlImagen(imagen.url)} width={imagen.ancho} height={imagen.alto} />

      {mostrar && cajas.filter(h => h.caja).map(h => {
        const [x, y, w, hgt] = h.caja!;
        return (
          <g key={h.id}>
            <rect x={x} y={y} width={w} height={hgt} fill="none" stroke="#E8790C" strokeWidth={r * 0.5} strokeDasharray={`${r * 1.5} ${r}`} />
            <text x={x} y={y - r} fill="#E8790C" fontSize={r * 3} fontWeight={700}>{h.mensaje.split(" ")[0]}</text>
          </g>
        );
      })}

      {mostrar && porPersona.map(persona => <g key={persona.id} aria-label={`Esqueleto ${persona.id}`}>
      {ARISTAS.map(({ a, b, segmento }) => {
        const p = persona.puntos.find(p => p.id === a), q = persona.puntos.find(p => p.id === b);
        if (!p || !q || !dentroDeImagen(p) || !dentroDeImagen(q) || !fiable(p) || !fiable(q)) return null;
        return (
          <line key={`${a}-${b}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y}
            stroke={colorSegmento?.(segmento) ?? "var(--jabil-cyan)"}
            strokeWidth={r * 0.8} strokeLinecap="round" opacity={0.9} />
        );
      })}

      {persona.puntos.map(k => {
        const baja = !fiable(k);
        return (
          <circle key={k.id} cx={k.x} cy={k.y} r={arrastrando === k.id ? r * 1.5 : r}
            fill={baja ? "white" : k.corregido ? "var(--jabil-navy)" : "var(--jabil-cyan)"}
            stroke={baja ? "#E8790C" : "white"} strokeWidth={r * 0.35}
            strokeDasharray={baja ? `${r * 0.6} ${r * 0.4}` : undefined}
            style={{ cursor: puedeEditar ? "grab" : "default" }}
            tabIndex={puedeEditar ? 0 : undefined}
            role={puedeEditar ? "button" : undefined}
            aria-label={`Punto ${k.id}. Confianza ${Number.isFinite(k.confianza) ? `${(k.confianza * 100).toFixed(0)}%` : "desconocida"}${k.corregido ? ". Corregido" : ""}${puedeEditar ? ". Mover con flechas; Mayús para 10 píxeles." : ""}`}
            onKeyDown={e => alTecla(e, k)}
            onPointerDown={e => {
              if (!puedeEditar) return;
              (e.target as Element).setPointerCapture(e.pointerId);
              setArrastrando(k.id);
            }}>
            <title>{`Punto ${k.id} · confianza ${(k.confianza * 100).toFixed(0)}%${k.corregido ? " · corregido" : ""}`}</title>
          </circle>
        );
      })}
      </g>)}
    </svg>
  );
}