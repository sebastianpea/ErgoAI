# Dashboard y paginación

## Entrar y trabajar con casos

La ruta inicial `/` muestra el dashboard de auditoría. **Ver casos y validar** abre
`/casos`; la navegación principal también ofrece ambos apartados. Se conservan
las rutas de análisis `/casos/:id`, plan `/casos/:id/plan` e informe
`/casos/:id/informe`, así como el selector de rol y las reglas de revisión.

El dashboard consulta `GET /metricas/dashboard`. Sus cifras cubren **todos los
casos**, no la página visible: total de casos, riesgo alto o muy alto, decisiones
por validar y cambios en planta por autorizar. Las gráficas comparan los conteos
por riesgo REBA y por tipo de tarea mediante **donas SVG interactivas**, con
etiquetas, conteos y porcentajes siempre visibles en una lista semántica.
Cada porcentaje usa la suma de los conteos de esa distribución, no los casos
de la página ni las decisiones pendientes; se redondea a un decimal, por lo
que la suma redondeada puede diferir de 100 %. No depende del color.

Pulsa una categoría de la leyenda (clic, toque o Tab y Enter/Espacio) para ver
su nombre, conteo y porcentaje en el centro; un borde y «Seleccionado» indican
la selección. Pulsa de nuevo o usa **Ver total** para restablecer el centro.
No hace falta pasar el cursor ni se ocultan los valores de otras categorías.
Los colores REBA conservan exactamente su significado anterior; las tareas
usan una paleta categórica navy/cyan/plata, sin sugerir niveles de seguridad.
Las tarjetas se adaptan al ancho y respetan movimiento reducido.

No se muestran tendencias ni ahorros estimados sin datos.
Un nivel sin evaluación se distingue de un riesgo bajo. Los tipos de tarea
nuevos conservan su nombre si todavía no tienen traducción en el cliente.

Hay mensajes de carga, colección vacía y errores con **Reintentar**. Una colección
vacía permite crear el primer caso desde fotos. Los valores cero se muestran
como cero; no se generan cifras de demostración en el cliente real. Una
categoría única positiva ocupa el 100 %; categorías con cero no generan
segmentos. Si todos los conteos son cero, se muestra un anillo neutro y 0 %
en la leyenda, sin sectores artificiales. Una distribución vacía se identifica
como tal. Conteos inválidos o una suma no finita muestran un aviso, sin
geometría ni porcentajes inventados.

## Consultar una página

La bandeja solicita exclusivamente:

```text
GET /casos/pagina?page=1&page_size=10
```

```json
{"items":[],"total":0,"page":1,"page_size":10,"total_pages":0}
```

El servidor ordena por `id_caso` ascendente. No hay ordenación local por riesgo:
ordenar una sola página podría sugerir una prioridad global falsa. **Anterior**
y **Siguiente** respetan los límites; se muestra página actual, páginas totales
y cantidad global. El selector ofrece 10, 25, 50 o 100 casos. Cambiar tamaño
vuelve a la primera página. **Actualizar** recarga la página; si disminuye el
total y desaparece la página actual, se consulta la última disponible sin bucle.
La colección vacía se representa como página 1 de 1 en la interfaz, aunque el
contrato devuelve `total_pages: 0`.

Página y tamaño viven en `?page=…&page_size=…`, por lo que el historial del
navegador conserva la selección al volver desde un análisis. Una página inválida
se interpreta como 1 y un tamaño no ofrecido como 10. El contrato API admite
cualquier entero `page >= 1` y `page_size` entre 1 y 100. Las páginas posteriores
al final devuelven `items: []`, sin cambiar datos.

## Contrato e integración

```ts
interface MetricasDashboard {
  total_casos: number;
  niveles: {
    sin_evaluar: number; inapreciable: number; bajo: number;
    medio: number; alto: number; muy_alto: number;
  };
  tipos_tarea: Record<string, number>;
  decisiones_pendientes: number;
  por_autorizar: number;
}
```

