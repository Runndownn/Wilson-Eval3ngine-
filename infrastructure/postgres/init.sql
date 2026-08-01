-- PostgreSQL initialization for Wilson Eval3ngine
-- Creates the we3 database, user, and initial schema extensions

-- Extensions required for production
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- RLS is enabled per-table in the application migrations
-- This file is sourced after the database is created by the Docker entrypoint

-- Create read-only user for monitoring
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'we3_monitor') THEN
        CREATE ROLE we3_monitor WITH LOGIN PASSWORD 'monitor_password';
        GRANT CONNECT ON DATABASE we3 TO we3_monitor;
        GRANT USAGE ON SCHEMA public TO we3_monitor;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO we3_monitor;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO we3_monitor;
    END IF;
END
$$;
