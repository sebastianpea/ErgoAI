import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type FotosNuevoCaso } from "../api";
import type { ContextoTarea, TipoTarea, Vista } from "../types/caso";
import { ETIQUETA_TAREA } from "../lib/niveles";
import { useSesion } from "../lib/sesion";
import { Encabezado } from "../components/Encabezado";
import { CONTEXTO_VACIO, CamposContexto } from "../components/FormContexto";

const VISTAS: { vista: Vista; titulo: string; ayuda: string; obligatoria: boolean }[] = [
  { vista: "lateral", titulo: "Lateral (costado)", ayuda: "Operador de perfil, de cuerpo completo. De aquí se miden los ángulos REBA.", obligatoria: true },
  { vista: "frontal", titulo: "Frontal", ayuda: "De frente: inclinaciones laterales y abducción de brazos.", obligatoria: false },
  { vista: "cenital", titulo: "Aérea (cenital)", ayuda: "Desde arriba: zonas de alcance y objetos sobre la mesa.", obligatoria: false },
];

function SelectorFoto({ vista, titulo, ayuda, obligatoria, archivo, onElegir }: {
  vista: Vista; titulo: string; ayuda: string; obligatoria: boolean; archivo?: File; onElegir: (f?: File) => void;
}) {
  const [vistaPrevia, setVistaPrevia] = useState<string>();
  useEffect(() => {
    if (!archivo) { setVistaPrevia(undefined); return; }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  return (
    <label className={`selector-foto${archivo ? " con-foto" : ""}`}>
      <span className="eyebrow">{titulo}{obligatoria ? " · obligatoria" : " · opcional"}</span>
      {vistaPrevia ? <img src={vistaPrevia} alt={`Vista ${vista}`} /> : <span className="foto-vacia">Elegir foto</span>}
      <span className="sutil">{archivo ? archivo.name : ayuda}</span>
      <input type="file" accept="image/jpeg,image/png" onChange={e => onElegir(e.target.files?.[0])} />
    </label>
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

  return (
    <section>
      <Encabezado
        eyebrow="Visión artificial · YOLOX + RTMPose WholeBody-133"
        titulo="Nuevo caso desde fotos"
        subtitulo="Sube las tomas de la estación. El sistema detecta la postura, calcula REBA y propone recomendaciones; tú revisas y decides."
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
              <SelectorFoto key={v.vista} {...v} archivo={fotos[v.vista]}
                onElegir={f => setFotos(x => ({ ...x, [v.vista]: f }))} />
            ))}
          </div>
          <p className="leyenda">
            Los rostros se difuminan automáticamente antes de guardar la foto. Formatos JPG o PNG, máximo 15 MB.
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
          {!fotos.lateral && <span className="sutil">Falta la foto lateral.</span>}
        </div>
      </form>
    </section>
  );
}
