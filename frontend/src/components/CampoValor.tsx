import type { ValorCambio } from "../types/caso";

interface Props {
  tipo: "numero" | "booleano" | "opcion";
  valor: ValorCambio | null;
  onChange: (v: ValorCambio) => void;
  etiqueta: string;
  unidad?: string | null;
  minimo?: number | null;
  maximo?: number | null;
  opciones?: string[];
}

/** Entrada para el valor objetivo de un parámetro (número con unidad, sí/no u opción). */
export function CampoValor({ tipo, valor, onChange, etiqueta, unidad, minimo, maximo, opciones = [] }: Props) {
  if (tipo === "booleano") {
    return (
      <select aria-label={etiqueta} value={valor ? "si" : "no"} onChange={e => onChange(e.target.value === "si")}>
        <option value="si">Sí</option>
        <option value="no">No</option>
      </select>
    );
  }
  if (tipo === "opcion") {
    return (
      <select aria-label={etiqueta} value={String(valor ?? "")} onChange={e => onChange(e.target.value)}>
        {opciones.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <span className="campo-numero">
      <input
        type="number" aria-label={etiqueta} step={unidad === "°" ? 0.5 : 1}
        min={minimo ?? undefined} max={maximo ?? undefined}
        value={typeof valor === "number" ? valor : ""}
        onChange={e => e.target.value !== "" && onChange(Number(e.target.value))}
      />
      {unidad && <span className="unidad">{unidad}</span>}
    </span>
  );
}
