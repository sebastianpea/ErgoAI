# backend/app/core_agent/models.py
from __future__ import annotations

from pydantic import BaseModel, Field


class RecomendacionErgonomica(BaseModel):
    jerarquia: str = Field(
        description="Clasificación estricta. Valores permitidos: 'INGENIERIA', 'TECNOLOGICO' o 'ADMINISTRATIVO'"
    )
    titulo: str = Field(
        description="Título corto de la acción correctiva (máximo 7 palabras)"
    )
    descripcion_tecnica: str = Field(
        description="Instrucción detallada de qué cambiar físicamente en la estación (alturas, distancias, equipos)"
    )
    fundamento_normativo: str = Field(
        description="Cita literal de la NOM-036 o estándar Jabil 16-PE30-6500-00023 que lo justifica"
    )
