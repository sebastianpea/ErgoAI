import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { COLOR_URGENCIA, ETIQUETA_EVENTO, formatearFecha } from "../lib/niveles";
import { Semaforo } from "./Semaforo";

export function AlertasCaso({ idCaso }: { idCaso: string }) {
  // Layout owns fetching and refreshes; this observer only reads the shared cache.
  const { data, isPending, error } = useQuery({
    queryKey: ["alertas"], queryFn: api.listarAlertas, enabled: false,
  });
  if (isPending) return <p className="cargando">Cargando alertas del caso…</p>;
  if (error) return <p className="aviso error">No se pudieron cargar las alertas del caso: {error.message}</p>;
  const alertas = (data ?? []).filter(a => a.id_caso === idCaso);
  if (alertas.length === 0) return null;

  return (
    <section className="tarjeta" aria-label="Detalle de alertas del caso">
      <h2>Detalle de alertas del caso</h2>
      {alertas.map(a => (
        <article key={a.id_alerta}>
          <div className="caso-cabecera">
            <h3>{ETIQUETA_EVENTO[a.tipo_evento]}</h3>
            <Semaforo color={COLOR_URGENCIA[a.nivel_urgencia]} texto={a.nivel_urgencia} />
          </div>
          {a.tipo_evento === "EMERGENCIA_CAIDA" && <span className="fase2">Fase 2 · simulación</span>}
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{a.detalles}</p>
          <p className="sutil">{a.estacion} · {formatearFecha(a.timestamp)} · {a.estado}</p>
        </article>
      ))}
    </section>
  );
}
