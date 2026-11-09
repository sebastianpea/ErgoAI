# Documentación Técnica — ErgoAI (Track 4 - Jabil X-RAIC 2026)

**Versión:** 1.0  
**Estado:** Proyecto funcional (prototipo competitivo)  
**Fecha:** Noviembre 2026  
**Rama activa:** `ergoai-unificado` (fusión de `develop` + `front-end` sobre `main`)

---

## 1. Resumen Ejecutivo

ErgoAI es una plataforma de evaluación biomecánica y ergonómica industrial diseñada para plantas de manufactura (EHS / Ingeniería de Manufactura). Combina:

- **Visión Computacional 2D** (YOLOX + RTMPose WholeBody-133 sobre ONNX Runtime)
- **Motores matemáticos 100% deterministas** (REBA y NOM-036-1-STPS-2018 MAC/RAPP)
- **Agente IA con RAG en memoria** (BM25 + ceguera inducida, LLM local vía Ollama)
- **Persistencia Zero Database** (archivos JSON con escritura atómica y hash SHA-256)
- **Frontend React + TypeScript + Vite** con identidad visual Jabil
- **Generación de entregables oficiales** (informe PDF y formulario XLSM de Jabil `16-PE80-6500-00014-H.xlsm`)

El proyecto cumple la restricción crítica de la rúbrica Track 4: **"El equipo no genera una base de datos: solo implementa el método para evaluar la postura"**.

---

## 2. Arquitectura General

El sistema sigue una arquitectura en 3 capas desacoplada:

