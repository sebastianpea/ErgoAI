# NOM-036: cinco hojas de captura y trazabilidad de factores

**La captura manual ahora permite seleccionar Equipo (3) y confirmar sus nueve factores de AI.4.** Se conservan los factores de las otras cuatro hojas y la validación íntegra, aunque el formulario se muestre por páginas. Esto amplía la captura completa de evidencia de equipo; **no certifica fórmulas automáticas, equivalencia con el libro Jabil ni cumplimiento normativo**.

## Ruta operativa

1. El especialista de Ergonomía observa la actividad representativa con los trabajadores y consulta la norma y el libro controlado `16-PE80-6500-00014-H`. Si hay actividades combinadas, debe evaluar cada una (AI.1, p.42; AII.1, pp.52–53).
2. En Análisis, abrir **Capturar evaluación NOM-036**, elegir la hoja y confirmar cada factor en todas las páginas. Sin confirmar no significa verde ni cero. En Equipo (3), registrar masa y número de operadores en la justificación y transcribir por separado color y valor de cada factor desde la hoja revisada con el especialista.
3. Añadir justificación y guardar. `GET /catalogo/nom036` publica las definiciones; `PUT /casos/{id_caso}/nom036` recibe `nom036: {metodo, factores}` más actor y motivo. `GET /casos/{id_caso}` permite verificar el resultado persistido. Un factor omitido o repetido se rechaza; el rechazo no debe alterar el caso ni la bitácora.

Cada caso conserva una captura NOM-036 activa, no una colección de evaluaciones simultáneas: cambiarla reemplaza la captura activa y registra la corrección. Evaluar actividades combinadas exige conservar sus estudios por separado; este cambio no añade un contenedor de múltiples estudios.

| Grupo | Método manual API | Hoja | Factores manuales |
| --- | --- | --- | --- |
| AI.2 Levantamiento/descenso individual | `levantamiento` | Levantamiento (1) | 8 |
| AI.3 Transporte | `transporte` | Transporte (2) | 9 |
| AI.4 Levantamiento/descenso en equipo | `equipo` | Equipo (3) | 9, captura libre |
| AII.3–AII.4 Empuje/arrastre sin auxiliar | `empuje_sin_auxiliar` | sin auxiliar (4) | 9 históricos; ver diferencia con los 8 oficiales abajo |
| AII.5–AII.6 Empuje/arrastre con auxiliar | `empuje_con_auxiliar` | con auxiliar (5) | 9, captura libre |

## Fuentes y alcance de la evidencia

Fuente oficial de referencia: [NOM-036-1-STPS-2018, DOF 23/11/2018](https://dof.gob.mx/normasOficiales/7468/stps11_C/stps11_C.html). El inventario siguiente se cotejó con la **transcripción local**, no con una nueva descarga ni con las imágenes originales de las gráficas: [`config_normativo/corpus_normativo.json`](../config_normativo/corpus_normativo.json), `fragmentos`. Las páginas son las declaradas por ese corpus. Sus identificadores `NOM036-Apendice-I-p43` … `p52` y `NOM036-Apendice-II-p53-1` … `p63` permiten localizar las cláusulas.

El numeral 7.3 (p.24) separa Apéndice I de Apéndice II. AI.5 (pp.51–52), AII.4 (pp.57–58) y AII.6 (p.63) describen registro de colores/valores, nivel y acciones. El informe, evaluación específica cuando corresponda, controles, vigilancia de salud y capacitación siguen siendo necesarios (7.1–7.4, pp.24; capítulos 8–10, pp.25–29); cinco hojas no sustituyen estas obligaciones.

Las claves manuales proceden de `metodos` en [`nom036_mac_rapp_tables.json`](../config_normativo/nom036_mac_rapp_tables.json). `sheets_mapping` describe las cinco estrategias y utiliza algunas claves distintas. La nueva captura de equipo reutiliza exactamente las nueve claves de `sheets_mapping.equipo_3.factors`, sin copiar sus umbrales numéricos.

## 1. AI.2 — Levantamiento/descenso individual

| Cláusula / página del corpus | Factor completo | Código de captura |
| --- | --- | --- |
| AI.2 a), p.43 | Peso de la carga y frecuencia de levantamiento/descenso | `peso_frecuencia` |
| AI.2 b), p.43 | Distancia horizontal entre manos y parte inferior de la espalda; peor escenario | `distancia_horizontal` |
| AI.2 c), p.44 | Región de levantamiento vertical a lo largo de la operación | `region_vertical` |
| AI.2 d), p.44 | Torsión y flexión lateral del torso | `torsion` |
| AI.2 e), p.44 | Restricciones posturales por espacio y diseño del puesto | `postura` |
| AI.2 f), p.45 | Acoplamiento mano-carga / elementos de sujeción | `agarre` |
| AI.2 g), p.45 | Superficie de trabajo donde camina o permanece de pie | `piso` |
| AI.2 h), p.45 | Otros factores ambientales: temperatura, circulación de aire e iluminación extremas | `otros` |

