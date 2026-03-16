# group 18 : Aya Boukhari, Ikram Firdaous
# date of creation : 16-03-2026

import mesa
import random
from objects import Waste


def _move_toward(current_pos, target_pos, allowed_x_range):

    cx, cy = current_pos
    tx, ty = target_pos

    dx = 0 if cx == tx else (1 if tx > cx else -1)
    dy = 0 if cy == ty else (1 if ty > cy else -1)

    # Prefer moving on the axis with the larger distance (avoids diagonal)
    if abs(tx - cx) >= abs(ty - cy):
        nx, ny = cx + dx, cy
    else:
        nx, ny = cx, cy + dy

    # Clamp x to allowed range
    nx = max(allowed_x_range[0], min(allowed_x_range[1], nx))
    return (nx, ny)


def _random_step(current_pos, allowed_x_range, grid_height):
    """Return a random adjacent cell within *allowed_x_range*."""
    cx, cy = current_pos
    candidates = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = cx + dx, cy + dy
            if allowed_x_range[0] <= nx <= allowed_x_range[1] and 0 <= ny < grid_height:
                candidates.append((nx, ny))
    if candidates:
        return random.choice(candidates)
    return current_pos  # stuck (shouldn't happen)



class RobotAgent(mesa.Agent):
    """Abstract base class for all robot types."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model)
        # Knowledge base (beliefs + memory)
        self.knowledge = {
            "pos": None,           # current position (x, y)
            "inventory": [],       # list of Waste agents being carried
            "known_wastes": {},    # {(x,y): waste_type} – remembered waste positions
            "disposal_zone_pos": None,  # remembered position of disposal zone
            "target": None,        # current movement target
            "zone_x_range": None,  # (x_min, x_max) allowed columns
            "grid_height": None,   # grid height (rows)
            "z1_x_max": None,      # last column of z1
            "z2_x_max": None,      # last column of z2
        }
        # Percepts from the previous step (populated by model.do at init time)
        self.percepts = {}



    def update_knowledge(self, percepts: dict) -> None:
        """Update the knowledge base from new percepts."""
        k = self.knowledge
        k["pos"] = self.pos

        for cell_pos, cell_info in percepts.items():
            wastes = cell_info.get("wastes", [])
            if wastes:
                for w in wastes:
                    k["known_wastes"][cell_pos] = w["type"]
            else:
                # Cell observed to be empty – remove stale entry
                k["known_wastes"].pop(cell_pos, None)

            if cell_info.get("is_disposal_zone"):
                k["disposal_zone_pos"] = cell_pos


    def step(self) -> None:
        self.update_knowledge(self.percepts)
        action = self.deliberate(self.knowledge)
        self.percepts = self.model.do(self, action)


    def deliberate(self, knowledge: dict) -> dict:
        raise NotImplementedError



class GreenAgent(RobotAgent):
    """
    Strategy:
      1. If carrying 2 green wastes → transform into 1 yellow waste.
      2. If carrying 1 yellow waste:
           - If at eastern edge of z1 → drop.
           - Else → move east.
      3. Otherwise → pick up green waste if present at current cell,
         else move toward the nearest known green waste,
         else random walk in z1.
    """

    def deliberate(self, knowledge: dict) -> dict:
        pos = knowledge["pos"]
        inventory = knowledge["inventory"]
        x_min, x_max = knowledge["zone_x_range"]
        z1_east = knowledge["z1_x_max"]
        height = knowledge["grid_height"]

        green_count = sum(1 for w in inventory if w.waste_type == "green")
        yellow_count = sum(1 for w in inventory if w.waste_type == "yellow")

        # 1. Transform 2 green → 1 yellow
        if green_count >= 2:
            return {"type": "transform"}

        # 2. Deposit yellow at east edge of z1
        if yellow_count >= 1:
            if pos[0] == z1_east:
                return {"type": "drop"}
            else:
                target = (z1_east, pos[1])
                new_pos = _move_toward(pos, target, (x_min, x_max))
                return {"type": "move", "target": new_pos}

        # 3. Pick up green waste at current cell (already there, model will check)
        current_wastes = knowledge["known_wastes"].get(pos, None)
        if current_wastes == "green":
            return {"type": "pick_up"}

        # 4. Move toward nearest known green waste
        green_positions = [
            p for p, t in knowledge["known_wastes"].items() if t == "green"
        ]
        if green_positions:
            target = min(green_positions,
                         key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
            new_pos = _move_toward(pos, target, (x_min, x_max))
            return {"type": "move", "target": new_pos}

        # 5. Random walk in z1
        new_pos = _random_step(pos, (x_min, x_max), height)
        return {"type": "move", "target": new_pos}


class YellowAgent(RobotAgent):
    """
    Strategy:
      1. If carrying 2 yellow wastes → transform into 1 red waste.
      2. If carrying 1 red waste:
           - If at eastern edge of z2 → drop.
           - Else → move east.
      3. Otherwise → pick up yellow waste if present at current cell,
         else move toward nearest known yellow waste,
         else random walk in z1+z2.
    """

    def deliberate(self, knowledge: dict) -> dict:
        pos = knowledge["pos"]
        inventory = knowledge["inventory"]
        x_min, x_max = knowledge["zone_x_range"]
        z2_east = knowledge["z2_x_max"]
        height = knowledge["grid_height"]

        yellow_count = sum(1 for w in inventory if w.waste_type == "yellow")
        red_count = sum(1 for w in inventory if w.waste_type == "red")

        # 1. Transform 2 yellow → 1 red
        if yellow_count >= 2:
            return {"type": "transform"}

        # 2. Deposit red at east edge of z2
        if red_count >= 1:
            if pos[0] == z2_east:
                return {"type": "drop"}
            else:
                target = (z2_east, pos[1])
                new_pos = _move_toward(pos, target, (x_min, x_max))
                return {"type": "move", "target": new_pos}

        # 3. Pick up yellow waste at current cell
        current_wastes = knowledge["known_wastes"].get(pos, None)
        if current_wastes == "yellow":
            return {"type": "pick_up"}

        # 4. Move toward nearest known yellow waste
        yellow_positions = [
            p for p, t in knowledge["known_wastes"].items() if t == "yellow"
        ]
        if yellow_positions:
            target = min(yellow_positions,
                         key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
            new_pos = _move_toward(pos, target, (x_min, x_max))
            return {"type": "move", "target": new_pos}

        # 5. Random walk in z1+z2
        new_pos = _random_step(pos, (x_min, x_max), height)
        return {"type": "move", "target": new_pos}



class RedAgent(RobotAgent):
    """
    Strategy:
      1. If carrying 1 red waste:
           - If at the waste-disposal zone → put away (drop there).
           - Else → move toward the disposal zone.
      2. Otherwise → pick up red waste if present at current cell,
         else move toward nearest known red waste,
         else random walk in z1+z2+z3.
    """

    def deliberate(self, knowledge: dict) -> dict:
        pos = knowledge["pos"]
        inventory = knowledge["inventory"]
        x_min, x_max = knowledge["zone_x_range"]
        height = knowledge["grid_height"]
        disposal_pos = knowledge["disposal_zone_pos"]

        red_count = sum(1 for w in inventory if w.waste_type == "red")

        # 1. Carry red waste to disposal zone
        if red_count >= 1:
            if disposal_pos is not None:
                if pos == disposal_pos:
                    return {"type": "put_away"}
                else:
                    new_pos = _move_toward(pos, disposal_pos, (x_min, x_max))
                    return {"type": "move", "target": new_pos}
            else:
                # Disposal zone not yet discovered → move east to find it
                new_pos = _move_toward(pos, (x_max, pos[1]), (x_min, x_max))
                return {"type": "move", "target": new_pos}

        # 2. Pick up red waste at current cell
        current_wastes = knowledge["known_wastes"].get(pos, None)
        if current_wastes == "red":
            return {"type": "pick_up"}

        # 3. Move toward nearest known red waste
        red_positions = [
            p for p, t in knowledge["known_wastes"].items() if t == "red"
        ]
        if red_positions:
            target = min(red_positions,
                         key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))
            new_pos = _move_toward(pos, target, (x_min, x_max))
            return {"type": "move", "target": new_pos}

        # 4. Random walk in full zone
        new_pos = _random_step(pos, (x_min, x_max), height)
        return {"type": "move", "target": new_pos}
