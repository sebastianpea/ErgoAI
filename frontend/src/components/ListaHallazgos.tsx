import { useState } from "react";
import type { Hallazgo } from "../types/caso";
import { PaginationControls, usePagination } from "./PaginationControls";

interface Props {
  hallazgos: Hallazgo[];
  editable: boolean;
  ocupado: boolean;
  onRevisar: (id: string, accion: "descartar" | "restaurar", motivo: string) => void;
}

/** Hallazgos del análisis; el especialista puede descartar falsos positivos con justificación. */
export function ListaHallazgos({ hallazgos, editable, ocupado, onRevisar }: Props) {
  const [abierto, setAbierto] = useState<string | null>(null);
  const [motivo, setMotivo] = useState("");
  const pagination = usePagination(hallazgos.length);

  if (hallazgos.length === 0) return <p className="sutil">Sin hallazgos.</p>;

  const cerrar = () => { setAbierto(null); setMotivo(""); };

  return (
    <>
    <PaginationControls {...pagination} label="hallazgos" />
    <ul className="hallazgos">
      {hallazgos.map((h, i) => {
        const accion = h.descartado ? "restaurar" : "descartar";
        return (
          <li key={h.id} className={`sev-${h.severidad}${h.descartado ? " descartado" : ""} ${pagination.rowClass(i)}`}>
            <span className="origen">{h.origen.replace(/_/g, " ")}{h.descartado && " · descartado"}</span>
            <span className="hallazgo-mensaje">{h.mensaje}</span>
            {h.referencia && <span className="referencia"> · {h.referencia}</span>}
            {h.descartado && (
              <span className="nota-descarte">{h.descartado.usuario}: {h.descartado.motivo}</span>
            )}
            {editable && (abierto === h.id ? (
              <form className="revision-hallazgo" onSubmit={e => {
                e.preventDefault();
                if (motivo.trim().length >= 3) { onRevisar(h.id, accion, motivo.trim()); cerrar(); }
              }}>
                <input autoFocus value={motivo} onChange={e => setMotivo(e.target.value)} aria-label="Justificación"
                  placeholder={h.descartado ? "¿Por qué se restaura?" : "¿Por qué no aplica? (obligatorio)"} />
                <button type="submit" className="mini primario" disabled={ocupado || motivo.trim().length < 3}>
                  {h.descartado ? "Restaurar" : "Descartar"}
                </button>
                <button type="button" className="mini" onClick={cerrar}>Cancelar</button>
              </form>
            ) : (
              <button className="enlace" onClick={() => { setAbierto(h.id); setMotivo(""); }}>
                {h.descartado ? "Restaurar hallazgo" : "No aplica / es un error"}
              </button>
            ))}
          </li>
        );
      })}
    </ul>
    </>
  );
}
