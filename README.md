# Thinker Bell v0.4 (desarrollo)

Apoyo a la evaluación NEWS2 con historial y auditoría. **Solo datos sintéticos. Reglas NEWS2 PENDIENTES DE VALIDACIÓN CLÍNICA. No es diagnóstico, dispositivo médico autorizado ni sistema listo para uso clínico.** Sin IA y sin integración FHIR funcional (ver `docs/ROADMAP_FHIR_AI.md`).

## Requisitos
Python 3.12, Node 20+, PostgreSQL 16 (o Docker). SQLite sirve para desarrollo rápido.

## Instalación y ejecución
```bash
# 1) Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && export $(grep -v '^#' .env | grep -v '^$' | cut -d' ' -f1 | xargs)   # o exporta las variables a mano
python3 -c "import secrets;print(secrets.token_urlsafe(48))"      # úsalo como JWT_SECRET

# 2) PostgreSQL — opción A: Docker (no probado en mi entorno)
export POSTGRES_PASSWORD=<elige> && docker compose up -d db
export DATABASE_URL=postgresql+psycopg://thinkerbell:$POSTGRES_PASSWORD@localhost:5432/thinkerbell
# opción B: PostgreSQL local (probado con 16.15)
sudo -u postgres psql -c "create user tb with password '<clave>'" -c "create database tb_dev owner tb" -c "create database tb_test owner tb"
export DATABASE_URL=postgresql+psycopg://tb:<clave>@localhost:5432/tb_dev
# opción C: SQLite   export DATABASE_URL=sqlite:///./thinkerbell_dev.db

# 3) Migraciones y primer administrador
alembic upgrade head
python -m backend.app.cli create-admin --username <nombre>   # pide contraseña ≥12 sin eco (o TB_ADMIN_PASSWORD); se niega si ya hay un admin
# 4) Arranque
uvicorn backend.app.main:app --port 8000                      # OpenAPI: http://localhost:8000/docs
cd frontend && npm install && npm run dev                     # http://localhost:5173 (proxy /api → :8000)
```
Los demás usuarios los crea el admin con `POST /api/v1/auth/users` (roles `clinician`, `auditor`, `admin`). La interfaz aún no tiene pantalla de gestión de usuarios.

## Pruebas
```bash
pytest                                                                   # SQLite en memoria
TEST_DATABASE_URL=postgresql+psycopg://tb:<clave>@localhost:5432/tb_test pytest   # PostgreSQL real (incluye prueba de concurrencia)
cd frontend && npm run build                                             # tsc estricto + build de producción
```

## Copias de seguridad, restauración y mínimo privilegio (PostgreSQL)
```bash
PG_URL=postgresql://usuario:clave@host/bd scripts/backup.sh /ruta/copia.dump          # genera .dump + .sha256 (contiene datos personales: cifrar y guardar fuera del servidor)
PG_URL=postgresql://usuario:clave@host/bd_VACIA scripts/restore_check.sh /ruta/copia.dump   # restaura en BD vacía y verifica conteos + cadena de auditoría
psql -d <bd> -v db=<bd> -v app_password="'<clave>'" -f scripts/pg_roles.sql            # rol tb_app de mínimo privilegio (tras alembic upgrade); usar su URL en DATABASE_URL de la app
PYTHONPATH=. DATABASE_URL=<url tb_app> VERIFY_USER=<clínico> VERIFY_PASSWORD=<clave> python scripts/verify_least_privilege.py
```
Las migraciones se ejecutan con el rol propietario, nunca con `tb_app`.

## Variables de entorno
`DATABASE_URL`, `JWT_SECRET`, `APP_ENV` (`production` exige secreto ≥32 y `COOKIE_SECURE=true`, y desactiva /docs), `COOKIE_SECURE`, `SESSION_MINUTES`, `LOGIN_MAX_FAILS`, `LOGIN_LOCK_MINUTES`, `CORS_ORIGINS`, `AUTO_CREATE_TABLES` (solo desarrollo), `POSTGRES_PASSWORD`, `TEST_DATABASE_URL`, `TB_ADMIN_PASSWORD`.

## Estado
| Función | Estado |
|---|---|
| Auth, roles, CSRF, bloqueo de cuenta, revocación de sesión | Implementado y probado (SQLite y PostgreSQL) |
| Pacientes (auditor sin nombre/edad), evaluación, historial, panel, auditoría verificable, desactivación de usuarios | Implementado y probado |
| Copia/restauración, rol de mínimo privilegio | Probados localmente con datos sintéticos |
| NEWS2 v2.0.0-dev | Contrastado con la RCP 2017 (`docs/NEWS2_VERIFICATION.md`); **pendiente de validación clínica** |
| Frontend (6 secciones, menú móvil) | Build OK; revisado en Chromium a 390/768/1024/1440 px; axe-core 0 violaciones; **sin pruebas automatizadas de componentes** |
| Migraciones Alembic | Probadas (upgrade/downgrade/upgrade) en PostgreSQL 16 y SQLite |
| Docker Compose | **No ejecutado** |
| FHIR / IA | **No implementado** (adaptador heredado sin conectar) |

## Limitaciones pendientes
Sin MFA ni recuperación de contraseña; sin gestión de usuarios en la UI; sin detalle de evaluación en la UI; gráficos simples (sin anillo ni líneas de tendencia de la referencia); sin cifrado de datos en reposo ni del volcado; copias sin automatizar; sin `pip-audit`/`npm audit`; sin límite por IP; sin revisión legal para Colombia; embarazo y lesión medular no modelados; sin recomendaciones de frecuencia de monitorización. Informe completo: `docs/TECHNICAL_REPORT.md`; seguridad: `docs/SECURITY_REVIEW.md`.

## Pasos de despliegue (checklist; no se ha desplegado nada)
1. Revisión clínica y legal completada y documentada.
2. Proxy inverso con TLS, HSTS, CSP y límite de peticiones por IP; servir `frontend/dist` desde el mismo origen que `/api`.
3. `APP_ENV=production`, `JWT_SECRET` y contraseñas desde un gestor de secretos; `COOKIE_SECURE=true`; `AUTO_CREATE_TABLES=false`.
4. PostgreSQL gestionado con cifrado en reposo; rol de migración distinto del rol de la aplicación; `REVOKE UPDATE, DELETE ON audit_logs` para el rol de la aplicación.
5. `alembic upgrade head`; crear el primer admin con el CLI; rotar cualquier credencial de prueba.
6. Copias de seguridad automáticas y **restauración probada**; monitoreo y alertas; verificación periódica de `/api/v1/audit/verify`.
