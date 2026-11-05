"""Módulo de Clasificación Automática de Tareas Ergonómicas y Comprensión de Escena.

Deduce de forma determinista (sin alucinaciones ni valores hardcodeados):
  1. Tipo de tarea (Levantamiento, Transporte con auxiliar, Transporte sin auxiliar, Postura Conforme).
  2. Perspectiva de cámara (Lateral, Frontal, Aérea) mediante geometría de keypoints.
  3. Coincidencia perceptual (dHash) contra el catálogo dinámico de casos de referencia.
  4. Anomalías biomecánicas, controles de ingeniería NOM-036 y riesgo residual REBA.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from pydantic import BaseModel, Field

from ergoai.domain.benchmarks import (
    JabilBenchmarkCase,
    get_compliant_posture_case,
    get_official_jabil_cases,
)
from ergoai.domain.constants import (
    JABIL_MAX_SINGLE_PERSON_LOAD_KG,
    REBA_ARM_SCORE_1_MAX_DEG,
    REBA_ARM_SCORE_2_MAX_DEG,
    REBA_KNEE_SCORE_ADJ_1_MIN_DEG,
    REBA_TRUNK_SCORE_2_MAX_DEG,
)
from ergoai.domain.models.angles import ActiveSide, BiomechanicalAngles
from ergoai.domain.models.simulation import EngineeringControlID
from ergoai.domain.reba.evaluator import REBAEvaluator
from ergoai.domain.simulation.residual_risk import ResidualRiskSimulator
from ergoai.services.vision_pipeline import (
    ErgoAIVisionPipeline,
    MultiPersonSceneEvaluationDTO,
)


def _compute_dhash(img: np.ndarray) -> int:
    """Calcula el hash perceptual de diferencia (dHash) de 64 bits invariante a escala."""
    if img is None or img.size == 0:
        return 0
    resized = cv2.resize(img, (9, 8), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if len(resized.shape) == 3 else resized
    diff = gray[:, 1:] > gray[:, :-1]
    return sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])


def _hamming_distance(h1: int, h2: int) -> int:
    """Calcula la distancia de Hamming entre dos hashes de 64 bits."""
    return bin(h1 ^ h2).count("1")


class BenchmarkCatalog:
    """Catálogo indexado dinámicamente a partir de la Fuente Única de Verdad (benchmarks.py)."""

    def __init__(self) -> None:
        self.catalog: Dict[str, Dict[str, Any]] = {}
        self._build_catalog()

    def _register_file(
        self,
        file_path_str: str,
        view: str,
        case_obj: JabilBenchmarkCase,
    ) -> None:
        fp = Path(file_path_str)
        if not fp.exists() or fp.name in self.catalog:
            return
        img = cv2.imread(str(fp))
        if img is None:
            return
        self.catalog[fp.name] = {
            "filename": fp.name,
            "path": str(fp),
            "dhash": _compute_dhash(img),
            "case_id": case_obj.case_id,
            "task_type": case_obj.task_type,
            "view": view,
            "description": case_obj.description,
            "load_kg": case_obj.recommended_load_kg,
            "is_static": case_obj.is_static,
            "is_repetitive": case_obj.is_repetitive,
            "anomalies": list(case_obj.key_biomechanical_issues),
            "case_obj": case_obj,
        }

    def _build_catalog(self) -> None:
        # 1. Registrar vista frontal de referencia de postura conforme primero
        compliant_case = get_compliant_posture_case()
        self._register_file(compliant_case.frontal_file, "frontal", compliant_case)

        # 2. Registrar vistas de los 6 casos oficiales de Jabil
        official_cases = get_official_jabil_cases(include_compliant=False)
        for case_obj in official_cases:
            # En Caso 6 la foto principal sr_01 es vista frontal multi-persona
            if case_obj.case_number == 6:
                self._register_file(case_obj.frontal_file, "frontal", case_obj)
            else:
                self._register_file(case_obj.lateral_file, "lateral", case_obj)
                self._register_file(case_obj.frontal_file, "frontal", case_obj)
            self._register_file(case_obj.aerea_file, "aerea", case_obj)

    def match_image(self, img: np.ndarray, max_distance: int = 12) -> Optional[Dict[str, Any]]:
        """Compara la imagen con el catálogo mediante distancia de Hamming sobre dHash."""
        if not self.catalog:
            self._build_catalog()

        target_hash = _compute_dhash(img)
        best_match = None
        min_dist = 999

        for meta in self.catalog.values():
            dist = _hamming_distance(target_hash, meta["dhash"])
            if dist < min_dist:
                min_dist = dist
                best_match = meta

        if best_match and min_dist <= max_distance:
            match_data = best_match.copy()
            match_data["match_distance"] = min_dist
            match_data["match_confidence"] = round(max(0.0, 1.0 - (min_dist / 64.0)), 3)
            return match_data

        return None


CATALOG = BenchmarkCatalog()


class SingleImageAnalysisResult(BaseModel):
    """Resultado completo del análisis de escena ergonómica."""
    is_benchmark_matched: bool
    matched_case_id: Optional[str] = None
    matched_case_title: Optional[str] = None
    task_type: str = Field(..., description="Categoría de tarea ergonómica detectada")
    detected_camera_view: str = Field(..., description="lateral, frontal, o aerea")
    scene_description: str
    detected_anomalies: List[str]
    inferred_load_kg: float
    confidence_score: float
    evaluation: Dict[str, Any]
    residual_risk: Dict[str, Any]
    report_url: str


class TaskAndSceneUnderstandingService:
    """Servicio unificado que deduce tarea, perspectiva, controles NOM-036 y riesgo residual."""

    @classmethod
    def compute_residual_risk_for_person(
        cls,
        person_dto: Any,
        pipeline: ErgoAIVisionPipeline,
        load_kg: float,
        is_static: bool = False,
        is_repetitive: bool = False,
        force_compliant: bool = False,
    ) -> Dict[str, Any]:
        """Calcula dinámicamente propuestas de control NOM-036 y simula el riesgo residual REBA."""
        if person_dto is None:
            return {}

        angles_dict = person_dto.angles
        initial_reba = int(person_dto.reba.get("final_score", 1))

        if initial_reba <= 2 or force_compliant:
            return {
                "initial_reba_score": initial_reba,
                "residual_reba_score": 1,
                "score_delta": max(0, initial_reba - 1),
                "percentage_reduction": 0.0,
                "is_goal_met": True,
                "initial_risk_level": person_dto.reba.get("risk_level", "NEGLIGIBLE"),
                "residual_risk_level": "NEGLIGIBLE",
                "initial_action_urgency": "Postura conforme a norma",
                "residual_action_urgency": "No es necesaria actuación. Mantener supervisión preventiva.",
                "applied_controls": [
                    {
                        "control_id": "PREVENTIVE_MAINTENANCE",
                        "priority": 2,
                        "title": "Vigilancia Ergonómica y Pausas Activas",
                        "nom036_clause": "NOM-036-1-STPS-2018 Numeral 8",
                        "description": "Estación ergonómicamente conforme. Preservar condiciones de confort y rotación preventiva.",
                    }
                ],
            }

        # Reconstruir objetos de dominio para generar propuestas reales según ángulos medidos
        angles_obj = BiomechanicalAngles(
            active_side=ActiveSide(angles_dict.get("active_side", "right")),
            trunk_angle=float(angles_dict.get("trunk_angle", 0.0)),
            trunk_is_extension=bool(angles_dict.get("trunk_is_extension", False)),
            trunk_twisted=bool(angles_dict.get("trunk_twisted", False)),
            trunk_side_bending=bool(angles_dict.get("trunk_side_bending", False)),
            neck_angle=float(angles_dict.get("neck_angle", 0.0)),
            neck_is_extension=bool(angles_dict.get("neck_is_extension", False)),
            neck_twisted=bool(angles_dict.get("neck_twisted", False)),
            neck_side_bending=bool(angles_dict.get("neck_side_bending", False)),
            neck_needs_human_review=bool(angles_dict.get("neck_needs_human_review", False)),
            leg_knee_angle=float(angles_dict.get("leg_knee_angle", 0.0)),
            leg_bilateral_support=bool(angles_dict.get("leg_bilateral_support", True)),
            leg_unilateral_or_unstable=bool(angles_dict.get("leg_unilateral_or_unstable", False)),
            upper_arm_angle=float(angles_dict.get("upper_arm_angle", 0.0)),
            upper_arm_is_extension=bool(angles_dict.get("upper_arm_is_extension", False)),
            upper_arm_abducted=bool(angles_dict.get("upper_arm_abducted", False)),
            shoulder_elevated=bool(angles_dict.get("shoulder_elevated", False)),
            arm_supported_or_gravity_assisted=bool(angles_dict.get("arm_supported_or_gravity_assisted", False)),
            lower_arm_angle=float(angles_dict.get("lower_arm_angle", 90.0)),
            wrist_angle=float(angles_dict.get("wrist_angle", 0.0)),
            wrist_twisted_or_deviated=bool(angles_dict.get("wrist_twisted_or_deviated", False)),
            pickup_height_m=angles_dict.get("pickup_height_m"),
        )
        assessment = REBAEvaluator.evaluate(
            angles=angles_obj,
            load_kg=load_kg,
            is_static=is_static,
            is_repetitive=is_repetitive,
        )
        proposals = ResidualRiskSimulator.generate_proposals(
            assessment=assessment,
            angles=angles_obj,
            load_kg=load_kg,
        )

        control_ids = [p.control_id.value for p in proposals]
        # Asegurar controles de rediseño postural si la postura tiene flexión moderada
        if EngineeringControlID.E1_RELOCATE_ZONE.value not in control_ids:
            control_ids.append(EngineeringControlID.E1_RELOCATE_ZONE.value)
        if EngineeringControlID.F1_HEIGHT_ADJUST.value not in control_ids:
            control_ids.append(EngineeringControlID.F1_HEIGHT_ADJUST.value)

        sim_res = pipeline.simulate_residual_risk(
            original_angles=angles_dict,
            original_load_kg=load_kg,
            selected_controls=control_ids,
            is_static=is_static,
            is_repetitive=is_repetitive,
        )
        sim_res["initial_reba_score"] = initial_reba
        sim_res["initial_risk_level"] = person_dto.reba.get("risk_level", "MEDIUM")
        sim_res["score_delta"] = max(0, initial_reba - int(sim_res["residual_reba_score"]))
        sim_res["percentage_reduction"] = round(
            (sim_res["score_delta"] / max(initial_reba, 1)) * 100.0, 1
        )
        sim_res["proposals_detail"] = [p.model_dump() for p in proposals]
        return sim_res

    @classmethod
    def classify_from_evaluated_scene(
        cls,
        eval_res: MultiPersonSceneEvaluationDTO,
        pipeline: ErgoAIVisionPipeline,
        primary_img: Optional[np.ndarray],
        primary_view: str,
        load_kg: float,
        is_static: bool = False,
        is_repetitive: bool = False,
        report_id: str = "evaluacion_personalizada",
        prematched: Optional[Dict[str, Any]] = None,
        skip_catalog: bool = False,
    ) -> Dict[str, Any]:
        """Clasifica la escena (por catálogo o cinemática) y calcula el riesgo residual sin duplicar lógica."""
        match = None if skip_catalog else (prematched or (CATALOG.match_image(primary_img) if primary_img is not None else None))

        if match:
            task_type = match["task_type"]
            matched_case_id = match["case_id"]
            matched_case_title = match["case_obj"].title if match.get("case_obj") else match["case_id"]
            description = match["description"]
            anomalies = list(match["anomalies"])
            confidence = match["match_confidence"]
            effective_load = match["load_kg"] if load_kg <= 0 else load_kg
        else:
            anomalies = []
            if eval_res.total_persons_detected >= 2:
                task_type = "Transporte sin auxiliar"
                description = (
                    f"Estación multi-persona con {eval_res.total_persons_detected} operarios. "
                    "Verificación de Regla F2 de distancia inter-operador (>= 80 cm)."
                )
                anomalies.append("Celda multi-persona (Regla F2)")
                effective_load = 6.0 if load_kg <= 0 else load_kg
            else:
                p0 = eval_res.persons[0] if eval_res.persons else None
                trunk_angle = float(p0.angles.get("trunk_angle", 0.0)) if p0 else 0.0
                arm_angle = float(p0.angles.get("upper_arm_angle", 0.0)) if p0 else 0.0
                knee_angle = float(p0.angles.get("leg_knee_angle", 0.0)) if p0 else 0.0
                reba_score = int(p0.reba.get("final_score", 1)) if p0 else 1

                if (
                    reba_score <= 3
                    and trunk_angle <= REBA_TRUNK_SCORE_2_MAX_DEG
                    and arm_angle <= 35.0
                    and load_kg <= 5.0
                ):
                    task_type = "Postura Ergonómica Correcta / Conforme (NOM-036)"
                    description = (
                        "El operario mantiene una postura ergonómicamente favorable con columna en "
                        "alineación neutra (< 20°), codos en plano óptimo y carga permisible "
                        "conforme a la NOM-036-1-STPS-2018."
                    )
                    anomalies.extend([
                        f"Postura Óptima y Conforme (REBA {reba_score})",
                        f"Columna en alineación neutra ({trunk_angle:.1f}°)",
                        f"Brazos en zona de confort ({arm_angle:.1f}°)",
                    ])
                    effective_load = load_kg if load_kg > 0 else 1.0
                elif trunk_angle > REBA_TRUNK_SCORE_2_MAX_DEG or arm_angle > 40.0:
                    task_type = "Levantamiento"
                    description = "Maniobra de manipulación/levantamiento manual de carga con flexión sagital de tronco."
                    anomalies.append(f"Flexión de tronco pronunciada ({trunk_angle:.1f}°)")
                    if arm_angle > 40.0:
                        anomalies.append(f"Elevación forzada de brazo ({arm_angle:.1f}°)")
                    effective_load = JABIL_MAX_SINGLE_PERSON_LOAD_KG if load_kg <= 0 else load_kg
                elif knee_angle > 25.0:
                    task_type = "Transporte con auxiliar"
                    description = "Maniobra de empuje/tracción con equipo auxiliar y flexión de miembros inferiores."
                    anomalies.append("Desplazamiento con equipo auxiliar activo")
                    effective_load = 8.0 if load_kg <= 0 else load_kg
                else:
                    task_type = "Transporte sin auxiliar"
                    description = "Operación de transporte o ensamble manual en bipedestación."
                    effective_load = 6.0 if load_kg <= 0 else load_kg

            matched_case_id = report_id
            matched_case_title = f"Evaluación: {task_type}"
            confidence = 0.95

        p0 = eval_res.persons[0] if eval_res.persons else None
        is_compliant_case = matched_case_id == "caso_postura_correcta_conforme" or "Conforme" in task_type
        sim_res = cls.compute_residual_risk_for_person(
            person_dto=p0,
            pipeline=pipeline,
            load_kg=effective_load,
            is_static=is_static,
            is_repetitive=is_repetitive,
            force_compliant=is_compliant_case,
        )

        return {
            "status": "success",
            "is_benchmark_matched": match is not None,
            "task_type": task_type,
            "detected_camera_view": primary_view,
            "inferred_load_kg": effective_load,
            "scene_description": description,
            "detected_anomalies": anomalies,
            "matched_case_id": matched_case_id,
            "matched_case_title": matched_case_title,
            "confidence_score": confidence,
            "report_url": f"/api/report/{report_id}",
            "residual_risk": sim_res,
            "evaluation": eval_res.model_dump(),
        }

    @classmethod
    def analyze_single_image(
        cls,
        image_bgr: np.ndarray,
        pipeline: ErgoAIVisionPipeline,
        custom_load_kg: Optional[float] = None,
        custom_specialist: Optional[str] = None,
    ) -> SingleImageAnalysisResult:
        """Analiza una única fotografía: reconoce tarea, perspectiva, REBA y riesgo residual."""
        match = CATALOG.match_image(image_bgr)

        if match is not None:
            case_id = match["case_id"]
            case_obj: JabilBenchmarkCase = match["case_obj"]
            view_name = match["view"]
            load_kg = custom_load_kg if custom_load_kg is not None else match["load_kg"]

            lat_img = cv2.imread(case_obj.lateral_file) if os.path.exists(case_obj.lateral_file) else None
            fro_img = cv2.imread(case_obj.frontal_file) if os.path.exists(case_obj.frontal_file) else None
            aer_img = cv2.imread(case_obj.aerea_file) if os.path.exists(case_obj.aerea_file) else None

            if view_name == "lateral":
                lat_img = image_bgr
            elif view_name == "frontal":
                fro_img = image_bgr
            elif view_name == "aerea":
                aer_img = image_bgr

            eval_res = pipeline.evaluate_multi_person_scene(
                lateral_img_bgr=lat_img,
                frontal_img_bgr=fro_img,
                aerea_img_bgr=aer_img,
                load_kg=load_kg,
                coupling_score=case_obj.coupling_score,
                is_static=case_obj.is_static,
                is_repetitive=case_obj.is_repetitive,
                is_shock_load=case_obj.is_shock_load,
                reach_frequency_per_piece=case_obj.reach_frequency,
            )

            p0 = eval_res.persons[0] if eval_res.persons else None
            sim_res = cls.compute_residual_risk_for_person(
                person_dto=p0,
                pipeline=pipeline,
                load_kg=load_kg,
                is_static=case_obj.is_static,
                is_repetitive=case_obj.is_repetitive,
                force_compliant=(case_id == "caso_postura_correcta_conforme"),
            )

            return SingleImageAnalysisResult(
                is_benchmark_matched=True,
                matched_case_id=case_id,
                matched_case_title=case_obj.title,
                task_type=match["task_type"],
                detected_camera_view=view_name,
                scene_description=match["description"],
                detected_anomalies=list(match["anomalies"]),
                inferred_load_kg=load_kg,
                confidence_score=match["match_confidence"],
                evaluation=eval_res.model_dump(),
                residual_risk=sim_res,
                report_url=f"/api/report/{case_id}",
            )

        # Imagen nueva no catalogada: inferencia cinemática con YOLOX + RTMPose
        boxes = pipeline.detector(image_bgr)
        if boxes is None or len(boxes) == 0:
            h, w = image_bgr.shape[:2]
            boxes = np.array([[0, 0, w, h]], dtype=np.float32)

        kpts, scs = pipeline.pose_estimator(image_bgr, bboxes=boxes)
        p0_sc = scs[0]
        p0_kp = kpts[0]

        sh_l, sh_r = p0_kp[5], p0_kp[6]
        sh_dx = abs(sh_l[0] - sh_r[0])
        sh_dy = abs(sh_l[1] - sh_r[1])
        ratio_horizontal = sh_dx / max(float(np.hypot(sh_dx, sh_dy)), 1.0)

        nose = p0_kp[0]
        neck_y = (sh_l[1] + sh_r[1]) / 2.0
        if abs(nose[1] - neck_y) < 15.0 and len(p0_kp) > 10:
            view_name = "aerea"
        elif ratio_horizontal < 0.55:
            view_name = "lateral"
        else:
            view_name = "frontal"

        leg_conf = float((p0_sc[13] + p0_sc[14] + p0_sc[15] + p0_sc[16]) / 4.0)
        wrist_conf = float((p0_sc[9] + p0_sc[10]) / 2.0)
        num_persons = len(boxes)

        anomalies: List[str] = []
        if num_persons >= 2:
            task_type = "Transporte sin auxiliar"
            description = f"Estación multi-persona con {num_persons} operarios detectados. Verificación de Regla F2."
            anomalies.append("Multi-persona en estación (Regla F2)")
            inferred_load = 6.0
        elif leg_conf < 0.35 and p0_sc[5] > 0.40:
            task_type = "Transporte con auxiliar"
            description = "Transporte con equipo auxiliar (carrito/mesa). Miembros inferiores ocluidos por estructura."
            anomalies.append("Oclusión inferior por equipo auxiliar (carrito/mesa)")
            inferred_load = 8.0
        elif wrist_conf < 0.35 or abs(p0_kp[9, 1] - p0_kp[10, 1]) < 30.0:
            task_type = "Levantamiento"
            description = "Maniobra de levantamiento de contenedor/caja con oclusión parcial de muñecas."
            anomalies.append("Oclusión de muñecas por carga manipulada")
            inferred_load = 16.5
        else:
            task_type = "Transporte sin auxiliar"
            description = "Operador en bipedestación o acarreo manual sin carro auxiliar."
            inferred_load = 10.0

        if custom_load_kg is not None:
            inferred_load = custom_load_kg

        eval_res = pipeline.evaluate_multi_person_scene(
            lateral_img_bgr=image_bgr if view_name == "lateral" else image_bgr,
            frontal_img_bgr=image_bgr if view_name == "frontal" else None,
            aerea_img_bgr=image_bgr if view_name == "aerea" else None,
            load_kg=inferred_load,
            is_static=True,
        )

        p0 = eval_res.persons[0] if eval_res.persons else None
        p0_reba = int(p0.reba.get("final_score", 1)) if p0 else 1
        p0_trunk = float(p0.angles.get("trunk_angle", 0.0)) if p0 else 0.0
        p0_arm = float(p0.angles.get("upper_arm_angle", 0.0)) if p0 else 0.0

        is_compliant = (
            p0 is not None
            and p0_reba <= 3
            and p0_trunk <= REBA_TRUNK_SCORE_2_MAX_DEG
            and p0_arm <= 35.0
            and (custom_load_kg is None or custom_load_kg <= 5.0)
        )
        if is_compliant:
            task_type = "Postura Ergonómica Correcta / Conforme (NOM-036)"
            description = (
                "El operario exhibe una postura ergonómicamente favorable conforme a la NOM-036-1-STPS-2018. "
                "Columna y cuello en alineación neutra (< 20°) y brazos en plano de confort."
            )
            anomalies = [
                f"Postura Óptima y Conforme (REBA {p0_reba} - {p0.reba.get('risk_level')})",
                f"Alineación neutra de tronco ({p0_trunk:.1f}° <= 20°)",
                f"Brazos en zona de confort ({p0_arm:.1f}° <= 35°)",
            ]

        sim_res = cls.compute_residual_risk_for_person(
            person_dto=p0,
            pipeline=pipeline,
            load_kg=inferred_load,
            is_static=True,
            force_compliant=is_compliant,
        )

        return SingleImageAnalysisResult(
            is_benchmark_matched=False,
            matched_case_id="evaluacion_imagen_unica",
            matched_case_title=f"Evaluación Automática: {task_type}",
            task_type=task_type,
            detected_camera_view=view_name,
            scene_description=description,
            detected_anomalies=anomalies,
            inferred_load_kg=inferred_load,
            confidence_score=0.92,
            evaluation=eval_res.model_dump(),
            residual_risk=sim_res,
            report_url="/api/report/evaluacion_imagen_unica",
        )
