"""
Shared skill constants for the XP Tracker plugin.
Mirrors data from player_lookup but kept here to avoid cross-plugin imports.
"""

# Cumulative XP required to reach each level (index 0 = level 1, 120 levels total)
# Source: https://bitjita.com/static/experience/levels.json
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

# Ordered list of displayable skills (excludes hidden ANY/Hexite by default)
DISPLAY_SKILLS = [
    {"id": 2,  "name": "Forestry",       "category": "Profession"},
    {"id": 3,  "name": "Carpentry",      "category": "Profession"},
    {"id": 4,  "name": "Masonry",        "category": "Profession"},
    {"id": 5,  "name": "Mining",         "category": "Profession"},
    {"id": 6,  "name": "Smithing",       "category": "Profession"},
    {"id": 7,  "name": "Scholar",        "category": "Profession"},
    {"id": 8,  "name": "Leatherworking", "category": "Profession"},
    {"id": 9,  "name": "Hunting",        "category": "Profession"},
    {"id": 10, "name": "Tailoring",      "category": "Profession"},
    {"id": 11, "name": "Farming",        "category": "Profession"},
    {"id": 12, "name": "Fishing",        "category": "Profession"},
    {"id": 13, "name": "Cooking",        "category": "Adventure"},
    {"id": 14, "name": "Foraging",       "category": "Profession"},
    {"id": 15, "name": "Construction",   "category": "Adventure"},
    {"id": 17, "name": "Taming",         "category": "Adventure"},
    {"id": 18, "name": "Slayer",         "category": "Adventure"},
    {"id": 19, "name": "Merchanting",    "category": "Adventure"},
    {"id": 21, "name": "Sailing",        "category": "Adventure"},
]

# Map skill_id -> name for quick lookups
SKILL_ID_TO_NAME = {s["id"]: s["name"] for s in DISPLAY_SKILLS}
SKILL_NAME_TO_ID = {s["name"]: s["id"] for s in DISPLAY_SKILLS}


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
    pct       = min(100.0, round((xp_into / xp_needed * 100), 1)) if xp_needed > 0 else 100.0
    return idx + 1, xp_into, xp_needed, pct
