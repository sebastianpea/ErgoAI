# Base de Conocimiento Normativo NOM-036-1-STPS-2018
**Factores de Riesgo Ergonómico en el Trabajo - Parte 1: Manejo manual de cargas**

> **Referencia de trabajo no certificada.** No es texto legal oficial ni fuente para puntuar. El cálculo consume `nom036_mac_rapp_tables.json`; discrepancias requieren cotejo con originales y especialista, no copiar valores de este Markdown. Ver [estado actual y validaciones pendientes](../docs/ESTADO_ACTUAL.md).

---

## 1. Objetivo y Campo de Aplicación (Capítulo 1 y 2)
* **Objetivo**: Establecer los elementos para identificar, analizar, prevenir y controlar los factores de riesgo ergonómico en los centros de trabajo derivados del manejo manual de cargas, a efecto de prevenir alteraciones a la salud de los trabajadores.
* **Campo de aplicación**: Rige en todo el territorio nacional y aplica en todos los centros de trabajo donde existan trabajadores que realicen manejo manual de cargas de forma cotidiana (más de una vez al día).

---

## 2. Obligaciones del Patrón y Jerarquía de Control (Capítulo 5 y 8)
* **Obligación 5.1**: Contar con el análisis de los factores de riesgo ergonómico debido al manejo manual de cargas.
* **Obligación 5.3**: Adoptar medidas de prevención y control para mitigar los riesgos derivados del manejo manual de cargas.
* **Jerarquía de Control (Capítulo 8.3)**:
  1. **Eliminación o Controles de Ingeniería**:
     - Integración de ayudas mecánicas (polipastos, grúas, montacargas, mesas elevadoras hidráulicas, transportadores de rodillos o bandas, carritos con ruedas adecuadas).
     - Rediseño de la estación de trabajo (alturas de superficie de trabajo entre nudillos y codos, optimización de zonas de alcance).
     - Modificación de las características de la carga (reducir peso unitario, proveer agarraderas ergonómicas).
  2. **Controles Administrativos y de Organización del Trabajo**:
     - Rotación de puestos y asignación a tareas de menor demanda física.
     - Programación de períodos de descanso y pausas activas.
     - Limitación de tiempos máximos continuos en posturas estáticas o de pie.
  3. **Capacitación y Adiestramiento**:
     - Instrucción formal sobre técnica segura de levantamiento (flexión de rodillas, mantener carga pegada al cuerpo, evitar torsión de tronco).

---

## 3. Límites Máximos de Carga Manual (Capítulo 7.1)
* **Masa máxima para hombres de 18 a 45 años**: 25 kg.
* **Masa máxima para mujeres de 18 a 45 años**: 20 kg.
* **Menores de 18 años y mayores de 45 años**: Hombres 20 kg, Mujeres 15 kg.
* **Masa máxima para mujeres embarazadas o en periodo de lactancia**: Prohibido el manejo manual de cargas > 10 kg.
* *Nota de prevalencia Jabil Site CUU*: En planta Jabil Chihuahua, el estándar interno **16-PE30-6500-00023 §6.4.1** establece un límite estricto de **14.0 kg por persona**, el cual prevalece sobre el límite legal de 25 kg por ser más restrictivo y protector.

---

## 4. Apéndice I: Método de Evaluación de Levantamiento y Transporte de Carga (MAC)
> **Advertencia MAC:** este resumen mezcla peso/frecuencia con bandas totales y difiere del JSON operativo: región vertical `[0, 1, 3]` frente al crítico 6 aquí; torsión máxima 2 frente a 3 aquí. No se ha establecido cuál interpretación es correcta sin originales. No usar estos valores para cambiar cálculos o certificar cumplimiento.

* **Factores Críticos Evaluados**:
  1. **Peso de la carga y frecuencia de levantamiento**: Rango de 0 a 6 puntos (Verde: <=4, Amarillo: 5-12, Rojo: 13-20, Morado: >=21).
  2. **Distancia horizontal entre manos y espalda baja**:
     - Cerca: manos a menos de 25 cm del cuerpo (0 pts).
     - Moderada: manos entre 25 y 45 cm (3 pts).
     - Lejos: manos a más de 45 cm (6 pts).
  3. **Región vertical del levantamiento**:
     - Óptima: entre nudillos y codo (0 pts).
     - Desfavorable: por debajo de rodillas o por encima de hombros (3 pts).
     - Crítica: nivel de piso o sobre cabeza (6 pts).
  4. **Torsión e inclinación lateral del tronco**:
     - Sin torsión: tronco recto (< 10°) (0 pts).
     - Torsión moderada (10° a 45°) (1 pto).
     - Torsión severa (> 45°) o inclinación lateral (> 10°) (3 pts).
  5. **Restricciones posturales**:
     - Espacio libre y sin obstáculos para pies y cuerpo (0 pts).
     - Espacio restringido, necesidad de agacharse o pasar por debajo (1 a 3 pts).
  6. **Acoplamiento / Agarre de la carga**:
     - Bueno: asas o ranuras anatómicas de sujeción (0 pts).
     - Regular: sujeción en bordes sin asas o flexión de dedos a 90° (1 pto).
     - Malo: sin puntos de apoyo, voluminosa, resbalosa o bordes filosos (2 pts).
  7. **Superficie del piso**:
     - Seco, limpio, nivelado y en buen estado (0 pts).
     - Resbaladizo, húmedo, desnivelado o con obstáculos (1 a 2 pts).

---

## 5. Apéndice II: Método de Evaluación de Empuje y Arrastre (RAPP)
* **Modalidad con Auxiliar de Transporte (Carros, Zorras, Plataformas)**:
  - Carga total transportada y fuerza requerida (inicial para poner en movimiento y sostenida para mantener).
  - Diámetro y material de ruedas (poliuretano, hule vulcanizado, rodamientos sellados).
  - Estado del piso y pendientes (> 2% requiere asistencia motriz).
  - Altura de manerales: debe ubicarse entre 90 cm y 120 cm del piso (nivel de codos/cadera).
* **Modalidad sin Auxiliar de Transporte (Acarreo Forzado / Rodamiento)**:
  - Distancia de traslado: traslados mayores a 10 metros con carga manual individual deben sustituirse por equipo rodante o montacargas.
  - Carga > 14 kg trasladada a pie representa riesgo alto/inaceptable.

---

## 6. Legislación Complementaria: Ley Silla STPS
* **Regulación de Postura de Pie Prolongada**:
  - Prohibido mantener al operario de pie por más de 3 horas continuas.
  - Obligatorio proveer asiento ergonómico con respaldo en la estación de trabajo cuando la naturaleza del proceso lo permita.
  - Para estaciones donde la tarea deba realizarse de pie, es obligatorio proveer descansos periódicos mínimos de 5 minutos en asiento habilitado.
