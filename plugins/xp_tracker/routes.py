"""
routes.py — Flask Blueprint for XP Tracker plugin.

Page routes:
  GET  /xp-tracker/                        — Home: tracked players + search
  GET  /xp-tracker/player/<player_id>      — Player XP history
  GET  /xp-tracker/empire                  — Empire comparison chart
  GET  /xp-tracker/settlement              — Settlement comparison chart
  GET  /xp-tracker/leaderboard             — Top XP gainers

API routes (JSON):
  POST /xp-tracker/api/track               — Add player to tracking
  POST /xp-tracker/api/untrack             — Remove player from tracking
  POST /xp-tracker/api/snapshot-now        — Trigger immediate poll
  GET  /xp-tracker/api/history/<player_id> — XP history data for Chart.js
  GET  /xp-tracker/api/empire-history      — Multi-player history for empire chart
  GET  /xp-tracker/api/settlement-history  — Multi-player history for settlement chart
  GET  /xp-tracker/api/search-empire       — Scan leaderboard for empire members
  GET  /xp-tracker/api/claim-search        — Search claims by name
  GET  /xp-tracker/api/claim-members       — Get citizens of a claim
  GET  /xp-tracker/api/status              — Poller status

CLI commands:
  flask xp-tracker set-interval <minutes>  — Change poll interval
"""

import time
import click

from flask import Blueprint, render_template, request, jsonify, current_app
from core.bitjita import search_players, get_player, get_leaderboard_skills, get_claims, get_claim_citizens

from plugins.xp_tracker import db
from plugins.xp_tracker import poller as xp_poller
from plugins.xp_tracker.skills import DISPLAY_SKILLS, SKILL_ID_TO_NAME, SKILL_ICONS, xp_to_level

bp = Blueprint(
    "xp_tracker", __name__,
    template_folder="templates",
    static_folder="static",
)

# Time window options (label -> seconds)
TIME_WINDOWS = {
    "24h":  86400,
    "7d":   86400 * 7,
    "30d":  86400 * 30,
    "all":  None,
}


def _window_since(window_key):
    """Return unix timestamp for the start of the given window, or None for 'all'."""
    seconds = TIME_WINDOWS.get(window_key)
    return int(time.time()) - seconds if seconds else None


def _build_chart_data(player_id, since, skill_id=None):
    """
    Build Chart.js-ready data for a single player.
    Returns {labels: [...], gains: [...]} where gains are XP delta from window start.
    skill_id=None means total XP.
    """
    snapshots = db.get_snapshots(player_id, since=since)
    if len(snapshots) < 2:
        return {"labels": [], "gains": []}

    sid = str(skill_id) if skill_id is not None else None

    def get_xp(snap):
        return snap["skill_data"].get(sid, 0) if sid else snap["total_xp"]

    baseline = get_xp(snapshots[0])
    labels   = []
    gains    = []

    for snap in snapshots:
        ts = snap["snapshot_time"]
        labels.append(ts * 1000)  # JS expects milliseconds
        gains.append(get_xp(snap) - baseline)

    return {"labels": labels, "gains": gains}


# ── Page routes ───────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    players = db.get_tracked_player_summary()
    status  = xp_poller.get_status()
    return render_template(
        "xp_tracker/index.html",
        players=players,
        status=status,
        skill_icons=SKILL_ICONS,
    )


@bp.route("/player/<player_id>")
def player_detail(player_id):
    if not db.is_tracked(player_id):
        # Still show the page but with a "not tracked" message
        pass

    tracked_players = db.get_tracked_players()
    player_info = next((p for p in tracked_players if p["player_id"] == player_id), None)

    window    = request.args.get("window", "7d")
    skill_id  = request.args.get("skill", None)
    since     = _window_since(window)
    snapshots = db.get_snapshots(player_id, since=since)

    # Compute per-skill gains for the gains table
    skill_gains = []
    if len(snapshots) >= 2:
        first = snapshots[0]
        last  = snapshots[-1]
        for skill in DISPLAY_SKILLS:
            sid  = str(skill["id"])
            start = first["skill_data"].get(sid, 0)
            end   = last["skill_data"].get(sid, 0)
            gain  = end - start
            if gain > 0 or end > 0:
                start_level, _, _, _ = xp_to_level(start)
                end_level,   _, _, _ = xp_to_level(end)
                skill_gains.append({
                    **skill,
                    "gain":        gain,
                    "end_xp":      end,
                    "start_level": start_level,
                    "end_level":   end_level,
                    "levelled_up": end_level > start_level,
                })
        skill_gains.sort(key=lambda s: s["gain"], reverse=True)

    return render_template(
        "xp_tracker/player.html",
        player_id=player_id,
        player_info=player_info,
        window=window,
        skill_id=skill_id,
        skills=DISPLAY_SKILLS,
        skill_gains=skill_gains,
        skill_icons=SKILL_ICONS,
        snapshot_count=len(snapshots),
        time_windows=list(TIME_WINDOWS.keys()),
    )


