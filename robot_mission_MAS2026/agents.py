# Group: X | Date: 2026-03-20 | Members: (à compléter)
# agents.py — Robot agent classes: GreenAgent, YellowAgent, RedAgent
#
# Agent loop (per step):
#   1. update(knowledge, percepts)  — integrates percepts + incoming messages
#   2. action = deliberate(knowledge) — reasoning WITHOUT access to external variables
#   3. percepts = model.do(self, action)  — execution + return of new percepts
#
# Communication (Step 2 — FIPA-ACL style, decentralised):
#   Protocol A — Waste Handoff: resolves deadlock when robots hold unpaired wastes.
#     initiator: broadcasts INFORM has_unpaired → receives ACCEPT → stays put briefly.
#     responder: receives INFORM → sends ACCEPT → navigates to initiator → put_down.
#     drop_avoid_pos: prevents the responder from immediately re-picking up its dropped waste.
#   Protocol B — Map Sharing: robots inform others of wastes outside their domain.
#     GreenAgent seeing yellow waste → INFORM waste_at to yellow robots.
#     YellowAgent seeing red waste  → INFORM waste_at to red robots.

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
    Priority order:
      0. Send any pending one-shot message (e.g. handoff ACCEPT reply)
      1. Transform: 2 green → 1 yellow
      2. Transport yellow east to z1/z2 boundary → put_down
      3. Handoff responder: navigate to partner position → put_down green
      4. Pick up visible green waste (skips drop_avoid_pos to avoid self-pickup)
      5. Navigate toward remembered green waste (skips drop_avoid_pos)
      6. Handoff initiator: stay put and wait for responder to arrive
      7. Stuck with 1 green: wander to find more greens AND occasionally broadcast
      8. Protocol B: inform yellow robots of any yellow waste in view
      9. Random walk within z1
    """
    inventory      = knowledge["inventory"]
    pos            = knowledge["pos"]
    percepts       = knowledge["percepts"]
    z1_max_x       = knowledge["zone_boundaries"]["z1_max_x"]
    known_wastes   = knowledge.get("known_wastes", {})
    handoff_role   = knowledge.get("handoff_role")
    partner_pos    = knowledge.get("partner_pos")
    pending_msg    = knowledge.get("pending_msg")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    green_count  = inventory.count("green")
    yellow_count = inventory.count("yellow")

    # 0. Send pending message (ACCEPT reply queued during _update_knowledge)
    if pending_msg:
        return pending_msg

    # 1. Transform
    if green_count >= 2:
        return {"type": "transform"}

    # 2. Transport yellow east → deposit at z1/z2 border
    if yellow_count >= 1:
        if pos[0] >= z1_max_x:
            return {"type": "put_down", "waste_type": "yellow"}
        return {"type": "move", "direction": "E"}

    # 3. Handoff responder: go to initiator's cell and drop waste
    if handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "green"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Pick up visible green waste.
    #    Skip drop_avoid_pos: the waste we dropped this step (to avoid re-picking it up).
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "green":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Navigate toward a remembered green waste (also skip drop_avoid_pos)
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "green" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 6. Handoff initiator: stay in place until responder drops the waste
    if handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    # 7. Stuck with 1 green: wander to explore the grid (find more greens),
    #    and occasionally broadcast to seek a pairing partner.
    #    85 % of the time → random walk (robots MUST move to discover grid greens).
    #    15 % of the time → broadcast (allows forming a pair when grid is empty).
    if green_count == 1 and random.random() < 0.15:
        return {
            "type": "send_message",
            "recipients": None,        # broadcast to all green robots
            "message": {
                "performative": "inform",
                "content": {"type": "has_unpaired", "waste": "green", "pos": list(pos)},
            },
        }

    # 8. Protocol B: share yellow waste locations with yellow robots
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "yellow":
                return {
                    "type": "send_message",
                    "recipients": None,
                    "message": {
                        "to_color":     "yellow",
                        "performative": "inform",
                        "content": {"type": "waste_at", "waste": "yellow", "pos": list(cell_pos)},
                    },
                }

    # 9. Random walk (zone enforced by model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_yellow(knowledge: dict) -> dict:
    """
    Deliberation for YellowAgent (zones z1 + z2).
    Priority order:
      0. Send any pending one-shot message
      1. Transform: 2 yellow → 1 red
      2. Transport red east to z2/z3 boundary → put_down
      3. Handoff responder: navigate to partner → put_down yellow
      4. Pick up visible yellow waste (skips drop_avoid_pos)
      5. Navigate toward remembered yellow waste (skips drop_avoid_pos)
      6. Handoff initiator: stay put
      7. Stuck with 1 yellow: wander + occasionally broadcast
      8. Protocol B: inform red robots of any red waste in view
      9. Random walk within z1/z2
    """
    inventory      = knowledge["inventory"]
    pos            = knowledge["pos"]
    percepts       = knowledge["percepts"]
    z2_max_x       = knowledge["zone_boundaries"]["z2_max_x"]
    known_wastes   = knowledge.get("known_wastes", {})
    handoff_role   = knowledge.get("handoff_role")
    partner_pos    = knowledge.get("partner_pos")
    pending_msg    = knowledge.get("pending_msg")
    drop_avoid_pos = knowledge.get("drop_avoid_pos")

    yellow_count = inventory.count("yellow")
    red_count    = inventory.count("red")

    # 0. Send pending message
    if pending_msg:
        return pending_msg

    # 1. Transform
    if yellow_count >= 2:
        return {"type": "transform"}

    # 2. Transport red east → deposit at z2/z3 border
    if red_count >= 1:
        if pos[0] >= z2_max_x:
            return {"type": "put_down", "waste_type": "red"}
        return {"type": "move", "direction": "E"}

    # 3. Handoff responder
    if handoff_role == "responder" and partner_pos:
        if pos == partner_pos:
            return {"type": "put_down", "waste_type": "yellow"}
        dx, dy = partner_pos[0] - pos[0], partner_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 4. Pick up visible yellow waste
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "yellow":
                if cell_pos == drop_avoid_pos:
                    continue
                dx, dy = cell_pos[0] - pos[0], cell_pos[1] - pos[1]
                if dx == 0 and dy == 0:
                    return {"type": "pick_up"}
                return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 5. Navigate toward remembered yellow waste
    for waste_pos, waste_type in list(known_wastes.items()):
        if waste_type == "yellow" and waste_pos != drop_avoid_pos:
            dx, dy = waste_pos[0] - pos[0], waste_pos[1] - pos[1]
            if dx == 0 and dy == 0:
                return {"type": "pick_up"}
            return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 6. Handoff initiator: wait for responder
    if handoff_role == "initiator":
        return {"type": "move", "direction": "stay"}

    # 7. Stuck with 1 yellow: wander + occasionally broadcast
    if yellow_count == 1 and random.random() < 0.15:
        return {
            "type": "send_message",
            "recipients": None,
            "message": {
                "performative": "inform",
                "content": {"type": "has_unpaired", "waste": "yellow", "pos": list(pos)},
            },
        }

    # 8. Protocol B: share red waste locations with red robots
    for cell_pos, contents in percepts.items():
        for obj in contents.get("wastes", []):
            if obj["waste_type"] == "red":
                return {
                    "type": "send_message",
                    "recipients": None,
                    "message": {
                        "to_color":     "red",
                        "performative": "inform",
                        "content": {"type": "waste_at", "waste": "red", "pos": list(cell_pos)},
                    },
                }

    # 9. Random walk (zone enforced by model.do)
    return {"type": "move", "direction": random.choice(["N", "S", "E", "W"])}


def deliberate_red(knowledge: dict) -> dict:
    """
    Deliberation for RedAgent (all zones z1 + z2 + z3).
    Priority order:
      0. Send any pending one-shot message
      1. Carry red waste to disposal zone → put_down
      2. Pick up visible red waste
      3. Navigate toward remembered red waste
      4. Random walk
    """
    inventory    = knowledge["inventory"]
    pos          = knowledge["pos"]
    percepts     = knowledge["percepts"]
    disposal_pos = knowledge.get("disposal_pos")
    known_wastes = knowledge.get("known_wastes", {})
    pending_msg  = knowledge.get("pending_msg")

    red_count = inventory.count("red")

    # 0. Send pending message
    if pending_msg:
        return pending_msg

    # 1. Transport red to disposal zone
    if red_count >= 1 and disposal_pos:
        if pos == disposal_pos:
            return {"type": "put_down", "waste_type": "red"}
        dx, dy = disposal_pos[0] - pos[0], disposal_pos[1] - pos[1]
        return {"type": "move", "direction": _dir_from_delta(dx, dy)}

    # 2. Pick up visible red waste
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
            # --- Communication (Step 2) ---
            "mailbox":          [],          # incoming messages for this step
            "pending_msg":      None,        # one-shot send_message action queued by _update_knowledge
            "partner_id":       None,        # unique_id of handoff partner
            "partner_pos":      None,        # target position for handoff rendezvous
            "handoff_role":     None,        # "initiator" | "responder" | None
            "handoff_wait":     0,           # steps spent in current handoff role (timeout guard)
            "drop_avoid_pos":   None,        # position of waste we just dropped (suppress re-pickup)
        }

    # ------------------------------------------------------------------
    # Knowledge update helpers
    # ------------------------------------------------------------------

    def _check_handoff_resolution(self) -> None:
        """Auto-clear handoff state once the rendezvous has completed or timed out."""
        role = self.knowledge.get("handoff_role")
        if not role:
            self.knowledge["handoff_wait"] = 0
            return

        inv           = self.knowledge["inventory"]
        handoff_waste = "green" if self.color == "green" else "yellow"

        if role == "initiator":
            self.knowledge["handoff_wait"] = self.knowledge.get("handoff_wait", 0) + 1
            if inv.count(handoff_waste) >= 2:
                # Success: responder delivered the waste
                self.knowledge.update({"handoff_role": None, "partner_id": None, "handoff_wait": 0})
            elif self.knowledge["handoff_wait"] > 20:
                # Timeout: partner never arrived — resume normal behaviour
                self.knowledge.update({"handoff_role": None, "partner_id": None, "handoff_wait": 0})

        elif role == "responder":
            self.knowledge["handoff_wait"] = self.knowledge.get("handoff_wait", 0) + 1
            if handoff_waste not in inv:
                # Delivered the waste — mission complete
                self.knowledge.update({
                    "handoff_role": None, "partner_id": None,
                    "partner_pos":  None, "handoff_wait": 0,
                })
            elif self.knowledge["handoff_wait"] > 40:
                # Timeout: can't reach initiator — give up
                self.knowledge.update({
                    "handoff_role": None, "partner_id": None,
                    "partner_pos":  None, "handoff_wait": 0,
                })

    def _process_message(self, msg: dict) -> None:
        """
        Integrate a single incoming FIPA-ACL message into the knowledge base.

        Handled performatives:
          inform / waste_at      → update known_wastes map (Protocol B)
          inform / has_unpaired  → queue ACCEPT reply and set responder state (Protocol A)
          accept / handoff_accept → confirm as initiator (Protocol A)
        """
        performative = msg.get("performative")
        content      = msg.get("content", {})
        content_type = content.get("type")

        # --- Protocol B: map sharing ---
        if performative == "inform" and content_type == "waste_at":
            pos = tuple(content["pos"])
            self.knowledge["known_wastes"][pos] = content["waste"]
            return

        # --- Protocol A: handoff (green and yellow robots only) ---
        if self.color not in ("green", "yellow"):
            return

        handoff_waste = "green" if self.color == "green" else "yellow"
        inv           = self.knowledge["inventory"]

        if performative == "inform" and content_type == "has_unpaired":
            # Only respond if: matching waste type, carrying exactly 1, no active partner
            if (content["waste"] == handoff_waste
                    and self.knowledge["partner_id"] is None
                    and inv.count(handoff_waste) == 1
                    and self.knowledge["pending_msg"] is None):
                sender_pos = tuple(msg["sender_pos"])
                self.knowledge["partner_id"]   = msg["sender_id"]
                self.knowledge["partner_pos"]  = sender_pos
                self.knowledge["handoff_role"] = "responder"
                # Queue ACCEPT reply — sent as next action via deliberate priority 0
                self.knowledge["pending_msg"] = {
                    "type":       "send_message",
                    "recipients": [msg["sender_id"]],
                    "message": {
                        "performative": "accept",
                        "content":      {"type": "handoff_accept"},
                    },
                }

        elif performative == "accept" and content_type == "handoff_accept":
            # First ACCEPT wins; ignore duplicates
            if self.knowledge["partner_id"] is None:
                self.knowledge["partner_id"]   = msg["sender_id"]
                self.knowledge["handoff_role"] = "initiator"

    def _update_knowledge(self, percepts: dict) -> None:
        """Integrate new percepts and incoming messages into the knowledge base."""
        # Extract mailbox injected by model._get_percepts (special key)
        mailbox = percepts.pop("__mailbox__", [])

        # Clear one-shot pending message (consumed as an action last step)
        self.knowledge["pending_msg"] = None

        # Clear drop_avoid_pos once the robot has moved away from that cell
        drop_pos = self.knowledge.get("drop_avoid_pos")
        if drop_pos is not None and drop_pos != self.pos:
            self.knowledge["drop_avoid_pos"] = None

        # Standard percept integration
        self.knowledge["pos"]      = self.pos
        self.knowledge["percepts"] = percepts

        # Update waste memory map from observations
        for cell_pos, contents in percepts.items():
            if not contents.get("wastes"):
                self.knowledge["known_wastes"].pop(cell_pos, None)
            else:
                for w in contents["wastes"]:
                    self.knowledge["known_wastes"][cell_pos] = w["waste_type"]

        # Auto-clear resolved or timed-out handoff state
        self._check_handoff_resolution()

        # Process incoming messages
        for msg in mailbox:
            self._process_message(msg)

        self.knowledge["mailbox"] = mailbox

    def step(self) -> None:
        """
        Main agent loop:
          1. Update knowledge with percepts from previous step
          2. Deliberate (pure function — no external variable access)
          3. Execute action via model.do(), store returned percepts
        """
        self._update_knowledge(self._last_percepts)
        action = self.deliberate_fn(self.knowledge)

        # Track drop position to prevent the robot from immediately re-picking up
        # its own dropped waste (self-pickup loop in handoff protocol)
        if action.get("type") == "put_down":
            self.knowledge["drop_avoid_pos"] = self.pos
        else:
            self.knowledge["drop_avoid_pos"] = None

        self._last_percepts = self.model.do(self, action)


# ---------------------------------------------------------------------------
# Concrete robot classes
# ---------------------------------------------------------------------------

class GreenAgent(RobotAgent):
    """
    Green robot — operates only in z1.
    - Collects 2 green wastes → transforms into 1 yellow
    - Transports yellow waste to east edge of z1
    - Communicates to resolve unpaired waste deadlock (Protocol A)
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
    - Communicates to resolve unpaired waste deadlock (Protocol A)
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
    - Benefits from Protocol B map-sharing messages
    """

    def __init__(self, model: mesa.Model) -> None:
        super().__init__(model, color="red")
        self.allowed_zones  = {1, 2, 3}
        self.deliberate_fn  = deliberate_red
