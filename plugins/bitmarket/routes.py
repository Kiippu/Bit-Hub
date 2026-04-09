"""
BitMarket plugin routes.
Flask acts as a server-side proxy to bitjita.com — no CORS issues,
no need for Node/proxy.js. All JS in the template calls /bitmarket/api/*
which this blueprint forwards to bitjita.com and returns as JSON.
"""

import requests
from flask import Blueprint, render_template, jsonify, request as flask_request

bp = Blueprint(
    "bitmarket", __name__,
    template_folder="templates",
    static_folder="static"
)

BITJITA = "https://bitjita.com"
TIMEOUT = 12
HEADERS = {
    "User-Agent": "BitJita (bitcraft-hub)",
    "Accept": "application/json",
}


def _proxy(path, params=None):
    """Forward a GET request to bitjita.com and return parsed JSON or an error dict."""
    try:
        url = f"{BITJITA}{path}"
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json(), r.status_code
    except requests.exceptions.HTTPError as e:
        return {"error": str(e), "status": e.response.status_code}, e.response.status_code
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 502


# ── Main page ────────────────────────────────────────────────────────────────

@bp.route("/")
def index():
    return render_template("bitmarket/index.html")


# ── API proxy routes — JS calls these, Flask forwards to bitjita ─────────────

@bp.route("/api/market")
def market():
    params = {k: v for k, v in flask_request.args.items()}
    data, status = _proxy("/api/market", params)
    return jsonify(data), status


@bp.route("/api/market/orders")
def market_orders():
    params = {k: v for k, v in flask_request.args.items()}
    data, status = _proxy("/api/market/orders", params)
    return jsonify(data), status


@bp.route("/api/market/deals")
def market_deals():
    data, status = _proxy("/api/market/deals")
    return jsonify(data), status


@bp.route("/api/market/<string:item_type>/<int:item_id>")
def market_item(item_type, item_id):
    """Order book for a specific item/cargo: /api/market/item/123 or /api/market/cargo/123"""
    data, status = _proxy(f"/api/market/{item_type}/{item_id}")
    return jsonify(data), status


@bp.route("/api/market/<string:item_type>s/<int:item_id>/price-history")
def price_history(item_type, item_id):
    """Price history: /api/market/items/123/price-history or /api/market/cargos/123/price-history"""
    params = {k: v for k, v in flask_request.args.items()}
    data, status = _proxy(f"/api/market/{item_type}s/{item_id}/price-history", params)
    return jsonify(data), status


@bp.route("/api/regions")
def regions():
    data, status = _proxy("/api/regions")
    return jsonify(data), status
