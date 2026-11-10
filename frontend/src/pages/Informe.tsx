import { useState } from "react";
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

export function Informe() {
  const { id = "" } = useParams();
  const caso = useQuery({ queryKey: ["caso", id], queryFn: () => api.obtenerCaso(id) });
  const bitacora = useQuery({ queryKey: ["bitacora", id], queryFn: () => api.bitacora(id) });

  const [descargandoExcel, setDescargandoExcel] = useState(false);
  const [descargandoPdf, setDescargandoPdf] = useState(false);
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null);

  const handleDescargarExcel = async () => {
    setDescargandoExcel(true);
    setErrorDescarga(null);
    try {
      await api.descargarExcel(id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorDescarga(msg);
    } finally {
      setDescargandoExcel(false);
    }
  };

  const handleDescargarPdf = async () => {
    setDescargandoPdf(true);
    setErrorDescarga(null);
    try {
      await api.descargarPdf(id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorDescarga(msg);
    } finally {
      setDescargandoPdf(false);
    }
  };

  if (caso.isLoading) return <p className="cargando">Cargando…</p>;
  if (caso.error || !caso.data) return <p className="aviso error">{(caso.error as Error)?.message ?? "Caso no encontrado"}</p>;
  const c = caso.data;

  // Invariante 1: nada sale al informe sin validación total e implementación (también si se entra por URL).
  const v = c.validacion;
  const todoListo = Boolean(
    v.aprobado_e_implementado ?? (
      v.pendientes === 0 &&
      v.por_autorizar === 0 &&
      v.por_implementar === 0 &&
      !v.falta_ingenieria
    )
  );

  if (!todoListo) {
    return (
      <section>
        <div className="tarjeta corte">
          <h2>Informe no disponible</h2>
          <p className="aviso error">
            El informe oficial de <strong>{c.id_caso}</strong> no puede generarse hasta que todas las recomendaciones estén <strong>aprobadas por Ergonomía, autorizadas por Ingeniería e implementadas en piso</strong>.
          </p>
          <div className="resumen-plan" style={{ margin: "1.25rem 0" }}>
            <div><span className="cifra-valor">{v.pendientes}</span><span className="cifra-texto">Por validar (ergonomía)</span></div>
            <div><span className="cifra-valor">{v.por_autorizar}</span><span className="cifra-texto">Por autorizar (ingeniería)</span></div>
            <div><span className="cifra-valor">{v.por_implementar}</span><span className="cifra-texto">Por implementar</span></div>
            <div><span className="cifra-valor">{v.implementadas}</span><span className="cifra-texto">Implementadas</span></div>
          </div>
          <Link className="boton primario" to={`/casos/${id}/plan`}>← Ir al Plan para completar aprobaciones e implementación</Link>
        </div>
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
      {/* Barra de Acciones Superior */}
      <div className="no-imprimir acciones" style={{ marginBottom: "1.25rem", display: "flex", flexWrap: "wrap", gap: "0.6rem" }}>
        <Link className="boton" to={`/casos/${id}/plan`}>← Volver al Plan</Link>
        
        <button
          type="button"
          className="boton primario"
          onClick={handleDescargarExcel}
          disabled={descargandoExcel}
          title="Guardar expediente completo en formato Microsoft Excel (.xlsx)"
        >
          {descargandoExcel ? "⏳ Generando Excel…" : "📊 Guardar como Excel"}
        </button>

        <button
          type="button"
          className="boton primario"
          onClick={handleDescargarPdf}
          disabled={descargandoPdf}
          title="Guardar informe oficial en formato Adobe PDF (.pdf)"
        >
          {descargandoPdf ? "⏳ Generando PDF…" : "📥 Guardar como PDF"}
        </button>

        <button
          type="button"
          className="boton"
          onClick={() => window.print()}
          title="Abrir cuadro de diálogo de impresión"
        >
          🖨️ Imprimir
        </button>
      </div>

      {errorDescarga && (
        <div className="aviso error no-imprimir" style={{ marginBottom: "1rem" }}>
          {errorDescarga}
        </div>
      )}

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

      <h2>2. Ángulos medidos</h2>
      <TablaAngulos angulos={c.angulos} editable={false} />

      <h2>3. Evaluación REBA</h2>
      {c.reba ? <DesgloseReba reba={c.reba} /> : <p className="sutil">Sin cálculo REBA disponible.</p>}

      <h2>4. Evaluación NOM-036-1-STPS-2018</h2>
      {c.nom036 ? <DesgloseNom036 nom={c.nom036} /> : <p className="sutil">Tarea sin evaluación NOM-036.</p>}

      <h2>5. Plan de mitigación aprobado e implementado</h2>
      <div className="tabla-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Nivel</th><th>Tipo</th><th>Recomendación</th><th>Ajuste de parámetros</th>
              <th>Responsable</th><th>Compromiso</th><th>Implementación</th>
            </tr>
          </thead>
          <tbody>
            {aprobadas.map(r => (
              <tr key={r.id}>
                <td className="mono">{r.id}</td>
                <td><span className="etiqueta-control">{r.nivel_control}</span></td>
                <td>{ETIQUETA_TIPO_CAMBIO[r.tipo_cambio]}</td>
                <td>
                  <strong>{r.titulo}</strong>
                  <div className="sutil">{r.texto}</div>
                  <div className="rec-rag-justificacion-destacada">
                    <div className="etiqueta-justificacion">
                      <span>Fundamento Normativo (NOM-036 / Jabil)</span>
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

      <h2>7. Trazabilidad</h2>
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

      {/* Barra de Acciones Inferior al cierre del informe */}
      <div className="no-imprimir acciones" style={{ marginTop: "2rem", paddingTop: "1rem", borderTop: "1px solid var(--borde)", display: "flex", justifyContent: "flex-end", gap: "0.6rem" }}>
        <button
          type="button"
          className="boton primario"
          onClick={handleDescargarExcel}
          disabled={descargandoExcel}
          title="Guardar expediente completo en formato Microsoft Excel (.xlsx)"
        >
          {descargandoExcel ? "⏳ Generando Excel…" : "📊 Guardar como Excel"}
        </button>

        <button
          type="button"
          className="boton primario"
          onClick={handleDescargarPdf}
          disabled={descargandoPdf}
          title="Guardar informe oficial en formato Adobe PDF (.pdf)"
        >
          {descargandoPdf ? "⏳ Generando PDF…" : "📥 Guardar como PDF"}
        </button>
      </div>
    </article>
  );
}
