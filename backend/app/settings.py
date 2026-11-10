"""
Configuración centralizada (ARCHITECTURE.md §4.3).
Rutas, credenciales, modelos y tolerancias se resuelven dinámicamente mediante
variables de entorno (con soporte dual de prefijos ERGOAI_* y estándar .env)
y valores por defecto resueltos respecto a la raíz del repositorio, garantizando
la eliminación total de hardcode y compatibilidad multi-entorno.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cargar_dotenv(ruta_env: Path) -> None:
    """Carga variables de entorno desde `.env` si existe, sin sobrescribir variables ya definidas."""
    if not ruta_env.is_file():
        return
    try:
        for linea in ruta_env.read_text(encoding="utf-8").splitlines():
            limpia = linea.strip()
            if not limpia or limpia.startswith("#") or "=" not in limpia:
                continue
            clave, valor = limpia.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip().strip("'\""))
    except OSError:
        pass


# Intentar cargar .env desde ubicaciones estándar (CWD, REPO_ROOT y raíz superior)
for posible_env in [
    Path.cwd() / ".env",
    REPO_ROOT / ".env",
    REPO_ROOT.parent / ".env",
]:
    _cargar_dotenv(posible_env)


def _env_str(claves: List[str] | str, defecto: str) -> str:
    """Obtiene el primer valor definido en variables de entorno entre los alias provistos."""
    if isinstance(claves, str):
        claves = [claves]
    for k in claves:
        v = os.environ.get(k)
        if v is not None and v.strip() != "":
            return v.strip()
    return defecto


def _env_float(claves: List[str] | str, defecto: float) -> float:
    """Obtiene y castea a float el primer valor numérico válido entre los alias provistos."""
    if isinstance(claves, str):
        claves = [claves]
    for k in claves:
        v = os.environ.get(k)
        if v is not None and v.strip() != "":
            try:
                return float(v.strip())
            except ValueError:
                pass
    return defecto


def _env_int(claves: List[str] | str, defecto: int) -> int:
    """Obtiene y castea a int el primer valor entero válido entre los alias provistos."""
    if isinstance(claves, str):
        claves = [claves]
    for k in claves:
        v = os.environ.get(k)
        if v is not None and v.strip() != "":
            try:
                return int(v.strip())
            except ValueError:
                pass
    return defecto


def _ruta(claves: List[str] | str, defecto: Path) -> Path:
    """Resuelve rutas del sistema de archivos a partir de variables de entorno o valor por defecto."""
    if isinstance(claves, str):
        claves = [claves]
    for k in claves:
        valor = os.environ.get(k)
        if valor is not None and valor.strip() != "":
            return Path(valor.strip()).resolve()
    return defecto


# --- Servidor HTTP (Uvicorn / FastAPI) ---
BACKEND_HOST = _env_str(["BACKEND_HOST", "HOST"], "0.0.0.0")
BACKEND_PORT = _env_int(["BACKEND_PORT", "PORT"], 8000)

# --- Rutas del Sistema de Archivos (Persistencia Cero Base de Datos) ---
CONFIG_DIR = _ruta(["ERGOAI_CONFIG_DIR", "CONFIG_NORMATIVO_DIR", "CONFIG_DIR"], REPO_ROOT / "config_normativo")
WORKSPACE_DIR = _ruta(["ERGOAI_WORKSPACE_DIR", "WORKSPACE_DIR"], REPO_ROOT / "casos_jabil_workspace")
SEED_DIR = Path(__file__).resolve().parent / "seed"
MODELS_DIR = _ruta(["ERGOAI_MODELS_DIR", "VISION_MODELOS_DIR", "MODELS_DIR"], REPO_ROOT / "models")
# Plantilla oficial de Jabil (16-PE80-6500-00014-H). Es material de Jabil: no se versiona en git.
PLANTILLA_14H = _ruta(["ERGOAI_PLANTILLA_14H", "PLANTILLA_14H"],
                      REPO_ROOT / "plantillas" / "16-PE80-6500-00014-H.xlsm")

# --- Visión artificial (YOLOX + RTMPose WholeBody-133 sobre ONNX Runtime) ---
# "cpu" funciona en cualquier laptop; "cuda" requiere onnxruntime-gpu.
VISION_DEVICE = _env_str(["ERGOAI_DEVICE", "VISION_DISPOSITIVO", "DEVICE"], "cpu")
VISION_CONFIANZA_KEYPOINT = _env_float(["ERGOAI_VISION_CONFIANZA", "VISION_CONFIANZA_MIN"], 0.3)
VISION_CONFIANZA_RESPALDO = _env_float(["ERGOAI_VISION_CONFIANZA_RESPALDO", "VISION_CONFIANZA_RESPALDO"], 0.15)
VISION_MIN_PUNTOS_RESPALDO = _env_int(["ERGOAI_VISION_MIN_PUNTOS_RESPALDO", "VISION_MIN_PUNTOS_RESPALDO"], 5)
VISION_LADO_MAXIMO_PX = _env_int(["ERGOAI_VISION_MAX_PX", "VISION_LADO_MAXIMO_PX"], 1600)
VISION_STD_MINIMA_IMAGEN = _env_float(["ERGOAI_VISION_STD_MINIMA", "VISION_STD_MINIMA_IMAGEN"], 3.0)
VISION_DOWNLOAD_TIMEOUT_SEC = _env_int(["ERGOAI_VISION_DOWNLOAD_TIMEOUT_SEC", "VISION_DOWNLOAD_TIMEOUT_SEC"], 120)

YOLOX_MODEL_URL = _env_str(
    ["ERGOAI_YOLOX_URL", "YOLOX_MODEL_URL"],
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "yolox_tiny_8xb8-300e_humanart-6f3252f9.zip",
)
RTMPOSE_MODEL_URL = _env_str(
    ["ERGOAI_RTMPOSE_URL", "RTMPOSE_MODEL_URL"],
    "https://download.openmmlab.com/mmpose/v1/projects/rtmw/onnx_sdk/"
    "rtmw-dw-l-m_simcc-cocktail14_270e-256x192_20231122.zip",
)
MAX_FOTO_MB = _env_float(["ERGOAI_MAX_FOTO_MB", "MAX_FOTO_MB"], 15.0)

# Línea base para medir el impacto (criterio 8). Reemplazar por el tiempo medido en Jabil cuando se tenga.
MINUTOS_EVALUACION_MANUAL = float(os.environ.get("ERGOAI_MINUTOS_EVALUACION_MANUAL", "45"))
FUENTE_EVALUACION_MANUAL = os.environ.get(
    "ERGOAI_FUENTE_EVALUACION_MANUAL",
    "Estimación del equipo (Especificaciones_y_Arquitectura_ErgoAI.md): ~45 min por evaluación manual REBA + redacción",
)

# --- Seguridad y CORS ---
CORS_ORIGINS = [
    o.strip()
    for o in _env_str(
        ["ERGOAI_CORS_ORIGINS", "CORS_ORIGINS"],
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:80,http://localhost",
    ).split(",")
    if o.strip()
]

# --- Umbrales Biomecánicos REBA y Calidad de Imagen ---
TOLERANCIA_UMBRAL_GRADOS = _env_float(["ERGOAI_TOLERANCIA_GRADOS", "TOLERANCIA_UMBRAL_GRADOS"], 5.0)
CONFIANZA_MINIMA = _env_float(["ERGOAI_CONFIANZA_MINIMA", "CONFIANZA_MINIMA"], 0.4)
UMBRAL_ANCHO_TORSO_FRONTAL = _env_float(["ERGOAI_UMBRAL_TORSO_FRONTAL", "UMBRAL_ANCHO_TORSO_FRONTAL"], 0.35)
CALIDAD_JPEG = _env_int(["ERGOAI_CALIDAD_JPEG", "CALIDAD_JPEG"], 90)

# --- Identidades de Auditoría y Trazabilidad (Bitácora SHA-256) ---
USUARIO_POR_DEFECTO = _env_str(["ERGOAI_DEFAULT_USER", "USUARIO_POR_DEFECTO"], "Ing. Ergonomía")
USUARIO_SISTEMA = _env_str(["ERGOAI_SYSTEM_USER", "USUARIO_SISTEMA"], "sistema")

# --- Hiperparámetros BM25 del Motor RAG en Memoria ---
BM25_K1 = _env_float(["ERGOAI_BM25_K1", "BM25_K1"], 1.2)
BM25_B = _env_float(["ERGOAI_BM25_B", "BM25_B"], 0.75)

# --- Catálogo Normativo RAG y Orquestación LLM ---
JABIL_REGLAS_PATH = _ruta(["ERGOAI_JABIL_REGLAS_PATH", "JABIL_REGLAS_PATH"], CONFIG_DIR / "jabil_reglas.json")
LLM_PROVIDER = _env_str(["LLM_PROVIDER"], "OLLAMA")
MODEL_NAME = _env_str(["MODEL_NAME", "OLLAMA_MODEL"], "qwen2.5")
GEMINI_DEFAULT_MODEL = _env_str(["ERGOAI_GEMINI_MODEL", "GEMINI_DEFAULT_MODEL"], "gemini-2.5-pro")
OPENAI_DEFAULT_MODEL = _env_str(["ERGOAI_OPENAI_MODEL", "OPENAI_DEFAULT_MODEL"], "gpt-4o-mini")
OLLAMA_BASE_URL = _env_str(["OLLAMA_BASE_URL"], "http://localhost:11434")
LLM_TEMPERATURE = _env_float(["LLM_TEMPERATURE"], 0.1)
OLLAMA_TAG_TIMEOUT_SEC = _env_float(["OLLAMA_TAG_TIMEOUT_SEC"], 1.5)

# Credenciales Cloud (Opcionales si LLM_PROVIDER es GEMINI o OPENAI)
GEMINI_API_KEY = _env_str(["GEMINI_API_KEY"], "")
OPENAI_API_KEY = _env_str(["OPENAI_API_KEY"], "")
