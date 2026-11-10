import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { Encabezado } from "../components/Encabezado";
import { GraficaDashboard } from "../components/GraficaDashboard";
import { COLOR_SEMAFORO, ETIQUETA_TAREA, NIVEL_REBA } from "../lib/niveles";
import type { NivelReba, TipoTarea } from "../types/caso";

export function Dashboard() {
  // El prefijo conserva las invalidaciones de creación, revisión y autorización existentes.
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["casos", "dashboard"], queryFn: api.metricasDashboard,
  });
  const encabezado = (
    <Encabezado eyebrow="Auditoría ergonómica" titulo="Dashboard"
      subtitulo="Resumen global de todos los casos. Las decisiones las toma el especialista."
      acciones={<Link className="boton primario" to="/casos">Ver casos y validar</Link>} />
  );
  if (isLoading) return <section>{encabezado}<p className="cargando" role="status">Cargando resumen global…</p></section>;
  if (error) return <section>{encabezado}<div className="aviso error" role="alert">
    <p>No se pudo cargar el resumen: {(error as Error).message}</p>
    <button onClick={() => refetch()}>Reintentar</button>
  </div></section>;
  if (!data) return null;

  const cifras = [
    { valor: data.total_casos, texto: "Casos en auditoría" },
    { valor: (data.niveles.alto ?? 0) + (data.niveles.muy_alto ?? 0), texto: "Riesgo alto o muy alto" },
    { valor: data.decisiones_pendientes, texto: "Decisiones por validar" },
    { valor: data.por_autorizar, texto: "Cambios en planta por autorizar" },
  ];
  const riesgos = [
    { etiqueta: "Sin evaluar", valor: data.niveles.sin_evaluar ?? 0, color: COLOR_SEMAFORO.gris },
    ...(Object.keys(NIVEL_REBA) as NivelReba[]).map(nivel => ({
      etiqueta: NIVEL_REBA[nivel].etiqueta, valor: data.niveles[nivel] ?? 0,
      color: COLOR_SEMAFORO[NIVEL_REBA[nivel].color],
    })),
  ];
  const tareas = Object.entries(data.tipos_tarea).map(([tipo, valor]) => ({
    etiqueta: ETIQUETA_TAREA[tipo as TipoTarea] ?? tipo, valor,
  }));
  return (
    <section className="dashboard">
      {encabezado}
      <div className="cifras">
        {cifras.map(c => <div key={c.texto} className="cifra">
          <span className="cifra-valor">{c.valor}</span><span className="cifra-texto">{c.texto}</span>
        </div>)}
      </div>
      {data.total_casos === 0 && <div className="tarjeta" role="status">
        <p>No hay casos en auditoría.</p>
        <Link className="boton" to="/casos/nuevo">Crear el primer caso desde fotos</Link>
      </div>}
      <div className="dashboard-graficas">
        <GraficaDashboard titulo="Distribución de riesgo REBA · todos los casos" datos={riesgos} />
        <GraficaDashboard titulo="Tipos de tarea · todos los casos" datos={tareas} />
      </div>
    </section>
  );
}
