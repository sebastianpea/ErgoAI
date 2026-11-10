import { useEffect, useRef, useState } from "react";
import { api, type AnalisisRapidoResponse } from "../api";
import type { NivelReba, TipoTarea, Vista } from "../types/caso";
import { COLOR_SEMAFORO, ETIQUETA_TAREA, NIVEL_REBA } from "../lib/niveles";

function obtenerColorRiesgo(nivel: string): string {
  const clave = nivel.toLowerCase() as NivelReba;
  const config = NIVEL_REBA[clave];
  return config ? COLOR_SEMAFORO[config.color] : "#163E6A";
}

interface Props {
  vistaObjetivo?: Vista;
  modo?: "captura_simple" | "diagnostico_rapido";
  alCapturarFoto?: (archivo: File, vista: Vista) => void;
  alCerrar: () => void;
}

export function CapturaCamaraModal({
  vistaObjetivo = "lateral",
  modo = "diagnostico_rapido",
  alCapturarFoto,
  alCerrar,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [dispositivos, setDispositivos] = useState<MediaDeviceInfo[]>([]);
  const [deviceIdSeleccionado, setDeviceIdSeleccionado] = useState<string>("");
  const [errorCamara, setErrorCamara] = useState<string | null>(null);
  const [iniciandoCamara, setIniciandoCamara] = useState<boolean>(true);

  // Parámetros para análisis rápido
  const [tipoTarea, setTipoTarea] = useState<TipoTarea>("levantamiento");
  const [cargaKg, setCargaKg] = useState<number>(5.0);

  // Estados de captura y análisis
  const [fotoCapturada, setFotoCapturada] = useState<File | null>(null);
  const [fotoUrl, setFotoUrl] = useState<string | null>(null);
  const [analizando, setAnalizando] = useState<boolean>(false);
  const [resultado, setResultado] = useState<AnalisisRapidoResponse | null>(null);

  // Detener cámara limpiando tracks del sistema operativo (V4L2 en Linux, DirectShow en Windows)
  const detenerCamara = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  // Inicializar o cambiar de dispositivo de video
  const iniciarCamara = async (deviceId?: string) => {
    detenerCamara();
    setIniciandoCamara(true);
    setErrorCamara(null);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("El navegador actual no soporta acceso a la cámara mediante WebRTC (getUserMedia).");
      }

      const constraints: MediaStreamConstraints = {
        video: deviceId
          ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
          : { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Enumerar cámaras conectadas (Windows / Linux)
      const todosDispositivos = await navigator.mediaDevices.enumerateDevices();
      const camaras = todosDispositivos.filter(d => d.kind === "videoinput");
      setDispositivos(camaras);

      // Si no hay deviceId seleccionado, tomar el que está activo
      const trackActivo = stream.getVideoTracks()[0];
      const settings = trackActivo?.getSettings();
      if (settings?.deviceId) {
        setDeviceIdSeleccionado(settings.deviceId);
      } else if (camaras.length > 0 && !deviceId) {
        setDeviceIdSeleccionado(camaras[0].deviceId);
      }
    } catch (err: unknown) {
      const mensaje = err instanceof Error ? err.message : String(err);
      console.error("Error al iniciar cámara:", err);
      if (mensaje.includes("NotAllowedError") || mensaje.includes("Permission denied")) {
        setErrorCamara("Permiso de cámara denegado. Permite el acceso a la cámara en tu navegador.");
      } else if (mensaje.includes("NotFoundError") || mensaje.includes("DevicesNotFoundError")) {
        setErrorCamara("No se detectó ninguna cámara conectada en tu equipo (Windows/Linux).");
      } else {
        setErrorCamara(`No se pudo inicializar la cámara: ${mensaje}`);
      }
    } finally {
      setIniciandoCamara(false);
    }
  };

  useEffect(() => {
    iniciarCamara();
    return () => {
      detenerCamara();
      if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    };
  }, []);

  // Cambiar dispositivo seleccionado
  const handleCambiarDispositivo = (id: string) => {
    setDeviceIdSeleccionado(id);
    iniciarCamara(id);
  };

  // Capturar fotograma actual a Blob y File
  const capturarFotograma = (): Promise<File | null> => {
    return new Promise(resolve => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
        resolve(null);
        return;
      }

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(null);
        return;
      }

      // Dibujar fotograma
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(blob => {
        if (!blob) {
          resolve(null);
          return;
        }
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
        const nombre = `captura_${vistaObjetivo}_${timestamp}.jpg`;
        const archivo = new File([blob], nombre, { type: "image/jpeg" });
        resolve(archivo);
      }, "image/jpeg", 0.95);
    });
  };

  // Acción: Capturar foto para el formulario
  const handleCapturarParaFormulario = async () => {
    const archivo = await capturarFotograma();
    if (!archivo) return;
    detenerCamara();
    alCapturarFoto?.(archivo, vistaObjetivo);
    alCerrar();
  };

  // Acción: Capturar y diagnosticar en vivo
  const handleCapturarYDiagnosticar = async () => {
    const archivo = await capturarFotograma();
    if (!archivo) return;

    const url = URL.createObjectURL(archivo);
    setFotoCapturada(archivo);
    setFotoUrl(url);
    setAnalizando(true);
    setErrorCamara(null);

    try {
      const res = await api.analizarRapido(archivo, tipoTarea, cargaKg);
      setResultado(res);
      // Pausar o apagar cámara para ahorrar recursos mientras ve el reporte
      detenerCamara();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorCamara(`Error durante el análisis biomecánico: ${msg}`);
    } finally {
      setAnalizando(false);
    }
  };

  // Reanudar cámara para repetir captura
  const handleRepetirFoto = () => {
    setResultado(null);
    setFotoCapturada(null);
    if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    setFotoUrl(null);
    iniciarCamara(deviceIdSeleccionado);
  };

  // Usar la foto analizada para el nuevo caso
  const handleUsarEnNuevoCaso = () => {
    if (fotoCapturada) {
      alCapturarFoto?.(fotoCapturada, vistaObjetivo);
      alCerrar();
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="titulo-modal-camara">
      <div className="modal-contenido modal-camara-caja">
        <div className="modal-cabecera">
          <div>
            <span className="eyebrow">
              {modo === "diagnostico_rapido" ? "Visión en tiempo real · REBA Instantáneo" : `Captura de cámara · Vista ${vistaObjetivo}`}
            </span>
            <h2 id="titulo-modal-camara">
              {modo === "diagnostico_rapido" ? "Diagnóstico Ergonómico con Cámara" : `Tomar Fotografía (${vistaObjetivo})`}
            </h2>
          </div>
          <button type="button" className="boton-cerrar-modal" onClick={() => { detenerCamara(); alCerrar(); }} aria-label="Cerrar modal">
            ✕
          </button>
        </div>

        {errorCamara && (
          <div className="aviso error mb-4">
            {errorCamara}
          </div>
        )}

        {/* SI ESTAMOS EN MODO DE CAPTURA EN VIVO (SIN RESULTADO AÚN) */}
        {!resultado && (
          <div className="camara-contenedor">
            <div className="camara-viewfinder-wrapper">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className={`camara-video ${iniciandoCamara ? "cargando" : ""}`}
              />

              {/* Guía ergonómica superpuesta en el visor */}
              <div className="camara-guia-overlay" aria-hidden>
                <div className="guia-linea-centro" />
                <div className="guia-indicador-cabeza" />
                <div className="guia-indicador-tronco" />
                <div className="guia-texto-ayuda">
                  {vistaObjetivo === "lateral" || modo === "diagnostico_rapido"
                    ? "Alinea el operador de perfil de cuerpo completo"
                    : `Encuadre recomendado para vista ${vistaObjetivo}`}
                </div>
              </div>

              {iniciandoCamara && (
                <div className="camara-cargando-overlay">
                  <div className="spinner" />
                  <p>Iniciando sensor de cámara...</p>
                </div>
              )}

              {analizando && (
                <div className="camara-cargando-overlay">
                  <div className="spinner" />
                  <p>Detectando postura con RTMPose WholeBody y calculando REBA...</p>
                </div>
              )}
            </div>

            {/* Controles de cámara */}
            <div className="camara-barra-controles">
              <div className="selector-dispositivo">
                <label htmlFor="select-camara">Cámara:</label>
                <select
                  id="select-camara"
                  value={deviceIdSeleccionado}
                  onChange={e => handleCambiarDispositivo(e.target.value)}
                  disabled={iniciandoCamara || analizando || dispositivos.length === 0}
                >
                  {dispositivos.length === 0 && <option value="">Cámara por defecto</option>}
                  {dispositivos.map((d, i) => (
                    <option key={d.deviceId || i} value={d.deviceId}>
                      {d.label || `Cámara ${i + 1}`}
                    </option>
                  ))}
                </select>
              </div>

              {modo === "diagnostico_rapido" && (
                <div className="parametros-rapidos">
                  <label>
                    Tarea:
                    <select
                      value={tipoTarea}
                      onChange={e => setTipoTarea(e.target.value as TipoTarea)}
                      disabled={analizando}
                    >
                      {(Object.keys(ETIQUETA_TAREA) as TipoTarea[]).map(t => (
                        <option key={t} value={t}>{ETIQUETA_TAREA[t]}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Carga:
                    <input
                      type="number"
                      min="0"
                      max="100"
                      step="0.5"
                      value={cargaKg}
                      onChange={e => setCargaKg(parseFloat(e.target.value) || 0)}
                      disabled={analizando}
                      style={{ width: "70px" }}
                    />
                    kg
                  </label>
                </div>
              )}
            </div>

            <div className="camara-acciones-pie">
              <button
                type="button"
                className="boton"
                onClick={() => { detenerCamara(); alCerrar(); }}
                disabled={analizando}
              >
                Cancelar
              </button>

              {modo === "captura_simple" ? (
                <button
                  type="button"
                  className="boton primario boton-capturar"
                  onClick={handleCapturarParaFormulario}
                  disabled={iniciandoCamara || analizando || !!errorCamara}
                >
                  📸 Capturar Fotografía
                </button>
              ) : (
                <button
                  type="button"
                  className="boton primario boton-capturar"
                  onClick={handleCapturarYDiagnosticar}
                  disabled={iniciandoCamara || analizando || !!errorCamara}
                >
                  ⚡ Capturar y Analizar REBA
                </button>
              )}
            </div>
          </div>
        )}

        {/* SI YA TENEMOS EL RESULTADO DEL ANÁLISIS RÁPIDO */}
        {resultado && (
          <div className="resultado-analisis-rapido">
            <div className="resultado-grid">
              {/* Imagen con anotaciones de la IA */}
              <div className="resultado-visual">
                <h3>Esqueleto Biomecánico y Ángulos</h3>
                <div className="imagen-anotada-caja">
                  <img
                    src={resultado.imagen_anotada_b64}
                    alt="Esqueleto Biomecánico anotado por ErgoAI"
                  />
                </div>
                <p className="sutil mt-2">
                  Keypoints detectados mediante WholeBody-133 con corrección biomecánica.
                </p>
              </div>

              {/* Tarjeta de Métricas REBA */}
              <div className="resultado-metricas">
                <div
                  className="tarjeta-reba-resumen"
                  style={{
                    borderLeftColor: obtenerColorRiesgo(resultado.nivel_riesgo),
                  }}
                >
                  <div className="reba-puntuacion-grande">
                    <span className="puntos">{resultado.reba_score}</span>
                    <span className="etiqueta-reba">PUNTAJE REBA</span>
                  </div>
                  <div className="reba-info-riesgo">
                    <span
                      className="insignia-riesgo"
                      style={{
                        backgroundColor: obtenerColorRiesgo(resultado.nivel_riesgo),
                        color: "#fff",
                      }}
                    >
                      {resultado.nivel_riesgo.toUpperCase()}
                    </span>
                    <p className="reba-accion-texto">{resultado.accion_recomendada}</p>
                  </div>
                </div>

                <h3>Desglose de Ángulos Calculados</h3>
                <div className="tabla-angulos-rapida">
                  <table>
                    <thead>
                      <tr>
                        <th>Segmento</th>
                        <th>Ángulo Medido</th>
                        <th>Pts REBA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(resultado.angulos).map(([seg, ang]) => (
                        <tr key={seg}>
                          <td className="nombre-segmento">{seg.toUpperCase()}</td>
                          <td className="valor-angulo">{ang.grados}°</td>
                          <td className="puntos-reba">+{ang.puntaje_reba}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="resultado-botones-acciones">
                  <button
                    type="button"
                    className="boton"
                    onClick={handleRepetirFoto}
                  >
                    🔄 Tomar otra foto
                  </button>
                  {alCapturarFoto && (
                    <button
                      type="button"
                      className="boton primario"
                      onClick={handleUsarEnNuevoCaso}
                    >
                      ✓ Usar esta foto para Crear Caso
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
