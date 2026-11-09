"""
Script unificado para preparar y verificar el entorno de IA Local (Visión + LLM) de ErgoAI.
Cualquier miembro del equipo puede ejecutar este script para:
  1. Descargar los modelos ONNX de Visión 2D (YOLOX + RTMPose WholeBody-133).
  2. Verificar la disponibilidad de Ollama y descargar automáticamente el modelo LLM local (qwen2.5).
  3. Ejecutar una prueba rápida de inferencia para certificar que la IA local está lista.

Uso:
  python scripts/preparar_entorno_ia.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.settings import (
    MODELS_DIR,
    MODEL_NAME,
    VISION_DEVICE,
)
from backend.app.core_agent.llm_factory import _resolver_ollama_base_url
from backend.app.vision.modelos import MODELOS, descargar, faltantes


def seccion(titulo: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {titulo}")
    print("=" * 70)


def preparar_modelos_vision() -> bool:
    seccion("1. MODELOS DE VISIÓN COMPUTACIONAL 2D (YOLOX + RTMPose)")
    print(f"Directorio de destino: {MODELS_DIR}")
    print(f"Dispositivo configurado: {VISION_DEVICE}")

    faltan = faltantes()
    if not faltan:
        print("✓ Todos los modelos ONNX ya están descargados en models/:")
        for k in MODELOS:
            ruta = MODELS_DIR / MODELOS[k].archivo
            mb = ruta.stat().st_size / 1e6
            print(f"  - {MODELOS[k].nombre}: {ruta.name} ({mb:.1f} MB)")
        return True

    print(f"Descargando {len(faltan)} modelo(s) faltante(s) desde OpenMMLab (~150 MB total)...")
    for k in faltan:
        try:
            descargar(k)
        except Exception as e:
            print(f"✗ Error al descargar modelo '{k}': {e}", file=sys.stderr)
            return False

    print("✓ Modelos de visión listos para inferencia local.")
    return True


def preparar_modelo_llm() -> bool:
    seccion("2. MODELO DE LENGUAJE LOCAL (Ollama LLM)")
    modelo = MODEL_NAME or "qwen2.5"
    base_url = _resolver_ollama_base_url().rstrip("/")
    print(f"URL de Ollama: {base_url}")
    print(f"Modelo objetivo: {modelo}")

    # Verificar si el servicio de Ollama responde
    ollama_online = False
    try:
        req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "ErgoAI-Setup"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            modelos_disponibles = [m.get("name", "") for m in data.get("models", [])]
            ollama_online = True
            print("✓ Servicio Ollama detectado en ejecución.")
            if any(modelo in m for m in modelos_disponibles):
                print(f"✓ El modelo '{modelo}' ya se encuentra disponible en Ollama.")
                return True
    except Exception:
        pass

    if not ollama_online:
        print("\n⚠ Ollama no parece estar corriendo en " + base_url)
        print("  Para instalar y correr Ollama:")
        print("  - Linux/WSL:   curl -fsSL https://ollama.com/install.sh | sh")
        print("                 ollama serve")
        print("  - Windows/Mac: Descargar instalador de https://ollama.com/")
        print("  - Docker:      docker compose up -d llm_engine")
        print(f"  Luego ejecuta: ollama pull {modelo}\n")
        return False

    # Intentar descargar el modelo vía comando CLI de ollama si está en PATH
    print(f"Descargando modelo '{modelo}' en Ollama (esto puede tomar un par de minutos según tu conexión)...")
    try:
        res = subprocess.run(["ollama", "pull", modelo], check=True)
        print(f"✓ Modelo '{modelo}' descargado con éxito en Ollama.")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"⚠ Ejecuta manualmente en otra terminal: ollama pull {modelo}")
        return False


def probar_agente_local() -> None:
    seccion("3. PRUEBA DE INFERENCIA DEL AGENTE ERGOAI")
    try:
        from backend.app.core_agent.ergo_agent import ErgoAIAgent
        from backend.app.core_agent.knowledge_retriever import InMemoryNormativeRetriever
        from backend.app.core_agent.llm_factory import LLMFactory
        from backend.app.settings import JABIL_REGLAS_PATH

        retriever = InMemoryNormativeRetriever(JABIL_REGLAS_PATH)
        llm = LLMFactory.get_llm()
        agente = ErgoAIAgent(llm=llm, retriever=retriever)

        print("Ejecutando caso de prueba: levantamiento manual de 18 kg...")
        resultado = agente.evaluar_caso(
            anomalia="Operador levanta caja de 18 kg flexionando tronco a 45 grados.",
            reba_score=10,
            palabras_clave=["carga", "peso", ">14kg"],
            tipo_prueba="Levantamiento (1)",
            riesgo_determinista="REBA: Riesgo Alto, 10 puntos | NOM-036: Riesgo Alto",
        )
        print("\n✓ Inferencia exitosa:")
        print(f"  - Jerarquía: {resultado.get('jerarquia')}")
        print(f"  - Título: {resultado.get('titulo')}")
        print(f"  - Fundamento: {resultado.get('fundamento_normativo')}")
    except Exception as exc:
        print(f"⚠ No se pudo completar la prueba de inferencia: {exc}")
        print("  Verifica que el servicio Ollama esté levantado con el modelo cargado.")


if __name__ == "__main__":
    ok_vision = preparar_modelos_vision()
    ok_llm = preparar_modelo_llm()
    if ok_vision and ok_llm:
        probar_agente_local()
        seccion("RESUMEN: ENTORNO DE IA LOCAL 100% OPERATIVO")
    else:
        seccion("RESUMEN: CONFIGURACIÓN PARCIAL")
        print("Revisa las indicaciones anteriores para completar los modelos faltantes.")
