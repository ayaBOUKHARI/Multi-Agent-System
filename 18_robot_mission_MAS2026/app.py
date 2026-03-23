# Group: 18 | Date: 2026-03-23 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
"""
app.py – Flask web server for the Robot Mission simulation.

Run:
    python app.py
Then open  http://127.0.0.1:5000  in your browser.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, jsonify, request
from model import RobotMission
from objects import WasteAgent, WasteDisposalZone
from agents import GreenAgent, YellowAgent, RedAgent

app = Flask(__name__)

_model = None   # current simulation instance
_steps = 0      # manual step counter (model.step() does not auto-increment)
MAX_STEPS = 1000


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize():
    """Convert current model state to a JSON-serialisable dict."""
    m = _model
    if m is None:
        return {"ready": False}

    wastes, robots = [], []

    for cell_content, (x, y) in m.grid.coord_iter():
        for agent in cell_content:
            if isinstance(agent, WasteAgent):
                wastes.append({"x": x, "y": y, "type": agent.waste_type})

            elif isinstance(agent, (GreenAgent, YellowAgent, RedAgent)):
                rtype = ("green"  if isinstance(agent, GreenAgent)  else
                         "yellow" if isinstance(agent, YellowAgent) else "red")
                # inventory holds strings (e.g. "green", "yellow", "red")
                robots.append({
                    "x": x, "y": y, "type": rtype,
                    "inventory": [w[0].upper() for w in agent.knowledge["inventory"]],
                })

    return {
        "ready":        True,
        "step":         _steps,
        "width":        m.width,
        "height":       m.height,
        "z1_end":       m.z1_max_x,   # renamed for frontend compatibility
        "z2_end":       m.z2_max_x,   # renamed for frontend compatibility
        "disposal":     {"x": m.disposal_pos[0], "y": m.disposal_pos[1]},
        "wastes":       wastes,
        "robots":       robots,
        "green_count":  m._count_waste("green"),
        "yellow_count": m._count_waste("yellow"),
        "red_count":    m._count_waste("red"),
        "disposed":     m.disposed_count,
        "finished":     m.is_done() or _steps >= MAX_STEPS,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/reset", methods=["POST"])
def reset():
    global _model, _steps
    d = request.get_json(silent=True) or {}
    _model = RobotMission(
        width           = 15,
        height          = 10,
        n_green_robots  = max(1, int(d.get("green_robots",   3))),
        n_yellow_robots = max(1, int(d.get("yellow_robots",  3))),
        n_red_robots    = max(1, int(d.get("red_robots",     3))),
        n_green_wastes  = max(4, int(d.get("green_wastes",  12))),
        seed            = int(d.get("seed", 42)),
    )
    _steps = 0
    return jsonify(_serialize())


@app.route("/api/step", methods=["POST"])
def step():
    global _steps
    if _model and not (_model.is_done() or _steps >= MAX_STEPS):
        _model.step()
        _steps += 1
    return jsonify(_serialize())


@app.route("/api/state")
def state():
    return jsonify(_serialize())


if __name__ == "__main__":
    app.run(debug=False, port=5000)
