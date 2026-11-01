# Marco Arquitectónico y Directrices Conceptuales: ErgoAI

> **Documento Rector del Proyecto**  
> **Versión:** 1.0.0  
> **Ámbito:** Antigravity / Ecosistema de Manufactura Jabil / Reto X-RAIC 2026 (Track 4)  
> **Estado:** Aprobado para Diseño e Implementación  

---

## 1. Visión, Misión y Límites del Sistema

### 1.1 Misión Central
Desarrollar un prototipo funcional de un **Agente Inteligente de Ergonomía** concebido como un **auditor técnico y copiloto analítico** para estaciones de manufactura y ensamble.

El propósito fundamental de la solución es:
1. **Auditar y validar evaluaciones ergonómicas previas**: Contrastar los registros históricos levantados manualmente en piso contra la evidencia postural objetiva extraída de fotografías estáticas multi-ángulo (frontal, lateral y cenital).
2. **Detectar y alertar discrepancias biomecánicas**: Identificar subestimaciones o errores de captura en ángulos articulares (cuello, tronco, brazos, piernas).
3. **Generar propuestas de rediseño de ingeniería**: Priorizar controles de ingeniería física y adecuaciones de layout según la **NOM-036-1-STPS-2018** y la normativa corporativa Jabil antes que medidas administrativas.
4. **Calcular el riesgo residual esperado**: Simular el impacto ergonómico post-intervención para proyectar la reducción efectiva de lesiones y optimizar el tiempo de respuesta de los equipos de soporte.

---

### 1.2 Límites Críticos del Dominio (Lo que el sistema ES y lo que NO ES)

Para evitar desvíos de alcance (*scope creep*) y garantizar el cumplimiento estricto de la rúbrica del reto, se establecen las siguientes fronteras inmutables:

```
┌──────────────────────────────────────────────┐  ┌──────────────────────────────────────────────┐
│                  EL SISTEMA ES               │  │                EL SISTEMA NO ES              │
├──────────────────────────────────────────────┤  ├──────────────────────────────────────────────┤
│ • Copiloto de auditoría para el ergónomo.    │  │ • NO es un monitor de signos vitales.        │
│ • Validador de consistencia angular y REBA.  │  │ • NO es un detector de caídas o epilepsia.   │
│ • Analizador de fotografías estáticas (3D).  │  │ • NO procesa streams continuos de CCTV.      │
│ • Generador de planes de acción NOM-036.     │  │ • NO es un sistema de vigilancia punitiva.   │
│ • Canal exclusivo para Supervisión / IE / EHS│  │ • NO emite alertas directas al trabajador.   │
│ • Persistencia ligera y reproducible.        │  │ • NO despliega clusters de bases de datos.   │
└──────────────────────────────────────────────┘  └──────────────────────────────────────────────┘
```

---

## 2. Principios de Diseño e Invariantes del Negocio

Cualquier propuesta, modificación o extensión del sistema debe respetar de forma estricta los siguientes cinco invariantes:

### Invariante 1: "El Agente Propone, el Especialista Decide"
Ninguna reclasificación de riesgo, cambio de layout o modificación de estación podrá ejecutarse de forma autónoma.
- El sistema actúa como un generador estructurado de propuestas de ingeniería.
- La aprobación, edición o rechazo humano por parte del especialista ergonómico o supervisor es un **paso bloqueante obligatorio**.
- El sistema debe mantener un registro de auditoría inmutable de quién validó cada acción y qué modificaciones introdujo (Trazabilidad estricta).

### Invariante 2: Destinatario Único de Alertas (Supervisión e Ingeniería)
Queda estrictamente prohibida cualquier retroalimentación en tiempo real o interfaz orientada al operador de línea (pantallas en estación, dispositivos hápticos o pulseras vibratorias).
* **Justificación de Seguridad Operativa:** En estaciones con prensas, líneas de inserción y soldadura (SMT/Backend) o tráfico de vehículos autónomos (AMR), las alertas directas inducen distracción cognitiva, riesgo de atrapamiento o accidentes graves.
* **Justificación de Productividad:** Las interrupciones no planificadas degradan la cadencia productiva (*Takt Time*) y penalizan la tasa de balanceo de línea ($LBR \ge 85\%$).
* **Justificación Organizacional:** El operario carece de facultades de ingeniería y presupuesto para alterar el layout físico o gestionar un control de cambios (*MOC*).

