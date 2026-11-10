import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { CasoDetalle, ContextoTarea, Punto, Segmento, Vista } from "../types/caso";
import { COLOR_SEMAFORO, ETIQUETA_TAREA, VISTAS, semaforoSegmento } from "../lib/niveles";
import { useSesion } from "../lib/sesion";
import { SkeletonEditor } from "../components/SkeletonEditor";
import { TablaAngulos } from "../components/TablaAngulos";
import { DesgloseNom036, DesgloseReba } from "../components/DesgloseReba";
import { Encabezado } from "../components/Encabezado";
import { FormContexto } from "../components/FormContexto";
import { ListaHallazgos } from "../components/ListaHallazgos";

export function Analisis() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const { esErgonomia } = useSesion();
  const [vista, setVista] = useState<Vista>("lateral");
  const [reinicios, setReinicios] = useState(0); // fuerza a re-montar el editor si el guardado falla
  const { data: caso, isLoading, error } = useQuery({ queryKey: ["caso", id], queryFn: () => api.obtenerCaso(id) });

  // Toda corrección recalcula el caso: actualiza bandeja, alertas y bitácora.
  const aplicar = (actualizado: CasoDetalle) => {
    qc.setQueryData(["caso", id], actualizado);
    qc.invalidateQueries({ queryKey: ["casos"] });
    qc.invalidateQueries({ queryKey: ["alertas"] });
    qc.invalidateQueries({ queryKey: ["bitacora"] });
  };

  const corregir = useMutation({
    mutationFn: (puntos: Punto[]) => api.corregirPuntos(id, vista, puntos),
    onSuccess: aplicar,
    onError: () => setReinicios(n => n + 1), // el punto vuelve a su posición guardada
  });
  const contexto = useMutation({
    mutationFn: ({ c, motivo }: { c: ContextoTarea; motivo: string }) => api.corregirContexto(id, c, motivo),
    onSuccess: aplicar,
  });
  const hallazgo = useMutation({
    mutationFn: ({ h, accion, motivo }: { h: string; accion: "descartar" | "restaurar"; motivo: string }) =>
      api.revisarHallazgo(id, h, accion, motivo),
    onSuccess: aplicar,
  });
  const confirmarAngulo = useMutation({
    mutationFn: ({ v, s }: { v: Vista; s: Segmento }) => api.confirmarAngulo(id, v, s),
    onSuccess: aplicar,
  });

  if (isLoading) return <p className="cargando">Cargando caso…</p>;
  if (error || !caso) return <p className="aviso error">{(error as Error)?.message ?? "Caso no encontrado"}</p>;

  const imagen = caso.imagenes.find(i => i.vista === vista);
  const puntajePorSegmento = new Map<string, number>();
  for (const a of caso.angulos.filter(x => x.vista === vista)) {
    puntajePorSegmento.set(a.segmento, a.puntaje_reba);
  }
  if (puntajePorSegmento.size === 0) {
    for (const a of caso.angulos) {
      puntajePorSegmento.set(a.segmento, Math.max(puntajePorSegmento.get(a.segmento) ?? 0, a.puntaje_reba));
    }
  }
  const colorSegmento = (s: string) => COLOR_SEMAFORO[semaforoSegmento(puntajePorSegmento.get(s))];
  const v = caso.validacion;

  return (
    <section>
      <Encabezado
        eyebrow={`Análisis y revisión · ${ETIQUETA_TAREA[caso.tipo_tarea]}`}
        titulo={<>{caso.id_caso} <span className="ligero">· {caso.estacion}</span></>}
        subtitulo="Revisa lo que detectó el sistema y corrige cualquier error: cada cambio recalcula el REBA y queda en la bitácora."
        acciones={<Link className="boton primario" to={`/casos/${id}/plan`}>
          Recomendaciones{v.pendientes + v.por_autorizar > 0 ? ` (${v.pendientes + v.por_autorizar})` : ""} →
        </Link>}
      />

      <div className="rejilla">
        <div className="tarjeta">
          <h2>Esqueleto detectado</h2>
          <div className="pestanas">
            {VISTAS.map(vv => (
              <button key={vv} className={vv === vista ? "activa" : ""} onClick={() => setVista(vv)}>{vv}</button>
            ))}
          </div>
          {imagen ? (
            <SkeletonEditor
              key={`${caso.id_caso}-${vista}-${reinicios}`}
              imagen={imagen}
              editable={esErgonomia}
              colorSegmento={colorSegmento}
              cajas={caso.hallazgos.filter(h => h.vista === vista && !h.descartado)}
              onCommit={puntos => corregir.mutate(puntos)}
            />
          ) : (
            <p className="sutil">Sin foto para esta vista.</p>
          )}
          <p className="leyenda">
            {esErgonomia
              ? "Si un punto está mal colocado, arrástralo a su lugar. Punteado naranja = baja confianza; azul marino = corregido."
              : "Solo Ergonomía puede corregir el esqueleto."}
            {corregir.isPending && " Guardando…"}
          </p>
          {corregir.isError && <p className="aviso error">No se guardó la corrección: {corregir.error.message}</p>}
        </div>

        <div className="tarjeta">
          <h2>Hallazgos</h2>
          <ListaHallazgos hallazgos={caso.hallazgos} editable={esErgonomia} ocupado={hallazgo.isPending}
            onRevisar={(h, accion, motivo) => hallazgo.mutate({ h, accion, motivo })} />
          {hallazgo.isError && <p className="aviso error">{hallazgo.error.message}</p>}
        </div>
      </div>

      <div className="tarjeta">
        <h2>Ángulos por segmento</h2>
        <TablaAngulos
          angulos={caso.angulos}
          editable={esErgonomia}
          ocupado={confirmarAngulo.isPending}
          onConfirmar={(v, s) => confirmarAngulo.mutate({ v, s })}
        />
        {confirmarAngulo.isError && <p className="aviso error">{confirmarAngulo.error.message}</p>}
      </div>

      <div className="tarjeta">
        <h2>Datos de la tarea</h2>
        <p className="sutil">
          Estos datos no salen de la foto (peso, agarre, torsiones…). Si alguno está mal, corrígelo aquí con su justificación.
        </p>
        <FormContexto
          key={JSON.stringify(caso.contexto)}
          contexto={caso.contexto} editable={esErgonomia} ocupado={contexto.isPending}
          error={contexto.error?.message}
          onGuardar={(c, motivo) => contexto.mutate({ c, motivo })}
        />
      </div>

      <div className="rejilla">
        {caso.reba && (
          <div className="tarjeta"><h2>REBA</h2><DesgloseReba reba={caso.reba} /></div>
        )}
        {caso.nom036 && (
          <div className="tarjeta"><h2>NOM-036-1-STPS-2018</h2><DesgloseNom036 nom={caso.nom036} /></div>
        )}
      </div>

      <div className="tarjeta" style={{
        marginTop: "20px",
        background: "linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)",
        border: "2px solid #3b82f6",
        textAlign: "center",
        padding: "24px 20px",
        borderRadius: "12px",
      }}>
        <h3 style={{ margin: "0 0 8px 0", color: "#1e3a8a", fontSize: "1.2rem" }}>
          Paso 2: Generar Plan de Mitigación con ErgoAI
        </h3>
        <p style={{ margin: "0 0 16px 0", color: "#475569", maxWidth: "680px", marginLeft: "auto", marginRight: "auto", fontSize: "0.95rem" }}>
          El análisis biomecánico se ha completado con exactitud matemática (REBA {caso.reba?.final ?? "—"}).
          Continúa al plan de acción para que el Agente consulte la NOM-036-1-STPS-2018 y los estándares de Jabil y redacte las recomendaciones técnicas.
        </p>
        <Link className="boton primario" style={{ fontSize: "1rem", padding: "12px 28px", display: "inline-block" }} to={`/casos/${id}/plan`}>
          Generar Plan de Mitigación con ErgoAI →
        </Link>
      </div>
    </section>
  );
}
