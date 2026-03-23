# group 18 : Aya Boukhari, Ikram Firdaous
# date of creation : 16-03-2026


import mesa
import random


class Radioactivity(mesa.Agent):
    """Passive agent placed on every cell of the grid.

    Attributes
    ----------
    zone : int
        1 = low radioactivity (z1, west)
        2 = medium radioactivity (z2, middle)
        3 = high radioactivity (z3, east)
    radioactivity_level : float
        Random level sampled uniformly within the zone range:
          z1 → [0.00, 0.33]
          z2 → [0.33, 0.66]
          z3 → [0.66, 1.00]
    """

    def __init__(self, model: mesa.Model, zone: int) -> None:
        super().__init__(model)
        self.zone = zone
        if zone == 1:
            self.radioactivity_level = random.uniform(0.0, 0.33)
        elif zone == 2:
            self.radioactivity_level = random.uniform(0.33, 0.66)
        else:  # zone == 3
            self.radioactivity_level = random.uniform(0.66, 1.0)

    def step(self) -> None:
        pass  # no behaviour


class WasteDisposalZone(mesa.Agent):
    """Passive agent that marks the waste-disposal cell in z3 (easternmost column).

    Robots identify this cell by looking for an agent of this type in their
    percepts.
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model)

    def step(self) -> None:
        pass  # no behaviour


class Waste(mesa.Agent):
    """Represents a piece of waste on the grid or in a robot's inventory.

    Attributes
    ----------
    waste_type : str
        One of ``"green"``, ``"yellow"``, or ``"red"``.
    """

    def __init__(self, model: mesa.Model, waste_type: str) -> None:
        super().__init__(model)
        assert waste_type in ("green", "yellow", "red"), (
            f"Unknown waste type: {waste_type}"
        )
        self.waste_type = waste_type

    def step(self) -> None:
        pass  # no behaviour
