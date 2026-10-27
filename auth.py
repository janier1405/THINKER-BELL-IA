import hmac, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.core.security import COOKIE, CSRF_COOKIE, SESSION_MINUTES, hash_password, make_token, read_token, verify_password
from backend.app.db.models import User
from backend.app.db.session import get_db
from backend.app.schemas.triage import LoginIn, UserCreate
from backend.app.services.audit import append_audit

router = APIRouter(prefix="/auth", tags=["Auth"])
MAX_FAILS = int(os.getenv("LOGIN_MAX_FAILS", "5")); LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
SAFE = ("GET", "HEAD", "OPTIONS")
_aware = lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    tok = request.cookies.get(COOKIE); data = read_token(tok) if tok else None
    user = db.get(User, data["sub"]) if data else None
    # el rol y la versión de sesión se leen SIEMPRE de la BD, no del token
    if user is None or not user.is_active or data.get("v") != user.session_version: raise HTTPException(401, "No autenticado.")
    if request.method not in SAFE:  # CSRF: el token va ligado a la sesión (claim firmado) y debe repetirse en cabecera
        h = request.headers.get("x-csrf-token")
        if not h or not hmac.compare_digest(h, str(data.get("csrf", ""))): raise HTTPException(403, "Token CSRF ausente o inválido.")
    return user

def require_roles(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles: raise HTTPException(403, "Permiso insuficiente.")
        return user
    return dep

def _cookie_kw(): return dict(samesite="lax", max_age=SESSION_MINUTES * 60, secure=os.getenv("COOKIE_SECURE", "false").lower() == "true")

@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    locked = bool(user and user.locked_until and _aware(user.locked_until) > now)
    ok = verify_password(user.password_hash if user else None, body.password)  # siempre se verifica (tiempo constante aprox.)
    if locked or not (ok and user and user.is_active):
        if user and not locked:
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILS:
                user.locked_until, user.failed_attempts = now + timedelta(minutes=LOCK_MINUTES), 0
                append_audit(db, event_type="account_locked", actor_id=user.id)
            else: append_audit(db, event_type="login_failed", actor_id=user.id)
            db.commit()
        raise HTTPException(401, "Credenciales inválidas o cuenta bloqueada temporalmente.")  # mensaje único: no revela si existe
    user.failed_attempts, user.locked_until = 0, None
    append_audit(db, event_type="login_success", actor_id=user.id); db.commit()
    csrf = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE, make_token(user.id, user.session_version, csrf), httponly=True, **_cookie_kw())
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **_cookie_kw())  # legible por JS a propósito (patrón double-submit)
    return {"username": user.username, "role": user.role}

@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    tok = request.cookies.get(COOKIE); data = read_token(tok) if tok else None
    user = db.get(User, data["sub"]) if data else None
    if user and data.get("v") == user.session_version:
        user.session_version += 1  # revoca TODAS las sesiones emitidas; cerrar sesión es inocuo ante CSRF
        append_audit(db, event_type="logout", actor_id=user.id); db.commit()
    response.delete_cookie(COOKIE); response.delete_cookie(CSRF_COOKIE)

@router.get("/me")
def me(user: User = Depends(current_user)): return {"username": user.username, "role": user.role}

@router.post("/users", status_code=201)
def create_user(body: UserCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    user = User(username=body.username, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    try:
        db.flush(); append_audit(db, event_type="user_created", actor_id=admin.id, summary={"username": body.username, "role": body.role}); db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "El usuario ya existe.")
    return {"username": user.username, "role": user.role}

@router.post("/users/{username}/deactivate", status_code=204)
def deactivate_user(username: str, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    u = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if not u: raise HTTPException(404, "Usuario no encontrado.")
    if u.id == admin.id: raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
    u.is_active, u.session_version = False, u.session_version + 1  # corta sesiones vigentes
    append_audit(db, event_type="user_deactivated", actor_id=admin.id, summary={"username": username}); db.commit()
