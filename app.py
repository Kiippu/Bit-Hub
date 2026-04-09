import os
import secrets
from flask import Flask, render_template
from core.plugin_loader import load_plugins

app = Flask(__name__)

# ── Secret key (persisted to disk so sessions survive restarts) ───────────────
_KEY_FILE = os.path.join(os.path.dirname(__file__), "data", ".secret_key")

def _load_secret_key():
    os.makedirs(os.path.dirname(_KEY_FILE), exist_ok=True)
    if os.path.exists(_KEY_FILE):
        return open(_KEY_FILE).read().strip()
    key = secrets.token_hex(32)
    open(_KEY_FILE, "w").write(key)
    return key

app.secret_key = os.environ.get("BITCRAFT_HUB_SECRET", _load_secret_key())
app.config["SESSION_COOKIE_HTTPONLY"]    = True
app.config["SESSION_COOKIE_SAMESITE"]   = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = 86400 * 7   # 7-day sessions

# ── Template filter ───────────────────────────────────────────────────────────
@app.template_filter("format_int")
def format_int(value):
    """Format an integer with thousands separators: 10852 → 10,852"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

# ── Initialise empire planner DB ──────────────────────────────────────────────
from plugins.empire_planner import db as epdb
epdb.init_db()

# ── Load plugins ──────────────────────────────────────────────────────────────
plugin_registry = load_plugins(app)

@app.context_processor
def inject_plugins():
    return dict(plugins=plugin_registry)

@app.route("/")
def home():
    return render_template("home.html", plugins=plugin_registry)

if __name__ == "__main__":
    app.run(debug=True)
