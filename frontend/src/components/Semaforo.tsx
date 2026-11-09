import { COLOR_SEMAFORO, type Semaforo as TipoSemaforo } from "../lib/niveles";

interface Props {
  color: TipoSemaforo;
  texto: string;
  valor?: number | string;
}

/** Etiqueta de nivel: siempre color + texto, nunca solo color. */
export function Semaforo({ color, texto, valor }: Props) {
  return (
    <span className="chip" style={{ background: COLOR_SEMAFORO[color] }}>
      {valor !== undefined && <strong>{valor}</strong>}
      {texto}
    </span>
  );
}