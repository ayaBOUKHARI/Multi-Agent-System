# Robot Mission — Radioactive Waste Collection MAS
### Multi-Agent Systems Project 2026

> # Group: 18 | Date: 2026-03-23 | Members: Ikram Firdaous, Aya Boukhari, Ghiles Kemiche
> Framework: Mesa 3.5, Python, SolaraViz


## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [System Scope](#2-system-scope)
3. [Agent Architecture](#3-agent-architecture)
4. [Behavioral Strategies](#4-behavioral-strategies)
5. [Communication Design — Dual Message Boards](#5-communication-design--dual-message-boards)
   - [5.7 Centralization Risks](#57-centralization-risks-and-how-we-control-them)
6. [Evaluation Criteria & Metrics](#6-evaluation-criteria--metrics)
7. [Results](#7-results)
8. [How to Run](#8-how-to-run)
9. [Project Structure](#9-project-structure)


## 1. Problem Statement

Radioactive waste has been scattered across a hostile environment. The environment is divided into **three zones of increasing radioactivity**. Robots of different capabilities must collect, transform, and route this waste toward a disposal zone, working without a central coordinator.

Each waste tier requires two units to merge into one of the next tier. With an odd number of wastes at any tier, at least one robot ends up holding an unpaired unit it cannot transform — a deadlock that random walk alone cannot break.


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

| Agent | Label | Zone access | Inventory | Responsibility |
|---|---|---|---|---|
| `GreenAgent` | g1, g2… | z1 only | 2 items | Collect 2 green → transform → deposit 1 yellow at z1 border |
| `YellowAgent` | y1, y2… | z1 + z2 | 2 items | Collect 2 yellow → transform → deposit 1 red at z2 border |
| `RedAgent` | r1, r2… | z1 + z2 + z3 | 1 item | Collect 1 red → transport to disposal zone ★ → eliminate |

### 2.3 Waste Transformation Pipeline

```
  z1                        z2                        z3
  ┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
  │  2× green waste  │ ──►  │  2× yellow waste │ ──►  │  1× red waste    │
  │  (GreenAgent)    │      │  (YellowAgent)   │      │  (RedAgent)      │
  │  transform →     │      │  transform →     │      │  put_down at ★   │
  │  1 yellow        │      │  1 red           │      │  → ELIMINATED ✓  │
  └──────────────────┘      └──────────────────┘      └──────────────────┘
```

N initial green wastes yield ⌊N/2⌋ yellow, ⌊N/4⌋ red, and ⌊N/4⌋ disposed. Full disposal requires N to be a multiple of 4 (8, 12, 16…).


## 3. Agent Architecture

### 3.1 Agent Type: Deliberative with Reactive Fallback

Agents are **goal-directed deliberative agents** structured around a `knowledge` dict (analogous to a BDI belief base). When no specific goal applies, they fall back to **reactive random walk**.

### 3.2 Perception–Board–Deliberation–Action Loop

```
Step N:
  1.  _update_knowledge(percepts)
      ├── update pos, percepts, known_wastes
      └── _check_handoff_resolution() — timeout / success guard

  2.  _check_confirmations()
      └── if my stuck request was taken → become handoff initiator

  3.  _evaluate_boards()
      ├── scan Internal Board + External Board
      ├── compute personal cost for each request
      └── take lowest-cost request (if available)

  4.  action = deliberate_fn(knowledge)   ← pure function

  5.  percepts = model.do(agent, action)  ← world execution

  6.  _post_to_boards()
      ├── Internal: post stuck_unpaired if stuck (or update position)
      └── External: post waste_available for cross-tier waste in view
```

### 3.3 Knowledge Base Structure

```python
knowledge = {
    # Perception
    "pos":             (x, y),
    "percepts":        {(x,y): {"wastes": [...], "robots": [...], ...}},
    "known_wastes":    {(x,y): "green"|"yellow"|"red"},

    # Internal state
    "inventory":       ["green", "green"],
    "zone_boundaries": {"z1_max_x": int, "z2_max_x": int, ...},
    "disposal_pos":    (x, y),

    # Communication
    "communication_enabled": bool,

    # Handoff state
    "partner_id":      int | None,
    "partner_pos":     (x,y) | None,
    "handoff_role":    "initiator"|"responder"|None,
    "handoff_wait":    int,
    "drop_avoid_pos":  (x,y) | None,
}
```


## 4. Behavioral Strategies

### Deliberation Priorities (GreenAgent example)

| Priority | Condition | Action |
|:---:|---|---|
| 1 | inventory ≥ 2 green | `transform` |
| 2 | inventory has 1 yellow | move E → `put_down` at z1 border |
| 3 | handoff responder | navigate to partner → `put_down` green |
| 4 | green waste visible | `pick_up` or move toward it |
| 5 | green waste in memory | move toward it |
| 6 | handoff initiator | stay put (wait for responder) |
| 7 | otherwise | random walk within z1 |

Communication is **no longer an action** — it happens automatically through the message boards before and after deliberation. This means agents never lose a turn to communicate.


## 5. Communication Design — Dual Message Boards

### 5.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTERNAL BOARD                                │
│  (same-color: handoff when stuck)                               │
│                                                                 │
│  ┌─────────────────────────────────────────────┐                │
│  │ #5  g1  stuck green  (3,4)  age:5           │  ← heap       │
│  │ #8  y2  stuck yellow (7,3)  age:2           │    (oldest     │
│  └─────────────────────────────────────────────┘     first)     │
│                                                                 │
│  Cost = manhattan_distance(agent, stuck_agent_pos)              │
│  Eligible: same color, carrying 1 matching waste, not in handoff│
├─────────────────────────────────────────────────────────────────┤
│                    EXTERNAL BOARD                                │
│  (cross-color: waste positions after deposit / observation)     │
│                                                                 │
│  ┌─────────────────────────────────────────────┐                │
│  │ #12 g3 → yellow waste  (4,5)  age:1         │  ← heap       │
│  │ #14 y1 → red waste     (9,3)  age:0         │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
│  Cost = manhattan_distance(agent, waste_pos) + busy_penalty     │
│  Eligible: target color, has inventory room, not in handoff     │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Cost Function

Each agent computes a **personal cost** for every available request:

```
cost = manhattan_distance(agent.pos, target_pos) + penalties
```

| Condition | Penalty |
|---|---|
| Agent already in handoff | ∞ (unavailable) |
| Wrong inventory (stuck_unpaired: not carrying 1 matching waste) | ∞ |
| Full inventory (waste_available) | ∞ |
| Carrying items to deliver (waste_available) | +15 |
| Otherwise | 0 |

The agent picks the **single lowest-cost** request across both boards. If tied, internal (handoff) is preferred since it resolves deadlocks.

### 5.3 Request Types

| Type | Board | Trigger | Content |
|---|---|---|---|
| `stuck_unpaired` | Internal | Agent has 1 waste, no known targets, not in handoff | `{waste_type, pos}` |
| `waste_available` | External | Agent deposits transformed waste at boundary, or sees cross-tier waste | `{waste_type, pos}` |

### 5.4 Protocol A — Waste Handoff (Internal Board)

```
  g1 (1 green, stuck)                  g2 (1 green, stuck)
    │                                       │
    ├─ posts stuck_unpaired ──►  INTERNAL BOARD
    │                                       │
    │                              g2 evaluates board
    │                              cost = manhattan(g2, g1.pos)
    │                              g2 takes request
    │                                       │
    │◄── confirmation ─────────── g2 becomes responder
    │                              g2 navigates to g1.pos
    g1 becomes initiator
    g1 stays put                   g2 arrives → put_down green
                                   (drop_avoid_pos prevents self-pickup)
    g1 sees green on ground
    g1 picks up → 2 green → transform ✓
```

- `drop_avoid_pos` prevents the responder from immediately re-picking up the waste it just dropped
- Initiator timeout: 20 steps, then resumes normal exploration
- Responder timeout: 40 steps, then abandons the handoff
- Position auto-update: the stuck agent refreshes its position in the request each step

### 5.5 Protocol B — Deposit Notification (External Board)

```
  g1 transforms 2 green → 1 yellow
  g1 moves east to z1 border
  g1 deposits yellow at (4, 5)
    │
    ├── model posts waste_available ──► EXTERNAL BOARD
    │   target: "yellow", pos: (4, 5)
    │
    │                            y1 evaluates board (cost = 3)
    │                            y2 evaluates board (cost = 7)
    │                            y1 wins (lowest cost)
    │                            y1 takes request
    │
    │                            y1 adds (4,5) to known_wastes
    │                            y1 navigates to (4,5) → pick_up
```

Cross-tier waste seen during observation is also posted to the external board (redundancy for wastes deposited by other agents in earlier steps).

### 5.6 Safeguards

| Safeguard | Description |
|---|---|
| **Duplicate prevention** | Agent can't post if it already has an active request of the same type |
| **Position dedup** | No two `waste_available` requests at the same cell |
| **Max capacity** | Internal: 30, External: 50 — board rejects when full |
| **TTL expiry** | Internal: 80 steps, External: 100 steps — auto-removed |
| **Self-filter** | Agent cannot take its own request |
| **Cleanup on pickup** | `waste_available` removed when waste is physically picked up |
| **Cleanup on handoff** | `stuck_unpaired` removed when handoff resolves or times out |
| **Position refresh** | Stuck agent updates its position in the request each step |
| **Responder self-cleanup** | Responder removes its own stuck request when it takes another's |
| **Stale waste guard** | Agent navigates to taken waste_available position, finds nothing → known_wastes auto-cleared by observation |

### 5.7 Centralization Risks (and How We Control Them)

The dual message board is a **shared, writable data structure** — effectively a small "central tower" that every agent reads from and writes to. That design pays off in coordination quality but it inherits the usual centralized-coordination risks. Worth stating them honestly:

| Risk | What could go wrong | Concrete example | Mitigation in this project |
|---|---|---|---|
| **Write conflicts / coherence** | Two agents post or take "the same" thing simultaneously; the board drifts out of sync with ground truth. | Two green robots both post `stuck_unpaired` for the same cell before either sees the other; or one agent picks up a waste while another is still deciding to take the `waste_available` entry. | Sequential stepping (one agent at a time) serializes all writes. `take()` is atomic (`dict.pop`): only one agent can consume a request. On pickup, `remove_by_position` evicts stale `waste_available` entries. Duplicate-sender and duplicate-position checks reject redundant posts. |
| **Stale / lying state** | An entry keeps pointing to a position that has changed or no longer contains waste. | A `stuck_unpaired` post freezes the sender's position from 10 steps ago; a `waste_available` cell was already emptied. | Position is refreshed each step while the request is active (`update_sender_position`). TTLs (80 / 100 steps) drop stale entries. If an agent navigates to a position and observes an empty cell, `known_wastes` is cleared — behavior degrades gracefully to random walk. |
| **Saturation / message storm** | Unbounded board growth slows every evaluation and floods candidates. | Every robot posts every step, boards grow to thousands of entries, cost evaluation becomes O(N·M). | Hard capacity caps (internal 30, external 50) — `post()` returns `None` when full. Duplicate prevention keeps post rate O(agents), not O(agents × steps). Cost-based arbitration elects **one** taker per request, not a broadcast. |
| **Single point of failure** | If the board is corrupted or disabled, the whole fleet freezes. | Partial crash of the "tower". | The boards are **not load-bearing for correctness**. Disabling them (UI toggle "Heap communication" → off) falls back to the peer-to-peer direct-message protocol, which still converges (see §7.1) — we lose some efficiency and predictability the time of the "repair", but the mission keeps completing. Recovery is immediate when the board is re-enabled. |
| **Hidden coupling / starvation** | A "loud" agent monopolizes the board and crowds out others. | One robot keeps reposting the same stuck signal and always wins on locality. | Each sender is limited to one active request per `(type)` via `has_active_from`. Arbitration tie-breaks on `steps_taken`, favoring agents that have acted less. |
| **Inconsistency between boards and ground truth** | Internal state (inventory, handoff role) drifts relative to board content. | Agent handoff times out locally but its entry stays on the board. | `_clear_handoff` calls `remove_by_sender`; the responder removes its own stuck entry when it takes another's. TTLs provide a floor even if a bug leaves an orphan. |

The dual board is a deliberate design choice for coordination quality. The risks above are real in the general case but are contained here by sequential stepping, atomic take, per-sender/per-position dedup, TTLs, capacity caps, position refresh, and arbitration tie-breaks. There is also a fallback: disabling the boards falls back to the peer-to-peer direct-message protocol, which still converges. Coherence failures are not prevented by assumption — they are bounded by explicit safeguards, and the worst observed degradation is the efficiency gap documented in §7.1, not a stalled system.

### 5.8 Edge Cases Handled

| Case | Handling |
|---|---|
| Waste picked up before taker arrives | Agent observes empty cell → `known_wastes` cleared → resumes normal behavior |
| Both agents post stuck & one takes the other's | Sequential stepping prevents simultaneous takes; taker removes own request |
| Request expires (TTL) with no taker | Agent can repost next step if still stuck |
| Board full (saturation) | New posts rejected → agents continue exploring independently |
| Agent becomes un-stuck naturally (finds waste) | Request auto-removed via `remove_by_sender` in `_post_to_boards` |
| Handoff partner moved since posting | Position refreshed each step; responder navigates to latest position |


## 6. Evaluation Criteria & Metrics

### 6.1 Primary Criterion: Mission Completion

```python
def is_done(self) -> bool:
    return self._count_waste(None) == 0 and self._count_inventory_waste() == 0
```

### 6.2 Secondary Metrics

| Metric | Description |
|---|---|
| `Disposed` | Cumulative wastes eliminated at ★ |
| `In inventories` | Wastes currently held by robots |
| `Green/Yellow/Red wastes` | Per-type grid count over time |
| `Internal board activity` | Handoff requests posted, taken, costs |
| `External board activity` | Waste-sharing requests posted, taken, costs |


## 7. Results

### 7.1 Benchmark — Heap Board vs. Direct-Message Protocol

Both modes are toggled by the "Heap communication" button in the Flask UI. Both communicate and both converge; the comparison is about coordination efficiency. Setup: seeds (1, 2, 3, 7, 11), 3+3+3 robots, grid 15×10, 800-step cap, 5 seeds averaged.

| Initial green wastes | Mode | Avg. completion step | min / max | Disposed / max |
|:---:|:---:|:---:|:---:|:---:|
| **8**  | Heap board   | **74.2**  | 64 / 82   | 2 / 2 ✓ |
| 8      | Direct messages | 163.8  | 88 / 304  | 2 / 2 ✓ |
| **12** | Heap board   | **135.2** | 100 / 199 | 3 / 3 ✓ |
| 12     | Direct messages | 194.2  | 135 / 257 | 3 / 3 ✓ |
| **16** | Heap board   | **120.4** | 93 / 139  | 4 / 4 ✓ |
| 16     | Direct messages | 181.4  | 107 / 241 | 4 / 4 ✓ |
| **24** | Heap board   | **134.0** | 117 / 153 | 6 / 6 ✓ |
| 24     | Direct messages | 191.0  | 119 / 338 | 6 / 6 ✓ |
| **32** | Heap board   | **179.8** | 121 / 339 | 8 / 8 ✓ |
| 32     | Direct messages | 223.8  | 211 / 241 | 8 / 8 ✓ |

### 7.2 Interpretation

Both modes complete the mission across all tested configurations. The direct-message protocol resolves the same structural deadlocks peer-to-peer; the heap board adds a global arbitration layer on top of the same principle, not a correctness requirement.

The heap board is consistently faster in average across all waste counts tested (1.2× to 2.2×). At small loads (N=8), the gap is most pronounced: the board surfaces every pending request to all eligible agents simultaneously, so the nearest one wins, whereas direct messaging depends on the right responder being within broadcast range. This also explains why direct-message runs have larger tails (304 steps at N=8, 338 at N=24) — a stuck signal can simply be missed.

At N=32 the spread reverses: direct-message runs are tighter (211–241 steps) while the heap board has one outlier at 339. With many wastes in play, percept-driven pick-up dominates and deadlocks are rarer, so the arbitration advantage matters less — but the heap board still wins on average.

Disabling the board removes the arbitration layer but the fleet keeps coordinating through direct messages. The trade-off is efficiency and predictability, not capability.


## 8. How to Run

### Installation

```bash
pip install -r requirements.txt
```

### Flask web UI (recommended)

```bash
cd 18_robot_mission_MAS2026
python app.py
```

Opens at `http://127.0.0.1:5000`. The interface shows the animated grid with robot labels, live message board state (internal and external), an activity log of who took which request and at what cost, and a Chart.js time series of waste counts. The "Heap communication" toggle switches between the two coordination modes without restarting.

### SolaraViz interactive interface

```bash
solara run 18_robot_mission_MAS2026/server.py
```

### Headless runner (terminal output + matplotlib chart)

```bash
python 18_robot_mission_MAS2026/run.py --wastes 12 --seed 42
python 18_robot_mission_MAS2026/run.py --wastes 12 --steps 500 --no-plot
```


## 9. Project Structure

```
18_robot_mission_MAS2026/
├── core/                      — Heap-board model (current design)
│   ├── __init__.py
│   ├── objects.py             — Passive agents (RadioactivityAgent, WasteAgent, WasteDisposalZone)
│   ├── messaging.py           — Dual message boards (MessageBoard, Request)
│   ├── agents.py              — Robot deliberation + board interaction + RobotAgent base
│   └── model.py               — RobotMission: grid, do(), boards, percepts
├── direct/                    — Peer-to-peer direct-message protocol (toggle from the UI)
│   ├── __init__.py
│   ├── agents.py              — DirectRobotAgent + Direct{Green,Yellow,Red}Agent
│   └── model.py               — DirectRobotMission
├── templates/
│   └── index.html             — Browser UI: canvas grid, Chart.js, board visualization
├── app.py                     — Flask entry: API + serves index.html, toggles heap/direct
├── server.py                  — SolaraViz interactive interface
├── server1.py                 — Matplotlib + TkAgg animated desktop UI
├── run.py                     — Headless runner + matplotlib charts
└── ARCHITECTURE.md            — Extended design notes
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Two separate boards (internal/external) | Different priorities: deadlock resolution vs. information sharing |
| Cost-based request selection | Best-suited agent handles each request (nearest, most available) |
| Communication is free (no turn cost) | Posting/taking happens outside the deliberate-act cycle |
| `deliberate_fn` is a pure function | Reasoning must not depend on external global state |
| Board safeguards (TTL, dedup, capacity) | Prevents saturation, stale data, and message storms |
| Sequential agent stepping | Eliminates race conditions on shared boards |
| Robot labels (g1, y2, r3…) | Distinguishes same-type robots in visualization and logs |
