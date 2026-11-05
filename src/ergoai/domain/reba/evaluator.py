"""Motor de cálculo y auditoría postural según el Método REBA (R1 a R4)."""

from typing import Optional
from ergoai.domain.models.angles import BiomechanicalAngles
from ergoai.domain.models.reba import (
    REBARiskLevel,
    REBAGroupAScore,
    REBAGroupBScore,
    REBAActivityScore,
    REBAAssessment,
)
from ergoai.domain.reba.tables import (
    lookup_table_a,
    lookup_table_b,
    lookup_table_c,
)
from ergoai.domain.constants import (
    REBA_TRUNK_SCORE_1_MAX_DEG,
    REBA_TRUNK_SCORE_2_MAX_DEG,
    REBA_TRUNK_SCORE_3_MAX_DEG,
    REBA_NECK_SCORE_1_MAX_DEG,
    REBA_KNEE_SCORE_ADJ_1_MIN_DEG,
    REBA_KNEE_SCORE_ADJ_2_MIN_DEG,
    REBA_ARM_SCORE_1_MAX_DEG,
    REBA_ARM_SCORE_2_MAX_DEG,
    REBA_ARM_SCORE_3_MAX_DEG,
    REBA_ELBOW_OPTIMAL_MIN_DEG,
    REBA_ELBOW_OPTIMAL_MAX_DEG,
    REBA_WRIST_SCORE_1_MAX_DEG,
    REBA_LOAD_SCORE_0_MAX_KG,
    REBA_LOAD_SCORE_1_MAX_KG,
)