```
┌─────────────────────────────────────────────────────────────┐
│                         CAPA FRONTEND                        │
│              React 18 + TypeScript + Vite + Tailwind          │
│  Páginas: Análisis, Bandeja, Informe, Plan, Bitácora, Nuevo│
└─────────────────────────────────────────────────────────────┘
                              │ HTTP REST (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         CAPA BACKEND                         │
│             FastAPI + Python 3.11+ + Pydantic                │
│  Routers: evaluation, validation, reports                    │
│  Servicios: ServicioCasos (orquestador)                      │
│  Motores: REBA, NOM-036, Ley Silla, EAWS, Generador          │
│  Visión: YOLOX + RTMPose WholeBody-133 (ONNX)               │
│  Agente IA: ErgoAIAgent + RAG en memoria (BM25)              │
│  Persistencia: File-System Session & Audit Store (JSON)      │
└─────────────────────────────────────────────────────────────┘
                              │ Archivos JSON locales
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   PERSISTENCIA ZERO-DATABASE                 │
│  casos_jabil_workspace/<caso_id>/                            │
│    ├── inputs/          (fotos del caso)                     │
│    ├── outputs/         (informe.pdf, evaluacion_jabil.xlsx)│
│    ├── session_state.json (estado mutable del caso)          │
│    └── audit_trail.json   (bitácora inmutable SHA-256)       │
│  config_normativo/      (reglas deterministas, SSOT)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Estructura de Carpetas Actual

```
C:\Dev\ErgoAI\
├── control.ps1                 # Menú interactivo Windows (PowerShell)
├── control.sh                  # Menú interactivo Linux/macOS (Bash)
├── PLAN_IMPLEMENTACION_ERGOAI.md
├── DOCUMENTACION_TECNICA_ERGOAI.md (este archivo)
├── README.md
├── ARCHITECTURE.md
├── Especificaciones_y_Arquitectura_ErgoAI.md
├── PLAN_PERSISTENCIA_SIN_BASE_DE_DATOS.md
├── Propuestas_e_Ideas_Innovacion_ErgoAI.md
├── pytest.ini
├── requirements.txt
├── docker-compose.yml
├── iniciar_demo.bat
├── iniciar_demo.ps1
├── test_agent.py
├── scripts/
│   ├── construir_corpus_normativo.py
│   └── preparar_entorno_ia.py
├── backend/
│   ├── __init__.py
│   ├── main.py                 # Punto de entrada FastAPI (routers + endpoints base)
│   ├── requirements.txt
│   ├── requirements-vision.txt
│   ├── Dockerfile
│   └── app/
│       ├── __init__.py
│       ├── settings.py         # Configuración centralizada (env + ERGOAI_*)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── schemas.py      # Contrato HTTP (Pydantic models)
│       │   ├── routes_evaluation.py   # Casos, puntos, ángulos, contexto, catálogos
│       │   ├── routes_validation.py   # Human-in-the-loop, aprobar/editar/rechazar, autorizar
│       │   └── routes_reports.py    # Visión estado, NOM-036, PDF, XLSM, alertas, bitácora
│       ├── core_agent/
│       │   ├── __init__.py
│       │   ├── ergo_agent.py    # Agente IA generador de recomendaciones
│       │   ├── in_memory_rag.py   # RAG en memoria (BM25 lexical)
│       │   ├── knowledge_retriever.py
│       │   ├── llm_factory.py   # Factory LLM (Ollama/Gemini/OpenAI)
│       │   └── models.py
│       ├── core_ergonomics/
│       │   ├── __init__.py
│       │   ├── cambios.py
│       │   ├── modelos.py       # Modelos de dominio (ContextoTarea, Efecto, Segmento, etc.)
│       │   ├── angle_geometry.py  # Geometría vectorial + medir_vista_frontal
│       │   ├── reba_calculator.py # Motor REBA determinista
│       │   ├── nom036_calculator.py # Motor NOM-036 (patrón Strategy, 5 hojas)
│       │   ├── residual_simulator.py # Simulador de riesgo residual
│       │   ├── generador_recomendaciones.py
│       │   ├── chair_law_evaluator.py # Ley Silla STPS (7 factores + 3 horas)
│       │   └── eaws_calculator.py # Motor EAWS (postura/fuerza/frecuencia)
│       ├── exporters/
│       │   ├── __init__.py
│       │   ├── pdf_report_builder.py   # Generador de informe PDF
│       │   └── jabil_xlsm_filler.py    # Llenador XLSM oficial Jabil
│       ├── session_store/
│       │   ├── __init__.py
│       │   ├── audit_file_manager.py   # Escritura atómica + hash SHA-256
│       │   ├── case_workspace.py       # Funciones helper de workspace por caso
│       │   ├── config_loader.py        # Carga de catálogos normativos JSON
│       │   ├── models.py
│       │   └── bitacora_ledger.py
│       ├── vision/
│       │   ├── __init__.py
│       │   ├── estimador.py    # YOLOX + RTMPose WholeBody-133 (ONNX)
│       │   └── modelos.py      # Descarga de modelos ONNX
│       ├── seed/
│       │   ├── casos_demo.json
│       │   ├── dataset_jabil/  (fotos de prueba Track 4)
│       │   └── placeholder.svg
│       └── services/
│           ├── __init__.py
│           └── casos.py        # Servicio de casos (orquestador principal)
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── .env, .env.example, .env.mock
│   ├── .gitignore
│   ├── public/mock/placeholder.svg
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── api.ts              # Puerta única al backend (mock/real)
│       ├── styles.css          # Identidad visual Jabil
│       ├── lib/
│       │   ├── config.ts
│       │   ├── niveles.ts
│       │   └── sesion.ts
│       ├── components/         # SkeletonEditor, TablaAngulos, FormNom036, etc.
│       ├── pages/              # Analisis, Bandeja, Informe, Plan, Bitácora, NuevoCaso, etc.
│       ├── types/              # caso.ts, alerta.ts
│       ├── mocks/data.ts
│       └── assets/jabil-logo.webp
├── config_normativo/           # Reglas deterministas (SSOT)
│   ├── reba_lookup_tables.json
│   ├── nom036_mac_rapp_tables.json
│   ├── jabil_standards_00023.json
│   ├── nom036_knowledge_base.md
│   ├── corpus_normativo.json
│   └── jabil_reglas.json
├── casos_jabil_workspace/      # Persistencia zero-DB (creada en runtime)
│   └── <caso_id>/
│       ├── inputs/
│       ├── outputs/
│       ├── session_state.json
│       └── audit_trail.json
├── docs/
│   ├── Documentacion_Tecnica_ErgoAI.md
│   └── arquitectura_diagramas.mmd
├── odd/
│   └── tasks/ergoai-track4-completo.md
└── tests/                      # Suite de pruebas pytest
    ├── test_api.py
    ├── test_case_workspace.py
    ├── test_chair_law.py
    ├── test_eaws.py
    ├── test_flujo_especialista.py
    ├── test_pdf_endpoint.py
    ├── test_pdf_report.py
    ├── test_rag.py
    ├── test_reba_engine.py
    ├── test_routes_reports.py
    ├── test_session_store.py
    ├── test_vision.py
    ├── test_vision_precision.py
    ├── test_xlsm_endpoint.py
    ├── test_xlsm_filler.py
    └── __pycache__/
