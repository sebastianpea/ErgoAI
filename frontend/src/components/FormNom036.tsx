import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type FactorCatalogo, type Nom036Captura } from "../api";
import type { ColorNom, FactorNom, MetodoNom036, ResultadoNom036, TipoTarea } from "../types/caso";
import { ETIQUETA_COLOR_NOM, ETIQUETA_TAREA } from "../lib/niveles";

const METODOS: MetodoNom036[] = ["levantamiento", "transporte", "empuje_con_auxiliar", "empuje_sin_auxiliar"];
const COLORES: ColorNom[] = ["verde", "amarillo", "naranja", "rojo", "morado"];

interface Props {
  tipoTarea: TipoTarea;
  actual: ResultadoNom036 | null;
  editable: boolean;
  ocupado: boolean;
  error?: string;
  onGuardar: (nom036: Nom036Captura | null, motivo: string) => void;
}

/** Captura de la hoja NOM-036 (16-PE80-6500-00014-H). En métodos con tabla, el color fija el valor. */
export function FormNom036({ tipoTarea, actual, editable, ocupado, error, onGuardar }: Props) {
  const catalogo = useQuery({ queryKey: ["catalogo-nom036"], queryFn: api.catalogoNom036, staleTime: Infinity });
  const metodoInicial: MetodoNom036 = actual?.metodo ?? (
    METODOS.includes(tipoTarea as MetodoNom036) ? tipoTarea as MetodoNom036 : "levantamiento"
  );
  const [metodo, setMetodo] = useState<MetodoNom036>(metodoInicial);
  const [valores, setValores] = useState<Record<string, Record<string, { color?: ColorNom; valor?: number }>>>(
    () => ({ [metodoInicial]: Object.fromEntries((actual?.factores ?? []).map(f => [f.codigo, { color: f.color, valor: f.valor }])) }));
  const [motivo, setMotivo] = useState("");
  const [abierto, setAbierto] = useState(false);

  const def = catalogo.data?.[metodo];
  const hoja = typeof def === "object" ? def : undefined;
  const libre = !!hoja?.captura_libre;

  const filas = useMemo(() => (hoja?.factores ?? []).map((f: FactorCatalogo) => {
    const v = valores[metodo]?.[f.codigo];
    const opciones = f.opciones ?? {};
    const color = v?.color && (libre ? COLORES.includes(v.color) : v.color in opciones) ? v.color : undefined;
    return { codigo: f.codigo, etiqueta: f.etiqueta, color, valor: libre ? v?.valor : color ? opciones[color] : undefined };
  }), [hoja, valores, libre, metodo]);
  const confirmados: FactorNom[] = filas.flatMap(f =>
    f.color !== undefined && f.valor !== undefined && Number.isFinite(f.valor) && Number.isInteger(f.valor) && f.valor >= 0 && (!libre || f.valor <= 50)
      ? [{ ...f, color: f.color, valor: f.valor }] : []);
  const completo = filas.length > 0 && confirmados.length === filas.length;
  const total = completo ? confirmados.reduce((s, f) => s + f.valor, 0) : "Pendiente de confirmar";

  if (!editable && !actual) return <p className="sutil">Sin evaluación NOM-036 capturada.</p>;
  if (!abierto) {
    return editable ? (
      <button onClick={() => setAbierto(true)}>{actual ? "Corregir evaluación NOM-036" : "Capturar evaluación NOM-036"}</button>
    ) : null;
  }
  if (catalogo.isError) return <p className="aviso error">{catalogo.error.message}</p>;
  if (!hoja) return <p className="cargando">Cargando hoja NOM-036…</p>;

  const set = (codigo: string, cambio: Partial<{ color: ColorNom; valor: number }>) =>
    setValores(v => ({ ...v, [metodo]: { ...v[metodo], [codigo]: { ...v[metodo]?.[codigo], ...cambio } } }));

  return (
    <form className="form-nom036" onSubmit={e => {
      e.preventDefault();
      if (completo && !ocupado && motivo.trim().length >= 3) onGuardar({ metodo, factores: confirmados }, motivo.trim());
    }}>
      <div className="campos">
        <label>Método (hoja)
          <select value={metodo} onChange={e => setMetodo(e.target.value as MetodoNom036)}>
            {METODOS.map(m => {
              const h = catalogo.data?.[m];
              return <option key={m} value={m}>{ETIQUETA_TAREA[m]}{typeof h === "object" ? ` · ${h.hoja}` : ""}</option>;
            })}
          </select>
        </label>
        <label>Total
          <input readOnly value={`${total}`} />
        </label>
      </div>
      <p className="sutil">Confirma cada factor con datos observados o con la hoja oficial. Sin confirmar no significa verde ni cero; el total queda pendiente hasta completar todos los factores.</p>
      {libre && <p className="sutil">Captura los valores tal como aparecen en la hoja oficial {hoja.hoja}.</p>}
      <div className="tabla-scroll">
        <table className="tabla-cambios">
          <thead><tr><th>Factor</th><th>Color</th><th>Valor</th></tr></thead>
          <tbody>
            {filas.map(f => {
              const opciones = hoja.factores.find(x => x.codigo === f.codigo)?.opciones ?? {};
              return (
                <tr key={f.codigo}>
                  <td>{f.etiqueta}</td>
                  <td>
                    <select aria-label={`Color: ${f.etiqueta}`} value={f.color ?? ""} onChange={e => set(f.codigo, { color: e.target.value ? e.target.value as ColorNom : undefined })}>
                      <option value="">Sin confirmar</option>
                      {(libre ? COLORES : (Object.keys(opciones) as ColorNom[])).map(c => (
                        <option key={c} value={c}>{ETIQUETA_COLOR_NOM[c]}{!libre ? ` (${opciones[c]})` : ""}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {libre ? (
                      <input type="number" min={0} max={50} step={1} aria-label={`Valor: ${f.etiqueta}`} value={f.valor ?? ""}
                        className="valor-corto" onChange={e => set(f.codigo, { valor: e.target.value === "" ? undefined : Math.max(0, Math.round(Number(e.target.value))) })} />
                    ) : <strong>{f.valor ?? "Sin confirmar"}</strong>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <label className="campo-bloque">Justificación (obligatoria)
        <input value={motivo} onChange={e => setMotivo(e.target.value)} placeholder="Ej. Hoja 16-PE80-6500-00014-H llenada en piso" />
      </label>
      {error && <p className="aviso error">{error}</p>}
      <div className="acciones">
        <button type="submit" className="primario" disabled={ocupado || !completo || motivo.trim().length < 3}>Guardar NOM-036</button>
        <button type="button" onClick={() => setAbierto(false)}>Cancelar</button>
        {actual && (
          <button type="button" className="peligro" disabled={ocupado || motivo.trim().length < 3}
            title={motivo.trim().length < 3 ? "Escribe la justificación" : undefined}
            onClick={() => onGuardar(null, motivo.trim())}>Quitar evaluación</button>
        )}
      </div>
    </form>
  );
}
