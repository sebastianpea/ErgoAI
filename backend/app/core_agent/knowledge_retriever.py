# backend/app/core_agent/knowledge_retriever.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.settings import JABIL_REGLAS_PATH


class InMemoryNormativeRetriever:
    def __init__(self, json_filepath: str | Path | list[dict[str, Any]] = JABIL_REGLAS_PATH):
        # Carga el archivo una sola vez en la memoria RAM (Cero Bases de Datos) o recibe la lista ya cargada
        if isinstance(json_filepath, list):
            self.knowledge_base: list[dict[str, Any]] = json_filepath
        else:
            with open(json_filepath, "r", encoding="utf-8") as file:
                self.knowledge_base = json.load(file)

    def search(self, keywords: list[str], tipo_prueba: str | None = None) -> str:
        """
        Buscador léxico en RAM con Ceguera Inducida (Filtro de Contexto por tipo_prueba):
        1. Si se especifica `tipo_prueba` (ej. 'Levantamiento (1)', 'Transporte (2)',
           'con auxiliar (5)'), filtra primero el corpus en memoria para aislar
           EXCLUSIVAMENTE los fragmentos de esa prueba. Si el modelo no lee reglas de
           otras pruebas (ej. mantenimiento de llantas durante un levantamiento), no las puede alucinar.
        2. Respeta las restricciones declarativas `requiere_alguno_de` del catálogo normativo
           para no inyectar reglas de exceso de carga o rediseño de mesa cuando no aplican.
        3. Sobre el subconjunto filtrado, recupera los fragmentos cuyos `tags` coinciden con `keywords`.
        """
        candidatos = self.knowledge_base
        if tipo_prueba:
            tp_norm = tipo_prueba.strip().lower()
            filtrados = [
                item
                for item in self.knowledge_base
                if tp_norm
                in [
                    t.lower()
                    for t in (
                        item.get("tipo_prueba", [])
                        if isinstance(item.get("tipo_prueba"), list)
                        else [str(item.get("tipo_prueba", ""))]
                    )
                ]
            ]
            if filtrados:
                candidatos = filtrados

        kw_norm = {kw.strip().lower() for kw in keywords}
        fragmentos_encontrados: list[str] = []

        for item in candidatos:
            tags_item = [tag.lower() for tag in item.get("tags", [])]
            requeridos = [req.lower() for req in item.get("requiere_alguno_de", [])]
            # Ceguera Inducida declarativa desde el catálogo JSON: si la regla exige ciertas condiciones y no están en keywords, se omite
            if requeridos and not (kw_norm & set(requeridos)):
                continue
            if kw_norm & set(tags_item):
                fragmentos_encontrados.append(item["texto_normativo"])

        # Si hay filtro por tipo_prueba pero ninguna keyword puntual coincidió, devolver fragmentos generales sin restricciones incumplidas
        if not fragmentos_encontrados and tipo_prueba and candidatos is not self.knowledge_base:
            fragmentos_encontrados = [
                item["texto_normativo"]
                for item in candidatos
                if not item.get("requiere_alguno_de")
                or (kw_norm & {req.lower() for req in item.get("requiere_alguno_de", [])})
            ][:2]

        if not fragmentos_encontrados:
            return "No se encontró normativa específica para esta anomalía. Mantener condiciones ergonómicas conforme a NOM-036 y estándar Jabil."

        return "\n\n".join(fragmentos_encontrados)


# Alias de compatibilidad
KnowledgeRetriever = InMemoryNormativeRetriever
