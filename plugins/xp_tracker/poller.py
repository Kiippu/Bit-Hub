"""
poller.py — Background XP snapshot polling for XP Tracker.

Strategy:
  - APScheduler runs a tick every 1 minute.
  - Each tick checks if enough time has elapsed since the last poll
    (based on poll_interval_minutes in the config table).
  - This means changing poll_interval_minutes takes effect within 1 minute
    without needing to restart the scheduler.
  - For each tracked player, we call get_player() individually.
    This is the most reliable way to get full per-skill XP data.
  - A 0.5s delay between player calls keeps us friendly to the API.

CLI usage (change poll rate without restarting the server):
  flask xp-tracker set-interval <minutes>
"""

import time
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from core.bitjita import get_player
from plugins.xp_tracker import db

log = logging.getLogger("xp_tracker.poller")

_scheduler = None


def _extract_skill_data(player_data):
    """
    Pull skill XP out of the API response.
    Returns (skill_data_dict, total_xp, empire_id, empire_name, claim_id, claim_name, username).

    Handles the real API shape:
      player_data['player']['experience'] = [{skill_id, quantity}, ...]
      player_data['player']['empireMemberships'] = [{empireEntityId, empireName, ...}, ...]
      player_data['player']['claims'] = [{entityId, name, ...}, ...]
    """
    player = player_data.get("player", {})
    experience = player.get("experience", [])

    skill_data = {}
    for entry in experience:
        sid = entry.get("skill_id")
        qty = entry.get("quantity", 0)
        if sid is not None:
            skill_data[str(sid)] = qty

    total_xp = sum(skill_data.values())

    # Empire — use first membership as primary
    memberships = player.get("empireMemberships", [])
    empire_id   = None
    empire_name = None
    if memberships:
        primary     = memberships[0]
        empire_id   = str(primary.get("empireEntityId", ""))
        empire_name = primary.get("empireName")

    # Claim/settlement — use first claim as primary
    claims     = player.get("claims", [])
    claim_id   = None
    claim_name = None
    if claims:
        primary    = claims[0]
        claim_id   = str(primary.get("entityId", ""))
        claim_name = primary.get("name")

    username = player.get("username", "")
    return skill_data, total_xp, empire_id, empire_name, claim_id, claim_name, username


def _do_poll():
    """Snapshot all tracked players. Called by the scheduler tick when interval has elapsed."""
    players = db.get_tracked_players()
    if not players:
        log.info("No tracked players, skipping poll.")
        return

    log.info("XP Tracker poll starting — %d player(s) to snapshot.", len(players))
    success = 0
    failed  = 0

    for player in players:
        pid = player["player_id"]
        try:
            data = get_player(pid)
            if not data:
                log.warning("Could not fetch player %s (%s).", pid, player["username"])
                failed += 1
                continue

            skill_data, total_xp, empire_id, empire_name, claim_id, claim_name, username = _extract_skill_data(data)

            if not skill_data:
                log.warning("No skill data for player %s.", pid)
                failed += 1
                continue

            db.insert_snapshot(pid, total_xp, skill_data)

            # Keep username, empire, and claim info up to date
            if username:
                db.update_player_username(pid, username)
            if empire_id or empire_name:
                db.update_player_empire(pid, empire_id, empire_name)
            if claim_id or claim_name:
                db.update_player_claim(pid, claim_id, claim_name)

            success += 1
        except Exception:
            log.exception("Error snapshotting player %s.", pid)
            failed += 1

        # Be friendly to the API
        time.sleep(0.5)

    db.set_config("last_poll_time", str(int(time.time())))
    log.info("XP Tracker poll complete — %d ok, %d failed.", success, failed)


def _tick():
    """
    Called every minute by APScheduler.
    Runs the actual poll only if the configured interval has elapsed.
    """
    try:
        interval_minutes = int(db.get_config("poll_interval_minutes", "10"))
        last_poll        = int(db.get_config("last_poll_time", "0"))
        elapsed_seconds  = time.time() - last_poll

        if elapsed_seconds >= interval_minutes * 60:
            _do_poll()
    except Exception:
        log.exception("Error in XP Tracker scheduler tick.")


def start_scheduler():
    """
    Start the background scheduler. Called once from app.py at startup.
    Returns the scheduler instance (stored globally for CLI access).
    """
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_tick, "interval", minutes=1, id="xp_tracker_tick",
                       max_instances=1, coalesce=True)
    _scheduler.start()
    log.info("XP Tracker scheduler started (tick every 1 min).")
    return _scheduler


def trigger_poll_now():
    """Manually trigger an immediate poll (called from the UI or CLI)."""
    _do_poll()


def get_status():
    """Return a dict with current poller status for display in the UI."""
    interval  = int(db.get_config("poll_interval_minutes", "10"))
    last_poll = int(db.get_config("last_poll_time", "0"))
    next_poll = last_poll + interval * 60
    now       = int(time.time())

    return {
        "poll_interval_minutes": interval,
        "last_poll_time":        last_poll,
        "next_poll_in_seconds":  max(0, next_poll - now),
        "scheduler_running":     _scheduler is not None and _scheduler.running,
    }
