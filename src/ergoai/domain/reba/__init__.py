"""Módulo para el Método de Evaluación Ergonómica REBA."""

from ergoai.domain.reba.tables import (
    TABLE_A,
    TABLE_B,
    TABLE_C,
    lookup_table_a,
    lookup_table_b,
    lookup_table_c,
)
from ergoai.domain.reba.evaluator import REBAEvaluator

__all__ = [
    "TABLE_A",
    "TABLE_B",
    "TABLE_C",
    "lookup_table_a",
    "lookup_table_b",
    "lookup_table_c",
    "REBAEvaluator",
]

