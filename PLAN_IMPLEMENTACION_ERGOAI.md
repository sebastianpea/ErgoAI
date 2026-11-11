# Plan de Implementación ErgoAI — Track 4 Jabil

> **Plan histórico, no lista vigente de tareas ni evidencia de ejecución.** Ramas, rutas, resultados y acciones de commit abajo corresponden a su contexto original; no son instrucciones para esta limpieza. Consultar [estado actual](docs/ESTADO_ACTUAL.md) y [README](README.md).

Rama histórica: `ergoai-unificado` (cambios staged, sin commit aún)
Metodología: ODD (Organic Driven Development), test-first RED → GREEN → REFACTOR, work-unit commits.  
Runner: `pytest` (backend); `unittest discover` no sustituye la suite porque no descubre funciones pytest.

## Fase 0 — Baseline y verificación del merge

Objetivo: asegurar que la fusión `develop` + `front-end` sobre `main` no rompió nada antes de añadir código nuevo.

Tareas:
1. Commit de estado actual en `ergoai-unificado` (usuario debe ejecutar `git commit`).
2. Ejecutar suite actual: `.venv\Scripts\python -m pytest` desde `C:\Dev\ErgoAI`.
3. Documentar qué tests pasan, cuáles fallan y por qué.
4. Crear `odd/tasks/ergoai-track4-completo.md` (hecho).

Criterio de aceptación: `pytest` termina con 0 fallos inesperados (fallos preexistentes documentados).

---

## Fase 1 — Estructura de carpetas por caso y persistencia zero-DB

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §3.1 punto 3, §3.2; `PLAN_PERSISTENCIA_SIN_BASE_DE_DATOS.md`.

Archivos a crear:
- `backend/app/session_store/case_workspace.py` — función `init_case_workspace(case_id)` que crea `casos_jabil_workspace/caso_<id>/inputs/`, `session_state.json`, `audit_trail.json` (GENESIS hash SHA-256).
- `casos_jabil_workspace/` (carpeta raíz en repo).
- `casos_jabil_workspace/templates/` (para `.xlsm` base, placeholder vacío si no hay archivo oficial).

Archivos a modificar:
- `backend/app/services/casos.py` — `sembrar_si_vacio` y `crear_caso` deben llamar a `init_case_workspace` y guardar `session_state.json` + `audit_trail.json` por caso.

Tests a crear:
- `tests/test_case_workspace.py`:
  - `test_init_case_workspace_creates_directories` — verifica `inputs/` existe.
  - `test_session_state_and_audit_trail_created` — verifica JSONs válidos y hash GENESIS presente.
  - `test_audit_trail_hash_chain_detects_tampering` — cambiar un carácter en `audit_trail.json`, `verify_case_audit_integrity` debe retornar `ok=False`.

Criterio de aceptación: creación de caso genera carpeta y archivos; alterar `audit_trail.json` se detecta.

---

## Fase 2 — Generador de informes PDF

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §3.1 punto 4 (Generador de Entregables Oficiales).

Archivos a crear:
- `backend/app/exporters/__init__.py`
- `backend/app/exporters/pdf_report_builder.py` — clase `PdfReportBuilder` con método `build(case_id, output_path)` que genera PDF con:
  - Cabecera Jabil (logo, estación, caso, fecha).
  - Esqueleto con ángulos superpuestos (imagen de referencia).
  - Tabla REBA inicial vs residual (por segmento).
  - Resultado NOM-036.
  - Tabla de trazabilidad del especialista (qué aprobó/editó/rechazó).
  - Firmas (Ergonomía, Ingeniería).
- `backend/app/api/routes_reports.py` — endpoint `GET /casos/{id_caso}/informe` que devuelve `FileResponse` del PDF generado.

Archivos a modificar:
- `backend/main.py` — incluir router de reports.

Tests a crear:
- `tests/test_pdf_report.py`:
  - `test_pdf_report_builds_without_case_data` — PDF se genera aunque el caso sea mínimo (no crashea).
  - `test_pdf_report_contains_expected_sections` — buscar strings "REBA", "NOM-036", "Bitácora" en bytes del PDF (búsqueda binaria simple).

Criterio de aceptación: endpoint `/casos/{id}/informe` devuelve PDF válido (cabecera `%PDF`).

---

