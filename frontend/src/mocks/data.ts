// Datos simulados para trabajar sin backend. Mismo formato que el contrato.
// `validacion` no se guarda: api.ts la calcula con la misma regla que el backend.
import type {
  CambioPropuesto, CasoDetalle, ContextoTarea, Imagen, NivelControl, Punto, Recomendacion, TipoCambio,
} from "../types/caso";
import type { Alerta } from "../types/alerta";

export type CasoMock = Omit<CasoDetalle, "validacion">;

const FOTO = "/mock/placeholder.svg";

// [id, x, y, confianza]
type P = [number, number, number, number];
const pts = (lista: P[]): Punto[] =>
  lista.map(([id, x, y, confianza]) => ({ id, x, y, confianza, corregido: false }));

const lateral: Imagen = {
  vista: "lateral", url: FOTO, ancho: 1280, alto: 720,
  puntos: pts([
    [0, 772, 300, 0.62], [1, 765, 288, 0.55], [2, 768, 290, 0.5], [3, 745, 292, 0.81], [4, 742, 295, 0.4],
    [5, 700, 332, 0.93], [6, 694, 336, 0.71], [7, 724, 452, 0.9], [8, 716, 456, 0.66],
    [9, 795, 520, 0.88], [10, 788, 526, 0.35], [11, 580, 442, 0.95], [12, 574, 446, 0.8],
    [13, 612, 560, 0.92], [14, 606, 564, 0.77], [15, 600, 680, 0.9], [16, 594, 684, 0.74],
  ]),
};

const frontal: Imagen = {
  vista: "frontal", url: FOTO, ancho: 1280, alto: 720,
  puntos: pts([
    [0, 640, 232, 0.7], [1, 650, 220, 0.6], [2, 630, 220, 0.6], [3, 665, 230, 0.75], [4, 615, 230, 0.75],
    [5, 720, 300, 0.95], [6, 560, 300, 0.95], [7, 762, 392, 0.9], [8, 528, 402, 0.9],
    [9, 742, 472, 0.86], [10, 558, 482, 0.84], [11, 690, 450, 0.93], [12, 590, 450, 0.93],
    [13, 682, 570, 0.9], [14, 598, 570, 0.9], [15, 680, 690, 0.88], [16, 600, 690, 0.88],
  ]),
};

const cenital: Imagen = {
  vista: "cenital", url: FOTO, ancho: 1280, alto: 720,
  puntos: pts([
    [0, 640, 300, 0.45], [1, 652, 296, 0.4], [2, 628, 296, 0.4], [3, 668, 290, 0.6], [4, 612, 290, 0.6],
    [5, 715, 330, 0.88], [6, 565, 330, 0.88], [7, 770, 410, 0.8], [8, 520, 405, 0.82],
    [9, 760, 500, 0.78], [10, 535, 495, 0.8], [11, 680, 360, 0.3], [12, 600, 360, 0.3],
    [13, 680, 380, 0.15], [14, 600, 380, 0.15], [15, 680, 390, 0.1], [16, 600, 390, 0.1],
  ]),
};

const rec = (
  id: string, nivel_control: NivelControl, tipo_cambio: TipoCambio, titulo: string, texto: string,
  referencia: string, reba_proyectado: number | null, cambios: CambioPropuesto[],
): Recomendacion => ({
  id, nivel_control, tipo_cambio, titulo, texto, referencia, origen: "ia", estado: "propuesta", implementacion: null,
  cambios, reba_proyectado, requiere_autorizacion: tipo_cambio === "planta",
});

const num = (parametro: string, etiqueta: string, unidad: string, actual: number, objetivo: number): CambioPropuesto => ({
  parametro, etiqueta, tipo: "numero", unidad, actual, objetivo, minimo: unidad === "kg" ? 0 : -90, maximo: unidad === "kg" ? 200 : 180, opciones: [],
});

const contexto: ContextoTarea = {
  carga_kg: 16, carga_brusca: false, agarre: "regular", actividad: 1, apoyo_unilateral: false,
  muneca_grados: null, altura_trabajo_cm: null,
  modificadores: {
    tronco_torsion_o_inclinacion: true, cuello_torsion_o_inclinacion: true, hombro_elevado: false,
    brazo_abducido_o_rotado: false, brazo_apoyado: false, muneca_desviada_o_torcida: false,
  },
};