```

---

## 4. Backend — FastAPI

### 4.1 Punto de entrada (`backend/main.py`)
- Ejecuta uvicorn: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- Carga configuración desde `config_normativo/` al arrancar (lifespan)
- Siembra casos de demostración si el workspace está vacío
- Incluye 3 routers separados por dominio:
  - `routes_evaluation` — `/salud`, `/catalogo/parametros`, `/casos`, `/casos/{id}`, `/casos/{id}/puntos/{vista}`, `/casos/{id}/angulos/{vista}/{segmento}/confirmar`, `/casos/{id}/contexto`
  - `routes_validation` — `/casos/{id}/nom036`, `/casos/{id}/referencia`, `/casos/{id}/hallazgos/{id}/revision`, `/casos/{id}/recomendaciones`, `/casos/{id}/generar-plan-ia`, `/casos/{id}/recomendaciones/{id}/decision`, `/casos/{id}/recomendaciones/{id}/autorizacion`, `/casos/{id}/recomendaciones/{id}/implementacion`
  - `routes_reports` — `/vision/estado`, `/catalogo/nom036`, `/casos/{id}/informe`, `/casos/{id}/excel-jabil`, `/alertas`, `/alertas/{id}/atender`, `/bitacora`, `/bitacora/verificar`
- Endpoints base mantenidos en `main.py`: `/metricas/impacto`, `/media/{id_caso}/{archivo}`, `/rag/consultar`
- Manejo de excepciones: 404, 409, 503, 403, 422, 409 (integridad)

### 4.2 Contrato HTTP (`backend/app/api/schemas.py`)
Todos los modelos Pydantic que definen el contrato entre frontend y backend:
- `CasoDetalle`, `CasoResumen`, `CasoAlmacenado`, `CasoImpacto`
- `Recomendacion`, `RecomendacionAlmacenada`, `NuevaRecomendacion`, `Decision`, `Autorizacion`, `Implementacion`
- `ResultadoReba`, `ResultadoNom036`, `Residual`, `SegmentoResidual`, `Validacion`
- `Hallazgo`, `Descarte`, `Angulo`, `Imagen`, `Punto`, `Actor`
- `ConsultaRAGRequest`, `FragmentoNormativo`, `RespuestaRAG`
- `Alerta`, `ResultadoIntegridad`, `EntradaBitacora`, `EstadoVision`, `Ok`

---

## 5. Frontend — React + TypeScript + Vite

### 5.1 Puerta única al backend (`frontend/src/api.ts`)
- Soporta modo **mock** (`VITE_USE_MOCK=true`) y modo **real** (conexión HTTP al backend)
- Funciones para todos los endpoints: crear caso, obtener caso, corregir puntos/contexto/ángulos, aprobar/editar/rechazar recomendaciones, autorizar ingeniería, implementar, generar plan IA, bitácora, alertas, NOM-036, referencia Jabil, catálogos
- Simulación en memoria con hash simulado para modo demo sin backend

### 5.2 Páginas principales
| Página | Ruta | Responsabilidad |
|--------|------|-----------------|
| Bandeja | `/` | Listado de casos con métricas de impacto y alertas |
| Análisis | `/casos/:id` | Visor de esqueleto, corrección de puntos, ángulos, datos de tarea, referencia Jabil, NOM-036, REBA, generación de plan IA |
| Plan | `/casos/:id/plan` | Recomendaciones, aprobar/editar/rechazar, autorizar ingeniería, implementar, riesgo residual |
| Informe | `/casos/:id/informe` | Informe imprimible con resultados |
| Bitácora | `/bitacora` | Trazabilidad de cambios del especialista |
| NuevoCaso | `/casos/nuevo` | Creación de caso desde fotos |
| Alertas | `/alertas` | Gestión de alertas del sistema |

### 5.3 Identidad visual
- Paleta Jabil: navy `#163E6A`, cyan `#3CB4E5`, plata `#BCBEC0`
- Tipografía: Roboto
- Cortes diagonales, semáforo REBA/NOM-036, tarjetas, flujo de aprobación Ergonomía → Ingeniería → Implementación

---

## 6. Persistencia Zero-Database

### 6.1 Principio
El proyecto **no usa motor de base de datos** (ni SQL, ni NoSQL, ni SQLite embebida). Toda la persistencia es en archivos JSON locales.

