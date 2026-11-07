"""Totalización NOM-036-1-STPS-2018: suma de factores y banda de color según el catálogo."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def total_factores(valores: Iterable[int]) -> int:
    return sum(valores)


def color_total(total: int, tablas: Mapping[str, Any]) -> str:
    for banda in tablas["total_score_bands"]:
        if banda["min"] <= total <= banda["max"]:
            return banda["color"]
    raise ValueError(f"Total NOM-036 fuera de las bandas configuradas: {total}")