const casoBase: CasoMock = {
  id_caso: "C-001",
  estacion: "Linea_2 · Estación 04",
  tipo_tarea: "levantamiento",
  fecha: "2026-11-06T10:00:00-06:00",
  imagenes: [lateral, frontal, cenital],
  contexto,
  evaluacion_previa: { segmentos: { tronco: 2, cuello: 1, piernas: 1, brazo: 3, antebrazo: 1 }, reba_final: 7 },
  metricas: { creado_en: null, analisis_ms: null, primera_decision_en: null, validado_en: null },
  angulos: [
    { segmento: "tronco", lado: null, vista: "lateral", angulo_grados: 34.2, puntaje_reba: 3, modificadores: ["torsión"], estado: "ok", puntaje_previo: 2 },
    { segmento: "cuello", lado: null, vista: "lateral", angulo_grados: 22.5, puntaje_reba: 2, modificadores: [], estado: "revisar", puntaje_previo: 1 },
    { segmento: "piernas", lado: null, vista: "lateral", angulo_grados: 12.0, puntaje_reba: 1, modificadores: [], estado: "ok", puntaje_previo: 1 },
    { segmento: "brazo", lado: "izq", vista: "lateral", angulo_grados: 48.0, puntaje_reba: 3, modificadores: [], estado: "ok", puntaje_previo: 3 },
    { segmento: "antebrazo", lado: "izq", vista: "lateral", angulo_grados: 75.0, puntaje_reba: 1, modificadores: [], estado: "ok", puntaje_previo: 1 },
    { segmento: "muneca", lado: "izq", vista: "lateral", angulo_grados: null, puntaje_reba: 1, modificadores: [], estado: "sin_dato", puntaje_previo: null },
  ],
  reba: { grupo_a: 5, grupo_b: 4, tabla_c: 6, carga: 2, agarre: 1, actividad: 1, final: 9, nivel: "alto" },
  nom036: {
    metodo: "levantamiento", total: 14, nivel: "rojo", // total = suma de factores
    factores: [
      { codigo: "peso_frecuencia", etiqueta: "Peso de la carga y frecuencia", color: "rojo", valor: 6 },
      { codigo: "distancia_horizontal", etiqueta: "Distancia horizontal manos–espalda", color: "amarillo", valor: 3 },
      { codigo: "region_vertical", etiqueta: "Región vertical del levantamiento", color: "naranja", valor: 3 },
      { codigo: "torsion", etiqueta: "Torsión e inclinación lateral", color: "amarillo", valor: 1 },
      { codigo: "postura", etiqueta: "Restricciones posturales", color: "verde", valor: 0 },
      { codigo: "agarre", etiqueta: "Agarre de la carga", color: "amarillo", valor: 1 },
      { codigo: "piso", etiqueta: "Superficie del piso", color: "verde", valor: 0 },
      { codigo: "otros", etiqueta: "Otros factores ambientales", color: "verde", valor: 0 },
    ],
  },
  hallazgos: [
    { id: "H1", origen: "vision", severidad: "advertencia", mensaje: "Botella sobre la mesa en zona de alcance 2", vista: "cenital", caja: [930, 420, 70, 150] },
    { id: "H2", origen: "reglas_jabil", severidad: "critico", mensaje: "Carga de 16 kg supera el límite de 14 kg por persona", referencia: "16-PE30-6500-00023 §6.4.1" },
    { id: "H3", origen: "auditoria", severidad: "advertencia", mensaje: "Tronco capturado en rango 2; la foto indica rango 3 (REBA 7 → 9)" },
  ],
  recomendaciones: [
    rec("R1", "ingenieria", "planta", "Asistencia mecánica para la carga", "Instalar lifter o mesa elevadora para eliminar el levantamiento manual de 16 kg.", "16-PE30-6500-00023 §6.4.1; NOM-036-1-STPS-2018", 8,
      [num("carga_kg", "Carga manipulada", "kg", 16, 0)]),
    rec("R2", "ingenieria", "planta", "Elevar la superficie de toma", "Colocar el material a la altura de codos (95–120 cm) para reducir la flexión de tronco.", "16-PE30-6500-00023 §6.4.4 y §7.2.3", 6,
      [num("angulo.tronco", "Ángulo de tronco", "°", 47.5, 10), num("angulo.brazo", "Ángulo de brazo", "°", 58.8, 15)]),
    rec("R3", "administrativo", "administrativo", "Rotación de puesto", "Rotar entre esta estación y una de bajo riesgo cada 2 horas mientras se implementan los controles de ingeniería.", "NOM-036-1-STPS-2018", null, []),
    rec("R4", "administrativo", "postura", "Corregir técnica de levantamiento", "Capacitar al operador para flexionar rodillas y reducir 15° la flexión de tronco al tomar la pieza.", "NOM-036-1-STPS-2018 capacitación", 9,
      [num("angulo.tronco", "Ángulo de tronco", "°", 47.5, 32.5)]),
  ],
  residual: {
    antes_final: 9, antes_nivel: "alto", despues_final: 4, despues_nivel: "medio",
    segmentos: [
      { segmento: "tronco", antes: 3, despues: 1 },
      { segmento: "cuello", antes: 2, despues: 1 },
      { segmento: "piernas", antes: 1, despues: 1 },
      { segmento: "brazo", antes: 3, despues: 2 },
      { segmento: "antebrazo", antes: 1, despues: 1 },
      { segmento: "muneca", antes: 1, despues: 1 },
    ],
    recomendaciones_aplicadas: ["R1", "R2"],
  },
};

