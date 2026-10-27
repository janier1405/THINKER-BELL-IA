import os, subprocess, sys
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from backend.app.db.models import AuditLog, User
from backend.app.main import app
from tests.conftest import PW, login_as

P = {"patient_id": "SYN-9", "full_name": "Sintético", "age": 40, "gender": "unknown"}

def test_csrf_required_on_unsafe_methods(env):
    c = TestClient(app)
    assert c.post("/api/v1/auth/login", json={"username": "clin1", "password": PW}).status_code == 200
    assert c.get("/api/v1/patients").status_code == 200                       # GET no exige token
    assert c.post("/api/v1/patients", json=P).status_code == 403              # sin cabecera
    assert c.post("/api/v1/patients", json=P, headers={"X-CSRF-Token": "falso"}).status_code == 403
    assert c.post("/api/v1/patients", json=P, headers={"X-CSRF-Token": c.cookies.get("tb_csrf")}).status_code == 201

def test_csrf_token_bound_to_session(env):
    a, b = login_as(env, "clin1"), login_as(env, "admin1")
    a.headers["X-CSRF-Token"] = b.cookies.get("tb_csrf")                      # token de OTRA sesión
    assert a.post("/api/v1/patients", json=P).status_code == 403

def test_lockout_and_audit(env):
    c, S = env
    for _ in range(5): assert c.post("/api/v1/auth/login", json={"username": "clin1", "password": "mala"}).status_code == 401
    assert c.post("/api/v1/auth/login", json={"username": "clin1", "password": PW}).status_code == 401   # correcta pero bloqueada
    with S() as s:
        assert s.execute(select(User).where(User.username == "clin1")).scalar_one().locked_until is not None
        assert "account_locked" in [a.event_type for a in s.execute(select(AuditLog)).scalars()]
        s.execute(update(User).where(User.username == "clin1").values(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1))); s.commit()
    assert c.post("/api/v1/auth/login", json={"username": "clin1", "password": PW}).status_code == 200  # expiró el bloqueo
    assert c.post("/api/v1/auth/login", json={"username": "nadie", "password": "x"}).json() == {"detail": "Credenciales inválidas o cuenta bloqueada temporalmente."}
    assert login_as(env, "aud1").get("/api/v1/audit/verify").json()["valid"] is True

def test_logout_revokes_session(env):
    c = login_as(env, "clin1"); old = c.cookies.get("tb_session")
    assert c.post("/api/v1/auth/logout").status_code == 204
    r = TestClient(app); r.cookies.set("tb_session", old)
    assert r.get("/api/v1/auth/me").status_code == 401                        # el token antiguo ya no sirve

def test_news2_age_guard(env):
    c = login_as(env, "clin1")
    c.post("/api/v1/patients", json={**P, "age": 15})
    v = {"respiratory_rate": 16, "oxygen_saturation": 97, "supplemental_oxygen": False, "systolic_bp": 120, "heart_rate": 70, "consciousness": "A", "temperature": 36.8}
    assert c.post("/api/v1/triage/evaluate", json={"patient_id": "SYN-9", "vitals": v}).status_code == 422

def test_headers_and_generic_404(env):
    c, _ = env; r = c.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert login_as(env, "clin1").get("/api/v1/patients").headers["cache-control"] == "no-store"

def test_production_fails_fast_with_insecure_config():
    env = {**os.environ, "APP_ENV": "production", "JWT_SECRET": "", "COOKIE_SECURE": "false"}
    r = subprocess.run([sys.executable, "-c", "import backend.app.core.security"], env=env, capture_output=True, text=True)
    assert r.returncode != 0 and "JWT_SECRET" in r.stderr
    env.update(JWT_SECRET="x" * 40, COOKIE_SECURE="true")
    assert subprocess.run([sys.executable, "-c", "import backend.app.core.security"], env=env).returncode == 0

import pytest
from concurrent.futures import ThreadPoolExecutor
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Requiere PostgreSQL (TEST_DATABASE_URL)")
def test_audit_concurrency_postgres(env):
    from backend.app.services.audit import append_audit, verify_chain
    _, S = env
    with S() as s: uid = s.execute(select(User)).scalars().first().id
    def w(i):
        with S() as s: append_audit(s, event_type="carga", actor_id=uid, summary={"i": i}); s.commit()
    with ThreadPoolExecutor(20) as ex: list(ex.map(w, range(20)))
    with S() as s: assert verify_chain(s) == (True, None)
