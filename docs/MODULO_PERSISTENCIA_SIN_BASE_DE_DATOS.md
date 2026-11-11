# Documentación Técnica: Módulo `File-System Session & Audit Store`

> **Componente:** `backend.app.session_store`  
> **Versión:** 1.0.0  
> **Estado:** Módulo implementado; resultados de prueba abajo son históricos, no validación del árbol actual.
> **Decisiones vigentes y límites:** [estado actual](ESTADO_ACTUAL.md). Archivos ahora; SQLite solo como alternativa futura previa aclaración y autorización.
> **Ámbito:** Persistencia Atómica, Trazabilidad Criptográfica y Catálogo Normativo (Cero Base de Datos)  
> **Cumplimiento Normativo:** Rúbrica Track 4 X-RAIC 2026 (Restricción "Cero BD" + Criterio 6 Human-in-the-Loop)  

---

## 1. Propósito y Justificación de Dominio

La decisión operativa por archivos toma como referencia esta cita, sin concluir una prohibición definitiva de SQLite:
> *"El equipo no genera una base de datos: solo implementa el método para evaluar la postura."*

El módulo **`File-System Session & Audit Store`** resuelve esta exigencia reemplazando los sistemas DBMS tradicionales (PostgreSQL, SQLite, MongoDB, Redis) por una arquitectura basada en:
1. **Estado en Memoria:** Objetos Pydantic v2 fuertemente tipados.
2. **Persistencia Local por Archivos:** Archivos JSON estructurados por caso en `/casos_jabil_workspace/`.
3. **Encadenamiento Criptográfico (SHA-256 Hash Chaining):** Integridad verificable de intervenciones humanas (*Human-in-the-Loop*), sin certificación de puntos ni firma digital.
4. **Catálogo Normativo Estático (SSOT):** Archivos JSON de solo lectura en `/config_normativo/` para umbrales REBA, NOM-036 y estándares Jabil `16-PE30-6500-00023`.

---

## 2. Estructura de Archivos del Módulo

```text
ErgoAI/
├── config_normativo/                   # SSOT Estático (Read-Only)
│   ├── jabil_standards_00023.json      # Límites Jabil CUU (14 kg, Ley Silla, alturas 95-125 cm)
│   ├── reba_lookup_tables.json         # Tablas A, B, C y umbrales angulares REBA
│   └── nom036_mac_rapp_tables.json     # Factores MAC/RAPP de NOM-036-1-STPS-2018
│
├── backend/app/session_store/          # Código fuente del módulo
│   ├── __init__.py                     # Fachada pública del paquete
│   ├── models.py                       # Contratos de datos Pydantic y Hash Chaining
│   ├── audit_file_manager.py           # Gestor de persistencia atómica y locks por caso
│   └── config_loader.py                # Cargador y validador de catálogos normativos
│
├── tests/
│   └── test_session_store.py           # Suite exhaustiva de pruebas unitarias (unittest)
│
└── casos_jabil_workspace/              # Espacio de trabajo local generado en runtime
    └── caso_{id}/
        ├── inputs/                     # Fotografías (frente, costado, aérea)
        ├── outputs/                    # Informes generados (PDF, XLSM)
        ├── audit_trail.json            # Registro de auditoría con sellado criptográfico
        └── session_state.json          # Snapshot del estado de la sesión
```

---

## 3. Patrones de Diseño Implementados

### 3.1 Patrón Write-Replace Atómico por Archivo
Reduce escrituras parciales; no garantiza recuperación ante cualquier corte de energía ni transacciones entre caso, snapshot y bitácoras:
1. Los datos se serializan en un archivo temporal (`.tmp_xxxx`) en el mismo directorio de destino.
2. Se fuerza la sincronización física del buffer al disco mediante `os.fsync(fileno)`.
3. Se invoca `os.replace(temp_path, target_path)`, garantizada como una operación atómica por el kernel del sistema operativo.

### 3.2 Registro Verificable con Hash Chaining
Cada evento de auditoría generado por la revisión del especialista humano contiene:
* `previous_event_hash`: Hash SHA-256 del evento cronológicamente anterior (o 64 ceros para el bloque génesis).
* `event_hash`: SHA-256 canónico calculado sobre el payload ordenado determinísticamente (`sort_keys=True`).

