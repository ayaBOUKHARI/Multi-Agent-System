# Group: 18 | Date: 2026-03-23 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# app.py — Flask server  →  http://127.0.0.1:5000

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, render_template, jsonify, request
from core.model import RobotMission
from core.objects import WasteAgent, WasteDisposalZone
from core.agents import GreenAgent, YellowAgent, RedAgent
from direct.model import DirectRobotMission
from direct.agents import DirectGreenAgent, DirectYellowAgent, DirectRedAgent

app = Flask(__name__)

_model = None
_steps = 0
_msg_log = []
_total_messages = 0
MAX_STEPS = 1000
MSG_LOG_SIZE = 60


def _board_snapshot_with_candidates(m, board):
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
        item["cost_to_reach"] = h.get("cost")
        item["cost_come_and_deposit"] = (h.get("cost") + 1) if h.get("cost") is not None else None
        history.append(item)

    return {
        "name": board.name,
        "count": len(requests),
        "requests": requests,
        "history": history,
    }


def _wrap_send_message(model):
    original = getattr(model, "_do_send_message", None)
    if original is None:
        return

    def _intercepted(agent, recipients, message):
        global _msg_log, _total_messages
        _total_messages += 1
        content = message.get("content", {})
        entry = {
            "step": _steps,
            "from": agent.label or f"{agent.color[0]}{agent.unique_id}",
            "color": agent.color,
            "perf": message.get("performative", "?"),
            "type": content.get("type", "?"),
            "pos": content.get("pos"),
            "waste": content.get("waste"),
            "to": "broadcast" if recipients is None else f"#{recipients[0]}",
        }
        _msg_log.append(entry)
        if len(_msg_log) > MSG_LOG_SIZE:
            _msg_log.pop(0)
        return original(agent, recipients, message)

    model._do_send_message = _intercepted


def _serialize():
    m = _model
    if m is None:
        return {"ready": False}

    wastes, robots = [], []
    robot_types = (
        GreenAgent, YellowAgent, RedAgent,
        DirectGreenAgent, DirectYellowAgent, DirectRedAgent,
    )

    for cell_content, (x, y) in m.grid.coord_iter():
        for agent in cell_content:
            if isinstance(agent, WasteAgent):
                wastes.append({"x": x, "y": y, "type": agent.waste_type})

            elif isinstance(agent, robot_types):
                rtype = ("green"  if isinstance(agent, (GreenAgent,  DirectGreenAgent))  else
                         "yellow" if isinstance(agent, (YellowAgent, DirectYellowAgent)) else "red")
                partner_pos = agent.knowledge.get("partner_pos")
                robots.append({
                    "x": x, "y": y, "type": rtype,
                    "label": agent.label,
                    "inventory": [w[0].upper() for w in agent.knowledge["inventory"]],
                    "handoff_role": agent.knowledge.get("handoff_role"),
                    "partner_pos": list(partner_pos) if partner_pos else None,
                })

    if getattr(m, "communication_enabled", True):
        internal_board = _board_snapshot_with_candidates(m, m.internal_board)
        external_board = _board_snapshot_with_candidates(m, m.external_board)
    else:
        internal_board = {"name": "internal", "count": 0, "requests": [], "history": []}
        external_board = {"name": "external", "count": 0, "requests": [], "history": []}

    return {
        "ready":        True,
        "step":         _steps,
        "width":        m.width,
        "height":       m.height,
        "communication_enabled": m.communication_enabled,
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
        "total_messages": _total_messages,
        "msg_log": list(reversed(_msg_log[-20:])),
        "internal_board": internal_board,
        "external_board": external_board,
    }



@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/reset", methods=["POST"])
def reset():
    global _model, _steps, _total_messages
    d = request.get_json(silent=True) or {}
    use_heap_mode = bool(d.get("communication_enabled", True))
    common_args = {
        "width": 15,
        "height": 10,
        "n_green_robots": max(1, int(d.get("green_robots", 3))),
        "n_yellow_robots": max(1, int(d.get("yellow_robots", 3))),
        "n_red_robots": max(1, int(d.get("red_robots", 3))),
        "n_green_wastes": max(4, int(d.get("green_wastes", 12))),
        "seed": int(d.get("seed", 42)),
    }

    if use_heap_mode:
        _model = RobotMission(
            communication_enabled=True,
            **common_args,
        )
    else:
        _model = DirectRobotMission(**common_args)
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