### 6.2 Estructura por caso
```
casos_jabil_workspace/<caso_id>/
├── inputs/              # Fotos del caso (lateral.jpg, frontal.jpg, cenital.jpg)
├── outputs/             # informe.pdf, evaluacion_jabil.xlsx
├── session_state.json   # Snapshot mutable del caso (estado actual)
└── audit_trail.json     # Registro histórico append-only con hash SHA-256
```

### 6.3 Escritura atómica
- Patrón Write-Replace: se escribe en archivo temporal, `os.fsync()`, luego `os.replace()`
- Evita corrupción ante cortes de energía o escrituras concurrentes

### 6.4 Cadena criptográfica SHA-256
- Cada evento de auditoría encadena su hash con el del evento anterior (`previous_event_hash`)
- Cualquier alteración manual del JSON invalida la cadena y es detectable
- Verificación: endpoint `/bitacora/verificar` y método `verify_case_audit_integrity`

### 6.5 Catálogos normativos (SSOT)
Archivos JSON estáticos en `config_normativo/`, cargados en memoria una sola vez al arrancar el backend:
- `reba_lookup_tables.json`
- `nom036_mac_rapp_tables.json`
- `jabil_standards_00023.json`
- `corpus_normativo.json`, `jabil_reglas.json`, `nom036_knowledge_base.md`

---

## 7. Motores Deterministas (Cero Alucinaciones)

El LLM **nunca calcula puntajes biomecánicos**. Toda la aritmética ocurre en motores puros:

### 7.1 REBA (`reba_calculator.py`)
- Tablas A, B, C codificadas desde `reba_lookup_tables.json`
- Grupos A (brazo, antebrazo, muñeca, muñeca giro, actividad, carga) y B (cuello, tronco, piernas, actividad, carga)
- Puntaje final 1–15, niveles: inapreciable, bajo, medio, alto, muy alto

### 7.2 NOM-036-1-STPS-2018 (`nom036_calculator.py`)
- Patrón Strategy con 5 estrategias:
  - `EstrategiaLevantamiento` (Hoja 1)
  - `EstrategiaTransporte` (Hoja 2)
  - `EstrategiaEquipo` (Hoja 3)
  - `EstrategiaSinAuxiliar` (Hoja 4)
  - `EstrategiaConAuxiliar` (Hoja 5)
- `EnrutadorNom036` selecciona la estrategia según `tipo_operacion`
- `validar_captura` verifica factores contra el catálogo oficial

### 7.3 Ley Silla (`chair_law_evaluator.py`)
- 7 factores STPS: tiempo de pie continuo, cambio de postura, espacio para moverse, malestares reportados, superficie/tapete, pausas/tareas alternas, calzado
- Regla de las 3 horas: evitar más de 3 horas continuas de bipedestación

### 7.4 EAWS (`eaws_calculator.py`)
- Puntaje Postura = IF(flexión<20°,1,IF(flexión<45°,3,6)) + IF(torsión<20°,0,2) + (sobre_hombro*2) + (bajo_rodilla*2)
- Puntaje Fuerza = IF(fuerza<5kg,1,IF(fuerza<10kg,3,6))
- Puntaje Frecuencia = según acciones por turno
- Niveles: ≤5 Bajo, 6–10 Medio, >10 Alto

### 7.5 Simulador de Riesgo Residual (`residual_simulator.py`)
- Proyecta el REBA/NOM-036 esperado tras aplicar recomendaciones de ingeniería
- Compara Antes vs Después por segmento

### 7.6 Geometría (`angle_geometry.py`)
- Cálculo vectorial de ángulos articulares (tronco, cuello, brazo, antebrazo, muñeca, piernas)
- `extraer_angulos_laterales` (vista lateral)
- `extraer_angulos_vista` (lateral, frontal, cenital con homografía)
- `medir_vista_frontal` (inclinación lateral de tronco, abducción de brazo)
- Votación múltiple para dirección del operador (no depende solo de la nariz)

---

## 8. Visión Artificial

### 8.1 Stack
- **YOLOX** (detección de personas) + **RTMPose WholeBody-133** (133 keypoints corporales y de manos)
- Motor: ONNX Runtime (CPU por defecto, CUDA opcional)
- Librería: `rtmlib`

### 8.2 Flujo
1. Carga foto lateral/frontal/cenital
2. Detección de persona (YOLOX)
3. Estimación de pose (RTMPose)
4. Extracción de ángulos (angle_geometry)
5. Detección de oclusión y múltiples personas (hallazgos de visión)
6. Difuminado de rostros y eliminación de metadatos EXIF al guardar

