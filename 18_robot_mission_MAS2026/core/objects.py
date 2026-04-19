# Group: 18 | Date: 2026-03-16 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# objects.py — Passive agents without behaviors

import random
import mesa


class RadioactivityAgent(mesa.Agent):
    """
    Passive agent placed in every cell to encode the zone and its radioactivity level.
    - zone 1 (z1): low radioactivity  [0.00, 0.33)
    - zone 2 (z2): medium radioactivity [0.33, 0.66)
    - zone 3 (z3): high radioactivity  [0.66, 1.00]
    Robot agents read this to know which zone they are in.
    """

    def __init__(self, model: mesa.Model, zone: int) -> None:
        super().__init__(model)
        self.zone = zone
        if zone == 1:
            self.radioactivity = random.uniform(0.00, 0.33)
        elif zone == 2:
            self.radioactivity = random.uniform(0.33, 0.66)
        else:  # zone == 3
            self.radioactivity = random.uniform(0.66, 1.00)

    def step(self) -> None:
        pass  # No behavior


class WasteDisposalZone(mesa.Agent):
    """
    Passive agent marking the waste disposal cell (easternmost zone, z3).
    Red robots must deliver red waste here; once deposited, waste is 'put away'.
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model)

    def step(self) -> None:
        pass  # No behavior


class WasteAgent(mesa.Agent):
    """
    Passive agent representing a piece of waste on the grid.
    waste_type ∈ {"green", "yellow", "red"}
    """

    VALID_TYPES = {"green", "yellow", "red"}

    def __init__(self, model: mesa.Model, waste_type: str = "green") -> None:
        super().__init__(model)
        if waste_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid waste_type '{waste_type}'. Must be one of {self.VALID_TYPES}")
        self.waste_type = waste_type

    def step(self) -> None:
        pass  # No behavior
