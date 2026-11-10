// Única puerta al backend. Con VITE_USE_MOCK=true trabaja con datos simulados en memoria.
import type {
  CambioPropuesto, CasoDetalle, CasoResumen, ContextoTarea, Decision, EntradaBitacora, NuevaRecomendacion, Punto,
  Recomendacion, ResultadoIntegridad, Segmento, TipoTarea, Validacion, ValorCambio, Vista,
} from "./types/caso";
import type { Alerta } from "./types/alerta";
import { API_URL, USE_MOCK } from "./lib/config";
import { actorActual } from "./lib/sesion";
import { alertasMock, casosMock, type CasoMock } from "./mocks/data";

type Ok = { ok: true };

// ---------- Backend real ----------

/** Convierte el `detail` de FastAPI o errores de proxy (Nginx) en un mensaje legible y amigable. */
function mensajeError(status: number, cuerpo: string): string {
  try {
    const { detail } = JSON.parse(cuerpo);
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d: { msg?: string }) => (d.msg ?? "").replace(/^Value error, /, "")).join("; ");
    }
  } catch {
    // Si la respuesta es una página de error HTML (ej. Nginx 504 Gateway Time-out o 502 Bad Gateway)
    if (cuerpo.includes("<html") || cuerpo.includes("<!DOCTYPE") || status === 504 || status === 502) {
      if (status === 504) {
        return "Tiempo de espera agotado (504 Gateway Timeout). La inferencia de IA o el servidor está tomando más tiempo del esperado en procesar. Espera un momento y vuelve a intentarlo.";
      }
      if (status === 502) {
        return "El backend no está respondiendo (502 Bad Gateway). Verifica que el contenedor del backend esté en ejecución.";
      }
      return `Error del servidor web (${status}). Por favor intenta de nuevo.`;
    }
  }
  return `Error ${status}${cuerpo ? `: ${cuerpo}` : ""}`;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new Error(`No se pudo conectar con el backend (${API_URL || "servidor local"}). ¿Está en ejecución?`);
  }
  if (!res.ok) throw new Error(mensajeError(res.status, await res.text()));
  return res.json() as Promise<T>;
}

const seg = encodeURIComponent;
const enviar = (method: string, cuerpo: object): RequestInit => ({ method, body: JSON.stringify(cuerpo) });
const rutaRec = (idCaso: string, idRec: string) => `/casos/${seg(idCaso)}/recomendaciones/${seg(idRec)}`;

/** Parámetro que una recomendación puede modificar (catálogo del backend). */
export type ParametroCatalogo = Omit<CambioPropuesto, "actual" | "objetivo">;

export interface DatosNuevoCaso {
  estacion: string;
  tipo_tarea: TipoTarea;
  contexto: ContextoTarea;
}
export type FotosNuevoCaso = Partial<Record<Vista, File>> & { lateral: File };

export interface ResumenAnguloRapido {
  grados: number;
  puntaje_reba: number;
}

export interface AnalisisRapidoResponse {
  ok: boolean;
  reba_score: number;
  nivel_riesgo: string;
  accion_recomendada: string;
  angulos: Record<string, ResumenAnguloRapido>;
  imagen_anotada_b64: string;
}

