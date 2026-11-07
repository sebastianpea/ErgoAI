# ErgoAI

Copiloto de auditoría ergonómica (REBA + NOM-036-1-STPS-2018 + estándar Jabil 16-PE30-6500-00023)
con validación *Human-in-the-Loop* y trazabilidad SHA-256, sin base de datos.

## Ejecutar

Requisitos: Python 3.11+ y Node 18+.

```powershell
# 1. Backend (desde la raíz del repositorio)
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000

# 2. Frontend (otra terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173, usa el backend en VITE_API_URL
npm run dev:mock     # alternativa: datos simulados sin backend
```

### Visión artificial (crear casos desde fotos)

YOLOX + RTMPose WholeBody-133 sobre ONNX Runtime (mismo stack que `github.com/sebastianpea/ErgoAI`, rama `develop`).
Es opcional: sin esto, todo funciona excepto "Nuevo caso desde fotos".

```powershell
.venv\Scripts\python -m pip install -r backend/requirements-vision.txt
.venv\Scripts\python -m backend.app.vision.modelos   # descarga ~150 MB a models/ (una vez, con internet)
```

Después la demo funciona sin conexión. Los rostros se difuminan antes de guardar cada foto.
Variables: `ERGOAI_DEVICE=cuda` (con `onnxruntime-gpu`), `ERGOAI_MODELS_DIR`, `ERGOAI_MAX_FOTO_MB`.

Al primer arranque el backend crea `casos_jabil_workspace/` con 3 casos de demostración
(`backend/app/seed/casos_demo.json`). Borra esa carpeta para reiniciar la demo.

## Pruebas

```powershell
.venv\Scripts\python -m unittest discover -s tests -p "test_*.py"
cd frontend; npm run build   # comprobación de tipos + build
```

## Estructura

| Ruta | Contenido |
|---|---|
| `backend/main.py` | API FastAPI (CORS, rutas, manejo de errores) |
| `backend/app/core_ergonomics/` | Motor determinista: geometría angular, REBA (Tablas A/B/C), NOM-036, riesgo residual |
| `backend/app/services/casos.py` | Casos de uso: evaluación, corrección de puntos, decisiones, alertas, integridad |
| `backend/app/session_store/` | Persistencia atómica en JSON, `audit_trail.json` por caso y bitácora global encadenada |
| `backend/app/settings.py` | Rutas y tolerancias (variables `ERGOAI_*`) |
| `config_normativo/` | Catálogos normativos (única fuente de verdad de tablas y límites) |
| `frontend/` | React + Vite + TanStack Query. Contrato en `src/types/` = `backend/app/api/schemas.py` |

## API

| Método | Ruta | Uso |
|---|---|---|
| GET | `/casos` | Bandeja |
| GET | `/casos/{id}` | Detalle con ángulos, REBA, NOM-036, hallazgos, residual y estado de validación |
| PUT | `/casos/{id}/puntos/{vista}` | Corrección manual de keypoints → recalcula REBA |
| POST | `/casos/{id}/recomendaciones/{rec}/decision` | Aprobar / editar / rechazar (editar y rechazar exigen motivo) |
| GET | `/alertas` · POST `/alertas/{id}/atender` | Alertas para ergonomía/IE/EHS |
| GET | `/bitacora[?id_caso=]` · `/bitacora/verificar` | Bitácora y verificación de ambas cadenas de hash |
| GET | `/media/{id}/{archivo}` | Fotos del caso (solo `inputs/`) |

Documentación interactiva: http://localhost:8000/docs
