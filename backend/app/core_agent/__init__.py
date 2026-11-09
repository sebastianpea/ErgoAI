"""
Módulo de Agente Inteligente y RAG Estático en Memoria (Track 4 Jabil X-RAIC 2026).
Garantiza cero dependencias de bases de datos vectoriales y ejecución 100% offline.
"""

from backend.app.core_agent.ergo_agent import ErgoAgent, ErgoAIAgent
from backend.app.core_agent.in_memory_rag import (
    ClausulaNormativa,
    InMemoryRAG,
    ResultadoBusquedaRAG,
)
from backend.app.core_agent.knowledge_retriever import (
    InMemoryNormativeRetriever,
    KnowledgeRetriever,
)
from backend.app.core_agent.llm_factory import LLMFactory
from backend.app.core_agent.models import RecomendacionErgonomica

__all__ = [
    "ClausulaNormativa",
    "ErgoAIAgent",
    "ErgoAgent",
    "InMemoryNormativeRetriever",
    "InMemoryRAG",
    "KnowledgeRetriever",
    "LLMFactory",
    "RecomendacionErgonomica",
    "ResultadoBusquedaRAG",
]
