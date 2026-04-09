"""
Empire Planner plugin — routes.py

Auth flow:
  1. User clicks "Verify Identity"
  2. App generates a unique code (e.g. A3F92B1C) stored in SQLite
  3. User posts  bitjita:auth:A3F92B1C  in in-game chat channel 2
  4. User clicks "I've posted it"
  5. App POSTs to Bitjita /api/auth/chat/validate → gets verified username + entityId
  6. Checks if they are claim owner (emperor) OR in planner_admins for this claim
  7. Flask session["ep_user"] set → they get edit access

Goals stored in SQLite, visible to all, auth required to edit.
Emperor can grant/revoke admin to other members.
"""

import requests
import time
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, jsonify, flash)

from plugins.empire_planner import db as epdb

bp = Blueprint(
    "empire_planner", __name__,
    template_folder="templates",
    static_folder="static"
)

BITJITA = "https://bitjita.com"
TIMEOUT = 12
HEADERS = {"x-app-identifier": "bitcraft-hub", "Accept": "application/json"}

SKILL_NAMES = {
    2: "Forestry", 3: "Carpentry", 4: "Masonry", 5: "Mining",
    6: "Smithing", 7: "Scholar", 8: "Leatherworking", 9: "Hunting",
    10: "Tailoring", 11: "Farming", 12: "Fishing", 13: "Cooking",
    14: "Foraging", 15: "Construction", 17: "Taming", 18: "Slayer",
    19: "Merchanting", 21: "Sailing",
}


