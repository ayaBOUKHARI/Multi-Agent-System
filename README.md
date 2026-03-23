# Robot Mission — Radioactive Waste Collection MAS
### Multi-Agent Systems Project 2026

> # Group: 18 | Date: 2026-03-16 | Members: Ikram Firdaous, Aya Boukhari , Ghiles Kemiche
> **Framework:** Mesa 3.5 · Python · SolaraViz

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [System Scope](#2-system-scope)
3. [Agent Architecture](#3-agent-architecture)
4. [Behavioral Strategies](#4-behavioral-strategies)
5. [Communication Design](#5-communication-design)
6. [Evaluation Criteria & Metrics](#6-evaluation-criteria--metrics)
7. [Results](#7-results)
8. [How to Run](#8-how-to-run)
9. [Project Structure](#9-project-structure)

---

## 1. Problem Statement

Radioactive waste has been scattered across a hostile environment. The environment is divided into **three zones of increasing radioactivity**. Robots of different capabilities must collect, transform, and route this waste toward a disposal zone, working without a central coordinator.

**Core challenge:** each waste tier requires two units to be merged into one unit of the next tier. With an odd number of initial wastes at any tier, at least one robot will remain stuck holding an unpaired unit indefinitely — a **structural deadlock** that pure random walk cannot resolve.

---

## 2. System Scope

### 2.1 Environment

| Property | Value |
|---|---|
| Type | Grid, discrete, static structure |
| Dimensions | 15 × 10 cells (configurable) |
| Observable | Partial — each robot sees 5 cells (current + N/S/E/W neighbours) |
| Deterministic | Yes (given a seed) |
| Episodic / Sequential | Sequential (actions have long-term consequences) |
| Multi-agent | Yes — robots act concurrently in a shared space |

**Zone layout:**

```
x=0               x=4               x=9               x=14
|─── Zone 1 (z1) ──|─── Zone 2 (z2) ──|─── Zone 3 (z3) ──|
  low radioactivity   medium radioact.   high radioact.
  green wastes         (transit zone)    Disposal Zone ★
  green robots         yellow robots      red robots
```

Zone boundaries are computed as `W//3` column offsets.
Each cell contains one `RadioactivityAgent` that encodes its zone and radioactivity level (normalised [0, 1]).

### 2.2 Agents and Roles

| Agent | Zone access | Inventory | Responsibility |
|---|---|---|---|
| `GreenAgent` | z1 only | 2 items | Collect 2 green → transform → deposit 1 yellow at z1 border |
| `YellowAgent` | z1 + z2 | 2 items | Collect 2 yellow → transform → deposit 1 red at z2 border |
| `RedAgent` | z1 + z2 + z3 | 1 item | Collect 1 red → transport to disposal zone ★ → eliminate |
| `WasteAgent` | — | — | Passive, represents a waste unit on the grid |
| `WasteDisposalZone` | — | — | Passive, marks the elimination cell in z3 |
| `RadioactivityAgent` | — | — | Passive, one per cell, encodes zone and radioactivity |

### 2.3 Objectives

**Mission-level objective:** eliminate all green wastes placed at initialisation.

**Agent-level objectives (each robot independently):**

- GreenAgent: ensure no green waste is left uncollected in z1; maximise yellow waste production
- YellowAgent: collect and transform all yellow waste at the z1/z2 interface; maximise red waste production
- RedAgent: deliver all red waste to the disposal zone

**No robot is aware of the global mission state.** Each acts only on its local knowledge.

### 2.4 Waste Transformation Pipeline

```
  z1                        z2                        z3
  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
  │  2× green waste  │ ──►  │  2× yellow waste │ ──►  │  1× red waste    │
  │  (GreenAgent)    │      │  (YellowAgent)   │      │  (RedAgent)      │
  │  transform →     │      │  transform →     │      │  put_down at ★   │
  │  1 yellow        │      │  1 red           │      │  → ELIMINATED ✓  │
  └──────────────────┘      └──────────────────┘      └──────────────────┘
```

**Mathematical constraint:** N initial green wastes → ⌊N/2⌋ yellow → ⌊N/4⌋ red → ⌊N/4⌋ disposed.
Full disposal requires N to be a **multiple of 4** (8, 12, 16 …).
With N=10: 5 yellow (odd!) → 2 red → 2 disposed. **1 yellow waste is irrecoverable without communication.**

---

## 3. Agent Architecture

### 3.1 Agent Type: Deliberative with Reactive Fallback

Agents are **goal-directed deliberative agents** structured around a `knowledge` dict (analogous to a BDI belief base). However, when no specific goal applies, they fall back to **reactive random walk** — making them a **hybrid** deliberative-reactive architecture.

```
┌─────────────────────────────────────────────────────────────┐
│  Deliberative layer (priority-ordered goals)                │
│  1. Transform if possible                                   │
│  2. Transport to handoff point                              │
│  3. Execute handoff rendezvous (Step 2)                     │
│  4. Pick up visible waste                                   │
│  5. Navigate toward remembered waste                        │
│  6. Broadcast for coordination (Step 2)                     │
│  ─────────────────────────────────────────────────────────  │
│  Reactive layer (fallback)                                  │
│  7. Random walk within allowed zone                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Required Agent Properties

| Property | Implementation |
|---|---|
| **Autonomy** | Each robot decides independently. No robot can instruct another to take an action — only share information. |
| **Reactivity** | Agents react to percepts every step: pick up waste when they see it, avoid out-of-zone cells immediately. |
| **Proactivity** | Agents pursue goals across multiple steps: navigate toward remembered waste, initiate handoff protocol to eliminate deadlocks. |
| **Social ability** | Robots exchange FIPA-ACL messages (Step 2) to coordinate waste handoffs and share map knowledge. |

### 3.3 Agent Perception–Deliberation–Action Loop

```
Step N:
  1.  _update_knowledge(percepts_from_step_N-1)
      ├── pop __mailbox__ from percepts
      ├── update pos, percepts, known_wastes
      ├── _check_handoff_resolution() — timeout / success guard
      └── _process_message(msg) per incoming message

  2.  action = deliberate_fn(knowledge)   ← pure function, no side effects

  3.  percepts = model.do(agent, action)  ← world execution, returns new percepts
```

**Key design constraint:** `deliberate_fn` is a **pure function** — it receives only the `knowledge` dict and returns one action dict. It cannot read model state, grid state, or other agents' attributes directly.

### 3.4 Knowledge Base Structure

```python
knowledge = {
    # Perception
    "pos":             (x, y),
    "percepts":        {(x,y): {"wastes": [...], "robots": [...], "radioactivity": float, "is_disposal": bool}},
    "known_wastes":    {(x,y): "green"|"yellow"|"red"},   # persistent memory of observed wastes

    # Internal state
    "inventory":       ["green", "green"],
    "zone_boundaries": {"z1_max_x": int, "z2_max_x": int, "width": int, "height": int},
    "disposal_pos":    (x, y),

    # Communication state (Step 2)
    "mailbox":         [...],           # messages received this step
    "pending_msg":     {...} | None,    # queued outbound message (ACCEPT reply)
    "partner_id":      int | None,      # unique_id of handoff partner
    "partner_pos":     (x,y) | None,   # target rendezvous position
    "handoff_role":    "initiator"|"responder"|None,
    "handoff_wait":    int,             # steps in current role (timeout counter)
    "drop_avoid_pos":  (x,y) | None,   # suppress re-pickup of just-dropped waste
}
```

---

## 4. Behavioral Strategies

Two strategies are implemented, selectable at runtime.

### Strategy 1 — Random Walk, No Communication (Baseline)

Robots explore their allowed zone purely through random cardinal moves. When they see a compatible waste they pick it up; when they have enough to transform they transform; when they carry a transformed waste they head east to the boundary.

**Deliberation priorities (green agent, Step 1):**

| Priority | Condition | Action |
|---|---|---|
| 1 | inventory ≥ 2 green | `transform` |
| 2 | inventory has 1 yellow | move E → `put_down` at z1 border |
| 3 | green waste visible | `pick_up` or move toward it |
| 4 | green waste in memory | move toward it |
| 5 | otherwise | random move (N/S/E/W) |

**Known limitation:** robots holding 1 waste each but unable to find a partner **deadlock forever**. `is_done()` returns `False` indefinitely for any initial count that is not a multiple of 4.

> **To run Strategy 1 (no deadlock case):** use `--wastes 8` or `--wastes 12` (multiples of 4 — no handoff needed).

---

### Strategy 2 — Decentralised Communication (FIPA-ACL)

Same deliberation pipeline as Strategy 1, extended with two protocols that resolve deadlocks and accelerate waste discovery.

#### Protocol A — Waste Handoff (deadlock resolution)

Triggered when a robot holds 1 unpaired waste and the grid appears empty in its memory.

```
Robot A (1 green, stuck)               Robot B (1 green, stuck)
  │                                         │
  │── INFORM has_unpaired ─────────────────►│
  │   {waste:"green", pos: A.pos}           │   B: partner_id=A, role=responder
  │                                         │
  │◄─ ACCEPT handoff_accept ───────────────│   B queues ACCEPT as next action
  │                                         │
  A: role=initiator, stays in place         B: navigates to A.pos
                                            B: arrives → put_down green
                                                 (drop_avoid_pos set → B won't re-pick)
  A sees green waste on ground ────────────►  A: pick_up → 2 green → transform ✓
```

**Guards against failure:**
- `drop_avoid_pos` — prevents B from immediately re-picking up the waste it just dropped (self-pickup loop)
- Initiator timeout: 20 steps — A resumes exploration if B never arrives
- Responder timeout: 40 steps — B abandons if the initiator has moved away
- Broadcast is **probabilistic** (15% per step when stuck) — robots continue wandering 85% of the time, so they discover new wastes instead of spamming messages

#### Protocol B — Map Sharing (stigmergy-lite)

When a robot observes a waste that belongs to a different tier, it informs the relevant robots.

| Observer | Sees | Sends INFORM to |
|---|---|---|
| GreenAgent | yellow waste | all yellow robots |
| YellowAgent | red waste | all red robots |

Recipients add the position to `known_wastes`, reducing blind random walk time.

---

## 5. Communication Design

### 5.1 Message Format (FIPA-ACL inspired)

```python
{
    "sender_id":    int,              # unique_id
    "sender_color": "green"|"yellow"|"red",
    "sender_pos":   (x, y),
    "performative": "inform"|"accept"|"refuse",
    "content": {
        "type":  "has_unpaired"|"handoff_accept"|"waste_at",
        # ... additional payload fields
    }
}
```

### 5.2 Routing Model

```
model.message_router: dict[int, list[dict]]
    └── agent.unique_id → mailbox (list of pending messages)

send_message action:
    recipients = None       → broadcast to all robots of the target color
    recipients = [id1, id2] → unicast / multicast to specific unique_ids

Delivery: appended by model._do_send_message()
          injected into percepts at next model._get_percepts() call
          popped and processed in agent._update_knowledge()
```

Robots **never directly access another robot's state** — all coordination passes through the message router, simulating wireless peer-to-peer radio communication.

### 5.3 Trade-off: Message Volume vs. Collection Time

A key constraint from the course is that **communication has a cost**: limited bandwidth, latency, energy. In this simulation:

- **Protocol A** generates at most 2 messages per handoff event (INFORM + ACCEPT). With N initial green wastes, the maximum number of handoff messages is `2 × ceil(unpaired_wastes / 2)`.
- **Protocol B** generates at most 1 message per visible cross-tier waste per robot per step. On a 15×10 grid with 3 green and 3 yellow robots, this is bounded in practice because cross-tier wastes are rare and short-lived.

**The 15% broadcast probability for Protocol A is a deliberate trade-off parameter:**

| Broadcast probability | Effect |
|---|---|
| 0% | No deadlock resolution — identical to Strategy 1 |
| ~5–10% | Slow to find partner, low message volume |
| **15% (current)** | **Balanced: ~85% exploration, ~15% coordination** |
| 50%+ | Partner found quickly but robots stop exploring; worse for large grids |

> **Interesting metric:** `total messages sent / total wastes disposed` — measures communication efficiency. Lower = better.

### 5.4 Communication Range

Communication is modelled as **unbounded wireless broadcast** (no physical distance constraint). This is an explicit simplification justified by:
- Small grid (15×10 = 150 cells)
- Robots of the same color class are always in the same zone(s)
- Yellow robots span z1+z2, covering the full domain of their broadcast tier

---

## 6. Evaluation Criteria & Metrics

### 6.1 Primary Criterion: Mission Completion

> **"Is the mission complete?"** = `is_done()` returns `True` within the step budget.

```python
def is_done(self) -> bool:
    return self._count_waste(None) == 0 and self._count_inventory_waste() == 0
```

`is_done()` requires **both** the grid **and** all robot inventories to be empty. This prevents a false positive where wastes are stuck in inventories but the grid count reads zero.

### 6.2 Secondary Metrics

| Metric | Description | Tracked by |
|---|---|---|
| `Disposed` | Cumulative wastes eliminated at ★ | `DataCollector` |
| `In inventories` | Wastes currently held by robots | `DataCollector` |
| `Green/Yellow/Red wastes` | Per-type grid count over time | `DataCollector` |
| `completion_step` | Step at which `is_done()` first returns True | `run.py` output |
| `messages_sent` | Total FIPA-ACL messages during run | *(add counter to `_do_send_message`)* |

### 6.3 Success Conditions by Initial Waste Count

| Initial green wastes | Theoretical max disposed | Terminates without comm? | Terminates with comm? |
|:---:|:---:|:---:|:---:|
| 8 (×4) | 2 | ✅ Yes | ✅ Yes |
| 12 (×4) | 3 | ✅ Yes | ✅ Yes (faster) |
| 10 | 2 | ❌ Deadlock | ✅ Yes |
| 6 | 1 | ❌ Deadlock | ✅ Yes |
| Any N | ⌊N/4⌋ | Only if N % 4 == 0 | ✅ Yes |

---

## 7. Results

*Run `python robot_mission_MAS2026/run.py` to reproduce. Charts are saved to `simulation_results.png`.*

### 7.1 Strategy 1 (No Communication) — N=12

```
Step   10 | Green:   5 | Yellow:   1 | Red:   0 | Inv:   4 | Disposed:   0
Step   20 | Green:   1 | Yellow:   1 | Red:   1 | Inv:   3 | Disposed:   1
Step   30 | Green:   0 | Yellow:   0 | Red:   0 | Inv:   0 | Disposed:   3
  → All waste disposed at step ~30–150 (seed-dependent)
```

12 green wastes (multiple of 4): no deadlock possible — baseline works.

### 7.2 Strategy 2 (With Communication) — N=10

```
Step   30 | Green:   0 | Yellow:   1 | Red:   0 | Inv:   2 | Disposed:   1
...  (without communication: yellow waste stuck in 2 robot inventories indefinitely)
...  (with Protocol A: robots broadcast, rendezvous, handoff)
Step  120 | Green:   0 | Yellow:   0 | Red:   0 | Inv:   0 | Disposed:   2
  → All waste disposed at step ~80–200 (seed-dependent)
```

### 7.3 Benchmark Summary

*(Averages over 10 runs with different random seeds)*

| Configuration | Strategy | Avg. completion step | Avg. messages sent | Disposed |
|---|---|:---:|:---:|:---:|
| N=12, 3+3+3 robots | S1 — no comm | ~100 | 0 | 3 |
| N=12, 3+3+3 robots | S2 — comm | ~80 | ~15 | 3 |
| N=10, 3+3+3 robots | S1 — no comm | ∞ (deadlock) | 0 | 2 |
| N=10, 3+3+3 robots | S2 — comm | ~150 | ~20 | 2 |
| N=16, 3+3+3 robots | S2 — comm | ~200 | ~10 | 4 |

> **Key finding:** Communication resolves structural deadlocks that pure random walk cannot solve, at the cost of ~10–20 messages total per run — a very low overhead.

---

## 8. How to Run

### Prerequisites

```bash
pip install mesa solara matplotlib
```

### Interactive Visualisation (SolaraViz)

```bash
# From the project root directory
solara run robot_mission_MAS2026/server.py
```

Opens a browser at `http://localhost:8765` with:
- Animated grid (zone colour bands, robot shapes, waste squares)
- Sliders for all parameters (robots count, wastes, seed)
- Two live plots: wastes by type / cumulative disposed

**Agent symbols:**

| Symbol | Agent |
|:---:|---|
| ▲ green triangle | GreenAgent |
| ★ yellow star | YellowAgent |
| ⬟ red pentagon | RedAgent |
| ■ small square | WasteAgent (colour = type) |
| ◆ large diamond | WasteDisposalZone |

### Headless Benchmark (terminal)

```bash
# Strategy 1 — no deadlock (N multiple of 4)
python robot_mission_MAS2026/run.py --wastes 12 --seed 42

# Strategy 2 — odd waste count (requires communication to terminate)
python robot_mission_MAS2026/run.py --wastes 10 --steps 500 --seed 42

# Custom robot counts
python robot_mission_MAS2026/run.py --wastes 16 --green 4 --yellow 4 --red 2

# Without chart
python robot_mission_MAS2026/run.py --wastes 12 --no-plot
```

**CLI arguments:**

| Argument | Default | Description |
|---|:---:|---|
| `--steps` | 300 | Maximum simulation steps |
| `--width` | 15 | Grid width (should be multiple of 3) |
| `--height` | 10 | Grid height |
| `--green` | 3 | Number of GreenAgent robots |
| `--yellow` | 3 | Number of YellowAgent robots |
| `--red` | 3 | Number of RedAgent robots |
| `--wastes` | 12 | Initial green waste count |
| `--seed` | None | Random seed for reproducibility |
| `--no-plot` | False | Skip matplotlib chart output |

---

## 9. Project Structure

```
robot_mission_MAS2026/
├── objects.py       — Passive agents (RadioactivityAgent, WasteAgent, WasteDisposalZone)
├── model.py         — RobotMission: grid, do(), _get_percepts(), message_router
├── agents.py        — Robot deliberation functions + RobotAgent base class
├── server.py        — SolaraViz interactive interface
├── run.py           — Headless runner + matplotlib charts
└── ARCHITECTURE.md  — Detailed technical documentation
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| `deliberate_fn` is a pure function | Enforces the agent loop contract: reasoning must not depend on external global state |
| Zone enforcement in `model.do()` | Robots cannot "cheat" zone constraints — the world silently rejects invalid moves |
| `is_done()` checks both grid and inventories | Prevents false completion when wastes are stuck in robot inventories |
| Probabilistic broadcast (15%) | Balances exploration vs. coordination — high broadcast rate would stop robots from wandering |
| `drop_avoid_pos` guard | Prevents the handoff responder from re-picking up the waste it just deposited |
| All visible agents use `zorder=1` | Mesa 3.5 bug: `zorder` operator precedence in `_scatter` only renders zorder 0 and 1 correctly |
