import type { ResultadoNom036, ResultadoReba } from "../types/caso";
import { ETIQUETA_COLOR_NOM, ETIQUETA_TAREA, NIVEL_REBA } from "../lib/niveles";
import { Semaforo } from "./Semaforo";

export function DesgloseReba({ reba }: { reba: ResultadoReba }) {
  const filas: [string, number][] = [
    ["Grupo A (tronco, cuello, piernas)", reba.grupo_a],
    ["Grupo B (brazo, antebrazo, muñeca)", reba.grupo_b],
    ["Tabla C", reba.tabla_c],
    ["Carga / fuerza", reba.carga],
    ["Agarre", reba.agarre],
    ["Actividad", reba.actividad],
  ];
  const nivel = NIVEL_REBA[reba.nivel];
  return (
    <div>
      <dl className="desglose">
        {filas.map(([k, v]) => (
          <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
        ))}
      </dl>
      <div className="total">
        Puntaje final REBA <Semaforo color={nivel.color} texto={nivel.etiqueta} valor={reba.final} />
      </div>
    </div>
  );
}

export function DesgloseNom036({ nom }: { nom: ResultadoNom036 }) {
  return (
    <div>
      <p className="sutil">Método: {ETIQUETA_TAREA[nom.metodo]}</p>
      <div className="tabla-scroll">
        <table>
          <thead><tr><th>Factor</th><th>Valor</th><th>Color</th></tr></thead>
          <tbody>
            {nom.factores.map(f => (
              <tr key={f.codigo}>
                <td>{f.etiqueta}</td>
                <td>{f.valor}</td>
                <td><Semaforo color={f.color} texto={ETIQUETA_COLOR_NOM[f.color]} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="total">
        Total NOM-036 <Semaforo color={nom.nivel} texto={ETIQUETA_COLOR_NOM[nom.nivel]} valor={nom.total} />
      </div>
    </div>
  );
}