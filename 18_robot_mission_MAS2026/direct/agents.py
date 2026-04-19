# Group: 18 | Date: 2026-03-16 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# agents.py — Peer-to-peer direct-message protocol.

import random
import mesa


def _dir_from_delta(dx: int, dy: int) -> str:
    """Convert a (dx, dy) offset to a dominant cardinal direction."""
    if dx == 0 and dy == 0:
        return "stay"
    if abs(dx) >= abs(dy):
        return "E" if dx > 0 else "W"
    return "N" if dy > 0 else "S"


def deliberate_green(knowledge: dict) -> dict:
    """
    Decision function for GreenAgent (zone z1).
    Transforms 2 green into 1 yellow, deposits it at the z1/z2 border,
    and uses direct messaging to coordinate handoffs when stuck with 1 unpaired green.
    """
    inventory = knowledge["inventory"]
    pos = knowledge["pos"]
    percepts = knowledge["percepts"]
    z1_max_x = knowledge["zone_boundaries"]["z1_max_x"]
    known_wastes = knowledge.get("known_wastes", {})
    comm = knowledge.get("comm_enabled", True)
    handoff_role = knowledge.get("handoff_role")
    partner_pos = knowledge.get("partner_pos")
    pending_msg = knowledge.get("pending_msg")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    green_count = inventory.count("green")
    yellow_count = inventory.count("yellow")

    if comm and pending_msg:
        return pending_msg

    if green_count >= 2:
        return {"type": "transform"}

    if yellow_count >= 1:
        if pos[0] >= z1_max_x:
            return {"type": "put_down", "waste_type": "yellow"}
        return {"type": "move", "direction": "E"}

    if comm and handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "green"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "green":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "green" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    if comm and handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    if comm and green_count == 1 and random.random() < 0.15:
        return {
            "type": "send_message",
            "recipients": None,
            "message": {
                "performative": "inform",
                "content": {"type": "has_unpaired", "waste": "green", "pos": list(pos)},
            },
        }

    if comm:
        for cell_pos, contents in percepts.items():
            for obj in contents.get("wastes", []):
                if obj["waste_type"] == "yellow":
                    return {
                        "type": "send_message",
                        "recipients": None,
                        "message": {
                            "to_color": "yellow",
                            "performative": "inform",
                            "content": {
                                "type": "waste_at",
                                "waste": "yellow",
                                "pos": list(cell_pos),
                            },
                        },
                    }

    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_yellow(knowledge: dict) -> dict:
    """
    Decision function for YellowAgent (zones z1 + z2).
    Transforms 2 yellow into 1 red, deposits it at the z2/z3 border,
    and uses direct messaging to coordinate handoffs when stuck with 1 unpaired yellow.
    """
    inventory = knowledge["inventory"]
    pos = knowledge["pos"]
    percepts = knowledge["percepts"]
    z2_max_x = knowledge["zone_boundaries"]["z2_max_x"]
    known_wastes = knowledge.get("known_wastes", {})
    comm = knowledge.get("comm_enabled", True)
    handoff_role = knowledge.get("handoff_role")
    partner_pos = knowledge.get("partner_pos")
    pending_msg = knowledge.get("pending_msg")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    yellow_count = inventory.count("yellow")
    red_count = inventory.count("red")

    if comm and pending_msg:
        return pending_msg

    if yellow_count >= 2:
        return {"type": "transform"}

    if red_count >= 1:
        if pos[0] >= z2_max_x:
            return {"type": "put_down", "waste_type": "red"}
        return {"type": "move", "direction": "E"}

    if comm and handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "yellow"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "yellow":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "yellow" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    if comm and handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    if comm and yellow_count == 1 and random.random() < 0.15:
        return {
            "type": "send_message",
            "recipients": None,
            "message": {
                "performative": "inform",
                "content": {"type": "has_unpaired", "waste": "yellow", "pos": list(pos)},
            },
        }

    if comm:
        for cell_pos, contents in percepts.items():
            for obj in contents.get("wastes", []):
                if obj["waste_type"] == "red":
                    return {
                        "type": "send_message",
                        "recipients": None,
                        "message": {
                            "to_color": "red",
                            "performative": "inform",
                            "content": {
                                "type": "waste_at",
                                "waste": "red",
                                "pos": list(cell_pos),
                            },
                        },
                    }

    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_red(knowledge: dict) -> dict:
    """Decision function for RedAgent (all zones). Picks up red waste and delivers it to the disposal zone."""
    inventory = knowledge["inventory"]
    pos = knowledge["pos"]
    percepts = knowledge["percepts"]
    disposal_pos = knowledge.get("disposal_pos")
    known_wastes = knowledge.get("known_wastes", {})
    comm = knowledge.get("comm_enabled", True)
    pending_msg = knowledge.get("pending_msg")

    red_count = inventory.count("red")

    if comm and pending_msg:
        return pending_msg

    if red_count >= 1 and disposal_pos:
        if pos == disposal_pos:
            return {"type": "put_down", "waste_type": "red"}
        dx, dy = disposal_pos[0] - pos[0], disposal_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "red":
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "red":
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


