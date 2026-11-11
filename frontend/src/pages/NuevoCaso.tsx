import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type FotosNuevoCaso } from "../api";
import type { ContextoTarea, EvaluacionPrevia, TipoTarea, Vista } from "../types/caso";
import { CamposReferencia, REFERENCIA_VACIA } from "../components/FormReferencia";
import { ETIQUETA_TAREA } from "../lib/niveles";
import { useSesion } from "../lib/sesion";
import { Encabezado } from "../components/Encabezado";
import { CONTEXTO_VACIO, CamposContexto } from "../components/FormContexto";
import { CapturaCamaraModal } from "../components/CapturaCamaraModal";

const VISTAS: { vista: Vista; titulo: string; ayuda: string; obligatoria: boolean }[] = [
  { vista: "lateral", titulo: "Lateral (costado)", ayuda: "Operador de perfil, de cuerpo completo. De aquí se miden los ángulos REBA.", obligatoria: true },
  { vista: "frontal", titulo: "Frontal", ayuda: "De frente: inclinaciones laterales y abducción de brazos.", obligatoria: false },
  { vista: "cenital", titulo: "Aérea (cenital)", ayuda: "Desde arriba: zonas de alcance y objetos sobre la mesa.", obligatoria: false },
];

function TarjetaSelectorFoto({
  vista,
  titulo,
  ayuda,
  obligatoria,
  archivo,
  onElegir,
  onAbrirCamara,
}: {
  vista: Vista;
  titulo: string;
  ayuda: string;
  obligatoria: boolean;
  archivo?: File;
  onElegir: (f?: File) => void;
  onAbrirCamara: () => void;
}) {
  const [vistaPrevia, setVistaPrevia] = useState<string>();

  useEffect(() => {
    if (!archivo) {
      setVistaPrevia(undefined);
      return;
    }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  return (
    <div className={`selector-foto-tarjeta corte ${archivo ? "con-foto" : ""}`}>
      <div className="selector-foto-header">
        <span className="eyebrow">{titulo}</span>
        <span className={`indicador-obligatoria ${obligatoria ? "obligatoria" : "opcional"}`}>
          {obligatoria ? "Obligatoria" : "Opcional"}
        </span>
      </div>

      <div className="selector-foto-preview">
        {vistaPrevia ? (
          <img src={vistaPrevia} alt={`Vista ${vista}`} />
        ) : (
          <div className="foto-vacia">
            <span className="foto-vacia-texto">Sin fotografía</span>
          </div>
        )}
      </div>

      <div className="selector-foto-info">
        <p className="sutil selector-foto-nombre" title={archivo ? archivo.name : ayuda}>
          {archivo ? archivo.name : ayuda}
        </p>
      </div>

      <div className="selector-foto-acciones">
        <button
          type="button"
          className="boton primario boton-accion-camara"
          onClick={onAbrirCamara}
          title={`Tomar fotografía en vivo con la cámara para vista ${vista}`}
        >
          {archivo ? "Retomar con cámara" : "Tomar con cámara"}
        </button>

        <label className="boton boton-accion-archivo" title="Seleccionar fotografía desde disco">
          {archivo ? "Cambiar archivo" : "Subir archivo"}
          <input
            type="file"
            accept="image/jpeg,image/png"
            onChange={e => {
              const f = e.target.files?.[0];
              if (f) onElegir(f);
            }}
            style={{ display: "none" }}
          />
        </label>

        {archivo && (
          <button
            type="button"
            className="boton peligro boton-quitar-foto"
            onClick={() => onElegir(undefined)}
            title="Quitar esta fotografía"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}

export function NuevoCaso() {
  const navegar = useNavigate();
  const qc = useQueryClient();
  const { esErgonomia } = useSesion();
  const vision = useQuery({ queryKey: ["vision"], queryFn: api.estadoVision, staleTime: 60_000 });
  const [estacion, setEstacion] = useState("");
  const [tarea, setTarea] = useState<TipoTarea>("sin_clasificar");
  const [contexto, setContexto] = useState<ContextoTarea>(CONTEXTO_VACIO);
  const [referencia, setReferencia] = useState<EvaluacionPrevia>(REFERENCIA_VACIA);
  const [fotos, setFotos] = useState<Partial<Record<Vista, File>>>({});

  // Control del modal de cámara integrado
  const [modalCamara, setModalCamara] = useState<{
    abierto: boolean;
    vista: Vista;
    modo: "captura_simple" | "diagnostico_rapido";
  }>({
    abierto: false,
    vista: "lateral",
    modo: "captura_simple",
  });

  const crear = useMutation({
    mutationFn: () => api.crearCaso(
      { estacion: estacion.trim(), tipo_tarea: tarea, contexto, evaluacion_previa: referencia }, fotos as FotosNuevoCaso),
    onSuccess: ({ id }) => {
      qc.invalidateQueries({ queryKey: ["casos"] });
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["bitacora"] });
      qc.invalidateQueries({ queryKey: ["impacto"] });
      navegar(`/casos/${id}`);
    },
  });

  const listo = esErgonomia && vision.data?.disponible && estacion.trim().length >= 3 && !!fotos.lateral;

  const handleRecibirFotoCamara = (archivo: File, vista: Vista) => {
    setFotos(prev => ({ ...prev, [vista]: archivo }));
  };

  return (
    <section>
      <Encabezado
        eyebrow="Visión artificial · YOLOX + RTMPose WholeBody-133"
        titulo="Nuevo caso desde fotos"
        subtitulo="Sube o captura las fotos. Después selecciona manualmente la persona en cada vista y revisa la evidencia antes de calcular el riesgo; no se asocian identidades entre imágenes."
        acciones={
          <button
            type="button"
            className="boton primario"
            onClick={() => setModalCamara({ abierto: true, vista: "lateral", modo: "diagnostico_rapido" })}
            title="Abre la cámara web para un diagnóstico ergonómico instantáneo"
          >
            Diagnóstico Rápido con Cámara
          </button>
        }
      />

      {vision.data && (
        <p className={`aviso ${vision.data.disponible ? "ok" : "error"}`}>
          {vision.data.disponible ? `Visión lista: ${vision.data.detalle}` : `Visión no disponible: ${vision.data.detalle}`}
        </p>
      )}
      {!esErgonomia && <p className="aviso">Solo Ergonomía puede crear casos. Cambia el rol en la barra superior.</p>}

      <form onSubmit={e => { e.preventDefault(); if (listo) crear.mutate(); }}>
        <div className="tarjeta">
          <h2>Fotografías de la Estación</h2>
          <div className="selector-fotos">
            {VISTAS.map(v => (
              <TarjetaSelectorFoto
                key={v.vista}
                {...v}
                archivo={fotos[v.vista]}
                onElegir={f => setFotos(x => ({ ...x, [v.vista]: f }))}
                onAbrirCamara={() => setModalCamara({ abierto: true, vista: v.vista, modo: "captura_simple" })}
              />
            ))}
          </div>
          <p className="leyenda">
            Compatible con cámaras web en Windows y Linux. Los rostros se difuminan automáticamente antes de guardar la foto. Formatos JPG o PNG, máximo 15 MB.
          </p>
        </div>

        <div className="tarjeta">
          <h2>Estación y tarea</h2>
          <div className="campos">
            <label>Estación<input value={estacion} onChange={e => setEstacion(e.target.value)} placeholder="Ej. Línea 2 · Estación 04" required minLength={3} /></label>
            <label>Tipo de tarea
              <select value={tarea} onChange={e => setTarea(e.target.value as TipoTarea)}>
                {(Object.keys(ETIQUETA_TAREA).filter(t => t !== "equipo") as TipoTarea[]).map(t => <option key={t} value={t}>{ETIQUETA_TAREA[t]}</option>)}
              </select>
            </label>
          </div>
          <p className="sutil">El modelo actual mide postura; no distingue de forma validada levantamiento, transporte o empuje. Si no podés confirmarlo, dejalo como “Sin clasificar”; no se generará una evaluación NOM-036 específica.</p>
          <p className="etiqueta-campo">Datos operativos por confirmar</p>
          <CamposContexto valor={contexto} onChange={setContexto} />
        </div>

        <div className="tarjeta">
          <h2>Estudio de referencia de Jabil (opcional)</h2>
          <p className="sutil">
            Puntajes REBA del estudio previo de la estación. El sistema los compara con lo que mide en la foto y
            marca cada diferencia como hallazgo de auditoría. Se pueden capturar después.
          </p>
          <CamposReferencia valor={referencia} onChange={setReferencia} />
        </div>

        {crear.isError && <p className="aviso error">No se creó el caso: {crear.error.message}</p>}
        <div className="acciones">
          <button type="submit" className="primario" disabled={!listo || crear.isPending}>
            {crear.isPending ? "Analizando fotos…" : "Analizar y crear caso"}
          </button>
          {!fotos.lateral && <span className="sutil">Falta la foto lateral (tómala con la cámara o súbela como archivo).</span>}
        </div>
      </form>

      {/* Modal de Cámara Web para Windows y Linux */}
      {modalCamara.abierto && (
        <CapturaCamaraModal
          vistaObjetivo={modalCamara.vista}
          modo={modalCamara.modo}
          alCapturarFoto={handleRecibirFotoCamara}
          alCerrar={() => setModalCamara(prev => ({ ...prev, abierto: false }))}
        />
      )}
    </section>
  );
}
