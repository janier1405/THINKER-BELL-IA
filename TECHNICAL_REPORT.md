# Informe técnico v0.4 — implementado / probado / pendiente
Fecha de verificación: 2026-10-26. Entorno: Linux, Python 3.12.3, Node 20+, PostgreSQL 16.15 local, Chromium (Playwright). **Solo datos sintéticos. No se desplegó nada.** NEWS2 sigue **PENDIENTE DE VALIDACIÓN CLÍNICA**.

## 1. Resultados de las verificaciones ejecutadas
| # | Verificación | Comando / método | Resultado observado |
|---|---|---|---|
| 1 | Suite, SQLite en memoria | `pytest` | 79 aprobadas, 1 omitida (concurrencia: exige PostgreSQL), 0 fallidas |
| 2 | Suite, PostgreSQL real | `TEST_DATABASE_URL=… pytest` | **80 aprobadas**, 0 omitidas, 0 fallidas; incluye `test_audit_concurrency_postgres` (20 hilos) |
| 3 | Concurrencia (sesión anterior, misma lógica) | 40 hilos, sin reintentos | 40/40 correctas, cadena válida |
| 4 | Migraciones desde BD vacía | `alembic upgrade head` (BD `tb_fresh`) | 2 migraciones aplicadas. Upgrade/downgrade/upgrade probados antes |
| 5 | Copia de seguridad | `scripts/backup.sh` sobre `tb_dev` | Volcado + SHA-256 generados |
| 6 | Restauración | `scripts/restore_check.sh` en BD vacía | Conteos idénticos (users 3, patients 6, evaluaciones 16, auditoría 87); cadena de auditoría válida |
| 7 | Restauración con volcado alterado | un byte añadido | **Rechazado** por la suma SHA-256 |
| 8 | Mínimo privilegio | rol `tb_app` + `scripts/verify_least_privilege.py` | Flujo de la app OK; UPDATE/DELETE sobre `audit_logs` y `triage_evaluations` y `DROP TABLE` **denegados** |
| 9 | Build de producción | `npm run build` (tsc estricto + Vite) | OK: JS 156,97 kB (50,48 kB gzip), CSS 4,62 kB |
| 10 | Responsive en Chromium | 390, 768, 1024, 1440 px; 6 secciones | Sin desbordamiento horizontal; menú móvil abre/cierra y se cierra al elegir sección (`aria-expanded`) |
| 11 | Accesibilidad automática | axe-core WCAG 2.0/2.1 A/AA | 0 violaciones (vista final de cada tamaño + vista de auditor). **No sustituye una auditoría manual** (lector de pantalla, teclado completo) |

Las 69 pruebas originales siguen pasando; se añadieron 11 (3 de privacidad, 7 de seguridad previas y 1 de concurrencia contados en la suite: total 80).

## 2. Defectos encontrados y corregidos en esta fase
- La barra superior móvil se estiraba (~180 px) con contenido corto → corregido (55,6 px).
- Navegación móvil: era una fila de botones que ocupaba media pantalla → menú colapsable accesible.
- La búsqueda de pacientes por nombre enviaba datos personales en la URL (acabarían en logs de acceso) → ahora solo por identificador.
- `pg_roles.sql` y mi script de prueba tuvieron errores de uso (BD equivocada / ruta); corregidos y verificados.

## 3. Implementado (código) y estado de prueba
| Capacidad | Implementado | Probado |
|---|---|---|
| Auth (argon2id), roles, CSRF ligado a sesión, bloqueo de cuenta, revocación | Sí | Sí (SQLite y PostgreSQL) |
| Desactivación de usuarios (corta sesiones) | Sí | Sí |
| Minimización: el auditor ve ID/sexo/fecha, sin nombre ni edad | Sí | Sí (tests + UI en navegador) |
| Auditoría encadenada con verificador y bloqueo consultivo | Sí | Sí (PostgreSQL, concurrencia) |
| Copia/restauración con verificación de integridad | Scripts | Sí (local, datos sintéticos) |
| Rol de BD de mínimo privilegio | `scripts/pg_roles.sql` | Sí (PostgreSQL local) |
| Frontend 6 secciones, menú móvil | Sí | Build + navegador + axe. **Sin pruebas automatizadas de componentes** |
| NEWS2 v2.0.0-dev | Sí | Unitarias de todos los límites; **sin validación clínica** |
| FHIR | Adaptador heredado | **No conectado ni validado** |
| IA/ML | **No existe** | — |

## 4. Privacidad y datos (prioridades)
**Inventario:** nombre, edad, sexo e ID del paciente; signos vitales; usuario que evalúa; eventos de auditoría (sin nombres).
1. *Minimización (hecho parcial):* auditor sin nombre/edad; nombres fuera de URLs y de logs. **Pendiente de decisión del producto:** ¿hace falta almacenar el nombre? La opción más fuerte es usar solo un identificador seudónimo y mantener el nombre en el sistema clínico de origen.
2. *Cifrado en reposo:* no implementado (depende de la infraestructura: disco/BD gestionada; cifrado a nivel de columna opcional).
3. *Retención:* no definida; la app no borra nada (el rol de mínimo privilegio tampoco puede). Hace falta política y procedimiento de supresión/anonimización aprobado legalmente, compatible con la auditoría.
4. *Copias:* el volcado contiene datos personales: **cifrar y guardar fuera del servidor** (no implementado en el script), restringir acceso, definir retención y repetir la prueba de restauración de forma periódica. RPO/RTO no definidos.
5. *Recuperación:* procedimiento probado solo en local (restore a BD vacía + verificación). Falta probarlo con el volumen real, en la infraestructura destino y con el proceso de conmutación.

## 5. Pendiente (no verificado ni resuelto)
MFA; cambio/recuperación de contraseña; límite de peticiones por IP; HSTS/CSP/TLS (proxy); `pip-audit` y `npm audit` (no ejecutados); pruebas de componentes y accesibilidad manual; gestión de usuarios en la UI; detalle de evaluación; gráficos de tendencia de la referencia; Docker Compose (no ejecutado); revisión legal (Ley 1581/2012, historia clínica, interoperabilidad, posible regulación de dispositivos médicos); validación clínica de NEWS2; embarazo y lesión medular no modelados; FHIR e IA (ver `ROADMAP_FHIR_AI.md`).
