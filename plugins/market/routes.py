from flask import Blueprint, render_template, request
from core.bitjita import get_market_orders, MOCK_ORDERS

bp = Blueprint(
    "market", __name__,
    template_folder="templates",
    static_folder="static"
)


@bp.route("/")
def index():
    search = request.args.get("q", "").strip()
    order_type = request.args.get("type", "")  # 'sell', 'buy', or ''

    data = get_market_orders(
        item_name=search if search else None,
        order_type=order_type if order_type else None,
        limit=100
    )

    if data is None:
        # Fall back to mock data
        orders = MOCK_ORDERS
        if search:
            orders = [o for o in orders if search.lower() in o["itemName"].lower()]
        if order_type:
            orders = [o for o in orders if o["type"] == order_type]
        using_mock = True
    else:
        # Real API may return a list directly or wrapped in a key — handle both
        if isinstance(data, list):
            orders = data
        else:
            orders = data.get("orders", data.get("data", []))
        using_mock = False

    return render_template(
        "market/index.html",
        orders=orders,
        search=search,
        order_type=order_type,
        using_mock=using_mock
    )
