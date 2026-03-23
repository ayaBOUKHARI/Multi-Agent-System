# Group: 18 | Date: 2026-03-23 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# agents.py — Robot agent classes: GreenAgent, YellowAgent, RedAgent
#
# Agent loop (per step):
#   1. update(knowledge, percepts)       — integrates percepts into knowledge
#   2. check_confirmations()             — handoff initiator role from board
#   3. evaluate_boards()                 — take lowest-cost request from boards
#   4. action = deliberate(knowledge)    — pure function, no external variables
#   5. percepts = model.do(self, action) — execution + return of new percepts
#   6. post_to_boards()                  — post requests based on new state
#
# Communication (dual message boards):
#   Internal board — same-color: handoff protocol for stuck agents
#   External board — cross-color: waste positions after deposit / observation
#
# Cost = manhattan_distance(agent, target) + penalties
#   Unavailable (in handoff / wrong inventory): cost = infinity
#   Carrying items (for waste_available):       cost + 15

import random
import mesa


# ---------------------------------------------------------------------------
# Deliberate functions — pure functions, no access to variables outside args
# ---------------------------------------------------------------------------

def _dir_from_delta(dx: int, dy: int) -> str:
    """Converts a (dx, dy) offset to the dominant cardinal direction."""
    if dx == 0 and dy == 0:
        return "stay"
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "N" if dy > 0 else "S"


def deliberate_green(knowledge: dict) -> dict:
    """
    Deliberation for GreenAgent (zone z1 only).
    Priority order:
      1. Transform: 2 green → 1 yellow
      2. Transport yellow east to z1/z2 boundary → put_down
      3. Handoff responder: navigate to partner position → put_down green
      4. Pick up visible green waste (skips drop_avoid_pos)
      5. Navigate toward remembered green waste (skips drop_avoid_pos)
      6. Handoff initiator: stay put and wait for responder
      7. Random walk within z1
    """
    inventory      = knowledge["inventory"]
    pos            = knowledge["pos"]
    percepts       = knowledge["percepts"]
    z1_max_x       = knowledge["zone_boundaries"]["z1_max_x"]
    known_wastes   = knowledge.get("known_wastes", {})
    handoff_role   = knowledge.get("handoff_role")
    partner_pos    = knowledge.get("partner_pos")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    green_count  = inventory.count("green")
    yellow_count = inventory.count("yellow")

    # 1. Transform
    if green_count >= 2:
        return {"type": "transform"}

    # 2. Transport yellow east → deposit at z1/z2 border
    if yellow_count >= 1:
        if pos[0] >= z1_max_x:
            return {"type": "put_down", "waste_type": "yellow"}
        return {"type": "move", "direction": "E"}

    # 3. Handoff responder: go to initiator's cell and drop waste
    if handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "green"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Pick up visible green waste (skip drop_avoid_pos)
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "green":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Navigate toward remembered green waste (skip drop_avoid_pos)
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "green" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 6. Handoff initiator: stay in place until responder drops the waste
    if handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    # 7. Random walk (zone enforced by model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_yellow(knowledge: dict) -> dict:
    """
    Deliberation for YellowAgent (zones z1 + z2).
    Priority order:
      1. Transform: 2 yellow → 1 red
      2. Transport red east to z2/z3 boundary → put_down
      3. Handoff responder: navigate to partner → put_down yellow
      4. Pick up visible yellow waste (skips drop_avoid_pos)
      5. Navigate toward remembered yellow waste (skips drop_avoid_pos)
      6. Handoff initiator: stay put
      7. Random walk within z1/z2
    """
    inventory      = knowledge["inventory"]
    pos            = knowledge["pos"]
    percepts       = knowledge["percepts"]
    z2_max_x       = knowledge["zone_boundaries"]["z2_max_x"]
    known_wastes   = knowledge.get("known_wastes", {})
    handoff_role   = knowledge.get("handoff_role")
    partner_pos    = knowledge.get("partner_pos")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    yellow_count = inventory.count("yellow")
    red_count    = inventory.count("red")

    # 1. Transform
    if yellow_count >= 2:
        return {"type": "transform"}

    # 2. Transport red east → deposit at z2/z3 border
    if red_count >= 1:
        if pos[0] >= z2_max_x:
            return {"type": "put_down", "waste_type": "red"}
        return {"type": "move", "direction": "E"}

    # 3. Handoff responder
    if handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "yellow"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Pick up visible yellow waste
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "yellow":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Navigate toward remembered yellow waste
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "yellow" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 6. Handoff initiator: wait for responder
    if handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    # 7. Random walk (zone enforced by model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_red(knowledge: dict) -> dict:
    """
    Deliberation for RedAgent (all zones z1 + z2 + z3).
    Priority order:
      1. Carry red waste to disposal zone → put_down
      2. Pick up visible red waste
      3. Navigate toward remembered red waste
      4. Random walk
    """
    inventory    = knowledge["inventory"]
    pos          = knowledge["pos"]
    percepts     = knowledge["percepts"]
    disposal_pos = knowledge.get("disposal_pos")
    known_wastes = knowledge.get("known_wastes", {})

    red_count = inventory.count("red")

    # 1. Transport red to disposal zone
    if red_count >= 1 and disposal_pos:
        if pos == disposal_pos:
            return {"type": "put_down", "waste_type": "red"}
        dx, dy = disposal_pos[0] - pos[0], disposal_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 2. Pick up visible red waste
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "red":
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 3. Navigate toward remembered red waste
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "red":
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Random walk (all zones)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


