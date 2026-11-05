# ErgoAI — Copiloto Auditor de Ergonomía Industrial

Sistema de auditoría ergonómica asistida por visión artificial para estaciones de manufactura (Track 4: Jabil / Reto X-RAIC 2026), diseñado conforme a la **NOM-036-1-STPS-2018** y al estándar corporativo **Jabil 16-PE30-6500-00023**.

---

## 1. Propósito del Sistema

ErgoAI actúa como un copiloto técnico para especialistas de ergonomía e ingeniería industrial. A partir de 1 a 3 fotografías estáticas de una estación de trabajo (`Lateral`, `Frontal`, `Aérea`), el sistema extrae la cinemática articular del operario, calcula el nivel de riesgo postural **REBA**, verifica las reglas de planta y simula el **riesgo residual** tras aplicar controles de ingeniería.

---

## 2. Decisiones de Diseño: ¿Por qué se construyó así?

### A. Visión Artificial Top-Down con 133 Puntos (`YOLOX` + `RTMPose WholeBody-133`)
* **¿Por qué este enfoque?** Los modelos convencionales de 17 puntos (COCO) no capturan la desviación de la muñeca ni el apoyo plantar, ambos obligatorios en el método REBA. Con **RTMPose WholeBody-133** se obtienen 21 puntos por mano, pies y puntos craneales, logrando medir flexión/desviación de muñeca y ángulos cervicales incluso cuando el operario tiene el rostro anonimizado o cubierto por privacidad.
* **Ejecución en ONNX Runtime:** Permite inferencia local en milisegundos (~200 ms) tanto en GPU como en CPU sin depender de servicios en la nube ni conexión a internet en planta.

### B. Cálculo Determinista y Cero Alucinaciones (`np.arctan2` + Tablas REBA Oficiales)
* **¿Por qué no usar un LLM para calificar el riesgo?** Una auditoría normativa ante la STPS o EHS requiere trazabilidad matemática exacta. En ErgoAI, la red neuronal solo entrega coordenadas $(x, y)$; los ángulos ($G_1$ a $G_7$) se calculan con trigonometría vectorial pura y el puntaje final (1 a 15) se obtiene de las matrices oficiales de Hignett & McAtamney (2000), garantizando **100% de reproducibilidad y cero alucinaciones**.

### C. Arquitectura Limpia y Fuente Única de Verdad (SSOT)
* **¿Por qué separar el dominio de la infraestructura?** Las reglas de la **NOM-036**, los umbrales **Jabil** (como el límite estricto de **14 kg** en manejo manual de carga y **$\ge 80\text{ cm}$** de separación entre operarios en Regla F2) y las constantes biomecánicas viven aisladas en `src/ergoai/domain/` y `configs/vision_config.json` validados con **Pydantic**. Esto evita valores mágicos dispersos y permite auditar o actualizar normas en un solo lugar.

### D. Jerarquía de Controles y Gobernanza *Human-in-the-Loop* (HITL)
* **¿Por qué priorizar ingeniería y exigir firma humana?**
  1. **Prelación Normativa:** La NOM-036 exige priorizar modificaciones físicas en la estación (asistencias mecánicas *lifters*, reubicación a Zonas de Alcance 1 y 2 $\le 400\text{ mm}$, ajuste de altura de mesa) sobre controles administrativos.
  2. **Seguridad Operativa:** El sistema no envía alertas directas al operador de línea para evitar distracciones en planta; emite diagnósticos y proyecciones de **riesgo residual** que el especialista valida y aprueba antes de convertirse en acciones de piso (`outputs/audit_log.json`).

### E. Interfaz Minimalista y Anotación por Excepción
* **¿Por qué un diseño sobrio?** Para reducir la carga cognitiva del ingeniero durante inspecciones rápidas. La interfaz concentra en una sola vista la carga de tomas, el esqueleto anotado (resaltando únicamente las articulaciones que exceden umbrales), los 6 ángulos medidos y el dictamen REBA con su simulación de mejora.

---

## 3. Estructura del Proyecto

```text
ErgoAI/
├── ARCHITECTURE.md               # Marco arquitectónico e invariantes del dominio
├── requirements.txt              # Dependencias y comandos de instalación/arranque
├── pyproject.toml                # Configuración del paquete y suite de pruebas
├── start_web.py / run_web.sh     # Arranque automático del servidor web
├── configs/
│   └── vision_config.json        # Umbrales y parámetros visuales validados con Pydantic
├── src/ergoai/
│   ├── config/                   # Descubrimiento dinámico de recursos y esquemas
│   ├── domain/                   # Lógica pura: REBA, geometría vectorial, reglas Jabil y simulación
│   ├── services/                 # Pipeline RTMPose, clasificador de escena, anotador e informes HTML/PDF
│   └── web/                      # API REST FastAPI y panel web de auditoría
└── tests/                        # 43 pruebas unitarias y de integración
```

---

## 4. Instalación y Ejecución

```bash
# 1. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar librerías requeridas
pip install --upgrade pip
pip install -r requirements.txt

# 3. Iniciar la aplicación web (http://127.0.0.1:8000)
python start_web.py

# 4. Ejecutar pruebas automatizadas
pytest tests/ -v
```
