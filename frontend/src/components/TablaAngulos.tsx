import type { Angulo } from "../types/caso";
import { ETIQUETA_SEGMENTO, semaforoSegmento } from "../lib/niveles";
import { Semaforo } from "./Semaforo";

const ESTADO: Record<Angulo["estado"], string> = { ok: "OK", revisar: "Revisar", sin_dato: "Sin dato" };

export function TablaAngulos({ angulos }: { angulos: Angulo[] }) {
  return (
    <div className="tabla-scroll">
      <table>
        <thead>
          <tr>
            <th>Segmento</th><th>Vista</th><th>Ángulo</th><th>Puntaje REBA</th>
            <th>Modificadores</th><th>Estado</th><th>Capturado en piso</th>
          </tr>
        </thead>
        <tbody>
          {angulos.map(a => {
            const discrepa = a.puntaje_previo != null && a.puntaje_previo !== a.puntaje_reba;
            return (
              <tr key={`${a.segmento}-${a.lado ?? ""}`}>
                <td>{ETIQUETA_SEGMENTO[a.segmento]}{a.lado ? ` (${a.lado})` : ""}</td>
                <td>{a.vista}</td>
                <td>{a.angulo_grados === null ? "—" : `${a.angulo_grados.toFixed(1)}°`}</td>
                <td><Semaforo color={semaforoSegmento(a.puntaje_reba)} texto="" valor={a.puntaje_reba} /></td>
                <td>{a.modificadores.length ? a.modificadores.join(", ") : "—"}</td>
                <td><span className={`estado estado-${a.estado}`}>{ESTADO[a.estado]}</span></td>
                <td className={discrepa ? "discrepancia" : ""}>
                  {a.puntaje_previo ?? "—"}{discrepa ? " ⚠ no coincide" : ""}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}