## 2. AI.3 — Transporte de cargas

| Cláusula / página del corpus | Factor completo | Código de captura |
| --- | --- | --- |
| AI.3 a), p.46 | Peso de la carga y frecuencia de transporte | `peso_frecuencia` |
| AI.3 b), p.46 | Distancia horizontal manos–parte inferior de la espalda | `distancia_manos_espalda` |
| AI.3 c), p.47 | Carga asimétrica sobre el torso, postura y estabilidad | `asimetria` |
| AI.3 d), p.47 | Restricciones posturales durante el transporte | `postura` |
| AI.3 e), p.47 | Acoplamiento mano-carga / elementos de sujeción | `agarre` |
| AI.3 f), p.48 | Superficie de trabajo | `piso` |
| AI.3 g), p.48 | Otros factores ambientales | `otros` |
| AI.3 h), p.48 | Distancia total de transporte / trayectoria | `distancia_transporte` |
| AI.3 i), p.48 | Obstáculos en la ruta: pendientes, escalones, puertas, tropiezos y combinaciones | `obstaculos` |

## 3. AI.4 — Levantamiento/descenso en equipo

| Cláusula / página del corpus | Factor completo | Código de captura y de `equipo_3.factors` |
| --- | --- | --- |
| AI.4 a), p.49 | Peso de la carga y número de operadores | `peso_equipo_operadores` |
| AI.4 b), p.49 | Distancia horizontal manos–espalda de cada trabajador; peor caso | `distancia_manos_espalda` |
| AI.4 c), p.49 | Región de levantamiento vertical durante toda la operación | `region_vertical` |
| AI.4 d), p.50 | Torsión y flexión lateral del torso | `torsion_flexion_lateral` |
| AI.4 e), p.50 | Restricciones posturales, incluido espacio entre miembros del equipo | `restricciones_posturales` |
| AI.4 f), p.50 | Acoplamiento mano-carga / elementos de sujeción | `acoplamiento_mano_carga` |
| AI.4 g), p.50 | Superficie de trabajo | `superficie_trabajo` |
| AI.4 h), p.51 | Otros factores ambientales | `factores_ambientales` |
| AI.4 i), p.51 | Comunicación, coordinación y control: levantamiento conjunto, parejo y suave | `comunicacion_coordinacion_control` |

No se obtiene el peso ni el número de operadores de los esqueletos. El especialista confirma la evidencia y transcribe los nueve colores/valores; la API exige el conjunto completo mediante el validador existente. `equipo` es un método de captura, no un nuevo `TipoTarea` general. Las estrategias automáticas y el mapeo histórico de equipo a `levantamiento` permanecen sin cambios; seleccionar este método no certifica ni modifica su fórmula.

## 4. AII.3–AII.4 — Empuje/arrastre sin equipo auxiliar

La norma distingue **rodando, girando sobre la base y arrastrando/jalando/deslizando**. AII.3 a) exige evaluar cada actividad aplicable y la mayor masa; AII.4 registra cada tipo por separado.

| Cláusula / página del corpus | Factor oficial completo | Relación con la captura histórica |
| --- | --- | --- |
| AII.3 a), pp.53–54 | Actividad y peso de la carga | `sheets_mapping.sin_auxiliar_4`: `actividad_y_peso`; no existe clave manual equivalente |
| AII.3 b), p.54 | Postura de manos y cuerpo | `postura` |
| AII.3 c), p.55 | Acoplamiento mano-carga, tanto en empuje como en tracción | `agarre` |
| AII.3 d), p.55 | Patrón de trabajo: repetición, ritmo y recuperación | `patron_trabajo` |
| AII.3 e), p.56 | Distancia por viaje: viaje más largo o promedio de al menos cinco si es repetitivo | `distancia` |
| AII.3 f), p.56 | Superficie de trabajo a lo largo de la ruta | `piso` |
| AII.3 g), p.56 | Obstáculos a lo largo de la ruta, cada tipo contado una vez | `obstaculos` |
| AII.3 h), p.57 | Otros factores: inestabilidad, visibilidad, contacto peligroso, iluminación, temperatura/humedad, aire, EPP/vestimenta | `otros` |