**Límite:** `verify_integrity()` recorre los eventos y detecta inconsistencias con `AuditIntegrityError`; no es tiempo constante. No impide reescribir y recalcular toda la cadena, ni aporta firma digital o no-repudio.

### 3.3 Concurrencia en Proceso (`RLock` por Caso)
Los locks no coordinan múltiples procesos o servidores. El gestor `AuditFileManager` utiliza bloqueos reentrantes (`threading.RLock`) asignados por cada `case_id`, previniendo colisiones de concurrencia cuando múltiples llamadas al API intentan registrar eventos sobre el mismo caso simultáneamente.

---

## 4. Guía de Uso del Módulo

### 4.1 Inicialización y Registro de Evento de Auditoría
```python
from backend.app.session_store import (
    AuditFileManager,
    AuditActionEnum,
    ControlHierarchyEnum,
    RecommendationSnapshot,
)

# Instanciar el gestor (usa casos_jabil_workspace/ por defecto)
mgr = AuditFileManager()

# Inicializar carpetas del caso
mgr.init_case_workspace("caso_01_levantamiento")

# Snapshot de la propuesta original de la IA
rec_ia = RecommendationSnapshot(
    recommendation_id="REC-01",
    hierarchy=ControlHierarchyEnum.INGENIERIA,
    description="Instalar mesa elevadora hidráulica para reducir flexión de tronco",
    projected_reba=3
)

# Snapshot de la corrección realizada por el especialista humano
rec_humana = RecommendationSnapshot(
    recommendation_id="REC-01",
    hierarchy=ControlHierarchyEnum.INGENIERIA,
    description="Ajustar perfil Bosch de estación existente a 105 cm",
    projected_reba=2,
    justification="Se cuenta con ajuste manual en la estación sin inversión en equipo"
)

# Registrar evento con hash encadenado automático
evento = mgr.append_audit_event(
    case_id="caso_01_levantamiento",
    event_id="EVT-001",
    specialist_id="ING_EHS_CHIH_042",
    action=AuditActionEnum.EDITED,
    target_recommendation_id="REC-01",
    original_ai_recommendation=rec_ia,
    human_edited_recommendation=rec_humana,
    initial_risk_score=11,
    residual_risk_score=2,
)

print(f"Evento registrado. Hash SHA-256: {evento.event_hash}")
```

### 4.2 Verificación de Integridad de la Auditoría
```python
is_valid, error = mgr.verify_case_audit_integrity("caso_01_levantamiento")
if not is_valid:
    print(f"¡ALERTA DE SEGURIDAD! Registro adulterado: {error}")
else:
    print("Cadena de auditoría 100% íntegra y verificada.")
```

### 4.3 Consulta de Estándares Normativos (SSOT en Memoria)
```python
from backend.app.session_store import default_config_loader

# Obtener parámetros Jabil Chihuahua
jabil = default_config_loader.get_jabil_standards()
limite_kg = jabil["load_limits"]["max_single_person_lift_kg"]  # 14.0 kg

# Obtener tablas REBA
reba = default_config_loader.get_reba_tables()
matriz_c = reba["table_c_matrix"]
```

---

## 5. Resultados de Pruebas y Validación Empírica

Ejecución de la suite completa de pruebas unitarias (`tests/test_session_store.py`):

```text
test_audit_event_hash_chaining .................................... OK
test_init_case_workspace .......................................... OK
test_normative_config_loader ...................................... OK
test_performance_latency_under_5ms ................................ OK
test_session_state_lifecycle ...................................... OK
test_tampering_detection .......................................... OK
test_zero_database_dependency ..................................... OK

----------------------------------------------------------------------
Ran 7 tests in 0.007s - OK
```

### Métricas Clave de Desempeño
* **Dependencia de DB:** 0 módulos de base de datos cargados (`sqlite3`, `sqlalchemy`, `psycopg2`, etc. están completamente ausentes).
* **Latencia de Persistencia:** Menor a **2.5 milisegundos** por evento en escritura atómica con fsync.
* **Tiempo Total de Suite:** 7 pruebas en **7 milisegundos**.
* **Detección de inconsistencias:** evidencia histórica acotada a los casos probados; no demuestra resistencia frente a reescritura completa de hashes.