const clonar = <T,>(x: T): T => structuredClone(x);

const caso2 = clonar(casoBase);
caso2.id_caso = "C-002";
caso2.estacion = "Linea_5 · Empaque";
caso2.tipo_tarea = "empuje_sin_auxiliar";
caso2.fecha = "2026-11-06T11:30:00-06:00";
caso2.reba = { ...casoBase.reba!, final: 11, nivel: "muy_alto" };
caso2.nom036 = {
  ...casoBase.nom036!, metodo: "empuje_sin_auxiliar", total: 22, nivel: "morado",
  factores: casoBase.nom036!.factores.map(f =>
    f.codigo === "peso_frecuencia" ? { ...f, color: "morado", valor: 10 } :
    f.codigo === "postura" ? { ...f, color: "rojo", valor: 3 } :
    f.codigo === "piso" ? { ...f, color: "amarillo", valor: 1 } : f),
};
caso2.residual = { ...casoBase.residual!, antes_final: 11, antes_nivel: "muy_alto", despues_final: 5, despues_nivel: "medio" };

const caso3 = clonar(casoBase);
caso3.id_caso = "C-003";
caso3.estacion = "Linea_1 · Ensamble fino";
caso3.tipo_tarea = "postura";
caso3.fecha = "2026-11-06T09:10:00-06:00";
caso3.reba = { ...casoBase.reba!, carga: 0, final: 5, nivel: "medio" };
caso3.nom036 = null;
caso3.hallazgos = casoBase.hallazgos.filter(h => h.id === "H1");
caso3.recomendaciones = [casoBase.recomendaciones[1]];
caso3.residual = { ...casoBase.residual!, antes_final: 5, antes_nivel: "medio", despues_final: 2, despues_nivel: "bajo", recomendaciones_aplicadas: ["R2"] };

export const casosMock: CasoMock[] = [casoBase, caso2, caso3];

export const alertasMock: Alerta[] = [
  { id_alerta: "A1", id_operario: null, estacion: "Linea_5 · Empaque", tipo_evento: "RIESGO_ALTO_PENDIENTE", nivel_urgencia: "CRITICO", detalles: "REBA 11 (muy alto) sin validación del especialista", timestamp: "2026-11-06T11:31:00-06:00", id_caso: "C-002", estado: "nueva" },
  { id_alerta: "A2", id_operario: null, estacion: "Linea_2 · Estación 04", tipo_evento: "DISCREPANCIA_EVALUACION", nivel_urgencia: "ALTO", detalles: "Tronco capturado en rango 2; la foto indica rango 3", timestamp: "2026-11-06T10:02:00-06:00", id_caso: "C-001", estado: "nueva" },
  { id_alerta: "A3", id_operario: null, estacion: "Linea_1 · Ensamble fino", tipo_evento: "OBJETO_DESCONOCIDO", nivel_urgencia: "MEDIO", detalles: "Botella sobre la mesa en zona de alcance 2", timestamp: "2026-11-06T09:12:00-06:00", id_caso: "C-003", estado: "vista" },
  { id_alerta: "A4", id_operario: "OP-1042", estacion: "Linea_2", tipo_evento: "EMERGENCIA_CAIDA", nivel_urgencia: "ALTO", detalles: "Simulación fase 2: persona desmayada o golpe con levantamiento rápido", timestamp: "2026-10-30T15:15:00-06:00", id_caso: null, estado: "nueva" },
];