# ErgoAI: estructura vigente y decisiones de trabajo

**La persistencia actual es por archivos; SQLite no está implementado ni descartado para el futuro.** Este índice distingue decisiones vigentes, implementación y propuestas históricas. No certifica cumplimiento normativo, precisión ni resultados de pruebas.

## Orden de lectura y autoridad

1. [README](../README.md): instalación y acceso inicial.
2. [ARCHITECTURE](../ARCHITECTURE.md): invariantes del negocio y separación de responsabilidades.
3. Este documento: decisiones vigentes y límites de las afirmaciones técnicas.
4. Guías funcionales enlazadas abajo: comportamiento específico.

Las [especificaciones](../Especificaciones_y_Arquitectura_ErgoAI.md) conservan requisitos y citas de la competencia; sus propuestas tecnológicas no describen necesariamente la implementación. Los documentos oficiales originales son necesarios para validar las interpretaciones normativas.

`PLAN_*.md`, las dos versiones de documentación técnica y la guía histórica de arquitectura conservan antecedentes, no una lista vigente de pendientes ni una certificación. `odd/tasks/` registra solicitudes, decisiones y pruebas de sus respectivas unidades; no se reescribe para aparentar validación del árbol actual. Las [ideas de innovación](../Propuestas_e_Ideas_Innovacion_ErgoAI.md) no autorizan ampliar el prototipo.

Ante contradicciones técnicas, comprobar el código y actualizar la guía afectada junto al cambio. Ante contradicciones normativas, no elegir una regla por antigüedad del documento: cotejar el original con el especialista antes de modificar cálculos.

## Estructura y responsabilidades

| Superficie | Responsabilidad |
| --- | --- |
| `backend/main.py`, `backend/app/api/` | Arranque FastAPI, contratos HTTP y validación de entrada |
| `backend/app/services/` | Orquestación del flujo de casos y exportación |
| `backend/app/core_ergonomics/` | Geometría, REBA, NOM-036, simulación residual y evaluadores complementarios |
| `backend/app/core_agent/` | Recuperación normativa y redacción LLM; no calcula puntajes |
| `backend/app/vision/` | Pose 2D ONNX, anotación y protección de imágenes |
| `backend/app/session_store/` | Archivos por caso, configuración y auditoría |
| `backend/app/exporters/` | Construcción de entregables PDF y Excel |
| `frontend/src/` | React/TypeScript, cliente HTTP, páginas y componentes |
| `config_normativo/` | Tablas y reglas utilizadas por el sistema; requieren validación normativa |
| `casos_jabil_workspace/` | Datos locales de ejecución; no confundir con código o fixtures |
| `tests/`, `frontend/tests/` | Verificación backend y frontend |

No mover módulos ni agregar una capa abstracta solo para preparar SQLite. Mantener cálculo, orquestación y almacenamiento separados usando la estructura existente.

## Persistencia: archivos ahora, SQLite condicionado

- Fuente del caso: `caso.json`; `session_state.json` es un snapshot. `resumen_consulta.json` es un derivado reconstruible, no autoridad.
- Auditoría: `audit_trail.json` por caso y `bitacora.json` global. Esta última enlaza eventos mediante `hash_anterior`; no es JSONL.
- Escrituras: temporal → `fsync` del archivo → `os.replace`. La atomicidad es por archivo, no una transacción entre caso, snapshot y bitácoras; no garantiza supervivencia ante cualquier fallo de energía.
- Los locks internos no coordinan múltiples procesos ni servidores. La verificación de una cadena recorre sus eventos; no es de tiempo constante.
- Los hashes permiten detectar inconsistencias, pero no ofrecen firma digital, no-repudio ni defensa ante quien pueda reescribir y recalcular toda la cadena. Proteger acceso al workspace y conservar respaldos sigue siendo necesario.
- Mantener la consulta paginada y los resúmenes existentes. La enumeración/ordenación sigue siendo O(N), y el dashboard agrega los resúmenes; no prometer coste constante.

**SQLite queda como alternativa de adaptador futuro**, no como dependencia, tarea pendiente de implementación ni permiso ya concedido. Antes de incorporarlo: aclarar su admisibilidad en la competencia, documentar la decisión y autorizar una migración con preservación de auditoría, pruebas de compatibilidad y recuperación. No se migran ni borran datos en esta limpieza.

Detalles: [persistencia](MODULO_PERSISTENCIA_SIN_BASE_DE_DATOS.md) y [paginación](PAGINACION_SIN_BD.md).

