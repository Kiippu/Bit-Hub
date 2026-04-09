"""
db.py — SQLite persistence for Empire Planner.

Schema:
  planner_sessions  — Bitjita auth codes we generated, pending verification
  planner_admins    — verified admin grants per claim (entity_id + username)
  planner_goals     — goals stored per claim
  planner_custom_goals — individual free-text goals per claim

Database file: data/empire_planner.db (relative to project root)
"""

import sqlite3
import os
import secrets
import time

# Resolve db path relative to this file's grandparent (project root)
_HERE   = os.path.dirname(__file__)                          # plugins/empire_planner/
_ROOT   = os.path.dirname(os.path.dirname(_HERE))            # project root
DB_PATH = os.path.join(_ROOT, "data", "empire_planner.db")

# Auth codes expire after 10 minutes
CODE_TTL = 600


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Called once at startup."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS planner_sessions (
            code        TEXT PRIMARY KEY,
            claim_id    TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS planner_admins (
            claim_id    TEXT NOT NULL,
            username    TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            granted_by  TEXT NOT NULL,       -- username of who granted this
            granted_at  INTEGER NOT NULL,
            PRIMARY KEY (claim_id, username)
        );

        CREATE TABLE IF NOT EXISTS planner_goals (
            claim_id            TEXT PRIMARY KEY,
            tier_target         TEXT,
            treasury_target     TEXT,
            supplies_target     TEXT,
            tiles_target        TEXT,
            member_target       TEXT,
            target_skill_id     TEXT,
            min_skill_level     TEXT,
            focus_skill_ids     TEXT,
            updated_by          TEXT,
            updated_at          INTEGER
        );

        CREATE TABLE IF NOT EXISTS planner_custom_goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id    TEXT NOT NULL,
            text        TEXT NOT NULL,
            created_by  TEXT NOT NULL,
            created_at  INTEGER NOT NULL
        );
        """)


# ── Auth codes ────────────────────────────────────────────────────────────────

def create_auth_code(claim_id: str) -> str:
    """Generate a unique 8-char code the player pastes in-game."""
    code = secrets.token_hex(4).upper()   # e.g. "A3F92B1C"
    with _conn() as c:
        # Clean up old codes first
        c.execute("DELETE FROM planner_sessions WHERE created_at < ?",
                  (int(time.time()) - CODE_TTL,))
        c.execute("INSERT OR REPLACE INTO planner_sessions VALUES (?,?,?)",
                  (code, claim_id, int(time.time())))
    return code


def consume_auth_code(code: str):
    """
    Look up a pending code. Returns (claim_id) or None if expired/invalid.
    Deletes the code after retrieval (single-use).
    """
    with _conn() as c:
        row = c.execute(
            "SELECT claim_id, created_at FROM planner_sessions WHERE code=?",
            (code.strip().upper(),)
        ).fetchone()
        if not row:
            return None
        if int(time.time()) - row["created_at"] > CODE_TTL:
            c.execute("DELETE FROM planner_sessions WHERE code=?", (code,))
            return None
        c.execute("DELETE FROM planner_sessions WHERE code=?", (code,))
        return row["claim_id"]


# ── Admin grants ──────────────────────────────────────────────────────────────

def get_admins(claim_id: str) -> list:
    with _conn() as c:
        rows = c.execute(
            "SELECT username, entity_id, granted_by, granted_at FROM planner_admins WHERE claim_id=?",
            (claim_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def is_admin(claim_id: str, username: str) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM planner_admins WHERE claim_id=? AND LOWER(username)=LOWER(?)",
            (claim_id, username)
        ).fetchone()
        return row is not None


def grant_admin(claim_id: str, username: str, entity_id: str, granted_by: str):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO planner_admins VALUES (?,?,?,?,?)",
            (claim_id, username, entity_id, granted_by, int(time.time()))
        )


def revoke_admin(claim_id: str, username: str):
    with _conn() as c:
        c.execute(
            "DELETE FROM planner_admins WHERE claim_id=? AND LOWER(username)=LOWER(?)",
            (claim_id, username)
        )


# ── Goals ─────────────────────────────────────────────────────────────────────

def get_goals(claim_id: str) -> dict:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM planner_goals WHERE claim_id=?", (claim_id,)
        ).fetchone()
        if not row:
            return {}
        goals = dict(row)
        # Attach custom goals
        customs = c.execute(
            "SELECT id, text, created_by, created_at FROM planner_custom_goals WHERE claim_id=? ORDER BY created_at",
            (claim_id,)
        ).fetchall()
        goals["custom_goals"] = [dict(r) for r in customs]
        return goals


def save_goals(claim_id: str, goals: dict, updated_by: str):
    with _conn() as c:
        c.execute("""
            INSERT INTO planner_goals
              (claim_id, tier_target, treasury_target, supplies_target,
               tiles_target, member_target, target_skill_id, min_skill_level,
               focus_skill_ids, updated_by, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(claim_id) DO UPDATE SET
              tier_target=excluded.tier_target,
              treasury_target=excluded.treasury_target,
              supplies_target=excluded.supplies_target,
              tiles_target=excluded.tiles_target,
              member_target=excluded.member_target,
              target_skill_id=excluded.target_skill_id,
              min_skill_level=excluded.min_skill_level,
              focus_skill_ids=excluded.focus_skill_ids,
              updated_by=excluded.updated_by,
              updated_at=excluded.updated_at
        """, (
            claim_id,
            goals.get("tier_target", ""),
            goals.get("treasury_target", ""),
            goals.get("supplies_target", ""),
            goals.get("tiles_target", ""),
            goals.get("member_target", ""),
            goals.get("target_skill_id", ""),
            goals.get("min_skill_level", ""),
            goals.get("focus_skill_ids", ""),
            updated_by,
            int(time.time()),
        ))


def add_custom_goal(claim_id: str, text: str, created_by: str) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO planner_custom_goals (claim_id, text, created_by, created_at) VALUES (?,?,?,?)",
            (claim_id, text.strip(), created_by, int(time.time()))
        )
        return cur.lastrowid


def delete_custom_goal(goal_id: int, claim_id: str):
    """Only delete if it belongs to this claim (safety check)."""
    with _conn() as c:
        c.execute(
            "DELETE FROM planner_custom_goals WHERE id=? AND claim_id=?",
            (goal_id, claim_id)
        )
