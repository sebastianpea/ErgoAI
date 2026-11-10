import { useState } from "react";
import type { EvaluacionPrevia, Segmento } from "../types/caso";
import { ETIQUETA_SEGMENTO } from "../lib/niveles";

/** Puntaje máximo REBA de cada segmento, incluidos modificadores. */
const MAXIMO: Record<Segmento, number> = { tronco: 5, cuello: 3, piernas: 4, brazo: 6, antebrazo: 2, muneca: 3 };
const SEGMENTOS = Object.keys(MAXIMO) as Segmento[];

export const REFERENCIA_VACIA: EvaluacionPrevia = { segmentos: {}, reba_final: null };

/** Campos del estudio de referencia de Jabil (controlado). Vacío = sin dato para ese segmento. */
export function CamposReferencia({ valor, onChange }: { valor: EvaluacionPrevia; onChange: (v: EvaluacionPrevia) => void }) {
  const setSeg = (s: Segmento, v: string) => {
    const segmentos = { ...valor.segmentos };
    if (v === "") delete segmentos[s]; else segmentos[s] = Number(v);
    onChange({ ...valor, segmentos });
  };
  return (
    <div className="campos campos-referencia">
      {SEGMENTOS.map(s => (
        <label key={s}>{ETIQUETA_SEGMENTO[s]}
          <select value={valor.segmentos[s] ?? ""} onChange={e => setSeg(s, e.target.value)}>
            <option value="">—</option>
            {Array.from({ length: MAXIMO[s] }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      ))}
      <label>REBA final
        <select value={valor.reba_final ?? ""} onChange={e => onChange({ ...valor, reba_final: e.target.value ? Number(e.target.value) : null })}>
          <option value="">—</option>
          {Array.from({ length: 15 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
    </div>
  );
}

interface Props {
  valor: EvaluacionPrevia;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onGuardar: (v: EvaluacionPrevia, motivo: string) => void;
}

/** Captura o corrección del estudio de referencia en un caso existente (con justificación). */
export function FormReferencia({ valor, editable, ocupado, error, onGuardar }: Props) {
  const [v, setV] = useState<EvaluacionPrevia>(valor);
  const [motivo, setMotivo] = useState("");
  const cambiado = JSON.stringify(v) !== JSON.stringify(valor);
  return (
    <form onSubmit={e => { e.preventDefault(); if (cambiado && motivo.trim().length >= 3) onGuardar(v, motivo.trim()); }}>
      <fieldset disabled={!editable || ocupado} className="sin-borde">
        <CamposReferencia valor={v} onChange={setV} />
        {editable && cambiado && (
          <>
            <label className="campo-bloque">Justificación (obligatoria)
              <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Ej. Estudio de apertura de Jabil, hoja 16-PE80-6500-00014-H" />
            </label>
            <div className="acciones">
              <button type="submit" className="primario" disabled={motivo.trim().length < 3}>Guardar referencia</button>
              <button type="button" onClick={() => { setV(valor); setMotivo(""); }}>Descartar cambios</button>
            </div>
          </>
        )}
      </fieldset>
      {error && <p className="aviso error">{error}</p>}
    </form>
  );
}
