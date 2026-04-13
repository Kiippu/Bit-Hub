"""
Empire Planner plugin — routes.py
"""

import requests, time
from flask import (Blueprint, render_template, request, session,
                   redirect, url_for, jsonify, flash)
from plugins.empire_planner import db as epdb

bp = Blueprint("empire_planner", __name__,
               template_folder="templates", static_folder="static")

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
PROFESSION_SKILLS = {2,3,4,5,6,7,8,9,10,11,12,14}
ADVENTURE_SKILLS  = {13,15,17,18,19,21}

# Ordered list for member table columns (profession first, then adventure)
SKILL_ORDER = [2,3,4,5,6,7,8,9,10,11,12,14,13,15,17,18,19,21]

# Per-skill column colours for the members table
SKILL_COLORS = {
    2:  {"hbg":"rgba(42,130,80,.28)",   "cbg":"rgba(42,130,80,.10)",   "txt":"#6dd4a4"},
    3:  {"hbg":"rgba(160,90,30,.28)",   "cbg":"rgba(160,90,30,.10)",   "txt":"#d4a060"},
    4:  {"hbg":"rgba(100,100,160,.28)", "cbg":"rgba(100,100,160,.10)", "txt":"#a0a0d0"},
    5:  {"hbg":"rgba(60,110,170,.28)",  "cbg":"rgba(60,110,170,.10)",  "txt":"#70b0d0"},
    6:  {"hbg":"rgba(110,110,100,.28)", "cbg":"rgba(110,110,100,.10)", "txt":"#b0b0a0"},
    7:  {"hbg":"rgba(80,100,180,.28)",  "cbg":"rgba(80,100,180,.10)",  "txt":"#90a0d8"},
    8:  {"hbg":"rgba(160,80,30,.28)",   "cbg":"rgba(160,80,30,.10)",   "txt":"#d09060"},
    9:  {"hbg":"rgba(90,130,30,.28)",   "cbg":"rgba(90,130,30,.10)",   "txt":"#a0c050"},
    10: {"hbg":"rgba(130,70,160,.28)",  "cbg":"rgba(130,70,160,.10)",  "txt":"#c090d0"},
    11: {"hbg":"rgba(50,150,80,.28)",   "cbg":"rgba(50,150,80,.10)",   "txt":"#70d090"},
    12: {"hbg":"rgba(40,120,160,.28)",  "cbg":"rgba(40,120,160,.10)",  "txt":"#60b0d0"},
    14: {"hbg":"rgba(100,150,50,.28)",  "cbg":"rgba(100,150,50,.10)",  "txt":"#b0d070"},
    13: {"hbg":"rgba(170,60,60,.28)",   "cbg":"rgba(170,60,60,.10)",   "txt":"#e08080"},
    15: {"hbg":"rgba(160,150,40,.28)",  "cbg":"rgba(160,150,40,.10)",  "txt":"#d0c860"},
    17: {"hbg":"rgba(40,160,150,.28)",  "cbg":"rgba(40,160,150,.10)",  "txt":"#60d0c0"},
    18: {"hbg":"rgba(170,40,70,.28)",   "cbg":"rgba(170,40,70,.10)",   "txt":"#e06080"},
    19: {"hbg":"rgba(170,140,30,.28)",  "cbg":"rgba(170,140,30,.10)",  "txt":"#d0c060"},
    21: {"hbg":"rgba(50,60,170,.28)",   "cbg":"rgba(50,60,170,.10)",   "txt":"#8090d0"},
}

# ── Server-side superadmins ───────────────────────────────────────────────────
# These usernames always have full admin access on every claim.
# Never sent to the frontend — checked server-side only.
_SUPERADMINS = {
    "snowpilla",   # case-insensitive
}

def _is_superadmin(username: str) -> bool:
    return (username or "").lower() in _SUPERADMINS


# ── HTTP helpers ──────────────────────────────────────────────────────────────

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
    if not unix_ms: return None
    try: return max(0, (float(unix_ms) / 1000 - time.time()) / 86400)
    except: return None

def _supply_status(days):
    if days is None: return "unknown"
    if days <= 3:    return "critical"
    if days <= 7:    return "warning"
    return "ok"

def _parse_citizens(data):
    if not data: return []
    result = []
    for c in data.get("citizens", []):
        raw = c.get("skills", {})
        skills = {}
        for sid_str, val in raw.items():
            try:
                sid = int(sid_str)
                skills[sid] = val.get("level", 0) if isinstance(val, dict) else int(val)
            except: pass
        highest_sid  = max(skills, key=skills.get, default=None)
        highest_name = SKILL_NAMES.get(highest_sid, f"Skill {highest_sid}") if highest_sid else "—"
        result.append({
            "entityId":     c.get("entityId", ""),
            "userName":     c.get("userName", "Unknown"),
            "totalLevel":   c.get("totalLevel", 0),
            "highestLevel": c.get("highestLevel", 0),
            "highestSkill": highest_name,
            "totalXP":      c.get("totalXP", 0),
            "skills":       skills,
        })
    result.sort(key=lambda x: x["totalLevel"], reverse=True)
    return result

