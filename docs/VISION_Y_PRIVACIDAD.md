# Fotografías protegidas y esqueletos verificables

**Se aplica difuminado gaussiano circular/elíptico sólo sobre los rostros localizados, conservando el torso y el fondo.** Si falta evidencia facial de alguna persona conocida, la localización es ambigua o falla un detector, **no se muestra la imagen**: la API devuelve 422 con aviso de revisión, nunca el original ni una imagen negra como respuesta exitosa.

## Qué verá el especialista

- El esqueleto conserva las coordenadas y dimensiones de la imagen usada en la inferencia. No se recorta la imagen ni se inventan puntos para acomodar una máscara.
- Se usan las cajas de **todas** las personas del análisis y detección facial frontal/de perfil de OpenCV. Sin sidecar se usa además el detector de personas HOG. Dos puntos de pose no bastan para inventar una región facial.
- Cada rostro requiere una caja finita dentro de la imagen, de al menos 20×20 píxeles y relación ancho/alto entre 0.5 y 2. Para cada persona conocida debe existir un rostro contenido en la mitad superior de su caja. Una asignación ambigua se rechaza. Son filtros conservadores, no una confianza calibrada.
- La elipse queda dentro de la caja facial, sin máscara rectangular ni márgenes sobre el torso. GaussianBlur usa sigma igual a un cuarto del lado mayor de la cara. Fuera de las elipses no se cambian píxeles durante el filtro; JPEG puede introducir diferencias de compresión.
- Una persona sin rostro sustentado retiene **toda** la imagen, aunque otra sí tenga rostro. Las vistas opcionales pasan por la misma política; la lateral sin persona continúa rechazándose.
- **Los detectores pueden omitir personas o localizar mal un rostro; el difuminado conserva información y no garantiza anonimización completa.** Los perfiles difíciles, oclusiones y caras pequeñas pueden impedir mostrar la toma. Revise antes de compartir; no valide puntos sólo porque se dibujan. Esta unidad no cambia la elección manual por vista ni establece identidad entre vistas.

Corregir puntos recalcula los ángulos y conserva la bitácora. Corregir el tronco no implica que baje el REBA total: éste combina segmentos y modificadores mediante tablas.

## Recorrido de los archivos

| Etapa | Comportamiento |
| --- | --- |
| Persistencia | `ServicioCasos` conserva JSON, `AuditFileManager` y bitácoras encadenadas; no incorpora una base de datos. |
| Semilla de fotos reales | Lee la imagen local, aplica `reducir` e infiere sobre ese tamaño. Guarda una copia protegida y no modifica la fuente. Sin visión disponible, entrega puntos vacíos y un aviso de revisión; nunca escala una plantilla ajena. |
| Semilla sin fotografía | Genera una imagen sintética con los puntos de su propia plantilla y un aviso explícito de demostración, no una evaluación de una persona real. |
| Carga | Valida las entradas antes de crear el caso. Recodifica únicamente píxeles protegidos, elimina EXIF y guarda regiones internas de privacidad mediante el escritor JSON atómico existente. |
| Evidencia de privacidad | El archivo lateral `nombre.jpg.privacidad.json` contiene versión de política, SHA-256 de los bytes protegidos y regiones. Evita perder contexto al volver a servir una imagen cuyas caras ya están cubiertas. La política **3** representa elipses con difuminado gaussiano. Un hash distinto, versión desconocida, regiones inválidas/vacías o evidencia ilegible retiene la imagen y requiere revisión. La política **2**, rectangular, nunca se interpreta como evidencia de blur ni se redetecta sobre sus máscaras para autorizar su visualización. Esta evidencia no sustituye las cadenas de auditoría ni protege contra un atacante que pueda modificar libremente el workspace. |
| Geometría antigua | Si los píxeles no coinciden con las dimensiones, faltan o no pueden verificarse, oculta puntos y requiere revisión en la respuesta. No reescribe el caso ni adivina anatomía. Esta comprobación añade lecturas de imágenes a la evaluación. |
| `GET /media/{id_caso}/{archivo}` | Reutiliza la validación de ruta y devuelve PNG protegido con `Cache-Control: no-store`. Sin evidencia suficiente: 422 JSON `{"detail":"Imagen no disponible por privacidad: requiere revisión del rostro de todas las personas."}`, también `no-store`. Archivo inexistente: 404. Archivo no decodificable, incluido SVG: 422. Nunca entrega bytes originales. |

La decisión de guardar o servir no se basa únicamente en `rostro_anonimizado`: valida las regiones sustentadas. Por compatibilidad interna con el estimador, los fotogramas sin evidencia se guardan negros con regiones vacías; **la API los rechaza**, no los presenta como fotos protegidas revisables. Las coordenadas y dimensiones no cambian.

## Workspaces existentes y límite de migración

No se ejecutan migraciones destructivas ni resiembras globales. Las imágenes, JSON y cadenas de auditoría existentes se conservan. Las fotografías antiguas sin sidecar se detectan y difuminan al responder por HTTP, o se retienen si no hay evidencia suficiente. Nunca se sobrescribe el original ni se crea evidencia lateral durante la lectura. Las copias con sidecar de política 2 se retienen: recuperar contexto requiere una fuente original conservada, no reinterpretar rectángulos.

**Las copias guardadas completamente negras por la primera implementación no pueden recuperarse desde sus píxeles.** Esta corrección no las restaura, sobrescribe ni resiembra. Si se necesita una nueva evaluación con contexto, deberá partirse de una fuente original conservada mediante el flujo autorizado, no intentar reconstruir una fotografía a partir de puntos.

No exponga `inputs` como directorio estático: el límite de protección es la API. Los archivos originales locales y las descargas anteriores siguen siendo confidenciales; la API no revoca copias ni cachés existentes. No se añaden dependencias, descargas de modelos ni transferencias externas.

## Verificación y precisión

```text
.venv/bin/python -m pytest -p no:cacheprovider tests/test_privacidad.py -q
.venv/bin/python -m pytest -p no:cacheprovider tests/test_seed_vision.py tests/test_api.py -q
```

Las pruebas sintéticas verifican varios rostros, forma elíptica y reducción de detalle, reutilización de todas las cajas de persona, respuesta de revisión ante un rostro incierto, píxeles guardados y servidos, conservación de torso/fondo, rechazo de evidencia rectangular/obsoleta y originales/registros sin modificaciones. Las pruebas de precisión no confunden estos mocks con exactitud anatómica real.

`test_vision_precision_within_reba_range` requiere ONNX y `backend/app/seed/dataset_jabil/angulos_referencia.json`, con ángulos anotados y validados por un especialista: `{"foto.jpg": {"tronco": 25, "brazo": 45}}`. Sin referencias o modelos se omite explícitamente, no se cuenta como acierto. Con referencias, mide los ángulos inferidos y exige al menos 90% de mediciones con confianza ≥0.5 dentro de ±5°. El archivo de referencias existe localmente, pero su presencia no acredita procedencia ni validación experta. Sin esa evidencia no se certifica precisión; ejecutar ONNX tampoco demuestra ese porcentaje ni certifica la privacidad. Ver [validaciones pendientes](ESTADO_ACTUAL.md).
