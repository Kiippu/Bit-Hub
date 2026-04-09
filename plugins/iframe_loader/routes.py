from flask import Blueprint, render_template, request, abort

bp = Blueprint(
    "iframe_loader", __name__,
    template_folder="templates",
    static_folder="static"
)

# Pre-registered embeds — add your crew's tools here
# Each entry: { "id": str, "name": str, "url": str, "description": str }
EMBEDS = [
    {
        "id": "bitjita",
        "name": "Bitjita Market",
        "url": "https://bitjita.com",
        "description": "The official Bitjita market site."
    },
    # Add more tools here as you build them:
    # {
    #   "id": "my_tool",
    #   "name": "My Custom Tool",
    #   "url": "https://yoursite.com/tool",
    #   "description": "A cool thing we built."
    # },
]


@bp.route("/")
def index():
    return render_template("iframe_loader/index.html", embeds=EMBEDS)


@bp.route("/<embed_id>")
def view(embed_id):
    embed = next((e for e in EMBEDS if e["id"] == embed_id), None)
    if not embed:
        abort(404)
    return render_template("iframe_loader/view.html", embed=embed)
