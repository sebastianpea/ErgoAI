# Propuestas de Innovación y Diferenciación para ErgoAI (Track 4 - Jabil)

> **Propuestas, no funcionalidades certificadas ni tareas autorizadas.** Porcentajes, tiempos y puntos son aspiraciones o ejemplos que exigen evidencia. Ver [estado actual](docs/ESTADO_ACTUAL.md); las vistas y ajustes humanos no garantizan precisión anatómica.

Este documento reúne propuestas de alto impacto técnico y operativo diseñadas específicamente para maximizar el puntaje en los bloques de **Diseño e Innovación (Criterios 4 y 5 - 15 pts)**, **Viabilidad y Valor (Criterios 6, 7 y 8 - 15 pts)** y **Desempeño Técnico (Criterios 1, 2 y 3 - 50 pts)** de la rúbrica oficial de Jabil en X-RAIC 2026.

---

## 1. Propuestas para Dominar el Desempeño Técnico (Precisión Angular y Puntaje REBA Exacto)

### Propuesta 1.1: Fusión Geométrica Multi-Vista con Corrección de Oclusiones (Frente + Costado + Aérea)
*   **Problema que resuelve**: Una sola cámara suele fallar cuando la mesa de ensamble o el propio cuerpo oculta el brazo o la muñeca. Además, los ángulos 2D sufren distorsión por perspectiva.
*   **Cómo implementarla**:
    *   Asignar a cada vista su plano biomecánico de máxima confiabilidad:
        *   **Vista Lateral (Costado)**: Extrae flexión/extensión de tronco (`0°-20°`, `20°-60°`, `>60°`), flexión de cuello (`0°-20°`, `>20°`), flexión de hombro/brazo, ángulo de codo (`60°-100°`) y flexión de rodillas (`30°-60°`, `>60°`).
        *   **Vista Frontal**: Extrae inclinación lateral (*side-bending*) de cuello y tronco (+1 pto REBA), elevación/abducción de hombros (+1 pto REBA) y asimetría de carga en piernas.
        *   **Vista Aérea (Superior)**: Extrae torsión/rotación transversal de tronco y cuello (+1 pto REBA) y proyecta mediante **Homografía 2D** el arco de alcance sobre la mesa (`Posiciones 1 a 5` de la sección `7.2.2.2` de Jabil: `150 mm` a `1500 mm`).
*   **Impacto en Rúbrica**: Busca `>= 90%` de coincidencia, sujeto a validación, en la estimación de ángulos (Criterio 2: 15 pts) y 6 de 6 casos exactos en REBA (Criterio 1: 20 pts, primer criterio de desempate).

### Propuesta 1.2: "Interactive Skeleton Fine-Tuner" (Ajuste Asistido de Keypoints en 2 Segundos)
*   **Problema que resuelve**: Durante la evaluación en vivo de los 6 casos, si una fotografía tiene baja iluminación o un equipo bloquea la articulación de la muñeca, un detector 100% caja negra podría equivocarse por unos grados y cambiar el rango REBA.
*   **Cómo implementarla**:
    *   En el visor web del Frontend, mostrar los vectores articulares como nodos arrastrables (*drag-and-drop*).
    *   Si el especialista nota que la muñeca está rotada o que el punto del tobillo quedó tapado por la mesa, puede ajustar el nodo con el mouse en 1 segundo o marcar casillas de micro-ajustes difíciles de ver en foto estática (*"¿Giro de muñeca?"*, *"¿Agarre deficiente?"*, *"¿Cambio brusco de postura?"*), actualizando el cálculo REBA al instante.
*   **Impacto en Rúbrica**: Busca mejorar la exactitud, sin garantizar un porcentaje, en los 6 casos en vivo y refuerza el principio de *"El agente propone y el especialista decide"*.

---

## 2. Propuestas de Innovación y Diferenciación frente a Calculadoras Genéricas (Bloque 2)

