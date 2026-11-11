# Plan Técnico: Módulo de Persistencia Ligera y Trazabilidad sin Base de Datos
> **Diseño histórico/propuesto, no contrato vigente ni evidencia de pruebas.** Ver [estado actual](docs/ESTADO_ACTUAL.md) y [módulo de persistencia](docs/MODULO_PERSISTENCIA_SIN_BASE_DE_DATOS.md). Ejemplos de esquemas y objetivos de latencia requieren comprobarse contra código y entorno.

## Denominación Formal del Componente: `File-System Session & Audit Store`

> **Documento de Diseño e Implementación Enfocado**  
> **Ámbito Exclusivo:** Persistencia, Estado de Sesión y Trazabilidad de Auditoría (Cero Motores DB)  
> **Referencia Normativa:** Rúbrica Track 4 X-RAIC 2026 (Restricción "Cero BD" + Criterio 6 Human-in-the-Loop)  

---

## 1. Justificación y Alcance Delimitado

La rúbrica oficial de Jabil para el Track 4 establece de forma explícita:  
> *"El equipo no genera una base de datos: solo implementa el método para evaluar la postura."*

Se eligieron archivos para evitar servicios DBMS y simplificar la demostración; no es un dictamen regulatorio que descarte SQLite. Su admisibilidad y autorización siguen pendientes. Objetivos de este diseño:
1. **Despliegue instantáneo (< 60 segundos)** sin scripts de inicialización de esquemas, migraciones o dependencias de drivers nativos del sistema operativo.
2. **Portabilidad absoluta** en cualquier entorno de evaluación o máquina portátil del jurado.
3. **Cumplimiento estricto del Criterio 6 (Trazabilidad y Human-in-the-Loop)**: Proveer un registro de auditoría con integridad verificable mediante hashes, sin firma digital que demuestre quién validó, editó o aprobó cada recomendación ergonómica.

---

## 2. Arquitectura del Componente: `File-System Session & Audit Store`

El almacenamiento se resuelve mediante tres mecanismos coordinados y desacoplados de cualquier DBMS:

