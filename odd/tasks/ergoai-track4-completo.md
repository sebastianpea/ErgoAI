# Feature: ErgoAI Track 4 Jabil — entrega funcional básica

Objective: make ErgoAI functionally complete per Especificaciones_y_Arquitectura_ErgoAI.md: PDF report, official Jabil XLSM filler, per-case workspace, Chair Law evaluator, EAWS calculator, split API routes, angular-precision validation, technical documentation.

Branch: ergoai-unificado
Test runner: pytest (backend), unittest fallback

## Specs

S1. Per-case workspace: `casos_jabil_workspace/caso_<id>/` with `inputs/`, `session_state.json`, `audit_trail.json`, created automatically on case creation. (phase 1)
S2. PDF report generator: `backend/app/exporters/pdf_report_builder.py`, endpoint `/casos/{id}/informe`, returns PDF with skeleton overlay, REBA initial vs residual, NOM-036, specialist validation signatures. (phase 2)
S3. Official Jabil XLSM filler: `backend/app/exporters/jabil_xlsm_filler.py`, populates `16-PE80-6500-00014-H.xlsm` sheets Mov, Levantamiento (1), Transporte (2), Equipo (3), sin auxiliar (4), con auxiliar (5), EAWS, Resultado, Observaciones y Mejoras. (phase 3)
S4. Chair Law evaluator: `backend/app/core_ergonomics/chair_law_evaluator.py`, 7 STPS factors, 3-hour rule, seat placement legend. (phase 4)
S5. EAWS calculator: `backend/app/core_ergonomics/eaws_calculator.py`, posture/force/frequency scoring, risk bands <=5 Bajo, 6-10 Medio, >10 Alto. (phase 5)
S6. Split API routes: `backend/app/api/routes_evaluation.py`, `routes_validation.py`, `routes_reports.py`, wired into `backend/main.py`. (phase 6)
S7. Angular precision validation: tests against `backend/app/seed/dataset_jabil/` images, target >=90% within REBA ranges. (phase 7)
S8. Technical documentation: `docs/Documentacion_Tecnica_ErgoAI.md` (<=10 cuartillas), `docs/arquitectura_diagramas.mmd`. (phase 8)

## Tasks

T1. Phase 0 baseline: verify current pytest suite passes, commit current merge state. Route: inline.
T2. Phase 1 per-case workspace. Route: inline.
T3. Phase 2 PDF report. Route: inline.
T4. Phase 3 XLSM filler. Route: inline.
T5. Phase 4 Chair Law. Route: inline.
T6. Phase 5 EAWS. Route: inline.
T7. Phase 6 split routes. Route: inline.
T8. Phase 7 angular precision tests. Route: inline.
T9. Phase 8 documentation. Route: inline.
T10. Phase 9 full suite verification. Route: inline.

## Log

L1: Analyze ErgoAI merged branches (develop + front-end over main), diagnose gaps vs Especificaciones_y_Arquitectura_ErgoAI.md, create implementation plan and test suite. [today]
