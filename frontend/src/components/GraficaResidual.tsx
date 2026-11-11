import type { Residual } from "../types/caso";
import { COLOR_SEMAFORO, ETIQUETA_SEGMENTO, NIVEL_REBA } from "../lib/niveles";
import { Semaforo } from "./Semaforo";
import { PaginationControls, usePagination } from "./PaginationControls";

/** Barras antes/después por segmento, sin librerías. */
export function GraficaResidual({ residual }: { residual: Residual }) {
  const pagination = usePagination(residual.segmentos.length);
  const max = Math.max(4, ...residual.segmentos.flatMap(s => [s.antes, s.despues]));
  const antes = NIVEL_REBA[residual.antes_nivel];
  const despues = NIVEL_REBA[residual.despues_nivel];
  const cambio = Math.round((1 - residual.despues_final / residual.antes_final) * 100);
  const textoCambio = cambio > 0
    ? `Reducción de ${cambio}% en el puntaje REBA`
    : cambio < 0 ? `Aumento de ${-cambio}% en el puntaje REBA` : "Sin cambio en el puntaje REBA";

  return (
    <div>
      <div className="residual-total">
        <Semaforo color={antes.color} texto={antes.etiqueta} valor={residual.antes_final} />
        <span className="flecha">→</span>
        <Semaforo color={despues.color} texto={despues.etiqueta} valor={residual.despues_final} />
        <span className="sutil">{textoCambio}</span>
      </div>

      <PaginationControls {...pagination} label="segmentos residuales" />
      <div className="barras">
        {residual.segmentos.map((s, i) => (
          <div key={s.segmento} className={`barra-fila ${pagination.rowClass(i)}`}>
            <span className="barra-etiqueta">{ETIQUETA_SEGMENTO[s.segmento]}</span>
            <div className="barra-par">
              <div className="barra-valor" style={{ width: `${(s.antes / max) * 100}%`, background: COLOR_SEMAFORO.gris }}>{s.antes}</div>
              <div className="barra-valor" style={{ width: `${(s.despues / max) * 100}%`, background: "var(--jabil-cyan)" }}>{s.despues}</div>
            </div>
          </div>
        ))}
      </div>
      <p className="leyenda">
        <span className="cuadro" style={{ background: COLOR_SEMAFORO.gris }} /> Actual
        <span className="cuadro" style={{ background: "var(--jabil-cyan)" }} />
        {residual.recomendaciones_aplicadas.length
          ? `Con recomendaciones ${residual.recomendaciones_aplicadas.join(", ")}`
          : "Sin recomendaciones con efecto modelado"}
      </p>
    </div>
  );
}