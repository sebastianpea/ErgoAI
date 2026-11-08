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
  const metodoInicial: MetodoNom036 = actual?.metodo ?? (tipoTarea === "postura" ? "levantamiento" : tipoTarea);
  const [metodo, setMetodo] = useState<MetodoNom036>(metodoInicial);
  const [valores, setValores] = useState<Record<string, { color: ColorNom; valor: number }>>(
    () => Object.fromEntries((actual?.factores ?? []).map(f => [f.codigo, { color: f.color, valor: f.valor }])));
  const [motivo, setMotivo] = useState("");
  const [abierto, setAbierto] = useState(false);

  const def = catalogo.data?.[metodo];
  const hoja = typeof def === "object" ? def : undefined;
  const libre = !!hoja?.captura_libre;

  const filas: FactorNom[] = useMemo(() => (hoja?.factores ?? []).map((f: FactorCatalogo) => {
    const v = valores[f.codigo];
    if (libre) return { codigo: f.codigo, etiqueta: f.etiqueta, color: v?.color ?? "verde", valor: v?.valor ?? 0 };
    const opciones = f.opciones ?? {};
    const color = v && v.color in opciones ? v.color : "verde";
    return { codigo: f.codigo, etiqueta: f.etiqueta, color, valor: opciones[color] ?? 0 };
  }), [hoja, valores, libre]);
  const total = filas.reduce((s, f) => s + f.valor, 0);

  if (!editable && !actual) return <p className="sutil">Sin evaluación NOM-036 capturada.</p>;
  if (!abierto) {
    return editable ? (
      <button onClick={() => setAbierto(true)}>{actual ? "Corregir evaluación NOM-036" : "Capturar evaluación NOM-036"}</button>
    ) : null;
  }
  if (catalogo.isError) return <p className="aviso error">{catalogo.error.message}</p>;
  if (!hoja) return <p className="cargando">Cargando hoja NOM-036…</p>;

  const set = (codigo: string, cambio: Partial<{ color: ColorNom; valor: number }>) =>
    setValores(v => ({ ...v, [codigo]: { ...(v[codigo] ?? { color: "verde" as ColorNom, valor: 0 }), ...cambio } }));

  return (
    <form className="form-nom036" onSubmit={e => {
      e.preventDefault();
      if (motivo.trim().length >= 3) onGuardar({ metodo, factores: filas }, motivo.trim());
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
                    <select aria-label={`Color: ${f.etiqueta}`} value={f.color} onChange={e => set(f.codigo, { color: e.target.value as ColorNom })}>
                      {(libre ? COLORES : (Object.keys(opciones) as ColorNom[])).map(c => (
                        <option key={c} value={c}>{ETIQUETA_COLOR_NOM[c]}{!libre ? ` (${opciones[c]})` : ""}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {libre ? (
                      <input type="number" min={0} max={50} step={1} aria-label={`Valor: ${f.etiqueta}`} value={f.valor}
                        className="valor-corto" onChange={e => set(f.codigo, { valor: Math.max(0, Math.round(Number(e.target.value))) })} />
                    ) : <strong>{f.valor}</strong>}
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
        <button type="submit" className="primario" disabled={ocupado || motivo.trim().length < 3}>Guardar NOM-036</button>
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
