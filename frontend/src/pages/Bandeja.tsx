import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { ETIQUETA_TAREA, NIVEL_REBA, formatearFecha } from "../lib/niveles";
import { Semaforo } from "../components/Semaforo";
import { Encabezado } from "../components/Encabezado";

export function Bandeja() {
  const [params, setParams] = useSearchParams();
  const requestedPage = Number(params.get("page") ?? 1);
  const requestedSize = Number(params.get("page_size") ?? 10);
  const page = Number.isSafeInteger(requestedPage) && requestedPage >= 1 ? requestedPage : 1;
  const pageSize = [10, 25, 50, 100].includes(requestedSize) ? requestedSize : 10;
  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["casos", "pagina", page, pageSize],
    queryFn: () => api.listarCasosPaginados(page, pageSize),
  });
  const cambiarPagina = (next: number, size = pageSize) => {
    const nextParams = new URLSearchParams(params);
    nextParams.set("page", String(next));
    nextParams.set("page_size", String(size));
    setParams(nextParams);
  };
  const totalPages = Math.max(1, data?.total_pages ?? 1);
  // Sin placeholder de otra página: solo corregimos usando la respuesta de esta consulta.
  useEffect(() => {
    if (data && !isFetching && !error && page > totalPages) {
      const nextParams = new URLSearchParams(params);
      nextParams.set("page", String(totalPages));
      setParams(nextParams, { replace: true });
    }
  }, [data, isFetching, error, page, totalPages, params, setParams]);

  const encabezado = (
    <Encabezado eyebrow="Auditoría ergonómica" titulo="Bandeja de casos"
      subtitulo="Ordenados por identificador de caso ascendente. El resumen global está en el dashboard."
      acciones={<Link className="boton primario" to="/casos/nuevo">+ Nuevo caso desde fotos</Link>} />
  );
  if (isLoading) return <section>{encabezado}<p className="cargando" role="status">Cargando casos…</p></section>;
  if (error) return <section>{encabezado}<div className="aviso error" role="alert">
    <p>No se pudieron cargar los casos: {(error as Error).message}</p>
    <button onClick={() => refetch()}>Reintentar</button>
  </div></section>;

  return (
    <section className="bandeja">
      {encabezado}
      <nav className="paginacion-casos" aria-label="Paginación de casos">
        <label>Casos por página <select aria-label="Casos por página" value={pageSize}
          onChange={e => cambiarPagina(1, Number(e.target.value))}>
          {[10, 25, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}
        </select></label>
        <span role="status">Página {Math.min(page, totalPages)} de {totalPages} · {data?.total ?? 0} casos en total</span>
        <div className="acciones">
          <button disabled={page <= 1 || isFetching} onClick={() => cambiarPagina(page - 1)}>Anterior</button>
          <button disabled={page >= totalPages || isFetching} onClick={() => cambiarPagina(page + 1)}>Siguiente</button>
          <button disabled={isFetching} onClick={() => refetch()}>Actualizar</button>
        </div>
      </nav>
      {isFetching && <p role="status">Actualizando página…</p>}
      {data?.total === 0 && <div className="tarjeta" role="status">
        <p>No hay casos en auditoría. Crea un caso desde fotos para comenzar.</p>
      </div>}
      {!!data?.total && !data.items.length && <p role="status">No hay casos en esta página; ajustando la paginación…</p>}
      <div className="lista-casos">
        {data?.items.map(c => {
          const nivel = c.nivel ? NIVEL_REBA[c.nivel] : null;
          return (
            <Link key={c.id_caso} to={`/casos/${encodeURIComponent(c.id_caso)}`} className="tarjeta caso corte">
              <div className="caso-cabecera">
                <span className="eyebrow">{ETIQUETA_TAREA[c.tipo_tarea] ?? c.tipo_tarea}</span>
                {nivel ? <Semaforo color={nivel.color} texto={nivel.etiqueta} valor={c.reba_final ?? undefined} /> : <span className="sutil">Sin evaluar</span>}
              </div>
              <h3>{c.id_caso} · {c.estacion}</h3>
              <div className="sutil">{formatearFecha(c.fecha)}</div>
              <div className={c.decisiones_pendientes ? "pendientes" : "sutil"}>
                {c.decisiones_pendientes ? `${c.decisiones_pendientes} recomendación(es) por validar` : "Sin decisiones pendientes"}
              </div>
              <span className="leer-mas">Abrir análisis <span aria-hidden>→</span></span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
