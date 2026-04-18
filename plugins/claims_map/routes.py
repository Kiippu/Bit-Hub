from flask import Blueprint, render_template, jsonify, request
from core.bitjita import get_claims

bp = Blueprint(
    "claims_map", __name__,
    template_folder="templates",
    static_folder="static"
)

MOCK_CLAIMS = [
    {
        "entityId": "2001", "name": "Ironhold",
        "ownerPlayerUsername": "Gordan", "neutral": False,
        "regionName": "Ashveil", "tier": 2,
        "numTiles": 300, "treasury": "12500", "supplies": "8400",
        "locationX": 1024.0, "locationZ": -512.0
    },
    {
        "entityId": "2002", "name": "Maplewood",
        "ownerPlayerUsername": "Wrenley", "neutral": False,
        "regionName": "Verdania", "tier": 1,
        "numTiles": 150, "treasury": "4200", "supplies": "3100",
        "locationX": -880.0, "locationZ": 220.0
    },
    {
        "entityId": "2003", "name": "Greywall",
        "ownerPlayerUsername": "Aldric", "neutral": True,
        "regionName": "Ashveil", "tier": 3,
        "numTiles": 600, "treasury": "55000", "supplies": "27000",
        "locationX": 340.0, "locationZ": 1750.0
    },
    {
        "entityId": "2004", "name": "Coppergate",
        "ownerPlayerUsername": "Petra", "neutral": False,
        "regionName": "Thornmere", "tier": 1,
        "numTiles": 120, "treasury": "1800", "supplies": "950",
        "locationX": -1600.0, "locationZ": -900.0
    },
    {
        "entityId": "2005", "name": "Thornfield",
        "ownerPlayerUsername": "Fenn", "neutral": False,
        "regionName": "Verdania", "tier": 2,
        "numTiles": 250, "treasury": "9800", "supplies": "5500",
        "locationX": 780.0, "locationZ": 630.0
    },
    {
        "entityId": "2006", "name": "Clearwater",
        "ownerPlayerUsername": "Sorin", "neutral": True,
        "regionName": "Mirewood", "tier": 1,
        "numTiles": 90, "treasury": "600", "supplies": "310",
        "locationX": -200.0, "locationZ": -1400.0
    },
    {
        "entityId": "2007", "name": "Emberveil",
        "ownerPlayerUsername": "Calix", "neutral": False,
        "regionName": "Ashveil", "tier": 3,
        "numTiles": 450, "treasury": "38000", "supplies": "19500",
        "locationX": 2100.0, "locationZ": 80.0
    },
    {
        "entityId": "2008", "name": "Driftstone",
        "ownerPlayerUsername": None, "neutral": True,
        "regionName": "Mirewood", "tier": 1,
        "numTiles": 60, "treasury": "200", "supplies": "120",
        "locationX": None, "locationZ": None
    },
]


@bp.route("/")
def index():
    return render_template("claims_map/index.html")


@bp.route("/api/claims")
def api_claims():
    data = get_claims(limit=5000, sort="supplies")

    if data is None:
        claims = MOCK_CLAIMS
        using_mock = True
    else:
        if isinstance(data, list):
            claims = data
        else:
            claims = data.get("claims", data.get("data", []))
        using_mock = False

    map_claims = [
        c for c in claims
        if c.get("locationX") is not None and c.get("locationZ") is not None
    ]

    return jsonify({
        "claims": claims,
        "map_claims": map_claims,
        "using_mock": using_mock,
    })