def _get(path, params=None):
    try:
        r = requests.get(f"{BITJITA}{path}", params=params,
                         headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[EmpirePlanner] GET {path}: {e}")
        return None


def _post(path, json_body):
    try:
        r = requests.post(f"{BITJITA}{path}", json=json_body,
                          headers={**HEADERS, "Content-Type": "application/json"},
                          timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[EmpirePlanner] POST {path}: {e}")
        return None


def _days_until(unix_ms):
    if not unix_ms:
        return None
    try:
        return max(0, (float(unix_ms) / 1000 - time.time()) / 86400)
    except Exception:
        return None


def _supply_status(days):
    if days is None: return "unknown"
    if days <= 3:    return "critical"
    if days <= 7:    return "warning"
    return "ok"


def _parse_citizens(data):
    if not data:
        return []
    result = []
    for c in data.get("citizens", []):
        raw = c.get("skills", {})
        skills = {}
        for sid_str, val in raw.items():
            try:
                sid = int(sid_str)
                skills[sid] = val.get("level", 0) if isinstance(val, dict) else int(val)
            except Exception:
                pass
        result.append({
            "entityId":     c.get("entityId", ""),
            "userName":     c.get("userName", "Unknown"),
            "totalLevel":   c.get("totalLevel", 0),
            "highestLevel": c.get("highestLevel", 0),
            "totalXP":      c.get("totalXP", 0),
            "skills":       skills,
        })
    result.sort(key=lambda x: x["totalLevel"], reverse=True)
    return result


def current_user():
    return session.get("ep_user")


def is_authorised(claim_id, owner_username):
    user = current_user()
    if not user:
        return False
    uname = user["username"]
    if uname.lower() == (owner_username or "").lower():
        return True
    return epdb.is_admin(claim_id, uname)


def is_emperor(claim_id, owner_username):
    user = current_user()
    if not user:
        return False
    return user["username"].lower() == (owner_username or "").lower()


# ── Main page ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    claim_id = request.args.get("claim_id", "").strip()

    claim = None
    citizens = []
    goals = {}
    db_admins = []
    error = None
    supply_days = None
    supply_status = "unknown"
    owner_username = ""

    if claim_id:
        claim_raw    = _get(f"/api/claims/{claim_id}")
        citizens_raw = _get(f"/api/claims/{claim_id}/citizens")

        if claim_raw is None:
            error = f"Could not load claim {claim_id}. Check the ID and try again."
        else:
            claim          = claim_raw.get("claim", claim_raw)
            owner_username = claim.get("ownerPlayerUsername", "")
            citizens       = _parse_citizens(citizens_raw)
            supply_days    = _days_until(claim.get("suppliesRunOut"))
            supply_status  = _supply_status(supply_days)
            goals          = epdb.get_goals(claim_id)
            db_admins      = epdb.get_admins(claim_id)

    user       = current_user()
    authorised = is_authorised(claim_id, owner_username) if (claim_id and claim) else False
    emperor    = is_emperor(claim_id, owner_username)    if (claim_id and claim) else False
    pending_code = session.pop("ep_pending_code", None)

    return render_template(
        "empire_planner/index.html",
        claim=claim,
        citizens=citizens,
        goals=goals,
        db_admins=db_admins,
        claim_id=claim_id,
        owner_username=owner_username,
        supply_days=supply_days,
        supply_status=supply_status,
        skill_names=SKILL_NAMES,
        error=error,
        user=user,
        authorised=authorised,
        emperor=emperor,
        pending_code=pending_code,
    )


# ── Auth: generate code ───────────────────────────────────────────────────────

@bp.route("/auth/start", methods=["POST"])
def auth_start():
    claim_id = request.form.get("claim_id", "").strip()
    if not claim_id:
        return redirect(url_for("empire_planner.index"))
    code = epdb.create_auth_code(claim_id)
    session["ep_pending_code"]  = code
    session["ep_pending_claim"] = claim_id
    return redirect(url_for("empire_planner.index", claim_id=claim_id))


# ── Auth: verify with Bitjita ─────────────────────────────────────────────────

@bp.route("/auth/verify", methods=["POST"])
def auth_verify():
    claim_id = request.form.get("claim_id", "").strip()
    code     = request.form.get("code", "").strip().upper()

    if not claim_id or not code:
        flash("Missing claim ID or code.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    result = _post("/api/auth/chat/validate", {"code": code})

    if not result or not result.get("success"):
        flash("Code not found or expired. Post the code in in-game chat channel 2 within 10 minutes.", "error")
        session["ep_pending_code"] = code
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    player    = result.get("player", {})
    username  = player.get("username", "")
    entity_id = player.get("entityId", "")

    if not username:
        flash("Could not retrieve your username from Bitjita.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    session["ep_user"] = {"username": username, "entity_id": entity_id}
    session.permanent  = True

    # Check claim ownership
    claim_raw = _get(f"/api/claims/{claim_id}")
    claim     = (claim_raw or {}).get("claim", claim_raw or {})
    owner     = claim.get("ownerPlayerUsername", "")

    if username.lower() == owner.lower():
        flash(f"⚔ Verified as Emperor {username}. Full admin access granted.", "success")
    elif epdb.is_admin(claim_id, username):
        flash(f"✓ Verified as {username}. Admin access confirmed.", "success")
    else:
        flash(f"✓ Verified as {username}. You are a member — the emperor ({owner}) can grant you admin access.", "info")

    return redirect(url_for("empire_planner.index", claim_id=claim_id))


# ── Auth: logout ──────────────────────────────────────────────────────────────

@bp.route("/auth/logout", methods=["POST"])
def auth_logout():
    claim_id = request.form.get("claim_id", "")
    session.pop("ep_user", None)
    return redirect(url_for("empire_planner.index", claim_id=claim_id))


# ── Goals: save ───────────────────────────────────────────────────────────────

@bp.route("/goals/save", methods=["POST"])
def goals_save():
    claim_id  = request.form.get("claim_id", "").strip()
    claim_raw = _get(f"/api/claims/{claim_id}")
    claim     = (claim_raw or {}).get("claim", claim_raw or {})
    owner     = claim.get("ownerPlayerUsername", "")

    if not is_authorised(claim_id, owner):
        flash("Verify your identity first.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    epdb.save_goals(claim_id, {
        "tier_target":     request.form.get("tier_target", "").strip(),
        "treasury_target": request.form.get("treasury_target", "").strip(),
        "supplies_target": request.form.get("supplies_target", "").strip(),
        "tiles_target":    request.form.get("tiles_target", "").strip(),
        "member_target":   request.form.get("member_target", "").strip(),
        "target_skill_id": request.form.get("target_skill_id", "").strip(),
        "min_skill_level": request.form.get("min_skill_level", "").strip(),
        "focus_skill_ids": request.form.get("focus_skill_ids", "").strip(),
    }, current_user()["username"])

    flash("Goals saved.", "success")
    return redirect(url_for("empire_planner.index", claim_id=claim_id) + "#tab-goals")


# ── Custom goals: add / delete (JSON API for JS) ──────────────────────────────

@bp.route("/goals/custom/add", methods=["POST"])
def custom_goal_add():
    claim_id = request.form.get("claim_id", "").strip()
    text     = request.form.get("text", "").strip()
    claim_raw = _get(f"/api/claims/{claim_id}")
    owner     = (claim_raw or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_authorised(claim_id, owner):
        return jsonify({"error": "Not authorised"}), 403
    if not text:
        return jsonify({"error": "Empty"}), 400
    goal_id = epdb.add_custom_goal(claim_id, text, current_user()["username"])
    return jsonify({"id": goal_id, "text": text})


@bp.route("/goals/custom/delete", methods=["POST"])
def custom_goal_delete():
    claim_id = request.form.get("claim_id", "").strip()
    goal_id  = request.form.get("goal_id", "")
    claim_raw = _get(f"/api/claims/{claim_id}")
    owner     = (claim_raw or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_authorised(claim_id, owner):
        return jsonify({"error": "Not authorised"}), 403
    epdb.delete_custom_goal(int(goal_id), claim_id)
    return jsonify({"ok": True})


# ── Admin management (emperor only) ──────────────────────────────────────────

@bp.route("/admin/grant", methods=["POST"])
def admin_grant():
    claim_id = request.form.get("claim_id", "").strip()
    username = request.form.get("username", "").strip()
    claim_raw = _get(f"/api/claims/{claim_id}")
    owner     = (claim_raw or {}).get("claim", {}).get("ownerPlayerUsername", "")

    if not is_emperor(claim_id, owner):
        flash("Only the emperor can grant admin access.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    if not username:
        flash("Enter a username.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    search    = _get("/api/players", params={"search": username, "limit": 5})
    players   = (search or {}).get("players", [])
    match     = next((p for p in players if p.get("username", "").lower() == username.lower()), None)
    entity_id = match["entityId"] if match else ""

    epdb.grant_admin(claim_id, username, entity_id, current_user()["username"])
    flash(f"Admin access granted to {username}.", "success")
    return redirect(url_for("empire_planner.index", claim_id=claim_id) + "#tab-admin")


@bp.route("/admin/revoke", methods=["POST"])
def admin_revoke():
    claim_id = request.form.get("claim_id", "").strip()
    username = request.form.get("username", "").strip()
    claim_raw = _get(f"/api/claims/{claim_id}")
    owner     = (claim_raw or {}).get("claim", {}).get("ownerPlayerUsername", "")

    if not is_emperor(claim_id, owner):
        flash("Only the emperor can revoke admin access.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    epdb.revoke_admin(claim_id, username)
    flash(f"Admin access revoked for {username}.", "success")
    return redirect(url_for("empire_planner.index", claim_id=claim_id) + "#tab-admin")
