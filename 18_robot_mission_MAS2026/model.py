# group 18 : Aya Boukhari, Ikram Firdaous
# date of creation : 16-03-2026



import random
import mesa
from mesa.space import MultiGrid
from mesa import DataCollector

from objects import Radioactivity, WasteDisposalZone, Waste
from agents import GreenAgent, YellowAgent, RedAgent


class RobotMission(mesa.Model):
    """Multi-agent model of robots cleaning dangerous waste.

    Parameters
    ----------
    width, height : int
        Grid dimensions.
    n_green_robots, n_yellow_robots, n_red_robots : int
        Number of each robot type to create.
    n_initial_waste : int
        Number of green waste items to scatter in z1 at initialization.
    seed : int | None
        Random seed for reproducibility.
    """

    def __init__(
        self,
        width: int = 21,
        height: int = 10,
        n_green_robots: int = 3,
        n_yellow_robots: int = 2,
        n_red_robots: int = 2,
        n_initial_waste: int = 15,
        seed: int | None = None,
    ) -> None:
        super().__init__(seed=seed)

        self.width = width
        self.height = height

        # Zone column boundaries (inclusive)
        self.z1_end = width // 3 - 1          # e.g. 6  for width=21
        self.z2_end = 2 * (width // 3) - 1    # e.g. 13 for width=21

        # Grid (multiple agents per cell allowed)
        self.grid = MultiGrid(width, height, torus=False)

        # ------------------------------------------------------------------
        # 1. Place Radioactivity agents on every cell
        # ------------------------------------------------------------------
        for x in range(width):
            for y in range(height):
                if x <= self.z1_end:
                    zone = 1
                elif x <= self.z2_end:
                    zone = 2
                else:
                    zone = 3
                rad = Radioactivity(self, zone)
                self.grid.place_agent(rad, (x, y))

        # ------------------------------------------------------------------
        # 2. Place Waste Disposal Zone in z3 (random cell in easternmost col)
        # ------------------------------------------------------------------
        disposal_x = width - 1
        disposal_y = self.random.randint(0, height - 1)
        self.disposal_zone_pos = (disposal_x, disposal_y)
        wdz = WasteDisposalZone(self)
        self.grid.place_agent(wdz, self.disposal_zone_pos)

        # ------------------------------------------------------------------
        # 3. Scatter initial green waste in z1
        # ------------------------------------------------------------------
        z1_cells = [(x, y) for x in range(self.z1_end + 1) for y in range(height)]
        waste_positions = self.random.choices(z1_cells, k=n_initial_waste)
        for pos in waste_positions:
            w = Waste(self, "green")
            self.grid.place_agent(w, pos)

        # ------------------------------------------------------------------
        # 4. Create and place robots
        # ------------------------------------------------------------------
        # Helper – allowed x range for each robot type
        def _place_robots(robot_cls, count, x_min, x_max, zone_x_range, z1_x_max, z2_x_max):
            for _ in range(count):
                robot = robot_cls(self)
                robot.knowledge["zone_x_range"] = zone_x_range
                robot.knowledge["z1_x_max"] = z1_x_max
                robot.knowledge["z2_x_max"] = z2_x_max
                robot.knowledge["grid_height"] = height
                x = self.random.randint(x_min, x_max)
                y = self.random.randint(0, height - 1)
                self.grid.place_agent(robot, (x, y))
                # Give initial percepts so the first step works correctly
                robot.percepts = self._get_percepts(robot)

        _place_robots(
            GreenAgent, n_green_robots,
            0, self.z1_end,
            (0, self.z1_end),
            self.z1_end, self.z2_end,
        )
        _place_robots(
            YellowAgent, n_yellow_robots,
            0, self.z2_end,
            (0, self.z2_end),
            self.z1_end, self.z2_end,
        )
        _place_robots(
            RedAgent, n_red_robots,
            0, width - 1,
            (0, width - 1),
            self.z1_end, self.z2_end,
        )
        # Red robots know the disposal zone position (mission briefing)
        for agent in self.agents:
            if isinstance(agent, RedAgent):
                agent.knowledge["disposal_zone_pos"] = self.disposal_zone_pos

        # ------------------------------------------------------------------
        # 5. Data collector
        # ------------------------------------------------------------------
        self.datacollector = DataCollector(
            model_reporters={
                "Green waste (grid)": lambda m: m._count_waste("green"),
                "Yellow waste (grid)": lambda m: m._count_waste("yellow"),
                "Red waste (grid)": lambda m: m._count_waste("red"),
                "Green waste (carried)": lambda m: m._count_inventory_waste("green"),
                "Yellow waste (carried)": lambda m: m._count_inventory_waste("yellow"),
                "Red waste (carried)": lambda m: m._count_inventory_waste("red"),
                "Disposed waste": lambda m: m.disposed_count,
            }
        )
        self.disposed_count = 0
        self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _count_waste(self, waste_type: str) -> int:
        """Count waste agents of *waste_type* currently placed on the grid."""
        return sum(
            1
            for agent in self.agents
            if isinstance(agent, Waste)
            and agent.waste_type == waste_type
            and agent.pos is not None  # excludes waste held in robot inventories
        )

    def _count_inventory_waste(self, waste_type: str) -> int:
        """Count waste of *waste_type* currently carried by robots."""
        total = 0
        for agent in self.agents:
            if isinstance(agent, (GreenAgent, YellowAgent, RedAgent)):
                total += sum(
                    1 for w in agent.knowledge["inventory"]
                    if w.waste_type == waste_type
                )
        return total

    def is_finished(self) -> bool:
        """Return True when no more productive work can be done.

        The simulation ends when:
        - No waste remains on the grid.
        - No red waste is still being transported (red waste can always be disposed).
        Green/yellow remainders carried by robots (odd-count remainder that cannot
        form a pair) are acceptable stopping conditions.
        """
        no_grid = all(
            self._count_waste(t) == 0 for t in ("green", "yellow", "red")
        )
        # Red waste can always reach the disposal zone, so wait until it's gone
        no_red_in_transit = self._count_inventory_waste("red") == 0
        return no_grid and no_red_in_transit

    def _get_percepts(self, robot) -> dict:
        """Return percepts for the Moore neighbourhood (radius 1) of *robot*."""
        percepts = {}
        neighbors = self.grid.get_neighborhood(robot.pos, moore=True,
                                               include_center=True, radius=1)
        for cell_pos in neighbors:
            contents = self.grid.get_cell_list_contents([cell_pos])
            wastes = [
                {"type": a.waste_type, "agent": a}
                for a in contents if isinstance(a, Waste)
            ]
            robots = [a for a in contents if isinstance(a, (GreenAgent, YellowAgent, RedAgent))]
            is_disposal = any(isinstance(a, WasteDisposalZone) for a in contents)
            rad_level = next(
                (a.radioactivity_level for a in contents if isinstance(a, Radioactivity)),
                None,
            )
            percepts[cell_pos] = {
                "wastes": wastes,
                "robots": robots,
                "is_disposal_zone": is_disposal,
                "radioactivity": rad_level,
            }
        return percepts

    # ------------------------------------------------------------------
    # do – execute an action and return percepts
    # ------------------------------------------------------------------

    def do(self, robot, action: dict) -> dict:
        """Execute *action* for *robot*, then return updated percepts.

        Supported action types
        ----------------------
        ``{"type": "move",      "target": (x, y)}``
        ``{"type": "pick_up"}``   – pick up one waste at current cell
        ``{"type": "transform"}`` – transform 2 green→yellow OR 2 yellow→red
        ``{"type": "drop"}``      – drop 1 waste from inventory onto current cell
        ``{"type": "put_away"}``  – drop 1 red waste at disposal zone (removes it)
        ``{"type": "wait"}``      – do nothing
        """
        if action is None:
            return self._get_percepts(robot)

        action_type = action.get("type", "wait")

        # ---- MOVE --------------------------------------------------------
        if action_type == "move":
            target = action["target"]
            tx, ty = target
            x_min, x_max = robot.knowledge["zone_x_range"]

            # Feasibility: target must be within allowed zone and grid bounds
            if (
                0 <= tx < self.width
                and 0 <= ty < self.height
                and x_min <= tx <= x_max
                and self.grid.is_cell_empty((tx, ty)) is False  # always True for MultiGrid
            ):
                # Check it's an adjacent cell (Moore, distance 1)
                cx, cy = robot.pos
                if abs(tx - cx) <= 1 and abs(ty - cy) <= 1:
                    self.grid.move_agent(robot, (tx, ty))

        # ---- PICK UP -----------------------------------------------------
        elif action_type == "pick_up":
            cell_contents = self.grid.get_cell_list_contents([robot.pos])
            wastes_here = [a for a in cell_contents if isinstance(a, Waste)]

            if wastes_here:
                # Determine which waste type this robot may pick up
                if isinstance(robot, GreenAgent):
                    allowed_type = "green"
                    max_carry = 2
                elif isinstance(robot, YellowAgent):
                    allowed_type = "yellow"
                    max_carry = 2
                else:  # RedAgent
                    allowed_type = "red"
                    max_carry = 1

                current_count = len(robot.knowledge["inventory"])
                matching = [w for w in wastes_here if w.waste_type == allowed_type]

                if matching and current_count < max_carry:
                    waste = matching[0]
                    self.grid.remove_agent(waste)
                    robot.knowledge["inventory"].append(waste)

        # ---- TRANSFORM ---------------------------------------------------
        elif action_type == "transform":
            inventory = robot.knowledge["inventory"]

            if isinstance(robot, GreenAgent):
                greens = [w for w in inventory if w.waste_type == "green"]
                if len(greens) >= 2:
                    # Remove two green wastes
                    for w in greens[:2]:
                        inventory.remove(w)
                    # Add one yellow waste
                    new_waste = Waste(self, "yellow")
                    inventory.append(new_waste)

            elif isinstance(robot, YellowAgent):
                yellows = [w for w in inventory if w.waste_type == "yellow"]
                if len(yellows) >= 2:
                    for w in yellows[:2]:
                        inventory.remove(w)
                    new_waste = Waste(self, "red")
                    inventory.append(new_waste)

        # ---- DROP --------------------------------------------------------
        elif action_type == "drop":
            inventory = robot.knowledge["inventory"]
            if inventory:
                waste = inventory.pop()
                self.grid.place_agent(waste, robot.pos)

        # ---- PUT AWAY (dispose of red waste at disposal zone) ------------
        elif action_type == "put_away":
            inventory = robot.knowledge["inventory"]
            red_wastes = [w for w in inventory if w.waste_type == "red"]
            if red_wastes and robot.pos == self.disposal_zone_pos:
                waste = red_wastes[0]
                inventory.remove(waste)
                self.disposed_count += 1
                # Waste is removed from simulation (not placed back on grid)

        # ---- WAIT --------------------------------------------------------
        # (no action taken)

        return self._get_percepts(robot)

    # ------------------------------------------------------------------
    # Mesa step
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the simulation by one step."""
        # Only step robot agents (passive objects have no behaviour)
        robot_agents = self.agents.select(
            lambda a: isinstance(a, (GreenAgent, YellowAgent, RedAgent))
        )
        robot_agents.shuffle_do("step")
        self.datacollector.collect(self)
