"""Constantes normativas y límites biomecánicos del dominio ErgoAI.

Fuente Única de Verdad (SSOT) conforme a ARCHITECTURE.md (Sección 4.1):
  - Norma Oficial Mexicana NOM-036-1-STPS-2018 (Factores de riesgo ergonómico).
  - Estándar Corporativo Jabil Chihuahua 16-PE30-6500-00023 Rev O (Administración y Control de Layouts).
  - Método REBA Oficial (Hignett & McAtamney, 2000).
"""

from typing import Final


# =============================================================================
# 1. CONSTANTES NORMATIVAS JABIL (16-PE30-6500-00023 Rev O)
# =============================================================================

# Regla B1: Límite máximo de carga manual por persona (más restrictivo que NOM-036)
JABIL_MAX_SINGLE_PERSON_LOAD_KG: Final[float] = 14.0

# Regla B2: Tablas de contención para levantamiento en equipo
JABIL_TEAM_LIFT_2_PERSONS_GREEN_MAX_KG: Final[float] = 19.0
JABIL_TEAM_LIFT_2_PERSONS_ORANGE_MAX_KG: Final[float] = 28.0
JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG: Final[float] = 23.0
JABIL_TEAM_LIFT_3_PERSONS_ORANGE_MAX_KG: Final[float] = 42.0
JABIL_TEAM_LIFT_4_PERSONS_ORANGE_MAX_KG: Final[float] = 56.0

# Aliases
JABIL_TEAM_LIFT_2P_GREEN_MAX_KG: Final[float] = JABIL_TEAM_LIFT_2_PERSONS_GREEN_MAX_KG
JABIL_TEAM_LIFT_2P_ORANGE_MAX_KG: Final[float] = JABIL_TEAM_LIFT_2_PERSONS_ORANGE_MAX_KG
JABIL_TEAM_LIFT_3P_GREEN_MAX_KG: Final[float] = JABIL_TEAM_LIFT_3_PERSONS_GREEN_MAX_KG
JABIL_TEAM_LIFT_3P_ORANGE_MAX_KG: Final[float] = JABIL_TEAM_LIFT_3_PERSONS_ORANGE_MAX_KG

# Regla B3: Espacio libre para levantamiento
JABIL_MIN_LIFTING_FREE_SPACE_CM: Final[float] = 60.0

# Regla B4: Altura de toma máxima según origen
JABIL_MAX_PICKUP_HEIGHT_RACK_M: Final[float] = 1.70
JABIL_MAX_PICKUP_HEIGHT_CART_PALLET_M: Final[float] = 1.60

# Regla F1: Altura ergonómica de superficie de trabajo (CUU)
JABIL_WORKSTATION_SURFACE_HEIGHT_MIN_CM: Final[float] = 95.0
JABIL_WORKSTATION_SURFACE_HEIGHT_MAX_CM: Final[float] = 125.0

# Regla F2: Distancia mínima obligatoria entre operadores adyacentes
JABIL_MIN_INTER_OPERATOR_DISTANCE_CM: Final[float] = 80.0

# Regla F3: Holgura para piernas en sedestación
JABIL_MIN_LEGROOM_DEPTH_CM: Final[float] = 55.0
JABIL_MIN_LEGROOM_WIDTH_CM: Final[float] = 60.0

# Regla F4: Reposapiés en mesa
JABIL_FOOTREST_HEIGHT_MIN_CM: Final[float] = 21.0
JABIL_FOOTREST_HEIGHT_MAX_CM: Final[float] = 37.0
JABIL_FOOTREST_RECESS_CM: Final[float] = 15.0

# Regla F5: Espesor máximo de mesa
JABIL_MAX_TABLE_THICKNESS_CM: Final[float] = 10.0

# Regla F6: Espacio libre para pies en bipedestación
JABIL_MIN_STANDING_FOOT_DEPTH_CM: Final[float] = 15.0

# Regla G1-G7: Conveyors / Transportadores
JABIL_CONVEYOR_HEIGHT_MIN_M: Final[float] = 0.50
JABIL_CONVEYOR_HEIGHT_MAX_M: Final[float] = 1.40
JABIL_CONVEYOR_MAX_GRAVITY_LENGTH_M: Final[float] = 3.0
JABIL_CONVEYOR_MIN_WORK_ACCESS_CM: Final[float] = 80.0
JABIL_CONVEYOR_MIN_PALLET_SEPARATION_CM: Final[float] = 30.0

