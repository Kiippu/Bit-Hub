from flask import Flask, render_template, g
from core.plugin_loader import load_plugins

app = Flask(__name__)
app.secret_key = "bitcraft-hub-secret-change-me"

@app.template_filter('format_int')
def format_int(value):
    """Format a number with thousands separators: 10852 → 10,852"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

# Load all plugins and get their manifests
plugin_registry = load_plugins(app)

@app.context_processor
def inject_plugins():
    """Make plugin list available in ALL templates automatically."""
    return dict(plugins=plugin_registry)

@app.route("/")
def home():
    return render_template("home.html", plugins=plugin_registry)

if __name__ == "__main__":
    app.run(debug=True)
