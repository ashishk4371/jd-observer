import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List

import sqlite_vec

# JD_GLANCE_DATA_DIR lets a deployment (e.g. a Docker volume) pin storage to a
# fixed mount point; unset falls back to the original local-dev location.
_DATA_DIR = Path(os.environ["JD_GLANCE_DATA_DIR"]) if os.environ.get("JD_GLANCE_DATA_DIR") else Path.home() / ".jd_glance_cache"
DB_PATH = _DATA_DIR / "jd_glance.db"
_LEGACY_DB_PATH = Path.home() / ".jd_analyzer_cache" / "jd_analyzer.db"  # pre-rename location
EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


def _migrate_legacy_db() -> None:
    """One-time carry-over: this project was renamed from JD Analyzer to JD Glance.
    If data exists at the old cache path and nothing exists at the new one yet,
    move it forward instead of silently orphaning already-uploaded resumes."""
    if not DB_PATH.exists() and _LEGACY_DB_PATH.exists():
        shutil.move(str(_LEGACY_DB_PATH), str(DB_PATH))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_db()
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


_conn: Optional[sqlite3.Connection] = None


def get_db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = get_connection()
        init_db(_conn)
    return _conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS resumes (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            content_hash TEXT UNIQUE NOT NULL,
            raw_text TEXT NOT NULL,
            uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS resume_profiles (
            id TEXT PRIMARY KEY,
            resume_id TEXT NOT NULL REFERENCES resumes(id),
            content_hash TEXT UNIQUE NOT NULL,
            summary TEXT,
            seniority_level TEXT,
            total_years_experience REAL,
            skills TEXT NOT NULL DEFAULT '[]',
            domains TEXT NOT NULL DEFAULT '[]',
            roles TEXT NOT NULL DEFAULT '[]',
            key_achievements TEXT NOT NULL DEFAULT '[]',
            is_llm_powered INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS job_descriptions (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            content_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            resume_id TEXT NOT NULL REFERENCES resumes(id),
            job_description_id TEXT NOT NULL REFERENCES job_descriptions(id),
            match_score REAL,
            score_level TEXT,
            breakdown TEXT,
            skills TEXT,
            llm_analysis TEXT,
            summary TEXT,
            actionable_tips TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_resume_profiles "
        f"USING vec0(id TEXT PRIMARY KEY, embedding FLOAT[{EMBEDDING_DIM}] distance_metric=cosine)"
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_job_descriptions "
        f"USING vec0(id TEXT PRIMARY KEY, embedding FLOAT[{EMBEDDING_DIM}] distance_metric=cosine)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Resumes
# ---------------------------------------------------------------------------

def get_resume_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute(
        "SELECT * FROM resumes WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return dict(row) if row else None


def get_resume(resume_id: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute(
        "SELECT * FROM resumes WHERE id = ?", (resume_id,)
    ).fetchone()
    return dict(row) if row else None


def insert_resume(filename: str, content_hash: str, raw_text: str) -> str:
    resume_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO resumes (id, filename, content_hash, raw_text) VALUES (?, ?, ?, ?)",
        (resume_id, filename, content_hash, raw_text),
    )
    conn.commit()
    return resume_id


def list_resumes() -> List[Dict[str, Any]]:
    rows = get_db().execute(
        "SELECT * FROM resumes ORDER BY uploaded_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def delete_resume(resume_id: str) -> None:
    """Remove a resume, its profile, and its embedding vector. Analyses that
    reference this resume are left alone — they're a historical snapshot,
    not a live join."""
    conn = get_db()
    profile = conn.execute(
        "SELECT id FROM resume_profiles WHERE resume_id = ?", (resume_id,)
    ).fetchone()
    if profile:
        conn.execute("DELETE FROM vec_resume_profiles WHERE id = ?", (profile["id"],))
        conn.execute("DELETE FROM resume_profiles WHERE id = ?", (profile["id"],))
    conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Resume profiles
# ---------------------------------------------------------------------------

def get_profile_by_content_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute(
        "SELECT * FROM resume_profiles WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return _deserialize_profile(row) if row else None


def get_profile_by_resume_id(resume_id: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute(
        "SELECT * FROM resume_profiles WHERE resume_id = ?", (resume_id,)
    ).fetchone()
    return _deserialize_profile(row) if row else None


def insert_profile(resume_id: str, content_hash: str, profile: Dict[str, Any]) -> str:
    profile_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO resume_profiles
           (id, resume_id, content_hash, summary, seniority_level, total_years_experience,
            skills, domains, roles, key_achievements, is_llm_powered)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile_id,
            resume_id,
            content_hash,
            profile.get("summary", ""),
            profile.get("seniority_level", "Unknown"),
            profile.get("total_years_experience"),
            json.dumps(profile.get("skills", [])),
            json.dumps(profile.get("domains", [])),
            json.dumps(profile.get("roles", [])),
            json.dumps(profile.get("key_achievements", [])),
            int(bool(profile.get("is_llm_powered", False))),
        ),
    )
    conn.commit()
    return profile_id


def _deserialize_profile(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    for field in ("skills", "domains", "roles", "key_achievements"):
        d[field] = json.loads(d[field]) if d[field] else []
    d["is_llm_powered"] = bool(d["is_llm_powered"])
    return d


# ---------------------------------------------------------------------------
# Job descriptions
# ---------------------------------------------------------------------------

def get_job_description_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    row = get_db().execute(
        "SELECT * FROM job_descriptions WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return dict(row) if row else None


def insert_job_description(text: str, content_hash: str) -> str:
    jd_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        "INSERT INTO job_descriptions (id, text, content_hash) VALUES (?, ?, ?)",
        (jd_id, text, content_hash),
    )
    conn.commit()
    return jd_id


# ---------------------------------------------------------------------------
# Analyses (history)
# ---------------------------------------------------------------------------

def insert_analysis(
    resume_id: str,
    job_description_id: str,
    match_score: float,
    score_level: str,
    breakdown: Dict[str, Any],
    skills: Dict[str, Any],
    llm_analysis: Dict[str, Any],
    summary: str,
    actionable_tips: List[str],
) -> str:
    analysis_id = str(uuid.uuid4())
    conn = get_db()
    conn.execute(
        """INSERT INTO analyses
           (id, resume_id, job_description_id, match_score, score_level, breakdown, skills,
            llm_analysis, summary, actionable_tips)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            analysis_id,
            resume_id,
            job_description_id,
            match_score,
            score_level,
            json.dumps(breakdown),
            json.dumps(skills),
            json.dumps(llm_analysis),
            summary,
            json.dumps(actionable_tips),
        ),
    )
    conn.commit()
    return analysis_id


# ---------------------------------------------------------------------------
# Vector storage (sqlite-vec, same connection/file as everything above)
# ---------------------------------------------------------------------------

def upsert_resume_profile_vector(profile_id: str, embedding: List[float]) -> None:
    conn = get_db()
    conn.execute("DELETE FROM vec_resume_profiles WHERE id = ?", (profile_id,))
    conn.execute(
        "INSERT INTO vec_resume_profiles (id, embedding) VALUES (?, ?)",
        (profile_id, sqlite_vec.serialize_float32(embedding)),
    )
    conn.commit()


def upsert_job_description_vector(jd_id: str, embedding: List[float]) -> None:
    conn = get_db()
    conn.execute("DELETE FROM vec_job_descriptions WHERE id = ?", (jd_id,))
    conn.execute(
        "INSERT INTO vec_job_descriptions (id, embedding) VALUES (?, ?)",
        (jd_id, sqlite_vec.serialize_float32(embedding)),
    )
    conn.commit()


def get_resume_profile_vector(profile_id: str) -> Optional[bytes]:
    row = get_db().execute(
        "SELECT embedding FROM vec_resume_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    return row["embedding"] if row else None


def get_job_description_vector(jd_id: str) -> Optional[bytes]:
    row = get_db().execute(
        "SELECT embedding FROM vec_job_descriptions WHERE id = ?", (jd_id,)
    ).fetchone()
    return row["embedding"] if row else None
