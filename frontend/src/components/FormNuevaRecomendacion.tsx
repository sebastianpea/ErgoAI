import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type ParametroCatalogo } from "../api";
import type { CasoDetalle, NivelControl, NuevaRecomendacion, TipoCambio, ValorCambio } from "../types/caso";
import { ETIQUETA_TIPO_CAMBIO, valorCambio } from "../lib/niveles";
import { CampoValor } from "./CampoValor";

type Datos = Omit<NuevaRecomendacion, "usuario" | "rol">;

interface Props {
  caso: CasoDetalle;
  ocupado: boolean;
  error?: string;
  onCrear: (datos: Datos) => void;
  onCancelar: () => void;
}

/** Valor actual del parámetro en el caso (para mostrarlo y como punto de partida). */
function valorActual(caso: CasoDetalle, p: ParametroCatalogo): ValorCambio | null {
  if (p.parametro.startsWith("angulo.")) {
    const seg = p.parametro.split(".")[1];
    return caso.angulos.find(a => a.segmento === seg)?.angulo_grados ?? null;
  }
  if (p.parametro.startsWith("mod.")) {
    return caso.contexto.modificadores[p.parametro.slice(4) as keyof CasoDetalle["contexto"]["modificadores"]] ?? null;
  }
  const v = caso.contexto[p.parametro as keyof CasoDetalle["contexto"]];
  return typeof v === "object" ? null : (v as ValorCambio);
}

const NIVEL_POR_TIPO: Record<TipoCambio, NivelControl | null> = {
  planta: "ingenieria", administrativo: "administrativo", postura: null,
};

export function FormNuevaRecomendacion({ caso, ocupado, error, onCrear, onCancelar }: Props) {
  const catalogo = useQuery({ queryKey: ["catalogo-parametros"], queryFn: api.catalogoParametros, staleTime: Infinity });
  const [tipo, setTipo] = useState<TipoCambio>("planta");
  const [nivelPostura, setNivelPostura] = useState<NivelControl>("administrativo");
  const [titulo, setTitulo] = useState("");
  const [texto, setTexto] = useState("");
  const [referencia, setReferencia] = useState("");
  const [motivo, setMotivo] = useState("");
  const [responsable, setResponsable] = useState("");
  const [fecha, setFecha] = useState("");
  const [cambios, setCambios] = useState<Record<string, ValorCambio>>({});
  const [nuevoParametro, setNuevoParametro] = useState("");

  const params = catalogo.data ?? [];
  const porClave = new Map(params.map(p => [p.parametro, p]));
  const disponibles = params.filter(p => !(p.parametro in cambios));
  const nivel = NIVEL_POR_TIPO[tipo] ?? nivelPostura;
  const valido = titulo.trim().length >= 3 && texto.trim().length >= 5 && motivo.trim().length >= 3;

  const agregar = () => {
    const p = porClave.get(nuevoParametro);
    if (!p) return;
    const actual = valorActual(caso, p);
    const inicial: ValorCambio = p.tipo === "booleano" ? !actual
      : p.tipo === "opcion" ? (p.opciones[0] ?? "") : typeof actual === "number" ? actual : 0;
    setCambios(c => ({ ...c, [p.parametro]: inicial }));
    setNuevoParametro("");
  };

  return (
    <form className="tarjeta form-nueva corte" onSubmit={e => {
      e.preventDefault();
      if (!valido) return;
      onCrear({
        tipo_cambio: tipo, nivel_control: nivel, titulo: titulo.trim(), texto: texto.trim(),
        referencia: referencia.trim() || undefined, cambios, motivo: motivo.trim(),
        responsable: responsable.trim() || undefined, fecha_compromiso: fecha || undefined,
      });
    }}>
      <p className="eyebrow">Recomendación del especialista</p>
      <h3>Nueva acción</h3>

      <div className="campos">
        <label>Tipo de cambio
          <select value={tipo} onChange={e => setTipo(e.target.value as TipoCambio)}>
            {(Object.keys(ETIQUETA_TIPO_CAMBIO) as TipoCambio[]).map(t =>
              <option key={t} value={t}>{ETIQUETA_TIPO_CAMBIO[t]}</option>)}
          </select>
        </label>
        <label>Nivel de control
          {tipo === "postura" ? (
            <select value={nivelPostura} onChange={e => setNivelPostura(e.target.value as NivelControl)}>
              <option value="administrativo">Administrativo</option>
              <option value="ingenieria">Ingeniería</option>
            </select>
          ) : <input value={nivel === "ingenieria" ? "Ingeniería" : "Administrativo"} readOnly />}
        </label>
        <label className="ancho">Título<input value={titulo} onChange={e => setTitulo(e.target.value)} required minLength={3} /></label>
        <label className="ancho">Descripción de la acción
          <textarea value={texto} onChange={e => setTexto(e.target.value)} rows={3} required minLength={5} />
        </label>
        <label className="ancho">Referencia normativa (opcional)
          <input value={referencia} onChange={e => setReferencia(e.target.value)} placeholder="Criterio del especialista" />
        </label>
      </div>

      <p className="etiqueta-campo">Ajustes que produce la acción (para proyectar el riesgo residual)</p>
      {Object.keys(cambios).length > 0 && (
        <div className="tabla-scroll">
          <table className="tabla-cambios">
            <thead><tr><th>Parámetro</th><th>Actual</th><th>Objetivo</th><th /></tr></thead>
            <tbody>
              {Object.entries(cambios).map(([clave, valor]) => {
                const p = porClave.get(clave);
                if (!p) return null;
                return (
                  <tr key={clave}>
                    <td>{p.etiqueta}</td>
                    <td>{valorCambio(valorActual(caso, p), p.unidad)}</td>
                    <td><CampoValor tipo={p.tipo} valor={valor} etiqueta={`Objetivo: ${p.etiqueta}`} unidad={p.unidad}
                      minimo={p.minimo} maximo={p.maximo} opciones={p.opciones}
                      onChange={v => setCambios(c => ({ ...c, [clave]: v }))} /></td>
                    <td><button type="button" className="mini" aria-label={`Quitar ${p.etiqueta}`}
                      onClick={() => setCambios(({ [clave]: _, ...resto }) => resto)}>Quitar</button></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="acciones agregar-parametro">
        <select value={nuevoParametro} onChange={e => setNuevoParametro(e.target.value)} aria-label="Parámetro a ajustar">
          <option value="">Elegir parámetro…</option>
          {disponibles.map(p => <option key={p.parametro} value={p.parametro}>{p.etiqueta}</option>)}
        </select>
        <button type="button" disabled={!nuevoParametro} onClick={agregar}>Agregar ajuste</button>
      </div>

      <div className="campos">
        <label>Responsable<input value={responsable} onChange={e => setResponsable(e.target.value)} /></label>
        <label>Fecha compromiso<input type="date" value={fecha} onChange={e => setFecha(e.target.value)} /></label>
        <label className="ancho">Justificación (obligatoria)
          <input value={motivo} onChange={e => setMotivo(e.target.value)} required minLength={3} />
        </label>
      </div>

      {tipo === "planta" && <p className="sutil">Al guardarla queda aprobada por ti y pasa a Ingeniería para autorización.</p>}
      {error && <p className="aviso error">{error}</p>}
      <div className="acciones">
        <button type="submit" className="primario" disabled={ocupado || !valido}>Guardar recomendación</button>
        <button type="button" onClick={onCancelar}>Cancelar</button>
      </div>
    </form>
  );
}