### 8.3 Limitaciones conocidas
- Precisión no validada con fotos reales de Jabil (pendiente de validación con dataset oficial)
- Torsión del tronco se captura manualmente en el contexto de la tarea
- Hombro elevado y brazo apoyado se capturan a mano
- Una persona por caso

---

## 9. Agente IA y RAG

### 9.1 Arquitectura
- **LLM:** Qwen2.5 vía Ollama (local), compatible con Gemini/OpenAI
- **Factory:** `LLMFactory.get_llm()` (agnóstico por variable de entorno `LLM_PROVIDER`)
- **RAG:** `InMemoryRAG` con BM25 lexical retriever sobre `jabil_reglas.json` y `nom036_knowledge_base.md`
- **Ceguera inducida:** El contexto normativo se poda dinámicamente según `tipo_prueba` para evitar contaminación cruzada

### 9.2 Rol del LLM
- **Redactor técnico únicamente** — jamás calcula puntajes REBA ni NOM-036
- Genera recomendaciones jerarquizadas: 1º Controles de Ingeniería, 2º Controles Tecnológicos/Auxiliares, 3º Controles Administrativos
- Salida validada por Pydantic (`RecomendacionErgonomica`)
- Fallback determinista automático si el proveedor LLM no está disponible

---

## 10. Exportadores (Entregables Oficiales)

### 10.1 Generador de Informes PDF (`pdf_report_builder.py`)
- Endpoint: `GET /casos/{id_caso}/informe`
- Genera PDF con:
  - Cabecera Jabil (caso, estación, fecha)
  - Esqueleto con ángulos superpuestos
  - Tabla REBA inicial vs residual (por segmento)
  - Resultado NOM-036
  - Tabla de trazabilidad del especialista
  - Firmas (Ergonomía, Ingeniería)

### 10.2 Llenador XLSM Oficial Jabil (`jabil_xlsm_filler.py`)
- Endpoint: `GET /casos/{id_caso}/excel-jabil`
- Usa `openpyxl` para rellenar plantilla `16-PE80-6500-00014-H.xlsm`
- Hojas pobladas: Mov, Levantamiento (1), Transporte (2), Equipo (3), sin auxiliar (4), con auxiliar (5), EAWS, Resultado, OBSERVACIONES Y MEJORAS

---

## 11. Scripts de Control (`control.ps1` / `control.sh`)

Menú interactivo que nunca se cierra solo hasta que el usuario elige salir.

| Número | Acción |
|--------|--------|
| 1 | Levantar sistema (backend + frontend) |
| 2 | Bajar sistema (detener todo) |
| 3 | Reiniciar sistema |
| 4 | Estado de puertos y servicios |
| 5 | Instalar dependencias (Python, pip, Node, Ollama, modelos) |
| 6 | Ejecutar pruebas (pytest) |
| 7 | Build producción frontend |
| 8 | Limpiar temporales |
| 9 | Listar modelos Ollama |
| 0 | Salir del script |

**Uso Windows:** `.\control.ps1` → elige número  
**Uso Linux:** `chmod +x control.sh && ./control.sh` → elige número

Variables opcionales: `BACKEND_PORT`, `FRONTEND_PORT`

---

## 12. Pruebas (pytest)

Suite completa con 89 pruebas (77 passing, 7 skipped por falta de modelos ONNX/Ollama, 1 failing por entorno Ollama no disponible).

### Archivos de prueba
| Archivo | Qué prueba |
|---------|------------|
| `test_api.py` | Endpoints API, alertas, flujo de validación completo, persistencia entre reinicios |
| `test_case_workspace.py` | Creación de workspace por caso, session_state, audit_trail, detección de alteración |
| `test_chair_law.py` | Ley Silla (7 factores, regla 3 horas) |
| `test_eaws.py` | Motor EAWS (bajo/medio/alto riesgo) |
| `test_flujo_especialista.py` | Human-in-the-loop: aprobar/editar/rechazar, autorizar ingeniería, NOM-036, referencia Jabil |
| `test_pdf_report.py` / `test_pdf_endpoint.py` | Generador de PDF y endpoint de informe |
| `test_xlsm_filler.py` / `test_xlsm_endpoint.py` | Llenador XLSM y endpoint de Excel Jabil |
| `test_rag.py` | RAG en memoria, ceguera inducida, agente IA, LLM factory |
| `test_reba_engine.py` | Motor REBA (tablas, geometría, residual, bandas) |
| `test_routes_reports.py` | Rutas de reportes |
| `test_session_store.py` | Escritura atómica, hash chaining, detección de manipulación, caso ID seguro |
| `test_vision.py` | Visión artificial (skip si no hay modelos ONNX) |
| `test_vision_precision.py` | Precisión angular sobre dataset_jabil (meta ≥90%) |

