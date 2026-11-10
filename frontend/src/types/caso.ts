// Contrato principal: debe coincidir con los modelos Pydantic del backend.

export type Vista = "lateral" | "frontal" | "cenital";
export type TipoTarea =
  | "postura"
  | "levantamiento"
  | "transporte"
  | "empuje_sin_auxiliar"
  | "empuje_con_auxiliar";
export type NivelReba = "inapreciable" | "bajo" | "medio" | "alto" | "muy_alto";
export type Segmento = "tronco" | "cuello" | "piernas" | "brazo" | "antebrazo" | "muneca";
export type ColorNom = "verde" | "amarillo" | "naranja" | "rojo" | "morado";

/**
 * Punto del esqueleto. id 0–16 = COCO-17 (0 nariz, 5 hombro izq, 11 cadera izq...);
 * 17/18 = nudillo medio izq/der (RTMPose WholeBody-133), para medir la muñeca.
 */
export interface Punto {
  id: number;
  x: number; // píxeles de la imagen original
  y: number;
  confianza: number; // 0 a 1
  corregido: boolean; // true si el especialista lo movió
}

export interface Imagen {
  vista: Vista;
  url: string;
  ancho: number;
  alto: number;
  puntos: Punto[];
}

export interface Angulo {
  segmento: Segmento;
  lado: "izq" | "der" | null;
  vista: Vista;
  angulo_grados: number | null;
  puntaje_reba: number;
  modificadores: string[];
  estado: "ok" | "revisar" | "sin_dato";
  motivo_estado?: string | null;
  confirmado?: boolean;
  puntaje_previo?: number | null; // de la evaluación capturada en piso, si existe
}

export interface ResultadoReba {
  grupo_a: number;
  grupo_b: number;
  tabla_c: number;
  carga: number;
  agarre: number;
  actividad: number;
  final: number;
  nivel: NivelReba;
}

export interface FactorNom {
  codigo: string;
  etiqueta: string;
  color: ColorNom;
  valor: number;
}

export type MetodoNom036 = Exclude<TipoTarea, "postura">;

export interface ResultadoNom036 {
  metodo: MetodoNom036;
  total: number;
  nivel: ColorNom;
  factores: FactorNom[];
}

/** El especialista marcó el hallazgo como falso positivo o no aplicable. */
export interface Descarte {
  motivo: string;
  usuario: string;
  timestamp: string;
}

export interface Hallazgo {
  id: string;
  origen: "vision" | "reglas_jabil" | "auditoria";
  severidad: "info" | "advertencia" | "critico";
  mensaje: string;
  referencia?: string | null;
  vista?: Vista | null;
  caja?: [number, number, number, number] | null; // x, y, ancho, alto en píxeles
  descartado?: Descarte | null;
}

/** Sin login en el prototipo: el rol se elige en la barra superior. */
export type Rol = "ergonomia" | "ingenieria";
export interface Actor {
  usuario: string;
  rol: Rol;
}

export type Agarre = "bueno" | "regular" | "malo" | "inaceptable";

export interface Modificadores {
  tronco_torsion_o_inclinacion: boolean;
  cuello_torsion_o_inclinacion: boolean;
  hombro_elevado: boolean;
  brazo_abducido_o_rotado: boolean;
  brazo_apoyado: boolean;
  muneca_desviada_o_torcida: boolean;
}

/** Datos de la tarea que no salen de la foto; el especialista los puede corregir. */
export interface ContextoTarea {
  carga_kg: number;
  carga_brusca: boolean;
  agarre: Agarre;
  actividad: number; // 0–3
  apoyo_unilateral: boolean;
  muneca_grados: number | null;
  altura_trabajo_cm: number | null;
  /** Personas que manipulan la misma carga (2 = levantamiento en equipo, hoja NOM-036 Equipo (3)). */
  personas_en_carga: number;
  modificadores: Modificadores;
}

export type ValorCambio = boolean | number | string;

