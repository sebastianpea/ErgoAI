import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { COLOR_URGENCIA, ETIQUETA_EVENTO, formatearFecha } from "../lib/niveles";
import { Semaforo } from "../components/Semaforo";
import { Encabezado } from "../components/Encabezado";

const ORDEN_URGENCIA = { CRITICO: 3, ALTO: 2, MEDIO: 1, BAJO: 0 } as const;

export function Alertas() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["alertas"], queryFn: api.listarAlertas });
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
      <div className="lista-alertas">
        {alertas.map((a, i) => (
          <article key={a.id_alerta} className={`tarjeta alerta corte entrar ${a.estado}`}
            style={{ "--i": i } as CSSProperties}>
            <div className="caso-cabecera">
              <strong>{ETIQUETA_EVENTO[a.tipo_evento]}</strong>
              <Semaforo color={COLOR_URGENCIA[a.nivel_urgencia]} texto={a.nivel_urgencia} />
            </div>
            {a.tipo_evento === "EMERGENCIA_CAIDA" && <span className="fase2">Fase 2 · simulación</span>}
            <p>{a.detalles}</p>
            <p className="sutil">{a.estacion} · {formatearFecha(a.timestamp)} · {a.estado}</p>
            <div className="acciones">
              {a.id_caso && <Link className="boton" to={`/casos/${a.id_caso}`}>Ver caso</Link>}
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