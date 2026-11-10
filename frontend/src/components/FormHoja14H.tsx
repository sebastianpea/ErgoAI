import { useState } from "react";
import type { Hoja14H } from "../types/caso";
import {
  ACTIVIDADES_ILUMINACION, EVALUACION_OPERADOR, HOJA_14H_VACIA, TIPOS_ACCION, ZONAS_ALCANCE,
} from "../lib/hoja14h";

interface Props {
  valor: Hoja14H;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onGuardar: (h: Hoja14H) => void;
}

type Clave = keyof Hoja14H;
const num = (v: string) => (v.trim() === "" ? null : Number(v));

/**
 * Datos de la hoja oficial 16-PE80-6500-00014-H que no salen de la foto, con sus mismas secciones.
 * La sección D (análisis de segmentos) la llena el sistema con el REBA calculado.
 */
export function FormHoja14H({ valor: recibido, editable, ocupado, error, onGuardar }: Props) {
  // Un caso guardado por una versión anterior del backend puede no traer la hoja: se parte de una vacía.
  const valor: Hoja14H = { ...HOJA_14H_VACIA, ...(recibido ?? {}) };
  const [h, setH] = useState<Hoja14H>(valor);
  const cambiado = JSON.stringify(h) !== JSON.stringify(valor);
  const set = <K extends Clave>(k: K, v: Hoja14H[K]) => setH(x => ({ ...x, [k]: v }));

  const texto = (k: "negocio" | "linea" | "area" | "modelo", etiqueta: string) => (
    <label>{etiqueta}<input value={h[k]} onChange={e => set(k, e.target.value)} /></label>
  );
  const numero = (k: Clave, etiqueta: string, ayuda?: string) => (
    <label>{etiqueta}{ayuda && <span className="ayuda-campo">{ayuda}</span>}
      <input type="number" min={0} step="any" value={(h[k] as number | null) ?? ""}
        onChange={e => set(k, num(e.target.value) as never)} />
    </label>
  );
  function opciones<K extends Clave>(k: K, etiqueta: string, lista: { valor: NonNullable<Hoja14H[K]>; etiqueta: string }[]) {
    return (
      <label>{etiqueta}
        <select value={h[k] === null ? "" : String(h[k])}
          onChange={e => {
            const elegido = lista.find(o => String(o.valor) === e.target.value);
            set(k, (elegido ? elegido.valor : null) as Hoja14H[K]);
          }}>
          <option value="">—</option>
          {lista.map(o => <option key={String(o.valor)} value={String(o.valor)}>{o.etiqueta}</option>)}
        </select>
      </label>
    );
  }
  const siNo = (k: Clave, etiqueta: string, si = "Sí", no = "No") =>
    opciones(k, etiqueta, [{ valor: true, etiqueta: si }, { valor: false, etiqueta: no }] as never);

  return (
    <form onSubmit={e => { e.preventDefault(); if (cambiado) onGuardar(h); }}>
      <fieldset disabled={!editable || ocupado} className="sin-borde">
        <p className="etiqueta-campo">Encabezado</p>
        <div className="campos campos-3">
          {texto("negocio", "Negocio")}{texto("linea", "Línea")}{texto("area", "Área")}{texto("modelo", "Modelo")}
        </div>

        <p className="etiqueta-campo">A · Zona más lejana donde se toma el material</p>
        <div className="campos campos-3">{opciones("zona_maxima", "Zona de alcance", ZONAS_ALCANCE)}</div>

        <p className="etiqueta-campo">B · Área de trabajo</p>
        <div className="campos campos-3">
          {opciones("posicion", "Posición", [
            { valor: "Pie", etiqueta: "De pie" }, { valor: "Sentado", etiqueta: "Sentado" },
            { valor: "Combinado", etiqueta: "Sentado-de pie (combinado)" }])}
          {opciones("altura_area", "Altura del área de trabajo", [
            { valor: ">95<120", etiqueta: "95–120 cm" }, { valor: ">120<130", etiqueta: "120–130 cm" },
            { valor: "<95>130", etiqueta: "Menos de 95 o más de 130 cm" }])}
          {opciones("tipo_trabajo", "Tipo de trabajo", [
            { valor: "Precisión", etiqueta: "Precisión" }, { valor: "Ligero", etiqueta: "Ligero" },
            { valor: "Esfuerzo", etiqueta: "Esfuerzo" }])}
          {opciones("tiempo_posicion", "Tiempo en la posición", [
            { valor: "> 4hrs", etiqueta: "Más de 4 h" }, { valor: "≤ 4hrs", etiqueta: "4 h o menos" }])}
          {siNo("tapete_antifatiga", "Tapete antifatiga")}
          {numero("espacio_pies_cm", "Espacio para los pies (cm)", "≥ 15")}
          {numero("reposapies_altura_cm", "Altura de reposapiés (cm)", "21–37")}
          {numero("reposapies_profundidad_cm", "Profundidad de reposapiés (cm)", "15 ± 2")}
          {numero("piernas_profundidad_cm", "Espacio piernas: profundidad (cm)", "> 55")}
          {numero("piernas_ancho_cm", "Espacio piernas: ancho (cm)", "> 60")}
          {numero("asiento_cm", "Espacio para el asiento (cm)", "> 30")}
          {numero("espesor_mesa_cm", "Espesor de la mesa (cm)", "< 10")}
        </div>

        <p className="etiqueta-campo">C · Fuerza</p>
        <div className="campos campos-3">
          {numero("fuerza_kg", "Fuerza (kg)", "si se deja vacío, se usa la carga del caso")}
          {opciones("tipo_accion", "Tipo de acción/postura", TIPOS_ACCION.map((t, i) => ({ valor: i, etiqueta: t })))}
          {opciones("velocidad", "Velocidad de movimiento", [
            { valor: "inmovil", etiqueta: "Inmovilidad o muy lento" }, { valor: "apreciable", etiqueta: "Movimiento apreciable" }])}
          {opciones("duracion_accion", "Duración de la acción", [
            { valor: "menos_3s", etiqueta: "Menos de 3 s" }, { valor: "mas_3s", etiqueta: "Más de 3 s" }])}
          {opciones("frecuencia", "Frecuencia (acciones/min)", [
            { valor: "0.2_o_menos", etiqueta: "0.2 o menos" }, { valor: "0.2_2", etiqueta: "0.2 – 2" },
            { valor: "2_20", etiqueta: "2 – 20" }, { valor: "mas_20", etiqueta: "Más de 20" }])}
          {opciones("duracion_tarea", "Duración de la tarea", [
            { valor: "hasta_1h", etiqueta: "1 h o menos" }, { valor: "1_2h", etiqueta: "Más de 1 a 2 h" },
            { valor: "mas_2h", etiqueta: "Más de 2 h" }])}
        </div>

        <p className="etiqueta-campo">E · Accesibilidad</p>
        <div className="campos campos-3">
          {siNo("acceso_800mm", "Acceso al área ≥ 800 mm", "Cumple", "No cumple")}
          {siNo("distancia_operadores_800mm", "Distancia entre operadores ≥ 800 mm", "Cumple", "No cumple")}
          {siNo("libertad_superiores", "Miembros superiores", "Se mueven fácilmente", "Obstaculizados")}
          {siNo("libertad_inferiores", "Miembros inferiores", "Se mueven fácilmente", "Obstaculizados")}
        </div>

        <p className="etiqueta-campo">F · Visual – señalización · G · Iluminación · H · Evaluación del operador</p>
        <div className="campos campos-3">
          {opciones("ayuda_visual_altura", "Altura de la ayuda visual", [
            { valor: "1400_1600", etiqueta: "Entre 1,400 y 1,600 mm" }, { valor: "fuera_de_rango", etiqueta: "Menos de 1,400 o más de 1,600 mm" }])}
          {opciones("visualizacion", "Visualización", [{ valor: "Buena", etiqueta: "Buena" }, { valor: "Mala", etiqueta: "Mala" }])}
          {opciones("iluminacion_actividad", "Actividad (iluminación requerida)", ACTIVIDADES_ILUMINACION)}
          {numero("iluminacion_lux", "Iluminación medida (lux)")}
          {numero("reflexion_lux", "Reflexión medida (lux)")}
          {opciones("evaluacion_operador", "Evaluación del operador", EVALUACION_OPERADOR)}
        </div>

        {editable && (
          <div className="acciones">
            <button type="submit" className="primario" disabled={!cambiado}>Guardar hoja 14-H</button>
            {cambiado && <button type="button" onClick={() => setH(valor)}>Descartar cambios</button>}
          </div>
        )}
      </fieldset>
      {!editable && <p className="sutil">Solo Ergonomía puede capturar la hoja 14-H.</p>}
      {error && <p className="aviso error">{error}</p>}
    </form>
  );
}
