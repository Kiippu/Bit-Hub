# ⚔ BitCraft Hub

A modular Flask webapp for hosting BitCraft helper plugins — market browsers, player dashboards, XP trackers, and anything else your crew builds.

---

## 🗂 Project Structure

```
bitcraft-hub/
├── app.py                  ← Flask entry point
├── wsgi.py                 ← PythonAnywhere WSGI config
├── requirements.txt
├── core/
│   ├── plugin_loader.py    ← Auto-discovers plugins
│   └── bitjita.py          ← Shared Bitjita API client
├── plugins/
│   ├── market/             ← Market browser plugin
│   ├── player_lookup/      ← Player XP/skills plugin
│   ├── iframe_loader/      ← Embed external HTML tools
│   └── _TEMPLATE/          ← Copy this to make a new plugin
└── templates/
    ├── base.html           ← Main shell + sidebar
    └── home.html           ← Plugin gallery landing page
```

---

## 💻 Run Locally

### 1. Clone or download the project

```bash
cd bitcraft-hub
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the development server

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## 🌐 Deploy to PythonAnywhere (Free Tier)

### Step 1 — Create a PythonAnywhere account

Go to https://www.pythonanywhere.com and sign up for a free account.
Your site will be live at: **https://yourusername.pythonanywhere.com**

---

### Step 2 — Upload your project

**Option A — Via GitHub (recommended)**

In the PythonAnywhere **Bash console**:

```bash
git clone https://github.com/yourusername/bitcraft-hub.git
```

**Option B — Via ZIP upload**

1. Zip your project folder locally
2. In PythonAnywhere → Files tab → Upload the zip
3. In Bash console: `unzip bitcraft-hub.zip`

---

### Step 3 — Install dependencies

In the PythonAnywhere **Bash console**:

```bash
cd bitcraft-hub
pip3 install --user -r requirements.txt
```

---

### Step 4 — Set up the Web App

1. Go to the **Web** tab in PythonAnywhere
2. Click **"Add a new web app"**
3. Choose **"Manual configuration"**
4. Choose **Python 3.10** (or latest available)
5. Click Next through the rest

---

### Step 5 — Configure the WSGI file

In the Web tab, find **"WSGI configuration file"** and click it to edit.

**Delete everything** in the file and paste this:

```python
import sys
import os

project_home = '/home/YOURUSERNAME/bitcraft-hub'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application
```

Replace `YOURUSERNAME` with your actual PythonAnywhere username. Save the file.

---

### Step 6 — Reload and visit

Back in the **Web** tab, click the green **"Reload"** button.

Visit: **https://yourusername.pythonanywhere.com** 🎉

---

## 🔌 Adding a New Plugin

1. Copy `plugins/_TEMPLATE/` to a new folder, e.g. `plugins/crafting_calc/`
2. Edit `plugin.json` — set `id`, `name`, `icon`, `route_prefix`, etc.
3. Edit `routes.py` — rename the Blueprint, add your Flask routes
4. Add your Jinja2 template(s) in `templates/<your_plugin_id>/index.html`
5. Use `from core.bitjita import ...` to call the Bitjita API
6. Restart the app (or reload on PythonAnywhere) — it appears in the sidebar automatically

### Mates submitting plugins

The cleanest workflow is:
- Everyone forks/clones the repo
- Each person works in their own `plugins/<their_plugin>/` folder
- Submit a Pull Request — you merge and redeploy

---

## 🔗 Bitjita API

Edit `core/bitjita.py` and update `BASE_URL` once you know the live endpoint.

Available helpers:
- `get_market_listings(search=None)` — market listings
- `get_player(name)` — player profile
- `get_player_skills(name)` — skill breakdown
- `get_leaderboard(skill=None)` — leaderboard data
- `get_settlements()` — settlement list
- `get_world_info()` — world data

All return parsed JSON or `None` on failure.
Plugins fall back to mock data (defined in `bitjita.py`) while the API is offline.

---

## 🔄 Updating on PythonAnywhere

If using GitHub:

```bash
# In PythonAnywhere Bash console
cd bitcraft-hub
git pull
```

Then hit **Reload** in the Web tab. Done.

---

## 🛠 Tips

- PythonAnywhere free tier allows **1 web app** and **512MB storage**
- The app auto-discovers plugins on startup — no registration needed
- Folders starting with `_` in `/plugins` are ignored (e.g. `_TEMPLATE`)
- Use the **Iframe Loader** plugin to embed your crew's existing HTML sites without rewriting them
- Flask's `debug=True` is safe locally but **don't use it on PythonAnywhere** — it's already off for WSGI deployments
