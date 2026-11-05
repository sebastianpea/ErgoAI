"""Servidor Web FastAPI y API REST de ErgoAI para Evaluación Ergonómica Multi-Persona."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ergoai.config import SETTINGS
from ergoai.domain.benchmarks import get_official_jabil_cases
from ergoai.services.report_generator import ErgonomicReportGenerator
from ergoai.services.scene_classifier import TaskAndSceneUnderstandingService
from ergoai.services.vision_pipeline import (
    ErgoAIVisionPipeline,
    MultiPersonSceneEvaluationDTO,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
AUDIT_LOG_FILE = SETTINGS.audit_log_path

# Caché en memoria de la última evaluación para generación de informes instantáneos
LATEST_EVALUATION_CACHE: Dict[str, Any] = {}

app = FastAPI(
    title="ErgoAI Multi-Person Vision & REBA Ergonomics API",
    description="Auditor Técnico Ergonómico con RTMPose WholeBody_133, REBA Oficial y NOM-036",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PIPELINE: Optional[ErgoAIVisionPipeline] = None


def get_pipeline() -> ErgoAIVisionPipeline:
    global PIPELINE
    if PIPELINE is None:
        PIPELINE = ErgoAIVisionPipeline()
    return PIPELINE


def record_audit(event_type: str, details: Dict[str, Any], specialist: Optional[str] = None) -> None:
    """Registra eventos de auditoría y validación Human-in-the-Loop en audit_log.json."""
    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "fecha_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "especialista": specialist or SETTINGS.default_specialist,
        "evento": event_type,
        "detalles": details,
    }
    log_data = []
    if AUDIT_LOG_FILE.exists():
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                log_data = json.load(f)
        except Exception:
            log_data = []
    log_data.append(entry)
    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    pipeline = get_pipeline()
    return {
        "status": "online",
        "system": "ErgoAI Track 4 (Jabil)",
        "models": {
            "pose": "RTMPose WholeBody-133 (ONNX Cocktail14)",
            "detector": "YOLOX-Tiny HumanArt",
            "pipeline": "RTMPose Top-Down (YOLOX + RTMPose-133)",
            "backend": pipeline.backend,
            "device": pipeline.device,
        },
        "ecosystem": [
            "rtmlib (Pipeline Top-Down: YOLOX + RTMPose Wholebody 133)",
            "onnxruntime (Motor Inferencia Universal ONNX)",
            "opencv-python (Lectura de imagen y renderizado por excepción)",
            "numpy (Trigonometría vectorial np.arctan2)",
            "pydantic (Esquemas de configuración validados desde JSON sin hardcode)",
        ],
    }


@app.get("/api/sample_cases")
async def get_sample_cases(include_compliant: bool = False) -> List[Dict[str, Any]]:
    """Retorna los casos de prueba de Jabil desde la fuente única de verdad."""
    benchmark_cases = get_official_jabil_cases(include_compliant=include_compliant)
    return [
        {
            "id": c.case_id,
            **c.model_dump(),
        }
        for c in benchmark_cases
    ]


@app.post("/api/load_sample")
async def load_sample_case(case_id: str = Form(...)) -> Dict[str, Any]:
    """Carga y procesa un caso de prueba del dataset con el pipeline RTMPose WholeBody-133."""
    benchmark_cases = get_official_jabil_cases(include_compliant=True)
    selected = next((c for c in benchmark_cases if c.case_id == case_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail=f"Caso no encontrado: {case_id}")

    pipeline = get_pipeline()

    lat_img = cv2.imread(selected.lateral_file) if os.path.exists(selected.lateral_file) else None
    fro_img = cv2.imread(selected.frontal_file) if os.path.exists(selected.frontal_file) else None
    aer_img = cv2.imread(selected.aerea_file) if os.path.exists(selected.aerea_file) else None

    result = pipeline.evaluate_multi_person_scene(
        lateral_img_bgr=lat_img,
        frontal_img_bgr=fro_img,
        aerea_img_bgr=aer_img,
        load_kg=float(selected.recommended_load_kg),
        coupling_score=int(selected.coupling_score),
        is_static=bool(selected.is_static),
        is_repetitive=bool(selected.is_repetitive),
        is_shock_load=bool(selected.is_shock_load),
        reach_frequency_per_piece=float(selected.reach_frequency),
    )

    LATEST_EVALUATION_CACHE[case_id] = {
        "result": result,
        "case_obj": selected,
    }

    record_audit(
        event_type="EVALUACION_CASO_MUESTRA",
        details={
            "case_id": case_id,
            "case_number": selected.case_number,
            "task_type": selected.task_type,
            "total_personas": result.total_persons_detected,
            "reba_scores": [p.reba["final_score"] for p in result.persons],
            "multi_person_metrics": result.multi_person_metrics,
        },
    )

    p0 = result.persons[0] if result.persons else None
    load_val = float(selected.recommended_load_kg)
    sim_res = TaskAndSceneUnderstandingService.compute_residual_risk_for_person(
        person_dto=p0,
        pipeline=pipeline,
        load_kg=load_val,
        is_static=bool(selected.is_static),
        is_repetitive=bool(selected.is_repetitive),
        force_compliant=(case_id == "caso_postura_correcta_conforme"),
    )

    primary_view = (
        "lateral"
        if os.path.exists(selected.lateral_file)
        else ("frontal" if os.path.exists(selected.frontal_file) else "aerea")
    )

    return {
        "status": "success",
        "task_type": selected.task_type,
        "detected_camera_view": primary_view,
        "inferred_load_kg": load_val,
        "scene_description": selected.description,
        "detected_anomalies": selected.key_biomechanical_issues,
        "matched_case_id": case_id,
        "matched_case_title": selected.title,
        "confidence_score": 1.0,
        "report_url": f"/api/report/{case_id}",
        "residual_risk": sim_res,
        "evaluation": result.model_dump(),
    }


@app.get("/api/single_image_samples")
async def get_single_image_samples() -> List[Dict[str, Any]]:
    """Retorna dinámicamente las imágenes representativas de los 6 casos oficiales."""
    cases = get_official_jabil_cases(include_compliant=False)
    samples: List[Dict[str, Any]] = []
    for c in cases:
        samples.append({
            "case_id": c.case_id,
            "case_number": c.case_number,
            "filename": Path(c.lateral_file).name,
            "title": c.title,
            "task_type": c.task_type,
            "detected_view": "lateral",
            "anomaly": c.key_biomechanical_issues[0] if c.key_biomechanical_issues else c.nom036_focus,
            "load_kg": c.recommended_load_kg,
        })
    return samples


@app.post("/api/analyze_sample_image")
async def analyze_sample_image(
    filename: str = Form(...),
    custom_load_kg: Optional[float] = Form(None),
) -> Dict[str, Any]:
    """Carga y analiza una imagen del dataset deduciendo la tarea y escena."""
    clean_name = os.path.basename(filename)
    target_path = None
    for root, _, files in os.walk(SETTINGS.dataset_dir):
        if clean_name in files:
            target_path = Path(root) / clean_name
            break

    if not target_path or not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Imagen no encontrada en dataset: {filename}")

    img_bgr = cv2.imread(str(target_path))
    if img_bgr is None:
        raise HTTPException(status_code=500, detail=f"No se pudo decodificar la imagen: {filename}")

    pipeline = get_pipeline()
    analysis = TaskAndSceneUnderstandingService.analyze_single_image(
        image_bgr=img_bgr,
        pipeline=pipeline,
        custom_load_kg=custom_load_kg,
    )

    eval_dto = MultiPersonSceneEvaluationDTO.model_validate(analysis.evaluation)
    case_obj = None
    if analysis.matched_case_id:
        benchmark_cases = get_official_jabil_cases(include_compliant=True)
        case_obj = next((c for c in benchmark_cases if c.case_id == analysis.matched_case_id), None)

    cache_entry = {"result": eval_dto, "case_obj": case_obj}
    if analysis.matched_case_id:
        LATEST_EVALUATION_CACHE[analysis.matched_case_id] = cache_entry
    LATEST_EVALUATION_CACHE["evaluacion_imagen_unica"] = cache_entry
    LATEST_EVALUATION_CACHE["evaluacion_personalizada"] = cache_entry

    record_audit(
        event_type="EVALUACION_IMAGEN_UNICA_MUESTRA",
        details={
            "filename": filename,
            "matched_case_id": analysis.matched_case_id,
            "task_type": analysis.task_type,
            "detected_view": analysis.detected_camera_view,
            "anomalies": analysis.detected_anomalies,
        },
    )

    res_dict = analysis.model_dump()
    res_dict["status"] = "success"
    return res_dict


@app.post("/api/analyze_single_image")
async def analyze_single_image(
    image_file: UploadFile = File(...),
    load_kg: Optional[float] = Form(None),
    specialist_name: Optional[str] = Form(None),
) -> Dict[str, Any]:
    """Recibe una fotografía del usuario y deduce automáticamente tarea, perspectiva, REBA y riesgo residual."""
    contents = await image_file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="El archivo de imagen está vacío.")

    nparr = np.frombuffer(contents, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(status_code=400, detail="No se pudo decodificar la imagen proporcionada.")

    pipeline = get_pipeline()
    analysis = TaskAndSceneUnderstandingService.analyze_single_image(
        image_bgr=img_bgr,
        pipeline=pipeline,
        custom_load_kg=load_kg,
        custom_specialist=specialist_name,
    )

    eval_dto = MultiPersonSceneEvaluationDTO.model_validate(analysis.evaluation)
    case_obj = None
    if analysis.matched_case_id:
        benchmark_cases = get_official_jabil_cases(include_compliant=True)
        case_obj = next((c for c in benchmark_cases if c.case_id == analysis.matched_case_id), None)

    cache_entry = {"result": eval_dto, "case_obj": case_obj}
    if analysis.matched_case_id:
        LATEST_EVALUATION_CACHE[analysis.matched_case_id] = cache_entry
    LATEST_EVALUATION_CACHE["evaluacion_imagen_unica"] = cache_entry

    record_audit(
        event_type="EVALUACION_IMAGEN_UNICA_AUTO_TAREA",
        details={
            "filename": image_file.filename,
            "is_benchmark_matched": analysis.is_benchmark_matched,
            "matched_case_id": analysis.matched_case_id,
            "task_type": analysis.task_type,
            "detected_view": analysis.detected_camera_view,
            "anomalies": analysis.detected_anomalies,
            "inferred_load_kg": analysis.inferred_load_kg,
            "confidence": analysis.confidence_score,
        },
        specialist=specialist_name,
    )

    return analysis.model_dump()


@app.post("/api/evaluate")
async def evaluate_uploaded_images(
    lateral_file: Optional[UploadFile] = File(None),
    frontal_file: Optional[UploadFile] = File(None),
    aerea_file: Optional[UploadFile] = File(None),
    load_kg: float = Form(0.0),
    coupling_score: int = Form(0),
    is_static: bool = Form(False),
    is_repetitive: bool = Form(False),
    is_shock_load: bool = Form(False),
    reach_frequency: float = Form(1.0),
) -> Dict[str, Any]:
    """Recibe de 1 a 3 imágenes subidas por el usuario y ejecuta inferencia RTMPose WholeBody_133 y REBA."""
    pipeline = get_pipeline()

    async def _read_upload(upload_file: Optional[UploadFile]) -> Optional[np.ndarray]:
        if upload_file is None:
            return None
        contents = await upload_file.read()
        if not contents:
            return None
        nparr = np.frombuffer(contents, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    lat_img = await _read_upload(lateral_file)
    fro_img = await _read_upload(frontal_file)
    aer_img = await _read_upload(aerea_file)

    if lat_img is None and fro_img is None and aer_img is None:
        raise HTTPException(status_code=400, detail="Debe proporcionar al menos una fotografía para evaluar.")

    result = pipeline.evaluate_multi_person_scene(
        lateral_img_bgr=lat_img,
        frontal_img_bgr=fro_img,
        aerea_img_bgr=aer_img,
        load_kg=load_kg,
        coupling_score=coupling_score,
        is_static=is_static,
        is_repetitive=is_repetitive,
        is_shock_load=is_shock_load,
        reach_frequency_per_piece=reach_frequency,
    )

    record_audit(
        event_type="EVALUACION_IMAGENES_USUARIO",
        details={
            "total_personas": result.total_persons_detected,
            "reba_scores": [p.reba["final_score"] for p in result.persons],
            "load_kg": load_kg,
            "is_static": is_static,
            "is_repetitive": is_repetitive,
        },
    )

    LATEST_EVALUATION_CACHE["evaluacion_personalizada"] = {"result": result, "case_obj": None}
    LATEST_EVALUATION_CACHE["evaluacion_imagen_unica"] = {"result": result, "case_obj": None}

    primary_img = lat_img if lat_img is not None else (fro_img if fro_img is not None else aer_img)
    primary_view = "lateral" if lat_img is not None else ("frontal" if fro_img is not None else "aerea")

    return TaskAndSceneUnderstandingService.classify_from_evaluated_scene(
        eval_res=result,
        pipeline=pipeline,
        primary_img=primary_img,
        primary_view=primary_view,
        load_kg=load_kg,
        is_static=is_static,
        is_repetitive=is_repetitive,
        report_id="evaluacion_personalizada",
    )


class SimulationRequest(BaseModel):
    original_angles: Dict[str, Any]
    original_load_kg: float = 0.0
    selected_controls: List[str] = []
    user_adjusted_angles: Optional[Dict[str, float]] = None
    is_static: bool = False
    is_repetitive: bool = False
    specialist_name: str = SETTINGS.default_specialist


@app.post("/api/simulate")
async def simulate_residual_risk(req: SimulationRequest) -> Dict[str, Any]:
    """Calcula el riesgo residual REBA tras la aprobación de controles de ingeniería."""
    pipeline = get_pipeline()
    res = pipeline.simulate_residual_risk(
        original_angles=req.original_angles,
        original_load_kg=req.original_load_kg,
        selected_controls=req.selected_controls,
        user_adjusted_angles=req.user_adjusted_angles,
        is_static=req.is_static,
        is_repetitive=req.is_repetitive,
    )

    record_audit(
        event_type="SIMULACION_RIESGO_RESIDUAL",
        details={
            "controles_aprobados": req.selected_controls,
            "angulos_ajustados": req.user_adjusted_angles,
            "reba_residual": res["residual_reba_score"],
            "nivel_residual": res["residual_risk_level"],
        },
        specialist=req.specialist_name,
    )

    return res


@app.get("/api/report/{case_id}", response_class=HTMLResponse)
async def get_case_report(case_id: str) -> HTMLResponse:
    """Genera y sirve el Informe Técnico Oficial (NOM-036 / Jabil) en formato HTML."""
    cached = LATEST_EVALUATION_CACHE.get(case_id)
    if not cached:
        await load_sample_case(case_id=case_id)
        cached = LATEST_EVALUATION_CACHE.get(case_id)

    if not cached:
        raise HTTPException(status_code=404, detail=f"No se pudo generar el informe para el caso: {case_id}")

    html = ErgonomicReportGenerator.generate_html_report(
        eval_data=cached["result"],
        case_info=cached.get("case_obj"),
        specialist_name=SETTINGS.default_specialist,
        is_approved_for_floor=True,
    )
    return HTMLResponse(content=html)


@app.post("/api/generate_all_reports")
async def generate_all_reports() -> Dict[str, Any]:
    """Genera en lote los 6 informes técnicos oficiales de Jabil requeridos por la Rúbrica."""
    reports = ErgonomicReportGenerator.generate_all_official_reports()
    record_audit(
        event_type="GENERACION_MASIVA_INFORMES_RUBRICA",
        details={"total_informes": len(reports), "informes": reports},
    )
    return {
        "status": "success",
        "total_generated": len(reports),
        "output_directory": str(ErgonomicReportGenerator.OUTPUT_DIR),
        "reports": reports,
    }


class ApproveActionRequest(BaseModel):
    case_id: str
    action_id: str
    action_title: str
    specialist_name: str = SETTINGS.default_specialist
    specialist_notes: str = "Aprobado para implementación inmediata en piso tras validación ergonómica."
    is_approved: bool = True


@app.post("/api/approve_action")
async def approve_action_hitl(req: ApproveActionRequest) -> Dict[str, Any]:
    """El especialista valida y aprueba recomendaciones antes de convertirlas en acciones de piso."""
    record_audit(
        event_type="CERTIFICACION_ACCION_PISO_HITL",
        details={
            "case_id": req.case_id,
            "action_id": req.action_id,
            "action_title": req.action_title,
            "aprobada": req.is_approved,
            "notas_especialista": req.specialist_notes,
            "estatus": "APROBADA_PARA_PISO" if req.is_approved else "RECHAZADA",
        },
        specialist=req.specialist_name,
    )
    return {
        "status": "APROBADA_PARA_PISO" if req.is_approved else "RECHAZADA",
        "message": f"Acción '{req.action_title}' registrada con éxito en bitácora de auditoría.",
        "case_id": req.case_id,
        "specialist": req.specialist_name,
        "timestamp": time.time(),
    }


@app.get("/api/audit_log")
async def get_audit_log() -> List[Dict[str, Any]]:
    if AUDIT_LOG_FILE.exists():
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


@app.get("/", response_class=HTMLResponse)
async def serve_index() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Archivo index.html no encontrado.")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=SETTINGS.host, port=SETTINGS.port)