## Fase 3 — Llenador del XLSM oficial de Jabil

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §3.1 punto 4; `Propuestas_e_Ideas_Innovacion_ErgoAI.md` Propuesta 2.2.

Archivos a crear:
- `backend/app/exporters/jabil_xlsm_filler.py` — clase `JabilXlsmFiller` con método `fill(case_data, template_path, output_path)` que usa `openpyxl` para escribir en hojas:
  - `Mov`: metadatos, ángulos por segmento, REBA total.
  - `Levantamiento (1)`, `Transporte (2)`, `Equipo (3)`, `sin auxiliar (4)`, `con auxiliar (5)`: factores NOM-036 con colores y puntajes.
  - `EAWS`: postura, fuerza, frecuencia, nivel.
  - `Resultado`: consolidado.
  - `OBSERVACIONES Y MEJORAS`: plan de acción con responsable y fecha.
- `casos_jabil_workspace/templates/16-PE80-6500-00014-H_base.xlsm` — placeholder (archivo binario vacío o mínimo con las hojas esperadas).

Archivos a modificar:
- `backend/app/api/routes_reports.py` — endpoint `GET /casos/{id_caso}/excel-jabil` que devuelve `FileResponse` del XLSM rellenado.

Tests a crear:
- `tests/test_xlsm_filler.py`:
  - `test_xlsm_filler_opens_template_and_writes_sheets` — con template placeholder, verificar que no lanza excepción y crea archivo de salida.
  - `test_xlsm_filler_has_required_sheets` — verificar que las hojas esperadas existen en el salida (si openpyxl puede leerlo).

Criterio de aceptación: rellenar XLSM no lanza excepción y genera archivo de salida legible por openpyxl.

---

## Fase 4 — Evaluador Ley Silla (STPS)

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §1.2 (Ley Silla), `ARCHITECTURE.md` §3.2 (módulo `chair_law_evaluator.py`).

Archivos a crear:
- `backend/app/core_ergonomics/chair_law_evaluator.py` — clase `ChairLawEvaluator` con método `evaluate(context)` que retorna:
  - `cumple_ley_silla: bool`
  - `factores`: lista de 7 factores con resultado (cumple/no cumple).
  - `alerta_bipedestacion_3h: bool` si tiempo de pie continuo > 3 horas.
  - `recomendacion: str` (agregar silla, rotar, etc.).

Tests a crear:
- `tests/test_chair_law.py`:
  - `test_chair_law_tres_horas_continua_es_no_cumple` — contexto con tiempo de pie > 3h retorna `cumple_ley_silla=False`.
  - `test_chair_law_menos_de_tres_horas_es_cumple` — tiempo <= 3h retorna `cumple_ley_silla=True`.
  - `test_chair_law_siete_factores_retornados` — exactamente 7 factores en resultado.

Criterio de aceptación: 7 factores evaluados; regla de las 3 horas aplicada correctamente.

---

## Fase 5 — Motor EAWS dedicado

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §1.1 (hoja EAWS), `config_normativo/nom036_mac_rapp_tables.json` (ya tiene `sheets_mapping.eaws`).

Archivos a crear:
- `backend/app/core_ergonomics/eaws_calculator.py` — clase `EawsCalculator` con método `calculate(trunk_flexion_deg, torso_twist_deg, work_above_shoulder_bool, work_below_knee_bool, force_kg, frequency_actions_per_shift)` que retorna:
  - `posture_score`, `force_score`, `frequency_score`, `total_score`, `risk_level` ("Bajo" <=5, "Medio" 6-10, "Alto" >10).

Archivos a modificar:
- `backend/app/core_ergonomics/nom036_calculator.py` — opcional: importar y usar `EawsCalculator` desde `EnrutadorNom036` si se desea unificar, pero fase 5 puede ser standalone.

Tests a crear:
- `tests/test_eaws.py`:
  - `test_eaws_low_risk` — flexión <20°, fuerza <5kg, frecuencia <100 → total <=5, "Bajo".
  - `test_eaws_medium_risk` — combinación media → "Medio".
  - `test_eaws_high_risk` — flexión >45°, fuerza >=10kg, frecuencia >=500 → >10, "Alto".

Criterio de aceptación: fórmulas EAWS exactas según especificación.

---

## Fase 6 — Rutas de API separadas

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §3.2 (routes separados).

