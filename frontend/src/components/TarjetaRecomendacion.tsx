import { useState } from "react";
import type { CambioPropuesto, Decision, Recomendacion, ValorCambio } from "../types/caso";
import { ETIQUETA_IMPLEMENTACION, ETIQUETA_TIPO_CAMBIO, nivelDeReba, valorCambio } from "../lib/niveles";
import { useSesion } from "../lib/sesion";
import { CampoValor } from "./CampoValor";
import { Semaforo } from "./Semaforo";

const ESTADO: Record<Recomendacion["estado"], string> = {
  propuesta: "Pendiente de validación",
  aprobada: "Aprobada",
  editada_aprobada: "Editada y aprobada",
  rechazada: "Rechazada",
};

export type DecisionTarjeta = Omit<Decision, "id_caso" | "id_recomendacion" | "usuario" | "rol">;

interface Props {
  rec: Recomendacion;
  rebaActual: number | null;
  ocupado: boolean;
  onDecidir: (d: DecisionTarjeta) => void;
  onAutorizar: (accion: "autorizar" | "denegar", motivo?: string) => void;
  onImplementar: (nota?: string) => void;
}

function diferencia(c: CambioPropuesto, objetivo: ValorCambio | null): string {
  if (typeof c.actual !== "number" || typeof objetivo !== "number") return "";
  const d = objetivo - c.actual;
  if (Math.abs(d) < 0.05) return "sin cambio";
  return `${d > 0 ? "+" : "−"}${valorCambio(Math.abs(d), c.unidad)}`;
}

