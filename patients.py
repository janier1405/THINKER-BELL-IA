from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.api.v1.endpoints.auth import require_roles
from backend.app.db.models import Patient, User
from backend.app.db.session import get_db
from backend.app.schemas.triage import PatientIn
from backend.app.services.audit import append_audit

router = APIRouter(prefix="/patients", tags=["Patients"])
ANY = ("admin", "clinician", "auditor")

def ser(p: Patient, role: str = "clinician"):
    hide = role == "auditor"  # minimización: el auditor ve seudónimos (ID, sexo, fecha), no nombre ni edad
    return {"patient_id": p.id, "full_name": None if hide else p.full_name, "age": None if hide else p.age, "gender": p.gender, "created_at": p.created_at}

@router.post("", status_code=201)
def create_patient(body: PatientIn, user: User = Depends(require_roles("admin", "clinician")), db: Session = Depends(get_db)):
    if db.get(Patient, body.patient_id): raise HTTPException(409, "El paciente ya existe; no se sobrescribe.")
    p = Patient(id=body.patient_id, full_name=body.full_name, age=body.age, gender=body.gender)
    db.add(p); db.flush()
    append_audit(db, event_type="patient_created", actor_id=user.id, patient_id=p.id)
    db.commit()
    return ser(p)

@router.get("")
def list_patients(q: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                  user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    stmt = select(Patient)
    if q: stmt = stmt.where(Patient.id.istartswith(q, autoescape=True))  # solo por ID: nombres en query string acabarían en logs de acceso
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.execute(stmt.order_by(Patient.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return {"items": [ser(p, user.role) for p in rows], "total": total, "limit": limit, "offset": offset}

@router.get("/{patient_id}")
def get_patient(patient_id: str, user: User = Depends(require_roles(*ANY)), db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p: raise HTTPException(404, "Paciente no encontrado.")
    return ser(p, user.role)