### Invariante 3: Jerarquía Estricta de Controles Ergonómicos
El motor de recomendaciones debe aplicar rigurosamente la prelación establecida por la NOM-036-1-STPS-2018 y las directrices de Ingeniería Industrial de Jabil:
1. **Prioridad 1: Controles de Ingeniería y Rediseño de Puesto:** Reubicación de componentes a zonas de alcance 1 y 2, ajuste de altura de mesas (95–125 cm), provisión de asistencias mecánicas (*lifters*), adecuación de hueco para piernas en sedestación ($\ge 55 \times 60\text{ cm}$) y reposapiés.
2. **Prioridad 2: Controles Administrativos y de Rotación:** Implementación de roles de descanso y relevo o rotación entre puestos de pie y sentado para dar cumplimiento a la Ley Silla (evitar bipedestación continua $> 3\text{ horas}$).

### Invariante 4: Prevalencia del Estándar Restrictivo Jabil
Cuando exista discrepancia entre la normativa federal (NOM-036) y los estándares internos de planta Chihuahua (`16-PE30-6500-00023`), **prevalece siempre el límite corporativo más estricto**:
* **Manejo Manual de Carga:** El límite máximo absoluto por persona es de **14 kg** (la NOM-036 permite hasta 25 kg en condiciones ideales). Toda carga superior a 14 kg exige obligatoriamente asistencia mecánica o levantamiento en equipo con evaluación médica y trámite MOC.

### Invariante 5: Cumplimiento de la Restricción "Cero Base de Datos Externa"
Para alinearse con las especificaciones técnicas del concurso y garantizar un despliegue instantáneo en la fase de demostración (1 minuto de preparación):
* No se desplegarán servicios ni contenedores de motores DBMS externos (PostgreSQL, TimescaleDB, MySQL, MongoDB, Redis).
* La persistencia de configuraciones, conocimiento normativo y trazabilidad de evaluaciones se resolverá mediante almacenamiento local estructurado desacoplado (archivos JSON/YAML inmutables, SQLite embebido serverless y sincronización con hojas de cálculo oficiales de Jabil).

---

## 3. Filosofía Arquitectónica y Patrones

El sistema adoptará los principios de **Arquitectura Limpia (Clean Architecture)** y **Puertos y Adaptadores (Arquitectura Hexagonal)** para garantizar máxima modularidad, testabilidad sin dependencias y aislamiento de la lógica de negocio ergonómica.

```
                      ┌──────────────────────────────────────────────┐
                      │             ADAPTADORES DE ENTRADA           │
                      │  (CLI, Dashboard Web/Desktop, Ingesta Excel) │
                      └──────────────────────┬───────────────────────┘
                                             │
                                             ▼
                      ┌──────────────────────────────────────────────┐
                      │              CASOS DE USO (CORE)             │
                      │  • AuditarEvaluacionPrevia                    │
                      │  • CalcularDiscrepanciasAngulares            │
                      │  • EstimarRiesgoResidual                     │
                      │  • GenerarPlanDeIngenieria                   │
                      └───────┬──────────────────────────────┬───────┘
                              │                              │
                              ▼                              ▼
    ┌───────────────────────────────────┐  ┌───────────────────────────────────┐
    │       DOMINIO Y ENTIDADES         │  │     PUERTOS / ADAPTADORES OUT     │
    │  • Modelos Tipados (Pydantic)     │  │  • Motor Visión (Pose 3D)         │
    │  • Reglas REBA / RULA / NOM-036   │  │  • Base de Conocimiento Local     │
    │  • Invariantes Cinemáticos Jabil │  │  • Exportador Excel (.xlsm)       │
    └───────────────────────────────────┘  └───────────────────────────────────┘
```

### 3.1 Separación de Responsabilidades por Capas

1. **Capa de Dominio (Domain Core):**
   - Contiene exclusivamente la lógica ergonómica pura, fórmulas matemáticas vectoriales, cálculo de matrices REBA, límites antropométricos de Jabil y modelos tipados de datos.
   - Es 100% agnóstica a la infraestructura: no sabe qué librería de visión estima la pose, ni qué framework renderiza el panel visual, ni en qué formato físico se persisten los datos.
