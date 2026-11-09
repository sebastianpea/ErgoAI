import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

const fmt = (v: number | null, unidad: string) => (v == null ? "—" : `${v.toLocaleString("es-MX")} ${unidad}`);

/** Tiempos reales medidos en los casos analizados desde fotos frente a la evaluación manual (criterio 8). */
export function TarjetaImpacto() {
  const { data } = useQuery({ queryKey: ["impacto"], queryFn: api.impacto });
  if (!data) return null;
  const hayDatos = data.casos.length > 0;

  return (
    <div className="tarjeta impacto">
      <h2>Impacto en tiempos de respuesta</h2>
      {!hayDatos ? (
        <p className="sutil">
          Aún no hay casos analizados desde fotos. Cada caso nuevo registra cuánto tarda el análisis automático y
          cuánto tarda el especialista en dejar el plan validado.
        </p>
      ) : (
        <>
          <div className="impacto-cifras">
            <div><span className="cifra-valor">{fmt(data.analisis_promedio_s, "s")}</span>
              <span className="cifra-texto">Análisis automático (promedio)</span></div>
            <div><span className="cifra-valor">{fmt(data.validacion_promedio_min, "min")}</span>
              <span className="cifra-texto">Hasta plan validado (con revisión humana)</span></div>
            <div><span className="cifra-valor">{fmt(data.minutos_evaluacion_manual, "min")}</span>
              <span className="cifra-texto">Evaluación manual de referencia</span></div>
            <div><span className="cifra-valor">{data.ahorro_porcentaje == null ? "—" : `${data.ahorro_porcentaje}%`}</span>
              <span className="cifra-texto">Reducción de tiempo</span></div>
          </div>
          <div className="tabla-scroll">
            <table>
              <thead><tr><th>Caso</th><th>Estación</th><th>Análisis</th><th>Hasta validación</th></tr></thead>
              <tbody>
                {data.casos.map(c => (
                  <tr key={c.id_caso}>
                    <td>{c.id_caso}</td><td>{c.estacion}</td>
                    <td>{fmt(c.analisis_s, "s")}</td>
                    <td>{c.validacion_min == null ? "Pendiente" : fmt(c.validacion_min, "min")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <p className="leyenda">Referencia manual: {data.fuente_referencia_manual}.</p>
    </div>
  );
}