```
┌────────────────────────────────────────────────────────────────────────┐
│                       MEMORIA VIVA (FASTAPI / PYDANTIC)                 │
│  • Estado volátil de la sesión activa del caso en análisis             │
│  • Cero dependencia de conexiones de socket o pools de base de datos  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ Persistencia en Disco Atómica
┌────────────────────────────────────────────────────────────────────────┐
│             SISTEMA DE ARCHIVOS LOCAL: /casos_jabil_workspace/          │
│                                                                        │
│   caso_01_levantamiento/                                               │
│   ├── session_state.json        (Snapshot del estado actual del caso)  │
│   └── audit_trail.json          (Registro histórico append-only con    │
│                                  hashing SHA-256 por cada acción)      │
└────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ Carga Única (Read-Only)
┌────────────────────────────────────────────────────────────────────────┐
│                 CATÁLOGO NORMATIVO ESTÁTICO: /config_normativo/         │
│  • reba_lookup_tables.json                                             │
│  • nom036_mac_rapp_tables.json                                         │
│  • jabil_standards_00023.json                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Especificación Técnica de Archivos y Contratos de Datos

### 3.1 Catálogo Normativo Estático (Configuración Read-Only)
* **Ubicación:** `config_normativo/`
* **Naturaleza:** Archivos JSON inmutables cargados en memoria una única vez durante el ciclo de vida del backend (`lifespan` de FastAPI).
* **Propósito:** Actuar como Fuente Única de Verdad (SSOT) de las matrices REBA, rangos de flexión y límites de planta Jabil (ej. límite 14 kg, zonas 1-5).
* **Archivos:**
  1. `reba_lookup_tables.json`: Matrices de cruce Grupo A, Grupo B y Tabla C.
  2. `nom036_mac_rapp_tables.json`: Ponderación de factores y bandas de color de las hojas de la NOM-036.
  3. `jabil_standards_00023.json`: Parámetros físicos oficiales de planta Chihuahua (alturas, distancias, Ley Silla).

### 3.2 Registro de Auditoría Verificable (`audit_trail.json`)
* **Ubicación:** `casos_jabil_workspace/caso_{id}/audit_trail.json`
* **Patrón de Persistencia:** *Append-Only Event Log* con encadenamiento de integridad (hash chaining).
* **Estructura del Registro:**
```json
{
  "case_id": "caso_01_levantamiento",
  "created_at_utc": "2026-11-06T12:00:00Z",
  "audit_trail_version": "1.0.0",
  "events": [
    {
      "event_id": "evt_001",
      "timestamp_utc": "2026-11-06T12:05:22.104Z",
      "specialist_id": "ING_EHS_CUU_042",
      "action": "EDITED",
      "target_recommendation_id": "REC-01",
      "original_ai_recommendation": {
        "hierarchy": "INGENIERIA",
        "description": "Instalar mesa elevadora hidráulica para reducir flexión de tronco de 48° a 15°.",
        "projected_reba": 3
      },
      "human_edited_recommendation": {
        "hierarchy": "INGENIERIA",
        "description": "Ajustar perfil Bosch de la estación existente a 105 cm y recolocar feeder en Zona 1.",
        "projected_reba": 2,
        "justification": "Se dispone de ajuste mecánico sin requerir compra de mesa hidráulica."
      },
      "initial_risk_score": 11,
      "residual_risk_score": 2,
      "previous_event_hash": "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000",
      "event_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0"
    }
  ]
}
```

### 3.3 Snapshot de Sesión (`session_state.json`)
* **Ubicación:** `casos_jabil_workspace/caso_{id}/session_state.json`
* **Naturaleza:** Snapshot mutable del estado de trabajo en curso para permitir recargar la interfaz sin pérdida de datos en caso de refrescar el navegador.
* **Propósito:** Almacena los ángulos actuales medidos, el estado de las recomendaciones (`PENDING`, `APPROVED`, `EDITED`, `REJECTED`) y las banderas de validación del especialista.

---

## 4. Garantías de Fiabilidad: Escritura Atómica sin DBMS

Para reducir escrituras parciales por archivo, sin garantizar recuperación ante todo fallo de energía ni transacciones entre archivos o coordinación multiproceso:

1. **Patrón de Escritura Atómica (`Write-Replace via Temporary File`):**
   * El sistema nunca escribe directamente sobre el archivo final.
   * Se escribe en un archivo temporal en el mismo sistema de archivos (`audit_trail.json.tmp`).
   * Se fuerza la sincronización a disco (`os.fsync`).
   * Se realiza una operación atómica de renombre (`os.replace`), garantizada por el kernel del sistema operativo.
2. **Sellado Criptográfico (SHA-256 Hash Chaining):**
   * Cada evento calcula un hash SHA-256 canónico de sus campos más el hash del evento anterior.
   * Una alteración sin recalcular hashes genera inconsistencias detectables. Quien pueda reescribir toda la cadena puede recalcularla; no hay inviolabilidad ni no-repudio.

---

## 5. Plan de Implementación Exclusivo

El desarrollo de este subsistema se estructura en 4 fases secuenciales estrictamente acotadas a la persistencia sin base de datos:

### Fase 1: Modelado de Esquemas Tipados (Pydantic Core)
* **Objetivo:** Definir las estructuras de datos que gobernarán el almacenamiento.
* **Entregables:**
  * `backend/app/session_store/models.py`:
    * `AuditActionEnum` (`APPROVED`, `EDITED`, `REJECTED`).
    * `RecommendationSnapshot` (contenido propuesto vs contenido aprobado).
    * `AuditEvent` (metadatos, timestamps, diffs, hashes).
    * `AuditTrailDocument` (lista de eventos y verificación de integridad).
    * `SessionStateDocument` (estado del caso en progreso).

### Fase 2: Implementación del Gestor de Archivos (`AuditFileManager`)
* **Objetivo:** Construir el motor de persistencia atómica en disco y hash chaining.
* **Entregables:**
  * `backend/app/session_store/audit_file_manager.py`:
    * Métodos de inicialización de espacio de trabajo para los 6 casos (`init_case_workspace`).
    * Método append atómico de eventos con cálculo de hash SHA-256 (`append_audit_event`).
    * Método de verificación de integridad del historial (`verify_audit_integrity`).
    * Métodos de lectura y guardado atómico de snapshot (`save_session_state`, `load_session_state`).

### Fase 3: Cargador de Catálogos Normativos en Memoria (`ConfigLoader`)
* **Objetivo:** Implementar la carga *stateless* y en caché de los archivos estáticos de reglas ergonómicas.
* **Entregables:**
  * `backend/app/session_store/config_loader.py`:
    * Lector de `reba_lookup_tables.json`.
    * Lector de `nom036_mac_rapp_tables.json`.
    * Lector de `jabil_standards_00023.json`.
    * Validación de esquemas en tiempo de arranque para fallar rápido (*fail-fast*) si un JSON está malformado.

### Fase 4: Batería de Pruebas Unitarias de Persistencia e Integridad
* **Objetivo:** Demostrar con pruebas deterministas que el almacenamiento es robusto y cumple la rúbrica.
* **Entregables:**
  * `tests/test_audit_file_manager.py`:
    * Prueba de persistencia y recarga de sesión.
    * Prueba de encadenamiento de hash SHA-256 en múltiples eventos.
    * Prueba de detección de manipulaciones (alterar un carácter en el JSON debe disparar error de integridad).
    * Prueba de atomicidad ante fallos de escritura.

---

## 6. Criterio de Éxito y Verificación

El componente se considerará completado cuando:
1. Mantener la operación actual sin drivers DBMS; no convierte la exclusión de SQLite en una prohibición normativa futura.
2. La ejecución de pruebas unitarias cree, actualice y valide la trazabilidad de los 6 casos en `/casos_jabil_workspace/` mediante puros archivos `.json`.
3. El tiempo de lectura/escritura de un evento de auditoría sea inferior a **5 milisegundos**.
