import { useState } from "react";
import type { Angulo, Segmento, Vista } from "../types/caso";
import { ETIQUETA_SEGMENTO, VISTAS, semaforoSegmento } from "../lib/niveles";
import { Semaforo } from "./Semaforo";

const ESTADO: Record<Angulo["estado"], string> = { ok: "OK", revisar: "Revisar", sin_dato: "Sin dato" };

interface Props {
  angulos: Angulo[];
  editable?: boolean;
  ocupado?: boolean;
  onConfirmar?: (vista: Vista, segmento: Segmento) => void;
}

export function TablaAngulos({ angulos, editable = false, ocupado = false, onConfirmar }: Props) {
  const [filtroVista, setFiltroVista] = useState<"todas" | Vista>("todas");
  const vistas = VISTAS.filter(v => angulos.some(a => a.vista === v));
  const filas = filtroVista === "todas" ? angulos : angulos.filter(a => a.vista === filtroVista);

  return (
    <div>
      {vistas.length > 1 && (
        <div className="pestanas no-imprimir">
          <button
            type="button"
            className={filtroVista === "todas" ? "activa" : ""}
            onClick={() => setFiltroVista("todas")}
          >
            Todas ({vistas.length} fotos)
          </button>
          {vistas.map(v => (
            <button
              key={v}
              type="button"
              className={filtroVista === v ? "activa" : ""}
              onClick={() => setFiltroVista(v)}
            >
              {v}
            </button>
          ))}
        </div>
      )}
      <div className="tabla-scroll">
        <table>
          <thead>
            <tr>
              <th>Segmento</th><th>Vista</th><th>Ángulo</th><th>Puntaje REBA</th>
              <th>Modificadores</th><th>Estado</th><th>Capturado en piso</th>
            </tr>
          </thead>
          <tbody>
            {filas.map(a => {
              const discrepa = a.puntaje_previo != null && a.puntaje_previo !== a.puntaje_reba;
              return (
                <tr key={`${a.vista}-${a.segmento}-${a.lado ?? ""}`}>
                  <td>{ETIQUETA_SEGMENTO[a.segmento]}{a.lado ? ` (${a.lado})` : ""}</td>
                  <td>{a.vista}</td>
                  <td>{a.angulo_grados === null ? "—" : `${a.angulo_grados.toFixed(1)}°`}</td>
                  <td><Semaforo color={semaforoSegmento(a.puntaje_reba)} texto="" valor={a.puntaje_reba} /></td>
                  <td>{a.modificadores.length ? a.modificadores.join(", ") : "—"}</td>
                  <td>
                    <div className="celda-estado">
                      <span className={`estado estado-${a.estado}`}>{ESTADO[a.estado]}</span>
                      {a.estado === "revisar" && editable && onConfirmar && a.angulo_grados !== null && (
                        <button
                          type="button"
                          className="boton-confirmar no-imprimir"
                          disabled={ocupado}
                          onClick={() => onConfirmar(a.vista, a.segmento)}
                          title="Confirmar que el ángulo es correcto y pasar a OK"
                        >
                          ✓ Confirmar
                        </button>
                      )}
                    </div>
                    {a.motivo_estado && <div className="motivo-estado">{a.motivo_estado}</div>}
                  </td>
                  <td className={discrepa ? "discrepancia" : ""}>
                    {a.puntaje_previo ?? "—"}{discrepa ? " ⚠ no coincide" : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}