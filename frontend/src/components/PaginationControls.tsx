import { useState } from "react";

const PAGE_SIZE = 5;

/** Solo presentación: las filas permanecen montadas para conservar edición e impresión. */
export function usePagination(total: number) {
  const [requestedPage, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = Math.min(requestedPage, pages);
  const changePage = (next: number) => setPage(Math.max(1, Math.min(next, pages)));
  return {
    page, pages, total, changePage,
    rowClass: (index: number) => Math.floor(index / PAGE_SIZE) + 1 === page ? "" : "pagination-oculto",
  };
}

type Props = ReturnType<typeof usePagination> & { label: string };

export function PaginationControls({ page, pages, total, changePage, label }: Props) {
  return <>
    {/* El informe y la impresión siempre incluyen todas las filas, incluso con filtros activos. */}
    <style>{`
      .pagination-oculto.pagination-oculto { display: none; }
      .informe .pagination-oculto.pagination-oculto { display: revert; }
      .informe .barra-fila.pagination-oculto { display: grid; }
      .informe .pagination-controls { display: none; }
      @media print {
        .pagination-oculto.pagination-oculto { display: revert; }
        .barra-fila.pagination-oculto { display: grid; }
      }
    `}</style>
    {pages > 1 && <nav className="paginacion-casos pagination-controls no-imprimir" aria-label={`Paginación de ${label}`}>
      <span role="status">Página {page} de {pages} · {total} en total</span>
      <div className="acciones">
        <button type="button" disabled={page <= 1} onClick={() => changePage(page - 1)}>Anterior</button>
        <button type="button" disabled={page >= pages} onClick={() => changePage(page + 1)}>Siguiente</button>
      </div>
    </nav>}
  </>;
}