@bp.route("/empire")
def empire():
    empire_name = request.args.get("empire", "")
    window      = request.args.get("window", "7d")
    skill_id    = request.args.get("skill", None)

    empire_names   = db.get_empire_names()
    empire_members = db.get_players_by_empire(empire_name) if empire_name else []

    return render_template(
        "xp_tracker/empire.html",
        empire_name=empire_name,
        empire_names=empire_names,
        empire_members=empire_members,
        window=window,
        skill_id=skill_id,
        skills=DISPLAY_SKILLS,
        skill_icons=SKILL_ICONS,
        time_windows=list(TIME_WINDOWS.keys()),
    )


@bp.route("/settlement")
def settlement():
    settlement_name  = request.args.get("settlement", "")
    window           = request.args.get("window", "7d")
    skill_id         = request.args.get("skill", None)

    settlement_names   = db.get_settlement_names()
    settlement_members = db.get_players_by_settlement(settlement_name) if settlement_name else []

    return render_template(
        "xp_tracker/settlement.html",
        settlement_name=settlement_name,
        settlement_names=settlement_names,
        settlement_members=settlement_members,
        window=window,
        skill_id=skill_id,
        skills=DISPLAY_SKILLS,
        skill_icons=SKILL_ICONS,
        time_windows=list(TIME_WINDOWS.keys()),
    )


@bp.route("/leaderboard")
def leaderboard():
    window   = request.args.get("window", "7d")
    skill_id = request.args.get("skill", None)
    since    = _window_since(window)

    sid = int(skill_id) if skill_id and skill_id.isdigit() else None
    top_gainers = db.get_top_gainers(since=since, skill_id=sid, limit=25)

    return render_template(
        "xp_tracker/leaderboard.html",
        top_gainers=top_gainers,
        window=window,
        skill_id=skill_id,
        skills=DISPLAY_SKILLS,
        skill_icons=SKILL_ICONS,
        skill_id_to_name=SKILL_ID_TO_NAME,
        time_windows=list(TIME_WINDOWS.keys()),
    )


# ── API routes ────────────────────────────────────────────────────────────────

@bp.route("/api/track", methods=["POST"])
def api_track():
    data      = request.get_json(silent=True) or {}
    player_id = data.get("player_id", "").strip()
    username  = data.get("username", "").strip()

    if not player_id:
        return jsonify({"error": "player_id required"}), 400

    # Fetch from API if username not supplied
    if not username:
        api_data = get_player(player_id)
        if api_data:
            username = api_data.get("player", {}).get("username", player_id)

    db.add_tracked_player(player_id, username or player_id)
    return jsonify({"ok": True, "player_id": player_id, "username": username})


@bp.route("/api/untrack", methods=["POST"])
def api_untrack():
    data      = request.get_json(silent=True) or {}
    player_id = data.get("player_id", "").strip()
    if not player_id:
        return jsonify({"error": "player_id required"}), 400
    db.remove_tracked_player(player_id)
    return jsonify({"ok": True})