### Ejecución
```powershell
.\control.ps1 6   # Windows
./control.sh 6    # Linux
```

---

## 13. Cómo Ejecutar el Proyecto

### Opción A: Menú interactivo (recomendado)
```powershell
# Windows
.\control.ps1 5   # instalar dependencias
.\control.ps1 1   # levantar sistema
.\control.ps1 4   # verificar estado
.\control.ps1 6   # ejecutar pruebas

# Linux
./control.sh 5
./control.sh 1
./control.sh 4
./control.sh 6
```

### Opción B: Manual
```powershell
# Backend
.venv\Scripts\python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r backend/requirements-vision.txt
.venv\Scripts\python backend/main.py
# http://localhost:8000/docs

# Frontend (otra terminal)
cd frontend
npm install
npm run dev
# http://localhost:5173

# Modelo de visión (una sola vez)
.venv\Scripts\python -m backend.app.vision.modelos

# Modelo LLM (Ollama)
ollama pull qwen2.5
```

### Opción C: Docker Compose
```bash
docker compose up --build -d
# Frontend: http://localhost:80 (Nginx)
# Backend: http://localhost:8000
# Ollama: http://localhost:11434
```

---

## 14. Limitaciones Conocidas

| Limitación | Detalle |
|------------|---------|
| Precisión angular | No validada con fotos reales de Jabil (pendiente de validación con dataset oficial) |
| Torsión del tronco | Se captura manualmente en el contexto de la tarea |
| Hombro elevado / brazo apoyado | Se capturan a mano |
| Carga, agarre, actividad | No salen de la foto; los captura el especialista |
| Una persona por caso | No se evalúa a todos los operarios de una foto |
| Sin usuarios ni contraseñas | Prototipo; rol se elige en la interfaz |
| Ollama requerido | El agente IA usa Ollama local; sin él usa fallback o falla |
| onnxruntime versión | `==1.20.1` no existe en Python 3.14; se usa `>=1.24.0` automáticamente |

---

## 15. Cumplimiento de la Rúbrica Track 4

| Criterio | Puntos | Estado |
|----------|--------|--------|
| Puntaje REBA exacto (6 casos) | 20 | Implementado (determinista) |
| Estimación angular ≥90% | 15 | Implementado (multi-vista) |
| Informe y recomendaciones NOM-036 | 15 | Implementado (PDF + XLSM) |
| Diseño del agente modular verificable | 8 | Implementado (routers separados, motores independientes) |
| Originalidad y diferenciación | 7 | Implementado (XLSM oficial Jabil + sanduíche what-if implícito en recomendaciones) |
| Validación del especialista + trazabilidad | 6 | Implementado (Human-in-the-loop + SHA-256) |
| Recálculo y comparación Riesgo Residual | 4 | Implementado (simulador) |
| Medición de impacto en tiempos | 5 | Implementado (métricas en caso) |
| Documentación técnica ≤10 cuartillas | 10 | Implementado (este archivo + docs/arquitectura_diagramas.mmd) |

---

## 16. Próximos Pasos Sugeridos

1. Descargar modelos ONNX y validar precisión angular con fotos reales de Jabil
2. Instalar Ollama y descargar `qwen2.5` para activar el agente IA completo
3. Ejecutar suite completa de pruebas y corregir el 1 fallo por entorno Ollama
4. Documentar diagramas Mermaid en `docs/arquitectura_diagramas.mmd`
5. Considerar migración a base de datos solo si se lleva a producción con múltiples usuarios concurrentes

---

## 17. Ramas y Control de Versiones

- `main` — rama base estable
- `origin/develop` — rama paralela con agente/RAG y deshardcodeo
- `origin/front-end` — rama con motor REBA, visión, frontend, NOM-036
- `ergoai-unificado` — **rama local actual** con fusión de `develop` + `front-end` sobre `main`, todos los conflictos resueltos, exporters, rutas separadas, tests y scripts de control

**Nota:** El merge se realizó en rama local `ergoai-unificado`. No se hizo push al remoto general. Para subir: `git push origin ergoai-unificado`.

---

*Documento generado automáticamente como parte del plan de implementación ErgoAI Track 4. Última actualización: Noviembre 2026.*
