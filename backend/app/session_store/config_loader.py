"""
Cargador de Catálogos Normativos Estáticos (Read-Only SSOT).
Carga y valida los estándares ergonómicos de Jabil y NOM-036 desde archivos JSON locales.
Restricción: Cero consultas a base de datos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.settings import CONFIG_DIR


class ConfigLoadError(Exception):
    """Excepción lanzada cuando un catálogo normativo está ausente o malformado."""
    pass


class NormativeConfigLoader:
    """
    Cargador en memoria de configuraciones normativas inmutables.
    Implementa caché en memoria para garantizar lecturas en microsegundos.
    """

    DEFAULT_CONFIG_DIR = CONFIG_DIR

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir or self.DEFAULT_CONFIG_DIR)
        self._jabil_standards: Optional[Dict[str, Any]] = None
        self._jabil_reglas: Optional[list[Dict[str, Any]]] = None
        self._reba_tables: Optional[Dict[str, Any]] = None
        self._nom036_tables: Optional[Dict[str, Any]] = None
        self._nom036_kb: Optional[str] = None

    def _load_json_file(self, filename: str) -> Any:
        file_path = self.config_dir / filename
        if not file_path.exists():
            raise ConfigLoadError(f"Catálogo normativo no encontrado: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigLoadError(f"Error de sintaxis en JSON {file_path}: {e}") from e
        except OSError as e:
            raise ConfigLoadError(f"Error de lectura en {file_path}: {e}") from e

    def get_jabil_standards(self, reload: bool = False) -> Dict[str, Any]:
        """Obtiene las especificaciones de planta Chihuahua (16-PE30-6500-00023)."""
        if self._jabil_standards is None or reload:
            data = self._load_json_file("jabil_standards_00023.json")
            # Validación rápida de esquema mínimo
            required_sections = ["load_limits", "workstation_geometry", "reach_zones_mm", "chair_law_stps"]
            for section in required_sections:
                if section not in data:
                    raise ConfigLoadError(f"Estructura inválida en jabil_standards: falta sección '{section}'")
            self._jabil_standards = data
        return self._jabil_standards

    def get_reba_tables(self, reload: bool = False) -> Dict[str, Any]:
        """Obtiene las tablas de lookup y rangos angulares de REBA."""
        if self._reba_tables is None or reload:
            data = self._load_json_file("reba_lookup_tables.json")
            for section in ("risk_levels", "table_a_matrix", "table_b_matrix", "table_c_matrix", "load_force_kg"):
                if section not in data:
                    raise ConfigLoadError(f"Estructura inválida en reba_lookup_tables: falta sección '{section}'")
            self._reba_tables = data
        return self._reba_tables

    def get_nom036_tables(self, reload: bool = False) -> Dict[str, Any]:
        """Obtiene las tablas de factores de la NOM-036-1 y mapeo de 16-PE80-6500-00014-H."""
        if self._nom036_tables is None or reload:
            data = self._load_json_file("nom036_mac_rapp_tables.json")
            for section in ("risk_bands", "sheets_mapping", "total_score_bands"):
                if section not in data:
                    raise ConfigLoadError(f"Estructura inválida en nom036_mac_rapp_tables: falta sección '{section}'")
            self._nom036_tables = data
        return self._nom036_tables

    def get_nom036_kb(self, reload: bool = False) -> str:
        """Obtiene el texto normativo de la base de conocimiento NOM-036-1-STPS-2018."""
        if self._nom036_kb is None or reload:
            kb_path = self.config_dir / "nom036_knowledge_base.md"
            if not kb_path.exists():
                raise ConfigLoadError(f"Base de conocimiento no encontrada: {kb_path}")
            try:
                self._nom036_kb = kb_path.read_text(encoding="utf-8")
            except OSError as e:
                raise ConfigLoadError(f"Error al leer base de conocimiento {kb_path}: {e}") from e
        return self._nom036_kb

    def get_jabil_reglas(self, reload: bool = False) -> list[Dict[str, Any]]:
        """Obtiene el catálogo de reglas RAG con aislamiento por tipo_prueba (jabil_reglas.json)."""
        if self._jabil_reglas is None or reload:
            data = self._load_json_file("jabil_reglas.json")
            if not isinstance(data, list) or not data:
                raise ConfigLoadError("Estructura inválida en jabil_reglas.json: se esperaba una lista no vacía")
            self._jabil_reglas = data
        return self._jabil_reglas

    def validate_all(self) -> None:
        """Valida que todos los catálogos existan y cumplan sus contratos en tiempo de arranque."""
        self.get_jabil_standards(reload=True)
        self.get_jabil_reglas(reload=True)
        self.get_reba_tables(reload=True)
        self.get_nom036_tables(reload=True)
        self.get_nom036_kb(reload=True)


# Instancia compartida por defecto (Singleton de lectura)
default_config_loader = NormativeConfigLoader()