Archivos a crear:
- `backend/app/api/routes_evaluation.py` — endpoints de creación de caso, obtención de caso, corrección de puntos/contexto/ángulos.
- `backend/app/api/routes_validation.py` — endpoints Human-in-the-Loop (aprobar/editar/rechazar, autorizar ingeniería, implementar, revisar hallazgo).
- `backend/app/api/routes_reports.py` — endpoints de informe PDF y XLSJ (fases 2 y 3).

Archivos a modificar:
- `backend/main.py` — eliminar lógica de rutas inline, incluir `app.include_router(...)` para los tres routers.

Tests a crear:
- `tests/test_routes_evaluation.py`, `tests/test_routes_validation.py`, `tests/test_routes_reports.py` — usar `fastapi.testclient.TestClient`, verificar status 200/404/422 en endpoints clave.

Criterio de aceptación: `main.py` no define rutas inline; todos los endpoints responden a través de routers.

---

## Fase 7 — Validación de precisión angular con fotos reales

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §1.3 punto 2 (>=90% en rango REBA); `docs/NOTAS_PARA_DOCUMENTACION.md` §4 (precisión no validada con fotos reales Jabil).

Archivos a crear:
- `tests/test_vision_precision.py` — usar imágenes de `backend/app/seed/dataset_jabil/` como entrada al estimador de visión y comparar ángulos medidos contra valores esperados (hardcodeados como "ground truth" por caso).

Tests a crear:
- `tests/test_vision_precision.py`:
  - `test_vision_precision_within_reba_range` — para cada imagen del dataset, el ángulo medido está dentro de ±5° del valor esperado (o se marca "revisar").
  - `test_vision_person_detected` — cada imagen lateral detecta al menos 1 persona.

Criterio de aceptación: >=90% de imágenes dentro del umbral REBA o marcadas para revisión.

---

## Fase 8 — Documentación técnica y diagramas

Especificación: `Especificaciones_y_Arquitectura_ErgoAI.md` §1.3 punto 9 (≤10 cuartillas, entrega 9 Nov 2026), §3.2 (diagramas Mermaid).

Archivos a crear:
- `docs/Documentacion_Tecnica_ErgoAI.md` — máximo 10 cuartillas, cubriendo arquitectura, visión, motores deterministas, agente IA, persistencia zero-DB, pruebas, cómo ejecutar.
- `docs/arquitectura_diagramas.mmd` — diagramas Mermaid de flujo y arquitectura (visión → REBA → NOM-036 → agente → especialista → PDF/XLSM).

Criterio de aceptación: archivo Markdown existe y tiene sección de ejecución paso a paso.

---

## Fase 9 — Suite completa y verificación final

Objetivo: verificar que todos los cambios funcionan juntos y no hay regresiones.

Tareas:
1. Ejecutar suite completa: `.venv\Scripts\python -m pytest` (sin sustituir por `unittest discover`).
2. Ejecutar `python test_agent.py` para verificar agente IA + RAG.
3. Ejecutar `cd frontend && npm run build` para verificar TypeScript.
4. Corregir fallos encontrados en fases anteriores.
5. Commit final en `ergoai-unificado` (usuario debe ejecutar).

Criterio de aceptación: 100% de tests pasan; build de frontend exitoso; agente IA responde sin Ollama (modo fallback) o con Ollama si está disponible.

---

## Riesgos conocidos a vigilar

- `casos.py:1212`: `medidos["brazo"].lado` lanza `KeyError` si falta segmento brazo. Test en Fase 1 debe cubrir.
- `casos.py:1238`: `get_reba_tables()["frontal_view_thresholds_deg"]` puede lanzar `KeyError`. Verificar JSON.
- `nom036_mac_rapp_tables.json` tiene dos esquemas (`metodos` y `sheets_mapping`); asegurar que `validar_captura` y el motor usen el mismo.
- `LLMFactory.get_llm()` y `ErgoAIAgent` requieren Ollama; tests deben usar mock o fallback si Ollama no está disponible.

---

## Estimación de work-units (commits)

| Fase | Work-units estimados |
|------|---------------------|
| 0 | 1 |
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 1 |
| 5 | 1 |
| 6 | 2 |
| 7 | 1 |
| 8 | 1 |
| 9 | 1 |
| **Total** | **14** |

Cada work-unit = commit en `ergoai-unificado` con tests y docs junto al código.
