import type { ColorNom, EstadoImplementacion, NivelReba, Segmento, TipoCambio, TipoTarea, Vista } from "../types/caso";
import type { NivelUrgencia, TipoEvento } from "../types/alerta";

export const VISTAS: Vista[] = ["lateral", "frontal", "cenital"];

export type Semaforo = "gris" | "verde" | "amarillo" | "naranja" | "rojo" | "morado";

export const COLOR_SEMAFORO: Record<Semaforo, string> = {
  gris: "#8A9EB4",
  verde: "#2E9E5B",
  amarillo: "#E0B000",
  naranja: "#E8790C",
  rojo: "#D93A3A",
  morado: "#7B3FA0",
};

export const NIVEL_REBA: Record<NivelReba, { etiqueta: string; color: Semaforo; orden: number; maxScore: number }> = {
  inapreciable: { etiqueta: "Inapreciable", color: "gris", orden: 0, maxScore: 1 },
  bajo: { etiqueta: "Bajo", color: "verde", orden: 1, maxScore: 3 },
  medio: { etiqueta: "Medio", color: "amarillo", orden: 2, maxScore: 7 },
  alto: { etiqueta: "Alto", color: "naranja", orden: 3, maxScore: 10 },
  muy_alto: { etiqueta: "Muy alto", color: "rojo", orden: 4, maxScore: 15 },
};

export function nivelDeReba(final: number) {
  if (final <= NIVEL_REBA.inapreciable.maxScore) return NIVEL_REBA.inapreciable;
  if (final <= NIVEL_REBA.bajo.maxScore) return NIVEL_REBA.bajo;
  if (final <= NIVEL_REBA.medio.maxScore) return NIVEL_REBA.medio;
  if (final <= NIVEL_REBA.alto.maxScore) return NIVEL_REBA.alto;
  return NIVEL_REBA.muy_alto;
}

export const ETIQUETA_COLOR_NOM: Record<ColorNom, string> = {
  verde: "Verde",
  amarillo: "Amarillo",
  naranja: "Naranja",
  rojo: "Rojo",
  morado: "Morado",
};

export const ETIQUETA_SEGMENTO: Record<Segmento, string> = {
  tronco: "Tronco",
  cuello: "Cuello",
  piernas: "Piernas",
  brazo: "Brazo",
  antebrazo: "Antebrazo",
  muneca: "Muñeca",
};

export const ETIQUETA_TAREA: Record<TipoTarea, string> = {
  // Terminología de la rúbrica Jabil: levantamiento, transporte sin auxiliar y transporte con auxiliar.
  sin_clasificar: "Sin clasificar · requiere revisión",
  postura: "Postura (ensamble)",
  levantamiento: "Levantamiento",
  transporte: "Transporte sin auxiliar (acarreo)",
  empuje_con_auxiliar: "Transporte con auxiliar (carro)",
  empuje_sin_auxiliar: "Empuje/arrastre sin auxiliar",
};

export const ETIQUETA_EVENTO: Record<TipoEvento, string> = {
  RIESGO_ALTO_PENDIENTE: "Riesgo alto pendiente",
  DISCREPANCIA_EVALUACION: "Discrepancia con evaluación previa",
  ANGULO_POR_REVISAR: "Ángulo por revisar",
  OBJETO_DESCONOCIDO: "Objeto desconocido en estación",
  AUTORIZACION_PENDIENTE: "Cambio en planta por autorizar",
  EMERGENCIA_CAIDA: "Emergencia: caída (fase 2)",
};

export const ETIQUETA_TIPO_CAMBIO: Record<TipoCambio, string> = {
  planta: "Cambio en planta",
  postura: "Ajuste de postura / método",
  administrativo: "Medida administrativa",
};

export const ETIQUETA_IMPLEMENTACION: Record<EstadoImplementacion, string> = {
  pendiente_autorizacion: "Esperando autorización de ingeniería",
  por_implementar: "Por implementar",
  implementada: "Implementada",
  denegada: "Denegada por ingeniería",
};

/** Formatea el valor de un cambio propuesto con su unidad. */
export function valorCambio(v: boolean | number | string | null | undefined, unidad?: string | null): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Sí" : "No";
  if (typeof v === "number") {
    const n = Number.isInteger(v) ? v.toString() : v.toFixed(1);
    return unidad === "°" ? `${n}°` : unidad ? `${n} ${unidad}` : n;
  }
  return v;
}

export const COLOR_URGENCIA: Record<NivelUrgencia, Semaforo> = {
  BAJO: "verde",
  MEDIO: "amarillo",
  ALTO: "naranja",
  CRITICO: "rojo",
};

/** Color de un segmento según su puntaje REBA parcial (solo para pintar el esqueleto). */
export function semaforoSegmento(puntaje: number | undefined): Semaforo {
  if (puntaje === undefined) return "gris";
  if (puntaje <= 1) return "verde";
  if (puntaje === 2) return "amarillo";
  if (puntaje === 3) return "naranja";
  return "rojo";
}

export function formatearFecha(iso: string): string {
  return new Date(iso).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}