# Regla H2: Anchos de pasillos en Back-End (BE)
JABIL_AISLE_BE_MATERIAL_CART_MIN_M: Final[float] = 0.90
JABIL_AISLE_LOW_FLOW_SECONDARY_MIN_M: Final[float] = 1.20
JABIL_AISLE_LOW_FLOW_PRIMARY_MIN_M: Final[float] = 1.80
JABIL_AISLE_STAFF_ONLY_MIN_M: Final[float] = 1.50
JABIL_AISLE_SUPERVISION_NO_MATERIAL_MIN_M: Final[float] = 1.40
JABIL_AISLE_SUPERVISION_REAR_MIN_M: Final[float] = 0.50

# Regla H3: Separación mínima frente a tableros eléctricos
JABIL_MIN_ELECTRICAL_PANEL_CLEARANCE_CM: Final[float] = 90.0

# Regla H5: Área MRB (Material Review Board)
JABIL_MRB_CAGE_MIN_HEIGHT_M: Final[float] = 1.60


# =============================================================================
# 2. ZONAS DE ALCANCE DIGITALIZADAS (Jabil Sección 7.2.2.2)
# =============================================================================

REACH_ZONE_1_MAX_R_MM: Final[float] = 300.0
REACH_ZONE_1_MAX_ALPHA_DEG: Final[float] = 35.0
REACH_ZONE_1_CENTRAL_BOX_MM: Final[float] = 150.0

REACH_ZONE_2_MAX_R_MM: Final[float] = 400.0
REACH_ZONE_2_MAX_ALPHA_DEG: Final[float] = 35.0
REACH_ZONE_2_MAX_DX_MM: Final[float] = 550.0

REACH_ZONE_3_MAX_R_MM: Final[float] = 500.0
REACH_ZONE_3_MAX_DX_MM: Final[float] = 650.0
REACH_ZONE_3_MIN_ALPHA_DEG: Final[float] = 20.0

REACH_ZONE_4_MAX_DX_MM: Final[float] = 750.0

REACH_ZONE_LOWER_MAX_DEPTH_MM: Final[float] = 300.0
REACH_ZONE_LOWER_MID_DEPTH_MM: Final[float] = 150.0


# =============================================================================
# 3. UMBRALES BIOMECÁNICOS DEL MÉTODO REBA (Hignett & McAtamney 2000)
# =============================================================================

# Tronco
REBA_TRUNK_SCORE_1_MAX_DEG: Final[float] = 5.0
REBA_TRUNK_SCORE_2_MAX_DEG: Final[float] = 20.0
REBA_TRUNK_SCORE_3_MAX_DEG: Final[float] = 60.0

# Cuello
REBA_NECK_SCORE_1_MAX_DEG: Final[float] = 20.0

# Piernas / Flexión de Rodilla
REBA_KNEE_SCORE_ADJ_1_MIN_DEG: Final[float] = 30.0
REBA_KNEE_SCORE_ADJ_2_MIN_DEG: Final[float] = 60.0

# Brazo / Hombro
REBA_ARM_SCORE_1_MAX_DEG: Final[float] = 20.0
REBA_ARM_SCORE_2_MAX_DEG: Final[float] = 45.0
REBA_ARM_SCORE_3_MAX_DEG: Final[float] = 90.0
REBA_ARM_ABDUCTION_THRESHOLD_DEG: Final[float] = 20.0

# Antebrazo / Codo (Rango Óptimo 60° a 100°)
REBA_ELBOW_OPTIMAL_MIN_DEG: Final[float] = 60.0
REBA_ELBOW_OPTIMAL_MAX_DEG: Final[float] = 100.0

# Muñeca
REBA_WRIST_SCORE_1_MAX_DEG: Final[float] = 15.0
REBA_WRIST_DEVIATION_ANGLE_TOLERANCE_DEG: Final[float] = 15.0

# Puntuación por Carga / Fuerza
REBA_LOAD_SCORE_0_MAX_KG: Final[float] = 5.0
REBA_LOAD_SCORE_1_MAX_KG: Final[float] = 10.0


# =============================================================================
# 4. REFERENCIAS ANTROPOMÉTRICAS POR DEFECTO PARA CALIBRACIÓN DINÁMICA
# =============================================================================

DEFAULT_OPERATOR_HEIGHT_MM: Final[float] = 1700.0
DEFAULT_BIACROMIAL_SHOULDER_WIDTH_MM: Final[float] = 400.0
