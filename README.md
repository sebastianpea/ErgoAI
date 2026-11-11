# ErgoAI — Sistema de Evaluación Ergonómica Industrial y Agente RAG Normativo

**ErgoAI** es una plataforma integral de evaluación biomecánica y ergonómica industrial diseñada para plantas de manufactura (EHS / Ingeniería de Manufactura). Combina **Visión Computacional 2D (YOLOX + RTMPose/RTMW WholeBody-133 ONNX)**, **motores matemáticos 100% deterministas (REBA y NOM-036-1-STPS-2018 MAC/RAPP)**, **Recuperación Aumentada por Generación en Memoria (BM25 + Ceguera Inducida)**, **Agentes LLM locales/cloud con validación estricta Pydantic**, y una **bitácora de auditoría con integridad verificable mediante SHA-256**, operando bajo una arquitectura **Zero Database**.

---

## Documentación Detallada

- **[Estado actual y decisiones vigentes](docs/ESTADO_ACTUAL.md)**: empezar aquí para distinguir implementación, antecedentes y validaciones pendientes. Archivos ahora; SQLite solo como alternativa futura autorizada.

- **[Arquitectura, Auditoría Anti-Hardcode, Logros y Guía de Ejecución (`docs/ARQUITECTURA_Y_GUIA_EJECUCION.md`)](docs/ARQUITECTURA_Y_GUIA_EJECUCION.md)**: Antecedente histórico de decisiones y logros; para ejecución vigente usar este README y el índice actual.
- **[Especificación Arquitectónica Base (`ARCHITECTURE.md`)](ARCHITECTURE.md)**: Reglas estructurales de Clean Architecture, separación de capas y principios inquebrantables.

---

## ¿Por qué se diseñó así? (Principios Arquitectónicos Clave)

1. **Separación Estricta entre Matemática Determinista y Redacción Generativa (Cero Alucinaciones Numéricas)**
   - Los modelos de lenguaje (LLMs) **jamás calculan puntajes biomecánicos ni evalúan tablas legales**. Toda la aritmética ergonómica ocurre en motores puros en Python (`REBACalculator`, `NOM036Calculator`, `GeneradorRecomendaciones`) alimentados por catálogos JSON auditables en `config_normativo/`. El LLM (`ErgonomicAgent`) actúa únicamente como redactor técnico estructurado con salida validada por Pydantic (`RecomendacionErgonomica`) y *fallback* determinista automático si el proveedor LLM no está disponible.

2. **Centralización de Configuración (SSOT como objetivo)**
   - Tablas y reglas se concentran en `config_normativo/` y la infraestructura en `backend/app/settings.py`; aún existen constantes y valores por defecto en calculadoras.
   - Cambiar una norma requiere cotejar originales, revisar consumidores y ejecutar pruebas: editar un JSON no certifica equivalencia normativa.

3. **Ceguera Inducida (*Context Pruning* Normativo)**
   - `InMemoryRAG` recupera cláusulas de `normative_rag_clauses` en `jabil_standards_00023.json`; `InMemoryNormativeRetriever` consulta reglas etiquetadas de `jabil_reglas.json`, con condiciones `requiere_alguno_de`.
   - El filtrado reduce contexto no pertinente, pero no acredita aislamiento absoluto ni sustituye la revisión del especialista. Ver [fuentes y límites actuales](docs/ESTADO_ACTUAL.md).

4. **Patrón *Strategy* para las 5 Hojas de Evaluación NOM-036-1-STPS-2018 (Apéndice I — MAC/RAPP)**
   - Cada modalidad física (`levantamiento`, `transporte`, `equipo`, `empuje_sin_auxiliar`, `empuje_con_auxiliar`) encapsula sus algoritmos en una clase estrategia independiente (`EstrategiaEvaluacionNOM036`), leyendo sus umbrales y bandas de color desde `config_normativo/nom036_mac_rapp_tables.json`.

5. **Arquitectura *Zero Database* con Persistencia Atómica y Cadena Criptográfica SHA-256**
   - No requiere PostgreSQL, SQLite, Redis ni bases vectoriales externas (Chroma/Qdrant).
   - Las escrituras son atómicas por archivo (`write temp` -> `os.fsync` -> `os.replace`), no transacciones entre archivos. La bitácora global es `bitacora.json`, enlazada por `hash_anterior`. SHA-256 detecta inconsistencias, pero no ofrece firma digital ni garantía legal; quien reescribe toda la cadena puede recalcularla.

---

## Cosas que se Lograron

