# group 18 : Aya Boukhari, Ikram Firdaous
# date of creation : 16-03-2026



import matplotlib
matplotlib.use("TkAgg")          # swap to "Qt5Agg" if TkAgg is unavailable
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
from matplotlib.widgets import Button, Slider
import numpy as np

from model import RobotMission
from objects import Waste, WasteDisposalZone
from agents import GreenAgent, YellowAgent, RedAgent

# ─── Theme ────────────────────────────────────────────────────────────────────
plt.style.use("dark_background")

ZONE_BG     = ["#0d2b0d", "#2b2b08", "#2b0d0d"]   # z1 / z2 / z3 dark tints
ROBOT_CLR   = {"green": "#00ff88", "yellow": "#ffd700", "red": "#ff4444"}
WASTE_CLR   = {"green": "#1db954", "yellow": "#f0c040", "red": "#e03030"}
ACCENT      = "#aaaaaa"
GRID_CLR    = "#333333"

# ─── Default parameters ───────────────────────────────────────────────────────
DEFAULTS = dict(
    width          = 21,
    height         = 10,
    n_green_robots = 1,
    n_yellow_robots= 1,
    n_red_robots   = 1,
    n_initial_waste= 20,
    seed           = 42,
)
MAX_STEPS    = 1000
INITIAL_FPS  = 10


# ─── Drawing helpers ──────────────────────────────────────────────────────────

def _draw_grid(ax, model):
    ax.clear()
    ax.set_facecolor("#111111")

    # Zone backgrounds (three axvspan strips)
    ax.axvspan(-0.5, model.z1_end + 0.5,
               facecolor=ZONE_BG[0], zorder=0)
    ax.axvspan(model.z1_end + 0.5, model.z2_end + 0.5,
               facecolor=ZONE_BG[1], zorder=0)
    ax.axvspan(model.z2_end + 0.5, model.width - 0.5,
               facecolor=ZONE_BG[2], zorder=0)

    # Zone labels
    for label, cx in [
        ("z1", model.z1_end / 2),
        ("z2", (model.z1_end + model.z2_end) / 2),
        ("z3", (model.z2_end + model.width - 1) / 2),
    ]:
        ax.text(cx, model.height - 0.1, label,
                ha="center", va="top", fontsize=8,
                color=ACCENT, alpha=0.6, zorder=1)

    ax.set_xlim(-0.5, model.width  - 0.5)
    ax.set_ylim(-0.5, model.height - 0.5)
    ax.set_aspect("equal")
    ax.set_xticks(range(model.width))
    ax.set_yticks(range(model.height))
    ax.tick_params(colors=GRID_CLR, labelsize=5)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.grid(True, color=GRID_CLR, linewidth=0.4, alpha=0.6)

    # Agents
    for cell_content, (x, y) in model.grid.coord_iter():
        for agent in cell_content:

            if isinstance(agent, WasteDisposalZone):
                # Glowing star
                ax.plot(x, y, marker="*", color="white",
                        markersize=18, zorder=3, alpha=0.25)
                ax.plot(x, y, marker="*", color="white",
                        markersize=12, zorder=4)

            elif isinstance(agent, Waste):
                c = WASTE_CLR[agent.waste_type]
                ax.plot(x, y, marker="s", color=c,
                        markersize=8, zorder=2,
                        markeredgecolor="#ffffff22", markeredgewidth=0.5)

            elif isinstance(agent, (GreenAgent, YellowAgent, RedAgent)):
                rtype = ("green"  if isinstance(agent, GreenAgent)  else
                         "yellow" if isinstance(agent, YellowAgent) else "red")
                c = ROBOT_CLR[rtype]
                # Glow layer
                ax.plot(x, y, marker="^", color=c,
                        markersize=16, zorder=3, alpha=0.20)
                # Main marker
                ax.plot(x, y, marker="^", color=c,
                        markersize=11, zorder=4,
                        markeredgecolor="white", markeredgewidth=0.5)
                # Inventory label
                inv = agent.knowledge["inventory"]
                if inv:
                    label = "".join(w.waste_type[0].upper() for w in inv)
                    ax.text(x, y + 0.45, label,
                            ha="center", va="bottom", fontsize=6,
                            color="white", fontweight="bold", zorder=5)

    g   = model._count_waste("green")
    y_w = model._count_waste("yellow")
    r   = model._count_waste("red")
    ax.set_title(
        f"Step {model.steps:>4}    "
        f"🟢 {g:>2}   🟡 {y_w:>2}   🔴 {r:>2}    ✓ disposed: {model.disposed_count}",
        color="white", fontsize=10, pad=6,
    )

    # Legend
    ax.legend(handles=[
        mpatches.Patch(color=ZONE_BG[0], label="z1 – low radioactivity"),
        mpatches.Patch(color=ZONE_BG[1], label="z2 – medium radioactivity"),
        mpatches.Patch(color=ZONE_BG[2], label="z3 – high radioactivity"),
        plt.Line2D([0],[0], marker="^", color="w",
                   markerfacecolor=ROBOT_CLR["green"],  markersize=8,
                   markeredgecolor="white", label="Green robot"),
        plt.Line2D([0],[0], marker="^", color="w",
                   markerfacecolor=ROBOT_CLR["yellow"], markersize=8,
                   markeredgecolor="white", label="Yellow robot"),
        plt.Line2D([0],[0], marker="^", color="w",
                   markerfacecolor=ROBOT_CLR["red"],    markersize=8,
                   markeredgecolor="white", label="Red robot"),
        plt.Line2D([0],[0], marker="s", color="w",
                   markerfacecolor=WASTE_CLR["green"],  markersize=7, label="Green waste"),
        plt.Line2D([0],[0], marker="s", color="w",
                   markerfacecolor=WASTE_CLR["yellow"], markersize=7, label="Yellow waste"),
        plt.Line2D([0],[0], marker="s", color="w",
                   markerfacecolor=WASTE_CLR["red"],    markersize=7, label="Red waste"),
        plt.Line2D([0],[0], marker="*", color="w",
                   markerfacecolor="white", markersize=10, label="Disposal zone"),
    ], loc="upper left", bbox_to_anchor=(1.01, 1.02),
       fontsize=7.5, framealpha=0.15, edgecolor="#444444",
       labelcolor="white")


