"""
db.py — Storage layer (SQLite).

WHAT:  SQLite is a full SQL database that lives in a single file
       (data/jobfisher.db). It ships with Python, so there is nothing to install
       and nothing to pay for.
WHY:   Browser memory disappears when you close the tab. The job history,
       statuses, profile and resume info must survive restarts, so they live
       in a database file on your computer.
HOW:   Every other module calls get_connection() to talk to the database.
       init_db() creates the tables the first time the app starts.

Developer mindset: keep all table definitions in ONE place so you can open
this file and understand the whole data model at a glance.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

# Where the data lives. Tests point this somewhere else (a temp folder) so they
# never touch your real database.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("JOBFISHER_DATA_DIR", os.path.join(BASE_DIR, "data"))


def db_path():
    return os.path.join(DATA_DIR, "jobfisher.db")


def resume_dir():
    return os.path.join(DATA_DIR, "resumes")


def now_iso():
    """Current time as an ISO-8601 string in UTC, e.g. '2026-10-02T17:05:00+00:00'.
    We always store UTC and let the browser convert to your local time."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def get_connection():
    """Open a connection for a `with` block:

        with get_connection() as conn:
            conn.execute(...)

    When the block finishes, changes are saved (commit) and the connection is
    closed. If an error happens inside the block, everything in it is undone
    (rollback) — so the database is never left half-updated.

    row_factory=sqlite3.Row lets us read columns by name (row["title"])
    instead of by position (row[1]) — much more readable.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
-- One row per unique job posting (duplicates from different sources are merged).
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key       TEXT UNIQUE NOT NULL,   -- company+title+city, used to spot duplicates
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT,
    work_arrangement TEXT,                   -- Remote / Hybrid / On-site / Unknown
    remote_region    TEXT,                   -- for remote jobs: who may apply ("USA only", "Europe"...)
    level_hint       TEXT,                   -- level label from the source, e.g. "Entry Level"
    employment_type  TEXT,                   -- Full-time / Part-time / Contract ... when stated
    salary_text      TEXT,                   -- only when the SOURCE provides it; never estimated
    salary_min       REAL,
    salary_max       REAL,
    description      TEXT,                   -- raw (cleaned) description, kept so analysis is traceable
    url              TEXT,                   -- best application URL (direct company URL preferred)
    source           TEXT,                   -- primary source name
    sources_json     TEXT DEFAULT '[]',      -- every source this job was seen on
    source_ids_json  TEXT DEFAULT '[]',      -- "source:id" strings, for exact duplicate matching
    date_posted      TEXT,
    date_discovered  TEXT NOT NULL,          -- first time JobFisher ever saw it
    last_checked     TEXT,                   -- last refresh that queried its source
    last_seen_active TEXT,                   -- last time it still appeared in results
    content_hash     TEXT,                   -- fingerprint of the text, to detect edits
    updated_at       TEXT,                   -- when the posting text last changed
    freshness        TEXT DEFAULT 'new',     -- new / updated / seen
    status           TEXT DEFAULT 'New',     -- lifecycle status you control
    is_relevant      INTEGER DEFAULT 0,      -- 1 = actually a web design/dev role
    fit_score        REAL DEFAULT 0,
    fit_category     TEXT,
    difficulty       TEXT,
    competitiveness  TEXT,
    hiring_context   TEXT,
    analysis_json    TEXT,                   -- full explainable analysis (see matcher.py)
    in_top8          INTEGER DEFAULT 0,      -- 1 = currently shown on the dashboard
    is_manual        INTEGER DEFAULT 0       -- 1 = you pasted it in yourself
);

-- One row per press of "Refresh Jobs" — powers the Search Summary panel.
CREATE TABLE IF NOT EXISTS refreshes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    scanned      INTEGER DEFAULT 0,
    relevant     INTEGER DEFAULT 0,
    new_count    INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    strong       INTEGER DEFAULT 0,
    displayed    INTEGER DEFAULT 0,
    source_report_json TEXT DEFAULT '[]'      -- per-source result / error messages
);

-- Your profile is one JSON document (skills, education, experience, projects...).
CREATE TABLE IF NOT EXISTS profile (
    id         INTEGER PRIMARY KEY CHECK (id = 1),   -- only ever one row
    data_json  TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- App settings (weights, locations, sources...). Also a single JSON document.
CREATE TABLE IF NOT EXISTS settings (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    data_json  TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Uploaded resumes. Only one is active; the file itself lives in data/resumes/.
CREATE TABLE IF NOT EXISTS resumes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    original_name TEXT NOT NULL,
    stored_name   TEXT NOT NULL,
    size_bytes    INTEGER,
    uploaded_at   TEXT NOT NULL,
    text          TEXT,          -- extracted text (stays local)
    parsed_json   TEXT,          -- structured data pulled from the text
    is_active     INTEGER DEFAULT 0
);

-- Application tracking details for jobs you act on.
CREATE TABLE IF NOT EXISTS applications (
    job_id              INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    date_applied        TEXT,
    interview_dates_json TEXT DEFAULT '[]',
    notes               TEXT DEFAULT '',
    updated_at          TEXT
);

-- Every status change, so history ("jobs viewed", "rejections") can be counted later.
CREATE TABLE IF NOT EXISTS status_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    status     TEXT NOT NULL,
    changed_at TEXT NOT NULL
);

-- Remembers when each source was last called, so we respect API rate limits.
CREATE TABLE IF NOT EXISTS source_calls (
    source     TEXT PRIMARY KEY,
    last_called TEXT NOT NULL
);
"""


def init_db():
    """Create tables if they don't exist yet. Safe to run every startup."""
    os.makedirs(resume_dir(), exist_ok=True)
    with get_connection() as conn:
        conn.executescript(SCHEMA)


# --- Small JSON helpers --------------------------------------------------------
# SQLite has no list/dict column type, so we store those as JSON text.

def to_json(value):
    return json.dumps(value, ensure_ascii=False)


def from_json(text, default=None):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default