# ---------------------------------------------------------------------------
# Robot base class
# ---------------------------------------------------------------------------

class RobotAgent(mesa.Agent):
    """
    Abstract base for all robot types.

    Subclasses set:
      - self.allowed_zones  : set of zone numbers the robot can enter
      - self.deliberate_fn  : pure deliberation function
    """

    # Penalty added to cost when agent is carrying items (for waste_available)
    BUSY_PENALTY = 15

    def __init__(self, model: mesa.Model, color: str) -> None:
        super().__init__(model)
        self.color = color
        self.label: str = ""              # assigned by model (g1, y2, r3 …)
        self.steps_taken: int = 0         # per-agent step count (step_n)
        self.allowed_zones: set = set()
        self.deliberate_fn = None
        self._last_percepts: dict = {}

        self.knowledge: dict = {
            "pos":              None,
            "inventory":        [],
            "percepts":         {},
            "zone_boundaries":  {},
            "known_wastes":     {},
            "disposal_pos":     None,
            # Handoff state
            "partner_id":       None,
            "partner_pos":      None,
            "handoff_role":     None,     # "initiator" | "responder" | None
            "handoff_wait":     0,
            "drop_avoid_pos":   None,
        }

    # ------------------------------------------------------------------
    # Knowledge update
    # ------------------------------------------------------------------

    def _update_knowledge(self, percepts: dict) -> None:
        """Integrate percepts into the knowledge base."""
        drop_pos = self.knowledge.get("drop_avoid_pos")
        if drop_pos is not None and drop_pos != self.pos:
            self.knowledge["drop_avoid_pos"] = None

        self.knowledge["pos"]      = self.pos
        self.knowledge["percepts"] = percepts

        for cell_pos, contents in percepts.items():
            if not contents.get("wastes"):
                self.knowledge["known_wastes"].pop(cell_pos, None)
            else:
                for w in contents["wastes"]:
                    self.knowledge["known_wastes"][cell_pos] = w["waste_type"]

        self._check_handoff_resolution()

    # ------------------------------------------------------------------
    # Handoff state management
    # ------------------------------------------------------------------

    def _check_handoff_resolution(self) -> None:
        """Auto-clear handoff state once completed or timed out."""
        role = self.knowledge.get("handoff_role")
        if not role:
            self.knowledge["handoff_wait"] = 0
            return

        inv           = self.knowledge["inventory"]
        handoff_waste = "green" if self.color == "green" else "yellow"

        if role == "initiator":
            self.knowledge["handoff_wait"] += 1
            if inv.count(handoff_waste) >= 2:
                self._clear_handoff()
            elif self.knowledge["handoff_wait"] > 20:
                self._clear_handoff()

        elif role == "responder":
            self.knowledge["handoff_wait"] += 1
            if handoff_waste not in inv:
                self._clear_handoff()
            elif self.knowledge["handoff_wait"] > 40:
                self._clear_handoff()

    def _clear_handoff(self) -> None:
        """Reset all handoff-related knowledge and clean the internal board."""
        self.knowledge.update({
            "handoff_role": None,
            "partner_id":   None,
            "partner_pos":  None,
            "handoff_wait": 0,
        })
        self.model.internal_board.remove_by_sender(self.unique_id)

    # ------------------------------------------------------------------
    # Board interaction — confirmations
    # ------------------------------------------------------------------

    def _check_confirmations(self) -> None:
        """
        Check if a posted stuck_unpaired request was taken by another agent.
        If so, become the handoff initiator.
        """
        conf = self.model.internal_board.pop_confirmation(self.unique_id)
        if conf and conf["request_type"] == "stuck_unpaired":
            if self.knowledge["partner_id"] is None:
                self.knowledge["partner_id"]   = conf["taker_id"]
                self.knowledge["handoff_role"] = "initiator"

    # ------------------------------------------------------------------
    # Board interaction — evaluate & take
    # ------------------------------------------------------------------

    def _compute_cost(self, request) -> float:
        """
        Compute personal cost to handle *request*.

        Returns infinity when the agent is unavailable.
        """
        target_pos = tuple(request.payload["pos"])
        distance = abs(self.pos[0] - target_pos[0]) + abs(self.pos[1] - target_pos[1])

        if self.knowledge.get("handoff_role"):
            return float("inf")

        if request.request_type == "stuck_unpaired":
            hw = "green" if self.color == "green" else "yellow"
            if self.knowledge["inventory"].count(hw) != 1:
                return float("inf")
            return distance

        if request.request_type == "waste_available":
            max_inv = 1 if self.color == "red" else 2
            inv = self.knowledge["inventory"]
            if len(inv) >= max_inv:
                return float("inf")
            return distance + (self.BUSY_PENALTY if inv else 0)

        return float("inf")

    def _evaluate_boards(self) -> None:
        """
        Evaluate both message boards and take the single lowest-cost request.
        Internal requests (handoff) and external requests (waste info) are
        compared together — the cheapest wins.
        """
        internal = self.model.internal_board.get_available(self.color, self.unique_id)
        external = self.model.external_board.get_available(self.color, self.unique_id)

        best_req   = None
        best_cost  = float("inf")
        best_board = None

        for req in internal:
            cost = self._compute_cost(req)
            if cost < best_cost:
                best_cost  = cost
                best_req   = req
                best_board = self.model.internal_board

        for req in external:
            cost = self._compute_cost(req)
            if cost < best_cost:
                best_cost  = cost
                best_req   = req
                best_board = self.model.external_board

        if best_req is None or best_cost >= float("inf"):
            return

        # Global arbitration: only the best eligible agent may take this request.
        # Tie-break rule: same cost -> lower step_n wins.
        best_taker = self.model.get_best_taker_for_request(best_req)
        if not best_taker or best_taker["agent"].unique_id != self.unique_id:
            return

        taken = best_board.take(
            best_req.request_id, self.unique_id,
            self.label, best_cost, self.model.current_step, self.steps_taken,
        )
        if taken:
            self._integrate_taken_request(taken)

    def _integrate_taken_request(self, request) -> None:
        """Process a taken request into the knowledge base."""
        if request.request_type == "stuck_unpaired":
            self.knowledge["partner_id"]   = request.sender_id
            self.knowledge["partner_pos"]  = tuple(request.payload["pos"])
            self.knowledge["handoff_role"] = "responder"
            # No longer need own stuck request (now busy as responder)
            self.model.internal_board.remove_by_sender(self.unique_id)

        elif request.request_type == "waste_available":
            pos = tuple(request.payload["pos"])
            self.knowledge["known_wastes"][pos] = request.payload["waste_type"]

    # ------------------------------------------------------------------
    # Board interaction — posting
    # ------------------------------------------------------------------

    def _has_reachable_waste(self, waste_type: str) -> bool:
        """True if a visible or known waste of *waste_type* exists (ignoring drop_avoid_pos)."""
        drop_pos = self.knowledge.get("drop_avoid_pos")
        for cell_pos, contents in self.knowledge["percepts"].items():
            if cell_pos == drop_pos:
                continue
            for obj in contents.get("wastes", []):
                if obj["waste_type"] == waste_type:
                    return True
        for pos, wtype in self.knowledge["known_wastes"].items():
            if wtype == waste_type and pos != drop_pos:
                return True
        return False

    def _post_to_boards(self) -> None:
        """
        Post requests to the message boards based on current state.

        Internal board: stuck with 1 unpaired waste and no known target.
        External board: cross-tier waste visible in percepts.
        """
        step = self.model.current_step

        # === Internal: stuck unpaired ===
        if self.color in ("green", "yellow"):
            hw  = "green" if self.color == "green" else "yellow"
            inv = self.knowledge["inventory"]

            if (inv.count(hw) == 1
                    and self.knowledge["handoff_role"] is None
                    and not self._has_reachable_waste(hw)):
                # Post or update position of existing request
                if self.model.internal_board.has_active_from(
                        self.unique_id, "stuck_unpaired"):
                    self.model.internal_board.update_sender_position(
                        self.unique_id, "stuck_unpaired", self.pos)
                else:
                    self.model.internal_board.post(
                        self.unique_id, self.label, self.color, self.color,
                        "stuck_unpaired",
                        {"waste_type": hw, "pos": list(self.pos)},
                        step,
                    )
            else:
                # No longer stuck → remove any leftover request
                self.model.internal_board.remove_by_sender(self.unique_id)

        # === External: cross-tier waste in view ===
        cross_map = {"green": "yellow", "yellow": "red"}
        if self.color in cross_map:
            target_type = cross_map[self.color]
            for cell_pos, contents in self.knowledge["percepts"].items():
                for obj in contents.get("wastes", []):
                    if obj["waste_type"] == target_type:
                        self.model.external_board.post(
                            self.unique_id, self.label, self.color, target_type,
                            "waste_available",
                            {"waste_type": target_type, "pos": list(cell_pos)},
                            step,
                        )

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------

    def step(self) -> None:
        """
        Main agent loop:
          1. Update knowledge with percepts from previous step
          2. Check board confirmations (become initiator if request was taken)
          3. Evaluate both boards — take the lowest-cost request
          4. Deliberate (pure function)
          5. Execute action via model.do(), store returned percepts
          6. Post to boards based on new state
        """
        self.steps_taken += 1
        self._update_knowledge(self._last_percepts)
        self._check_confirmations()
        self._evaluate_boards()

        action = self.deliberate_fn(self.knowledge)

        if action.get("type") == "put_down":
            self.knowledge["drop_avoid_pos"] = self.pos
        else:
            self.knowledge["drop_avoid_pos"] = None

        self._last_percepts = self.model.do(self, action)
        self._post_to_boards()


# ---------------------------------------------------------------------------
# Concrete robot classes
# ---------------------------------------------------------------------------

class GreenAgent(RobotAgent):
    """Green robot — operates only in z1. Collects 2 green → 1 yellow."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="green")
        self.allowed_zones  = {1}
        self.deliberate_fn  = deliberate_green


class YellowAgent(RobotAgent):
    """Yellow robot — operates in z1 + z2. Collects 2 yellow → 1 red."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="yellow")
        self.allowed_zones  = {1, 2}
        self.deliberate_fn  = deliberate_yellow


class RedAgent(RobotAgent):
    """Red robot — operates in all zones. Carries 1 red → disposal."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="red")
        self.allowed_zones  = {1, 2, 3}
        self.deliberate_fn  = deliberate_red
