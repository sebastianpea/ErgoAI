"""Tablas canónicas del Método REBA (Hignett & McAtamney, 2000).

Fuente Única de Verdad (SSOT) para las matrices de puntuación A, B y C.
"""

from typing import Final

# TABLA A: Tronco (filas 1 a 5) x Cuello (columnas 1 a 3) x Piernas (subcolumnas 1 a 4)
# Indexado como: TABLE_A[trunk - 1][neck - 1][legs - 1]
TABLE_A: Final[list[list[list[int]]]] = [
    # Tronco 1 (Erguido 0-5°)
    [
        [1, 2, 3, 4],  # Cuello 1
        [2, 3, 4, 5],  # Cuello 2
        [2, 4, 5, 6],  # Cuello 3
    ],
    # Tronco 2 (0-20° flexión o extensión)
    [
        [2, 3, 4, 5],  # Cuello 1
        [3, 4, 5, 6],  # Cuello 2
        [4, 5, 6, 7],  # Cuello 3
    ],
    # Tronco 3 (20-60° flexión o >20° extensión)
    [
        [2, 4, 5, 6],  # Cuello 1
        [4, 5, 6, 7],  # Cuello 2
        [5, 6, 7, 8],  # Cuello 3
    ],
    # Tronco 4 (>60° flexión)
    [
        [3, 5, 6, 7],  # Cuello 1
        [5, 6, 7, 8],  # Cuello 2
        [6, 7, 8, 9],  # Cuello 3
    ],
    # Tronco 5 (>60° flexión extrema o torsión crítica)
    [
        [4, 6, 7, 8],  # Cuello 1
        [6, 7, 8, 9],  # Cuello 2
        [7, 8, 9, 9],  # Cuello 3
    ],
]

# TABLA B: Brazo (filas 1 a 6) x Antebrazo (columnas 1 a 2) x Muñeca (subcolumnas 1 a 3)
# Indexado como: TABLE_B[upper_arm - 1][lower_arm - 1][wrist - 1]
TABLE_B: Final[list[list[list[int]]]] = [
    # Brazo 1 (20° extensión a 20° flexión)
    [
        [1, 2, 2],  # Antebrazo 1 (60-100°)
        [1, 2, 3],  # Antebrazo 2 (<60° o >100°)
    ],
    # Brazo 2 (>20° extensión o 20-45° flexión)
    [
        [1, 2, 3],  # Antebrazo 1
        [2, 3, 4],  # Antebrazo 2
    ],
    # Brazo 3 (45-90° flexión)
    [
        [3, 4, 5],  # Antebrazo 1
        [4, 5, 5],  # Antebrazo 2
    ],
    # Brazo 4 (>90° flexión)
    [
        [4, 5, 5],  # Antebrazo 1
        [5, 6, 7],  # Antebrazo 2
    ],
    # Brazo 5 (elevado extremo)
    [
        [6, 7, 8],  # Antebrazo 1
        [7, 8, 8],  # Antebrazo 2
    ],
    # Brazo 6 (hombro hiper-abducido)
    [
        [7, 8, 8],  # Antebrazo 1
        [8, 9, 9],  # Antebrazo 2
    ],
]

# TABLA C: Score A (filas 1 a 12) x Score B (columnas 1 a 12) -> Score C (1 a 12)
# Indexado como: TABLE_C[score_a - 1][score_b - 1]
TABLE_C: Final[list[list[int]]] = [
    [1, 1, 1, 2, 3, 3, 4, 5, 6, 7, 7, 7],       # Score A = 1
    [1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8],       # Score A = 2
    [2, 3, 3, 3, 4, 5, 6, 7, 7, 8, 8, 8],       # Score A = 3
    [3, 4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9],       # Score A = 4
    [4, 4, 4, 5, 6, 7, 8, 8, 9, 9, 9, 9],       # Score A = 5
    [6, 6, 6, 7, 8, 8, 9, 9, 10, 10, 10, 10],   # Score A = 6
    [7, 7, 7, 8, 9, 9, 9, 10, 10, 11, 11, 11],   # Score A = 7
    [8, 8, 8, 9, 10, 10, 10, 10, 10, 11, 11, 11], # Score A = 8
    [9, 9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12], # Score A = 9
    [10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12, 12], # Score A = 10
    [11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12], # Score A = 11
    [12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12], # Score A = 12
]


def lookup_table_a(trunk: int, neck: int, legs: int) -> int:
    """Consulta segura en Tabla A con acotamiento de límites."""
    t = max(1, min(5, trunk)) - 1
    n = max(1, min(3, neck)) - 1
    l = max(1, min(4, legs)) - 1
    return TABLE_A[t][n][l]


def lookup_table_b(upper_arm: int, lower_arm: int, wrist: int) -> int:
    """Consulta segura en Tabla B con acotamiento de límites."""
    ua = max(1, min(6, upper_arm)) - 1
    la = max(1, min(2, lower_arm)) - 1
    w = max(1, min(3, wrist)) - 1
    return TABLE_B[ua][la][w]


def lookup_table_c(score_a: int, score_b: int) -> int:
    """Consulta segura en Tabla C con acotamiento de límites [1, 12]."""
    sa = max(1, min(12, score_a)) - 1
    sb = max(1, min(12, score_b)) - 1
    return TABLE_C[sa][sb]

