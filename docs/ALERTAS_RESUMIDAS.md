# Alertas: resumen y detalle del caso

En **Alertas**, cada tarjeta muestra una frase breve según el evento, su título,
urgencia, estación, fecha y estado. La simulación de caída conserva su distintivo.
El relato completo no se incluye en el HTML de las tarjetas, ni en atributos
ocultos o tooltips; no se recorta ni modifica el dato almacenado.

## Consultar la evidencia completa

**Ver caso** abre el análisis del caso asociado con el identificador codificado
para la URL. Allí, **Detalle de alertas del caso** muestra el texto íntegro de
las alertas vinculadas a ese mismo identificador, junto con evento, urgencia,
estación, fecha y estado. Se conservan los hallazgos, ángulos, REBA y datos de la
tarea existentes. También funciona al entrar directamente a un caso.

La sección observa la consulta compartida `['alertas']` que ya carga Layout;
no inicia otra descarga de todas las alertas por caso. Mientras llega esa
consulta muestra carga; si falla, muestra el error sin bloquear el análisis.
Sin alertas vinculadas no añade una sección vacía. Nunca incluye alertas de
otro caso ni simulaciones sin caso asociado. React escapa los textos.

## Acciones sin cambios

Abrir el caso no marca la alerta atendida. **Marcar atendida** conserva la
mutación existente, el identificador original y las invalidaciones de
`['alertas']` y `['bitacora']`, sin cambios de roles ni permisos. Las alertas
atendidas no ofrecen ese botón. Las simulaciones sin caso no ofrecen **Ver caso**.
El orden sigue siendo no atendidas primero y mayor urgencia dentro de cada grupo.

## Verificación

```sh
node --test frontend/tests/alertas.test.mjs frontend/tests/dashboard.test.mjs frontend/tests/skeleton.test.mjs frontend/tests/proxy.test.mjs
npm --prefix frontend run build
```

Las pruebas usan TypeScript y React instalados en memoria y el router real para
comprobar el destino de **Ver caso** y sus parámetros. No constituyen una
inspección visual ni una prueba de navegador.
