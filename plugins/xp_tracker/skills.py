"""
Shared skill constants for the XP Tracker plugin.
Mirrors data from player_lookup but kept here to avoid cross-plugin imports.
"""

# Cumulative XP required to reach each level (index = level number, 80 levels)
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
    """Return (level, xp_into_level, xp_to_next, progress_pct)."""
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
    pct       = min(100.0, round((xp_into / xp_needed * 100), 1)) if xp_needed > 0 else 100.0
    return level, xp_into, xp_needed, pct
