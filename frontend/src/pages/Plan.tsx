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

// Ingeniería primero (jerarquía de controles NOM-036); dentro, lo que requiere acción primero.
const ORDEN_IMPL: Record<string, number> = { pendiente_autorizacion: 0, por_implementar: 1, ninguna: 2, implementada: 3, denegada: 4 };
const ordenar = (a: Recomendacion, b: Recomendacion) =>
  (a.nivel_control === b.nivel_control ? 0 : a.nivel_control === "ingenieria" ? -1 : 1) ||
  Number(a.estado !== "propuesta") - Number(b.estado !== "propuesta") ||
  ORDEN_IMPL[a.implementacion ?? "ninguna"] - ORDEN_IMPL[b.implementacion ?? "ninguna"];

export function Plan() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const sesion = useSesion();
  const [creando, setCreando] = useState(false);
  const { data: caso, isLoading, error } = useQuery({ queryKey: ["caso", id], queryFn: () => api.obtenerCaso(id) });

  const refrescar = () => {
    qc.invalidateQueries({ queryKey: ["caso", id] });
    qc.invalidateQueries({ queryKey: ["casos"] });
    qc.invalidateQueries({ queryKey: ["alertas"] });
    qc.invalidateQueries({ queryKey: ["bitacora"] });
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

  if (isLoading) return <p className="cargando">Cargando…</p>;
  if (error || !caso) return <p className="aviso error">{(error as Error)?.message ?? "Caso no encontrado"}</p>;

  const recs = [...caso.recomendaciones].sort(ordenar);
  const v = caso.validacion;
  const ocupado = accion.isPending;

  return (
    <section>
      <Encabezado
        eyebrow="Recomendaciones y validación"
        titulo={<>Plan de acción <span className="ligero">· {caso.id_caso}</span></>}
        subtitulo="El agente propone, el especialista decide. Los cambios en planta requieren además autorización de Ingeniería."
        acciones={<>
          <Link className="boton claro" to={`/casos/${id}`}>← Análisis</Link>
          {v.completa ? (
            <Link className="boton primario" to={`/casos/${id}/informe`}>Generar informe</Link>
          ) : (
            <button className="primario" disabled title="Completa la validación del plan primero">Generar informe</button>
          )}
        </>}
      />

      <div className="resumen-plan">
        <div><span className="cifra-valor">{v.pendientes}</span><span className="cifra-texto">Por validar (ergonomía)</span></div>
        <div><span className="cifra-valor">{v.por_autorizar}</span><span className="cifra-texto">Por autorizar (ingeniería)</span></div>
        <div><span className="cifra-valor">{v.por_implementar}</span><span className="cifra-texto">Por implementar</span></div>
        <div><span className="cifra-valor">{v.implementadas}</span><span className="cifra-texto">Implementadas</span></div>
      </div>

      {accion.isError && <p className="aviso error">No se guardó la acción: {accion.error.message}</p>}
      {sesion.esIngenieria && (
        <p className="aviso ok">
          Estás como <strong>Ingeniería</strong>: puedes autorizar o denegar los cambios en planta que Ergonomía ya aprobó.
          {v.por_autorizar === 0 && " En este caso no hay ninguno pendiente."}
        </p>
      )}
      {v.pendientes > 0 && <p className="aviso">Faltan {v.pendientes} recomendación(es) por validar.</p>}
      {v.falta_ingenieria && v.pendientes === 0 && (
        <p className="aviso error">
          Riesgo alto o muy alto: se requiere al menos un control de ingeniería aprobado y no denegado (NOM-036-1-STPS-2018).
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
