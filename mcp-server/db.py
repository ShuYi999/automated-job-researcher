"""
SQLite persistence for job research data.

Stores searches, jobs, descriptions, and AI analyses so they survive
browser refreshes and build up history over time.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_db(_conn)
    return _conn


def _init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT NOT NULL,
            location TEXT,
            experience TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            posted TEXT,
            url TEXT,
            first_seen TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS search_jobs (
            search_id INTEGER REFERENCES searches(id),
            job_id TEXT REFERENCES jobs(id),
            PRIMARY KEY (search_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS job_details (
            job_id TEXT PRIMARY KEY REFERENCES jobs(id),
            description TEXT,
            salary TEXT,
            apply_url TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT REFERENCES jobs(id),
            search_id INTEGER REFERENCES searches(id),
            github_username TEXT,
            score INTEGER,
            why TEXT,
            strengths TEXT,
            gaps TEXT,
            experience_fit TEXT,
            source TEXT,
            analyzed_at TEXT DEFAULT (datetime('now'))
        );
    """)


def save_search(prompt: str, location: str, experience: str) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO searches (prompt, location, experience) VALUES (?, ?, ?)",
        (prompt, location, experience),
    )
    conn.commit()
    return cur.lastrowid


def save_jobs(search_id: int, jobs: list[dict]):
    conn = _get_conn()
    for job in jobs:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (id, title, company, location, posted, url) VALUES (?, ?, ?, ?, ?, ?)",
            (job.get("id"), job.get("title"), job.get("company"),
             job.get("location"), job.get("posted"), job.get("url")),
        )
        conn.execute(
            "INSERT OR IGNORE INTO search_jobs (search_id, job_id) VALUES (?, ?)",
            (search_id, job.get("id")),
        )
    conn.commit()


def save_detail(job_id: str, detail: dict):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO job_details (job_id, description, salary, apply_url) VALUES (?, ?, ?, ?)",
        (job_id, detail.get("description", ""), detail.get("salary", ""),
         detail.get("apply_url", "")),
    )
    conn.commit()


def save_analyses(search_id: int, github_username: str, analyses: list[dict]):
    conn = _get_conn()
    for a in analyses:
        conn.execute(
            """INSERT INTO ai_analyses
               (job_id, search_id, github_username, score, why, strengths, gaps, experience_fit, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (a.get("id"), search_id, github_username, a.get("score"),
             a.get("why"), json.dumps(a.get("strengths", [])),
             json.dumps(a.get("gaps", [])), a.get("experience_fit", ""),
             a.get("source", "")),
        )
    conn.commit()


def load_latest_search() -> dict | None:
    conn = _get_conn()

    row = conn.execute(
        "SELECT * FROM searches ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None

    search_id = row["id"]

    # Load jobs for this search
    job_rows = conn.execute("""
        SELECT j.* FROM jobs j
        JOIN search_jobs sj ON sj.job_id = j.id
        WHERE sj.search_id = ?
    """, (search_id,)).fetchall()

    jobs = [
        {"id": r["id"], "title": r["title"], "company": r["company"],
         "location": r["location"], "posted": r["posted"], "url": r["url"]}
        for r in job_rows
    ]

    # Load cached details
    details = {}
    for job in jobs:
        det = conn.execute(
            "SELECT * FROM job_details WHERE job_id = ?", (job["id"],)
        ).fetchone()
        if det:
            details[job["id"]] = {
                "description": det["description"],
                "salary": det["salary"],
                "apply_url": det["apply_url"],
            }

    # Load AI analyses for this search
    analysis_rows = conn.execute(
        "SELECT * FROM ai_analyses WHERE search_id = ? ORDER BY score DESC",
        (search_id,),
    ).fetchall()

    analyses = []
    for a in analysis_rows:
        analyses.append({
            "id": a["job_id"],
            "title": next((j["title"] for j in jobs if j["id"] == a["job_id"]), ""),
            "company": next((j["company"] for j in jobs if j["id"] == a["job_id"]), ""),
            "location": next((j["location"] for j in jobs if j["id"] == a["job_id"]), ""),
            "url": next((j["url"] for j in jobs if j["id"] == a["job_id"]), ""),
            "score": a["score"],
            "why": a["why"],
            "strengths": json.loads(a["strengths"]) if a["strengths"] else [],
            "gaps": json.loads(a["gaps"]) if a["gaps"] else [],
            "experience_fit": a["experience_fit"],
            "source": a["source"],
            "github_username": a["github_username"],
            "analyzed_at": a["analyzed_at"],
        })

    return {
        "search_id": search_id,
        "prompt": row["prompt"],
        "location": row["location"],
        "experience": row["experience"],
        "jobs": jobs,
        "details": details,
        "analyses": analyses,
    }
