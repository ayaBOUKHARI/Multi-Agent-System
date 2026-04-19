# Group: 18 | Date: 2026-03-16 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# model.py — Simulation model using the peer-to-peer direct-message protocol.

import random
import mesa
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector

from core.objects import RadioactivityAgent, WasteAgent, WasteDisposalZone
from .agents import DirectGreenAgent, DirectYellowAgent, DirectRedAgent


DIRECTIONS = {
    "N": (0, 1),
    "S": (0, -1),
    "E": (1, 0),
    "W": (-1, 0),
    "stay": (0, 0),
}

_ROBOT_TYPES = (DirectGreenAgent, DirectYellowAgent, DirectRedAgent)


class DirectRobotMission(mesa.Model):
    """
    Multi-agent simulation using peer-to-peer direct messaging.

    Agents communicate by broadcasting or unicasting messages to one another
    through the model's message router.  There is no shared board — each
    agent's mailbox is delivered with its percepts at the start of each step.
    """

    def __init__(
        self,
        width: int = 15,
        height: int = 10,
        n_green_robots: int = 3,
        n_yellow_robots: int = 3,
        n_red_robots: int = 3,
        n_green_wastes: int = 10,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)

        self.width = width
        self.height = height
        self.grid = MultiGrid(width, height, torus=False)

        self.z1_max_x = width // 3 - 1
        self.z2_max_x = 2 * width // 3 - 1
        self.zone_boundaries = {
            "z1_max_x": self.z1_max_x,
            "z2_max_x": self.z2_max_x,
            "width": width,
            "height": height,
        }

        self.disposal_pos: tuple = None
        self.current_step = 0
        self.communication_enabled = False  # no shared board in this mode
        self.comm_enabled = True

        self.message_router: dict[int, list[dict]] = {}
        self.disposed_count = 0

        self._build_radioactivity()
        self._place_disposal_zone()
        self._place_initial_wastes(n_green_wastes)
        self._place_robots(n_green_robots, n_yellow_robots, n_red_robots)

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

    # Grid setup
    def _zone_of(self, x: int) -> int:
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
        prefix = {"green": "g", "yellow": "y", "red": "r"}

        placements = [
            (DirectGreenAgent,  n_green,  0, self.z1_max_x),
            (DirectYellowAgent, n_yellow, 0, self.z2_max_x),
            (DirectRedAgent,    n_red,    0, self.width - 1),
        ]
        for AgentClass, count, x_min, x_max in placements:
            for _ in range(count):
                x = self.random.randrange(x_min, x_max + 1)
                y = self.random.randrange(self.height)
                robot = AgentClass(self)
                counters[robot.color] += 1
                robot.label = f"{prefix[robot.color]}{counters[robot.color]}"
                robot.knowledge["zone_boundaries"] = self.zone_boundaries
                robot.knowledge["disposal_pos"] = self.disposal_pos
                robot.knowledge["pos"] = (x, y)
                robot.knowledge["comm_enabled"] = self.comm_enabled
                self.grid.place_agent(robot, (x, y))
                self.message_router[robot.unique_id] = []

    # Action execution
    def do(self, agent, action: dict) -> dict:
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
        max_inv = 1 if agent.color == "red" else 2

        if len(inventory) >= max_inv:
            return

        for obj in self.grid.get_cell_list_contents([agent.pos]):
            if isinstance(obj, WasteAgent) and obj.waste_type == agent.color:
                inventory.append(obj.waste_type)
                self.grid.remove_agent(obj)
                obj.remove()
                return

    def _do_transform(self, agent) -> None:
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
        inv = agent.knowledge["inventory"]
        if waste_type not in inv:
            return

        inv.remove(waste_type)
        cell_contents = self.grid.get_cell_list_contents([agent.pos])
        at_disposal = any(isinstance(c, WasteDisposalZone) for c in cell_contents)

        if at_disposal and waste_type == "red":
            self.disposed_count += 1
            return

        self.grid.place_agent(WasteAgent(self, waste_type), agent.pos)

    def _do_send_message(self, agent, recipients, message: dict) -> None:
        to_color = message.get("to_color")
        envelope = {
            "sender_id": agent.unique_id,
            "sender_color": agent.color,
            "sender_pos": agent.pos,
        }
        for k, v in message.items():
            if k != "to_color":
                envelope[k] = v

        if recipients is None:
            target_color = to_color if to_color else agent.color
            for other in self.agents:
                if hasattr(other, "color") and other.color == target_color and other is not agent:
                    self.message_router.setdefault(other.unique_id, []).append(envelope)
        else:
            for rid in recipients:
                if rid in self.message_router:
                    self.message_router[rid].append(envelope)

    # Percept generation
    def _get_percepts(self, agent) -> dict:
        percepts = {}
        cx, cy = agent.pos

        cells_to_observe = [(cx, cy)]
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                cells_to_observe.append((nx, ny))

        for pos in cells_to_observe:
            contents = self.grid.get_cell_list_contents([pos])
            radioact = 0.0
            wastes = []
            robots = []
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
                "wastes": wastes,
                "robots": robots,
                "is_disposal": is_disposal,
            }

        percepts["__mailbox__"] = list(self.message_router.get(agent.unique_id, []))
        self.message_router[agent.unique_id] = []
        return percepts

    # Model step & helpers
    def step(self) -> None:
        self.current_step += 1
        robots = [a for a in self.agents if isinstance(a, _ROBOT_TYPES)]
        random.shuffle(robots)
        for robot in robots:
            robot.step()
        self.datacollector.collect(self)

    def _count_waste(self, waste_type: str | None) -> int:
        count = 0
        for agent in self.agents:
            if isinstance(agent, WasteAgent):
                if waste_type is None or agent.waste_type == waste_type:
                    count += 1
        return count

    def _count_inventory_waste(self) -> int:
        return sum(
            len(a.knowledge["inventory"])
            for a in self.agents
            if isinstance(a, _ROBOT_TYPES)
        )

    def is_done(self) -> bool:
        return self._count_waste(None) == 0 and self._count_inventory_waste() == 0
