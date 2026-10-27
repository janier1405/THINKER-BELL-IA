"""Crea el primer administrador: python -m backend.app.cli create-admin --username NOMBRE
La contraseña se pide por consola (sin eco) o se lee de TB_ADMIN_PASSWORD. Se niega si ya existe un admin."""
import argparse, getpass, os, sys
from sqlalchemy import select
from backend.app.core.security import hash_password
from backend.app.db.models import User
from backend.app.db.session import SessionLocal

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["create-admin"]); ap.add_argument("--username", required=True)
    a = ap.parse_args()
    pw = os.getenv("TB_ADMIN_PASSWORD") or getpass.getpass("Contraseña (mín. 12 caracteres): ")
    if len(pw) < 12: print("La contraseña debe tener al menos 12 caracteres."); return 1
    with SessionLocal() as db:
        if db.execute(select(User).where(User.role == "admin")).first(): print("Ya existe un administrador."); return 1
        db.add(User(username=a.username, password_hash=hash_password(pw), role="admin")); db.commit()
    print("Administrador creado."); return 0

if __name__ == "__main__": sys.exit(main())