`api.listarCasosPaginados(page, page_size)` es aditivo: `api.listarCasos()` sigue
disponible para consumidores anteriores. Ni la bandeja ni el dashboard llaman
al listado completo ni a `/metricas/impacto`. Las claves de React Query son
`["casos", "pagina", page, page_size]` y `["casos", "dashboard"]`: las
invalidaciones existentes por prefijo `["casos"]`, después de crear o revisar
casos y decidir/autorizar recomendaciones, refrescan ambos recursos.

El modo simulado usa los mismos nombres y sobres de respuesta; deriva los
agregados de sus casos en memoria y pagina en orden estable, sin valores
inventados. Esa paginación en memoria es propia de la simulación, no una descarga
completa del backend. La implementación file-backed del servidor debe limitar
lecturas de payloads a la página y mantener resúmenes ligeros para agregados;
un escaneo de metadatos del directorio no equivale a leer todos los casos.
La prueba de esas garantías del servidor pertenece a la implementación backend,
no a las pruebas de interfaz.

## Diagnosticar errores de JSON del dashboard

Si aparece `No se pudo cargar el resumen: JSON.parse: unexpected character at line 1 column 1 of the JSON data`, inspeccionar la respuesta de
`GET /metricas/dashboard` **a través del origen del frontend**, no solamente
el puerto del backend. Debe devolver estado 200, `Content-Type: application/json`
y el agregado JSON. Un 200 con `text/html` y el documento de la SPA indica que
la petición no llegó al backend; no se corrige ocultando el error de JSON.

Vite (`frontend/vite.config.ts`) y Nginx (`frontend/nginx.conf`) incluyen
`/metricas` en sus listas de proxy, junto a los prefijos API anteriores.
Esto cubre tanto `/metricas/dashboard` como el endpoint existente
`/metricas/impacto`, sin reescribir la ruta enviada al backend. Tras aplicar la
configuración, comprobar el origen del frontend que realmente se esté usando;
un despliegue existente requiere su proceso habitual de actualización.

La ruta `/` y las rutas frontend no coincidentes conservan el fallback SPA.
Los prefijos API tienen precedencia: las peticiones HTTP directas a
`/casos/...` (incluso con `Accept: text/html`) siguen yendo al backend, igual
que antes. La navegación interna de React a análisis, plan e informe no cambia;
este arreglo no modifica el contrato de recarga directa de esas rutas.

## Comprobaciones

```text
node --test frontend/tests/dashboard.test.mjs frontend/tests/skeleton.test.mjs frontend/tests/proxy.test.mjs
npm --prefix frontend run build
```

`proxy.test.mjs` ejecuta el proxy HTTP real de Vite contra un backend sintético
en puertos efímeros de `127.0.0.1`, sin leer `.env` ni datos de usuario. Comprueba
estado, tipo y cuerpo JSON exactos para ambos endpoints de métricas y cada
prefijo anterior, además del fallback SPA. Aísla la carga del entorno y del
plugin React, no el proxy; cierra ambos servidores y elimina su directorio
temporal incluso ante fallos. Para Nginx comprueba el regex acotado, los prefijos,
el fallback y `proxy_pass` sin reescritura; esa comprobación estructural no
sustituye `nginx -t` ni una prueba HTTP del despliegue Nginx.

Las otras pruebas Node compilan TypeScript en memoria y ejercitan rutas, JSX de
las gráficas, geometría proporcional, colores REBA exactos, conteos/porcentajes,
casos cero/vacío/único e inválidos, y selección/restablecimiento mediante los
handlers reales con estado persistente entre renders. También cubren estados,
callbacks y claves de consulta,
URLs reales y comportamiento de la simulación (incluidos límites y rechazo
sin cambios). No sustituyen una inspección visual de escritorio/móvil ni una
prueba navegador-backend integrada.
