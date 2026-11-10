import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type FotosNuevoCaso } from "../api";
import type { ContextoTarea, TipoTarea, Vista } from "../types/caso";
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

function SelectorFoto({ vista, titulo, ayuda, obligatoria, archivo, onElegir, onAbrirCamara }: {
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
    if (!archivo) { setVistaPrevia(undefined); return; }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  return (
    <div className={`selector-foto-contenedor${archivo ? " con-foto" : ""}`}>
      <label className={`selector-foto${archivo ? " con-foto" : ""}`}>
        <span className="eyebrow">{titulo}{obligatoria ? " · obligatoria" : " · opcional"}</span>
        {vistaPrevia ? <img src={vistaPrevia} alt={`Vista ${vista}`} /> : <span className="foto-vacia">📁 Elegir archivo</span>}
        <span className="sutil">{archivo ? archivo.name : ayuda}</span>
        <input type="file" accept="image/jpeg,image/png" onChange={e => onElegir(e.target.files?.[0])} />
      </label>
      <div className="selector-foto-botones">
        <button
          type="button"
          className="boton-camara-directa"
          onClick={e => {
            e.stopPropagation();
            onAbrirCamara();
          }}
          title={`Tomar foto con cámara web para vista ${vista}`}
        >
          📷 {archivo ? "Cambiar con cámara" : "Tomar con cámara"}
        </button>
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
  const [tarea, setTarea] = useState<TipoTarea>("levantamiento");
  const [contexto, setContexto] = useState<ContextoTarea>(CONTEXTO_VACIO);
  const [fotos, setFotos] = useState<Partial<Record<Vista, File>>>({});

  // Control del modal de cámara
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
    mutationFn: () => api.crearCaso({ estacion: estacion.trim(), tipo_tarea: tarea, contexto }, fotos as FotosNuevoCaso),
    onSuccess: ({ id }) => {
      qc.invalidateQueries({ queryKey: ["casos"] });
      qc.invalidateQueries({ queryKey: ["alertas"] });
      qc.invalidateQueries({ queryKey: ["bitacora"] });
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
        subtitulo="Sube las tomas de la estación o captura fotos con la cámara en vivo. El sistema detecta la postura, calcula REBA y propone recomendaciones."
        acciones={
          <button
            type="button"
            className="boton primario boton-diagnostico-header"
            onClick={() => setModalCamara({ abierto: true, vista: "lateral", modo: "diagnostico_rapido" })}
            title="Abre la cámara para diagnosticar la postura al instante en Windows y Linux"
          >
            ⚡ Diagnóstico Rápido con Cámara
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
          <h2>Fotografías</h2>
          <div className="selector-fotos">
            {VISTAS.map(v => (
              <SelectorFoto
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
                {(Object.keys(ETIQUETA_TAREA) as TipoTarea[]).map(t => <option key={t} value={t}>{ETIQUETA_TAREA[t]}</option>)}
              </select>
            </label>
          </div>
          <p className="etiqueta-campo">Datos que no salen de la foto</p>
          <CamposContexto valor={contexto} onChange={setContexto} />
        </div>

        {crear.isError && <p className="aviso error">No se creó el caso: {crear.error.message}</p>}
        <div className="acciones">
          <button type="submit" className="primario" disabled={!listo || crear.isPending}>
            {crear.isPending ? "Analizando fotos…" : "Analizar y crear caso"}
          </button>
          {!fotos.lateral && <span className="sutil">Falta la foto lateral (captúrala con la cámara o súbela como archivo).</span>}
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
