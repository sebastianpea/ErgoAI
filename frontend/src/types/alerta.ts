// Contrato de alertas (basado en el contrato original del equipo).

export type TipoEvento =
  | "RIESGO_ALTO_PENDIENTE" // caso alto o muy alto sin validar
  | "DISCREPANCIA_EVALUACION" // lo capturado en piso no coincide con la foto
  | "ANGULO_POR_REVISAR" // ángulo cerca de un límite REBA o baja confianza
  | "OBJETO_DESCONOCIDO" // detectado en la foto cenital
  | "AUTORIZACION_PENDIENTE" // cambio en planta esperando a ingeniería
  | "EMERGENCIA_CAIDA"; // fase 2: solo para la maqueta del pitch

export type NivelUrgencia = "BAJO" | "MEDIO" | "ALTO" | "CRITICO";

export interface Alerta {
  id_alerta: string;
  id_operario: string | null;
  estacion: string;
  tipo_evento: TipoEvento;
  nivel_urgencia: NivelUrgencia;
  detalles: string;
  timestamp: string; // ISO con zona horaria
  id_caso: string | null;
  estado: "nueva" | "vista" | "atendida";
}