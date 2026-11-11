import { useEffect, useRef, useState } from "react";
import { api, type AnalisisRapidoResponse } from "../api";
import type { NivelReba, Vista } from "../types/caso";
import { COLOR_SEMAFORO, NIVEL_REBA } from "../lib/niveles";

interface Props {
  vistaObjetivo?: Vista;
  modo?: "captura_simple" | "diagnostico_rapido";
  alCapturarFoto?: (archivo: File, vista: Vista) => void;
  alCerrar: () => void;
}

function obtenerColorRiesgo(nivel: string): string {
  const clave = nivel.toLowerCase() as NivelReba;
  const config = NIVEL_REBA[clave];
  return config ? COLOR_SEMAFORO[config.color] : "#163E6A";
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

  // Estados de captura y análisis
  const [fotoCapturada, setFotoCapturada] = useState<File | null>(null);
  const [fotoUrl, setFotoUrl] = useState<string | null>(null);
  const [analizando, setAnalizando] = useState<boolean>(false);
  const [resultado, setResultado] = useState<AnalisisRapidoResponse | null>(null);

  // Detener cámara liberando hardware en Windows (DirectShow) y Linux (V4L2)
  const detenerCamara = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

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

      const todosDispositivos = await navigator.mediaDevices.enumerateDevices();
      const camaras = todosDispositivos.filter(d => d.kind === "videoinput");
      setDispositivos(camaras);

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
        setErrorCamara("Permiso de cámara denegado. Permite el acceso a la cámara en los permisos de tu navegador.");
      } else if (mensaje.includes("NotFoundError") || mensaje.includes("DevicesNotFoundError")) {
        setErrorCamara("No se detectó ninguna cámara conectada en tu equipo (Windows o Linux).");
      } else {
        setErrorCamara(`No se pudo inicializar la cámara web: ${mensaje}`);
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

  const handleCambiarDispositivo = (id: string) => {
    setDeviceIdSeleccionado(id);
    iniciarCamara(id);
  };

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

  const handleCapturarParaFormulario = async () => {
    const archivo = await capturarFotograma();
    if (!archivo) return;
    detenerCamara();
    alCapturarFoto?.(archivo, vistaObjetivo);
    alCerrar();
  };

  const handleCapturarYDiagnosticar = async () => {
    const archivo = await capturarFotograma();
    if (!archivo) return;

    const url = URL.createObjectURL(archivo);
    setFotoCapturada(archivo);
    setFotoUrl(url);
    setAnalizando(true);
    setErrorCamara(null);

    try {
      const res = await api.analizarRapido(archivo);
      setResultado(res);
      detenerCamara();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorCamara(`Error durante el análisis biomecánico: ${msg}`);
    } finally {
      setAnalizando(false);
    }
  };

  const handleRepetirFoto = () => {
    setResultado(null);
    setFotoCapturada(null);
    if (fotoUrl) URL.revokeObjectURL(fotoUrl);
    setFotoUrl(null);
    iniciarCamara(deviceIdSeleccionado);
  };

  const handleUsarEnNuevoCaso = () => {
    if (fotoCapturada) {
      alCapturarFoto?.(fotoCapturada, vistaObjetivo);
      alCerrar();
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="titulo-modal-camara">
      <div className="tarjeta corte modal-camara-caja">
        {/* Cabecera con identidad Jabil */}
        <div className="modal-cabecera">
          <div>
            <p className="eyebrow">
              {modo === "diagnostico_rapido"
                ? "Visión Biomecánica · YOLOX + RTMPose WholeBody-133"
                : `Sensor de Cámara · Vista ${vistaObjetivo}`}
            </p>
            <h2 id="titulo-modal-camara" className="modal-titulo">
              {modo === "diagnostico_rapido"
                ? "Diagnóstico Rápido REBA en Tiempo Real"
                : `Capturar Fotografía de Estación (${vistaObjetivo})`}
            </h2>
          </div>
          <button
            type="button"
            className="boton modal-cerrar-btn"
            onClick={() => { detenerCamara(); alCerrar(); }}
            aria-label="Cerrar modal"
            title="Cerrar visor"
          >
            ✕
          </button>
        </div>

        {errorCamara && (
          <div className="aviso error">
            {errorCamara}
          </div>
        )}

        {/* MODO 1: VISOR DE CÁMARA ACTIVO */}
        {!resultado && (
          <div className="camara-cuerpo">
            <div className="camara-viewfinder-marco">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                className={`camara-video ${iniciandoCamara ? "cargando" : ""}`}
              />

              {/* Retícula de Calibración Ergonómica Industrial */}
              <div className="camara-reticula-guia" aria-hidden>
                <div className="reticula-esquina sup-izq" />
                <div className="reticula-esquina sup-der" />
                <div className="reticula-esquina inf-izq" />
                <div className="reticula-esquina inf-der" />
                <div className="reticula-linea-eje" />
                <div className="reticula-silueta-perfil" />
                <span className="reticula-badge-modo">
                  {vistaObjetivo === "lateral" || modo === "diagnostico_rapido"
                    ? "ALINEACIÓN DE PERFIL REBA · CUERPO COMPLETO"
                    : `ENCUADRE RECOMENDADO · VISTA ${vistaObjetivo.toUpperCase()}`}
                </span>
              </div>

              {iniciandoCamara && (
                <div className="camara-overlay-mensaje">
                  <span className="cargando">Iniciando sensor de video (Windows/Linux)…</span>
                </div>
              )}

              {analizando && (
                <div className="camara-overlay-mensaje">
                  <span className="cargando">Detectando postura con RTMPose WholeBody y calculando REBA…</span>
                </div>
              )}
            </div>

            {/* Controles de Configuración y Dispositivo */}
            <div className="campos camara-barra-parametros">
              <label>
                Dispositivo de Entrada
                <select
                  value={deviceIdSeleccionado}
                  onChange={e => handleCambiarDispositivo(e.target.value)}
                  disabled={iniciandoCamara || analizando || dispositivos.length === 0}
                >
                  {dispositivos.length === 0 && <option value="">Cámara predeterminada del sistema</option>}
                  {dispositivos.map((d, i) => (
                    <option key={d.deviceId || i} value={d.deviceId}>
                      {d.label || `Cámara ${i + 1}`}
                    </option>
                  ))}
                </select>
              </label>

              {modo === "diagnostico_rapido" && (
                <p className="sutil">Esta captura mide postura. La clasificación de tarea y el riesgo requieren datos confirmados en la revisión del caso.</p>
              )}
            </div>

            {/* Acciones del pie del modal */}
            <div className="acciones camara-pie-acciones">
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
                  className="boton primario"
                  onClick={handleCapturarParaFormulario}
                  disabled={iniciandoCamara || analizando || !!errorCamara}
                >
                  Capturar fotografía
                </button>
              ) : (
                <button
                  type="button"
                  className="boton primario"
                  onClick={handleCapturarYDiagnosticar}
                  disabled={iniciandoCamara || analizando || !!errorCamara}
                >
                  Capturar y analizar REBA
                </button>
              )}
            </div>
          </div>
        )}

        {/* MODO 2: RESULTADOS DEL DIAGNÓSTICO RÁPIDO */}
        {resultado && !resultado.ok && (
          <div className="aviso error" role="alert">
            <p>{resultado.advertencia ?? "No se detectó a ninguna persona con suficiente claridad en la toma."}</p>
            <button type="button" className="boton" onClick={handleRepetirFoto}>Tomar otra fotografía</button>
          </div>
        )}
        {resultado?.ok && (
          <div className="resultado-diagnostico-cuerpo">
            <div className="rejilla">
              {/* Esqueleto Anotado por ErgoAI */}
              <div className="tarjeta">
                <h2>Esqueleto y Articulaciones</h2>
                <div className="imagen-anotada-marco">
                  <img
                    src={resultado.imagen_anotada_b64 ?? undefined}
                    alt="Esqueleto Biomecánico anotado por ErgoAI"
                  />
                </div>
                <p className="sutil" style={{ marginTop: "0.5rem" }}>
                  133 keypoints detectados mediante YOLOX + RTMPose con corrección articular determinista.
                </p>
              </div>

              {/* Métricas y Ángulos */}
              <div className="tarjeta">
                <h2>{resultado.risk_ready ? "Dictamen REBA" : "Análisis de postura"}</h2>

                <div className="cifras" style={{ gridTemplateColumns: "1fr", margin: "0 0 1rem" }}>
                  <div className="cifra" style={{ borderLeftColor: obtenerColorRiesgo(resultado.reba_nivel) }}>
                    <span className="cifra-valor">{resultado.reba_final ?? "—"}</span>
                    <span className="cifra-texto">{resultado.risk_ready ? "Puntaje REBA Final" : "Riesgo pendiente de revisión"}</span>
                  </div>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <span
                    className="chip"
                    style={{
                      backgroundColor: obtenerColorRiesgo(resultado.reba_nivel),
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      fontWeight: 700,
                    }}
                  >
                    Nivel de Riesgo: {resultado.reba_nivel}
                  </span>
                </div>

                <p className="sutil" style={{ lineHeight: 1.45, marginBottom: "1.25rem" }}>
                  {resultado.advertencia}
                </p>

                <h2>Ángulos Medidos</h2>
                <div className="tabla-scroll" style={{ marginBottom: "1.25rem" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Segmento</th>
                        <th>Ángulo</th>
                        <th>Puntos REBA</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultado.angulos.map(ang => (
                        <tr key={ang.segmento}>
                          <td style={{ fontWeight: 500, textTransform: "capitalize" }}>{ang.segmento}</td>
                          <td className="mono" style={{ fontWeight: 600 }}>{ang.grados == null ? "—" : `${ang.grados}°`}</td>
                          <td style={{ fontWeight: 700, color: ang.puntaje_reba != null && ang.puntaje_reba > 1 ? "#D93A3A" : "inherit" }}>
                            {ang.puntaje_reba == null ? "—" : `+${ang.puntaje_reba}`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="acciones" style={{ flexDirection: "column", alignItems: "stretch" }}>
                  {alCapturarFoto && (
                    <button
                      type="button"
                      className="boton primario"
                      onClick={handleUsarEnNuevoCaso}
                    >
                      Usar esta fotografía para el nuevo caso
                    </button>
                  )}
                  <button
                    type="button"
                    className="boton"
                    onClick={handleRepetirFoto}
                  >
                    Tomar otra fotografía
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
