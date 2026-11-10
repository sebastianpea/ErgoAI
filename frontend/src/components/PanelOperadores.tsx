import { useState } from "react";
import { Link } from "react-router-dom";
import type { GrupoResumen, Vista } from "../types/caso";
import { VISTAS } from "../lib/niveles";

interface Props {
  idCaso: string;
  grupo: GrupoResumen;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onAsignar: (vista: Vista, indice: number, motivo: string) => void;
}

/** Varios operadores en la misma foto: navegación entre ellos y corrección del emparejamiento por vista. */
export function PanelOperadores({ idCaso, grupo, editable, ocupado, error, onAsignar }: Props) {
  const [cambio, setCambio] = useState<{ vista: Vista; indice: number } | null>(null);
  const [motivo, setMotivo] = useState("");
  const vistas = VISTAS.filter(v => (grupo.personas_por_vista[v] ?? 0) > 0);

  return (
    <div className="tarjeta panel-operadores">
      <h2>Operador {grupo.indice} de {grupo.total}</h2>
      <p className="sutil">
        En esta foto hay varios operadores; cada uno tiene su propio análisis, REBA y plan de acción. El Excel
        oficial del grupo incluye una hoja de evaluación por operador.
      </p>
      <div className="acciones">
        {grupo.casos.map((c, i) => (
          c === idCaso
            ? <span key={c} className="boton primario activo" aria-current="page">Operador {i + 1}</span>
            : <Link key={c} className="boton" to={`/casos/${c}`}>Operador {i + 1}</Link>
        ))}
      </div>

      {vistas.length > 0 && (
        <>
          <p className="etiqueta-campo">¿Qué persona es este operador en cada foto? (1 = la de más a la izquierda)</p>
          <div className="campos campos-3">
            {vistas.map(v => (
              <label key={v}>Vista {v}
                <select
                  disabled={!editable || ocupado}
                  value={cambio?.vista === v ? cambio.indice : (grupo.asignacion[v] ?? 0)}
                  onChange={e => setCambio({ vista: v, indice: Number(e.target.value) })}
                >
                  {Array.from({ length: grupo.personas_por_vista[v] ?? 0 }, (_, i) => (
                    <option key={i} value={i}>Persona {i + 1}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          {cambio && cambio.indice !== (grupo.asignacion[cambio.vista] ?? 0) && (
            <form className="acciones" onSubmit={e => {
              e.preventDefault();
              if (motivo.trim().length >= 3) {
                onAsignar(cambio.vista, cambio.indice, motivo.trim());
                setCambio(null);
                setMotivo("");
              }
            }}>
              <input className="entrada-motivo" value={motivo} onChange={e => setMotivo(e.target.value)}
                placeholder="Justificación (obligatoria), p. ej. en la frontal el operador está a la derecha" />
              <button type="submit" className="primario" disabled={ocupado || motivo.trim().length < 3}>
                Cambiar y recalcular
              </button>
              <button type="button" onClick={() => { setCambio(null); setMotivo(""); }}>Cancelar</button>
            </form>
          )}
        </>
      )}
      {error && <p className="aviso error">{error}</p>}
    </div>
  );
}
