"""Totalización NOM-036-1-STPS-2018: validación de factores, suma y banda de color según el catálogo."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def total_factores(valores: Iterable[int]) -> int:
    return sum(valores)


def color_total(total: int, tablas: Mapping[str, Any]) -> str:
    for banda in tablas["total_score_bands"]:
        if banda["min"] <= total <= banda["max"]:
            return banda["color"]
    raise ValueError(f"Total NOM-036 fuera de las bandas configuradas: {total}")


def validar_captura(metodo: str, factores: Sequence[Any], tablas: Mapping[str, Any]) -> None:
    """
    Comprueba que los factores capturados correspondan al método de la hoja oficial.
    En los métodos con tabla (levantamiento, transporte) el valor lo fija el color elegido;
    en los de captura libre (empuje/arrastre) se acepta el valor que el especialista lee de la hoja.
    """
    m = tablas["metodos"].get(metodo)
    if m is None:
        raise ValueError(f"Método NOM-036 desconocido: {metodo}")
    catalogo = {f["codigo"]: f for f in m["factores"]}
    codigos = [f.codigo for f in factores]
    if len(codigos) != len(set(codigos)):
        raise ValueError("Hay factores repetidos")
    faltan = set(catalogo) - set(codigos)
    sobran = set(codigos) - set(catalogo)
    if faltan or sobran:
        partes = []
        if faltan:
            partes.append(f"faltan {', '.join(sorted(faltan))}")
        if sobran:
            partes.append(f"no pertenecen a la hoja {m['hoja']}: {', '.join(sorted(sobran))}")
        raise ValueError("Factores NOM-036 incompletos: " + "; ".join(partes))
    if m.get("captura_libre"):
        return
    for f in factores:
        opciones = catalogo[f.codigo]["opciones"]
        if f.color not in opciones:
            raise ValueError(f"{catalogo[f.codigo]['etiqueta']}: el color {f.color} no existe en la hoja")
        if f.valor != opciones[f.color]:
            raise ValueError(f"{catalogo[f.codigo]['etiqueta']}: el color {f.color} vale {opciones[f.color]}, no {f.valor}")