2. **Capa de Casos de Uso (Application Services):**
   - Orquesta los flujos de auditoría: toma la evaluación registrada, invoca la extracción de ángulos sobre las fotos, compara valores, detecta desviaciones, aplica la jerarquía de controles de la NOM-036 y calcula el riesgo residual.
3. **Capa de Adaptadores (Adapters & Infrastructure):**
   - **Adaptadores de Visión:** Implementan la extracción de puntos articulares tridimensionales a partir de imágenes locales.
   - **Adaptadores de Datos y Persistencia:** Lectores y escritores de archivos Excel (`openpyxl` sobre `16-PE80-6500-00014-H.xlsm`), serializadores JSON y repositorios SQLite locales.
   - **Adaptadores de Presentación:** Paneles de supervisión e interfaces de visualización para el especialista.

---

## 4. Estándares de Calidad de Código (*Clean Code*)

Para asegurar un proyecto homogéneo, mantenible y libre de deuda técnica, todo desarrollo debe seguir las siguientes reglas de ingeniería:

### 4.1 Principio DRY (*Don't Repeat Yourself*) y Fuente Única de Verdad (*SSOT*)
* Las constantes normativas (tablas REBA, rangos de flexión de tronco, límites de peso, cotas de layout) se definirán **exactamente una vez** dentro del catálogo de dominio. Queda terminantemente prohibido duplicar valores numéricos o reglas "mágicas" dentro de controladores, vistas o scripts sueltos.
* Las operaciones vectoriales y el cálculo de ángulos articulares residirán en utilitarios matemáticos puros y centralizados.

### 4.2 Tipado Estático y Modelado Robusto
* Todo el código Python debe utilizar **Type Hints** de manera estricta y validar sus esquemas mediante estructuras fuertemente tipadas (`dataclasses` o modelos de `Pydantic`).
* Cada contrato entre componentes (por ejemplo: coordenadas articulares estimadas, reporte de discrepancia, ficha de auditoría) estará explícitamente formalizado en una clase de datos.

### 4.3 Centralización de Configuraciones y Tolerancias
* Las variables de entorno, umbrales de detección de discrepancias (por ejemplo, tolerancia admisible de $\pm 5^\circ$ en flexión antes de disparar alerta) y rutas de trabajo deben administrarse desde un módulo centralizado de configuración (*Settings*). Ninguna clase de negocio tendrá rutas o credenciales hardcodeadas.

### 4.4 Manejo Predictible de Errores y Registro de Eventos (*Logging*)
* No se permiten bloques `try/except` silenciosos o genéricos (`except Exception: pass`).
* Se implementará un sistema de logging estructurado que permita diagnosticar con claridad qué archivo se procesó, qué discrepancias se detectaron y qué factores gatillaron el riesgo residual estimado.

---

## 5. Criterios de Evaluación y Toma de Decisiones

Cuando surja una disyuntiva técnica o propuesta de cambio durante el ciclo de vida del proyecto, el equipo y cualquier agente que intervenga deberán evaluar la propuesta contra este checklist prioritario:

1. **¿Aporta directamente a los criterios de la Rúbrica Oficial?**
   - Prioridad máxima: Precisión del cálculo REBA (20 pts), estimación angular (15 pts), calidad del informe NOM-036 con controles de ingeniería (15 pts), trazabilidad del especialista (6 pts) y cálculo de riesgo residual (4 pts).
2. **¿Respeta las restricciones logísticas de demostración?**
   - La solución debe encender y ejecutar la auditoría de los casos de prueba en menos de **60 segundos** en una máquina portátil estándar, sin requerir acceso a internet ni servicios en la nube externos.
3. **¿Protege la privacidad de los operarios?**
   - Las imágenes procesadas deben mantenerse en almacenamiento local volátil o anonimizado, sin retención de biometría facial.
4. **¿Pertenece al Núcleo de Auditoría o al Roadmap de Fase 2?**
   - Si una función involucra telemetría continua de video en tiempo real, conectividad a cámaras de planta, detección de desmayos o ingesta en series de tiempo (TimescaleDB / Redis), **se documenta como propuesta de escalabilidad para el pitch y la documentación técnica**, pero **no se incorpora al código base del prototipo**, evitando sobrecargar y desestabilizar la solución central.

---

*Este marco arquitectónico constituye la referencia técnica inmutable para el diseño de componentes, algoritmos y contratos de datos del proyecto ErgoAI.*