### Propuesta 2.1: "What-If Ergonomic Sandbox" (Simulador Interactivo de Rediseño y Riesgo Residual en Tiempo Real)
*   **Qué aporta**: En lugar de que el Riesgo Residual sea solo un número estático en el texto del informe, incorporar controles deslizantes (*sliders*) interactivos de **Controles de Ingeniería** basados en el documento `16-PE30-6500-00023` de Jabil:
    *   *Slider 1: Altura de Mesa de Trabajo* (ajustable entre `65 cm` y `130 cm`, resaltando la franja verde de Jabil CUU de `95 cm a 125 cm`). Al mover el slider, el sistema recalcula trigonométricamente cómo disminuye la flexión del tronco y de los hombros del operador.
    *   *Slider 2: Reubicación de Materiales y Herramental* (mover contenedores de `Zona 4/5 [>650 mm]` a `Zona 1/2 [150-400 mm]`).
    *   *Switch 3: Integración de Asistencia Mecánica / Lifter* (obligatorio si `Peso > 14 kg`) o cambio a postura **Sentado / Combinado con Silla ESD** (si `Peso < 3 kg`).
*   **Visualización**: Mostrar lado a lado el **"Esqueleto Actual (Rojo - REBA 11)"** vs. el **"Esqueleto Proyectado Post-Ingeniería (Verde - REBA 2)"**.
*   **Impacto en Rúbrica**: Aspira al puntaje máximo en **Originalidad y Diferenciación (Criterio 5)** y en **Riesgo Residual (Criterio 7)** porque recalcula matemáticamente el riesgo con las modificaciones propuestas y lo compara visualmente con el inicial.

### Propuesta 2.2: Puente Directo "ErgoAI-to-Jabil XLSM & AutoCAD Layer Advisor"
*   **Qué aporta**: La mayoría de los equipos solo entregarán un PDF genérico. Ustedes conocen a fondo el archivo real de Jabil **`16-PE80-6500-00014-H.xlsm`** y el manual de layouts **`16-PE30-6500-00023.pdf`**.
*   **Cómo implementarla**:
    1.  **Exportación Nativa a `16-PE80-6500-00014-H.xlsm`**: Un botón que descarga no solo el PDF del informe, sino también el archivo Excel oficial de Jabil ya pre-llenado automáticamente en las pestañas `Mov`, `Levantamiento (1)`, `Transporte (2)`, `sin auxiliar (4)`, `con auxiliar (5)`, `EAWS`, `Resultado` y `OBSERVACIONES Y MEJORAS`.
    2.  **Checklist MOC & AutoCAD Layer Tagging**: Cada recomendación de ingeniería incluye el código de documento normativo interno de Jabil que se activa:
        *   Si recomienda agregar una silla por la **Ley Silla STPS** -> Indica: *"Marcar en piso con leyenda 'SILLA', registrar en layer AutoCAD `Mobiliario` y documentar en Fábrica Visual"*.
        *   Si recomienda instalar un lifter o modificar altura de estación con servicios eléctricos/neumáticos -> Indica: *"Requiere formato de capacidad instalada `16-FS80-8000-00010`, actualizar layer `Equipos` y `Servicios` (Azul-150), y liberar con MOC `16-HS80-8000-00021`"*.
*   **Impacto en Rúbrica**: Los jueces especialistas de Jabil verán una solución que habla exactamente el lenguaje de su planta en Chihuahua, diferenciándose radicalmente de cualquier asistente genérico.

---

## 3. Propuestas para Viabilidad, Valor y Medición de Impacto (Bloque 3)

