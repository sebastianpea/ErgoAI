import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { NuevaRecomendacion, Recomendacion } from "../types/caso";
import { useSesion } from "../lib/sesion";
import { TarjetaRecomendacion, type DecisionTarjeta } from "../components/TarjetaRecomendacion";
import { FormNuevaRecomendacion } from "../components/FormNuevaRecomendacion";
import { GraficaResidual } from "../components/GraficaResidual";
import { Encabezado } from "../components/Encabezado";

type Accion =
  | { tipo: "decidir"; rec: string; d: DecisionTarjeta }
  | { tipo: "autorizar"; rec: string; accion: "autorizar" | "denegar"; motivo?: string }
  | { tipo: "implementar"; rec: string; nota?: string };

// Lo pendiente de validar ("propuesta") siempre arriba; dentro de cada grupo, Ingeniería primero (NOM-036).
const ORDEN_IMPL: Record<string, number> = { pendiente_autorizacion: 0, por_implementar: 1, ninguna: 2, implementada: 3, denegada: 4 };
const ordenar = (a: Recomendacion, b: Recomendacion) =>
  Number(a.estado !== "propuesta") - Number(b.estado !== "propuesta") ||
  (a.nivel_control === b.nivel_control ? 0 : a.nivel_control === "ingenieria" ? -1 : 1) ||
  ORDEN_IMPL[a.implementacion ?? "ninguna"] - ORDEN_IMPL[b.implementacion ?? "ninguna"];

