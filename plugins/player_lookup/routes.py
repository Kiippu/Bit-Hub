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
# Source: https://bitjita.com/static/experience/levels.json (index 0 = level 1, 120 levels)
XP_PER_LEVEL = [
    0,          520,        1100,       1740,       2460,       3270,       4170,       5170,
    6290,       7540,       8930,       10490,      12220,      14160,      16320,      18730,
    21420,      24410,      27760,      31490,      35660,      40310,      45490,      51280,
    57740,      64940,      72980,      81940,      91950,      103110,     115560,     129460,
    144960,     162260,     181560,     203100,     227130,     253930,     283840,     317220,
    354450,     396000,     442350,     494070,     551770,     616150,     687980,     768130,
    857560,     957330,     1068650,    1192860,    1331440,    1486060,    1658570,    1851060,
    2065820,    2305430,    2572780,    2871080,    3203890,    3575230,    3989550,    4451810,
    4967590,    5543050,    6185120,    6901500,    7700800,    8592610,    9587630,    10697810,
    11936490,   13318540,   14860540,   16581010,   18500600,   20642370,   23032020,   25698250,
    28673070,   31992200,   35695470,   39827360,   44437480,   49581160,   55320170,   61723410,
    68867770,   76839000,   85732810,   95656000,   106727680,  119080790,  132863630,  148241700,
    165399620,  184543380,  205902840,  229734400,  256324240,  285991580,  319092580,  356024680,
    397231240,  443207040,  494504080,  551738200,  615596560,  686845760,  766341360,  855037760,
    953999760,  1064415520, 1187610880, 1325064640, 1478427360, 1649540000, 1840457120, 2053471040,
]


def xp_to_level(xp):
    """Return (level, xp_into_level, xp_to_next, progress_pct). Level is 1-based (1–120)."""
    idx = 0
    for i, threshold in enumerate(XP_PER_LEVEL):
        if xp >= threshold:
            idx = i
        else:
            break
    idx       = min(idx, len(XP_PER_LEVEL) - 2)
    xp_this   = XP_PER_LEVEL[idx]
    xp_next   = XP_PER_LEVEL[idx + 1]
    xp_into   = xp - xp_this
    xp_needed = xp_next - xp_this
    pct       = round((xp_into / xp_needed * 100), 1) if xp_needed > 0 else 100.0
    return idx + 1, xp_into, xp_needed, pct


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
