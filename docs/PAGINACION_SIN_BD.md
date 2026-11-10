# Consultas paginadas sin base de datos

## API

- `GET /casos/pagina?page=1&page_size=10` devuelve `{items: CasoResumen[], total, page, page_size, total_pages}`. `page` es entero >= 1; `page_size` es entero de 1 a 100. Parámetros inválidos devuelven 422 antes de ejecutar el servicio, sin cambiar casos, auditorías ni resúmenes.
- Orden: `id_caso` ascendente, independiente de la fecha y del orden de creación. Una página fuera de rango devuelve `items: []`; un conjunto vacío tiene `total_pages: 0`.
- `GET /metricas/dashboard` devuelve `{total_casos, niveles: {sin_evaluar, inapreciable, bajo, medio, alto, muy_alto}, tipos_tarea, decisiones_pendientes, por_autorizar}`. Cuenta todos los casos, no sólo la página visible. `sin_evaluar` corresponde a REBA ausente, no a un riesgo inventado.
- `GET /casos` conserva el array completo y su evaluación original por compatibilidad; es costoso y no debe usarse en la nueva bandeja ni en el dashboard. `/metricas/impacto` también conserva su contrato; no es la fuente del dashboard.

La documentación interactiva de FastAPI (`/docs`) expone los modelos y límites. `/casos/pagina` se registra antes de `/casos/{id_caso}`.

## Archivos y costo real

La fuente sigue siendo `caso.json`; `audit_trail.json`, `session_state.json`, bitácora, fotos y evidencias de privacidad mantienen sus responsabilidades. No hay motor, driver ni dependencia de base de datos.

Cada caso tiene un archivo **derivado** `resumen_consulta.json`, escrito con `AuditFileManager.write_json_atomic`. Contiene versión, firma de vigencia y el mismo `CasoResumen` que construye el listado compatible. No contiene fotos, puntos, recomendaciones completas ni datos de auditoría. No sustituye una cadena de integridad.

| Estado | Lecturas de payload/evaluaciones | Otros costos |
| --- | --- | --- |
| Página caliente, incluso tras reiniciar | 0 casos; 0 fotos; 0 evaluaciones | Enumeración de IDs/metadatos de directorios O(N); lectura de JSON de resumen sólo para los IDs de la página, como máximo `page_size` |
| Página fría en workspace antiguo | Una carga/evaluación por entrada solicitada sin resumen vigente, como máximo `page_size` | Sólo reconstruye los IDs de esa página; puede leer sus fotos para proyectar geometría segura |
| Página fuera de rango | 0 casos; 0 fotos; 0 evaluaciones | Enumeración de IDs O(N), pero 0 lecturas de JSON de resumen y 0 reconstrucciones |
| Dashboard caliente, incluso tras reiniciar | 0 casos; 0 fotos; 0 evaluaciones | Metadatos y lectura de todos los resúmenes O(N), necesarios para el agregado global |
| Dashboard frío | Una carga/evaluación por entrada sin resumen vigente | Reconstruye las entradas restantes, no las ya calentadas por páginas anteriores |
| Resumen ausente, inválido u obsoleto | Una carga/evaluación por entrada afectada consultada | Una página no lee ni reconstruye entradas fuera de sus IDs; el dashboard sí consulta todas |
| Mutación | El cálculo habitual del caso mutado | Actualiza su resumen al sincronizar; no recalcula otros casos |

La paginación enumera y ordena IDs, calcula el total y selecciona el intervalo **antes** de leer cualquier JSON de resumen. Limita tanto la respuesta como las lecturas de resúmenes a la página solicitada; **no** convierte la enumeración de archivos ni los agregados globales en O(1). El dashboard inicial de un workspace antiguo puede ser lento porque debe reconstruir todos los resúmenes pendientes. Una página caliente no necesita ni siquiera cargar el cuerpo de los casos de esa página.

## Vigencia y fallos

La firma usa metadatos (`mtime_ns`, `ctime_ns`, tamaño) de `caso.json` y de los archivos directos de `inputs`, además del hash de catálogos REBA/NOM-036/Jabil y la versión del resumen. Cambios en fotos o sidecars invalidan la proyección de geometría; cambiar la lógica de evaluación requiere incrementar `VERSION_RESUMEN`. Los catálogos se cargan al iniciar el servicio: sus cambios entran en vigor al reiniciarlo.

Todas las mutaciones existentes terminan en la sincronización común: puntos, confirmación de ángulos, contexto, hallazgos, referencia, NOM-036, recomendaciones, decisiones, autorización, implementación, creación y plan generado. La escritura original cambia también la firma: si el proceso se interrumpe antes de actualizar el resumen, la siguiente consulta lo reconstruye. Operaciones sin cambios conservan el estado.

Un resumen corrupto se reconstruye desde el caso validado, sin reescribir el caso ni sus auditorías ni migrar imágenes antiguas. Una fuente corrupta no se convierte en un resumen vacío ni en contadores ficticios: su error de lectura/validación se propaga como antes. Un fallo de escritura o permisos tampoco se oculta. Los resúmenes son datos locales derivados, no documentos confiables frente a manipulación deliberada; la firma de metadatos detecta cambios ordinarios, no sustituye un hash criptográfico del cuerpo ni protege contra restauraciones maliciosas de metadatos.

El `RLock` existente del servicio serializa consultas y mutaciones dentro de esa instancia. No se promete consistencia entre procesos o múltiples instancias que escriban simultáneamente el mismo workspace. La atomicidad evita JSON parciales, pero no constituye una transacción multiproceso entre archivos.

## Verificación

`tests/test_paginacion.py` comprueba contratos HTTP, orden estable, tamaños 1/100, límites inválidos sin mutación, agregados globales, reconstrucción fría/caliente, corrupción, actualización por mutaciones y reinicio. Los espías cuentan cargas/evaluaciones y las aperturas reales de archivos `resumen_consulta.json`: una página de tamaño 2 consulta sólo 2 resúmenes, fría o caliente; fuera de rango consulta 0. El dashboard conserva los totales globales y reconstruye sólo las entradas todavía frías. Una lectura de imagen caliente hace fallar la prueba. Las fotos de las pruebas de mutación usan un estimador determinista, sin inferencia ONNX ni LLM de red.

Ejecutar: `.venv/Scripts/python.exe -m pytest tests/test_paginacion.py tests/test_session_store.py tests/test_api.py -q`.
