# Revisar el esqueleto sobre la foto

En **Análisis**, Ergonomía puede arrastrar cada punto o seleccionarlo con **Tab** y moverlo con las **flechas** (1 píxel; **Mayús + flecha**, 10 píxeles). Cada movimiento de teclado y cada fin de arrastre envía la corrección para recalcular el caso. El informe y los demás roles son de solo lectura.

## Qué representa la superposición

- Las coordenadas son píxeles de la imagen original. El `viewBox` y la imagen SVG comparten el ancho y alto recibidos; el arrastre usa la inversa de `getScreenCTM()` para respetar escala, desplazamiento y márgenes del SVG. Las correcciones se limitan a los bordes de la imagen.
- Una conexión requiere ambos extremos presentes, con coordenadas finitas dentro de la imagen y confianza de al menos 0,4 (inclusive), o una corrección manual. Una confianza desconocida, no finita o superior a 1 no se considera fiable.
- Un punto de baja confianza permanece editable, blanco con borde naranja punteado, pero no genera conexiones hasta corregirlo. El azul marino indica corrección manual, no mayor confianza del modelo: se conservan su identificador y confianza originales en el callback.
- Los puntos ausentes o con coordenadas no finitas/fuera de la imagen no se dibujan ni se inventan. Una conexión oculta no demuestra ausencia de una extremidad ni permite deducir su postura. El editor no reconstruye puntos faltantes ni verifica por sí mismo que una detección corresponda a la persona fotografiada.

## Guardado y actualizaciones

Una respuesta del servidor con cambios en puntos, URL, vista o dimensiones reemplaza el estado local y termina el arrastre anterior. Un refresco con los mismos valores, aunque cree objetos nuevos, conserva las ediciones locales no guardadas. Tras un error de guardado, Análisis vuelve a montar el editor con los puntos guardados y muestra el error.

El frontend no reescala ni normaliza semillas para disimular una discrepancia entre la fotografía y sus dimensiones. Esa coherencia debe garantizarse al generar los datos en el backend; una geometría incorrecta pero dentro de los límites no puede detectarse solo con estas comprobaciones.

## Verificación reproducible

`node --test frontend/tests/skeleton.test.mjs` transpila el componente instalado en memoria y comprueba sus elementos SVG y manejadores: conexiones, refresco de props, edición, límites y transformación inversa simulada. No lee fotos ni datos de usuarios y no crea archivos temporales. Estas pruebas no sustituyen una inspección visual en navegador ni prueban el cálculo de la matriz por el navegador o la persistencia del backend.
