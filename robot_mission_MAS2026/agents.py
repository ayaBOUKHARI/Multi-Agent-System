# Group: X | Date: 2026-03-20 | Members: (à compléter)
# agents.py — Robot agent classes: GreenAgent, YellowAgent, RedAgent
#
# Agent loop (per step):
#   1. update(knowledge, percepts)  — intègre les percepts du dernier do()
#   2. action = deliberate(knowledge) — raisonnement SANS accès à des variables externes
#   3. percepts = model.do(self, action)  — exécution + retour des nouveaux percepts

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
    Goals (in priority order):
      1. If carrying 2 green wastes → transform into 1 yellow
      2. If carrying 1 yellow waste → move east to z1 east boundary, then put_down
      3. If there is green waste visible in percepts → move toward / pick up
      4. If a known green waste location exists in memory → navigate there
      5. Otherwise → random walk within z1
    """
    inventory   = knowledge["inventory"]
    pos         = knowledge["pos"]
    percepts    = knowledge["percepts"]
    z1_max_x    = knowledge["zone_boundaries"]["z1_max_x"]
    known_wastes = knowledge.get("known_wastes", {})

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

    # 3. Waste visible in adjacent cells (including current cell)
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "green":
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Navigate toward a remembered green waste
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "green":
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Random walk (constrained to z1 — enforced in model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_yellow(knowledge: dict) -> dict:
    """
    Deliberation for YellowAgent (zones z1 + z2).
    Goals (in priority order):
      1. If carrying 2 yellow wastes → transform into 1 red
      2. If carrying 1 red waste → move east to z2 east boundary, then put_down
      3. If yellow waste visible → move toward / pick up
      4. If known yellow waste in memory → navigate there
      5. Otherwise → random walk within z1/z2
    """
    inventory    = knowledge["inventory"]
    pos          = knowledge["pos"]
    percepts     = knowledge["percepts"]
    z2_max_x     = knowledge["zone_boundaries"]["z2_max_x"]
    known_wastes = knowledge.get("known_wastes", {})

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

    # 3. Waste visible in percepts
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "yellow":
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Navigate toward remembered yellow waste
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "yellow":
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Random walk (constrained to z1+z2 in model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_red(knowledge: dict) -> dict:
    """
    Deliberation for RedAgent (all zones z1 + z2 + z3).
    Goals (in priority order):
      1. If carrying 1 red waste → navigate to disposal zone, then put_down
      2. If red waste visible in percepts → move toward / pick up
      3. If known red waste in memory → navigate there
      4. Otherwise → random walk
    """
    inventory     = knowledge["inventory"]
    pos           = knowledge["pos"]
    percepts      = knowledge["percepts"]
    disposal_pos  = knowledge.get("disposal_pos")
    known_wastes  = knowledge.get("known_wastes", {})

    red_count = inventory.count("red")

    # 1. Transport red to disposal zone
    if red_count >= 1 and disposal_pos:
        if pos == disposal_pos:
            return {"type": "put_down", "waste_type": "red"}
        dx, dy = disposal_pos[0] - pos[0], disposal_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 2. Waste visible in percepts
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

    # 4. Random walk (all zones — no zone constraint on red)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


# ---------------------------------------------------------------------------
# Robot base class
# ---------------------------------------------------------------------------

class RobotAgent(mesa.Agent):
    """
    Abstract base for all robot types.
    Subclasses must define:
      - self.allowed_zones: set of allowed zone numbers
      - self.deliberate_fn: the deliberate function to use
    """

    def __init__(self, model: mesa.Model, color: str) -> None:
        super().__init__(model)
        self.color = color          # "green" | "yellow" | "red"
        self.allowed_zones: set = set()   # overridden by subclass
        self.deliberate_fn = None         # overridden by subclass
        self._last_percepts: dict = {}    # percepts returned by last model.do()

        # Knowledge base: the only input to deliberate()
        self.knowledge: dict = {
            "pos":              None,
            "inventory":        [],          # list of waste_type strings
            "percepts":         {},          # {pos: {"wastes": [...], "radioactivity": float, ...}}
            "zone_boundaries":  {},          # set by model after placement
            "known_wastes":     {},          # {pos: waste_type}  — persistent memory
            "disposal_pos":     None,        # set by model (relevant for red robots)
        }

    def _update_knowledge(self, percepts: dict) -> None:
        """Integrate new percepts into the agent's knowledge base."""
        self.knowledge["pos"]     = self.pos
        self.knowledge["percepts"] = percepts

        # Update memory map with newly observed wastes
        for cell_pos, contents in percepts.items():
            # Remove position from known_wastes if we can see it's now empty
            if not contents.get("wastes"):
                self.knowledge["known_wastes"].pop(cell_pos, None)
            else:
                # Record the first waste seen at that cell
                for w in contents["wastes"]:
                    self.knowledge["known_wastes"][cell_pos] = w["waste_type"]

    def step(self) -> None:
        """
        Main agent loop:
          1. Update knowledge with percepts from previous step
          2. Deliberate (pure function — no external variable access)
          3. Execute action via model.do(), store returned percepts
        """
        self._update_knowledge(self._last_percepts)
        action = self.deliberate_fn(self.knowledge)
        self._last_percepts = self.model.do(self, action)


# ---------------------------------------------------------------------------
# Concrete robot classes
# ---------------------------------------------------------------------------

class GreenAgent(RobotAgent):
    """
    Green robot — operates only in z1.
    - Collects 2 green wastes → transforms into 1 yellow
    - Transports yellow waste to east edge of z1
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="green")
        self.allowed_zones  = {1}
        self.deliberate_fn  = deliberate_green


class YellowAgent(RobotAgent):
    """
    Yellow robot — operates in z1 and z2.
    - Collects 2 yellow wastes → transforms into 1 red
    - Transports red waste to east edge of z2
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="yellow")
        self.allowed_zones  = {1, 2}
        self.deliberate_fn  = deliberate_yellow


class RedAgent(RobotAgent):
    """
    Red robot — operates in z1, z2, and z3.
    - Collects 1 red waste
    - Transports it to the waste disposal zone (easternmost z3 cell)
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="red")
        self.allowed_zones  = {1, 2, 3}
        self.deliberate_fn  = deliberate_red
