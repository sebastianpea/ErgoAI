import type { ReactNode } from "react";

interface Props {
  eyebrow: string;
  titulo: ReactNode;
  subtitulo?: ReactNode;
  acciones?: ReactNode;
}

/** Banda de página con el corte diagonal y la textura de marca. */
export function Encabezado({ eyebrow, titulo, subtitulo, acciones }: Props) {
  return (
    <header className="banda">
      <span className="banda-franja f1" aria-hidden />
      <span className="banda-franja f2" aria-hidden />
      <div className="banda-contenido">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{titulo}</h1>
          {subtitulo && <p className="banda-sub">{subtitulo}</p>}
        </div>
        {acciones && <div className="acciones">{acciones}</div>}
      </div>
    </header>
  );
}
