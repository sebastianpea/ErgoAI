# Unificación de ramas en main
Objetivo: integrar las ramas existentes sin descartar las capacidades de main. Rama: integration/unify-main; destino: main local; sin push ni eliminación de ramas.
Entrega: merges por rama conservando sus commits; cambios de resolución separados por integración. Verificación: pytest, build frontend y revisión independiente. Espejo Engram no disponible.

## Specs
- S1: "analiza el proyecto y unifica los cambios con las tistitnas cambios de las ramas para que este totalente unificado en main"

## Tasks
- T1 [S1] Analizar historia, ramas y contratos compartidos — route: inline + exploración delegada por alcance; done; evidencia: fetch correcto, grafo y mapa de contratos; commit: pendiente.
- T2 [S1] Integrar feat/vision-privacy-dashboard conservando configuración de main — route: inline (integraciones dependientes); in_progress; commit: pendiente.
- T3 [S1] Integrar develop conservando funcionalidades acumuladas — route: inline (depende de T2); pending; commit: pendiente.
- T4 [S1] Verificar integración, revisar riesgos e incorporar en main local — route: inline + verificación independiente por privacidad/contratos compartidos; pending; commit: pendiente.

## Log
- L1: "analiza el proyecto y unifica los cambios con las tistitnas cambios de las ramas para que este totalente unificado en main"
- L2: Árbol inicial limpio. main=f34252a; origin/develop=b08dde3; origin/feat/vision-privacy-dashboard=2d0a0db. origin/front-end=261d5ce y origin/ergoai-unificado=067acd4 ya son ancestros de main. Fetch completado correctamente.
- L3: La integración conserva la historia existente; no se reescriben commits ni se publican cambios. Primer cruce previsto: frontend/src/api.ts y frontend/vite.config.ts. Los merges incorporan miles de líneas previamente escritas; el presupuesto de ~400 líneas se aplica a resoluciones nuevas, no a reescribir esas funcionalidades.
- L4: No hay RED significativo para una integración histórica completa; se ejecutan suite base, regresiones existentes, build y verificaciones de contratos. Cualquier corrección de comportamiento nueva se reproduce antes de modificarla. No hay herramientas Engram activas; continuidad conservada en este documento.
