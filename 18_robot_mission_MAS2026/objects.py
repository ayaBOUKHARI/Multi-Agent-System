# groupe 18 : Aya Boukhari, Ikram Firdaous
# created on 16/03/2026

import mesa
import random

class Radioactivity(mesa.Agent):
    def __init__(self, unique_id, model, zone):
        super().__init__(unique_id, model)
        self.zone = zone
        if zone == 'z1':
            self.radioactivity = random.uniform(0, 0.33)         
        if zone == 'z2':
            self.radioactivity = random.uniform(0.33, 0.66)
        if zone == 'z3':
            self.radioactivity = random.uniform(0.66, 1.0)
    def step(self):
        pass

class Waste(mesa.Agent):
    def __init__(self, unique_id, model, waste_type):
        super().__init__(unique_id, model)
        self.waste_type = waste_type  # 'green', 'yellow', ou 'red'
    
    def step(self):
        pass

class WasteDisposalZone(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
    
    def step(self):
        pass
