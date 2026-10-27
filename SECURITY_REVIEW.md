# Revisión de seguridad (v0.4; ver también TECHNICAL_REPORT.md). NO es una certificación ni una auditoría independiente.

## Controles implementados y verificados con pruebas
| Control | Implementación | Verificación |
|---|---|---|
| Contraseñas | argon2id; mínimo 12 caracteres | test_login |
| Sesión | JWT en cookie `httpOnly`, `SameSite=Lax`, `Secure` configurable, caducidad (60 min por defecto) | test_login / test_logout |
| Revocación | `session_version` por usuario; el logout invalida todas las sesiones | test_logout_revokes_session |
| CSRF | Token aleatorio firmado dentro del JWT + cookie legible + cabecera `X-CSRF-Token` obligatoria en POST; comparación en tiempo constante | test_csrf_* (incl. token de otra sesión) |
| Fuerza bruta | Bloqueo de cuenta tras 5 fallos (15 min), mensaje único que no revela si el usuario existe, verificación siempre ejecutada | test_lockout_and_audit |
| Autorización | Roles verificados en backend; rol leído de la BD en cada petición | test_roles |
| Auditoría | Cadena de hashes con `seq` único; verificador; eventos de login, bloqueo, logout, alta de usuario/paciente y evaluación | test_full_flow_and_audit |
| Concurrencia de auditoría | `pg_advisory_xact_lock`. Se encontró y corrigió un fallo real (8 de 20 escrituras perdidas con `FOR UPDATE`) | 40/40 correctas en PostgreSQL; test_audit_concurrency_postgres |
| Configuración de producción | `APP_ENV=production` exige `JWT_SECRET` ≥32 y `COOKIE_SECURE=true`; desactiva /docs | test_production_fails_fast |
| Cabeceras / errores | nosniff, X-Frame-Options, no-referrer, `no-store` en /api; error 500 genérico y log sin datos clínicos | test_headers |
| Minimización por rol | El auditor no recibe nombre ni edad; búsqueda solo por ID | test_privacy |
| Mínimo privilegio en BD | `scripts/pg_roles.sql`: la app no puede UPDATE/DELETE auditoría ni evaluaciones, ni hacer DDL | `scripts/verify_least_privilege.py` (PostgreSQL local) |
| Baja de usuarios | Desactivación con corte inmediato de sesiones | test_deactivate_user_* |
| Copias | `backup.sh` con SHA-256; `restore_check.sh` verifica conteos y cadena de auditoría | Ejecutado localmente; volcado alterado rechazado |
| Integridad de datos | Validación Pydantic; ID de paciente restringido; evaluar no sobrescribe pacientes | test_validation_errors |

## Riesgos pendientes (no resueltos)
- Sin MFA, sin cambio/recuperación de contraseña y sin política de rotación.
- Bloqueo solo por cuenta: permite denegación de servicio dirigida a un usuario conocido; falta límite por IP (hacerlo en el proxy inverso).
- JWT stateless de HS256 con secreto compartido; sin rotación de claves.
- HSTS, CSP y TLS no los aplica la app: requieren proxy inverso/CDN. Sin ellos `COOKIE_SECURE` no funciona.
- Nombres de pacientes en claro en la BD: falta cifrado en reposo y decidir si el nombre es necesario (ver TECHNICAL_REPORT §4).
- La cadena de hashes detecta manipulación casual; no protege contra un administrador de BD con control total. Falta anclaje externo de los hashes. El rol de mínimo privilegio ya está disponible, pero debe adoptarse en el despliegue real.
- Sin escaneo de dependencias (`pip-audit`, `npm audit`) **no ejecutado**; sin SAST/DAST.
- Copias: scripts probados en local, pero sin cifrado del volcado, sin automatización, sin RPO/RTO definidos y sin prueba en la infraestructura destino; sin retención de datos definida; sin monitoreo/alertas.
- Sin revisión legal (Ley 1581 de 2012 y normas de historia clínica/interoperabilidad: base de tratamiento, autorización, finalidad, transferencias, registro de bases de datos) ni evaluación de si aplica regulación de dispositivos médicos.
