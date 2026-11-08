import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ETIQUETA_TAREA, NIVEL_REBA, formatearFecha } from "../lib/niveles";
import { Semaforo } from "../components/Semaforo";
import { Encabezado } from "../components/Encabezado";
import { Contador } from "../components/Contador";
import { TarjetaImpacto } from "../components/TarjetaImpacto";

export function Bandeja() {
  const { data, isLoading, error } = useQuery({ queryKey: ["casos"], queryFn: api.listarCasos });
  const { data: alertas } = useQuery({ queryKey: ["alertas"], queryFn: api.listarAlertas });

  const encabezado = (
    <Encabezado
      eyebrow="Auditoría ergonómica"
      titulo="Bandeja de casos"
      subtitulo="Ordenados por nivel de riesgo. Los casos alto y muy alto se validan primero."
      acciones={<Link className="boton primario" to="/casos/nuevo">+ Nuevo caso desde fotos</Link>}
    />
  );

  if (isLoading) return <>{encabezado}<p className="cargando">Cargando casos…</p></>;
  if (error) return <>{encabezado}<p className="aviso error">{(error as Error).message}</p></>;

  // Mayor riesgo primero; dentro del mismo nivel, más decisiones pendientes primero
  const casos = [...(data ?? [])].sort((a, b) =>
    (b.nivel ? NIVEL_REBA[b.nivel].orden : -1) - (a.nivel ? NIVEL_REBA[a.nivel].orden : -1) ||
    b.decisiones_pendientes - a.decisiones_pendientes);

  const cifras = [
    { valor: casos.length, texto: "Casos en auditoría" },
    { valor: casos.filter(c => c.nivel === "alto" || c.nivel === "muy_alto").length, texto: "Riesgo alto o muy alto" },
    { valor: casos.reduce((s, c) => s + c.decisiones_pendientes, 0), texto: "Decisiones por validar" },
    { valor: alertas?.filter(a => a.estado === "nueva").length ?? 0, texto: "Alertas nuevas" },
  ];

  return (
    <section>
      {encabezado}

      <div className="cifras">
        {cifras.map((c, i) => (
          <div key={c.texto} className="cifra entrar" style={{ "--i": i } as CSSProperties}>
            <span className="cifra-valor"><Contador valor={c.valor} /></span>
            <span className="cifra-texto">{c.texto}</span>
          </div>
        ))}
      </div>

      <p className="eyebrow">Casos</p>
      <h2 className="titulo-seccion">Priorizados por riesgo</h2>
      <div className="lista-casos">
        {casos.map((c, i) => {
          const nivel = c.nivel ? NIVEL_REBA[c.nivel] : null;
          return (
            <Link key={c.id_caso} to={`/casos/${c.id_caso}`} className="tarjeta caso corte entrar"
              style={{ "--i": i + 2 } as CSSProperties}>
              <div className="caso-cabecera">
                <span className="eyebrow">{ETIQUETA_TAREA[c.tipo_tarea]}</span>
                {nivel && <Semaforo color={nivel.color} texto={nivel.etiqueta} valor={c.reba_final ?? undefined} />}
              </div>
              <h3>{c.id_caso} · {c.estacion}</h3>
              <div className="sutil">{formatearFecha(c.fecha)}</div>
              <div className={c.decisiones_pendientes ? "pendientes" : "sutil"}>
                {c.decisiones_pendientes
                  ? `${c.decisiones_pendientes} recomendación(es) por validar`
                  : "Sin decisiones pendientes"}
              </div>
              <span className="leer-mas">Abrir análisis <span aria-hidden>→</span></span>
            </Link>
          );
        })}
      </div>

      <TarjetaImpacto />
    </section>
  );
}
