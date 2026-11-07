import { useState } from "react";
import type { Agarre, ContextoTarea, Modificadores } from "../types/caso";

const MODIFICADORES: { clave: keyof Modificadores; etiqueta: string }[] = [
  { clave: "tronco_torsion_o_inclinacion", etiqueta: "Tronco con torsión o inclinación lateral" },
  { clave: "cuello_torsion_o_inclinacion", etiqueta: "Cuello con torsión o inclinación lateral" },
  { clave: "hombro_elevado", etiqueta: "Hombro elevado" },
  { clave: "brazo_abducido_o_rotado", etiqueta: "Brazo abducido o rotado" },
  { clave: "brazo_apoyado", etiqueta: "Brazo apoyado / a favor de la gravedad" },
  { clave: "muneca_desviada_o_torcida", etiqueta: "Muñeca desviada o torcida" },
];

const AGARRES: { valor: Agarre; etiqueta: string }[] = [
  { valor: "bueno", etiqueta: "Bueno (0)" },
  { valor: "regular", etiqueta: "Regular (+1)" },
  { valor: "malo", etiqueta: "Malo (+2)" },
  { valor: "inaceptable", etiqueta: "Inaceptable (+3)" },
];

export const CONTEXTO_VACIO: ContextoTarea = {
  carga_kg: 0, carga_brusca: false, agarre: "bueno", actividad: 0, apoyo_unilateral: false,
  muneca_grados: null, altura_trabajo_cm: null,
  modificadores: {
    tronco_torsion_o_inclinacion: false, cuello_torsion_o_inclinacion: false, hombro_elevado: false,
    brazo_abducido_o_rotado: false, brazo_apoyado: false, muneca_desviada_o_torcida: false,
  },
};

const numeroONulo = (v: string) => (v.trim() === "" ? null : Number(v));

/** Campos de los datos de la tarea que no salen de la foto (controlado). */
export function CamposContexto({ valor: c, onChange }: { valor: ContextoTarea; onChange: (c: ContextoTarea) => void }) {
  const set = <K extends keyof ContextoTarea>(k: K, v: ContextoTarea[K]) => onChange({ ...c, [k]: v });
  const setMod = (k: keyof Modificadores, v: boolean) => onChange({ ...c, modificadores: { ...c.modificadores, [k]: v } });
  return (
    <>
      <div className="campos campos-3">
        <label>Carga manipulada (kg)
          <input type="number" min={0} max={200} step={0.5} value={c.carga_kg}
            onChange={e => set("carga_kg", Number(e.target.value))} />
        </label>
        <label>Agarre
          <select value={c.agarre} onChange={e => set("agarre", e.target.value as Agarre)}>
            {AGARRES.map(a => <option key={a.valor} value={a.valor}>{a.etiqueta}</option>)}
          </select>
        </label>
        <label>Condiciones de actividad (0–3)
          <input type="number" min={0} max={3} step={1} value={c.actividad}
            onChange={e => set("actividad", Math.max(0, Math.min(3, Math.round(Number(e.target.value)))))} />
        </label>
        <label>Ángulo de muñeca medido a mano (°)
          <input type="number" min={-90} max={90} step={0.5} value={c.muneca_grados ?? ""} placeholder="Lo mide la visión"
            onChange={e => set("muneca_grados", numeroONulo(e.target.value))} />
        </label>
        <label>Altura de trabajo (cm)
          <input type="number" min={1} max={250} step={1} value={c.altura_trabajo_cm ?? ""} placeholder="Sin medir"
            onChange={e => set("altura_trabajo_cm", numeroONulo(e.target.value))} />
        </label>
      </div>
      <div className="casillas">
        <label><input type="checkbox" checked={c.carga_brusca} onChange={e => set("carga_brusca", e.target.checked)} /> Carga brusca o repentina</label>
        <label><input type="checkbox" checked={c.apoyo_unilateral} onChange={e => set("apoyo_unilateral", e.target.checked)} /> Apoyo en una sola pierna</label>
        {MODIFICADORES.map(m => (
          <label key={m.clave}>
            <input type="checkbox" checked={c.modificadores[m.clave]} onChange={e => setMod(m.clave, e.target.checked)} /> {m.etiqueta}
          </label>
        ))}
      </div>
    </>
  );
}

interface Props {
  contexto: ContextoTarea;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onGuardar: (contexto: ContextoTarea, motivo: string) => void;
}

/** Corrección de los datos de la tarea de un caso existente, con justificación obligatoria. */
export function FormContexto({ contexto, editable, ocupado, error, onGuardar }: Props) {
  const [c, setC] = useState<ContextoTarea>(contexto);
  const [motivo, setMotivo] = useState("");
  const cambiado = JSON.stringify(c) !== JSON.stringify(contexto);

  return (
    <form onSubmit={e => { e.preventDefault(); if (cambiado && motivo.trim().length >= 3) onGuardar(c, motivo.trim()); }}>
      <fieldset disabled={!editable || ocupado} className="sin-borde">
        <CamposContexto valor={c} onChange={setC} />
        {editable && cambiado && (
          <>
            <label className="campo-bloque">Justificación de la corrección (obligatoria)
              <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Ej. Se pesó la pieza en báscula: 12 kg" />
            </label>
            <div className="acciones">
              <button type="submit" className="primario" disabled={motivo.trim().length < 3}>Guardar y recalcular REBA</button>
              <button type="button" onClick={() => { setC(contexto); setMotivo(""); }}>Descartar cambios</button>
            </div>
          </>
        )}
      </fieldset>
      {!editable && <p className="sutil">Solo Ergonomía puede corregir estos datos.</p>}
      {error && <p className="aviso error">{error}</p>}
    </form>
  );
}
