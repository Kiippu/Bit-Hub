"""
Bitjita API client — aligned with https://bitjita.com/docs/api
Base: https://bitjita.com
All endpoints: /api/*
Requires header: x-app-identifier (identify your app)

Key facts from the docs:
  - Players are identified by entityId (numeric string), not username.
    To find a player by name, use /api/players?search=<name>
  - Market orders live at /api/market/orders with fields:
      priceThreshold, quantity, itemName, claimName, regionName, type (sell/buy)
  - Skills are returned inside /api/players/<entityId> as a `skills` array
  - Leaderboards: /api/leaderboard/skills, /api/leaderboard/playtime, /api/leaderboard/exploration
  - Claims: /api/claims
"""

import requests

BASE_URL = "https://bitjita.com"
TIMEOUT = 10
HEADERS = {
    "x-app-identifier": "bitcraft-hub",
    "Accept": "application/json",
}


def _get(endpoint, params=None):
    """Internal GET helper. Returns parsed JSON or None on failure."""
    try:
        url = f"{BASE_URL}{endpoint}"
        resp = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[BitjitaAPI] Error fetching {endpoint}: {e}")
        return None


# ── PLAYERS ──────────────────────────────────────────────────────────────────

def search_players(query, limit=20):
    """
    GET /api/players?search=<query>&limit=<limit>
    Returns: { players: [...], count, ... }
    Each player: entityId, username, totalLevel, totalXP, highestLevel
    """
    return _get("/api/players", params={"search": query, "limit": limit})


def get_player(entity_id):
    """
    GET /api/players/<entityId>
    Returns: { player, claims, empires, marketOrders, skills }
    skills items: { skillName, level, xp, nextLevelXp }
    """
    return _get(f"/api/players/{entity_id}")


def get_player_exploration(entity_id):
    """
    GET /api/players/<entityId>/exploration
    Returns: { bitmap, exploredChunksCount, regions, meta }
    """
    return _get(f"/api/players/{entity_id}/exploration")


# ── MARKET ───────────────────────────────────────────────────────────────────

def get_market_orders(item_name=None, order_type=None, limit=50, offset=0):
    """
    GET /api/market/orders
    Params: search, type (sell/buy), limit, offset
    Each order: entityId, itemId, itemName, priceThreshold, quantity,
                status, claimName, regionName, type, iconAssetName
    """
    params = {"limit": limit, "offset": offset}
    if item_name:
        params["search"] = item_name
    if order_type:
        params["type"] = order_type
    return _get("/api/market/orders", params=params)


def get_player_market_history(player_id, order_type=None, status=None, limit=50):
    """
    GET /api/market/player/<playerId>/history
    Params: type (sell/buy), status (OPEN/PARTIALLY_COMPLETED/COMPLETED), limit
    Returns: { playerId, playerUsername, sellOrderHistory, buyOrderHistory,
               totalSellOrders, totalBuyOrders }
    """
    params = {"limit": limit}
    if order_type:
        params["type"] = order_type
    if status:
        params["status"] = status
    return _get(f"/api/market/player/{player_id}/history", params=params)


def get_player_market_trades(player_id, trade_type=None, limit=50):
    """
    GET /api/market/player/<playerId>/trades
    Returns: { trades: [ { id, itemName, quantity, unitPrice, totalPrice,
                            sellerUsername, purchaserUsername, regionName, createdAt } ] }
    """
    params = {"limit": limit}
    if trade_type:
        params["type"] = trade_type
    return _get(f"/api/market/player/{player_id}/trades", params=params)


