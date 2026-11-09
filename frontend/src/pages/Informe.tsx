import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import {
  COLOR_SEMAFORO, ETIQUETA_IMPLEMENTACION, ETIQUETA_TAREA, ETIQUETA_TIPO_CAMBIO, formatearFecha, semaforoSegmento,
  valorCambio,
} from "../lib/niveles";
import { SkeletonEditor } from "../components/SkeletonEditor";
import { TablaAngulos } from "../components/TablaAngulos";
import { DesgloseNom036, DesgloseReba } from "../components/DesgloseReba";
import { GraficaResidual } from "../components/GraficaResidual";
import logoJabil from "../assets/jabil-logo.webp";

function minutosEntre(desde: string | null, hasta: string | null): string {
  if (!desde || !hasta) return "—";
  const min = (new Date(hasta).getTime() - new Date(desde).getTime()) / 60000;
  return `${min.toFixed(1)} min`;
}

export function Informe() {
  const { id = "" } = useParams();
  const caso = useQuery({ queryKey: ["caso", id], queryFn: () => api.obtenerCaso(id) });
  const bitacora = useQuery({ queryKey: ["bitacora", id], queryFn: () => api.bitacora(id) });

  if (caso.isLoading) return <p className="cargando">Cargando…</p>;
  if (caso.error || !caso.data) return <p className="aviso error">{(caso.error as Error)?.message ?? "Caso no encontrado"}</p>;
  const c = caso.data;

  // Invariante 1: nada sale al informe sin validación del especialista (también si se entra por URL).
  if (!c.validacion.completa) {
    return (
      <section>
        <p className="aviso error">
          El informe de {c.id_caso} no está disponible: el plan de acción aún no está validado por el especialista.
        </p>
        <Link className="boton primario" to={`/casos/${id}/plan`}>Ir a plan y validación</Link>
      </section>
    );
  }

  const aprobadas = c.recomendaciones.filter(r =>
    (r.estado === "aprobada" || r.estado === "editada_aprobada") && r.implementacion !== "denegada");
  const vigentes = c.hallazgos.filter(h => !h.descartado);
  const puntaje = new Map<string, number>();
  for (const a of c.angulos) puntaje.set(a.segmento, Math.max(puntaje.get(a.segmento) ?? 0, a.puntaje_reba));

  return (
    <article className="informe">
      <div className="no-imprimir acciones">
        <Link className="boton" to={`/casos/${id}/plan`}>← Plan</Link>
        <button className="primario" onClick={() => window.print()}>Imprimir / Guardar PDF</button>
      </div>

      <header className="informe-cabecera">
        <div>
          <h1>Informe de evaluación ergonómica</h1>
          <p>{c.id_caso} · {c.estacion} · {ETIQUETA_TAREA[c.tipo_tarea]}</p>
          <p className="sutil">Fecha del análisis: {formatearFecha(c.fecha)}</p>
        </div>
        <span className="logo-informe">
          <img src={logoJabil} alt="Jabil" className="logo-jabil" />
          <span className="producto">Ergo<b>AI</b></span>
        </span>
      </header>

      <h2>1. Evidencia fotográfica</h2>
      <div className="fotos-informe">
        {c.imagenes.map(img => (
          <figure key={img.vista}>
            <SkeletonEditor imagen={img} editable={false}
              colorSegmento={s => COLOR_SEMAFORO[semaforoSegmento(
                c.angulos.find(a => a.vista === img.vista && a.segmento === s)?.puntaje_reba ?? puntaje.get(s)
              )]}
              cajas={vigentes.filter(h => h.vista === img.vista)} />
            <figcaption>Vista {img.vista}</figcaption>
          </figure>
        ))}
      </div>

      <h2>2. Ángulos por segmento</h2>
      <TablaAngulos angulos={c.angulos} />

      <h2>3. Evaluación</h2>
      <div className="rejilla">
        {c.reba && <div><h3>REBA</h3><DesgloseReba reba={c.reba} /></div>}
        {c.nom036 && <div><h3>NOM-036-1-STPS-2018</h3><DesgloseNom036 nom={c.nom036} /></div>}
      </div>

      <h2>4. Hallazgos</h2>
      <ul className="hallazgos">
        {vigentes.map(h => (
          <li key={h.id} className={`sev-${h.severidad}`}>
            {h.mensaje}{h.referencia && <span className="referencia"> · {h.referencia}</span>}
          </li>
        ))}
      </ul>

      <h2>5. Plan de acción aprobado</h2>
      <div className="tabla-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Control</th>
              <th>Acción y Cita Normativa RAG</th>
              <th>Ajustes</th>
              <th>Responsable</th>
              <th>Compromiso</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {aprobadas.map((r, i) => (
              <tr key={r.id}>
                <td>{i + 1}</td>
                <td>
                  <strong>{r.nivel_control === "ingenieria" ? "Ingeniería" : "Administrativo"}</strong>
                  <br />
                  <span className="sutil">{ETIQUETA_TIPO_CAMBIO[r.tipo_cambio]}</span>
                </td>
                <td>
                  <div style={{ marginBottom: "6px" }}>
                    <strong>{r.titulo}.</strong> {r.texto}
                  </div>
                  {(r.layer_autocad || r.hoja_excel_jabil || r.tramite_moc) && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", margin: "6px 0" }}>
                      {r.layer_autocad && (
                        <span style={{ fontSize: "0.72rem", padding: "2px 6px", borderRadius: "3px", background: "#e0f2fe", color: "#0369a1", fontWeight: 600 }}>
                          📐 AutoCAD: Layer {r.layer_autocad}
                        </span>
                      )}
                      {r.hoja_excel_jabil && (
                        <span style={{ fontSize: "0.72rem", padding: "2px 6px", borderRadius: "3px", background: "#dcfce7", color: "#15803d", fontWeight: 600 }}>
                          📊 Excel: {r.hoja_excel_jabil}
                        </span>
                      )}
                      {r.tramite_moc && (
                        <span style={{ fontSize: "0.72rem", padding: "2px 6px", borderRadius: "3px", background: "#fef3c7", color: "#b45309", fontWeight: 600 }}>
                          🛡️ {r.tramite_moc}
                        </span>
                      )}
                    </div>
                  )}
                  <div
                    className="informe-justificacion-rag"
                    style={{
                      marginTop: "8px",
                      padding: "8px 10px",
                      background: "#f0f9ff",
                      borderLeft: "3.5px solid #0284c7",
                      borderRadius: "4px",
                      fontSize: "0.82rem",
                      lineHeight: "1.45",
                      color: "#0f172a",
                    }}
                  >
                    <div style={{ fontWeight: 700, color: "#0369a1", marginBottom: "3px", fontSize: "0.8rem" }}>
                      📑 Justificación RAG (16-PE30-6500-00023 / NOM-036) · Párrafo Completo Citado:
                    </div>
                    <div>
                      {r.justificacion_rag || `Referencia: ${r.referencia}`}
                    </div>
                  </div>
                </td>
                <td>{r.cambios.length ? r.cambios.map(cb => (
                  <div key={cb.parametro}>{cb.etiqueta}: {valorCambio(cb.actual, cb.unidad)} → <strong>{valorCambio(cb.objetivo, cb.unidad)}</strong></div>
                )) : "—"}</td>
                <td>{r.responsable ?? "—"}</td>
                <td>{r.fecha_compromiso ?? "—"}</td>
                <td>{r.implementacion ? ETIQUETA_IMPLEMENTACION[r.implementacion] : "—"}
                  {r.autorizado_por && <div className="sutil">Autorizó: {r.autorizado_por}</div>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {c.residual && (<><h2>6. Riesgo residual esperado</h2><GraficaResidual residual={c.residual} /></>)}

      {c.metricas.analisis_ms != null && (
        <>
          <h2>7. Tiempos del estudio</h2>
          <dl className="desglose">
            <div><dt>Análisis automático (visión + REBA + recomendaciones)</dt><dd>{(c.metricas.analisis_ms / 1000).toFixed(1)} s</dd></div>
            <div><dt>Caso creado → plan validado por el especialista</dt><dd>{minutosEntre(c.metricas.creado_en, c.metricas.validado_en)}</dd></div>
          </dl>
        </>
      )}

      <h2>{c.metricas.analisis_ms != null ? "8" : "7"}. Trazabilidad</h2>
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>#</th><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Motivo</th><th>Hash</th></tr></thead>
          <tbody>
            {(bitacora.data ?? []).map(e => (
              <tr key={e.secuencia}>
                <td>{e.secuencia}</td><td>{formatearFecha(e.timestamp)}</td><td>{e.usuario}</td>
                <td>{e.accion}</td><td>{e.motivo ?? "—"}</td><td className="mono" title={e.hash}>{e.hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="firmas">
        <div>Especialista en ergonomía</div>
        <div>Ingeniería industrial</div>
      </div>
    </article>
  );
}