import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { formatearFecha } from "../lib/niveles";
import { Encabezado } from "../components/Encabezado";

export function Bitacora() {
  const { data, isLoading, error } = useQuery({ queryKey: ["bitacora"], queryFn: () => api.bitacora() });
  const verificar = useMutation({ mutationFn: api.verificarIntegridad });

  if (isLoading) return <p className="cargando">Cargando bitácora…</p>;
  if (error) return <p className="aviso error">{(error as Error).message}</p>;

  return (
    <section>
      <Encabezado
        eyebrow="Trazabilidad SHA-256"
        titulo="Bitácora de auditoría"
        subtitulo="Registro de solo inserción. Cada entrada guarda el hash de la anterior."
        acciones={
          <button className="primario" disabled={verificar.isPending} onClick={() => verificar.mutate()}>
            Verificar integridad
          </button>
        }
      />

      {verificar.data && (
        <p className={verificar.data.ok ? "aviso ok" : "aviso error"}>
          {verificar.data.ok
            ? `Cadena íntegra: ${verificar.data.total} entradas verificadas.`
            : verificar.data.primera_falla != null
              ? `Alteración detectada en la entrada ${verificar.data.primera_falla}.`
              : `Alteración detectada: ${verificar.data.detalle ?? "registro ilegible"}.`}
        </p>
      )}
      {verificar.isError && <p className="aviso error">No se pudo verificar: {verificar.error.message}</p>}

      <div className="tarjeta tabla-scroll">
        <table>
          <thead>
            <tr><th>#</th><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Objetivo</th><th>Cambio</th><th>Motivo</th><th>Hash</th></tr>
          </thead>
          <tbody>
            {[...(data ?? [])].reverse().map(e => (
              <tr key={e.secuencia}>
                <td>{e.secuencia}</td>
                <td>{formatearFecha(e.timestamp)}</td>
                <td>{e.usuario}</td>
                <td>{e.accion}</td>
                <td>{e.objetivo}</td>
                <td>{e.antes || e.despues ? <>{e.antes && <div className="antes">{e.antes}</div>}{e.despues && <div className="despues">{e.despues}</div>}</> : "—"}</td>
                <td>{e.motivo ?? "—"}</td>
                <td className="mono" title={`hash: ${e.hash}\nanterior: ${e.hash_anterior}`}>{e.hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}