import type { CSSProperties } from "react";
import { PaginationControls, usePagination } from "../components/PaginationControls";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { COLOR_URGENCIA, ETIQUETA_EVENTO, formatearFecha } from "../lib/niveles";
import { Semaforo } from "../components/Semaforo";
import { Encabezado } from "../components/Encabezado";

const ORDEN_URGENCIA = { CRITICO: 3, ALTO: 2, MEDIO: 1, BAJO: 0 } as const;
const RESUMEN_EVENTO = {
  RIESGO_ALTO_PENDIENTE: "Riesgo ergonómico alto pendiente de validación por el especialista.",
  DISCREPANCIA_EVALUACION: "La evaluación previa y la evidencia del caso requieren comparación.",
  ANGULO_POR_REVISAR: "Una medición de postura requiere revisión del especialista.",
  OBJETO_DESCONOCIDO: "Se detectó un objeto en la estación que requiere identificación.",
  AUTORIZACION_PENDIENTE: "Un cambio en planta espera autorización de ingeniería.",
  EMERGENCIA_CAIDA: "Simulación de caída para demostrar el flujo de emergencia.",
} as const;

export function Alertas() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["alertas"], queryFn: api.listarAlertas });
  const pagination = usePagination(data?.length ?? 0);
  const atender = useMutation({
    mutationFn: api.atenderAlerta,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["bitacora"] });
    },
  });

  if (isLoading) return <p className="cargando">Cargando alertas…</p>;
  if (error) return <p className="aviso error">{(error as Error).message}</p>;

  const alertas = [...(data ?? [])].sort((a, b) =>
    Number(a.estado === "atendida") - Number(b.estado === "atendida") ||
    ORDEN_URGENCIA[b.nivel_urgencia] - ORDEN_URGENCIA[a.nivel_urgencia]);

  return (
    <section>
      <Encabezado
        eyebrow="Supervisión · IE · EHS"
        titulo="Alertas"
        subtitulo="Dirigidas solo a ergonomía, IE y EHS. Nunca se notifica al operador."
      />
      {atender.isError && <p className="aviso error">No se pudo atender la alerta: {atender.error.message}</p>}
      {alertas.length === 0 && <p className="sutil">Sin alertas.</p>}
      <p role="status">{alertas.filter(a => a.estado !== "atendida").length} alertas pendientes en total.</p>
      <PaginationControls {...pagination} label="alertas" />
      <div className="lista-alertas">
        {alertas.map((a, i) => (
          <article key={a.id_alerta} className={`tarjeta alerta corte entrar ${a.estado} ${pagination.rowClass(i)}`}
            style={{ "--i": i } as CSSProperties}>
            <div className="caso-cabecera">
              <strong>{ETIQUETA_EVENTO[a.tipo_evento]}</strong>
              <Semaforo color={COLOR_URGENCIA[a.nivel_urgencia]} texto={a.nivel_urgencia} />
            </div>
            {a.tipo_evento === "EMERGENCIA_CAIDA" && <span className="fase2">Fase 2 · simulación</span>}
            <p>{RESUMEN_EVENTO[a.tipo_evento]}</p>
            <p className="sutil">{a.estacion} · {formatearFecha(a.timestamp)} · {a.estado}</p>
            <div className="acciones">
              {a.id_caso && <Link className="boton verde" to={`/casos/${encodeURIComponent(a.id_caso)}`}>Ver caso <span aria-hidden>›</span></Link>}
              {a.estado !== "atendida" && (
                <button disabled={atender.isPending} onClick={() => atender.mutate(a.id_alerta)}>Marcar atendida</button>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}