/** Un ajuste concreto que propone una recomendación (p. ej. tronco 47.5° → 32.5°). */
export interface CambioPropuesto {
  parametro: string; // "angulo.tronco", "carga_kg", "agarre", "mod.hombro_elevado"…
  etiqueta: string;
  tipo: "numero" | "booleano" | "opcion";
  unidad?: string | null;
  actual: ValorCambio | null;
  objetivo: ValorCambio | null;
  minimo?: number | null;
  maximo?: number | null;
  opciones: string[];
}

export type NivelControl = "ingenieria" | "administrativo";
/** planta = cambio físico (equipo, layout, alturas): requiere autorización de ingeniería. */
export type TipoCambio = "planta" | "postura" | "administrativo";
export type EstadoRecomendacion = "propuesta" | "aprobada" | "editada_aprobada" | "rechazada";
export type EstadoImplementacion = "pendiente_autorizacion" | "por_implementar" | "implementada" | "denegada";

export interface Recomendacion {
  id: string;
  nivel_control: NivelControl;
  tipo_cambio: TipoCambio;
  titulo: string;
  texto: string;
  referencia: string;
  origen: "ia" | "especialista";
  estado: EstadoRecomendacion;
  implementacion: EstadoImplementacion | null;
  responsable?: string | null;
  fecha_compromiso?: string | null; // YYYY-MM-DD
  aprobado_por?: string | null;
  autorizado_por?: string | null;
  nota_autorizacion?: string | null;
  implementado_por?: string | null;
  nota_implementacion?: string | null;
  cambios: CambioPropuesto[];
  reba_proyectado: number | null;
  requiere_autorizacion: boolean;
  justificacion_rag?: string | null;
  norma_vinculada?: string | null;
  codigo_jabil?: string | null;
  hoja_excel_jabil?: string | null;
  layer_autocad?: string | null;
  tramite_moc?: string | null;
}

export interface Residual {
  antes_final: number;
  antes_nivel: NivelReba;
  despues_final: number;
  despues_nivel: NivelReba;
  segmentos: { segmento: Segmento; antes: number; despues: number }[];
  recomendaciones_aplicadas: string[];
}

export interface CasoResumen {
  id_caso: string;
  estacion: string;
  tipo_tarea: TipoTarea;
  fecha: string;
  reba_final: number | null;
  nivel: NivelReba | null;
  decisiones_pendientes: number;
  por_autorizar: number;
}