def get_market_prices_bulk(item_ids=None, cargo_ids=None):
    """
    POST /api/market/prices/bulk
    Returns lowestSellPrice, highestBuyPrice, spread, volume24h per item.
    """
    import json as _json
    try:
        body = {}
        if item_ids:
            body["itemIds"] = item_ids
        if cargo_ids:
            body["cargoIds"] = cargo_ids
        resp = requests.post(
            f"{BASE_URL}/api/market/prices/bulk",
            headers={**HEADERS, "Content-Type": "application/json"},
            data=_json.dumps(body),
            timeout=TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[BitjitaAPI] Error in bulk prices: {e}")
        return None


# ── LEADERBOARDS ─────────────────────────────────────────────────────────────

def get_leaderboard_skills(sort_by=None, page=1, page_size=50):
    """GET /api/leaderboard/skills — sortBy = skill id number"""
    params = {"page": page, "pageSize": page_size}
    if sort_by:
        params["sortBy"] = sort_by
    return _get("/api/leaderboard/skills", params=params)


def get_leaderboard_playtime(page=1, page_size=50):
    """GET /api/leaderboard/playtime"""
    return _get("/api/leaderboard/playtime", params={
        "sortBy": "timePlayed", "page": page, "pageSize": page_size
    })


def get_leaderboard_exploration(page=1, page_size=50):
    """GET /api/leaderboard/exploration"""
    return _get("/api/leaderboard/exploration", params={
        "sortBy": "totalExploredChunks", "page": page, "pageSize": page_size
    })


# ── CLAIMS ───────────────────────────────────────────────────────────────────

def get_claims(search=None, sort="supplies", limit=50):
    """
    GET /api/claims
    Sort: entityId, name, neutral, regionName, supplies, numTiles,
          locationX, locationZ, treasury, createdAt, updatedAt, tier
    Each claim: entityId, name, neutral, regionName, supplies, numTiles,
                treasury, ownerPlayerUsername, tier
    """
    params = {"sort": sort, "limit": limit}
    if search:
        params["search"] = search
    return _get("/api/claims", params=params)


def get_claim(entity_id):
    """GET /api/claims/<entityId> — full claim detail"""
    return _get(f"/api/claims/{entity_id}")


def get_claim_inventories(entity_id):
    """GET /api/claims/<entityId>/inventories"""
    return _get(f"/api/claims/{entity_id}/inventories")


# ── ITEMS ────────────────────────────────────────────────────────────────────

def get_item(item_id):
    """
    GET /api/items/<itemId>
    Returns: { item, craftingRecipes, extractionRecipes, relatedSkills,
               marketStats, recipesUsingItem }
    """
    return _get(f"/api/items/{item_id}")


def get_buildings():
    """GET /api/buildings — Returns: { buildings: array }"""
    return _get("/api/buildings")


# ── MOCK DATA (used when API unreachable) ────────────────────────────────────
# Field names match the real API response shapes

MOCK_ORDERS = [
    {
        "entityId": "1001", "type": "sell", "status": "OPEN",
        "itemName": "Iron Ingot", "itemId": 101,
        "priceThreshold": "12", "quantity": "100",
        "claimName": "Ironhold", "regionName": "Ashveil",
        "sellerUsername": "Gordan", "iconAssetName": "iron_ingot"
    },
    {
        "entityId": "1002", "type": "sell", "status": "OPEN",
        "itemName": "Oak Plank", "itemId": 202,
        "priceThreshold": "5", "quantity": "250",
        "claimName": "Maplewood", "regionName": "Verdania",
        "sellerUsername": "Wrenley", "iconAssetName": "oak_plank"
    },
    {
        "entityId": "1003", "type": "sell", "status": "OPEN",
        "itemName": "Stone Brick", "itemId": 303,
        "priceThreshold": "3", "quantity": "500",
        "claimName": "Greywall", "regionName": "Ashveil",
        "sellerUsername": "Aldric", "iconAssetName": "stone_brick"
    },
    {
        "entityId": "1004", "type": "buy", "status": "OPEN",
        "itemName": "Copper Wire", "itemId": 404,
        "priceThreshold": "8", "quantity": "75",
        "claimName": "Coppergate", "regionName": "Thornmere",
        "sellerUsername": "Petra", "iconAssetName": "copper_wire"
    },
    {
        "entityId": "1005", "type": "sell", "status": "OPEN",
        "itemName": "Leather", "itemId": 505,
        "priceThreshold": "15", "quantity": "40",
        "claimName": "Thornfield", "regionName": "Verdania",
        "sellerUsername": "Fenn", "iconAssetName": "leather"
    },
    {
        "entityId": "1006", "type": "sell", "status": "OPEN",
        "itemName": "Glass Pane", "itemId": 606,
        "priceThreshold": "22", "quantity": "30",
        "claimName": "Clearwater", "regionName": "Mirewood",
        "sellerUsername": "Sorin", "iconAssetName": "glass_pane"
    },
]

MOCK_PLAYER_SEARCH = {
    "players": [
        {
            "entityId": "360287970203109911",
            "username": "Gordan",
            "totalLevel": 227,
            "totalXP": 415100,
            "highestLevel": 44,
        }
    ],
    "count": 1
}

MOCK_PLAYER_PROFILE = {
    # Mirrors the exact real API shape from /api/players/<entityId>
    "player": {
        "entityId": "360287970203109911",
        "username": "Gordan",
        "timePlayed": 320400,
        "timeSignedIn": 380000,
        "location": {"name": "Ironhold", "regionId": 3},
        "experience": [
            {"skill_id": 2,  "quantity": 261432},   # Forestry
            {"skill_id": 3,  "quantity": 171538},   # Carpentry
            {"skill_id": 4,  "quantity": 6664},     # Masonry
            {"skill_id": 5,  "quantity": 32488},    # Mining
            {"skill_id": 6,  "quantity": 56695},    # Smithing
            {"skill_id": 7,  "quantity": 10220},    # Scholar
            {"skill_id": 8,  "quantity": 939379},   # Leatherworking
            {"skill_id": 9,  "quantity": 528654},   # Hunting
            {"skill_id": 10, "quantity": 4332},     # Tailoring
            {"skill_id": 11, "quantity": 0},        # Farming
            {"skill_id": 12, "quantity": 5637325},  # Fishing
            {"skill_id": 13, "quantity": 53596},    # Cooking
            {"skill_id": 14, "quantity": 27985},    # Foraging
            {"skill_id": 15, "quantity": 500},      # Construction
            {"skill_id": 17, "quantity": 62980},    # Taming
            {"skill_id": 18, "quantity": 59505},    # Slayer
            {"skill_id": 19, "quantity": 5000},     # Merchanting
            {"skill_id": 21, "quantity": 260762},   # Sailing
            {"skill_id": 22, "quantity": 0},        # Hexite Gathering (hidden)
            {"skill_id": 1,  "quantity": 0},        # ANY (hidden)
        ],
        "skillMap": {
            "1":  {"id": 1,  "name": "ANY",              "title": "",                  "skillCategoryStr": "None"},
            "2":  {"id": 2,  "name": "Forestry",         "title": "Forester",          "skillCategoryStr": "Profession"},
            "3":  {"id": 3,  "name": "Carpentry",        "title": "Carpenter",         "skillCategoryStr": "Profession"},
            "4":  {"id": 4,  "name": "Masonry",          "title": "Mason",             "skillCategoryStr": "Profession"},
            "5":  {"id": 5,  "name": "Mining",           "title": "Miner",             "skillCategoryStr": "Profession"},
            "6":  {"id": 6,  "name": "Smithing",         "title": "Smith",             "skillCategoryStr": "Profession"},
            "7":  {"id": 7,  "name": "Scholar",          "title": "Scholar",           "skillCategoryStr": "Profession"},
            "8":  {"id": 8,  "name": "Leatherworking",   "title": "Leatherworker",     "skillCategoryStr": "Profession"},
            "9":  {"id": 9,  "name": "Hunting",          "title": "Hunter",            "skillCategoryStr": "Profession"},
            "10": {"id": 10, "name": "Tailoring",        "title": "Tailor",            "skillCategoryStr": "Profession"},
            "11": {"id": 11, "name": "Farming",          "title": "Farmer",            "skillCategoryStr": "Profession"},
            "12": {"id": 12, "name": "Fishing",          "title": "Fisher",            "skillCategoryStr": "Profession"},
            "13": {"id": 13, "name": "Cooking",          "title": "Cook",              "skillCategoryStr": "Adventure"},
            "14": {"id": 14, "name": "Foraging",         "title": "Forager",           "skillCategoryStr": "Profession"},
            "15": {"id": 15, "name": "Construction",     "title": "Builder",           "skillCategoryStr": "Adventure"},
            "17": {"id": 17, "name": "Taming",           "title": "Tamer",             "skillCategoryStr": "Adventure"},
            "18": {"id": 18, "name": "Slayer",           "title": "Slayer",            "skillCategoryStr": "Adventure"},
            "19": {"id": 19, "name": "Merchanting",      "title": "Merchant",          "skillCategoryStr": "Adventure"},
            "21": {"id": 21, "name": "Sailing",          "title": "Sailor",            "skillCategoryStr": "Adventure"},
            "22": {"id": 22, "name": "Hexite Gathering", "title": "Hexite Gatherer",   "skillCategoryStr": "None"},
        },
        "claims": [
            {"entityId": "111", "name": "Ironhold", "regionName": "Ashveil",
             "tier": 2, "numTiles": 300, "treasury": "12500", "supplies": "8400"}
        ],
        "empireMemberships": [
            {"empireEntityId": "999", "empireName": "Iron League",
             "rank": 5, "rankTitle": "Lieutenant"}
        ],
    },
    "exploration": {
        "totalExploredChunks": 420,
        "totalPercentageExplored": 0.2625,
        "totalChunks": 160000,
        "regionCount": 12
    }
}
