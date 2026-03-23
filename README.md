# Robot Mission — Radioactive Waste Collection MAS
### Multi-Agent Systems Project 2026

> # Group: 18 | Date: 2026-03-23 | Members: Ikram Firdaous, Aya Boukhari , Ghiles Kemiche
> **Framework:** Mesa 3.5 · Python · SolaraViz

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [System Scope](#2-system-scope)
3. [Agent Architecture](#3-agent-architecture)
4. [Behavioral Strategies](#4-behavioral-strategies)
5. [Communication Design — Dual Message Boards](#5-communication-design--dual-message-boards)
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

**Mathematical constraint:** N initial green wastes → ⌊N/2⌋ yellow → ⌊N/4⌋ red → ⌊N/4⌋ disposed.
Full disposal requires N to be a **multiple of 4** (8, 12, 16 …).

---

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

    # Handoff state
    "partner_id":      int | None,
    "partner_pos":     (x,y) | None,
    "handoff_role":    "initiator"|"responder"|None,
    "handoff_wait":    int,
    "drop_avoid_pos":  (x,y) | None,
}
```

---

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

---

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

**Guards against failure:**
- `drop_avoid_pos` prevents responder from re-picking up dropped waste
- Initiator timeout: 20 steps → resume normal exploration
- Responder timeout: 40 steps → abandon handoff
- Position auto-update: stuck agent's position refreshed each step while request is active

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

### 5.7 Edge Cases Handled

| Case | Handling |
|---|---|
| Waste picked up before taker arrives | Agent observes empty cell → `known_wastes` cleared → resumes normal behavior |
| Both agents post stuck & one takes the other's | Sequential stepping prevents simultaneous takes; taker removes own request |
| Request expires (TTL) with no taker | Agent can repost next step if still stuck |
| Board full (saturation) | New posts rejected → agents continue exploring independently |
| Agent becomes un-stuck naturally (finds waste) | Request auto-removed via `remove_by_sender` in `_post_to_boards` |
| Handoff partner moved since posting | Position refreshed each step; responder navigates to latest position |

---

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

---

## 7. Results

*Run `python 18_robot_mission_MAS2026/run.py` to reproduce.*

### 7.1 Benchmark Summary

| Configuration | Avg. completion step | Disposed |
|---|:---:|:---:|
| N=12, 3+3+3 robots | ~80 | 3 |
| N=10, 3+3+3 robots | ~150 | 2 |
| N=16, 3+3+3 robots | ~200 | 4 |

Communication resolves structural deadlocks at very low overhead.
The board-based system is more efficient than broadcast: only the best-suited agent takes each request, avoiding redundant processing.

---

## 8. How to Run

### Prerequisites

```bash
pip install mesa solara matplotlib flask flask-cors
```

### Flask Web UI (recommended)

```bash
cd 18_robot_mission_MAS2026
python app.py
```

Opens at `http://127.0.0.1:5000` with:
- Animated grid with robot labels (g1, g2, y1, y2, r1, r2…)
- Live message board visualization (Internal + External)
- Activity log showing who took which request and at what cost
- Chart.js time series of waste counts

### Interactive Visualisation (SolaraViz)

```bash
solara run 18_robot_mission_MAS2026/server.py
```

### Headless Benchmark (terminal)

```bash
python 18_robot_mission_MAS2026/run.py --wastes 12 --seed 42
python 18_robot_mission_MAS2026/run.py --wastes 10 --steps 500 --seed 42
```

---

## 9. Project Structure

```
18_robot_mission_MAS2026/
├── messaging.py    — Dual message boards (MessageBoard, Request classes)
├── objects.py      — Passive agents (RadioactivityAgent, WasteAgent, WasteDisposalZone)
├── model.py        — RobotMission: grid, do(), boards, percepts
├── agents.py       — Robot deliberation + board interaction + RobotAgent base class
├── app.py          — Flask web server (API + serves index.html)
├── templates/
│   └── index.html  — Browser UI: canvas grid, Chart.js, board visualization
├── server.py       — SolaraViz interactive interface
├── server1.py      — Matplotlib + TkAgg animated desktop UI
└── run.py          — Headless runner + matplotlib charts
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
