import { useEffect, useState } from "react";

const sinMovimiento = () =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Cifra que cuenta desde 0 hasta `valor` (salta directo si el usuario reduce el movimiento). */
export function Contador({ valor, duracion = 900 }: { valor: number; duracion?: number }) {
  const [actual, setActual] = useState(() => (sinMovimiento() ? valor : 0));

  useEffect(() => {
    if (sinMovimiento()) {
      setActual(valor);
      return;
    }
    let frame = 0;
    const inicio = performance.now();
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracion);
      setActual(Math.round(valor * (1 - Math.pow(1 - p, 3)))); // ease-out cúbico
      if (p < 1) frame = requestAnimationFrame(paso);
    };
    frame = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame);
  }, [valor, duracion]);

  return <>{actual}</>;
}