def _draw_chart(ax, history):
    ax.clear()
    ax.set_facecolor("#111111")
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.tick_params(colors=ACCENT, labelsize=7)

    steps = range(len(history["green"]))
    ax.fill_between(steps, history["green"],
                    color=WASTE_CLR["green"],  alpha=0.25)
    ax.fill_between(steps, history["yellow"],
                    color=WASTE_CLR["yellow"], alpha=0.25)
    ax.fill_between(steps, history["red"],
                    color=WASTE_CLR["red"],    alpha=0.25)
    ax.plot(steps, history["green"],  color=WASTE_CLR["green"],  lw=1.5, label="Green")
    ax.plot(steps, history["yellow"], color=WASTE_CLR["yellow"], lw=1.5, label="Yellow")
    ax.plot(steps, history["red"],    color=WASTE_CLR["red"],    lw=1.5, label="Red")
    ax.plot(steps, history["disposed"],
            color="#bb88ff", lw=1.5, linestyle="--", label="Disposed ↑")

    ax.set_xlabel("Step", color=ACCENT, fontsize=8)
    ax.set_ylabel("Waste count", color=ACCENT, fontsize=8)
    ax.set_title("Waste over time", color="white", fontsize=9)
    ax.legend(fontsize=7, framealpha=0.15, edgecolor="#444444", labelcolor="white")
    ax.grid(True, color=GRID_CLR, alpha=0.5)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_visual():

    # ── Figure & axes layout ─────────────────────────────────────────────
    fig = plt.figure(figsize=(19, 9), facecolor="#0a0a0a")
    fig.suptitle("Robot Mission – Waste Cleanup Simulation",
                 color="white", fontsize=13, y=0.98)

    ax_grid  = fig.add_axes([0.01, 0.27, 0.58, 0.68])
    ax_chart = fig.add_axes([0.65, 0.27, 0.33, 0.68])

    # ── Parameter sliders ────────────────────────────────────────────────
    #   row y=0.17  (parameter sliders)
    #   row y=0.06  (speed + buttons)
    slider_specs = [
        # (label,          x,    y,     w,    vmin, vmax, vinit, valstep)
        ("🟢 Green robots",  0.04, 0.17, 0.12,  1,  5,  DEFAULTS["n_green_robots"],  1),
        ("🟡 Yellow robots", 0.19, 0.17, 0.12,  1,  5,  DEFAULTS["n_yellow_robots"], 1),
        ("🔴 Red robots",    0.34, 0.17, 0.12,  1,  5,  DEFAULTS["n_red_robots"],    1),
        ("🗑 Initial waste", 0.49, 0.17, 0.14,  5, 50,  DEFAULTS["n_initial_waste"], 1),
        ("🌱 Seed",          0.66, 0.17, 0.12,  0, 99,  DEFAULTS["seed"],            1),
    ]

    sliders = {}
    for label, lx, ly, lw, vmin, vmax, vinit, vstep in slider_specs:
        ax_s = fig.add_axes([lx, ly, lw, 0.028], facecolor="#1a1a1a")
        s = Slider(ax_s, label, vmin, vmax,
                   valinit=vinit, valstep=vstep,
                   color="#444466", track_color="#222233")
        s.label.set_color("white")
        s.label.set_fontsize(8)
        s.valtext.set_color("#aaaaff")
        sliders[label] = s

    # Speed slider
    ax_speed = fig.add_axes([0.04, 0.07, 0.30, 0.028], facecolor="#1a1a1a")
    sl_speed = Slider(ax_speed, "⚡ Speed (fps)", 1, 30,
                      valinit=INITIAL_FPS, valstep=1,
                      color="#446644", track_color="#223322")
    sl_speed.label.set_color("white")
    sl_speed.label.set_fontsize(8)
    sl_speed.valtext.set_color("#aaffaa")

    # Buttons
    ax_restart = fig.add_axes([0.38, 0.055, 0.10, 0.055])
    ax_pause   = fig.add_axes([0.50, 0.055, 0.10, 0.055])

    btn_restart = Button(ax_restart, "↺  Restart",
                         color="#1a3a1a", hovercolor="#2a5a2a")
    btn_pause   = Button(ax_pause,   "⏸  Pause",
                         color="#1a1a3a", hovercolor="#2a2a5a")
    for btn in (btn_restart, btn_pause):
        btn.label.set_color("white")
        btn.label.set_fontsize(9)

    # ── Simulation state ─────────────────────────────────────────────────
    state = {
        "model":   None,
        "history": None,
        "running": True,
        "ani":     None,
    }

    def _new_model():
        keys = ["🟢 Green robots", "🟡 Yellow robots", "🔴 Red robots",
                "🗑 Initial waste", "🌱 Seed"]
        field = ["n_green_robots", "n_yellow_robots", "n_red_robots",
                 "n_initial_waste", "seed"]
        params = {f: int(sliders[k].val) for k, f in zip(keys, field)}
        params["width"]  = DEFAULTS["width"]
        params["height"] = DEFAULTS["height"]
        return RobotMission(**params)

    def _new_history():
        return {"green": [], "yellow": [], "red": [], "disposed": []}

    def _record(model, history):
        history["green"].append(model._count_waste("green"))
        history["yellow"].append(model._count_waste("yellow"))
        history["red"].append(model._count_waste("red"))
        history["disposed"].append(model.disposed_count)

    # First model
    state["model"]   = _new_model()
    state["history"] = _new_history()
    _record(state["model"], state["history"])

    # ── Button callbacks ──────────────────────────────────────────────────
    def restart(event):
        state["model"]   = _new_model()
        state["history"] = _new_history()
        _record(state["model"], state["history"])
        state["running"] = True
        btn_pause.label.set_text("⏸  Pause")
        _draw_grid(ax_grid,  state["model"])
        _draw_chart(ax_chart, state["history"])
        fig.canvas.draw_idle()

    def toggle_pause(event):
        state["running"] = not state["running"]
        btn_pause.label.set_text(
            "⏸  Pause" if state["running"] else "▶  Play"
        )
        fig.canvas.draw_idle()

    def update_speed(val):
        fps = max(1, int(sl_speed.val))
        if state["ani"] and state["ani"].event_source:
            state["ani"].event_source.interval = int(1000 / fps)

    btn_restart.on_clicked(restart)
    btn_pause.on_clicked(toggle_pause)
    sl_speed.on_changed(update_speed)

    # ── Animation callback ────────────────────────────────────────────────
    def animate(_frame):
        model   = state["model"]
        history = state["history"]

        if not state["running"]:
            return
        if model.steps >= MAX_STEPS or model.is_finished():
            state["running"] = False
            btn_pause.label.set_text("✓  Done")
            fig.canvas.draw_idle()
            return

        model.step()
        _record(model, history)
        _draw_grid(ax_grid,   model)
        _draw_chart(ax_chart, history)

    # Initial draw
    _draw_grid(ax_grid,   state["model"])
    _draw_chart(ax_chart, state["history"])

    ani = animation.FuncAnimation(
        fig, animate,
        interval=int(1000 / INITIAL_FPS),
        cache_frame_data=False,
    )
    state["ani"] = ani

    plt.show()


if __name__ == "__main__":
    run_visual()
