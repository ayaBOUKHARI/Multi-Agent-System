# Group: 18 | Date: 2026-03-16 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# server.py — Mesa 3.x SolaraViz visualization
#
# Launch with (from the project root):
#   solara run robot_mission_MAS2026/server.py

import sys
import os

# Ensure this package's directory is on sys.path regardless of launch location
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mesa
from mesa.visualization import SolaraViz, make_space_component, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle

from model import RobotMission
from objects import RadioactivityAgent, WasteAgent, WasteDisposalZone
from agents import GreenAgent, YellowAgent, RedAgent


# ---------------------------------------------------------------------------
# Agent portrayal
# ---------------------------------------------------------------------------

def agent_portrayal(agent):
    """
    Return matplotlib scatter kwargs for each agent type.
    Robots:
      - GreenAgent  → large green  ▲ triangle
      - YellowAgent → large gold   ★ star
      - RedAgent    → large red    ⬟ pentagon
    Objects:
      - WasteAgent(green)  → small green  ■ square
      - WasteAgent(yellow) → small orange ■ square
      - WasteAgent(red)    → small red    ■ square
      - WasteDisposalZone  → large purple ⬦ diamond
      - RadioactivityAgent → very faint zone background tint
    """
    # Mesa 3.5 bug in _scatter: operator precedence causes
    #   zorder_mask = z_order == zorder & mask_marker
    # to evaluate as z_order == (zorder & mask_marker).
    # Only zorder=0 and zorder=1 survive (n & 1 == n only for 0 and 1).
    # Fix: use zorder=1 for all visible agents; use AgentPortrayalStyle
    # (not dicts) to avoid the FutureWarning.

    if isinstance(agent, GreenAgent):
        return AgentPortrayalStyle(color="limegreen", size=300, marker="^", zorder=1)
    if isinstance(agent, YellowAgent):
        return AgentPortrayalStyle(color="gold",      size=300, marker="*", zorder=1)
    if isinstance(agent, RedAgent):
        return AgentPortrayalStyle(color="crimson",   size=300, marker="p", zorder=1)
    if isinstance(agent, WasteDisposalZone):
        return AgentPortrayalStyle(color="mediumpurple", size=400, marker="D", zorder=1)
    if isinstance(agent, WasteAgent):
        colors = {"green": "forestgreen", "yellow": "darkorange", "red": "firebrick"}
        return AgentPortrayalStyle(color=colors[agent.waste_type], size=80, marker="s", zorder=1)

    # RadioactivityAgent — invisible; zone bands drawn by post_process
    return AgentPortrayalStyle(color="white", size=1, marker=".", alpha=0.0, zorder=1)


# ---------------------------------------------------------------------------
# Post-process to add zone labels
# ---------------------------------------------------------------------------

def post_process_space(ax):
    """Draw zone colour bands and labels. Derives grid size from axis limits."""
    import matplotlib.patches as mpatches

    # Axis limits are set by draw_orthogonal_grid to (-0.5, width-0.5) / (-0.5, height-0.5)
    w = round(ax.get_xlim()[1] + 0.5)
    h = round(ax.get_ylim()[1] + 0.5)

    z1 = w // 3
    z2 = w // 3
    z3 = w - z1 - z2

    alpha = 0.12
    ax.add_patch(mpatches.Rectangle((-0.5, -0.5), z1,          h, color="limegreen", alpha=alpha, zorder=0))
    ax.add_patch(mpatches.Rectangle((z1 - 0.5, -0.5), z2,      h, color="gold",      alpha=alpha, zorder=0))
    ax.add_patch(mpatches.Rectangle((z1+z2 - 0.5, -0.5), z3,   h, color="tomato",    alpha=alpha, zorder=0))

    mid_y = h - 0.7
    ax.text(z1/2 - 0.5,          mid_y, "z1",  ha="center", fontsize=8, fontweight="bold", color="darkgreen")
    ax.text(z1 + z2/2 - 0.5,     mid_y, "z2",  ha="center", fontsize=8, fontweight="bold", color="goldenrod")
    ax.text(z1 + z2 + z3/2 - 0.5, mid_y, "z3", ha="center", fontsize=8, fontweight="bold", color="darkred")


# ---------------------------------------------------------------------------
# Model parameters (interactive sliders in SolaraViz)
# ---------------------------------------------------------------------------

model_params = {
    "width": {
        "type": "SliderInt",
        "label": "Grid width",
        "value": 15,
        "min": 9,
        "max": 30,
        "step": 3,
    },
    "height": {
        "type": "SliderInt",
        "label": "Grid height",
        "value": 10,
        "min": 5,
        "max": 20,
        "step": 1,
    },
    "n_green_robots": {
        "type": "SliderInt",
        "label": "Green robots",
        "value": 3,
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_yellow_robots": {
        "type": "SliderInt",
        "label": "Yellow robots",
        "value": 3,
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_red_robots": {
        "type": "SliderInt",
        "label": "Red robots",
        "value": 3,
        "min": 1,
        "max": 10,
        "step": 1,
    },
    "n_green_wastes": {
        "type": "SliderInt",
        "label": "Initial green wastes",
        "value": 12,
        "min": 4,
        "max": 32,
        "step": 4,
    },
}

# ---------------------------------------------------------------------------
# Build visualization components
# ---------------------------------------------------------------------------

SpaceComponent = make_space_component(agent_portrayal, post_process=post_process_space)

WasteChart = make_plot_component(
    {
        "Green wastes":  "green",
        "Yellow wastes": "gold",
        "Red wastes":    "red",
    }
)

DisposedChart = make_plot_component({"Disposed": "mediumpurple"})

# ---------------------------------------------------------------------------
# SolaraViz page (entry point for `solara run robot_mission_MAS2026/server.py`)
#
# Mesa 3.5 requires a model INSTANCE (not the class) as the first argument.
# Passing the class causes model=None on first render → AttributeError.
# model_params still drives the interactive sliders; Mesa re-instantiates
# the model whenever a slider changes.
# ---------------------------------------------------------------------------

_initial_model = RobotMission(
    width=15,
    height=10,
    n_green_robots=3,
    n_yellow_robots=3,
    n_red_robots=3,
    n_green_wastes=12,
)

page = SolaraViz(
    _initial_model,
    components=[SpaceComponent, WasteChart, DisposedChart],
    model_params=model_params,
    name="Robot Mission — Waste Collection MAS 2026",
)
page  # noqa: B018 — required by Solara as the module-level page object
