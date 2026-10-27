-- Rol de aplicación con MÍNIMO privilegio. Ejecutar como superusuario DESPUÉS de `alembic upgrade head`:
--   psql -d <bd> -v db=<bd> -v app_password="'<clave>'" -f scripts/pg_roles.sql   (usar -d <bd>: los GRANT se aplican a la BD conectada)
-- Las migraciones se ejecutan con otro rol (propietario). La app nunca hace DDL, ni DELETE, ni UPDATE de evaluaciones/auditoría.
CREATE ROLE tb_app LOGIN PASSWORD :app_password;
GRANT CONNECT ON DATABASE :"db" TO tb_app;
GRANT USAGE ON SCHEMA public TO tb_app;
GRANT SELECT, INSERT, UPDATE ON users TO tb_app;          -- UPDATE: contador de intentos y versión de sesión
GRANT SELECT, INSERT ON patients, triage_evaluations, audit_logs TO tb_app;