- **Centralización de Configuración**:
  - **Configuración Centralizada (`backend/app/settings.py`)**: Soporte nativo de `.env` y parametrización de puertos, CORS, umbrales de visión, URLs de modelos ONNX, parámetros BM25 (`BM25_K1`, `BM25_B`), modelos por defecto (`OLLAMA_MODEL`, `GEMINI_DEFAULT_MODEL`, `OPENAI_DEFAULT_MODEL`) y usuarios por defecto.
  - **Catálogos de Motores Ergonómicos**: `REBACalculator`, `NOM036Calculator` y `GeneradorRecomendaciones` consumen tablas y parámetros de `reba_lookup_tables.json` y `nom036_mac_rapp_tables.json`.
  - **Reglas Corporativas Declarativas**: `jabil_reglas.json` define `requiere_alguno_de` por regla, eliminando condicionales con strings mágicos en Python (`knowledge_retriever.py`, `casos.py`, `test_agent.py`).
  - **Frontend sin URLs ni Reglas Duplicadas**: Proxy reverso unificado en Vite (`vite.config.ts`) y Nginx (`nginx.conf`) para `/casos`, `/alertas`, `/bitacora`, `/rag`, `/media`, `/vision`, `/catalogo` y `/salud`, evitando acoplar `http://localhost:8000` en el bundle de producción, y unificación del cálculo de niveles REBA en `frontend/src/lib/niveles.ts`.
- **Pipeline de Visión Computacional 2D Real sin GPU Obligatoria**:
  - Detección de personas con **YOLOX** y estimación de hasta **133 keypoints corporales y de mano** con **RTMPose / RTMW WholeBody-133** sobre `onnxruntime`, proyectando ángulos de tronco, cuello, hombro, codo, muñeca y rodilla en vistas lateral y cenital, con detección de oclusión y modo *Human-in-the-Loop* para confirmación o ajuste de ángulos.
- **Flujo Dual de Especialistas (Ergonomía + Ingeniería)**:
  - Segregación de permisos: los casos de riesgo alto (`REBA >= 8`) bloquean la aprobación unilateral por parte del rol de Ergonomía y exigen dictamen de Ingeniería de Manufactura.
- **Captura de Fotos y Diagnóstico Ergonómico en Vivo (Windows y Linux)**:
  - **Módulo Web Integrado (`CapturaCamaraModal.tsx`)**: Permite capturar fotos de las estaciones directamente desde la cámara web (WebRTC estándar 100% compatible en navegadores de Windows y Linux). Incluye enumeración de cámaras USB/internas, guía de encuadre ergonómico, diagnóstico instantáneo con esqueleto biomecánico superpuesto, tarjeta de riesgo REBA y desglose articular.
  - **Herramienta CLI Multiplataforma (`scripts/capturar_y_analizar.py`)**: Script autónomo en Python/OpenCV con detección automática de backend (`cv2.CAP_DSHOW` / `cv2.CAP_MSMF` en Windows, `cv2.CAP_V4L2` en Linux). Soporta modo interactivo con ventana en vivo, modo desatendido/temporizador (`--headless --timer`) para servidores/SSH/Docker y modo análisis de archivos de imagen (`--image`).
  - **Endpoint de Análisis Rápido (`POST /vision/analizar-rapido`)**: API REST que procesa la imagen con YOLOX + RTMPose WholeBody-133, calcula el REBA Score determinista y devuelve la imagen renderizada en Base64 con el esqueleto biomecánico colorizado según el nivel de riesgo.
- **Pruebas Automatizadas**:
  - Cobertura de regresión sobre cálculos REBA, las 5 estrategias NOM-036, RAG en memoria, Ceguera Inducida, Visión 2D (incluyendo endpoint de análisis rápido), API REST, control de roles y verificación criptográfica de la bitácora SHA-256.

---

## Instalación de Dependencias

El proyecto organiza sus dependencias en tres archivos `requirements.txt` para adaptarse tanto a entornos ligeros como a despliegues completos con visión computacional:

| Archivo | Propósito |
| :--- | :--- |
| [`requirements.txt`](requirements.txt) | **Instalador unificado raíz**: incluye todas las dependencias del backend + visión computacional ONNX. |
| [`backend/requirements.txt`](backend/requirements.txt) | Dependencias base del backend FastAPI, Pydantic, HTTPX y conectores LangChain/Ollama (`langchain-core`, `langchain-ollama`). |
| [`backend/requirements-vision.txt`](backend/requirements-vision.txt) | Dependencias del motor de visión 2D (`numpy`, `onnxruntime`, `opencv-python-headless`, `rtmlib`). |

### 1. Instalar dependencias de Python (Backend + Visión)

