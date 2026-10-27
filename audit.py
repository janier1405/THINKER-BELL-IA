import hashlib, json
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from backend.app.db.models import AuditLog

def _hash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

def _payload(seq, ev, actor, patient, etype, summary, prev):
    return {"seq": seq, "evaluation_id": ev, "actor_id": actor, "patient_id": patient,
            "event_type": etype, "summary": summary, "previous_hash": prev}

def append_audit(db: Session, *, event_type: str, actor_id: str, patient_id: str | None = None,
                 evaluation_id: str | None = None, summary: dict | None = None) -> AuditLog:
    summary = summary or {}
    if db.get_bind().dialect.name == "postgresql":  # serializa los escritores hasta el commit (FOR UPDATE no basta: la fila nueva no estaba bloqueada)
        db.execute(text("SELECT pg_advisory_xact_lock(727001)"))
    last = db.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).scalar_one_or_none()
    seq, prev = (last.seq + 1, last.event_hash) if last else (1, None)
    e = AuditLog(seq=seq, evaluation_id=evaluation_id, actor_id=actor_id, patient_id=patient_id, event_type=event_type,
                 summary=summary, previous_hash=prev, event_hash=_hash(_payload(seq, evaluation_id, actor_id, patient_id, event_type, summary, prev)))
    db.add(e)
    return e

def verify_chain(db: Session) -> tuple[bool, int | None]:
    prev = None
    for r in db.execute(select(AuditLog).order_by(AuditLog.seq)).scalars():
        ok = r.previous_hash == prev and r.event_hash == _hash(_payload(r.seq, r.evaluation_id, r.actor_id, r.patient_id, r.event_type, r.summary, prev))
        if not ok: return False, r.seq
        prev = r.event_hash
    return True, None
