"""
db.py — SQLite persistence for XP Tracker.

Schema:
  tracked_players  — players we actively snapshot each poll cycle
  xp_snapshots     — one row per player per poll (full skill XP blob)
  config           — key/value settings (poll interval, last poll time, etc.)

Database: data/xp_tracker.db (relative to project root)
"""

import json
import os
import sqlite3
import time

_HERE   = os.path.dirname(__file__)
_ROOT   = os.path.dirname(os.path.dirname(_HERE))
DB_PATH = os.path.join(_ROOT, "data", "xp_tracker.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Called once at startup."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tracked_players (
            player_id   TEXT PRIMARY KEY,
            username    TEXT NOT NULL,
            empire_id   TEXT,
            empire_name TEXT,
            claim_id    TEXT,
            claim_name  TEXT,
            added_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS xp_snapshots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id     TEXT NOT NULL,
            snapshot_time INTEGER NOT NULL,
            total_xp      INTEGER NOT NULL,
            skill_data    TEXT NOT NULL   -- JSON: {"2": 261432, "3": 171538, ...}
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_player_time
            ON xp_snapshots (player_id, snapshot_time);

        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO config (key, value) VALUES ('poll_interval_minutes', '10');
        INSERT OR IGNORE INTO config (key, value) VALUES ('last_poll_time', '0');
        INSERT OR IGNORE INTO config (key, value) VALUES ('max_leaderboard_pages', '20');
        """)
        # Migrate existing databases that predate claim columns
        for col in ("claim_id", "claim_name"):
            try:
                c.execute(f"ALTER TABLE tracked_players ADD COLUMN {col} TEXT")
            except Exception:
                pass  # column already exists


# ── Config ────────────────────────────────────────────────────────────────────

def get_config(key, default=None):
    with _conn() as c:
        row = c.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_config(key, value):
    with _conn() as c:
        c.execute(
            "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )


# ── Tracked players ───────────────────────────────────────────────────────────

def add_tracked_player(player_id, username, empire_id=None, empire_name=None):
    with _conn() as c:
        c.execute(
            """INSERT INTO tracked_players (player_id, username, empire_id, empire_name, added_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(player_id) DO UPDATE SET username=excluded.username""",
            (player_id, username, empire_id, empire_name, int(time.time()))
        )


def remove_tracked_player(player_id):
    with _conn() as c:
        c.execute("DELETE FROM tracked_players WHERE player_id=?", (player_id,))


def get_tracked_players():
    """Return list of all tracked players as dicts."""
    with _conn() as c:
        rows = c.execute(
            "SELECT player_id, username, empire_id, empire_name, added_at FROM tracked_players ORDER BY username"
        ).fetchall()
        return [dict(r) for r in rows]


def is_tracked(player_id):
    with _conn() as c:
        row = c.execute("SELECT 1 FROM tracked_players WHERE player_id=?", (player_id,)).fetchone()
        return row is not None


def update_player_empire(player_id, empire_id, empire_name):
    with _conn() as c:
        c.execute(
            "UPDATE tracked_players SET empire_id=?, empire_name=? WHERE player_id=?",
            (empire_id, empire_name, player_id)
        )


def update_player_username(player_id, username):
    with _conn() as c:
        c.execute(
            "UPDATE tracked_players SET username=? WHERE player_id=?",
            (username, player_id)
        )


def get_empire_names():
    """Return sorted list of unique empire names across all tracked players."""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT empire_name FROM tracked_players WHERE empire_name IS NOT NULL ORDER BY empire_name"
        ).fetchall()
        return [r["empire_name"] for r in rows]


def get_players_by_empire(empire_name):
    """Return tracked players belonging to a given empire."""
    with _conn() as c:
        rows = c.execute(
            "SELECT player_id, username, empire_id, empire_name, added_at FROM tracked_players WHERE empire_name=? ORDER BY username",
            (empire_name,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_player_claim(player_id, claim_id, claim_name):
    with _conn() as c:
        c.execute(
            "UPDATE tracked_players SET claim_id=?, claim_name=? WHERE player_id=?",
            (claim_id, claim_name, player_id)
        )


def get_settlement_names():
    """Return sorted list of unique claim names across all tracked players."""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT claim_name FROM tracked_players WHERE claim_name IS NOT NULL ORDER BY claim_name"
        ).fetchall()
        return [r["claim_name"] for r in rows]


def get_players_by_settlement(claim_name):
    """Return tracked players belonging to a given claim/settlement."""
    with _conn() as c:
        rows = c.execute(
            "SELECT player_id, username, empire_id, empire_name, claim_id, claim_name, added_at "
            "FROM tracked_players WHERE claim_name=? ORDER BY username",
            (claim_name,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Snapshots ─────────────────────────────────────────────────────────────────

def insert_snapshot(player_id, total_xp, skill_data_dict, snapshot_time=None):
    """
    Insert a new XP snapshot.
    skill_data_dict: {skill_id_str: xp_int, ...}
    """
    ts = snapshot_time or int(time.time())
    with _conn() as c:
        c.execute(
            "INSERT INTO xp_snapshots (player_id, snapshot_time, total_xp, skill_data) VALUES (?,?,?,?)",
            (player_id, ts, total_xp, json.dumps(skill_data_dict))
        )


def get_snapshots(player_id, since=None, until=None):
    """
    Return snapshots for a player ordered by time ascending.
    since/until are unix timestamps.
    """
    query = "SELECT id, player_id, snapshot_time, total_xp, skill_data FROM xp_snapshots WHERE player_id=?"
    params = [player_id]
    if since:
        query += " AND snapshot_time >= ?"
        params.append(since)
    if until:
        query += " AND snapshot_time <= ?"
        params.append(until)
    query += " ORDER BY snapshot_time ASC"
    with _conn() as c:
        rows = c.execute(query, params).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["skill_data"] = json.loads(row["skill_data"])
            result.append(row)
        return result


def get_latest_snapshot(player_id):
    """Return the most recent snapshot for a player, or None."""
    with _conn() as c:
        row = c.execute(
            "SELECT id, player_id, snapshot_time, total_xp, skill_data FROM xp_snapshots WHERE player_id=? ORDER BY snapshot_time DESC LIMIT 1",
            (player_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["skill_data"] = json.loads(result["skill_data"])
        return result


def get_snapshot_count(player_id):
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) as cnt FROM xp_snapshots WHERE player_id=?", (player_id,)).fetchone()
        return row["cnt"]


# ── Leaderboard (computed from snapshots) ────────────────────────────────────

def get_top_gainers(since, skill_id=None, limit=25):
    """
    For each tracked player, compute XP gained in a skill (or total) since `since` timestamp.
    Returns list of {player_id, username, empire_name, gain, start_xp, end_xp} sorted by gain desc.
    """
    players = get_tracked_players()
    results = []

    for player in players:
        pid = player["player_id"]
        snapshots = get_snapshots(pid, since=since)
        if len(snapshots) < 2:
            # Need at least 2 snapshots to compute a gain
            continue

        first = snapshots[0]
        last  = snapshots[-1]

        if skill_id is not None:
            sid = str(skill_id)
            start_xp = first["skill_data"].get(sid, 0)
            end_xp   = last["skill_data"].get(sid, 0)
        else:
            start_xp = first["total_xp"]
            end_xp   = last["total_xp"]

        gain = end_xp - start_xp
        if gain <= 0:
            continue

        results.append({
            "player_id":   pid,
            "username":    player["username"],
            "empire_name": player["empire_name"],
            "gain":        gain,
            "start_xp":   start_xp,
            "end_xp":     end_xp,
        })

    results.sort(key=lambda r: r["gain"], reverse=True)
    return results[:limit]


def get_tracked_player_summary():
    """
    Return tracked players enriched with their latest snapshot info.
    Used for the index page.
    """
    players = get_tracked_players()
    results = []
    for player in players:
        latest = get_latest_snapshot(player["player_id"])
        count  = get_snapshot_count(player["player_id"])
        results.append({
            **player,
            "latest_snapshot": latest,
            "snapshot_count":  count,
        })
    return results
