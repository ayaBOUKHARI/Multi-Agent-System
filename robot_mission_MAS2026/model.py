# Group: X | Date: 2026-03-20 | Members: (à compléter)
# model.py — RobotMission model (Mesa 3.x)
#
# Grid layout (west → east):
#   z1 [0 .. W//3-1]  — low radioactivity, initial green wastes
#   z2 [W//3 .. 2W//3-1]  — medium radioactivity
#   z3 [2W//3 .. W-1] — high radioactivity, waste disposal zone

import random
import mesa
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from objects import RadioactivityAgent, WasteAgent, WasteDisposalZone
from agents import GreenAgent, YellowAgent, RedAgent


# Direction vectors (Mesa grid: x east, y north)
DIRECTIONS = {
    "N":    ( 0,  1),
    "S":    ( 0, -1),
    "E":    ( 1,  0),
    "W":    (-1,  0),
    "stay": ( 0,  0),
}


class RobotMission(mesa.Model):
    """
    Multi-agent simulation of robots collecting dangerous waste.

    Parameters
    ----------
    width, height   : grid dimensions
    n_green_robots  : number of GreenAgent robots
    n_yellow_robots : number of YellowAgent robots
    n_red_robots    : number of RedAgent robots
    n_green_wastes  : initial number of green WasteAgent objects placed in z1
    seed            : random seed (optional)
    """

    def __init__(
        self,
        width: int          = 15,
        height: int         = 10,
        n_green_robots: int = 3,
        n_yellow_robots: int = 3,
        n_red_robots: int   = 3,
        n_green_wastes: int = 10,
        seed: int | None    = None,
    ) -> None:
        super().__init__(seed=seed)

        self.width  = width
        self.height = height
        self.grid   = MultiGrid(width, height, torus=False)

        # Zone x-boundaries (inclusive)
        self.z1_max_x = width // 3 - 1
        self.z2_max_x = 2 * width // 3 - 1
        # z3 goes from 2*width//3 to width-1

        self.zone_boundaries = {
            "z1_max_x": self.z1_max_x,
            "z2_max_x": self.z2_max_x,
            "width":    width,
            "height":   height,
        }

        self.disposal_pos: tuple = None  # set during grid build

        # Message router: agent.unique_id → list of pending messages (FIPA-ACL style)
        self.message_router: dict = {}

        # Build environment
        self._build_radioactivity()
        self._place_disposal_zone()
        self._place_initial_wastes(n_green_wastes)

        # Place robots
        self._place_robots(n_green_robots, n_yellow_robots, n_red_robots)

        # Data collection — track waste counts over time
        self.datacollector = DataCollector(
            model_reporters={
                "Green wastes":  lambda m: m._count_waste("green"),
                "Yellow wastes": lambda m: m._count_waste("yellow"),
                "Red wastes":    lambda m: m._count_waste("red"),
                "Total wastes":  lambda m: m._count_waste(None),
                "In inventories": lambda m: m._count_inventory_waste(),
                "Disposed":      lambda m: m.disposed_count,
            }
        )
        self.disposed_count = 0
        self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # Grid setup helpers
    # ------------------------------------------------------------------

    def _zone_of(self, x: int) -> int:
        """Return the zone number (1/2/3) for a given x coordinate."""
        if x <= self.z1_max_x:
            return 1
        if x <= self.z2_max_x:
            return 2
        return 3

    def _build_radioactivity(self) -> None:
        """Place one RadioactivityAgent per cell to encode zone info."""
        for x in range(self.width):
            zone = self._zone_of(x)
            for y in range(self.height):
                agent = RadioactivityAgent(self, zone)
                self.grid.place_agent(agent, (x, y))

    def _place_disposal_zone(self) -> None:
        """Place the WasteDisposalZone in the easternmost column (random row)."""
        x = self.width - 1
        y = self.random.randrange(self.height)
        disposal = WasteDisposalZone(self)
        self.grid.place_agent(disposal, (x, y))
        self.disposal_pos = (x, y)

    def _place_initial_wastes(self, n: int) -> None:
        """Place n green WasteAgents randomly in z1."""
        for _ in range(n):
            x = self.random.randrange(0, self.z1_max_x + 1)
            y = self.random.randrange(self.height)
            waste = WasteAgent(self, "green")
            self.grid.place_agent(waste, (x, y))

    def _place_robots(self, n_green: int, n_yellow: int, n_red: int) -> None:
        """Place robots in random positions within their allowed zones."""
        placements = [
            (GreenAgent,  n_green,  0,                  self.z1_max_x),
            (YellowAgent, n_yellow, 0,                  self.z2_max_x),
            (RedAgent,    n_red,    0,                  self.width - 1),
        ]
        for AgentClass, count, x_min, x_max in placements:
            for _ in range(count):
                x = self.random.randrange(x_min, x_max + 1)
                y = self.random.randrange(self.height)
                robot = AgentClass(self)
                # Initialise knowledge with model-level constants
                robot.knowledge["zone_boundaries"] = self.zone_boundaries
                robot.knowledge["disposal_pos"]    = self.disposal_pos
                robot.knowledge["pos"]             = (x, y)
                self.grid.place_agent(robot, (x, y))
                self.message_router[robot.unique_id] = []

    # ------------------------------------------------------------------
    # Action execution — model.do()
    # ------------------------------------------------------------------

    def do(self, agent, action: dict) -> dict:
        """
        Execute an action on behalf of an agent.
        Checks feasibility, applies consequences, returns updated percepts.

        Supported actions:
          {"type": "move",      "direction": "N"|"S"|"E"|"W"|"stay"}
          {"type": "pick_up"}
          {"type": "transform"}
          {"type": "put_down",  "waste_type": "green"|"yellow"|"red"}
        """
        action_type = action.get("type", "stay")

        if action_type == "move":
            self._do_move(agent, action.get("direction", "stay"))

        elif action_type == "pick_up":
            self._do_pick_up(agent)

        elif action_type == "transform":
            self._do_transform(agent)

        elif action_type == "put_down":
            self._do_put_down(agent, action.get("waste_type"))

        elif action_type == "send_message":
            self._do_send_message(agent, action.get("recipients"), action.get("message", {}))

        return self._get_percepts(agent)

    def _do_move(self, agent, direction: str) -> None:
        """Move agent one step in direction if within bounds and allowed zone."""
        dx, dy = DIRECTIONS.get(direction, (0, 0))
        cx, cy = agent.pos
        nx, ny = cx + dx, cy + dy

        # Bounds check
        if not (0 <= nx < self.width and 0 <= ny < self.height):
            return

        # Zone access check
        target_zone = self._zone_of(nx)
        if target_zone not in agent.allowed_zones:
            return

        self.grid.move_agent(agent, (nx, ny))

    def _do_pick_up(self, agent) -> None:
        """
        Pick up one waste from the agent's current cell.
        Green robot picks green, yellow picks yellow, red picks red.
        Inventory limit: green/yellow = 2, red = 1.
        """
        inventory    = agent.knowledge["inventory"]
        target_types = {"green": "green", "yellow": "yellow", "red": "red"}
        robot_target = target_types[agent.color]

        # Check inventory capacity
        max_inv = 1 if agent.color == "red" else 2
        if len(inventory) >= max_inv:
            return

        # Find matching waste in current cell
        cell_contents = self.grid.get_cell_list_contents([agent.pos])
        for obj in cell_contents:
            if isinstance(obj, WasteAgent) and obj.waste_type == robot_target:
                inventory.append(obj.waste_type)
                self.grid.remove_agent(obj)
                obj.remove()
                return

    def _do_transform(self, agent) -> None:
        """
        Transform wastes in inventory:
          GreenAgent:  2 green → 1 yellow
          YellowAgent: 2 yellow → 1 red
        """
        inv = agent.knowledge["inventory"]

        if agent.color == "green" and inv.count("green") >= 2:
            inv.remove("green")
            inv.remove("green")
            inv.append("yellow")

        elif agent.color == "yellow" and inv.count("yellow") >= 2:
            inv.remove("yellow")
            inv.remove("yellow")
            inv.append("red")

    def _do_put_down(self, agent, waste_type: str) -> None:
        """
        Deposit waste_type from inventory onto the grid.
        If at the disposal zone AND waste is red, the waste is 'put away' (removed).
        """
        inv = agent.knowledge["inventory"]
        if waste_type not in inv:
            return

        inv.remove(waste_type)

        # Check if at waste disposal zone
        cell_contents = self.grid.get_cell_list_contents([agent.pos])
        at_disposal   = any(isinstance(c, WasteDisposalZone) for c in cell_contents)

        if at_disposal and waste_type == "red":
            # Waste is officially disposed of — do not place on grid
            self.disposed_count += 1
        else:
            # Place waste back on grid at current position
            waste = WasteAgent(self, waste_type)
            self.grid.place_agent(waste, agent.pos)

    def _do_send_message(self, agent, recipients, message: dict) -> None:
        """
        Route a FIPA-ACL-style message to one or more robots.

        recipients=None  → broadcast to all robots of `to_color` (default: same color as sender).
        recipients=[ids] → unicast / multicast to specific agent unique_ids.

        The message dict may include an optional `to_color` key to specify the
        target color for a broadcast (e.g. a GreenAgent informing YellowAgents).
        """
        to_color = message.get("to_color")

        # Build envelope without the routing-only `to_color` field
        envelope = {
            "sender_id":    agent.unique_id,
            "sender_color": agent.color,
            "sender_pos":   agent.pos,
        }
        for k, v in message.items():
            if k != "to_color":
                envelope[k] = v

        if recipients is None:
            target_color = to_color if to_color else agent.color
            for a in self.agents:
                if hasattr(a, "color") and a.color == target_color and a is not agent:
                    self.message_router.setdefault(a.unique_id, []).append(envelope)
        else:
            for rid in recipients:
                if rid in self.message_router:
                    self.message_router[rid].append(envelope)

    # ------------------------------------------------------------------
    # Percept generation
    # ------------------------------------------------------------------

    def _get_percepts(self, agent) -> dict:
        """
        Return a dict of cell contents for the agent's current cell
        and all 4-neighbourhood cells (N, S, E, W).

        Format:
          {
            (x, y): {
              "radioactivity": float,
              "wastes":        [{"waste_type": str}, ...],
              "robots":        [{"color": str}, ...],
              "is_disposal":   bool,
            },
            ...
          }
        """
        percepts = {}
        cx, cy   = agent.pos

        cells_to_observe = [(cx, cy)]  # current cell
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                cells_to_observe.append((nx, ny))

        for pos in cells_to_observe:
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
                elif hasattr(obj, "color"):  # robot
                    if obj is not agent:
                        robots.append({"color": obj.color})

            percepts[pos] = {
                "radioactivity": radioact,
                "wastes":        wastes,
                "robots":        robots,
                "is_disposal":   is_disposal,
            }

        # Deliver pending mailbox messages (cleared after delivery)
        percepts["__mailbox__"] = list(self.message_router.get(agent.unique_id, []))
        self.message_router[agent.unique_id] = []

        return percepts

    # ------------------------------------------------------------------
    # Model step & data helpers
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the simulation by one step (random activation of robots)."""
        robots = [a for a in self.agents if isinstance(a, (GreenAgent, YellowAgent, RedAgent))]
        random.shuffle(robots)
        for robot in robots:
            robot.step()
        self.datacollector.collect(self)

    def _count_waste(self, waste_type: str | None) -> int:
        """Count WasteAgents on the grid (optionally filtered by type)."""
        count = 0
        for agent in self.agents:
            if isinstance(agent, WasteAgent):
                if waste_type is None or agent.waste_type == waste_type:
                    count += 1
        return count

    def _count_inventory_waste(self) -> int:
        """Count wastes currently held in all robot inventories."""
        total = 0
        for agent in self.agents:
            if isinstance(agent, (GreenAgent, YellowAgent, RedAgent)):
                total += len(agent.knowledge["inventory"])
        return total

    def is_done(self) -> bool:
        """Return True when no waste remains on the grid OR in any robot inventory."""
        return self._count_waste(None) == 0 and self._count_inventory_waste() == 0