def _parse_members(data):
    if not data: return {}
    return {m.get("userName", ""): m for m in data.get("members", [])}

def _parse_inventories(data):
    if not data: return []
    item_map  = {i["id"]: i for i in data.get("items", [])}
    cargo_map = {c["id"]: c for c in data.get("cargos", [])}
    buildings = []
    for b in data.get("buildings", []):
        enriched_inv = []
        for slot in b.get("inventory", []):
            contents = slot.get("contents")
            if not contents: continue
            iid   = contents.get("item_id")
            itype = contents.get("item_type", "item")
            meta  = (cargo_map if itype == "cargo" else item_map).get(iid, {})
            enriched_inv.append({
                "item_id":   iid,
                "item_type": itype,
                "quantity":  contents.get("quantity", 0),
                "locked":    slot.get("locked", False),
                "volume":    slot.get("volume", 0),
                "name":      meta.get("name", "Unknown"),
                "rarityStr": meta.get("rarityStr", ""),
                "tier":      meta.get("tier", 0),
                "tag":       meta.get("tag", ""),
                "icon":      meta.get("iconAssetName", ""),
            })
        buildings.append({
            "entityId":     b.get("entityId", ""),
            "buildingName": b.get("buildingName", ""),
            "nickname":     b.get("buildingNickname", ""),
            "locationX":    b.get("locationX", 0),
            "locationZ":    b.get("locationZ", 0),
            "icon":         b.get("iconAssetName", ""),
            "inventory":    enriched_inv,
            "slot_count":   len(enriched_inv),
            "total_items":  sum(s["quantity"] for s in enriched_inv),
        })
    return buildings


# ── Session helpers ───────────────────────────────────────────────────────────

def current_user():
    return session.get("ep_user")

def is_authorised(claim_id, owner_username):
    """True if logged-in user is: superadmin, claim owner, or DB-granted admin."""
    user = current_user()
    if not user: return False
    uname = user["username"]
    if _is_superadmin(uname):                                    return True
    if uname.lower() == (owner_username or "").lower():          return True
    return epdb.is_admin(claim_id, uname)

def is_emperor(claim_id, owner_username):
    """True if logged-in user is the claim owner OR a superadmin."""
    user = current_user()
    if not user: return False
    uname = user["username"]
    if _is_superadmin(uname):                             return True
    return uname.lower() == (owner_username or "").lower()


# ── Main page ─────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    claim_id = request.args.get("claim_id", "").strip()

    claim = None; citizens = []; goals = {}; db_admins = []; members_map = {}
    inventories = []; layout = None; error = None
    supply_days = None; supply_status = "unknown"; owner_username = ""

    if claim_id:
        claim_raw    = _get(f"/api/claims/{claim_id}")
        citizens_raw = _get(f"/api/claims/{claim_id}/citizens")
        members_raw  = _get(f"/api/claims/{claim_id}/members")
        inv_raw      = _get(f"/api/claims/{claim_id}/inventories")
        layout_raw   = _get(f"/api/claims/{claim_id}/layout")

        if claim_raw is None:
            error = f"Could not load claim {claim_id}. Check the ID and try again."
        else:
            claim          = claim_raw.get("claim", claim_raw)
            owner_username = claim.get("ownerPlayerUsername", "")
            citizens       = _parse_citizens(citizens_raw)
            members_map    = _parse_members(members_raw)
            inventories    = _parse_inventories(inv_raw)
            layout         = layout_raw
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
        claim=claim, citizens=citizens, goals=goals,
        db_admins=db_admins, members_map=members_map,
        inventories=inventories, layout=layout,
        claim_id=claim_id, owner_username=owner_username,
        supply_days=supply_days, supply_status=supply_status,
        skill_names=SKILL_NAMES,
        skill_order=SKILL_ORDER,
        skill_colors=SKILL_COLORS,
        profession_skills=list(PROFESSION_SKILLS),
        adventure_skills=list(ADVENTURE_SKILLS),
        error=error, user=user,
        authorised=authorised, emperor=emperor,
        pending_code=pending_code,
    )


# ── Auth routes ───────────────────────────────────────────────────────────────

@bp.route("/auth/start", methods=["POST"])
def auth_start():
    claim_id = request.form.get("claim_id", "").strip()
    if not claim_id: return redirect(url_for("empire_planner.index"))
    code = epdb.create_auth_code(claim_id)
    session["ep_pending_code"]  = code
    session["ep_pending_claim"] = claim_id
    return redirect(url_for("empire_planner.index", claim_id=claim_id))


