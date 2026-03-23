# Group: 18 | Date: 2026-03-16 | Members: Aya Boukhari, Ikram Firdaous, Ghiles Kemiche
# run.py — Headless simulation runner with matplotlib chart output
#
# Usage:  python run.py
#         python run.py --steps 200 --width 15 --height 10

import argparse
import sys
import os

# Allow imports from this package directory
sys.path.insert(0, os.path.dirname(__file__))

import matplotlib.pyplot as plt
from model import RobotMission


def run_simulation(
    steps: int          = 300,
    width: int          = 15,
    height: int         = 10,
    n_green_robots: int = 3,
    n_yellow_robots: int = 3,
    n_red_robots: int   = 3,
    n_green_wastes: int = 10,
    seed: int | None    = None,
    verbose: bool       = True,
) -> RobotMission:
    """Run the simulation for a fixed number of steps and return the model."""

    print("=" * 60)
    print("  Robot Mission — Waste Collection MAS 2026")
    print("=" * 60)
    print(f"  Grid       : {width} x {height}")
    print(f"  Robots     : {n_green_robots} green | {n_yellow_robots} yellow | {n_red_robots} red")
    print(f"  Init waste : {n_green_wastes} green")
    print(f"  Steps      : {steps}")
    print("=" * 60)

    model = RobotMission(
        width=width,
        height=height,
        n_green_robots=n_green_robots,
        n_yellow_robots=n_yellow_robots,
        n_red_robots=n_red_robots,
        n_green_wastes=n_green_wastes,
        seed=seed,
    )

    for step in range(steps):
        if model.is_done():
            print(f"\n  All waste disposed at step {step}!")
            break
        model.step()
        if verbose and (step + 1) % 10 == 0:
            g = model._count_waste("green")
            y = model._count_waste("yellow")
            r = model._count_waste("red")
            d = model.disposed_count
            inv = model._count_inventory_waste()
            print(f"  Step {step+1:>4} | Green: {g:>3} | Yellow: {y:>3} | Red: {r:>3} | Inv: {inv:>3} | Disposed: {d:>3}")

    print(f"\n  Final disposed: {model.disposed_count}")
    return model


def plot_results(model: RobotMission) -> None:
    """Display a chart of waste counts over simulation time."""
    df = model.datacollector.get_model_vars_dataframe()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Robot Mission — Waste Counts Over Time", fontsize=13)

    # Left: waste by type
    ax1 = axes[0]
    ax1.plot(df.index, df["Green wastes"],  color="limegreen",     label="Green wastes",  linewidth=2)
    ax1.plot(df.index, df["Yellow wastes"], color="goldenrod",     label="Yellow wastes", linewidth=2)
    ax1.plot(df.index, df["Red wastes"],    color="crimson",       label="Red wastes",    linewidth=2)
    ax1.plot(df.index, df["Total wastes"],  color="steelblue",     label="Total wastes",  linewidth=2, linestyle="--")
    ax1.set_xlabel("Step")
    ax1.set_ylabel("Number of wastes on grid")
    ax1.set_title("Wastes by type over time")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Right: disposed wastes
    ax2 = axes[1]
    ax2.plot(df.index, df["Disposed"], color="mediumpurple", label="Total disposed", linewidth=2)
    ax2.set_xlabel("Step")
    ax2.set_ylabel("Cumulative disposed wastes")
    ax2.set_title("Cumulative waste disposal")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("simulation_results.png", dpi=120)
    print("\n  Chart saved to simulation_results.png")
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Robot Mission simulation")
    parser.add_argument("--steps",    type=int, default=300,  help="Number of simulation steps")
    parser.add_argument("--width",    type=int, default=15,   help="Grid width (multiple of 3)")
    parser.add_argument("--height",   type=int, default=10,   help="Grid height")
    parser.add_argument("--green",    type=int, default=3,    help="Number of green robots")
    parser.add_argument("--yellow",   type=int, default=3,    help="Number of yellow robots")
    parser.add_argument("--red",      type=int, default=3,    help="Number of red robots")
    parser.add_argument("--wastes",   type=int, default=12,   help="Initial green waste count (use multiples of 4 for full disposal)")
    parser.add_argument("--seed",     type=int, default=None, help="Random seed")
    parser.add_argument("--no-plot",  action="store_true",    help="Skip chart display")
    args = parser.parse_args()

    model = run_simulation(
        steps=args.steps,
        width=args.width,
        height=args.height,
        n_green_robots=args.green,
        n_yellow_robots=args.yellow,
        n_red_robots=args.red,
        n_green_wastes=args.wastes,
        seed=args.seed,
    )

    if not args.no_plot:
        plot_results(model)
