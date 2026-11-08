# Notas para la documentación técnica de ErgoAI

Insumo para redactar la documentación técnica (máximo 10 cuartillas, criterio 9 de la rúbrica).
Está organizado en las cinco partes que pide la rúbrica. Todo lo descrito aquí está en la rama `front-end`
y tiene pruebas automatizadas (59 pruebas de backend).

---

## 1. Arquitectura

**Flujo general:** fotos (lateral, frontal, aérea) → visión → ángulos → REBA y reglas → recomendaciones →
validación humana (ergonomía y, para cambios en planta, ingeniería) → informe con riesgo residual.

| Capa | Ubicación | Responsabilidad |
|---|---|---|
| Interfaz | `frontend/` (React + TypeScript, identidad Jabil) | Bandeja, análisis y corrección, plan de acción, alertas, bitácora, informe imprimible |
| API | `backend/main.py` (FastAPI) | Endpoints REST, validación de entradas (Pydantic), roles, errores 403/404/409/422/503 |
| Casos de uso | `backend/app/services/casos.py` | Orquesta visión, cálculo, recomendaciones, validación, bitácora y alertas |
| Visión | `backend/app/vision/` | YOLOX (detección de personas) + RTMPose WholeBody-133 (puntos del cuerpo) en ONNX Runtime |
| Dominio | `backend/app/core_ergonomics/` | Geometría de ángulos, REBA, NOM-036, simulador de riesgo residual, generador de recomendaciones |
| Persistencia | `backend/app/session_store/` | Archivos JSON con escritura atómica y cadenas de hash SHA-256 |
| Normativa | `config_normativo/*.json` | Única fuente de tablas, umbrales y referencias (REBA, NOM-036, Jabil 16-PE30-6500-00023) |

**Decisiones a justificar (criterio 4):**
- **La IA solo da coordenadas; los puntajes los calcula código determinista.** Un modelo de lenguaje no
  calcula REBA: se evita que invente valores y el resultado es reproducible y auditable.
- **Visión top-down con 133 puntos:** los 17 del cuerpo son el estándar COCO; los de la mano permiten medir
  la muñeca, que con solo 17 puntos queda sin dato.
- **Ningún número normativo está en el código:** todo sale de `config_normativo/`, que se puede auditar y
  actualizar en un solo lugar.
- **Sin base de datos**, por mandato de la rúbrica: archivos JSON por caso.
- **Recomendaciones por reglas, no por LLM:** cada regla cita la norma o la sección Jabil que la respalda,
  y pone primero los controles de ingeniería, como exige la NOM-036.

---

## 2. Métodos implementados

### Visión
- Modelos: `yolox_tiny_8xb8-300e_humanart` y `rtmw-dw-l-m_simcc-cocktail14_270e-256x192` (OpenMMLab,
  licencia Apache-2.0), los mismos del pipeline del equipo. Unos 150–200 ms por foto en CPU.
- Si hay varias personas, se evalúa la de mayor tamaño y se avisa con un hallazgo.
- Si el operador está tapado (p. ej. por una caja) y el detector no lo encuentra, se estima la pose sobre
  la imagen completa y se marca para revisión.
- Se guardan 19 puntos por foto: los 17 del cuerpo y el nudillo medio de cada mano.

### Ángulos (foto lateral)
Trigonometría vectorial con `atan2` sobre los puntos:
- **Tronco:** cadera → hombro respecto a la vertical. **Cuello:** hombro → oreja respecto al tronco.
- **Brazo:** hombro → codo respecto al tronco. **Antebrazo:** 180° − ángulo del codo.
- **Piernas:** flexión de rodilla. **Muñeca:** desviación entre antebrazo y mano.
- **Hacia dónde mira el operador** se decide por votación de varias pistas (nariz-oreja, nariz-hombro,
  manos-cadera, rodilla-tobillo). Es crítico: si se equivoca, una flexión se lee como extensión.
- **Lado evaluado:** el de mayor confianza de detección.

**Vista frontal:** inclinación lateral del tronco (umbral 10°) y abducción del brazo (umbral 20°). Activan
los modificadores REBA y el especialista puede desmarcarlos.

### REBA
Método oficial de Hignett & McAtamney (2000): puntajes por segmento, Tablas A, B y C, carga/fuerza,
agarre y actividad. Niveles: 1 inapreciable, 2–3 bajo, 4–7 medio, 8–10 alto, 11–15 muy alto.

Un ángulo a menos de 5° de un umbral REBA, o con baja confianza de detección, se marca "Revisar".

### NOM-036-1-STPS-2018
Formulario por método (levantamiento, transporte, empuje con o sin auxiliar). En levantamiento y transporte
el color elegido fija el valor del factor; el total se clasifica en verde, amarillo, rojo o morado.
**Pendiente:** confirmar los valores del catálogo contra la hoja oficial 16-PE80-6500-00014-H.