class REBAEvaluator:
    """Implementa el método REBA puro e independiente de cualquier infraestructura."""

    @classmethod
    def calculate_group_a(
        cls,
        angles: BiomechanicalAngles,
        load_kg: float = 0.0,
        is_shock_load: bool = False,
    ) -> REBAGroupAScore:
        """R1: Evaluación del Grupo A (Tronco, Cuello, Piernas y Carga)."""
        # --- 1. Tronco ---
        t_angle = angles.trunk_angle
        if t_angle <= REBA_TRUNK_SCORE_1_MAX_DEG and not angles.trunk_is_extension:
            trunk_base = 1
        elif (REBA_TRUNK_SCORE_1_MAX_DEG < t_angle <= REBA_TRUNK_SCORE_2_MAX_DEG and not angles.trunk_is_extension) or (angles.trunk_is_extension and t_angle <= REBA_TRUNK_SCORE_2_MAX_DEG):
            trunk_base = 2
        elif (REBA_TRUNK_SCORE_2_MAX_DEG < t_angle <= REBA_TRUNK_SCORE_3_MAX_DEG and not angles.trunk_is_extension) or (angles.trunk_is_extension and t_angle > REBA_TRUNK_SCORE_2_MAX_DEG):
            trunk_base = 3
        else:
            trunk_base = 4

        # Ajustes de tronco (+1 si torsión o flexión lateral)
        trunk_adj = 0
        if angles.trunk_twisted or angles.trunk_side_bending:
            trunk_adj += 1
        trunk_score = min(5, max(1, trunk_base + trunk_adj))

        # --- 2. Cuello ---
        n_angle = angles.neck_angle
        if n_angle <= REBA_NECK_SCORE_1_MAX_DEG and not angles.neck_is_extension:
            neck_base = 1
        else:
            neck_base = 2

        # Ajustes de cuello (+1 si torsión o inclinación lateral)
        neck_adj = 0
        if angles.neck_twisted or angles.neck_side_bending:
            neck_adj += 1
        neck_score = min(3, max(1, neck_base + neck_adj))

        # --- 3. Piernas ---
        if angles.leg_unilateral_or_unstable:
            legs_base = 2
        else:
            legs_base = 1

        # Ajuste por flexión de rodillas
        k_angle = angles.leg_knee_angle
        legs_adj = 0
        if REBA_KNEE_SCORE_ADJ_1_MIN_DEG <= k_angle <= REBA_KNEE_SCORE_ADJ_2_MIN_DEG:
            legs_adj += 1
        elif k_angle > REBA_KNEE_SCORE_ADJ_2_MIN_DEG:
            legs_adj += 2
        legs_score = min(4, max(1, legs_base + legs_adj))

        # Cruce en Tabla A
        table_a_score = lookup_table_a(trunk_score, neck_score, legs_score)

        # Ajuste por carga/fuerza
        if load_kg < REBA_LOAD_SCORE_0_MAX_KG:
            load_score = 0
        elif REBA_LOAD_SCORE_0_MAX_KG <= load_kg <= REBA_LOAD_SCORE_1_MAX_KG:
            load_score = 1
        else:
            load_score = 2
        if is_shock_load:
            load_score += 1

        score_a = min(12, max(1, table_a_score + load_score))

        return REBAGroupAScore(
            trunk_raw_score=trunk_score,
            neck_raw_score=neck_score,
            legs_raw_score=legs_score,
            table_a_score=table_a_score,
            load_score=load_score,
            score_a=score_a,
        )

    @classmethod
    def calculate_group_b(
        cls,
        angles: BiomechanicalAngles,
        coupling_score: int = 0,
    ) -> REBAGroupBScore:
        """R2: Evaluación del Grupo B (Brazo, Antebrazo, Muñeca y Agarre)."""
        # --- 1. Brazos (Hombro) ---
        arm_angle = angles.upper_arm_angle
        if arm_angle <= REBA_ARM_SCORE_1_MAX_DEG and not angles.upper_arm_is_extension:
            arm_base = 1
        elif (angles.upper_arm_is_extension and arm_angle > REBA_ARM_SCORE_1_MAX_DEG) or (REBA_ARM_SCORE_1_MAX_DEG < arm_angle <= REBA_ARM_SCORE_2_MAX_DEG):
            arm_base = 2
        elif REBA_ARM_SCORE_2_MAX_DEG < arm_angle <= REBA_ARM_SCORE_3_MAX_DEG:
            arm_base = 3
        else:
            arm_base = 4

        # Ajustes de brazo
        arm_adj = 0
        if angles.upper_arm_abducted:
            arm_adj += 1
        if angles.shoulder_elevated:
            arm_adj += 1
        if angles.arm_supported_or_gravity_assisted:
            arm_adj -= 1
        upper_arm_score = min(6, max(1, arm_base + arm_adj))

        # --- 2. Antebrazo (Codo) ---
        elbow_angle = angles.lower_arm_angle
        if REBA_ELBOW_OPTIMAL_MIN_DEG <= elbow_angle <= REBA_ELBOW_OPTIMAL_MAX_DEG:
            lower_arm_score = 1
        else:
            lower_arm_score = 2

        # --- 3. Muñeca ---
        wrist_angle = angles.wrist_angle
        if wrist_angle <= REBA_WRIST_SCORE_1_MAX_DEG:
            wrist_base = 1
        else:
            wrist_base = 2

        wrist_adj = 1 if angles.wrist_twisted_or_deviated else 0
        wrist_score = min(3, max(1, wrist_base + wrist_adj))

        # Cruce en Tabla B
        table_b_score = lookup_table_b(upper_arm_score, lower_arm_score, wrist_score)

        coupling_clamped = min(3, max(0, coupling_score))
        score_b = min(12, max(1, table_b_score + coupling_clamped))

        return REBAGroupBScore(
            upper_arm_raw_score=upper_arm_score,
            lower_arm_raw_score=lower_arm_score,
            wrist_raw_score=wrist_score,
            table_b_score=table_b_score,
            coupling_score=coupling_clamped,
            score_b=score_b,
        )

    @classmethod
    def evaluate(
        cls,
        angles: BiomechanicalAngles,
        load_kg: float = 0.0,
        is_shock_load: bool = False,
        coupling_score: int = 0,
        is_static: bool = False,
        is_repetitive: bool = False,
        is_rapid_change_or_unstable: bool = False,
    ) -> REBAAssessment:
        """R3 & R4: Dictamen integral REBA y categorización de riesgo."""
        group_a = cls.calculate_group_a(angles, load_kg=load_kg, is_shock_load=is_shock_load)
        group_b = cls.calculate_group_b(angles, coupling_score=coupling_score)

        table_c_score = lookup_table_c(group_a.score_a, group_b.score_b)

        # Puntuación por actividad
        act_score = 0
        if is_static:
            act_score += 1
        if is_repetitive:
            act_score += 1
        if is_rapid_change_or_unstable:
            act_score += 1

        activity = REBAActivityScore(
            is_static=is_static,
            is_repetitive=is_repetitive,
            is_rapid_change_or_unstable=is_rapid_change_or_unstable,
            activity_score=act_score,
        )

        final_score = min(15, max(1, table_c_score + act_score))

        # R4: Determinación de nivel de riesgo y código semafórico
        if final_score == 1:
            risk_level = REBARiskLevel.NEGLIGIBLE
            action_urgency = "Inapreciable: No es necesaria actuación"
            color_code = "VERDE"
        elif 2 <= final_score <= 3:
            risk_level = REBARiskLevel.LOW
            action_urgency = "Bajo: Puede ser necesaria la actuación"
            color_code = "AMARILLO"
        elif 4 <= final_score <= 7:
            risk_level = REBARiskLevel.MEDIUM
            action_urgency = "Medio: Es necesaria la actuación y rediseño de tareas"
            color_code = "NARANJA"
        elif 8 <= final_score <= 10:
            risk_level = REBARiskLevel.HIGH
            action_urgency = "Alto: Es necesaria la actuación e intervención cuanto antes"
            color_code = "ROJO"
        else:
            risk_level = REBARiskLevel.VERY_HIGH
            action_urgency = "Muy Alto: Actuación inmediata requerida"
            color_code = "CRITICO"

        return REBAAssessment(
            group_a=group_a,
            group_b=group_b,
            table_c_score=table_c_score,
            activity=activity,
            final_score=final_score,
            risk_level=risk_level,
            action_urgency=action_urgency,
            color_code=color_code,
        )

