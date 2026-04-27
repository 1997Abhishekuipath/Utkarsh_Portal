-- ─────────────────────────────────────────────────────────────────────────────
--  HSI Employee Engagement Platform — PostgreSQL Initialisation Script
--  Runs once when the DB container is first created (docker-entrypoint-initdb.d)
--  Reference: HSI-PRD-EEP-2026-v1.0 §3.1 and §3.2
--  Sprint F: SCRAM-SHA-256 enforced via --auth-host=scram-sha-256 initdb flag.
-- ─────────────────────────────────────────────────────────────────────────────

-- NOTE: PostgreSQL 16 with --auth-host=scram-sha-256 stores all passwords as
-- SCRAM-SHA-256 hashes. Change the default passwords below before production.

-- ── Create application roles (least-privilege per PRD §3.1) ──────────────────

DO $$
BEGIN
    -- hsi_api  — runtime API user (SELECT / INSERT / UPDATE only)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsi_api') THEN
        CREATE ROLE hsi_api WITH LOGIN PASSWORD 'hsi_api_password_change_me';
    END IF;

    -- hsi_admin — admin console user (also DELETE, cannot change schema)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsi_admin') THEN
        CREATE ROLE hsi_admin WITH LOGIN PASSWORD 'hsi_admin_password_change_me';
    END IF;

    -- hsi_readonly — read-only for analytics / BI / reporting
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsi_readonly') THEN
        CREATE ROLE hsi_readonly WITH LOGIN PASSWORD 'hsi_readonly_password_change_me';
    END IF;

    -- hsi_migrate — full DDL access; used only by CI/CD migrations, never at runtime
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hsi_migrate') THEN
        CREATE ROLE hsi_migrate WITH LOGIN PASSWORD 'hsi_migrate_password_change_me';
    END IF;
END $$;

-- ── Create application schema ─────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS app AUTHORIZATION hsi_migrate;

-- ── Grant schema USAGE to runtime roles ──────────────────────────────────────
GRANT USAGE ON SCHEMA app TO hsi_api, hsi_admin, hsi_readonly;

-- ── Default privileges for future tables created by hsi_migrate ──────────────
-- hsi_api: read / write (no delete)
ALTER DEFAULT PRIVILEGES FOR ROLE hsi_migrate IN SCHEMA app
    GRANT SELECT, INSERT, UPDATE ON TABLES TO hsi_api;

-- hsi_admin: read / write / delete (no schema changes)
ALTER DEFAULT PRIVILEGES FOR ROLE hsi_migrate IN SCHEMA app
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hsi_admin;

-- hsi_readonly: read only (analytics, BI tools)
ALTER DEFAULT PRIVILEGES FOR ROLE hsi_migrate IN SCHEMA app
    GRANT SELECT ON TABLES TO hsi_readonly;

-- Sequences (needed for SERIAL / BIGSERIAL columns)
ALTER DEFAULT PRIVILEGES FOR ROLE hsi_migrate IN SCHEMA app
    GRANT USAGE, SELECT ON SEQUENCES TO hsi_api, hsi_admin;

-- ── Grant connection to database ─────────────────────────────────────────────
GRANT CONNECT ON DATABASE hsi_portal TO hsi_api, hsi_admin, hsi_readonly, hsi_migrate;

-- ── Sprint G: grant privileges on EXISTING tables too (app bootstrap) ───────
-- Because tables are created by the POSTGRES_USER superuser via SQLAlchemy
-- create_all(), grant runtime roles the appropriate access on the public schema
-- so hsi_api (used by the backend in prod) can actually read/write.
GRANT USAGE ON SCHEMA public TO hsi_api, hsi_admin, hsi_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO hsi_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hsi_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO hsi_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO hsi_api, hsi_admin;

-- ── pgBouncer auth support ────────────────────────────────────────────────────
-- Creates the function used by pgBouncer's auth_query when auth_type=scram-sha-256.
-- Requires the pgbouncer user to have EXECUTE rights.
CREATE OR REPLACE FUNCTION public.get_auth(p_usename TEXT)
    RETURNS TABLE(username TEXT, password TEXT) AS $$
    SELECT rolname::TEXT, rolpassword::TEXT
    FROM pg_authid
    WHERE rolname = p_usename;
$$ LANGUAGE sql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.get_auth(TEXT) TO hsi_api;

-- ── Informational comment ─────────────────────────────────────────────────────
COMMENT ON SCHEMA app IS 'HSI Employee Engagement Platform — application schema (PRD §3.2)';
