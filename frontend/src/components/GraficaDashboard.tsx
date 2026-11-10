import { useState } from "react";

interface DatoGrafica {
  etiqueta: string;
  valor: number;
  color?: string;
}

// Colores categóricos de marca, no el semáforo de seguridad REBA.
const PALETA = ["var(--jabil-navy)", "var(--jabil-cyan)", "var(--gris-plata)", "#536B88", "#687080", "#246F91"];

/** Conteos y porcentajes siempre visibles; los botones nativos no requieren hover. */
export function GraficaDashboard({ titulo, datos }: { titulo: string; datos: DatoGrafica[] }) {
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const total = datos.reduce((sum, d) => sum + d.valor, 0);
  const valido = datos.every(d => Number.isFinite(d.valor) && d.valor >= 0) && Number.isFinite(total);
  const seleccionado = datos.find(d => d.etiqueta === seleccion);
  const porcentaje = (valor: number) => valido && total > 0 ? valor / total * 100 : 0;
  const textoPorcentaje = (valor: number) => `${Number(porcentaje(valor).toFixed(1))}%`;
  let acumulado = 0;

  return (
    <figure className="tarjeta grafica-dashboard">
      <figcaption>{titulo}</figcaption>
      <div className="grafica-contenido">
        <div className="grafica-donut">
          <svg viewBox="0 0 240 240" aria-hidden="true" focusable="false">
            <circle className="grafica-fondo" cx="120" cy="120" r="96" fill="none" strokeWidth="28" />
            {valido && datos.map((d, i) => {
              const parte = porcentaje(d.valor);
              const inicio = acumulado;
              acumulado += parte;
              return d.valor > 0 ? <circle key={d.etiqueta}
                className={`grafica-segmento${seleccionado?.etiqueta === d.etiqueta ? " seleccionado" : ""}`}
                cx="120" cy="120" r="96" fill="none" strokeWidth={seleccionado?.etiqueta === d.etiqueta ? 36 : 28}
                stroke={d.color ?? PALETA[i % PALETA.length]} pathLength={100}
                strokeDasharray={`${parte} ${100 - parte}`} strokeDashoffset={-inicio || 0}
                transform="rotate(-90 120 120)" /> : null;
            })}
          </svg>
          <div className="grafica-centro" aria-live="polite" aria-atomic="true">
            <span>{seleccionado?.etiqueta ?? "Total"}</span>
            <strong>{valido ? (seleccionado?.valor ?? total) : "—"}</strong>
            <span>{valido ? (seleccionado ? textoPorcentaje(seleccionado.valor) : "casos") : "No disponible"}</span>
          </div>
        </div>
        <div className="grafica-leyenda">
          <ul>
            {datos.map((d, i) => <li key={d.etiqueta}>
              <button type="button" aria-pressed={seleccionado?.etiqueta === d.etiqueta}
                onClick={() => setSeleccion(seleccion === d.etiqueta ? null : d.etiqueta)}>
                <span className="grafica-muestra" aria-hidden="true" style={{ background: d.color ?? PALETA[i % PALETA.length] }} />
                <span className="grafica-etiqueta">{d.etiqueta}</span><strong>{Number.isFinite(d.valor) && d.valor >= 0 ? d.valor : "Dato no válido"}</strong>
                <span className="grafica-porcentaje">{valido ? textoPorcentaje(d.valor) : "—"}</span>
                {seleccionado?.etiqueta === d.etiqueta && <span className="grafica-seleccion">Seleccionado</span>}
              </button>
            </li>)}
          </ul>
          {seleccionado && <button className="grafica-restablecer" type="button" onClick={() => setSeleccion(null)}>Ver total</button>}
        </div>
      </div>
      <p className="grafica-nota">{!valido ? "No se puede representar esta distribución: revise los conteos."
        : !datos.length ? "Sin datos para esta distribución."
        : total === 0 ? "Sin casos en esta distribución."
        : "Porcentaje del total mostrado · selecciona una categoría para ver el detalle."}</p>
    </figure>
  );
}