### Propuesta 3.1: Flujo "Dual-Sign Audit Trail" con Diff Visual (Human-in-the-Loop sin Base de Datos)
*   **Qué aporta**: Busca cubrir el Criterio 6 (*Validación del especialista y trazabilidad*) sin usar base de datos.
*   **Cómo implementarla**:
    *   Cada recomendación generada por el Agente IA nace en estado `PENDING_SPECIALIST_REVIEW`.
    *   Cuando el especialista edita una recomendación (por ejemplo, cambia *"Instalar mesa hidráulica"* por *"Ajustar perfil Bosch de la estación a 105 cm y colocar feeder en Zona 1"*), el sistema guarda un **Diff tipo Git** (`Texto Original IA` vs `Texto Validado por Especialista`), el motivo del cambio y la marca de tiempo UTC en un archivo JSON auditable.
    *   El PDF generado incluye al final una tabla de **"Manifiesto de Trazabilidad y Validación Humana"** (inspirada en la hoja *Signature Manifest* del PDF de Jabil), mostrando qué propuso la IA, qué ajustó o aprobó el ingeniero y el sello de validación.

### Propuesta 3.2: Telemetría Automática de ROI y Tiempos de Respuesta (Criterio 8)
*   **Qué aporta**: La rúbrica otorga **5 puntos** en el Criterio 8 si el impacto en tiempos de respuesta se mide **con datos reales de los casos de prueba** (y no solo estimaciones teóricas).
*   **Cómo implementarla**:
    *   Integrar un cronómetro interno automático en la interfaz que mide tres tiempos reales durante la resolución de cada uno de los 6 casos:
        1. `T_vision`: Tiempo de inferencia de pose y cálculo de ángulos (ej. `1.2 seg`).
        2. `T_calculo_y_agente`: Tiempo de evaluación REBA + NOM-036 + redacción de recomendaciones y riesgo residual (ej. `4.5 seg`).
        3. `T_validacion_humana`: Tiempo que tarda el especialista en revisar, editar y aprobar en pantalla (ej. `25 seg`).
    *   Comparar automáticamente en una tabla dentro del informe el **Tiempo Total ErgoAI (~30 segundos por caso)** contra el **Baseline Manual en Planta (~35 a 45 minutos por estación** entre medición con goniómetro, llenado manual de Excel y redacción de reporte), para medir una posible reducción; **el 97% es una meta ilustrativa, no un resultado observado**.

---

## 4. Propuesta de Estrategia para el Pitch de 6 Minutos (Bloque 5 - 10 pts)

Para aprovechar al máximo la dinámica de **1 min preparación + 6 min presentación con demo + 3 min preguntas**:
1.  **Minuto 0:00 - 0:45 (El Problema en Piso y Alineación Jabil)**: Explicar cómo la evaluación manual retrasa acciones correctivas y deja sin medir el riesgo residual, mostrando cómo ErgoAI integra **REBA + NOM-036-1 + Estándares Jabil (`16-PE80-6500-00014` y `16-PE30-6500-00023`)**.
2.  **Minuto 0:45 - 2:30 (Arquitectura Modular y Precisión Angular Multi-Vista)**: Mostrar cómo las 3 vistas (Frente, Costado, Aérea) alimentan el motor geométrico de ángulos y por qué el cálculo REBA/NOM-036 es **100% determinista** (cero alucinaciones), mientras el Agente IA redacta y jerarquiza los Controles de Ingeniería.
3.  **Minuto 2:30 - 4:30 (Demostración en Vivo de los Casos de Prueba)**:
    *   Cargar un caso de riesgo Alto/Muy Alto en vivo.
    *   Mostrar la detección de ángulos, el puntaje REBA y la alerta de la NOM-036 / Ley Silla / Límite 14 kg.
    *   Demostrar el paso obligatorio **Human-in-the-Loop**: editar/aprobar una recomendación de ingeniería, ver cómo se recalcula en vivo el **Riesgo Residual** y cómo queda grabado el registro de auditoría.
4.  **Minuto 4:30 - 6:00 (Resultados de los 6 Casos e Impacto Medido)**: Presentar el tablero resumen de los 6 casos resueltos, la reducción del riesgo residual y las métricas reales del cronómetro de tiempos de respuesta (`de 40 min a <35 seg`), exportando el PDF oficial y el Excel `.xlsm` de Jabil.
