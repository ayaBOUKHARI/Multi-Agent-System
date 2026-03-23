# Group: 18 | Date: 2026-03-23 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# messaging.py — Dual heap-based message boards for agent communication.
#
# Two boards:
#   InternalBoard : same-color agents (handoff when stuck with 1 unpaired waste)
#   ExternalBoard : cross-color agents (waste position after deposit / fusion)
#
# Each board stores requests sorted by posting step (oldest = highest priority).
# Agents evaluate available requests, compute a personal cost, and the
# lowest-cost agent takes the request.  Taken requests are removed for all.


class Request:
    """A single request posted to a message board."""

    __slots__ = (
        "request_id", "sender_id", "sender_label", "sender_color",
        "target_color", "request_type", "payload", "step_posted",
    )

    def __init__(self, request_id, sender_id, sender_label, sender_color,
                 target_color, request_type, payload, step_posted):
        self.request_id = request_id
        self.sender_id = sender_id
        self.sender_label = sender_label
        self.sender_color = sender_color
        self.target_color = target_color      # color of agents that should handle this
        self.request_type = request_type      # "stuck_unpaired" | "waste_available"
        self.payload = payload                # {"waste_type": str, "pos": [x, y]}
        self.step_posted = step_posted

    def to_dict(self, current_step=0):
        """Serialize for JSON / visualization."""
        return {
            "id": self.request_id,
            "sender": self.sender_label,
            "sender_color": self.sender_color,
            "type": self.request_type,
            "target": self.target_color,
            "pos": self.payload.get("pos"),
            "waste": self.payload.get("waste_type"),
            "step": self.step_posted,
            "age": current_step - self.step_posted,
        }


class MessageBoard:
    """
    Heap-based message board for agent communication.

    Requests are sorted by posting step (oldest first).  Agents take requests
    based on personal cost.  A confirmation is generated for the sender so
    it can react (e.g. become handoff initiator).

    Safeguards
    ----------
    - Duplicate prevention  : same sender + same type → reject
    - Position dedup        : no two waste_available at the same cell
    - Max capacity          : board rejects when full
    - TTL expiry            : stale requests auto-removed each step
    - Self-filter           : agent cannot take its own request
    """

    def __init__(self, name, max_size=30, ttl=80):
        self.name = name
        self.max_size = max_size
        self.ttl = ttl
        self._requests: dict[int, Request] = {}
        self._confirmations: dict[int, dict] = {}
        self._next_id = 0
        self.history: list[dict] = []

    @property
    def active_count(self):
        return len(self._requests)

    # ── Posting ───────────────────────────────────────────────────────

    def post(self, sender_id, sender_label, sender_color, target_color,
             request_type, payload, current_step):
        """
        Post a new request.

        Returns the request_id on success, None if rejected (duplicate,
        duplicate position, or board full).
        """
        for r in self._requests.values():
            if r.sender_id == sender_id and r.request_type == request_type:
                return None

        if request_type == "waste_available":
            pos_key = tuple(payload.get("pos", []))
            for r in self._requests.values():
                if (r.request_type == "waste_available"
                        and tuple(r.payload.get("pos", [])) == pos_key):
                    return None

        if len(self._requests) >= self.max_size:
            return None

        rid = self._next_id
        self._next_id += 1
        self._requests[rid] = Request(
            rid, sender_id, sender_label, sender_color,
            target_color, request_type, payload, current_step,
        )
        return rid

    # ── Taking ────────────────────────────────────────────────────────

    def take(self, request_id, taker_id, taker_label, cost, current_step, taker_step_n=None):
        """
        Take a request: remove it from the board and create a confirmation
        for the original sender.

        Returns the Request on success, None if already gone.
        """
        req = self._requests.pop(request_id, None)
        if req is None:
            return None

        self._confirmations[req.sender_id] = {
            "request_type": req.request_type,
            "taker_id": taker_id,
            "taker_label": taker_label,
            "cost": cost,
            "step": current_step,
            "payload": req.payload,
        }

        self.history.append({
            "id": request_id,
            "sender": req.sender_label,
            "type": req.request_type,
            "target": req.target_color,
            "pos": req.payload.get("pos"),
            "waste": req.payload.get("waste_type"),
            "taker": taker_label,
            "cost": cost,
            "taker_step_n": taker_step_n,
            "step_posted": req.step_posted,
            "step_taken": current_step,
        })
        return req

    def pop_confirmation(self, sender_id):
        """Consume and return the confirmation for *sender_id*, or None."""
        return self._confirmations.pop(sender_id, None)

    # ── Querying ──────────────────────────────────────────────────────

    def get_available(self, target_color, exclude_id):
        """Return requests matching *target_color*, excluding *exclude_id*."""
        return [
            r for r in self._requests.values()
            if r.target_color == target_color and r.sender_id != exclude_id
        ]

    def has_active_from(self, sender_id, request_type=None):
        """True if *sender_id* has an active request (optionally of a given type)."""
        for r in self._requests.values():
            if r.sender_id == sender_id:
                if request_type is None or r.request_type == request_type:
                    return True
        return False

    # ── Cleanup / removal ─────────────────────────────────────────────

    def remove_by_sender(self, sender_id):
        """Remove every request posted by *sender_id*."""
        to_del = [rid for rid, r in self._requests.items()
                  if r.sender_id == sender_id]
        for rid in to_del:
            del self._requests[rid]

    def remove_by_position(self, pos_tuple):
        """Remove waste_available requests at a specific cell (waste was picked up)."""
        to_del = [
            rid for rid, r in self._requests.items()
            if r.request_type == "waste_available"
            and tuple(r.payload.get("pos", [])) == pos_tuple
        ]
        for rid in to_del:
            del self._requests[rid]

    def update_sender_position(self, sender_id, request_type, new_pos):
        """Update the position payload of an active request from *sender_id*."""
        for r in self._requests.values():
            if r.sender_id == sender_id and r.request_type == request_type:
                r.payload["pos"] = list(new_pos)
                return

    def cleanup(self, current_step):
        """Remove expired requests (TTL exceeded)."""
        expired = [rid for rid, r in self._requests.items()
                   if current_step - r.step_posted > self.ttl]
        for rid in expired:
            del self._requests[rid]

    # ── Serialization ─────────────────────────────────────────────────

    def snapshot(self, current_step):
        """Return a JSON-serializable snapshot for the web UI."""
        active = sorted(self._requests.values(), key=lambda r: r.step_posted)
        return {
            "name": self.name,
            "count": len(active),
            "requests": [r.to_dict(current_step) for r in active],
            "history": self.history[-15:],
        }
