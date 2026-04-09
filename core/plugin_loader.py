import importlib
import json
from pathlib import Path


def load_plugins(app):
    """
    Auto-discover and register all plugins in the /plugins directory.
    Each plugin folder must contain a plugin.json manifest and a routes.py with a Flask Blueprint named 'bp'.
    Returns the list of plugin manifests for nav rendering.
    """
    plugin_dir = Path(__file__).parent.parent / "plugins"
    registry = []

    for folder in sorted(plugin_dir.iterdir()):
        if not folder.is_dir():
            continue
        # Skip template/hidden folders
        if folder.name.startswith("_"):
            continue

        manifest_path = folder / "plugin.json"
        routes_path = folder / "routes.py"

        if not manifest_path.exists() or not routes_path.exists():
            continue

        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)

            module_name = f"plugins.{folder.name}.routes"
            mod = importlib.import_module(module_name)

            app.register_blueprint(
                mod.bp,
                url_prefix=manifest.get("route_prefix", f"/{folder.name}")
            )

            registry.append(manifest)
            print(f"[PluginLoader] Loaded: {manifest['name']} → {manifest['route_prefix']}")

        except Exception as e:
            print(f"[PluginLoader] Failed to load plugin '{folder.name}': {e}")

    return registry
