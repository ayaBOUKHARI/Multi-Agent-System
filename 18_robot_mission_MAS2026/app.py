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

_model          = None   # current simulation instance
_steps          = 0      # manual step counter
_msg_log        = []     # rolling message log (last 60 entries)
_total_messages = 0      # total messages sent since last reset
MAX_STEPS       = 1000
MSG_LOG_SIZE    = 60


# ── Message interception ──────────────────────────────────────────────────────

def _wrap_send_message(model):
    """Monkey-patch model._do_send_message to capture all outgoing messages."""
    original = model._do_send_message

    def _intercepted(agent, recipients, message):
        global _msg_log, _total_messages
        _total_messages += 1
        content = message.get("content", {})
        entry = {
            "step":  _steps,
            "from":  f"{agent.color[0].upper()}#{agent.unique_id}",
            "color": agent.color,
            "perf":  message.get("performative", "?"),
            "type":  content.get("type", "?"),
            "pos":   content.get("pos"),   # [x, y] when present (waste_at / has_unpaired)
            "waste": content.get("waste"), # waste type when present
            "to":    "broadcast" if recipients is None
                     else (message.get("to_color", agent.color) + " broadcast"
                           if recipients is None else f"#{recipients[0]}"),
        }
        _msg_log.append(entry)
        if len(_msg_log) > MSG_LOG_SIZE:
            _msg_log.pop(0)
        return original(agent, recipients, message)

    model._do_send_message = _intercepted


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
                partner_pos = agent.knowledge.get("partner_pos")
                robots.append({
                    "x": x, "y": y, "type": rtype,
                    "id":           agent.unique_id,
                    "inventory":    [w[0].upper() for w in agent.knowledge["inventory"]],
                    "handoff_role": agent.knowledge.get("handoff_role"),
                    "partner_pos":  list(partner_pos) if partner_pos else None,
                })

    return {
        "ready":          True,
        "step":           _steps,
        "width":          m.width,
        "height":         m.height,
        "z1_end":         m.z1_max_x,
        "z2_end":         m.z2_max_x,
        "disposal":       {"x": m.disposal_pos[0], "y": m.disposal_pos[1]},
        "wastes":         wastes,
        "robots":         robots,
        "green_count":    m._count_waste("green"),
        "yellow_count":   m._count_waste("yellow"),
        "red_count":      m._count_waste("red"),
        "disposed":       m.disposed_count,
        "finished":       m.is_done() or _steps >= MAX_STEPS,
        "total_messages": _total_messages,
        "msg_log":        list(reversed(_msg_log[-20:])),  # last 20, newest first
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/reset", methods=["POST"])
def reset():
    global _model, _steps, _total_messages
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
    _wrap_send_message(_model)
    _steps = 0
    _msg_log.clear()
    _total_messages = 0
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