@bp.route("/api/snapshot-now", methods=["POST"])
def api_snapshot_now():
    """Trigger an immediate snapshot of all tracked players."""
    try:
        xp_poller.trigger_poll_now()
        return jsonify({"ok": True, "message": "Snapshot triggered."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/history/<player_id>")
def api_history(player_id):
    window   = request.args.get("window", "7d")
    skill_id = request.args.get("skill", None)
    since    = _window_since(window)
    sid      = int(skill_id) if skill_id and skill_id.isdigit() else None
    data     = _build_chart_data(player_id, since, skill_id=sid)
    return jsonify(data)


@bp.route("/api/empire-history")
def api_empire_history():
    """
    Return XP gain history for all members of an empire.
    Response: {players: [{player_id, username, labels, gains}, ...]}
    All players share the same label set (timestamps).
    """
    empire_name = request.args.get("empire", "")
    window      = request.args.get("window", "7d")
    skill_id    = request.args.get("skill", None)
    since       = _window_since(window)
    sid         = int(skill_id) if skill_id and skill_id.isdigit() else None

    members = db.get_players_by_empire(empire_name) if empire_name else []
    result  = []

    for member in members:
        chart = _build_chart_data(member["player_id"], since, skill_id=sid)
        if chart["labels"]:
            result.append({
                "player_id": member["player_id"],
                "username":  member["username"],
                **chart,
            })

    return jsonify({"players": result})


@bp.route("/api/settlement-history")
def api_settlement_history():
    """
    Return XP gain history for all members of a settlement (claim).
    Response: {players: [{player_id, username, labels, gains}, ...]}
    """
    settlement_name = request.args.get("settlement", "")
    window          = request.args.get("window", "7d")
    skill_id        = request.args.get("skill", None)
    since           = _window_since(window)
    sid             = int(skill_id) if skill_id and skill_id.isdigit() else None

    members = db.get_players_by_settlement(settlement_name) if settlement_name else []
    result  = []

    for member in members:
        chart = _build_chart_data(member["player_id"], since, skill_id=sid)
        if chart["labels"]:
            result.append({
                "player_id": member["player_id"],
                "username":  member["username"],
                **chart,
            })

    return jsonify({"players": result})


@bp.route("/api/search-empire")
def api_search_empire():
    """
    Page through the leaderboard looking for players in a given empire.
    Returns a list of {player_id, username, empire_name, is_tracked} objects.
    Note: The leaderboard may not always expose empire info; results depend on API shape.
    """
    empire_query = request.args.get("q", "").strip().lower()
    if not empire_query:
        return jsonify({"error": "q parameter required"}), 400

    max_pages = int(db.get_config("max_leaderboard_pages", "20"))
    found     = []
    tracked   = {p["player_id"] for p in db.get_tracked_players()}

    for page in range(1, max_pages + 1):
        data = get_leaderboard_skills(page=page, page_size=50)
        if not data:
            break

        # Try common response shapes
        players = data.get("players") or data.get("entries") or data.get("data") or []
        if not players:
            break

        for p in players:
            empire = (p.get("empireName") or p.get("empire_name") or "").lower()
            if empire_query in empire:
                pid = str(p.get("entityId") or p.get("player_id") or "")
                found.append({
                    "player_id":   pid,
                    "username":    p.get("username") or p.get("name") or "",
                    "empire_name": p.get("empireName") or p.get("empire_name") or "",
                    "is_tracked":  pid in tracked,
                })

        # Stop early if we've found a good number
        total = data.get("total") or data.get("count") or 0
        if total and len(found) >= total:
            break

    return jsonify({"results": found, "count": len(found)})


@bp.route("/api/player-search")
def api_player_search():
    """Proxy to Bitjita player search, used by the index page search bar."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q parameter required"}), 400
    data = search_players(query)
    if data is None:
        return jsonify({"error": "API unavailable. Check server connectivity."}), 502
    return jsonify({"players": data.get("players", [])})


@bp.route("/api/status")
def api_status():
    return jsonify(xp_poller.get_status())


@bp.route("/api/claim-search")
def api_claim_search():
    """Search claims by name. Returns list of {entityId, name, ownerPlayerUsername, regionName}."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q parameter required"}), 400
    data = get_claims(search=query, limit=50)
    if not data or (isinstance(data, dict) and data.get("__http_error__")):
        return jsonify({"error": "API unavailable."}), 502
    if isinstance(data, list):
        all_claims = data
    else:
        all_claims = data.get("claims") or data.get("data") or data.get("results") or []
    return jsonify({"claims": [
        {
            "entityId":            c.get("entityId", ""),
            "name":                c.get("name", ""),
            "ownerPlayerUsername": c.get("ownerPlayerUsername", ""),
            "regionName":          c.get("regionName", ""),
        }
        for c in all_claims
    ]})


@bp.route("/api/claim-members")
def api_claim_members():
    """
    Fetch citizens of a claim.
    Returns list of {player_id, username, is_tracked}.
    """
    claim_id = request.args.get("claim_id", "").strip()
    if not claim_id:
        return jsonify({"error": "claim_id parameter required"}), 400

    data = get_claim_citizens(claim_id)
    if not data or isinstance(data, dict) and data.get("__http_error__"):
        return jsonify({"error": "API unavailable or claim not found."}), 502

    tracked = {p["player_id"] for p in db.get_tracked_players()}
    citizens = data.get("citizens", [])
    results = []
    for c in citizens:
        pid = str(c.get("entityId", ""))
        results.append({
            "player_id":  pid,
            "username":   c.get("userName") or c.get("username") or "",
            "is_tracked": pid in tracked,
        })
    results.sort(key=lambda x: x["username"].lower())
    return jsonify({"members": results, "count": len(results)})


# ── CLI commands ──────────────────────────────────────────────────────────────

@bp.cli.command("set-interval")
@click.argument("minutes", type=int)
def cli_set_interval(minutes):
    """Set the XP tracker poll interval in minutes. Takes effect within 1 minute."""
    if minutes < 1:
        click.echo("Interval must be at least 1 minute.", err=True)
        return
    db.set_config("poll_interval_minutes", str(minutes))
    click.echo(f"XP Tracker poll interval set to {minutes} minute(s).")
    click.echo("Change takes effect within the next scheduler tick (up to 1 minute).")


@bp.cli.command("poll-now")
def cli_poll_now():
    """Immediately snapshot all tracked players."""
    click.echo("Triggering XP snapshot for all tracked players...")
    xp_poller.trigger_poll_now()
    click.echo("Done.")


@bp.cli.command("status")
def cli_status():
    """Show XP tracker poller status."""
    s = xp_poller.get_status()
    click.echo(f"Poll interval : {s['poll_interval_minutes']} minutes")
    click.echo(f"Scheduler     : {'running' if s['scheduler_running'] else 'stopped'}")
    if s["last_poll_time"]:
        import datetime
        last = datetime.datetime.fromtimestamp(s["last_poll_time"]).strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"Last poll     : {last}")
    click.echo(f"Next poll in  : {s['next_poll_in_seconds']}s")
