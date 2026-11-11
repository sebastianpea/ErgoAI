import { useState } from "react";
import type { Agarre, ContextoTarea, Modificadores, TipoTarea } from "../types/caso";
import { ETIQUETA_TAREA } from "../lib/niveles";

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
  carga_kg: null, carga_brusca: null, agarre: null, actividad: null, apoyo_unilateral: null,
  muneca_grados: null, altura_trabajo_cm: null,
  modificadores: {
    tronco_torsion_o_inclinacion: null, cuello_torsion_o_inclinacion: null, hombro_elevado: null,
    brazo_abducido_o_rotado: null, brazo_apoyado: null, muneca_desviada_o_torcida: null,
  },
};

const numeroONulo = (v: string) => (v.trim() === "" ? null : Number(v));
const booleanoONulo = (v: string) => v === "" ? null : v === "true";

function SelectorSiNo({ etiqueta, valor, onChange }: { etiqueta: string; valor: boolean | null; onChange: (v: boolean | null) => void }) {
  return (
    <label>{etiqueta}
      <select value={valor === null ? "" : String(valor)} onChange={e => onChange(booleanoONulo(e.target.value))}>
        <option value="">Sin confirmar</option>
        <option value="false">No</option>
        <option value="true">Sí</option>
      </select>
    </label>
  );
}

/** Captura explícita: los campos en blanco permanecen desconocidos, no se convierten en cero o "no". */
export function CamposContexto({ valor: c, onChange }: { valor: ContextoTarea; onChange: (c: ContextoTarea) => void }) {
  const set = <K extends keyof ContextoTarea>(k: K, v: ContextoTarea[K]) => onChange({ ...c, [k]: v });
  const setMod = (k: keyof Modificadores, v: boolean | null) => onChange({ ...c, modificadores: { ...c.modificadores, [k]: v } });
  return (
    <>
      <div className="campos campos-3">
        <label>Carga manipulada (kg)
          <input type="number" min={0} max={200} step={0.5} value={c.carga_kg ?? ""} placeholder="Sin pesar"
            onChange={e => set("carga_kg", numeroONulo(e.target.value))} />
        </label>
        <label>Agarre
          <select value={c.agarre ?? ""} onChange={e => set("agarre", e.target.value ? e.target.value as Agarre : null)}>
            <option value="">Sin confirmar</option>
            {AGARRES.map(a => <option key={a.valor} value={a.valor}>{a.etiqueta}</option>)}
          </select>
        </label>
        <label>Condiciones de actividad (0–3)
          <select value={c.actividad ?? ""} onChange={e => set("actividad", e.target.value === "" ? null : Number(e.target.value))}>
            <option value="">Sin confirmar</option>
            {[0, 1, 2, 3].map(n => <option key={n} value={n}>{n} condición{n === 1 ? "" : "es"}</option>)}
          </select>
        </label>
        <label>Ángulo de muñeca (°), si la visión no lo midió
          <input type="number" min={-90} max={90} step={0.5} value={c.muneca_grados ?? ""} placeholder="Lo mide la foto; corregible"
            onChange={e => set("muneca_grados", numeroONulo(e.target.value))} />
        </label>
        <label>Altura de trabajo (cm)
          <input type="number" min={1} max={250} step={1} value={c.altura_trabajo_cm ?? ""} placeholder="Medir en piso"
            onChange={e => set("altura_trabajo_cm", numeroONulo(e.target.value))} />
        </label>
      </div>
      <p className="sutil">
        En REBA, actividad suma 1 por cada condición presente: postura estática por más de 1 minuto; movimientos pequeños repetidos más de 4 veces por minuto; cambios rápidos de postura o base inestable. La foto no permite medir repetición ni duración: confirmalo en piso.
      </p>
      <div className="campos campos-3">
        <SelectorSiNo etiqueta="¿La carga se aplica de forma brusca o repentina?" valor={c.carga_brusca} onChange={v => set("carga_brusca", v)} />
        <SelectorSiNo etiqueta="¿El apoyo es principalmente en una pierna?" valor={c.apoyo_unilateral} onChange={v => set("apoyo_unilateral", v)} />
        {MODIFICADORES.map(m => (
          <SelectorSiNo key={m.clave} etiqueta={m.etiqueta} valor={c.modificadores[m.clave]} onChange={v => setMod(m.clave, v)} />
        ))}
      </div>
    </>
  );
}

interface Props {
  contexto: ContextoTarea;
  contextoFaltante?: string[];
  tipoTarea: TipoTarea;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onGuardar: (contexto: ContextoTarea, tipoTarea: TipoTarea, motivo: string) => void;
}

function contextoParaEdicion(contexto: ContextoTarea, faltantes: string[]): ContextoTarea {
  const faltan = new Set(faltantes);
  return {
    ...contexto,
    carga_kg: faltan.has("carga_kg") ? null : contexto.carga_kg,
    carga_brusca: faltan.has("carga_brusca") ? null : contexto.carga_brusca,
    agarre: faltan.has("agarre") ? null : contexto.agarre,
    actividad: faltan.has("actividad") ? null : contexto.actividad,
    apoyo_unilateral: faltan.has("apoyo_unilateral") ? null : contexto.apoyo_unilateral,
    altura_trabajo_cm: faltan.has("altura_trabajo_cm") ? null : contexto.altura_trabajo_cm,
    modificadores: Object.fromEntries(Object.entries(contexto.modificadores).map(([k, v]) => [k, faltan.has(`modificadores.${k}`) ? null : v])) as Modificadores,
  };
}

/** Corrección de contexto y clasificación; la justificación sigue siendo obligatoria. */
export function FormContexto({ contexto, contextoFaltante = [], tipoTarea, editable, ocupado, error, onGuardar }: Props) {
  const original = contextoParaEdicion(contexto, contextoFaltante);
  const [c, setC] = useState<ContextoTarea>(original);
  const [tarea, setTarea] = useState<TipoTarea>(tipoTarea);
  const [motivo, setMotivo] = useState("");
  const cambiado = JSON.stringify(c) !== JSON.stringify(original) || tarea !== tipoTarea;

  return (
    <form onSubmit={e => { e.preventDefault(); if (cambiado && motivo.trim().length >= 3) onGuardar(c, tarea, motivo.trim()); }}>
      <fieldset disabled={!editable || ocupado} className="sin-borde">
        <label className="campo-bloque">Tipo de tarea
          <select value={tarea} onChange={e => setTarea(e.target.value as TipoTarea)}>
            {(Object.keys(ETIQUETA_TAREA) as TipoTarea[]).map(t => <option key={t} value={t}>{ETIQUETA_TAREA[t]}</option>)}
          </select>
        </label>
        <CamposContexto valor={c} onChange={setC} />
        {editable && cambiado && (
          <>
            <label className="campo-bloque">Justificación de la corrección (obligatoria)
              <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Ej. Se pesó la pieza en báscula: 12 kg" />
            </label>
            <div className="acciones">
              <button type="submit" className="primario" disabled={motivo.trim().length < 3}>Guardar y recalcular</button>
              <button type="button" onClick={() => { setC(original); setTarea(tipoTarea); setMotivo(""); }}>Descartar cambios</button>
            </div>
          </>
        )}
      </fieldset>
      {!editable && <p className="sutil">Solo Ergonomía puede corregir estos datos.</p>}
      {error && <p className="aviso error">{error}</p>}
    </form>
  );
}