/** Página del servidor, ordenada por id_caso ascendente. */
export interface PaginaCasos {
  items: CasoResumen[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** Agregados de todos los casos, independientes de la página consultada. */
export interface MetricasDashboard {
  total_casos: number;
  niveles: Record<NivelReba | "sin_evaluar", number>;
  tipos_tarea: Record<string, number>;
  decisiones_pendientes: number;
  por_autorizar: number;
}

/** Calculado por el backend: el informe solo se habilita cuando `completa` es true. */
export interface Validacion {
  pendientes: number;
  falta_ingenieria: boolean; // riesgo alto/muy alto sin control de ingeniería aprobado
  completa: boolean;
  por_autorizar: number; // cambios en planta esperando a ingeniería
  por_implementar: number;
  implementadas: number;
  aprobado_e_implementado?: boolean;
}

/** Estudio de referencia de Jabil (puntajes REBA capturados en piso). */
export interface EvaluacionPrevia {
  segmentos: Partial<Record<Segmento, number>>;
  reba_final: number | null;
}

/** Tiempos del estudio (criterio 8: impacto en tiempos de respuesta). */
export interface Metricas {
  creado_en: string | null;
  analisis_ms: number | null;
  primera_decision_en: string | null;
  validado_en: string | null;
}

export interface Impacto {
  minutos_evaluacion_manual: number;
  fuente_referencia_manual: string;
  casos: { id_caso: string; estacion: string; analisis_s: number | null; validacion_min: number | null }[];
  analisis_promedio_s: number | null;
  validacion_promedio_min: number | null;
  ahorro_promedio_min: number | null;
  ahorro_porcentaje: number | null;
}

export interface CasoDetalle {
  id_caso: string;
  estacion: string;
  tipo_tarea: TipoTarea;
  fecha: string;
  imagenes: Imagen[];
  contexto: ContextoTarea;
  evaluacion_previa: EvaluacionPrevia;
  angulos: Angulo[];
  reba: ResultadoReba | null;
  nom036: ResultadoNom036 | null;
  hallazgos: Hallazgo[];
  recomendaciones: Recomendacion[];
  residual: Residual | null;
  validacion: Validacion;
  metricas: Metricas;
  hoja_14h: Hoja14H;
  grupo: GrupoResumen | null;
}

/** Varios operadores en la misma foto: un caso por operador. */
export interface GrupoResumen {
  id_grupo: string;
  indice: number;
  total: number;
  casos: string[];
  personas_por_vista: Partial<Record<Vista, number>>;
  asignacion: Partial<Record<Vista, number>>; // vista → persona detectada (0 = la de más a la izquierda)
}

/** Datos de la hoja oficial 16-PE80-6500-00014-H que no salen de la foto. Todo es opcional. */
export interface Hoja14H {
  negocio: string;
  linea: string;
  area: string;
  modelo: string;
  zona_maxima: number | null;
  posicion: "Sentado" | "Pie" | "Combinado" | null;
  espacio_pies_cm: number | null;
  tapete_antifatiga: boolean | null;
  reposapies_altura_cm: number | null;
  reposapies_profundidad_cm: number | null;
  altura_area: ">95<120" | ">120<130" | "<95>130" | null;
  tipo_trabajo: "Precisión" | "Ligero" | "Esfuerzo" | null;
  tiempo_posicion: "> 4hrs" | "≤ 4hrs" | null;
  piernas_profundidad_cm: number | null;
  piernas_ancho_cm: number | null;
  asiento_cm: number | null;
  espesor_mesa_cm: number | null;
  fuerza_kg: number | null;
  tipo_accion: number | null;
  velocidad: "inmovil" | "apreciable" | null;
  duracion_accion: "menos_3s" | "mas_3s" | null;
  frecuencia: "0.2_o_menos" | "0.2_2" | "2_20" | "mas_20" | null;
  duracion_tarea: "hasta_1h" | "1_2h" | "mas_2h" | null;
  acceso_800mm: boolean | null;
  distancia_operadores_800mm: boolean | null;
  libertad_superiores: boolean | null;
  libertad_inferiores: boolean | null;
  ayuda_visual_altura: "1400_1600" | "fuera_de_rango" | null;
  visualizacion: "Buena" | "Mala" | null;
  iluminacion_actividad: number | null;
  iluminacion_lux: number | null;
  reflexion_lux: number | null;
  evaluacion_operador: number | null;
}

export interface Decision extends Actor {
  id_caso: string;
  id_recomendacion: string;
  accion: "aprobar" | "editar" | "rechazar";
  texto_editado?: string; // al editar: mín. 5 caracteres
  cambios?: Record<string, ValorCambio>; // al editar: parámetro → nuevo objetivo
  motivo?: string; // obligatorio al editar o rechazar
  responsable?: string;
  fecha_compromiso?: string;
}

export interface NuevaRecomendacion extends Actor {
  nivel_control: NivelControl;
  tipo_cambio: TipoCambio;
  titulo: string;
  texto: string;
  referencia?: string;
  cambios: Record<string, ValorCambio>;
  motivo: string;
  responsable?: string;
  fecha_compromiso?: string;
}

export interface EntradaBitacora {
  secuencia: number;
  timestamp: string;
  usuario: string;
  accion: string;
  objetivo: string;
  id_caso: string | null;
  antes?: string;
  despues?: string;
  motivo?: string;
  hash: string;
  hash_anterior: string;
}

export interface ResultadoIntegridad {
  ok: boolean;
  total: number;
  primera_falla: number | null; // secuencia de la primera entrada alterada
  detalle?: string | null; // p. ej. audit_trail de un caso alterado
}
