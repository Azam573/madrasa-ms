"""
db.py — Database connection and schema initialization for Smart Madrasa ERP.
Uses psycopg2 with Supabase PostgreSQL. No ORM.
"""

import os
import psycopg2
import psycopg2.extras
import streamlit as st

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Return a psycopg2 connection using environment variables or Streamlit secrets."""
    try:
        dsn = (
            st.secrets.get("DATABASE_URL")
            if hasattr(st, "secrets") and "DATABASE_URL" in st.secrets
            else os.environ.get("DATABASE_URL")
        )
        if dsn:
            conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            conn = psycopg2.connect(
                host=_cfg("DB_HOST", "localhost"),
                port=_cfg("DB_PORT", "5432"),
                dbname=_cfg("DB_NAME", "madrasa_erp"),
                user=_cfg("DB_USER", "postgres"),
                password=_cfg("DB_PASSWORD", ""),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
        conn.autocommit = False
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None


def _cfg(key, default=""):
    """Helper to read from st.secrets then env."""
    if hasattr(st, "secrets") and key in st.secrets:
        return st.secrets[key]
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Schema Bootstrap
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Multi-tenant root
CREATE TABLE IF NOT EXISTS tenants (
    id               SERIAL PRIMARY KEY,
    madrasa_name     TEXT NOT NULL,
    slug             TEXT UNIQUE,
    address          TEXT,
    phone            TEXT,
    email            TEXT,
    logo_url         TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Seed a default tenant for demo
INSERT INTO tenants (madrasa_name, slug)
VALUES ('Demo Madrasa', 'demo')
ON CONFLICT (slug) DO NOTHING;

-- Academic sessions
CREATE TABLE IF NOT EXISTS academic_sessions (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_name TEXT NOT NULL,
    is_active    BOOLEAN DEFAULT FALSE,
    start_date   DATE,
    end_date     DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, session_name)
);

-- Classes
CREATE TABLE IF NOT EXISTS classes (
    id             SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_name     TEXT NOT NULL,
    class_numeric  INTEGER,
    section        TEXT DEFAULT 'A',
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, class_name, section)
);

-- Students master record
CREATE TABLE IF NOT EXISTS students (
    id               SERIAL PRIMARY KEY,
    tenant_id        INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    father_name      TEXT,
    mother_name      TEXT,
    mobile_no        TEXT,
    present_address  TEXT,
    permanent_address TEXT,
    date_of_birth    DATE,
    gender           TEXT DEFAULT 'Male',
    photo            TEXT,          -- URL or base64
    nid_no           TEXT,
    blood_group      TEXT,
    status           TEXT DEFAULT 'pending',  -- pending | active | inactive | graduated
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Student enrollments (session + class mapping)
CREATE TABLE IF NOT EXISTS student_enrollments (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    student_id        INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    session_id        INTEGER NOT NULL REFERENCES academic_sessions(id) ON DELETE CASCADE,
    class_id          INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    roll_no           INTEGER,
    monthly_fee       NUMERIC(10,2) DEFAULT 0,
    enrollment_status TEXT DEFAULT 'pending',   -- pending | active | dropped | completed
    enrolled_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, student_id, session_id)
);

-- Fee vouchers
CREATE TABLE IF NOT EXISTS fee_vouchers (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    enrollment_id   INTEGER REFERENCES student_enrollments(id) ON DELETE SET NULL,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    voucher_no      TEXT UNIQUE,
    issue_date      DATE DEFAULT CURRENT_DATE,
    due_date        DATE,
    month_name      TEXT,
    year            INTEGER,
    amount          NUMERIC(10,2) NOT NULL,
    fund_type       TEXT DEFAULT 'general',   -- general | zakat | lillah_boarding
    status          TEXT DEFAULT 'unpaid',    -- unpaid | paid | partial | waived
    paid_at         TIMESTAMPTZ,
    collected_by    TEXT,
    remarks         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Fee payments
CREATE TABLE IF NOT EXISTS fee_payments (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    voucher_id      INTEGER NOT NULL REFERENCES fee_vouchers(id) ON DELETE CASCADE,
    amount_paid     NUMERIC(10,2) NOT NULL,
    payment_date    DATE DEFAULT CURRENT_DATE,
    payment_method  TEXT DEFAULT 'cash',
    receipt_no      TEXT,
    collected_by    TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Subjects
CREATE TABLE IF NOT EXISTS subjects (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    class_id    INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    subject_name TEXT NOT NULL,
    subject_code TEXT,
    full_marks   INTEGER DEFAULT 100,
    pass_marks   INTEGER DEFAULT 33,
    is_optional  BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Exams
CREATE TABLE IF NOT EXISTS exams (
    id           SERIAL PRIMARY KEY,
    tenant_id    INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id   INTEGER REFERENCES academic_sessions(id) ON DELETE CASCADE,
    exam_name    TEXT NOT NULL,
    exam_date    DATE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Marks distribution config per exam+subject
CREATE TABLE IF NOT EXISTS marks_distribution (
    id             SERIAL PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    exam_id        INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    subject_id     INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    written_marks  INTEGER DEFAULT 80,
    mcq_marks      INTEGER DEFAULT 10,
    practical_marks INTEGER DEFAULT 10,
    UNIQUE(exam_id, subject_id)
);

-- Student marks
CREATE TABLE IF NOT EXISTS student_marks (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    enrollment_id   INTEGER NOT NULL REFERENCES student_enrollments(id) ON DELETE CASCADE,
    exam_id         INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    subject_id      INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    written_obtained INTEGER DEFAULT 0,
    mcq_obtained    INTEGER DEFAULT 0,
    practical_obtained INTEGER DEFAULT 0,
    total_obtained  INTEGER GENERATED ALWAYS AS (written_obtained + mcq_obtained + practical_obtained) STORED,
    is_absent       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(enrollment_id, exam_id, subject_id)
);

-- Attendance
CREATE TABLE IF NOT EXISTS attendance (
    id            SERIAL PRIMARY KEY,
    tenant_id     INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    enrollment_id INTEGER NOT NULL REFERENCES student_enrollments(id) ON DELETE CASCADE,
    date          DATE NOT NULL,
    status        TEXT DEFAULT 'present',  -- present | absent | late | holiday
    UNIQUE(enrollment_id, date)
);

-- App users (staff login)
CREATE TABLE IF NOT EXISTS app_users (
    id          SERIAL PRIMARY KEY,
    tenant_id   INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username    TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role        TEXT DEFAULT 'staff',   -- admin | staff | teacher | accountant
    full_name   TEXT,
    email       TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, username)
);

-- Seed demo admin (password: admin123 — bcrypt hash placeholder for demo)
INSERT INTO app_users (tenant_id, username, password_hash, role, full_name)
SELECT 1, 'admin', 'demo_hash_admin123', 'admin', 'System Administrator'
WHERE NOT EXISTS (SELECT 1 FROM app_users WHERE tenant_id=1 AND username='admin');

-- Seed demo session
INSERT INTO academic_sessions (tenant_id, session_name, is_active, start_date, end_date)
VALUES (1, '2024-2025', TRUE, '2024-01-01', '2025-12-31')
ON CONFLICT (tenant_id, session_name) DO NOTHING;

-- Seed classes
INSERT INTO classes (tenant_id, class_name, class_numeric) VALUES
(1, 'Hifz-1',   1),
(1, 'Hifz-2',   2),
(1, 'Hifz-3',   3),
(1, 'Nazera-1', 4),
(1, 'Nazera-2', 5),
(1, 'Ibtedaee', 6),
(1, 'Mutawassit',7),
(1, 'Thanawi',  8)
ON CONFLICT (tenant_id, class_name, section) DO NOTHING;
"""


def bootstrap_schema():
    """Create all tables if they don't exist. Safe to run repeatedly."""
    conn = get_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Schema bootstrap failed: {e}")
        return False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def fetchall(sql, params=()):
    conn = get_connection()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    except Exception as e:
        st.error(f"Query error: {e}")
        return []
    finally:
        conn.close()


def fetchone(sql, params=()):
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()
    except Exception as e:
        st.error(f"Query error: {e}")
        return None
    finally:
        conn.close()


def execute(sql, params=()):
    """Run INSERT/UPDATE/DELETE. Returns lastrowid or True/False."""
    conn = get_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            try:
                return cur.fetchone()
            except Exception:
                return True
    except Exception as e:
        conn.rollback()
        st.error(f"Execute error: {e}")
        return None
    finally:
        conn.close()
