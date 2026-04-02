from __future__ import annotations

import csv
import hashlib
import secrets
import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS crossings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    address TEXT,
    ward TEXT,
    district TEXT,
    city TEXT,
    latitude REAL,
    longitude REAL,
    crossing_type TEXT,
    barrier_type TEXT,
    manager_name TEXT,
    manager_phone TEXT,
    verification_status TEXT NOT NULL DEFAULT 'draft',
    coordinate_source TEXT,
    source_reference TEXT,
    verification_notes TEXT,
    surveyed_at TEXT,
    verified_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS train_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    route_name TEXT NOT NULL,
    direction TEXT NOT NULL,
    station_name TEXT NOT NULL,
    km INTEGER,
    train_no TEXT NOT NULL,
    pass_time TEXT NOT NULL,
    day_offset INTEGER NOT NULL DEFAULT 0,
    raw_time_text TEXT NOT NULL,
    scraped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_url, route_name, direction, station_name, train_no, raw_time_text)
);

CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    publisher TEXT,
    published_at TEXT,
    summary TEXT,
    matched_query TEXT,
    location_hint TEXT,
    severity_score INTEGER NOT NULL DEFAULT 0,
    scraped_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incident_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crossing_id INTEGER,
    title TEXT NOT NULL,
    incident_date TEXT,
    severity_level TEXT,
    casualties INTEGER NOT NULL DEFAULT 0,
    injured_count INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    source_url TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crossing_id) REFERENCES crossings(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS risk_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crossing_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    level TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crossing_id) REFERENCES crossings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS crossing_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crossing_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER NOT NULL DEFAULT 0,
    caption TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_cover INTEGER NOT NULL DEFAULT 0,
    uploaded_by INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crossing_id) REFERENCES crossings(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    user_role TEXT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    action TEXT NOT NULL,
    summary TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_crossings_city ON crossings(city, district, ward);
CREATE INDEX IF NOT EXISTS idx_train_schedules_station ON train_schedules(station_name, train_no);
CREATE INDEX IF NOT EXISTS idx_news_articles_published ON news_articles(published_at);
CREATE INDEX IF NOT EXISTS idx_incident_reports_crossing ON incident_reports(crossing_id, incident_date);
CREATE INDEX IF NOT EXISTS idx_risk_snapshots_crossing ON risk_snapshots(crossing_id, calculated_at);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token);
CREATE INDEX IF NOT EXISTS idx_crossing_images_crossing ON crossing_images(crossing_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs(entity_type, entity_id, created_at);
"""

ROLE_VALUES = ("admin", "editor", "reviewer", "viewer")


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _migrate_crossings_table(conn)
    _migrate_soft_delete_columns(conn)
    _migrate_users_table(conn)
    _migrate_crossing_images_table(conn)
    ensure_default_users(conn)
    conn.commit()


def import_crossings_csv(conn: sqlite3.Connection, csv_path: str) -> int:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    for row in rows:
        conn.execute(
            """
            INSERT INTO crossings (
                code, name, address, ward, district, city, latitude, longitude,
                crossing_type, barrier_type, manager_name, manager_phone,
                verification_status, coordinate_source, source_reference,
                verification_notes, surveyed_at, verified_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                ward = excluded.ward,
                district = excluded.district,
                city = excluded.city,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                crossing_type = excluded.crossing_type,
                barrier_type = excluded.barrier_type,
                manager_name = excluded.manager_name,
                manager_phone = excluded.manager_phone,
                verification_status = excluded.verification_status,
                coordinate_source = excluded.coordinate_source,
                source_reference = excluded.source_reference,
                verification_notes = excluded.verification_notes,
                surveyed_at = excluded.surveyed_at,
                verified_at = excluded.verified_at,
                notes = excluded.notes,
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                row.get("code"),
                row.get("name"),
                row.get("address"),
                row.get("ward"),
                row.get("district"),
                row.get("city"),
                _to_float(row.get("latitude")),
                _to_float(row.get("longitude")),
                row.get("crossing_type"),
                row.get("barrier_type"),
                row.get("manager_name"),
                row.get("manager_phone"),
                row.get("verification_status") or "draft",
                row.get("coordinate_source"),
                row.get("source_reference"),
                row.get("verification_notes"),
                row.get("surveyed_at"),
                row.get("verified_at"),
                row.get("notes"),
            ),
        )

    conn.commit()
    return len(rows)


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def ensure_default_users(conn: sqlite3.Connection) -> None:
    defaults = [
      ("admin", "admin123", "System Admin", "admin"),
      ("editor", "editor123", "Data Editor", "editor"),
      ("reviewer", "reviewer123", "Data Reviewer", "reviewer"),
      ("viewer", "viewer123", "Viewer User", "viewer"),
    ]
    for username, password, full_name, role in defaults:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, full_name, role)
            VALUES (?, ?, ?, ?)
            """,
            (username, hash_password(password), full_name, role),
        )


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, expected = password_hash.split("$", maxsplit=1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), 120_000)
    return secrets.compare_digest(digest.hex(), expected)


def _migrate_crossings_table(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(crossings)").fetchall()}
    desired_columns = {
        "verification_status": "TEXT NOT NULL DEFAULT 'draft'",
        "coordinate_source": "TEXT",
        "source_reference": "TEXT",
        "verification_notes": "TEXT",
        "surveyed_at": "TEXT",
        "verified_at": "TEXT",
    }
    for column_name, column_type in desired_columns.items():
        if column_name not in columns:
            conn.execute(f"ALTER TABLE crossings ADD COLUMN {column_name} {column_type}")


def _migrate_soft_delete_columns(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "crossings", "deleted_at", "TEXT")
    _ensure_column(conn, "train_schedules", "deleted_at", "TEXT")
    _ensure_column(conn, "incident_reports", "deleted_at", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def _migrate_users_table(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(users)").fetchall()
    if not rows:
        return

    current_columns = {row[1] for row in rows}
    needs_rebuild = "updated_at" not in current_columns
    if not needs_rebuild:
        invalid_roles = conn.execute(
            f"SELECT COUNT(*) AS total FROM users WHERE role NOT IN ({','.join('?' for _ in ROLE_VALUES)})",
            ROLE_VALUES,
        ).fetchone()
        needs_rebuild = bool(invalid_roles["total"])

    if not needs_rebuild:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        INSERT INTO users_new (id, username, password_hash, full_name, role, is_active, created_at, updated_at)
        SELECT
            id,
            username,
            password_hash,
            full_name,
            CASE
                WHEN role = 'admin' THEN 'admin'
                WHEN role = 'viewer' THEN 'viewer'
                ELSE 'viewer'
            END,
            COALESCE(is_active, 1),
            COALESCE(created_at, CURRENT_TIMESTAMP),
            CURRENT_TIMESTAMP
        FROM users
        """
    )
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")
    conn.execute("PRAGMA foreign_keys = ON")


def _migrate_crossing_images_table(conn: sqlite3.Connection) -> None:
    _ensure_column(conn, "crossing_images", "sort_order", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(conn, "crossing_images", "is_cover", "INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        WITH ranked AS (
            SELECT id, crossing_id, ROW_NUMBER() OVER (PARTITION BY crossing_id ORDER BY created_at, id) - 1 AS rn
            FROM crossing_images
        )
        UPDATE crossing_images
        SET sort_order = (
            SELECT rn
            FROM ranked
            WHERE ranked.id = crossing_images.id
        )
        WHERE sort_order = 0
        """
    )
    conn.execute(
        """
        WITH covers AS (
            SELECT MIN(id) AS id
            FROM crossing_images
            GROUP BY crossing_id
        )
        UPDATE crossing_images
        SET is_cover = CASE
            WHEN id IN (SELECT id FROM covers) THEN 1
            ELSE is_cover
        END
        WHERE crossing_id IN (SELECT crossing_id FROM crossing_images)
        """
    )
