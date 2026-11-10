// Hoja oficial de Jabil 16-PE80-6500-00014-H: valores vacíos y etiquetas de las opciones.
import type { Hoja14H } from "../types/caso";

export const HOJA_14H_VACIA: Hoja14H = {
  negocio: "", linea: "", area: "", modelo: "",
  zona_maxima: null,
  posicion: null, espacio_pies_cm: null, tapete_antifatiga: null, reposapies_altura_cm: null,
  reposapies_profundidad_cm: null, altura_area: null, tipo_trabajo: null, tiempo_posicion: null,
  piernas_profundidad_cm: null, piernas_ancho_cm: null, asiento_cm: null, espesor_mesa_cm: null,
  fuerza_kg: null, tipo_accion: null, velocidad: null, duracion_accion: null, frecuencia: null, duracion_tarea: null,
  acceso_800mm: null, distancia_operadores_800mm: null, libertad_superiores: null, libertad_inferiores: null,
  ayuda_visual_altura: null, visualizacion: null,
  iluminacion_actividad: null, iluminacion_lux: null, reflexion_lux: null,
  evaluacion_operador: null,
};

/** Renglones de "Tipo de acción/postura" en el orden de la hoja (sección C). */
export const TIPOS_ACCION = [
  "Herramientas manuales (una mano, agarre de potencia)",
  "Trabajo con brazo (sentado, hacia arriba)",
  "Trabajo con brazo (sentado, hacia abajo)",
  "Trabajo con brazo (sentado, hacia afuera)",
  "Trabajo con brazo (sentado, hacia adentro)",
  "Empujar (con soporte de tronco)",
  "Empujar (sin soporte de tronco)",
  "Jalar (con soporte de tronco)",
  "Jalar (sin soporte de tronco)",
  "Trabajo completo de pie: empujar",
  "Trabajo completo de pie: jalar",
  "Uso de pedal - movimiento de talón",
  "Uso de pedal - movimiento de pierna",
];

export const ZONAS_ALCANCE: { valor: number; etiqueta: string }[] = [
  { valor: 1, etiqueta: "Zona 1 (frente al operador)" },
  { valor: 2, etiqueta: "Zona 2" },
  { valor: 3, etiqueta: "Zona 3" },
  { valor: 4, etiqueta: "Zona 4 (fuera de alcance)" },
  { valor: 5, etiqueta: "Zona 5 (arriba / fuera de alcance)" },
];

export const ACTIVIDADES_ILUMINACION = [
  { valor: 1, etiqueta: "1 · Empaque, oficinas (300 lx)" },
  { valor: 2, etiqueta: "2 · Laboratorios, maquinado y ensamble (500 lx)" },
  { valor: 3, etiqueta: "3 · Ensamble de precisión, piezas pequeñas (750 lx)" },
  { valor: 4, etiqueta: "4 · Alta distinción de detalles, inspección con lupa (1000 lx)" },
];

export const EVALUACION_OPERADOR = [
  { valor: 1, etiqueta: "1 · Muy bien" },
  { valor: 2, etiqueta: "2 · Bien" },
  { valor: 3, etiqueta: "3 · Algunas mejoras a realizar" },
  { valor: 4, etiqueta: "4 · Molesto" },
  { valor: 5, etiqueta: "5 · Muy doloroso" },
];