### Reglas Jabil (16-PE30-6500-00023)
- Carga mayor a 14 kg por persona.
- Altura de trabajo fuera de 95–125 cm.
- Zonas de alcance 1–2 (150–400 mm), usadas en las recomendaciones.
- Ley Silla: máximo 3 h de pie continuas.

### Recomendaciones
Reglas que se disparan por umbrales del catálogo. Cada una trae los ajustes concretos (p. ej. "tronco
47.5° → 5°") y el REBA proyectado. El orden sigue la jerarquía de la NOM-036: primero ingeniería y
rediseño de estación, después método de trabajo y al final medidas administrativas. Hay reglas específicas
para levantamiento, transporte sin auxiliar (acarreo) y transporte con auxiliar (carro).

### Riesgo residual (criterio 7)
Se recalcula el REBA aplicando los ajustes de las recomendaciones no rechazadas ni denegadas por
ingeniería. Si dos acciones ajustan el mismo parámetro, prevalece la de mayor reducción. El informe
compara el REBA inicial con el residual, por segmento.

### Validación humana y trazabilidad (criterio 6)
- **Ergonomía** aprueba, edita (texto y valores) o rechaza. Editar o rechazar exige justificación.
- **Ingeniería (IE/Facilities)** autoriza o deniega los cambios en planta. Quien aprobó no puede autorizar.
- Ergonomía marca la recomendación como implementada.
- El informe solo se habilita con el plan validado.
- Ergonomía también puede corregir los puntos del esqueleto, los datos de la tarea, el estudio de
  referencia de Jabil y la NOM-036, y descartar hallazgos erróneos. Todo exige justificación y recalcula.
- Cada acción queda en dos registros encadenados con SHA-256: la bitácora global y el `audit_trail.json`
  de cada caso. El botón "Verificar integridad" detecta cualquier alteración manual.

### Impacto (criterio 8)
Cada caso nuevo registra el tiempo de análisis automático (unos 1.3 s) y el tiempo desde su creación hasta
el plan validado. Se compara contra 45 min de evaluación manual. **Ese valor es una estimación del
equipo; si Jabil da un dato real, se cambia en la variable `ERGOAI_MINUTOS_EVALUACION_MANUAL`.**
Se muestra en la Bandeja ("Impacto en tiempos de respuesta") y en cada informe.

---

## 3. Manejo de datos

- **Sin base de datos:** `casos_jabil_workspace/` guarda una carpeta por caso con `caso.json`,
  `session_state.json`, `audit_trail.json` y la carpeta `inputs/` con las fotos. En la raíz están
  `bitacora.json` y `alertas.json`.
- **Escritura atómica:** se escribe a un archivo temporal, se fuerza a disco y luego se reemplaza. Un corte
  de luz no deja archivos a medias.
- **Privacidad:** los rostros se difuminan y se eliminan los metadatos de la foto antes de guardarla. No se
  guardan datos biométricos faciales. No se envía nada a internet: los modelos corren localmente.
- **Las alertas van solo a ergonomía, IE y EHS**, nunca al operador.
- **Los datos de Jabil** se quedan en la computadora local.

---

## 4. Límites conocidos

- **Precisión de ángulos no validada con fotos reales de Jabil** al momento de escribir esto. Las fotos 2D
  tienen error de perspectiva si la cámara no está perpendicular al operador.
- **La torsión del tronco** no se mide automáticamente: se marca a mano.
- **Hombro elevado y brazo apoyado** se capturan a mano.
- **Carga, agarre y actividad** no salen de la foto: los captura el especialista.
- **Valores NOM-036** de levantamiento y transporte por verificar contra la hoja oficial. En empuje y
  arrastre se capturan a mano.
- **Sin usuarios ni contraseñas:** el rol se elige en la barra superior (prototipo).
- **Una persona por caso.** No se evalúa a todos los operadores de la foto.
- **Video y cámaras de planta:** no se procesan (fuera del alcance del prototipo; propuesta de Fase 2).

---

## 5. Instrucciones para reproducir

Requisitos: Windows 10/11, Python 3.11+ y Node 18+.

```powershell
git clone https://github.com/sebastianpea/ErgoAI.git ; cd ErgoAI ; git checkout front-end
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt -r backend/requirements-vision.txt
.venv\Scripts\python -m backend.app.vision.modelos      # descarga los modelos (~150 MB), una vez
cd frontend ; npm install ; cd ..
iniciar_demo.bat                                         # abre backend, frontend y navegador
```

- Pruebas: `.venv\Scripts\python -m unittest discover -s tests -p "test_*.py"`.
- Documentación interactiva de la API: http://localhost:8000/docs.
- Para reiniciar la demo desde cero, se borra la carpeta `casos_jabil_workspace/`.
