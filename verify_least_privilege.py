"""Verifica con el rol tb_app: la app funciona y NO puede alterar/borrar auditoría ni evaluaciones. Uso: DATABASE_URL=<url de tb_app> python scripts/verify_least_privilege.py"""
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from backend.app.db.session import SessionLocal
from backend.app.main import app
import os
u, pw = os.environ["VERIFY_USER"], os.environ["VERIFY_PASSWORD"]
c = TestClient(app); assert c.post("/api/v1/auth/login", json={"username": u, "password": pw}).status_code == 200
c.headers["X-CSRF-Token"] = c.cookies["tb_csrf"]
assert c.post("/api/v1/patients", json={"patient_id": "PRIV-1", "full_name": "Sintético", "age": 50, "gender": "unknown"}).status_code in (201, 409)
v = {"respiratory_rate": 16, "oxygen_saturation": 97, "supplemental_oxygen": False, "systolic_bp": 120, "heart_rate": 70, "consciousness": "A", "temperature": 36.8}
assert c.post("/api/v1/triage/evaluate", json={"patient_id": "PRIV-1", "vitals": v}).status_code == 201
print("flujo de la app con tb_app: OK")
for sql in ("UPDATE audit_logs SET event_type='x'", "DELETE FROM audit_logs", "UPDATE triage_evaluations SET total_score=0", "DELETE FROM triage_evaluations", "DROP TABLE users"):
    with SessionLocal() as s:
        try: s.execute(text(sql)); s.commit(); print("PERMITIDO (MAL):", sql)
        except ProgrammingError as e: print("denegado (bien):", sql, "|", str(e.orig).splitlines()[0][:60])
