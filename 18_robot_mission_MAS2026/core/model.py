# Group: 18 | Date: 2026-03-23 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# model.py — RobotMission (Mesa 3.x)
#
# Grid (west → east):
#   z1 [0 .. W//3-1]     — low radioactivity, green wastes
#   z2 [W//3 .. 2W//3-1] — medium radioactivity
#   z3 [2W//3 .. W-1]    — high radioactivity, disposal zone

import random
import mesa
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from .objects import RadioactivityAgent, WasteAgent, WasteDisposalZone
from .agents import GreenAgent, YellowAgent, RedAgent
from .messaging import MessageBoard


DIRECTIONS = {
    "N":    ( 0,  1),
    "S":    ( 0, -1),
    "E":    ( 1,  0),
    "W":    (-1,  0),
    "stay": ( 0,  0),
}


class RobotMission(mesa.Model):
    """Heap-board simulation. Agents coordinate through shared internal/external boards."""

    def __init__(
        self,
        width: int           = 15,
        height: int          = 10,
        n_green_robots: int  = 3,
        n_yellow_robots: int = 3,
        n_red_robots: int    = 3,
        n_green_wastes: int  = 10,
        communication_enabled: bool = True,
        seed: int | None     = None,
    ) -> None:
        super().__init__(seed=seed)

        self.width  = width
        self.height = height
        self.grid   = MultiGrid(width, height, torus=False)

        self.z1_max_x = width // 3 - 1
        self.z2_max_x = 2 * width // 3 - 1
        self.zone_boundaries = {
            "z1_max_x": self.z1_max_x,
            "z2_max_x": self.z2_max_x,
            "width":    width,
            "height":   height,
        }

        self.disposal_pos: tuple = None
        self.current_step: int = 0
        self.communication_enabled = communication_enabled
        self.internal_board = MessageBoard("internal", max_size=30, ttl=80)
        self.external_board = MessageBoard("external", max_size=50, ttl=100)

        self._build_radioactivity()
        self._place_disposal_zone()
        self._place_initial_wastes(n_green_wastes)
        self._place_robots(n_green_robots, n_yellow_robots, n_red_robots)

        self.disposed_count = 0
        self.datacollector = DataCollector(
            model_reporters={
                "Green wastes":   lambda m: m._count_waste("green"),
                "Yellow wastes":  lambda m: m._count_waste("yellow"),
                "Red wastes":     lambda m: m._count_waste("red"),
                "Total wastes":   lambda m: m._count_waste(None),
                "In inventories": lambda m: m._count_inventory_waste(),
                "Disposed":       lambda m: m.disposed_count,
            }
        )
        self.datacollector.collect(self)

    def _zone_of(self, x: int) -> int:
        """1, 2, or 3 depending on which radioactivity band x falls in."""
        if x <= self.z1_max_x:
            return 1
        if x <= self.z2_max_x:
            return 2
        return 3

    def _build_radioactivity(self) -> None:
        for x in range(self.width):
            zone = self._zone_of(x)
            for y in range(self.height):
                self.grid.place_agent(RadioactivityAgent(self, zone), (x, y))

    def _place_disposal_zone(self) -> None:
        x = self.width - 1
        y = self.random.randrange(self.height)
        disposal = WasteDisposalZone(self)
        self.grid.place_agent(disposal, (x, y))
        self.disposal_pos = (x, y)

    def _place_initial_wastes(self, n: int) -> None:
        for _ in range(n):
            x = self.random.randrange(0, self.z1_max_x + 1)
            y = self.random.randrange(self.height)
            self.grid.place_agent(WasteAgent(self, "green"), (x, y))

    def _place_robots(self, n_green: int, n_yellow: int, n_red: int) -> None:
        counters = {"green": 0, "yellow": 0, "red": 0}
        prefix   = {"green": "g", "yellow": "y", "red": "r"}

        placements = [
            (GreenAgent,  n_green,  0, self.z1_max_x),
            (YellowAgent, n_yellow, 0, self.z2_max_x),
            (RedAgent,    n_red,    0, self.width - 1),
        ]
        for AgentClass, count, x_min, x_max in placements:
            for _ in range(count):
                x = self.random.randrange(x_min, x_max + 1)
                y = self.random.randrange(self.height)
                robot = AgentClass(self)
                counters[robot.color] += 1
                robot.label = f"{prefix[robot.color]}{counters[robot.color]}"
                robot.knowledge["zone_boundaries"]       = self.zone_boundaries
                robot.knowledge["disposal_pos"]          = self.disposal_pos
                robot.knowledge["communication_enabled"] = self.communication_enabled
                robot.knowledge["pos"]                   = (x, y)
                self.grid.place_agent(robot, (x, y))

    def do(self, agent, action: dict) -> dict:
        """Execute one action for *agent* and return fresh percepts."""
        action_type = action.get("type", "stay")

        if action_type == "move":
            self._do_move(agent, action.get("direction", "stay"))
        elif action_type == "pick_up":
            self._do_pick_up(agent)
        elif action_type == "transform":
            self._do_transform(agent)
        elif action_type == "put_down":
            self._do_put_down(agent, action.get("waste_type"))

        return self._get_percepts(agent)

    def _do_move(self, agent, direction: str) -> None:
        dx, dy = DIRECTIONS.get(direction, (0, 0))
        cx, cy = agent.pos
        nx, ny = cx + dx, cy + dy

        if not (0 <= nx < self.width and 0 <= ny < self.height):
            return
        if self._zone_of(nx) not in agent.allowed_zones:
            return

        self.grid.move_agent(agent, (nx, ny))

    def _do_pick_up(self, agent) -> None:
        inventory = agent.knowledge["inventory"]
        max_inv   = 1 if agent.color == "red" else 2

        if len(inventory) >= max_inv:
            return

        for obj in self.grid.get_cell_list_contents([agent.pos]):
            if isinstance(obj, WasteAgent) and obj.waste_type == agent.color:
                inventory.append(obj.waste_type)
                self.grid.remove_agent(obj)
                obj.remove()
                if self.communication_enabled:
                    self.external_board.remove_by_position(agent.pos)
                return

    def _do_transform(self, agent) -> None:
        inv = agent.knowledge["inventory"]

        if agent.color == "green" and inv.count("green") >= 2:
            inv.remove("green"); inv.remove("green"); inv.append("yellow")
        elif agent.color == "yellow" and inv.count("yellow") >= 2:
            inv.remove("yellow"); inv.remove("yellow"); inv.append("red")

    def _do_put_down(self, agent, waste_type: str) -> None:
        inv = agent.knowledge["inventory"]
        if waste_type not in inv:
            return

        inv.remove(waste_type)
        cell_contents = self.grid.get_cell_list_contents([agent.pos])
        at_disposal   = any(isinstance(c, WasteDisposalZone) for c in cell_contents)

        if at_disposal and waste_type == "red":
            self.disposed_count += 1
            return

        self.grid.place_agent(WasteAgent(self, waste_type), agent.pos)

        x = agent.pos[0]
        target_color = None
        if agent.color == "green"  and waste_type == "yellow" and x >= self.z1_max_x:
            target_color = "yellow"
        elif agent.color == "yellow" and waste_type == "red"    and x >= self.z2_max_x:
            target_color = "red"

        if target_color and self.communication_enabled:
            self.external_board.post(
                agent.unique_id, agent.label, agent.color, target_color,
                "waste_available",
                {"waste_type": waste_type, "pos": list(agent.pos)},
                self.current_step,
            )

    def _get_percepts(self, agent) -> dict:
        percepts = {}
        cx, cy   = agent.pos

        cells = [(cx, cy)]
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                cells.append((nx, ny))

        for pos in cells:
            contents    = self.grid.get_cell_list_contents([pos])
            radioact    = 0.0
            wastes      = []
            robots      = []
            is_disposal = False

            for obj in contents:
                if isinstance(obj, RadioactivityAgent):
                    radioact = obj.radioactivity
                elif isinstance(obj, WasteAgent):
                    wastes.append({"waste_type": obj.waste_type})
                elif isinstance(obj, WasteDisposalZone):
                    is_disposal = True
                elif hasattr(obj, "color") and obj is not agent:
                    robots.append({"color": obj.color})

            percepts[pos] = {
                "radioactivity": radioact,
                "wastes":        wastes,
                "robots":        robots,
                "is_disposal":   is_disposal,
            }

        return percepts

    def get_robot_agents(self):
        return [a for a in self.agents if isinstance(a, (GreenAgent, YellowAgent, RedAgent))]

    def get_best_taker_for_request(self, request):
        """Return the robot with the lowest cost for *request*, or None if none qualifies."""
        candidates = []
        for robot in self.get_robot_agents():
            if robot.color != request.target_color or robot.unique_id == request.sender_id:
                continue
            cost = robot._compute_cost(request)
            if cost < float("inf"):
                candidates.append({"agent": robot, "cost": cost, "step_n": robot.steps_taken})

        if not candidates:
            return None
        candidates.sort(key=lambda c: (c["cost"], c["step_n"], c["agent"].label))
        return candidates[0]

    def step(self) -> None:
        self.current_step += 1
        if self.communication_enabled:
            self.internal_board.cleanup(self.current_step)
            self.external_board.cleanup(self.current_step)
        robots = self.get_robot_agents()
        random.shuffle(robots)
        for robot in robots:
            robot.step()
        self.datacollector.collect(self)

    def _count_waste(self, waste_type: str | None) -> int:
        return sum(
            1 for a in self.agents
            if isinstance(a, WasteAgent) and (waste_type is None or a.waste_type == waste_type)
        )

    def _count_inventory_waste(self) -> int:
        return sum(
            len(a.knowledge["inventory"])
            for a in self.agents
            if isinstance(a, (GreenAgent, YellowAgent, RedAgent))
        )

    def is_done(self) -> bool:
        return self._count_waste(None) == 0 and self._count_inventory_waste() == 0
