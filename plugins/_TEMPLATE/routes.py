# ─────────────────────────────────────────────────────────────────────────────
# Plugin: my_plugin — routes.py
#
# HOW TO USE THIS TEMPLATE:
#   1. Copy this entire folder and rename it (e.g. plugins/my_plugin/)
#   2. Edit plugin.json with your plugin's name, icon, route_prefix, etc.
#   3. Rename the Blueprint below to match your plugin id (no spaces)
#   4. Add your routes below
#   5. Add your Jinja2 templates to templates/<plugin_id>/
#   6. Restart the app — your plugin appears in the sidebar automatically!
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, render_template, request
from core.bitjita import get_player, get_market_listings  # import whatever you need

bp = Blueprint(
    "my_plugin", __name__,          # <-- change "my_plugin" to your plugin id
    template_folder="templates",
    static_folder="static"
)


@bp.route("/")
def index():
    # Your logic here — call Bitjita API, process data, etc.
    data = {}
    return render_template("my_plugin/index.html", data=data)


# Add more routes as needed:
# @bp.route("/<item_id>")
# def detail(item_id):
#     ...
