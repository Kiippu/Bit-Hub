from flask import Blueprint, render_template, request
from core.bitjita import (
    search_players, get_player,
    MOCK_PLAYER_SEARCH, MOCK_PLAYER_PROFILE
)

bp = Blueprint(
    "player_lookup", __name__,
    template_folder="templates",
    static_folder="static"
)

# ── Skill icons ───────────────────────────────────────────────────────────────
SKILL_ICONS = {
    "Forestry":         "🪵",
    "Carpentry":        "🪚",
    "Masonry":          "🧱",
    "Mining":           "⛏",
    "Smithing":         "🔨",
    "Scholar":          "📚",
    "Leatherworking":   "🧤",
    "Hunting":          "🏹",
    "Tailoring":        "🧵",
    "Farming":          "🌾",
    "Fishing":          "🎣",
    "Cooking":          "🍳",
    "Foraging":         "🍄",
    "Construction":     "🏗",
    "Taming":           "🐾",
    "Slayer":           "⚔",
    "Merchanting":      "🪙",
    "Sailing":          "⛵",
    "Hexite Gathering": "💎",
}

# ── XP thresholds — total XP required to reach each level ────────────────────
XP_PER_LEVEL = [
    0,        100,      250,      500,      900,      1500,     2300,     3300,
    4600,     6200,     8200,     10700,    13700,    17300,    21600,    26700,
    32700,    39700,    47800,    57100,    67700,    79800,    93400,    108800,
    126000,   145200,   166700,   190400,   216800,   246000,   278000,   313000,
    352000,   394000,   440000,   490000,   544000,   603000,   667000,   737000,
    813000,   896000,   986000,   1084000,  1191000,  1307000,  1434000,  1572000,
    1722000,  1885000,  2062000,  2254000,  2463000,  2690000,  2936000,  3203000,
    3492000,  3805000,  4144000,  4511000,  4908000,  5338000,  5804000,  6308000,
    6854000,  7444000,  8083000,  8774000,  9521000,  10329000, 11202000, 12146000,
    13165000, 14265000, 15451000, 16729000, 18105000, 19585000, 21177000, 22888000,
]


def xp_to_level(xp):
    level = 0
    for i, threshold in enumerate(XP_PER_LEVEL):
        if xp >= threshold:
            level = i
        else:
            break
    level = min(level, len(XP_PER_LEVEL) - 2)
    xp_this   = XP_PER_LEVEL[level]
    xp_next   = XP_PER_LEVEL[level + 1] if level + 1 < len(XP_PER_LEVEL) else XP_PER_LEVEL[-1]
    xp_into   = xp - xp_this
    xp_needed = xp_next - xp_this
    pct       = round((xp_into / xp_needed * 100), 1) if xp_needed > 0 else 100.0
    return level, xp_into, xp_needed, pct


def build_skills(profile_data):
    """
    Build skill list from real API shape:
      profile_data['player']['experience'] = [{ skill_id, quantity }, ...]
      profile_data['player']['skillMap']   = { "id": { name, title, skillCategoryStr } }
    """
    player     = profile_data.get("player", {})
    experience = player.get("experience", [])
    skill_map  = player.get("skillMap", {})

    skills = []
    for entry in experience:
        sid      = entry.get("skill_id")
        quantity = entry.get("quantity", 0)
        info     = skill_map.get(str(sid), {})
        name     = info.get("name", f"Skill {sid}")
        category = info.get("skillCategoryStr", "")

        if name in ("ANY", "") or category == "None":
            continue

        level, xp_into, xp_needed, pct = xp_to_level(quantity)
        skills.append({
            "skill_id": sid,
            "name":     name,
            "title":    info.get("title", ""),
            "category": category,
            "total_xp": quantity,
            "level":    level,
            "xp_into":  xp_into,
            "xp_needed": xp_needed,
            "pct":      pct,
        })

    cat_order = {"Profession": 0, "Adventure": 1}
    skills.sort(key=lambda s: (cat_order.get(s["category"], 9), -s["level"]))
    return skills


def extract_profile(profile_data):
    """
    Real API embeds everything inside player{}.
    Pull exploration out so the template can access it cleanly as profile.exploration.
    """
    player = profile_data.get("player", {})
    return {
        "player":      player,
        "exploration": player.get("exploration"),
    }


@bp.route("/", methods=["GET"])
def index():
    name           = request.args.get("name", "").strip()
    profile        = None
    skills         = []
    search_results = None
    using_mock     = False
    error          = None

    if name:
        search_data = search_players(name)

        if search_data is None:
            if name.lower() == "gordan":
                search_data = MOCK_PLAYER_SEARCH
                using_mock  = True
            else:
                error = f'API unreachable. Try "Gordan" for mock data.'
        elif "__http_error__" in search_data:
            error = f'API error looking up "{name}". Please try again.'
            search_data = None

        if search_data:
            players = search_data.get("players", [])
            if not players:
                error = f'No player found matching "{name}".'
            elif len(players) == 1:
                raw = get_player(players[0]["entityId"])
                if raw is None and using_mock:
                    raw = MOCK_PLAYER_PROFILE
                if raw:
                    profile = extract_profile(raw)
                    skills  = build_skills(raw)
                else:
                    error = f'Could not load profile for "{players[0].get("username", name)}".'
            else:
                search_results = players

    return render_template(
        "player_lookup/index.html",
        profile=profile,
        skills=skills,
        search_results=search_results,
        search_name=name,
        using_mock=using_mock,
        error=error,
        skill_icons=SKILL_ICONS,
    )


@bp.route("/id/<entity_id>")
def by_id(entity_id):
    raw    = get_player(entity_id)
    error  = None
    profile = None
    skills  = []
    if raw:
        profile = extract_profile(raw)
        skills  = build_skills(raw)
    else:
        error = f"Could not load player profile for entityId {entity_id}."
    return render_template(
        "player_lookup/index.html",
        profile=profile,
        skills=skills,
        search_results=None,
        search_name="",
        using_mock=False,
        error=error,
        skill_icons=SKILL_ICONS,
    )
