# backend/app/core_agent/llm_factory.py
from __future__ import annotations

import json
import logging
import os
import socket
import urllib.request
from urllib.parse import urlparse

from langchain_ollama import ChatOllama
from backend.app.settings import (
    GEMINI_DEFAULT_MODEL,
    LLM_PROVIDER as DEFAULT_LLM_PROVIDER,
    LLM_TEMPERATURE,
    MODEL_NAME as DEFAULT_MODEL_NAME,
    OLLAMA_BASE_URL as DEFAULT_OLLAMA_BASE_URL,
    OLLAMA_TAG_TIMEOUT_SEC,
    OPENAI_DEFAULT_MODEL,
)

log = logging.getLogger("ergoai.llm_factory")


def _resolver_ollama_base_url() -> str:
    """
    Resuelve inteligentemente la URL base de Ollama:
    - Si se configuró 'llm_engine' pero estamos ejecutando fuera del contenedor (host),
      hace fallback automático a 'http://localhost:11434'.
    - Si estamos dentro de la red Docker y 'llm_engine' resuelve, lo utiliza.
    """
    url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip()
    parsed = urlparse(url)
    hostname = parsed.hostname or "localhost"
    port = parsed.port or 11434

    if hostname not in ("localhost", "127.0.0.1"):
        try:
            socket.gethostbyname(hostname)
        except socket.gaierror:
            # El hostname de Docker no resuelve en la máquina local; redirigir a localhost
            return f"{parsed.scheme or 'http'}://localhost:{port}"

    return url


def _resolver_modelo_ollama(base_url: str, modelo_deseado: str) -> str:
    """
    Verifica los modelos disponibles en la instancia de Ollama:
    Si el modelo solicitado no está presente pero hay otros descargados,
    selecciona el mejor candidato disponible para evitar caídas por modelo faltante.
    """
    timeout_sec = float(os.getenv("OLLAMA_TAG_TIMEOUT_SEC", str(OLLAMA_TAG_TIMEOUT_SEC)))
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/tags",
            headers={"User-Agent": "ErgoAI"},
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            nombres = [m.get("name", "") for m in data.get("models", [])]

            # Coincidencia exacta o por prefijo
            for n in nombres:
                if modelo_deseado == n or n.startswith(f"{modelo_deseado}:"):
                    return n

            # Coincidencia parcial (ej. 'qwen2.5' en 'qwen2.5-coder:7b')
            for n in nombres:
                if modelo_deseado.split(":")[0] in n:
                    return n

            # Fallback al primer modelo disponible en Ollama si existe
            if nombres:
                return nombres[0]
    except Exception as exc:
        log.debug("No se pudo consultar /api/tags en %s (%s); se usará modelo '%s'", base_url, exc, modelo_deseado)

    return modelo_deseado


class LLMFactory:
    @staticmethod
    def get_llm():
        provider = os.getenv("LLM_PROVIDER", DEFAULT_LLM_PROVIDER).upper()
        temperature = float(os.getenv("LLM_TEMPERATURE", str(LLM_TEMPERATURE)))

        if provider == "OLLAMA":
            base_url = _resolver_ollama_base_url()
            modelo_solicitado = os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
            modelo = _resolver_modelo_ollama(base_url, modelo_solicitado)

            return ChatOllama(
                base_url=base_url,
                model=modelo,
                temperature=temperature,
            )

        elif provider == "GEMINI":
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

            return ChatGoogleGenerativeAI(
                model=os.getenv("MODEL_NAME", GEMINI_DEFAULT_MODEL),
                temperature=temperature,
                google_api_key=api_key or None,
            )

        elif provider == "OPENAI":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY")

            return ChatOpenAI(
                model=os.getenv("MODEL_NAME", OPENAI_DEFAULT_MODEL),
                temperature=temperature,
                api_key=api_key or None,
            )

        else:
            raise ValueError(f"Proveedor LLM '{provider}' no soportado.")

    @staticmethod
    def create():
        """Alias de compatibilidad para `get_llm()`."""
        return LLMFactory.get_llm()
