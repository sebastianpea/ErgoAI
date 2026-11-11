# Documentación Técnica — ErgoAI (Track 4 - Jabil X-RAIC 2026)

> **Informe condensado histórico.** No certifica resultados actuales; comandos y descripción son antecedentes. Consultar [estado actual y ejecución vigente](ESTADO_ACTUAL.md) y [README](../README.md).

**Versión:** 1.0  
**Fecha:** Noviembre 2026  
**Extensión objetivo:** ≤10 cuartillas; pendiente de verificar en el entregable maquetado.

---

## 1. Arquitectura

ErgoAI es una aplicación de evaluación ergonómica industrial para plantas de manufactura (EHS / Ingeniería de Manufactura). Sigue una arquitectura en capas desacoplada:

- **Backend (FastAPI + Python):** API REST, motores deterministas (REBA, NOM-036), agente IA con RAG en memoria, persistencia zero-DB.
- **Frontend (React + TypeScript + Vite):** SPA para especialistas de Ergonomía e Ingeniería, con identidad visual Jabil.
- **Persistencia:** Archivos JSON locales (zero database) con escritura atómica y cadena criptográfica SHA-256.

Flujo de datos: fotos multi-vista → visión (YOLOX + RTMPose ONNX) → ángulos → motores deterministas → recomendaciones IA → validación humana → informe PDF / XLSM oficial Jabil.

---

## 2. Módulos principales

| Módulo | Ruta | Responsabilidad |
|--------|------|-----------------|
| API | `backend/main.py` | Punto de entrada FastAPI, routers, manejo de excepciones |
| Rutas evaluación | `backend/app/api/routes_evaluation.py` | Casos, puntos, ángulos, contexto, catálogos |
| Rutas validación | `backend/app/api/routes_validation.py` | Human-in-the-loop, aprobar/editar/rechazar, autorizar ingeniería |
| Rutas reportes | `backend/app/api/routes_reports.py` | Informe PDF, XLSM Jabil, visión estado, bitácora, alertas |
| Servicios | `backend/app/services/casos.py` | Orquestación de casos, visión, REBA, NOM-036, recomendaciones, bitácora |
| Visión | `backend/app/vision/` | YOLOX + RTMPose WholeBody-133 en ONNX Runtime |
| Ergonomía | `backend/app/core_ergonomics/` | Geometría, REBA, NOM-036 Strategy, Riesgo Residual, Ley Silla, EAWS |
| Persistencia | `backend/app/session_store/` | AuditFileManager, CaseWorkspace, Bitácora SHA-256 |
| Agente IA | `backend/app/core_agent/` | ErgoAIAgent, RAG en memoria, LLM factory, Knowledge Retriever |
| Exportadores | `backend/app/exporters/` | Generador PDF, Llenador XLSM oficial Jabil |

---

## 3. Motores deterministas (cero alucinaciones)

- **REBA:** Tablas A, B, C codificadas desde `config_normativo/reba_lookup_tables.json`. Cálculo vectorial de ángulos en `angle_geometry.py`.
- **NOM-036-1-STPS-2018:** Patrón Strategy con 5 hojas (Levantamiento, Transporte, Equipo, sin auxiliar, con auxiliar) desde `nom036_mac_rapp_tables.json`.
- **Riesgo Residual:** Simulación matemática que proyecta el REBA/NOM-036 tras aplicar recomendaciones de ingeniería.
- **Ley Silla:** 7 factores STPS + regla de las 3 horas de bipedestación.
- **EAWS:** Postura, fuerza y frecuencia con bandas de riesgo Bajo/Medio/Alto.

El LLM **nunca calcula puntajes biomecánicos**; solo redacta recomendaciones técnicas basadas en los dictámenes deterministas.

---

## 4. Persistencia zero-database

Todos los datos se almacenan en archivos JSON bajo `casos_jabil_workspace/caso_<id>/`:
- `session_state.json`: snapshot mutable del estado del caso.
- `audit_trail.json`: registro append-only con encadenamiento SHA-256 (hash chaining).
- `inputs/`: fotografías del caso.

Escritura atómica por archivo (write-temp → fsync → os.replace), sin transacciones entre archivos ni coordinación multiproceso. Los hashes no son firmas ni impiden recalcular una cadena reescrita. No se usa DBMS; SQLite queda condicionado a autorización futura.