const real = {
  estadoVision: () => http<{ disponible: boolean; detalle: string }>("/vision/estado"),
  /** Analiza una fotografía al instante con YOLOX + RTMPose y calcula el REBA Score. */
  analizarRapido: async (foto: File, tipoTarea = "levantamiento", cargaKg = 0): Promise<AnalisisRapidoResponse> => {
    const form = new FormData();
    form.append("foto", foto);
    form.append("tipo_tarea", tipoTarea);
    form.append("carga_kg", cargaKg.toString());
    let res: Response;
    try {
      res = await fetch(`${API_URL}/vision/analizar-rapido`, { method: "POST", body: form });
    } catch {
      throw new Error(`No se pudo conectar con el backend en ${API_URL}. ¿Está en ejecución?`);
    }
    if (!res.ok) throw new Error(mensajeError(res.status, await res.text()));
    return res.json() as Promise<AnalisisRapidoResponse>;
  },
  /** Sube las fotos; el backend detecta la pose, calcula REBA y propone recomendaciones. */
  crearCaso: async (datos: DatosNuevoCaso, fotos: FotosNuevoCaso) => {
    const form = new FormData();
    form.append("datos", JSON.stringify({ ...datos, ...actorActual() }));
    for (const [vista, archivo] of Object.entries(fotos)) if (archivo) form.append(vista, archivo);
    let res: Response;
    try {
      // Sin Content-Type: el navegador pone multipart/form-data con su boundary.
      res = await fetch(`${API_URL}/casos`, { method: "POST", body: form });
    } catch {
      throw new Error(`No se pudo conectar con el backend en ${API_URL}. ¿Está en ejecución?`);
    }
    if (!res.ok) throw new Error(mensajeError(res.status, await res.text()));
    return res.json() as Promise<{ ok: true; id: string }>;
  },
  catalogoParametros: () => http<ParametroCatalogo[]>("/catalogo/parametros"),
  listarCasos: () => http<CasoResumen[]>("/casos"),
  obtenerCaso: (id: string) => http<CasoDetalle>(`/casos/${seg(id)}`),
  corregirPuntos: (id: string, vista: Vista, puntos: Punto[]) =>
    http<CasoDetalle>(`/casos/${seg(id)}/puntos/${vista}`, enviar("PUT", { puntos, ...actorActual() })),
  confirmarAngulo: (id: string, vista: Vista, segmento: Segmento) =>
    http<CasoDetalle>(`/casos/${seg(id)}/angulos/${vista}/${segmento}/confirmar`, enviar("POST", actorActual())),
  corregirContexto: (id: string, contexto: ContextoTarea, motivo: string) =>
    http<CasoDetalle>(`/casos/${seg(id)}/contexto`, enviar("PUT", { contexto, motivo, ...actorActual() })),
  revisarHallazgo: (id: string, idHallazgo: string, accion: "descartar" | "restaurar", motivo: string) =>
    http<CasoDetalle>(`/casos/${seg(id)}/hallazgos/${seg(idHallazgo)}/revision`,
      enviar("POST", { accion, motivo, ...actorActual() })),
  decidir: (d: Decision) => http<Ok>(`${rutaRec(d.id_caso, d.id_recomendacion)}/decision`, enviar("POST", d)),
  autorizar: (idCaso: string, idRec: string, accion: "autorizar" | "denegar", motivo?: string) =>
    http<Ok>(`${rutaRec(idCaso, idRec)}/autorizacion`, enviar("POST", { accion, motivo, ...actorActual() })),
  implementar: (idCaso: string, idRec: string, nota?: string) =>
    http<Ok>(`${rutaRec(idCaso, idRec)}/implementacion`, enviar("POST", { nota, ...actorActual() })),
  crearRecomendacion: (idCaso: string, n: NuevaRecomendacion) =>
    http<{ ok: true; id: string }>(`/casos/${seg(idCaso)}/recomendaciones`, enviar("POST", n)),
  generarPlanErgoAI: (idCaso: string) =>
    http<CasoDetalle>(`/casos/${seg(idCaso)}/generar-plan-ia`, enviar("POST", actorActual())),
  listarAlertas: () => http<Alerta[]>("/alertas"),
  atenderAlerta: (id: string) => http<Ok>(`/alertas/${seg(id)}/atender`, enviar("POST", actorActual())),
  bitacora: (idCaso?: string) =>
    http<EntradaBitacora[]>(idCaso ? `/bitacora?id_caso=${seg(idCaso)}` : "/bitacora"),
  verificarIntegridad: () => http<ResultadoIntegridad>("/bitacora/verificar"),
  descargarExcel: async (idCaso: string) => {
    let res: Response;
    try {
      res = await fetch(`${API_URL}/casos/${seg(idCaso)}/exportar/excel`);
    } catch {
      throw new Error(`No se pudo conectar con el backend (${API_URL}). ¿Está en ejecución?`);
    }
    if (!res.ok) throw new Error(mensajeError(res.status, await res.text()));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Informe_Ergonomico_${idCaso}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
  descargarPdf: async (idCaso: string) => {
    let res: Response;
    try {
      res = await fetch(`${API_URL}/casos/${seg(idCaso)}/exportar/pdf`);
    } catch {
      throw new Error(`No se pudo conectar con el backend (${API_URL}). ¿Está en ejecución?`);
    }
    if (!res.ok) throw new Error(mensajeError(res.status, await res.text()));
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Informe_Ergonomico_${idCaso}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

// ---------- Simulación en memoria (no recalcula REBA; eso solo lo hace el backend) ----------

const store = {
  casos: structuredClone(casosMock),
  alertas: structuredClone(alertasMock),
  bitacora: [] as EntradaBitacora[],
};

const copia = <T,>(x: T): Promise<T> =>
  new Promise(resolve => setTimeout(() => resolve(structuredClone(x)), 150));

const falla = (mensaje: string) => new Promise<never>((_, reject) => setTimeout(() => reject(new Error(mensaje)), 150));

// Hash simple solo para la simulación. El backend real usa SHA-256.
function hashSimulado(texto: string): string {
  let h = 5381;
  for (let i = 0; i < texto.length; i++) h = ((h << 5) + h + texto.charCodeAt(i)) >>> 0;
  return h.toString(16).padStart(8, "0");
}

function contenidoEntrada(e: Omit<EntradaBitacora, "hash">): string {
  return [e.secuencia, e.timestamp, e.usuario, e.accion, e.objetivo, e.id_caso, e.antes, e.despues, e.motivo, e.hash_anterior].join("|");
}

function registrar(datos: Omit<EntradaBitacora, "secuencia" | "timestamp" | "hash" | "hash_anterior">) {
  const anterior = store.bitacora[store.bitacora.length - 1];
  const base = {
    ...datos,
    secuencia: store.bitacora.length + 1,
    timestamp: new Date().toISOString(),
    hash_anterior: anterior?.hash ?? "00000000",
  };
  store.bitacora.push({ ...base, hash: hashSimulado(contenidoEntrada(base)) });
}

for (const c of store.casos) {
  registrar({ usuario: "sistema", accion: "caso_creado", objetivo: c.id_caso, id_caso: c.id_caso });
  registrar({ usuario: "sistema", accion: "analisis_ejecutado", objetivo: c.id_caso, id_caso: c.id_caso, despues: `REBA ${c.reba?.final ?? "—"}` });
}

/** Misma regla que el backend (ServicioCasos._validacion). */
function validacion(c: CasoMock): Validacion {
  const recs = c.recomendaciones;
  const pendientes = recs.filter(r => r.estado === "propuesta").length;
  const riesgoAlto = c.reba?.nivel === "alto" || c.reba?.nivel === "muy_alto";
  const ingenieria = recs.some(r =>
    r.nivel_control === "ingenieria" && (r.estado === "aprobada" || r.estado === "editada_aprobada")
    && r.implementacion !== "denegada");
  const falta_ingenieria = riesgoAlto && !ingenieria;
  const por_autorizar = recs.filter(r => r.implementacion === "pendiente_autorizacion").length;
  const por_implementar = recs.filter(r => r.implementacion === "por_implementar").length;
  const implementadas = recs.filter(r => r.implementacion === "implementada").length;
  const aprobadas = recs.filter(r => (r.estado === "aprobada" || r.estado === "editada_aprobada") && r.implementacion !== "denegada").length;

  const aprobado_e_implementado = (
    pendientes === 0
    && !falta_ingenieria
    && por_autorizar === 0
    && por_implementar === 0
    && (implementadas > 0 || aprobadas === 0)
  );

  return {
    pendientes, falta_ingenieria, completa: pendientes === 0 && !falta_ingenieria,
    por_autorizar,
    por_implementar,
    implementadas,
    aprobado_e_implementado,
  };
}

const detalle = (c: CasoMock): CasoDetalle => ({ ...c, validacion: validacion(c) });

function resumen(c: CasoMock): CasoResumen {
  const v = validacion(c);
  return {
    id_caso: c.id_caso, estacion: c.estacion, tipo_tarea: c.tipo_tarea, fecha: c.fecha,
    reba_final: c.reba?.final ?? null, nivel: c.reba?.nivel ?? null,
    decisiones_pendientes: v.pendientes, por_autorizar: v.por_autorizar,
  };
}

const buscarCaso = (id: string) => store.casos.find(x => x.id_caso === id);
const buscarRec = (c: CasoMock, id: string) => c.recomendaciones.find(x => x.id === id);
const rolEs = (rol: string) => actorActual().rol === rol;

const mock: typeof real = {
  estadoVision: () => copia({ disponible: false, detalle: "Modo simulado: la visión artificial requiere el backend real." }),
  analizarRapido: () =>
    copia<AnalisisRapidoResponse>({
      ok: true,
      reba_score: 4,
      nivel_riesgo: "MEDIO",
      accion_recomendada: "Es necesaria la actuación e intervención ergonómica para reducir posturas forzadas.",
      angulos: {
        tronco: { grados: 22.5, puntaje_reba: 2 },
        cuello: { grados: 15.0, puntaje_reba: 1 },
        brazo: { grados: 48.0, puntaje_reba: 3 },
        antebrazo: { grados: 85.0, puntaje_reba: 1 },
        muneca: { grados: 18.0, puntaje_reba: 2 },
        pierna: { grados: 10.0, puntaje_reba: 1 },
      },
      imagen_anotada_b64: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='300'><rect width='400' height='300' fill='%23163E6A'/><text x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' fill='white' font-family='sans-serif'>Simulacion Captura ErgoAI</text></svg>",
    }),
  crearCaso: () => falla("Crear casos desde fotos requiere el backend real (npm run dev, sin modo simulado)."),
  catalogoParametros: () => copia<ParametroCatalogo[]>([
    { parametro: "angulo.tronco", etiqueta: "Ángulo de tronco", tipo: "numero", unidad: "°", minimo: -90, maximo: 180, opciones: [] },
    { parametro: "angulo.cuello", etiqueta: "Ángulo de cuello", tipo: "numero", unidad: "°", minimo: -90, maximo: 180, opciones: [] },
    { parametro: "angulo.brazo", etiqueta: "Ángulo de brazo", tipo: "numero", unidad: "°", minimo: -90, maximo: 180, opciones: [] },
    { parametro: "carga_kg", etiqueta: "Carga manipulada", tipo: "numero", unidad: "kg", minimo: 0, maximo: 200, opciones: [] },
    { parametro: "agarre", etiqueta: "Calidad del agarre", tipo: "opcion", opciones: ["bueno", "regular", "malo", "inaceptable"] },
  ]),
  listarCasos: () => copia(store.casos.map(resumen)),

  obtenerCaso: id => {
    const c = buscarCaso(id);
    return c ? copia(detalle(c)) : falla(`Caso ${id} no encontrado`);
  },

  corregirPuntos: (id, vista, puntos) => {
    const c = buscarCaso(id);
    if (!c) return falla(`Caso ${id} no encontrado`);
    if (!rolEs("ergonomia")) return falla("Solo Ergonomía puede corregir el esqueleto");
    const img = c.imagenes.find(i => i.vista === vista);
    if (img) img.puntos = puntos;
    registrar({
      usuario: actorActual().usuario, accion: "puntos_corregidos", objetivo: `${id} / ${vista}`, id_caso: id,
      despues: `${puntos.filter(p => p.corregido).length} puntos corregidos`,
    });
    return copia(detalle(c));
  },

  confirmarAngulo: (id, vista, segmento) => {
    const c = buscarCaso(id);
    if (!c) return falla(`Caso ${id} no encontrado`);
    if (!rolEs("ergonomia")) return falla("Solo Ergonomía puede confirmar ángulos");
    const a = c.angulos.find(x => x.vista === vista && x.segmento === segmento);
    if (a) {
      a.estado = "ok";
      a.confirmado = true;
      a.motivo_estado = "Confirmado por especialista";
    }
    registrar({
      usuario: actorActual().usuario, accion: "angulo_confirmado", objetivo: `${id} / ${vista} / ${segmento}`, id_caso: id,
    });
    return copia(detalle(c));
  },

  corregirContexto: (id, contexto, motivo) => {
    const c = buscarCaso(id);
    if (!c) return falla(`Caso ${id} no encontrado`);
    if (!rolEs("ergonomia")) return falla("Solo Ergonomía puede corregir los datos de la tarea");
    c.contexto = contexto;
    registrar({ usuario: actorActual().usuario, accion: "contexto_corregido", objetivo: `${id} / datos de la tarea`, id_caso: id, motivo });
    return copia(detalle(c));
  },

  revisarHallazgo: (id, idHallazgo, accion, motivo) => {
    const c = buscarCaso(id);
    const h = c?.hallazgos.find(x => x.id === idHallazgo);
    if (!c || !h) return falla(`Hallazgo ${idHallazgo} no encontrado`);
    if (!rolEs("ergonomia")) return falla("Solo Ergonomía puede descartar o restaurar hallazgos");
    h.descartado = accion === "descartar"
      ? { motivo, usuario: actorActual().usuario, timestamp: new Date().toISOString() } : null;
    registrar({ usuario: actorActual().usuario, accion: `hallazgo_${accion === "descartar" ? "descartado" : "restaurado"}`, objetivo: `${id} / ${idHallazgo}`, id_caso: id, motivo });
    return copia(detalle(c));
  },

  decidir: d => {
    const c = buscarCaso(d.id_caso);
    const r = c && buscarRec(c, d.id_recomendacion);
    if (!c || !r) return falla(`Recomendación ${d.id_recomendacion} no encontrada`);
    if (d.rol !== "ergonomia") return falla("Solo Ergonomía puede aprobar, editar o rechazar recomendaciones");
    if (r.estado !== "propuesta") return falla(`La recomendación ${r.id} ya fue decidida (${r.estado})`);
    if (d.accion !== "aprobar" && !d.motivo?.trim()) return falla("Editar o rechazar requiere una justificación (motivo)");
    const antes = `${r.estado}: ${r.texto}`;
    if (d.accion === "rechazar") {
      r.estado = "rechazada";
      r.implementacion = null;
    } else {
      if (d.accion === "editar") {
        if (d.texto_editado !== undefined) r.texto = d.texto_editado.trim();
        for (const cambio of r.cambios) {
          if (d.cambios && cambio.parametro in d.cambios) cambio.objetivo = d.cambios[cambio.parametro];
        }
      }
      r.estado = d.accion === "editar" ? "editada_aprobada" : "aprobada";
      r.implementacion = r.tipo_cambio === "planta" ? "pendiente_autorizacion" : "por_implementar";
      r.aprobado_por = d.usuario;
      r.responsable = d.responsable;
      r.fecha_compromiso = d.fecha_compromiso;
    }
    registrar({
      usuario: d.usuario, accion: `recomendacion_${d.accion}`, objetivo: `${d.id_caso} / ${r.id}`, id_caso: d.id_caso,
      antes, despues: `${r.estado}: ${r.texto}`, motivo: d.motivo,
    });
    return copia({ ok: true as const });
  },

  autorizar: (idCaso, idRec, accion, motivo) => {
    const c = buscarCaso(idCaso);
    const r = c && buscarRec(c, idRec);
    const actor = actorActual();
    if (!r) return falla(`Recomendación ${idRec} no encontrada`);
    if (actor.rol !== "ingenieria") return falla("Solo Ingeniería (IE/Facilities) puede autorizar cambios en planta");
    if (r.implementacion !== "pendiente_autorizacion") return falla("La recomendación no está esperando autorización");
    if (accion === "denegar" && !motivo?.trim()) return falla("Denegar requiere una justificación (motivo)");
    r.implementacion = accion === "autorizar" ? "por_implementar" : "denegada";
    r.autorizado_por = actor.usuario;
    r.nota_autorizacion = motivo;
    registrar({ usuario: actor.usuario, accion: `cambio_planta_${accion === "autorizar" ? "autorizado" : "denegado"}`, objetivo: `${idCaso} / ${idRec}`, id_caso: idCaso, motivo });
    return copia({ ok: true as const });
  },

  implementar: (idCaso, idRec, nota) => {
    const c = buscarCaso(idCaso);
    const r = c && buscarRec(c, idRec);
    const actor = actorActual();
    if (!r) return falla(`Recomendación ${idRec} no encontrada`);
    if (actor.rol !== "ergonomia") return falla("Solo Ergonomía puede confirmar la implementación");
    if (r.implementacion !== "por_implementar") return falla("La recomendación no está lista para implementarse");
    r.implementacion = "implementada";
    r.implementado_por = actor.usuario;
    r.nota_implementacion = nota;
    registrar({ usuario: actor.usuario, accion: "recomendacion_implementada", objetivo: `${idCaso} / ${idRec}`, id_caso: idCaso, motivo: nota });
    return copia({ ok: true as const });
  },

  crearRecomendacion: (idCaso, n) => {
    const c = buscarCaso(idCaso);
    if (!c) return falla(`Caso ${idCaso} no encontrado`);
    if (n.rol !== "ergonomia") return falla("Solo Ergonomía puede crear recomendaciones");
    let i = 1;
    while (buscarRec(c, `E${i}`)) i++;
    const cambios: CambioPropuesto[] = Object.entries(n.cambios).map(([parametro, objetivo]: [string, ValorCambio]) => ({
      parametro, etiqueta: parametro, tipo: typeof objetivo === "boolean" ? "booleano" : typeof objetivo === "number" ? "numero" : "opcion",
      actual: null, objetivo, opciones: [],
    }));
    const rec: Recomendacion = {
      id: `E${i}`, nivel_control: n.nivel_control, tipo_cambio: n.tipo_cambio, titulo: n.titulo, texto: n.texto,
      referencia: n.referencia ?? "Criterio del especialista", origen: "especialista", estado: "aprobada",
      implementacion: n.tipo_cambio === "planta" ? "pendiente_autorizacion" : "por_implementar",
      aprobado_por: n.usuario, responsable: n.responsable, fecha_compromiso: n.fecha_compromiso,
      cambios, reba_proyectado: null, requiere_autorizacion: n.tipo_cambio === "planta",
    };
    c.recomendaciones.push(rec);
    registrar({ usuario: n.usuario, accion: "recomendacion_creada", objetivo: `${idCaso} / ${rec.id}`, id_caso: idCaso, despues: rec.titulo, motivo: n.motivo });
    return copia({ ok: true as const, id: rec.id });
  },

  generarPlanErgoAI: idCaso => {
    const c = buscarCaso(idCaso);
    if (!c) return falla(`Caso ${idCaso} no encontrado`);
    c.recomendaciones = c.recomendaciones.filter(r => !r.id.startsWith("AI"));
    const r = c.recomendaciones.find(x => x.estado === "propuesta") ?? c.recomendaciones[0];
    if (r) {
      r.justificacion_rag = "[16-PE30-6500-00023 / NOM-036-1-STPS-2018]: Fundamentación normativa validada en memoria RAM sobre los ángulos medidos.";
      registrar({ usuario: actorActual().usuario, accion: "plan_ia_generado", objetivo: `${idCaso} / ${r.id}`, id_caso: idCaso, despues: r.titulo });
    }
    return copia(detalle(c));
  },

  listarAlertas: () => copia(store.alertas),

  atenderAlerta: id => {
    const a = store.alertas.find(x => x.id_alerta === id);
    if (!a) return falla(`Alerta ${id} no encontrada`);
    if (a.estado !== "atendida") {
      a.estado = "atendida";
      registrar({ usuario: actorActual().usuario, accion: "alerta_atendida", objetivo: id, id_caso: a.id_caso });
    }
    return copia({ ok: true as const });
  },

  bitacora: idCaso => copia(store.bitacora.filter(e => !idCaso || e.id_caso === idCaso)),

  verificarIntegridad: () => {
    let anterior = "00000000";
    for (const e of store.bitacora) {
      const { hash, ...resto } = e;
      if (e.hash_anterior !== anterior || hashSimulado(contenidoEntrada(resto)) !== hash) {
        return copia({ ok: false, total: store.bitacora.length, primera_falla: e.secuencia });
      }
      anterior = hash;
    }
    return copia({ ok: true, total: store.bitacora.length, primera_falla: null });
  },

  descargarExcel: async (idCaso: string) => {
    const blob = new Blob([`Informe Simulador ErgoAI - Caso ${idCaso}`], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Informe_Ergonomico_${idCaso}_simulado.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  descargarPdf: async (idCaso: string) => {
    const blob = new Blob([`Informe PDF Simulador ErgoAI - Caso ${idCaso}`], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Informe_Ergonomico_${idCaso}_simulado.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};

export const api = USE_MOCK ? mock : real;

/** URL de una imagen: las del backend vienen relativas (/media/...). */
export function urlImagen(url: string): string {
  if (USE_MOCK || /^https?:\/\//.test(url)) return url;
  return `${API_URL}${url}`;
}
