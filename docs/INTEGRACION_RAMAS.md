# Integración de develop con main

La composición de FastAPI y sus routers de main se conservan. Las rutas nuevas son aditivas:

- `POST /vision/analizar-rapido`: multipart con `foto`, `tipo_tarea` y `carga_kg`; no crea un caso. Devuelve `reba_final`, `reba_nivel`, una lista `angulos` con `segmento`, y `imagen_anotada_b64` nullable. Si no hay personas, devuelve `ok: false` y `advertencia`; la cámara muestra el aviso y permite repetir la fotografía sin presentar un dictamen.
- `GET /casos/{id_caso}/exportar/excel` y `/exportar/pdf`: delegan a ServicioCasos, incluida su validación de aprobación e implementación. No sustituyen los informes previos `/informe` y `/excel-jabil`.

Se mantienen `/casos/pagina`, `/metricas/dashboard`, `/metricas/impacto` y la entrega protegida de `/media`, sin servir directamente los originales.

Nginx conserva las recargas SPA de develop: las vistas nuevo/plan/informe sirven React y los namespaces compartidos usan Accept HTML para la navegación. Las exportaciones y métricas siempre van al backend; `/media/` tiene precedencia sobre las extensiones estáticas. Los timeouts de API de 300 segundos permanecen. Vite conserva su contrato previo de proxy, incluso en navegaciones a `/casos`.

Las pruebas de integración usan servicios simulados sin iniciar el workspace; las pruebas de cámara renderizan la respuesta pública sin hardware ni modelos. La suite backend completa y la resolución del índice del merge corresponden al orquestador.
