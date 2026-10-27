from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, func, select
from sqlalchemy.orm import Session
from backend.app.api.v1.endpoints.auth import require_roles
from backend.app.db.models import Patient, TriageEvaluation, User
from backend.app.db.session import get_db
from backend.app.schemas.triage import EvaluateIn
from backend.app.services.audit import append_audit, verify_chain
from clinical.algorithms.news2.calculator import ALGORITHM_VERSION, RULES_SOURCE, RULES_STATUS, NEWS2Calculator, VitalSigns

router = APIRouter(tags=["Clinical"])
ANY = ("admin", "clinician", "auditor")

def ser(x: TriageEvaluation):
    return {"evaluation_id": x.id, "timestamp": x.timestamp, "patient_id": x.patient_id, "clinician_id": x.clinician_id,
            "total_score": x.total_score, "parameter_scores": x.parameter_scores, "vitals": x.vitals,
            "clinical_risk": x.clinical_risk, "recommended_response": x.recommended_response,
            "algorithm_version": x.algorithm_version, "rules_status": x.rules_status}

@router.get("/news2/info")
def news2_info(user: User = Depends(require_roles(*ANY))):
    return {"algorithm_version": ALGORITHM_VERSION, "rules_status": RULES_STATUS, "source": RULES_SOURCE,
            "notice": "Módulo pendiente de validación clínica. No es diagnóstico ni dispositivo médico autorizado."}

@router.post("/triage/evaluate", status_code=201)
def evaluate(body: EvaluateIn, user: User = Depends(require_roles("clinician")), db: Session = Depends(get_db)):
    patient = db.get(Patient, body.patient_id)
    if not patient: raise HTTPException(404, "Paciente no encontrado; regístralo primero.")
    if patient.age < 16:  # RCP 2017, recomendación 2: NEWS2 no debe usarse en menores de 16 años (embarazo no se modela: pendiente)
        raise HTTPException(422, "NEWS2 no está indicado para menores de 16 años (RCP 2017). Usa el protocolo pediátrico institucional.")
    r = NEWS2Calculator.evaluate(VitalSigns(**body.vitals.model_dump()))
    ev = TriageEvaluation(patient_id=body.patient_id, clinician_id=user.id, total_score=r.total_score,
                          parameter_scores=r.parameter_scores, vitals=body.vitals.model_dump(mode="json"),
                          clinical_risk=r.clinical_risk, recommended_response=r.recommended_response,
                          algorithm_version=r.algorithm_version, rules_status=r.rules_status)
    try:
        db.add(ev); db.flush()
        append_audit(db, event_type="triage_evaluated", actor_id=user.id, patient_id=body.patient_id, evaluation_id=ev.id,
                     summary={"score": r.total_score, "algorithm_version": r.algorithm_version})
        db.commit()
    except Exception as exc:
        db.rollback(); raise HTTPException(500, "No fue posible guardar la evaluación.") from exc
    return ser(ev)

@router.get("/triage/evaluations")
def list_evaluations(patient_id: str | None = None, risk: str | None = None, date_from: date | None = None,
                     date_to: date | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                     user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    stmt, day = select(TriageEvaluation), func.date(TriageEvaluation.timestamp, type_=Date)
    if patient_id: stmt = stmt.where(TriageEvaluation.patient_id == patient_id)
    if risk: stmt = stmt.where(TriageEvaluation.clinical_risk == risk)
    if date_from: stmt = stmt.where(day >= date_from)
    if date_to: stmt = stmt.where(day <= date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(TriageEvaluation.timestamp.desc()).limit(limit).offset(offset)).scalars().all()
    return {"items": [ser(x) for x in rows], "total": total, "limit": limit, "offset": offset}

@router.get("/triage/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: str, user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    x = db.get(TriageEvaluation, evaluation_id)
    if not x: raise HTTPException(404, "Evaluación no encontrada.")
    return ser(x)

@router.get("/dashboard/summary")
def dashboard(user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    day = func.date(TriageEvaluation.timestamp, type_=Date)
    per_day = db.execute(select(day, func.count()).group_by(day).order_by(day.desc()).limit(7)).all()
    recent = db.execute(select(TriageEvaluation).order_by(TriageEvaluation.timestamp.desc()).limit(5)).scalars().all()
    return {"evaluations": db.scalar(select(func.count(TriageEvaluation.id))), "patients": db.scalar(select(func.count(Patient.id))),
            "risk_distribution": {k: n for k, n in db.execute(select(TriageEvaluation.clinical_risk, func.count()).group_by(TriageEvaluation.clinical_risk)).all()},
            "per_day": [{"day": d.isoformat(), "count": n} for d, n in reversed(per_day)], "recent": [ser(x) for x in recent]}

@router.get("/audit/verify")
def audit_verify(user: User = Depends(require_roles("admin", "auditor")), db: Session = Depends(get_db)):
    ok, bad = verify_chain(db)
    return {"valid": ok, "first_invalid_seq": bad}