export function Plan() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const sesion = useSesion();
  const [creando, setCreando] = useState(false);
  const [descargandoExcel, setDescargandoExcel] = useState(false);
  const [descargandoPdf, setDescargandoPdf] = useState(false);
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null);

  const { data: caso, isLoading, error } = useQuery({ queryKey: ["caso", id], queryFn: () => api.obtenerCaso(id) });

  const refrescar = () => {
    qc.invalidateQueries({ queryKey: ["caso", id] });
    qc.invalidateQueries({ queryKey: ["casos"] });
    qc.invalidateQueries({ queryKey: ["alertas"] });
    qc.invalidateQueries({ queryKey: ["bitacora"] });
    qc.invalidateQueries({ queryKey: ["impacto"] });
  };

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

  const accion = useMutation({
    mutationFn: (a: Accion) => {
      if (a.tipo === "decidir") {
        return api.decidir({ ...a.d, id_caso: id, id_recomendacion: a.rec, usuario: sesion.usuario, rol: sesion.rol });
      }
      if (a.tipo === "autorizar") return api.autorizar(id, a.rec, a.accion, a.motivo);
      return api.implementar(id, a.rec, a.nota);
    },
    onSuccess: refrescar,
  });

  const crear = useMutation({
    mutationFn: (n: Omit<NuevaRecomendacion, "usuario" | "rol">) =>
      api.crearRecomendacion(id, { ...n, usuario: sesion.usuario, rol: sesion.rol }),
    onSuccess: () => { setCreando(false); refrescar(); },
  });

  const generarIA = useMutation({
    mutationFn: () => api.generarPlanErgoAI(id),
    onSuccess: (actualizado) => {
      qc.setQueryData(["caso", id], actualizado);
      refrescar();
    },
  });

  if (isLoading) return <p className="cargando">Cargando…</p>;
  if (error || !caso) return <p className="aviso error">{(error as Error)?.message ?? "Caso no encontrado"}</p>;

  const recs = [...caso.recomendaciones].sort(ordenar);
  const v = caso.validacion;
  const ocupado = accion.isPending;

  // El informe formal solo se permite si TODO está aprobado por Ergonomía, autorizado por Ingeniería e implementado
  const todoListo = Boolean(
    v.aprobado_e_implementado ?? (
      v.pendientes === 0 &&
      v.por_autorizar === 0 &&
      v.por_implementar === 0 &&
      !v.falta_ingenieria
    )
  );

  return (
    <section>
      <Encabezado
        eyebrow="Recomendaciones y validación"
        titulo={<>Plan de acción <span className="ligero">· {caso.id_caso}</span></>}
        subtitulo="El agente propone, el especialista decide. Los cambios en planta requieren además autorización de Ingeniería e implementación en piso."
        acciones={<>
          <Link className="boton claro" to={`/casos/${id}`}>← Análisis</Link>
          {todoListo ? (
            <>
              <Link className="boton primario" to={`/casos/${id}/informe`}>Ver informe</Link>
              <button
                type="button"
                className="boton"
                onClick={handleDescargarExcel}
                disabled={descargandoExcel}
                title="Guardar expediente completo en formato Microsoft Excel (.xlsx)"
              >
                {descargandoExcel ? "Generando Excel…" : "Guardar como Excel"}
              </button>
              <button
                type="button"
                className="boton"
                onClick={handleDescargarPdf}
                disabled={descargandoPdf}
                title="Guardar informe oficial en formato Adobe PDF (.pdf)"
              >
                {descargandoPdf ? "Generando PDF…" : "Guardar como PDF"}
              </button>
            </>
          ) : (
            <button
              className="primario"
              disabled
              title="Para generar el informe o exportar, todas las recomendaciones deben estar aprobadas e implementadas en piso."
            >
              Generar informe
            </button>
          )}
        </>}
      />

      <div className="resumen-plan">
        <div><span className="cifra-valor">{v.pendientes}</span><span className="cifra-texto">Por validar (ergonomía)</span></div>
        <div><span className="cifra-valor">{v.por_autorizar}</span><span className="cifra-texto">Por autorizar (ingeniería)</span></div>
        <div><span className="cifra-valor">{v.por_implementar}</span><span className="cifra-texto">Por implementar</span></div>
        <div><span className="cifra-valor">{v.implementadas}</span><span className="cifra-texto">Implementadas</span></div>
      </div>

      {errorDescarga && (
        <div className="aviso error">
          {errorDescarga}
        </div>
      )}

      {todoListo && (
        <div className="tarjeta corte" style={{ borderLeft: "4px solid #2E9E5B", marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <p className="eyebrow" style={{ color: "#2E9E5B" }}>Plan de acción completado e implementado</p>
              <h3 style={{ margin: "0.2rem 0" }}>Todas las recomendaciones fueron aprobadas e implementadas en planta</h3>
              <p className="sutil" style={{ margin: 0 }}>
                El caso cumple con todos los requisitos legales de la NOM-036-1-STPS-2018 y el estándar global Jabil.
              </p>
            </div>
            <div className="acciones">
              <button
                type="button"
                className="boton primario"
                onClick={handleDescargarExcel}
                disabled={descargandoExcel}
                title="Guardar expediente completo en formato Microsoft Excel (.xlsx)"
              >
                {descargandoExcel ? "Generando Excel…" : "Guardar como Excel"}
              </button>
              <button
                type="button"
                className="boton primario"
                onClick={handleDescargarPdf}
                disabled={descargandoPdf}
                title="Guardar informe oficial en formato Adobe PDF (.pdf)"
              >
                {descargandoPdf ? "Generando PDF…" : "Guardar como PDF"}
              </button>
              <Link className="boton" to={`/casos/${id}/informe`}>
                Ver Informe Web
              </Link>
            </div>
          </div>
        </div>
      )}

      {accion.isError && <p className="aviso error">No se guardó la acción: {accion.error.message}</p>}
      {sesion.esIngenieria && (
        <p className="aviso ok">
          Estás como <strong>Ingeniería</strong>: puedes autorizar o denegar los cambios en planta que Ergonomía ya aprobó.
          {v.por_autorizar === 0 && " En este caso no hay ninguno pendiente."}
        </p>
      )}
      {v.pendientes > 0 && <p className="aviso">Faltan {v.pendientes} recomendación(es) por validar (Ergonomía).</p>}
      {v.por_autorizar > 0 && <p className="aviso">Faltan {v.por_autorizar} recomendación(es) por autorizar (Ingeniería).</p>}
      {v.por_implementar > 0 && <p className="aviso">Faltan {v.por_implementar} recomendación(es) por marcar como implementadas en piso.</p>}
      {v.falta_ingenieria && v.pendientes === 0 && (
        <p className="aviso error">
          Riesgo alto o muy alto: se requiere al menos un control de ingeniería aprobado y no denegado (NOM-036-1-STPS-2018).
        </p>
      )}

      {sesion.esErgonomia && (
        <div style={{
          background: "linear-gradient(135deg, #eff6ff 0%, #f0fdf4 100%)",
          border: "2px solid #3b82f6",
          borderRadius: "12px",
          padding: "16px 20px",
          marginBottom: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
          boxShadow: "0 4px 6px -1px rgba(59, 130, 246, 0.1)"
        }}>
          <div>
            <h3 style={{ margin: "0 0 4px 0", color: "#1e3a8a", display: "flex", alignItems: "center", gap: "8px" }}>
              Generador Inteligente ErgoAI (NOM-036 + Jabil)
            </h3>
            <p style={{ margin: 0, fontSize: "0.9rem", color: "#334155" }}>
              Consulta el corpus normativo en RAM y genera una recomendación estructurada de control con LLM local.
            </p>
          </div>
          <button
            className="primario"
            style={{
              padding: "10px 20px",
              fontWeight: 700,
              fontSize: "0.95rem",
              background: "#2563eb",
              color: "#ffffff",
              border: "none",
              borderRadius: "8px",
              cursor: generarIA.isPending ? "wait" : "pointer",
            }}
            disabled={generarIA.isPending}
            onClick={() => generarIA.mutate()}
          >
            {generarIA.isPending
              ? "Consultando normativa…"
              : v.pendientes === 0
                ? "Actualizar fundamentación con ErgoAI"
                : "Generar Plan de Mitigación con ErgoAI"}
          </button>
        </div>
      )}

      {generarIA.isPending && (
        <div className="aviso ok" style={{
          fontSize: "1rem",
          fontWeight: 600,
          padding: "14px 18px",
          marginBottom: "16px",
          display: "flex",
          alignItems: "center",
          gap: "12px"
        }}>
          <span>ErgoAI está consultando la NOM-036 y estándares Jabil...</span>
        </div>
      )}
      {generarIA.isError && (
        <p className="aviso error">
          Error al generar recomendación con ErgoAI: {generarIA.error.message}
        </p>
      )}

      <div className="rejilla">
        <div>
          {recs.map(r => (
            <TarjetaRecomendacion
              key={`${r.id}-${r.estado}-${r.implementacion}`}
              rec={r}
              rebaActual={caso.reba?.final ?? null}
              ocupado={ocupado}
              onDecidir={d => accion.mutate({ tipo: "decidir", rec: r.id, d })}
              onAutorizar={(a, motivo) => accion.mutate({ tipo: "autorizar", rec: r.id, accion: a, motivo })}
              onImplementar={nota => accion.mutate({ tipo: "implementar", rec: r.id, nota })}
            />
          ))}

          {sesion.esErgonomia && (creando ? (
            <FormNuevaRecomendacion caso={caso} ocupado={crear.isPending} error={crear.error?.message}
              onCrear={n => crear.mutate(n)} onCancelar={() => { setCreando(false); crear.reset(); }} />
          ) : (
            <button className="agregar-rec" onClick={() => setCreando(true)}>+ Agregar recomendación propia</button>
          ))}
        </div>
        {caso.residual && (
          <div className="tarjeta pegajosa">
            <h2>Riesgo residual proyectado</h2>
            <GraficaResidual residual={caso.residual} />
            <p className="sutil">Incluye las recomendaciones no rechazadas ni denegadas.</p>
          </div>
        )}
      </div>
    </section>
  );
}