@bp.route("/auth/verify", methods=["POST"])
def auth_verify():
    claim_id = request.form.get("claim_id", "").strip()
    code     = request.form.get("code", "").strip().upper()

    if not claim_id or not code:
        flash("Missing claim ID or code.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    result = _post("/api/auth/chat/validate", {"code": code})
    if not result or not result.get("success"):
        flash("Code not found or expired. Post in chat channel 2 within 10 minutes.", "error")
        session["ep_pending_code"] = code
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    player    = result.get("player", {})
    username  = player.get("username", "")
    entity_id = player.get("entityId", "")

    if not username:
        flash("Could not retrieve username from Bitjita.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))

    session["ep_user"] = {"username": username, "entity_id": entity_id}
    session.permanent  = True

    claim_raw = _get(f"/api/claims/{claim_id}")
    owner     = (claim_raw or {}).get("claim", {}).get("ownerPlayerUsername", "")

    # Flash message — superadmin status intentionally not mentioned
    if username.lower() == owner.lower():
        flash(f"⚔ Verified as Emperor {username}. Full access granted.", "success")
    elif _is_superadmin(username) or epdb.is_admin(claim_id, username):
        flash(f"✓ Verified as {username}. Admin access confirmed.", "success")
    else:
        flash(f"✓ Verified as {username}. Emperor ({owner}) can grant you admin access.", "info")

    return redirect(url_for("empire_planner.index", claim_id=claim_id))


@bp.route("/auth/logout", methods=["POST"])
def auth_logout():
    claim_id = request.form.get("claim_id", "")
    session.pop("ep_user", None)
    return redirect(url_for("empire_planner.index", claim_id=claim_id))


# ── Goals ─────────────────────────────────────────────────────────────────────

@bp.route("/goals/save", methods=["POST"])
def goals_save():
    claim_id  = request.form.get("claim_id", "").strip()
    owner     = (_get(f"/api/claims/{claim_id}") or {}).get("claim", {}).get("ownerPlayerUsername", "")
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


@bp.route("/goals/custom/add", methods=["POST"])
def custom_goal_add():
    claim_id = request.form.get("claim_id", "").strip()
    text     = request.form.get("text", "").strip()
    owner    = (_get(f"/api/claims/{claim_id}") or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_authorised(claim_id, owner): return jsonify({"error": "Not authorised"}), 403
    if not text: return jsonify({"error": "Empty"}), 400
    goal_id = epdb.add_custom_goal(claim_id, text, current_user()["username"])
    return jsonify({"id": goal_id, "text": text})


@bp.route("/goals/custom/delete", methods=["POST"])
def custom_goal_delete():
    claim_id = request.form.get("claim_id", "").strip()
    goal_id  = request.form.get("goal_id", "")
    owner    = (_get(f"/api/claims/{claim_id}") or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_authorised(claim_id, owner): return jsonify({"error": "Not authorised"}), 403
    epdb.delete_custom_goal(int(goal_id), claim_id)
    return jsonify({"ok": True})


# ── Admin management (emperor + superadmins) ──────────────────────────────────

@bp.route("/admin/grant", methods=["POST"])
def admin_grant():
    claim_id = request.form.get("claim_id", "").strip()
    username = request.form.get("username", "").strip()
    owner    = (_get(f"/api/claims/{claim_id}") or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_emperor(claim_id, owner):
        flash("Only the emperor can grant admin access.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))
    search    = _get("/api/players", params={"search": username, "limit": 5})
    players   = (search or {}).get("players", [])
    match     = next((p for p in players if p.get("username","").lower() == username.lower()), None)
    entity_id = match["entityId"] if match else ""
    epdb.grant_admin(claim_id, username, entity_id, current_user()["username"])
    flash(f"Admin access granted to {username}.", "success")
    return redirect(url_for("empire_planner.index", claim_id=claim_id) + "#tab-admin")


@bp.route("/admin/revoke", methods=["POST"])
def admin_revoke():
    claim_id = request.form.get("claim_id", "").strip()
    username = request.form.get("username", "").strip()
    owner    = (_get(f"/api/claims/{claim_id}") or {}).get("claim", {}).get("ownerPlayerUsername", "")
    if not is_emperor(claim_id, owner):
        flash("Only the emperor can revoke admin access.", "error")
        return redirect(url_for("empire_planner.index", claim_id=claim_id))
    epdb.revoke_admin(claim_id, username)
    flash(f"Admin access revoked for {username}.", "success")
    return redirect(url_for("empire_planner.index", claim_id=claim_id) + "#tab-admin")


# ── API proxy for JS calls ────────────────────────────────────────────────────

@bp.route("/api/search_claims")
def api_search_claims():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"claims": []})
    data = _get("/api/claims", params={"q": q, "limit": 10})
    if isinstance(data, list):
        claims = data
    else:
        claims = (data or {}).get("claims", [])
    return jsonify({"claims": [
        {"id": c.get("entityId",""), "name": c.get("name",""),
         "owner": c.get("ownerPlayerUsername",""), "tier": c.get("tier",0)}
        for c in claims
    ]})


@bp.route("/api/layout/<claim_id>")
def api_layout(claim_id):
    data = _get(f"/api/claims/{claim_id}/layout")
    return jsonify(data or {"error": "not found"}), 200 if data else 502


@bp.route("/api/inventories/<claim_id>")
def api_inventories(claim_id):
    data = _get(f"/api/claims/{claim_id}/inventories")
    if data:
        return jsonify({"buildings": _parse_inventories(data)})
    return jsonify({"error": "not found"}), 502
