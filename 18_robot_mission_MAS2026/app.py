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

def _board_snapshot_with_candidates(m, board):
    """
    Snapshot board state with candidate heaps per request.

    For each request:
      - list eligible agents with their cost and step_n
      - expose the current best candidate (min cost, then min step_n)
    """
    active = sorted(board._requests.values(), key=lambda r: r.step_posted)
    requests = []
    robots = [a for a in m.get_robot_agents()]

    for req in active:
        candidates = []
        for robot in robots:
            if robot.color != req.target_color or robot.unique_id == req.sender_id:
                continue
            cost = robot._compute_cost(req)
            if cost < float("inf"):
                candidates.append({
                    "label": robot.label,
                    "cost": cost,
                    "step_n": robot.steps_taken,
                })
        candidates.sort(key=lambda c: (c["cost"], c["step_n"], c["label"]))

        req_data = req.to_dict(m.current_step)
        req_data["candidate_heap"] = candidates
        req_data["best_candidate"] = candidates[0] if candidates else None
        requests.append(req_data)

    history = []
    for h in board.history[-25:]:
        item = dict(h)
        # Cost currently represents the selection cost to take/reach the request.
        item["cost_to_reach"] = h.get("cost")
        # Approximation for "come + deposit": one extra action to deposit.
        item["cost_come_and_deposit"] = (h.get("cost") + 1) if h.get("cost") is not None else None
        history.append(item)

    return {
        "name": board.name,
        "count": len(requests),
        "requests": requests,
        "history": history,
    }


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
                robots.append({
                    "x": x, "y": y, "type": rtype,
                    "label": agent.label,
                    "inventory": [w[0].upper() for w in agent.knowledge["inventory"]],
                })

    return {
        "ready":        True,
        "step":         _steps,
        "width":        m.width,
        "height":       m.height,
        "z1_end":       m.z1_max_x,
        "z2_end":       m.z2_max_x,
        "disposal":     {"x": m.disposal_pos[0], "y": m.disposal_pos[1]},
        "wastes":       wastes,
        "robots":       robots,
        "green_count":  m._count_waste("green"),
        "yellow_count": m._count_waste("yellow"),
        "red_count":    m._count_waste("red"),
        "disposed":     m.disposed_count,
        "finished":     m.is_done() or _steps >= MAX_STEPS,
        "internal_board": _board_snapshot_with_candidates(m, m.internal_board),
        "external_board": _board_snapshot_with_candidates(m, m.external_board),
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
