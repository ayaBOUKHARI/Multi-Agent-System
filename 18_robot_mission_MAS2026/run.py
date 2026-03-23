# group 18 : Aya Boukhari, Ikram Firdaous
# date of creation : 16-03-2026

"""
run.py – Launch the Robot Mission simulation and display a data chart.

Usage:
    python run.py

Runs the simulation for N_STEPS steps, then shows a matplotlib chart of
waste counts over time.
"""

import matplotlib.pyplot as plt
from model import RobotMission

# ── Simulation parameters ──────────────────────────────────────────────────
N_STEPS = 200
MODEL_PARAMS = dict(
    width=21,
    height=10,
    n_green_robots=3,
    n_yellow_robots=2,
    n_red_robots=2,
    n_initial_waste=20,
    seed=42,
)
# ──────────────────────────────────────────────────────────────────────────


def run_simulation(n_steps: int = N_STEPS, **model_params) -> RobotMission:
    """Create and run the model, returning it for inspection."""
    model = RobotMission(**model_params)
    for _ in range(n_steps):
        model.step()
        if model.is_finished():
            print(f"All waste disposed at step {model.steps}!")
            break
    return model


def plot_results(model: RobotMission) -> None:
    """Plot waste counts over simulation time."""
    df = model.datacollector.get_model_vars_dataframe()

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle("Robot Mission – Waste Cleanup Simulation", fontsize=14)

    # Top: waste counts by type (grid + carried)
    ax = axes[0]
    ax.plot(df.index, df["Green waste (grid)"] + df["Green waste (carried)"],
            color="green",  label="Green waste (total)")
    ax.plot(df.index, df["Yellow waste (grid)"] + df["Yellow waste (carried)"],
            color="gold",   label="Yellow waste (total)")
    ax.plot(df.index, df["Red waste (grid)"] + df["Red waste (carried)"],
            color="red",    label="Red waste (total)")
    ax.set_ylabel("Waste remaining")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Bottom: disposed waste (cumulative)
    ax2 = axes[1]
    ax2.plot(df.index, df["Disposed waste"], color="purple", label="Disposed (cumulative)")
    ax2.set_xlabel("Simulation step")
    ax2.set_ylabel("Disposed waste")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("waste_chart.png", dpi=150)
    print("Chart saved to waste_chart.png")
    plt.show()


if __name__ == "__main__":
    print("Starting Robot Mission simulation …")
    model = run_simulation(N_STEPS, **MODEL_PARAMS)
    print(f"Steps run: {model.steps}")
    print(f"Green waste remaining : {model._count_waste('green')}")
    print(f"Yellow waste remaining: {model._count_waste('yellow')}")
    print(f"Red waste remaining   : {model._count_waste('red')}")
    print(f"Total disposed        : {model.disposed_count}")
    plot_results(model)
