"""db.py - SQLite storage. One file (recruit.db by default; evaluate.py uses eval.db)."""
import json
import sqlite3
from datetime import datetime, timedelta

from src.skills import normalise_skill

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY, title TEXT NOT NULL, min_years REAL NOT NULL);
CREATE TABLE IF NOT EXISTS job_skills (                  -- mandatory skills, one row each
    job_id TEXT REFERENCES jobs(job_id), skill TEXT, PRIMARY KEY (job_id, skill));
CREATE TABLE IF NOT EXISTS applications (
    application_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES jobs(job_id),
    file_name TEXT, file_hash TEXT,                       -- sha256 of the file bytes
    name TEXT, location TEXT,                             -- no email / phone stored
    total_years REAL,                                     -- calculated in Python
    resume_text TEXT, parsed_json TEXT,                   -- kept for search + audit
    status TEXT,                                          -- PENDING/SHORTLISTED/REJECTED/NEEDS_REVIEW/SCHEDULED
    reasons TEXT,                                         -- JSON list
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (job_id, file_hash));                          -- same resume can't apply twice
CREATE TABLE IF NOT EXISTS candidate_skills (            -- normalised skills, one row each
    application_id TEXT REFERENCES applications(application_id), skill TEXT,
    PRIMARY KEY (application_id, skill));
CREATE TABLE IF NOT EXISTS slots (
    slot_id TEXT PRIMARY KEY, panelist TEXT, start_time TEXT,
    status TEXT DEFAULT 'FREE', application_id TEXT);
CREATE UNIQUE INDEX IF NOT EXISTS one_slot_per_application
    ON slots(application_id) WHERE application_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS audit_log (
    ts TEXT DEFAULT CURRENT_TIMESTAMP, stage TEXT, application_id TEXT, details TEXT);
"""


def init_db(path="recruit.db", seed=True):
    conn = sqlite3.connect(path, check_same_thread=False)   # Streamlit uses several threads
    conn.executescript(SCHEMA)
    if seed and conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0:
        seed_data(conn)
    return conn


def seed_data(conn):
    add_job(conn, "ML Engineer", 2, ["Python", "SQL", "ML"])
    add_job(conn, "Backend Developer", 3, ["Java", "SQL", "Docker"])
    add_job(conn, "Frontend Developer", 2, ["JavaScript", "React", "CSS"])
    day0 = datetime(2026, 10, 28)
    panel = ["P. Rao", "S. Iyer", "A. Khan"]
    n = 0
    for d in range(3):
        for hhmm in ["10:00", "11:30", "14:00", "15:30"]:
            if n == 10:
                break
            n += 1
            t = (day0 + timedelta(days=d)).strftime("%Y-%m-%d") + " " + hhmm
            conn.execute("INSERT INTO slots (slot_id, panelist, start_time) VALUES (?,?,?)",
                         (f"S{n:02d}", panel[n % 3], t))
    conn.commit()


def add_job(conn, title, min_years, skills):
    job_id = f"J{conn.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] + 1:02d}"
    with conn:                                               # one transaction
        conn.execute("INSERT INTO jobs VALUES (?,?,?)", (job_id, title, float(min_years)))
        conn.executemany("INSERT OR IGNORE INTO job_skills VALUES (?,?)",
                         [(job_id, normalise_skill(s)) for s in skills if str(s).strip()])
    return job_id


def get_job(conn, job_id):
    row = conn.execute("SELECT job_id, title, min_years FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        return None
    skills = [r[0] for r in conn.execute("SELECT skill FROM job_skills WHERE job_id=? ORDER BY skill", (job_id,))]
    return {"job_id": row[0], "title": row[1], "min_years": row[2], "skills": skills}


def list_jobs(conn):
    return [get_job(conn, r[0]) for r in conn.execute("SELECT job_id FROM jobs ORDER BY job_id")]


def save_application(conn, job_id, file_name, file_hash, name, location, total_years,
                     resume_text, parsed_json, skills, status, reasons):
    app_id = f"A{conn.execute('SELECT COUNT(*) FROM applications').fetchone()[0] + 1:03d}"
    with conn:
        conn.execute("""INSERT INTO applications (application_id, job_id, file_name, file_hash, name,
                        location, total_years, resume_text, parsed_json, status, reasons)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                     (app_id, job_id, file_name, file_hash, name, location, total_years,
                      resume_text, parsed_json, status, json.dumps(reasons)))
        conn.executemany("INSERT OR IGNORE INTO candidate_skills VALUES (?,?)",
                         [(app_id, s) for s in skills])
    return app_id


def update_status(conn, application_id, status, reasons):
    with conn:
        conn.execute("UPDATE applications SET status=?, reasons=? WHERE application_id=?",
                     (status, json.dumps(reasons), application_id))


def get_applications(conn, job_id=None):
    sql = """SELECT a.application_id, a.job_id, a.name, a.total_years, a.status, a.reasons,
                    (SELECT GROUP_CONCAT(skill, ', ') FROM candidate_skills c
                     WHERE c.application_id = a.application_id) AS skills,
                    (SELECT start_time || ' (' || panelist || ')' FROM slots s
                     WHERE s.application_id = a.application_id) AS interview
             FROM applications a""" + (" WHERE a.job_id=?" if job_id else "") + " ORDER BY a.application_id"
    cols = ["application_id", "job_id", "name", "total_years", "status", "reasons", "skills", "interview"]
    rows = conn.execute(sql, (job_id,) if job_id else ()).fetchall()
    out = [dict(zip(cols, r)) for r in rows]
    for o in out:
        o["reasons"] = "; ".join(json.loads(o["reasons"] or "[]"))
    return out


def get_slots(conn):
    cols = ["slot_id", "panelist", "start_time", "status", "application_id"]
    return [dict(zip(cols, r)) for r in conn.execute(f"SELECT {', '.join(cols)} FROM slots ORDER BY start_time")]


def log_event(conn, stage, application_id, details):
    with conn:
        conn.execute("INSERT INTO audit_log (stage, application_id, details) VALUES (?,?,?)",
                     (stage, application_id, details))


def get_audit(conn, application_id):
    return [{"time": t, "stage": s, "details": d} for t, s, d in conn.execute(
        "SELECT ts, stage, details FROM audit_log WHERE application_id=? ORDER BY rowid", (application_id,))]