```bash
cd ErgoAI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

*(Opcional) Si desea instalar soporte para proveedores LLM en la nube (Gemini / OpenAI):*
```bash
pip install langchain-google-genai langchain-openai
```

### 2. Instalar dependencias de Node.js (Frontend React + TypeScript)

```bash
cd frontend
npm install
cd ..
```

---

## Cómo Correr el Proyecto

### Opción A: Ejecución Local en Modo Desarrollo (Recomendado para Desarrollo)

1. **(Opcional) Configurar variables de entorno**:
   ```bash
   cp .env.example .env
   ```

2. **Descargar modelos locales (Visión 2D + Ollama LLM)**:
   *(Cualquier miembro del equipo puede descargar y verificar todos los modelos locales ejecutando un solo comando:)*
   ```bash
   .venv/bin/python scripts/preparar_entorno_ia.py
   ```
   *O de forma manual:*
   - Visión ONNX: `.venv/bin/python -m backend.app.vision.modelos`
   - LLM Local: `ollama pull qwen2.5`

3. **Iniciar el Backend (FastAPI en puerto configurable `8000`)**:
   ```bash
   .venv/bin/python -m uvicorn backend.main:app --reload --port 8000
   ```
   - API interactiva (Swagger UI): `http://localhost:8000/docs`
   - Estado de salud y visión: `http://localhost:8000/salud` y `http://localhost:8000/vision/estado`

4. **Iniciar el Frontend (Vite en puerto `5173`)**:
   En otra terminal:
   ```bash
   cd frontend
   VITE_BACKEND_PROXY_TARGET=http://localhost:8000 npm run dev -- --port 5173
   ```
   En PowerShell, use `.venv\Scripts\python` para Python y defina `$env:VITE_BACKEND_PROXY_TARGET = "http://localhost:8000"` antes de `npm run dev -- --port 5173`. Sin configuración, Vite usa 5180 y proxy a 8080, mientras el backend usa 8000; por eso se alinean explícitamente.
   - Abra en el navegador: `http://localhost:5173`

---

### Opción B: Captura y Diagnóstico con Cámara (Windows y Linux)

ErgoAI ofrece dos formas de captura y análisis de fotografías:

#### 1. Desde la Aplicación Web (Recomendado para Evaluadores de Planta)
1. Navega a **"Nuevo Caso"** (`http://localhost:5173/casos/nuevo`).
2. Haz clic en **"⚡ Diagnóstico Rápido con Cámara"** o en el botón **"📷 Tomar con cámara"** en cualquiera de las vistas (lateral, frontal, cenital).
3. Selecciona tu cámara web preferida (soporta webcams integradas o cámaras USB externas en Windows y Linux sin controladores adicionales).
4. Alinea al operador en el visor utilizando las guías ergonómicas y presiona **"Capturar y Analizar REBA"**.
5. Observa el esqueleto biomecánico superpuesto, los ángulos articulares medidos y el REBA Score resultante. Si lo deseas, pulsa **"✓ Usar esta foto para Crear Caso"**.

#### 2. Desde la Línea de Comandos (CLI Script en Python)
Ideal para quioscos de ergonomía en piso de producción, pruebas de campo o automatización:
```bash
# Modo Interactivo con ventana de video en vivo (Espacio para capturar, Q para salir):
.venv/bin/python scripts/capturar_y_analizar.py

# En Windows seleccionando índice de cámara o backend DirectShow:
python scripts/capturar_y_analizar.py --camera 0

# Modo Headless con temporizador (útil para Docker, WSL o entornos sin servidor X11):
.venv/bin/python scripts/capturar_y_analizar.py --headless --timer 3 --output captura_planta.jpg

# Analizar una fotografía ya existente y generar el reporte visual anotado:
.venv/bin/python scripts/capturar_y_analizar.py --image backend/app/seed/dataset_jabil/lev_03_caja_lateral_perfil_C.jpg
```

---

### Opción C: Despliegue Completo con Docker Compose (Frontend + Backend + Ollama LLM)

El archivo [`docker-compose.yml`](docker-compose.yml) levanta servicios en la red `ergoai_net`. Requiere `.env`; el modelo por defecto es `qwen2.5` (configurable), pero Compose no lo descarga automáticamente. Con Ollama iniciado, aprovisionarlo con `docker compose exec llm_engine ollama pull qwen2.5` o el nombre configurado:

1. **Con aceleración GPU NVIDIA**:
   ```bash
   docker compose up --build -d
   ```

2. **En modo 100% CPU (sin GPU NVIDIA)**:
   Edite o comente la sección `deploy.resources.reservations.devices` del servicio `llm_engine` en `docker-compose.yml` y ejecute:
   ```bash
   docker compose up --build -d
   ```
   - Interfaz Web (Nginx): `http://localhost:5173` (host 5173 → contenedor 80 por defecto)
   - API Backend: `http://localhost:8000`

---

## Ejecución de Pruebas y Verificación

Para ejecutar las pruebas backend y frontend desde la raíz. Los conteos y resultados dependen del entorno; no se certifica precisión ni éxito de la suite por su mera existencia:

```bash
# pytest descubre también las funciones que unittest no ejecuta
.venv/bin/python -m pytest
node --test frontend/tests/*.test.mjs

# Ejecutar prueba rápida del Agente Ergonómico + Ceguera Inducida
.venv/bin/python test_agent.py

# Verificar tipado estricto TypeScript y build de producción del Frontend
cd frontend && npm run build
```