export function TarjetaRecomendacion({ rec, rebaActual, ocupado, onDecidir, onAutorizar, onImplementar }: Props) {
  const { esErgonomia, esIngenieria } = useSesion();
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(rec.texto);
  const [objetivos, setObjetivos] = useState<Record<string, ValorCambio>>(
    () => Object.fromEntries(rec.cambios.map(c => [c.parametro, c.objetivo as ValorCambio])));
  const [motivo, setMotivo] = useState("");
  const [nota, setNota] = useState("");
  const [responsable, setResponsable] = useState(rec.responsable ?? "");
  const [fecha, setFecha] = useState(rec.fecha_compromiso ?? "");

  const pendiente = rec.estado === "propuesta";
  const hayMotivo = motivo.trim().length > 0;
  const textoValido = texto.trim().length >= 5;
  const cambiosEditados = Object.fromEntries(
    rec.cambios.filter(c => objetivos[c.parametro] !== c.objetivo).map(c => [c.parametro, objetivos[c.parametro]]));
  const huboEdicion = texto.trim() !== rec.texto || Object.keys(cambiosEditados).length > 0;

  const extra = { responsable: responsable.trim() || undefined, fecha_compromiso: fecha || undefined };

  const cancelarEdicion = () => {
    setEditando(false);
    setTexto(rec.texto);
    setObjetivos(Object.fromEntries(rec.cambios.map(c => [c.parametro, c.objetivo as ValorCambio])));
  };

  const pasos = [
    { titulo: "Ergonomía", hecho: !pendiente && rec.estado !== "rechazada", detalle: rec.aprobado_por },
    ...(rec.requiere_autorizacion ? [{
      titulo: "Autorización de ingeniería",
      hecho: rec.implementacion === "por_implementar" || rec.implementacion === "implementada",
      detalle: rec.autorizado_por,
    }] : []),
    { titulo: "Implementación", hecho: rec.implementacion === "implementada", detalle: rec.implementado_por },
  ];
  const actual = pasos.findIndex(p => !p.hecho);
  const detenido = rec.estado === "rechazada" || rec.implementacion === "denegada";

  return (
    <article className={`tarjeta rec corte rec-${rec.nivel_control} rec-estado-${rec.estado} impl-${rec.implementacion ?? "ninguna"}`}>
      <header>
        <div className="rec-etiquetas">
          <span className={`etiqueta-control ${rec.nivel_control}`}>
            {rec.nivel_control === "ingenieria" ? "PRIORIDAD 1: INGENIERÍA" : "CONTROL ADMINISTRATIVO"}
          </span>
          <span className={`etiqueta-tipo tipo-${rec.tipo_cambio}`}>{ETIQUETA_TIPO_CAMBIO[rec.tipo_cambio]}</span>
          {rec.origen === "especialista" && <span className="etiqueta-tipo">Del especialista</span>}
        </div>
        <span className="estado-rec">
          {rec.implementacion ? ETIQUETA_IMPLEMENTACION[rec.implementacion] : ESTADO[rec.estado]}
        </span>
      </header>
      <h3><span className="rec-id">{rec.id}</span> {rec.titulo}</h3>

      {editando ? (
        <label className="campo-bloque">Texto de la recomendación
          <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={3} />
        </label>
      ) : (
        <p>{rec.texto}</p>
      )}

      {rec.cambios.length > 0 && (
        <div className="tabla-scroll">
          <table className="tabla-cambios">
            <thead><tr><th>Ajuste propuesto</th><th>Actual</th><th>Objetivo</th><th>Cambio</th></tr></thead>
            <tbody>
              {rec.cambios.map(c => (
                <tr key={c.parametro}>
                  <td>{c.etiqueta}</td>
                  <td>{valorCambio(c.actual, c.unidad)}</td>
                  <td>
                    {editando ? (
                      <CampoValor tipo={c.tipo} valor={objetivos[c.parametro]} etiqueta={`Objetivo: ${c.etiqueta}`}
                        unidad={c.unidad} minimo={c.minimo} maximo={c.maximo} opciones={c.opciones}
                        onChange={v => setObjetivos(o => ({ ...o, [c.parametro]: v }))} />
                    ) : <strong>{valorCambio(c.objetivo, c.unidad)}</strong>}
                  </td>
                  <td className="delta">{diferencia(c, editando ? objetivos[c.parametro] : c.objetivo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {rec.reba_proyectado != null && rebaActual != null && (
        <p className="proyeccion">
          REBA con solo esta acción:
          <Semaforo color={nivelDeReba(rebaActual).color} texto="" valor={rebaActual} />
          <span aria-hidden>→</span>
          <Semaforo color={nivelDeReba(rec.reba_proyectado).color} texto={nivelDeReba(rec.reba_proyectado).etiqueta}
            valor={rec.reba_proyectado} />
          {editando && Object.keys(cambiosEditados).length > 0 && <span className="sutil">(se recalcula al guardar)</span>}
        </p>
      )}
      <p className="referencia">Referencia: {rec.referencia}</p>

      {(rec.layer_autocad || rec.hoja_excel_jabil || rec.tramite_moc) && (
        <div className="rec-rag-badges" style={{ display: "flex", flexWrap: "wrap", gap: "6px", margin: "8px 0" }}>
          {rec.layer_autocad && (
            <span style={{ fontSize: "0.75rem", padding: "2px 8px", borderRadius: "4px", background: "#e0f2fe", color: "#0369a1", fontWeight: 600, border: "1px solid #bae6fd" }}>
              AutoCAD: Layer {rec.layer_autocad}
            </span>
          )}
          {rec.hoja_excel_jabil && (
            <span style={{ fontSize: "0.75rem", padding: "2px 8px", borderRadius: "4px", background: "#dcfce7", color: "#15803d", fontWeight: 600, border: "1px solid #bbf7d0" }}>
              Excel Jabil: {rec.hoja_excel_jabil}
            </span>
          )}
          {rec.tramite_moc && (
            <span style={{ fontSize: "0.75rem", padding: "2px 8px", borderRadius: "4px", background: "#fef3c7", color: "#b45309", fontWeight: 600, border: "1px solid #fde68a" }}>
              {rec.tramite_moc}
            </span>
          )}
        </div>
      )}

      {rec.justificacion_rag && (
        <div
          className="rec-rag-justificacion-destacada"
          style={{
            margin: "12px 0 16px 0",
            padding: "12px 14px",
            background: "linear-gradient(135deg, #f0f9ff 0%, #f8fafc 100%)",
            border: "1.5px solid #38bdf8",
            borderLeft: "5px solid #0284c7",
            borderRadius: "8px",
            boxShadow: "0 2px 4px rgba(2, 132, 199, 0.06)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              fontWeight: 700,
              fontSize: "0.88rem",
              color: "#0369a1",
              marginBottom: "8px",
              letterSpacing: "0.2px",
            }}
          >
            <span>Justificación RAG (16-PE30-6500-00023 / NOM-036) · Párrafo Oficial Citado:</span>
          </div>
          <div
            style={{
              margin: 0,
              fontSize: "0.88rem",
              lineHeight: "1.55",
              color: "#0f172a",
              background: "#ffffff",
              padding: "10px 14px",
              borderRadius: "6px",
              border: "1px solid #e2e8f0",
              fontStyle: "normal",
            }}
          >
            {rec.justificacion_rag}
          </div>
        </div>
      )}

      <ol className={`flujo${detenido ? " detenido" : ""}`} aria-label="Avance de la recomendación">
        {pasos.map((p, i) => (
          <li key={p.titulo} className={p.hecho ? "hecho" : i === actual && !detenido ? "actual" : ""}>
            <span className="flujo-titulo">{p.titulo}</span>
            {p.detalle && <span className="flujo-detalle">{p.detalle}</span>}
          </li>
        ))}
      </ol>

      {rec.nota_autorizacion && (
        <p className={`nota ${rec.implementacion === "denegada" ? "nota-error" : ""}`}>
          <strong>{rec.implementacion === "denegada" ? "Denegada" : "Autorizada"} por {rec.autorizado_por}:</strong> {rec.nota_autorizacion}
        </p>
      )}
      {rec.nota_implementacion && <p className="nota"><strong>Implementación:</strong> {rec.nota_implementacion}</p>}
      {!pendiente && rec.estado !== "rechazada" && (rec.responsable || rec.fecha_compromiso) && (
        <p className="sutil">Responsable: {rec.responsable ?? "—"} · Fecha compromiso: {rec.fecha_compromiso ?? "—"}</p>
      )}

      {/* ---- Acciones según estado y rol ---- */}
      {pendiente && esErgonomia && (
        <>
          <div className="campos">
            <label>Responsable<input value={responsable} onChange={e => setResponsable(e.target.value)} placeholder="Ej. IE Línea 2" /></label>
            <label>Fecha compromiso<input type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></label>
            <label className="ancho">
              Justificación (obligatoria para editar o rechazar)
              <input value={motivo} onChange={e => setMotivo(e.target.value)} />
            </label>
          </div>
          <div className="acciones">
            {editando ? (
              <>
                <button className="primario" disabled={ocupado || !textoValido || !hayMotivo || !huboEdicion}
                  title={!hayMotivo ? "Escribe la justificación de la edición" : !huboEdicion ? "No hay cambios" : undefined}
                  onClick={() => onDecidir({
                    accion: "editar", motivo: motivo.trim(), ...extra,
                    texto_editado: texto.trim() !== rec.texto ? texto.trim() : undefined,
                    cambios: Object.keys(cambiosEditados).length ? cambiosEditados : undefined,
                  })}>
                  Guardar y aprobar
                </button>
                <button onClick={cancelarEdicion}>Cancelar</button>
              </>
            ) : (
              <>
                <button className="primario" disabled={ocupado}
                  onClick={() => onDecidir({ accion: "aprobar", motivo: motivo.trim() || undefined, ...extra })}>Aprobar</button>
                <button disabled={ocupado} onClick={() => setEditando(true)}>Editar</button>
                <button className="peligro" disabled={ocupado || !hayMotivo}
                  title={!hayMotivo ? "Escribe la justificación del rechazo" : undefined}
                  onClick={() => onDecidir({ accion: "rechazar", motivo: motivo.trim() })}>Rechazar</button>
              </>
            )}
          </div>
          {rec.requiere_autorizacion && (
            <p className="sutil">Es un cambio en planta: al aprobarlo pasará a Ingeniería para su autorización.</p>
          )}
        </>
      )}
      {pendiente && esIngenieria && <p className="sutil">Pendiente de validación por Ergonomía.</p>}

      {rec.implementacion === "pendiente_autorizacion" && (esIngenieria ? (
        <div className="bloque-accion">
          <label className="campo-bloque">Comentario de ingeniería (obligatorio para denegar; p. ej. folio MOC)
            <input value={motivo} onChange={e => setMotivo(e.target.value)} />
          </label>
          <div className="acciones">
            <button className="primario" disabled={ocupado}
              onClick={() => onAutorizar("autorizar", motivo.trim() || undefined)}>Autorizar cambio</button>
            <button className="peligro" disabled={ocupado || !hayMotivo}
              title={!hayMotivo ? "Escribe el motivo de la denegación" : undefined}
              onClick={() => onAutorizar("denegar", motivo.trim())}>Denegar</button>
          </div>
        </div>
      ) : (
        <p className="aviso">Esperando autorización de Ingeniería (IE/Facilities). Cambia el rol en la barra superior para autorizar.</p>
      ))}

      {rec.implementacion === "por_implementar" && (esErgonomia ? (
        <div className="bloque-accion">
          <label className="campo-bloque">Nota de implementación (opcional)
            <input value={nota} onChange={e => setNota(e.target.value)} placeholder="Ej. Lifter instalado el 20/11" />
          </label>
          <div className="acciones">
            <button className="primario" disabled={ocupado} onClick={() => onImplementar(nota.trim() || undefined)}>
              Marcar como implementada
            </button>
          </div>
        </div>
      ) : <p className="sutil">Autorizada. Ergonomía confirmará la implementación.</p>)}
    </article>
  );
}