class DirectRobotAgent(mesa.Agent):
    """Base class for robots using peer-to-peer direct messaging."""

    def __init__(self, model: mesa.Model, color: str) -> None:
        super().__init__(model)
        self.color = color
        self.label = ""
        self.allowed_zones: set = set()
        self.deliberate_fn = None
        self._last_percepts: dict = {}

        self.knowledge: dict = {
            "pos": None,
            "inventory": [],
            "percepts": {},
            "zone_boundaries": {},
            "known_wastes": {},
            "disposal_pos": None,
            "comm_enabled": True,
            "mailbox": [],
            "pending_msg": None,
            "partner_id": None,
            "partner_pos": None,
            "handoff_role": None,
            "handoff_wait": 0,
            "drop_avoid_pos": None,
        }

    def _check_handoff_resolution(self) -> None:
        """Clears handoff state when it completes naturally or times out."""
        role = self.knowledge.get("handoff_role")
        if not role:
            self.knowledge["handoff_wait"] = 0
            return

        inv = self.knowledge["inventory"]
        handoff_waste = "green" if self.color == "green" else "yellow"

        if role == "initiator":
            self.knowledge["handoff_wait"] = self.knowledge.get("handoff_wait", 0) + 1
            if inv.count(handoff_waste) >= 2 or self.knowledge["handoff_wait"] > 20:
                self.knowledge.update({
                    "handoff_role": None,
                    "partner_id": None,
                    "partner_pos": None,
                    "handoff_wait": 0,
                })

        elif role == "responder":
            self.knowledge["handoff_wait"] = self.knowledge.get("handoff_wait", 0) + 1
            if handoff_waste not in inv or self.knowledge["handoff_wait"] > 40:
                self.knowledge.update({
                    "handoff_role": None,
                    "partner_id": None,
                    "partner_pos": None,
                    "handoff_wait": 0,
                })

    def _process_message(self, msg: dict) -> None:
        """Integrate a single incoming message into the knowledge base."""
        performative = msg.get("performative")
        content = msg.get("content", {})
        content_type = content.get("type")

        if performative == "inform" and content_type == "waste_at":
            pos = tuple(content["pos"])
            self.knowledge["known_wastes"][pos] = content["waste"]
            return

        if self.color not in ("green", "yellow"):
            return

        handoff_waste = "green" if self.color == "green" else "yellow"
        inv = self.knowledge["inventory"]

        if performative == "inform" and content_type == "has_unpaired":
            if (
                content["waste"] == handoff_waste
                and self.knowledge["partner_id"] is None
                and inv.count(handoff_waste) == 1
                and self.knowledge["pending_msg"] is None
                and msg["sender_id"] != self.unique_id
            ):
                sender_pos = tuple(msg["sender_pos"])
                self.knowledge["partner_id"] = msg["sender_id"]
                self.knowledge["partner_pos"] = sender_pos
                self.knowledge["handoff_role"] = "responder"
                self.knowledge["pending_msg"] = {
                    "type": "send_message",
                    "recipients": [msg["sender_id"]],
                    "message": {
                        "performative": "accept",
                        "content": {"type": "handoff_accept"},
                    },
                }

        elif performative == "accept" and content_type == "handoff_accept":
            if self.knowledge["partner_id"] is None:
                self.knowledge["partner_id"] = msg["sender_id"]
                self.knowledge["handoff_role"] = "initiator"

    def _update_knowledge(self, percepts: dict) -> None:
        """Integrate new percepts and incoming messages."""
        mailbox = percepts.pop("__mailbox__", [])
        self.knowledge["pending_msg"] = None

        drop_pos = self.knowledge.get("drop_avoid_pos")
        if drop_pos is not None and drop_pos != self.pos:
            self.knowledge["drop_avoid_pos"] = None

        self.knowledge["pos"] = self.pos
        self.knowledge["percepts"] = percepts

        for cell_pos, contents in percepts.items():
            if not contents.get("wastes"):
                self.knowledge["known_wastes"].pop(cell_pos, None)
            else:
                for w in contents["wastes"]:
                    self.knowledge["known_wastes"][cell_pos] = w["waste_type"]

        self._check_handoff_resolution()

        for msg in mailbox:
            self._process_message(msg)

        self.knowledge["mailbox"] = mailbox

    def step(self) -> None:
        self._update_knowledge(self._last_percepts)
        action = self.deliberate_fn(self.knowledge)

        if action.get("type") == "put_down":
            self.knowledge["drop_avoid_pos"] = self.pos
        else:
            self.knowledge["drop_avoid_pos"] = None

        self._last_percepts = self.model.do(self, action)


class DirectGreenAgent(DirectRobotAgent):
    """Green robot — operates only in z1. Collects 2 green → 1 yellow."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="green")
        self.allowed_zones = {1}
        self.deliberate_fn = deliberate_green


class DirectYellowAgent(DirectRobotAgent):
    """Yellow robot — operates in z1 + z2. Collects 2 yellow → 1 red."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="yellow")
        self.allowed_zones = {1, 2}
        self.deliberate_fn = deliberate_yellow


class DirectRedAgent(DirectRobotAgent):
    """Red robot — operates in all zones. Carries 1 red → disposal."""

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="red")
        self.allowed_zones = {1, 2, 3}
        self.deliberate_fn = deliberate_red
