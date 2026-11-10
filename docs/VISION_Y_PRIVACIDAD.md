# Fotografías protegidas y esqueletos verificables

**Se cubren las regiones de cabeza con máscaras sólidas, conservando el torso y el fondo cuando hay evidencia suficiente.** Si no hay detecciones, falta evidencia de cabeza para alguna persona conocida o falla un detector, se cubre toda la imagen. No se devuelve el original sin protección.

## Qué verá el especialista

- El esqueleto conserva las coordenadas y dimensiones de la imagen usada en la inferencia. No se recorta la imagen ni se inventan puntos para acomodar una máscara.
- Se combinan las cajas de **todas** las personas detectadas en el análisis, sus puntos de cabeza con confianza suficiente y detección facial frontal/de perfil de OpenCV. Para fotografías antiguas sin evidencia guardada se usa además el detector de personas HOG de OpenCV.
- Las regiones incluyen márgenes alrededor de cara, pelo y orejas y una zona superior conservadora de cada persona. La máscara sólida evita que un difuminado débil conserve rasgos identificables.
- Una persona conocida sin cabeza localizable provoca máscara completa, aunque sí se haya encontrado el rostro de otra persona. Una vista opcional sin pose también pasa por esta política; la lateral sin persona continúa rechazándose.
- **Los detectores pueden omitir personas o localizar mal una cabeza. Su éxito no garantiza anonimización completa.** Revise la protección antes de compartir; no valide puntos sólo porque se dibujan. La máscara completa impide revisar visualmente la anatomía y debe tratarse como incertidumbre, no como una evaluación fiable.

Corregir puntos recalcula los ángulos y conserva la bitácora. Corregir el tronco no implica que baje el REBA total: éste combina segmentos y modificadores mediante tablas.

## Recorrido de los archivos

| Etapa | Comportamiento |
| --- | --- |
| Persistencia | `ServicioCasos` conserva JSON, `AuditFileManager` y bitácoras encadenadas; no incorpora una base de datos. |
| Semilla de fotos reales | Lee la imagen local, aplica `reducir` e infiere sobre ese tamaño. Guarda una copia protegida y no modifica la fuente. Sin visión disponible, entrega puntos vacíos y un aviso de revisión; nunca escala una plantilla ajena. |
| Semilla sin fotografía | Genera una imagen sintética con los puntos de su propia plantilla y un aviso explícito de demostración, no una evaluación de una persona real. |
| Carga | Valida las entradas antes de crear el caso. Recodifica únicamente píxeles protegidos, elimina EXIF y guarda regiones internas de privacidad mediante el escritor JSON atómico existente. |
| Evidencia de privacidad | El archivo lateral `nombre.jpg.privacidad.json` contiene versión de política, SHA-256 de los bytes protegidos y regiones. Evita perder contexto al volver a servir una imagen cuyas caras ya están cubiertas. Un hash distinto, versión desconocida o evidencia ilegible obliga a detectar nuevamente; nunca habilita una respuesta original. Esta evidencia no sustituye las cadenas de auditoría ni protege contra un atacante que pueda modificar libremente el workspace. |
| Geometría antigua | Si los píxeles no coinciden con las dimensiones, faltan o no pueden verificarse, oculta puntos y requiere revisión en la respuesta. No reescribe el caso ni adivina anatomía. Esta comprobación añade lecturas de imágenes a la evaluación. |
| `GET /media/{id_caso}/{archivo}` | Reutiliza la validación de ruta existente y devuelve PNG protegido con `Cache-Control: no-store`. Archivo inexistente: 404. Archivo no decodificable, incluido SVG: 422. No entrega los bytes del original. |

La decisión de guardar o servir no se basa únicamente en `rostro_anonimizado`: vuelve a aplicar las regiones sustentadas o el cierre completo. Las coordenadas y dimensiones son las mismas antes y después de proteger; la recodificación JPEG puede introducir pequeñas diferencias de compresión alrededor de las máscaras.

## Workspaces existentes y límite de migración

No se ejecutan migraciones destructivas ni resiembras globales. Las imágenes, JSON y cadenas de auditoría existentes se conservan. Las fotografías antiguas se protegen al responder por HTTP, sin sobrescribir el original ni crear evidencia lateral durante la lectura.

**Las copias guardadas completamente negras por la primera implementación no pueden recuperarse desde sus píxeles.** Esta corrección no las restaura, sobrescribe ni resiembra. Si se necesita una nueva evaluación con contexto, deberá partirse de una fuente original conservada mediante el flujo autorizado, no intentar reconstruir una fotografía a partir de puntos.

No exponga `inputs` como directorio estático: el límite de protección es la API. Los archivos originales locales y las descargas anteriores siguen siendo confidenciales; la API no revoca copias ni cachés existentes. No se añaden dependencias, descargas de modelos ni transferencias externas.

## Verificación y precisión

```text
.venv/Scripts/python.exe -m pytest tests/test_vision.py tests/test_vision_precision.py tests/test_privacidad.py tests/test_seed_vision.py tests/test_api.py -q
```

Las pruebas sintéticas verifican varios rostros, reutilización de todas las cajas de persona, máscara completa ante una cabeza incierta, píxeles guardados y servidos, conservación de torso/fondo, evidencia obsoleta y originales/registros sin modificaciones. Las pruebas de precisión no confunden estos mocks con exactitud anatómica real.

`test_vision_precision_within_reba_range` requiere ONNX y `backend/app/seed/dataset_jabil/angulos_referencia.json`, con ángulos anotados y validados por un especialista: `{"foto.jpg": {"tronco": 25, "brazo": 45}}`. Sin referencias o modelos se omite explícitamente, no se cuenta como acierto. Con referencias, mide los ángulos inferidos y exige al menos 90% de mediciones con confianza ≥0.5 dentro de ±5°. Las referencias validadas no están incluidas actualmente; ejecutar ONNX no demuestra ese porcentaje ni certifica la privacidad.