## Evidencia, normativa y privacidad

- El agente propone; el especialista valida. Ingeniería precede a medidas administrativas y se conserva la prevalencia del estándar corporativo más restrictivo.
- Visión actual: YOLOX + RTMPose/RTMW WholeBody-133 sobre ONNX. El modelo puede producir 133 puntos; la representación de trabajo conserva un subconjunto de 19. Fotografías desde tres vistas no equivalen a reconstrucción 3D calibrada.
- No inferir masa, frecuencia, agarre ni alturas métricas sin evidencia/calibración. La corrección humana de puntos no certifica anatomía ni precisión.
- Las máscaras sólidas y el cierre completo ante incertidumbre sustituyen la descripción antigua de simple difuminado. No exponer `inputs/` como contenido estático. Ver [visión y privacidad](VISION_Y_PRIVACIDAD.md).
- Los cálculos consumen catálogos JSON; el determinismo no demuestra por sí mismo equivalencia normativa. `InMemoryRAG` indexa `normative_rag_clauses` del catálogo Jabil; `knowledge_retriever.py` consulta reglas etiquetadas de `jabil_reglas.json`. No confundir ambos recuperadores con el Markdown de referencia.

### Validaciones externas todavía necesarias

| Tema | Evidencia faltante / criterio |
| --- | --- |
| NOM-036 | El Markdown de conocimiento difiere del JSON en peso/frecuencia, región vertical y torsión. Cotejar hoja oficial y norma con especialista antes de cambiar tablas o presentar sus valores como certificados. |
| Precisión angular | La meta ≥90% exige referencias validadas y modelos disponibles. La presencia de `angulos_referencia.json` no acredita procedencia ni validación experta. La prueba mide tolerancia ±5°, no equivalencia clínica. |
| SQLite | La interpretación de su admisibilidad sigue abierta; archivos es la decisión operativa actual. |

## Ejecución y comprobaciones

Desde la raíz, con dependencias instaladas y `.env` preparado según el README:

```bash
# Backend y proxy alineados explícitamente; terminal 1
.venv/bin/python -m uvicorn backend.main:app --reload --port 8000
# Frontend; terminal 2 (Bash)
cd frontend
VITE_BACKEND_PROXY_TARGET=http://localhost:8000 npm run dev -- --port 5173
```

En PowerShell: usar `.venv\Scripts\python` y definir `$env:VITE_BACKEND_PROXY_TARGET = "http://localhost:8000"` antes de `npm run dev -- --port 5173`.

Sin variables, `settings.py` usa backend 8000; Vite actualmente usa frontend 5180 y proxy hacia 8080. Las variables y los scripts pueden cambiarlos: revisar la salida efectiva. Docker publica frontend 5173 → 80 y backend 8000 → 8000 por defecto; no confundir puerto interno con puerto del host. El modo Docker requiere `.env` y actualmente declara reserva NVIDIA en `llm_engine`; no es el camino CPU sin ajustar esa reserva.

```bash
# Desde raíz; no reemplazar pytest por unittest (hay funciones pytest)
.venv/bin/python -m pytest
node --test frontend/tests/*.test.mjs
npm --prefix frontend run build
```

Registrar comando, entorno, exit code y pruebas omitidas en cada ejecución relevante. Los conteos de documentos anteriores son históricos, no resultados actuales. Para una limpieza exclusivamente documental se comprueban enlaces locales, consistencia y `git diff --check`; no se afirma haber ejecutado estas suites funcionales.

## Guías funcionales

- [Dashboard y paginación](DASHBOARD_Y_PAGINACION.md): agregados globales y colecciones de detalle en páginas de cinco filas; captura NOM-036 íntegra e informes/impresión sin recortes.
- [Cobertura NOM-036](NOM036_COBERTURA.md): inventario de los cinco grupos de factores, captura manual de Equipo (3) con los nueve factores de AI.4 y trazabilidad a cláusulas/páginas del corpus local. No certifica fórmulas ni cumplimiento; conserva y explicita diferencias históricas de las hojas de empuje/arrastre pendientes del libro controlado y especialista.
- [Alertas resumidas](ALERTAS_RESUMIDAS.md)
- [Esqueleto interactivo](ESQUELETO_INTERACTIVO.md)
- [Integración de ramas](INTEGRACION_RAMAS.md)
- [Manual visual Jabil](../jabil_brand_identity_manual.md): referencia visual; cualquier diferencia con CSS se resuelve en una tarea de interfaz, no cambiando estilos durante una limpieza documental.