**Diferencia conservada, no resuelta:** el formulario histórico exige `fuerza_inicial` y `fuerza_sostenida` más los siete factores comunes anteriores, en lugar de `actividad_y_peso`. Esos nueve campos se conservan íntegros; las fuerzas no se declaran equivalentes a actividad/peso. Registrar actividad y masa en la justificación mantiene evidencia textual, pero no añade validación estructurada de ese factor. La reconciliación de esta diferencia exige libro controlado y especialista; no afirmar equivalencia completa del formulario histórico con AII.3. AII.4, pp.57–58, aporta la hoja de registro y las acciones, no nuevos factores.

## 5. AII.5–AII.6 — Empuje/arrastre con equipo auxiliar

| Cláusula / página del corpus | Factor completo | Código de captura |
| --- | --- | --- |
| AII.5 a), pp.58–59 | Tipo de equipo y peso total (equipo más cargas), capacidad nominal; pequeño 1–2 ruedas, mediano ≥3 ruedas, grande dirigible/sobre rieles | `peso_carga`; tipo y capacidad en justificación |
| AII.5 b), p.59 | Postura de manos y cuerpo | `postura` |
| AII.5 c), p.60 | Acoplamiento mano-carga, en ambas acciones si hay empuje y arrastre | `agarre` |
| AII.5 d), p.61 | Patrón de trabajo: repetición, ritmo, descansos y rotación | `patron_trabajo` |
| AII.5 e), p.61 | Distancia por viaje | `distancia` |
| AII.5 f), p.61 | Condición del equipo auxiliar: mantenimiento, ruedas, cojinetes y frenos | `estado_equipo` |
| AII.5 superficie, p.62 | Superficie de trabajo | `piso` |
| AII.5 obstáculos, p.62 | Obstáculos a lo largo de la ruta | `obstaculos` |
| AII.5 otros, p.62 | Inestabilidad del equipo/carga, visibilidad, contacto peligroso, iluminación, temperatura/humedad, aire y EPP/vestimenta | `otros` |

La transcripción local etiqueta los últimos tres apartados como i), j), k); aquí se identifican también por nombre para no inventar una corrección del original. AII.6 (p.63) exige registro por tipo de equipo, estimación del nivel y acciones. El formulario no convierte por sí solo una superación de capacidad nominal en una certificación de seguridad ni sustituye la prohibición de operar descrita en AII.5 a).

## Qué calcula el sistema y qué queda pendiente

- `backend/app/core_ergonomics/nom036_calculator.py:validar_captura` conserva unicidad y pertenencia de todos los factores. En captura libre el backend exige enteros no negativos; el formulario conserva su rango manual 0–50. No se amplían rangos ni se endurecen reglas históricas en este cambio.
- `backend/app/services/casos.py:corregir_nom036` reutiliza persistencia, auditoría y sincronización existentes. `_calcular_nom036` suma los factores manuales y usa las bandas globales configuradas; eso es determinismo, no certificación de la fórmula ni del dato introducido.
- `frontend/src/components/FormNom036.tsx` mantiene confirmaciones independientes por método y valida todas las páginas. Los valores desconocidos no se inicializan como observaciones verdes.
- No se modifican tablas numéricas, colores/puntajes existentes, estrategias, umbrales Jabil ni reglas de privacidad/paginación. Las diferencias entre Markdown, JSON y gráficos siguen pendientes del libro controlado `16-PE80-6500-00014-H` y de un especialista. La transcripción textual omite parte de la evidencia gráfica: no permite reconstruir cada tabla por inferencia.
- Esta entrega no automatiza todas las fórmulas NOM-036 ni declara cumplimiento regulatorio. El inventario completo permite reconocer también las diferencias históricas que todavía necesitan reconciliación.

## Verificación de esta unidad

Las pruebas de `tests/test_flujo_especialista.py` ejercen la API pública: guardado y consulta de los nueve factores de equipo, rechazo de cada omisión sin cambios en caso/bitácora y conservación de los cuatro métodos previos. `frontend/tests/nom036.test.mjs` usa el catálogo real para comprobar la quinta opción, los nueve factores y el bloqueo por un valor sin confirmar en otra página. Resultados y límites de ejecución: [T4/S5 en el registro ODD](../odd/tasks/ergoai-multivision-pagination-nom036.md).
