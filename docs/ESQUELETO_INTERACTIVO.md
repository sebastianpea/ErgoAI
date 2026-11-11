# Revisar a una persona sin inventar su postura

En **Análisis**, el esqueleto empieza apagado. La imagen sigue pasando por la protección facial del servidor: apagar la superposición nunca solicita el original. Si falta evidencia de privacidad, la imagen se retiene para revisión.

## Ruta rápida

1. Activa **Mostrar esqueleto** con el switch (también admite teclado).
2. Elige **Todas** para ver poses separadas, sin editar ni calcular una postura conjunta; elige un ID para enfocar sus puntos.
3. Ergonomía puede arrastrar puntos visibles o usar **Tab + flechas** (1 píxel; **Mayús + flecha**, 10 píxeles). Cada corrección recalcula el caso y queda en bitácora.
4. Repite la selección manualmente en cada imagen. `persona-1` de una vista **no identifica** a `persona-1` de otra.

## Evidencia y límites

- Cada detección conserva sus propios puntos y un ID local persistido con la imagen. No se elige automáticamente la persona más grande ni se duplica una pose para otras detecciones. Los IDs no son seguimiento ni identidades estables después de una nueva inferencia.
- Los puntos de baja confianza, no finitos, fuera de la imagen/caja o coincidentes no se completan, recortan ni apilan. En una pose de respaldo sin caja detectada no se atribuyen articulaciones a una persona. Una articulación ausente exige nueva evidencia y revisión; el editor no la crea.
- Una conexión exige ambos extremos fiables (confianza ≥ 0,4 inclusive) o corregidos, dentro de la imagen. Los datos históricos pueden conservar puntos inciertos, pero no se dibujan. Azul marino significa corrección manual, no mayor confianza del detector.
- Los controles son conservadores y heurísticos. Una oclusión o anatomía inconsistente que el modelo puntúe con confianza alta puede escapar a los filtros. No hay garantía de error cero, validación anatómica completa ni reconstrucción 3D. Una conexión oculta no demuestra que falte una extremidad.
- Se requiere seleccionar el objetivo de cada vista y confirmar la evidencia operativa antes del riesgo final. No se infieren modificadores combinando automáticamente identidades entre fotos.

## API y compatibilidad

| Operación | Contrato |
|---|---|
| Selección | `PUT /casos/{id}/persona/{vista}` con `persona_id` local; `null` vuelve a Todas |
| Corrección | `PUT /casos/{id}/puntos/{vista}` exige el `persona_id` seleccionado; no modifica otras poses |
| Histórico | Un caso antiguo con `puntos` pero sin `personas` se proyecta como `legacy`, sin migrar el archivo; sigue aceptando correcciones antiguas |
| Captura rápida | Devuelve `poses`; no elige objetivo ni publica ángulos de una persona implícita. La imagen protegida no lleva esqueleto y es `null` si falta evidencia facial. Para seleccionar y medir, crea un caso |

Cambiar el objetivo invalida confirmaciones de esa vista y propuestas pendientes dependientes de la pose. Una evaluación con recomendaciones decididas o NOM-036 capturada exige otro caso para cambiar de persona; no se reasigna silenciosamente.

## Guardado y coordenadas

El `viewBox` comparte las dimensiones de la imagen protegida; el arrastre usa la inversa de `getScreenCTM()` y limita las correcciones a los bordes. No se reescala una plantilla para disimular geometría incompatible.

Cambios del servidor en puntos, persona, URL, vista o dimensiones reemplazan el estado local y cancelan el gesto anterior. Un refresco con valores idénticos conserva ediciones locales. Un error de guardado restaura los puntos persistidos y muestra el error.

## Verificación

`node --test frontend/tests/skeleton.test.mjs frontend/tests/camera.test.mjs` comprueba JSX y manejadores en memoria, sin fotos reales. Las pruebas de `tests/test_case_evidence.py` ejercitan selección, aislamiento, rechazos sin mutación, compatibilidad y privacidad de captura rápida por API. No sustituyen inspección visual en navegador ni calibración del modelo con anatomía real.