---

## 5. Agente IA y RAG

- **RAG actual:** `InMemoryRAG` indexa `normative_rag_clauses` de `jabil_standards_00023.json`; `knowledge_retriever.py` consulta reglas etiquetadas de `jabil_reglas.json`. El Markdown no es fuente numérica del cálculo.
- **Ceguera inducida:** El contexto normativo se poda según el tipo de prueba activa para evitar contaminación cruzada.
- **LLM:** Compatible con Ollama (local), Gemini u OpenAI vía `LLMFactory`. Fallback determinista si el proveedor no está disponible.

---

## 6. Endpoints principales

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/casos` | GET | Listar casos |
| `/casos/{id}` | GET | Obtener detalle de caso |
| `/casos` | POST | Crear caso desde fotos |
| `/casos/{id}/puntos/{vista}` | PUT | Corregir esqueleto detectado |
| `/casos/{id}/nom036` | PUT | Capturar evaluación NOM-036 |
| `/casos/{id}/referencia` | PUT | Capturar estudio referencia Jabil |
| `/casos/{id}/recomendaciones` | POST | Crear recomendación de especialista |
| `/casos/{id}/recomendaciones/{rec}/decision` | POST | Aprobar/editar/rechazar (ergonomía) |
| `/casos/{id}/recomendaciones/{rec}/autorizacion` | POST | Autorizar/denegar (ingeniería) |
| `/casos/{id}/generar-plan-ia` | POST | Generar plan con ErgoAI Agent |
| `/casos/{id}/informe` | GET | Descargar informe PDF |
| `/casos/{id}/excel-jabil` | GET | Descargar XLSM oficial Jabil |
| `/bitacora/verificar` | GET | Verificar integridad SHA-256 |
| `/rag/consultar` | POST | Consulta normativa RAG |

---

## 7. Ejecución

```powershell
# Backend
.venv\Scripts\python -m pip install -r requirements.txt -r backend/requirements-vision.txt
.venv\Scripts\python backend/main.py

# Frontend
cd frontend
npm install
npm run dev

# Modelo de visión (una sola vez)
.venv\Scripts\python -m backend.app.vision.modelos

# Modelo LLM (Ollama)
ollama pull qwen2.5
```

Los comandos históricos sin variables no alinean necesariamente el proxy. Para backend 8000 y frontend 5173 seguir la [ejecución vigente](ESTADO_ACTUAL.md#ejecución-y-comprobaciones).

---

## 8. Pruebas

Suite completa con `pytest`:

```powershell
.venv\Scripts\python -m pytest
```

Cubre: API, REBA, NOM-036, RAG, visión, persistencia SHA-256, flujo de especialista, rutas separadas, exportadores PDF/XLSM, Ley Silla, EAWS.

---

## 9. Cumplimiento de la rúbrica Track 4

| Criterio | Puntos | Estado |
|----------|--------|--------|
| Puntaje REBA exacto (6 casos) | 20 | Implementado (determinista) |
| Estimación angular ≥90% | 15 | Pendiente de validación documentada con referencias expertas |
| Informe y recomendaciones NOM-036 | 15 | Implementado (PDF + XLSM) |
| Diseño del agente modular | 8 | Implementado (routers separados) |
| Originalidad/diferenciación | 7 | Implementado (XLSM oficial Jabil + sanduíche what-if) |
| Validación especialista + trazabilidad | 6 | Implementado (Human-in-the-loop + SHA-256) |
| Riesgo residual recalculado | 4 | Implementado (simulador) |
| Medición de impacto tiempos | 5 | Implementado (métricas en caso) |
| Documentación técnica ≤10 cuartillas | 10 | Pendiente de comprobar maquetación |

---

## 9. Limitaciones conocidas

- Precisión de ángulos no validada con fotos reales de Jabil (pendiente de descargar modelos ONNX y probar con dataset).
- Torsión del tronco se captura manualmente en el contexto de la tarea.
- Carga, agarre y actividad no se extraen de la foto; los captura el especialista.
- Una persona por caso; no se evalúa a todos los operarios de una foto.
- Sin usuarios ni contraseñas (prototipo; rol se selecciona en la interfaz).
