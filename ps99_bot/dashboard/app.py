"""
Local status dashboard. Serves one page that polls /api/status every
few seconds and renders one card per account, merging live zone/state
from the bots with currency data from the API poller.

Run from the project root: python dashboard/app.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import status_store

from flask import Flask, jsonify, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(status_store.get_all_status())


if __name__ == "__main__":
    status_store.init_db()
    app.run(host="0.0.0.0", port=5050, debug=False)
