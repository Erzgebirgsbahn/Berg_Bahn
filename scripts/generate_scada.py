import json
import os
import random
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "assets", "process_state.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "assets", "scada.png")

BG = "#0d0221"
PANEL_BG = "#150a30"
GRID = "#2a1f4d"
GRID_DIM = "#4a3f6d"
TEXT = "#e6e6f0"
LIQUID = "#00A8FF"
GREEN = "#39FF14"
RED = "#FF3355"
ORANGE = "#FF9900"
CYAN = "#00F0FF"

# Level switch thresholds shared by every vessel (percent of fill height)
LEVELS = [("H2", 95), ("H1", 80), ("M", 50), ("L1", 20), ("L2", 5)]
LEVELS_B2 = [("H2 (MAX)", 95), ("H1", 80), ("M", 50), ("L1", 20), ("L2", 5)]

PLANT_NAME = "XENICS 021"

DEFAULT_STATE = {
    "phase": "FILL_B2",
    "tank1_level": 82.0,
    "tank2_level": 15.0,
    "filter_level": 30.0,
    "stirrer_rpm": 0.0,
    "pump_rpm": 0.0,
    "wo1_percent": 0.0,
    "v1_open": True,
    "v2_open": True,
    "mix_ticks": 0,
    "cycles": 0,
}


def load_state():
    state = dict(DEFAULT_STATE)
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state.update(json.load(f))
    return state


def clamp(value, low, high):
    return max(low, min(high, value))


def step(state):
    phase = state.get("phase", "FILL_B2")
    t1 = state["tank1_level"]
    t2 = state["tank2_level"]
    tf = state["filter_level"]

    if phase == "FILL_B2":
        state["v1_open"] = True
        state["wo1_percent"] = 0.0
        state["pump_rpm"] = 0.0
        state["stirrer_rpm"] = 0.0
        transfer = min(random.uniform(6, 10), t1)
        t1 -= transfer
        t2 += transfer
        if t1 < 25:
            t1 += random.uniform(15, 25)
        if t2 >= 78:
            state["phase"] = "MIX"
            state["mix_ticks"] = 0
            state["v1_open"] = False

    elif phase == "MIX":
        state["v1_open"] = False
        state["wo1_percent"] = 0.0
        state["pump_rpm"] = 0.0
        state["stirrer_rpm"] = clamp(2.13 + random.uniform(-0.05, 0.05), 1.9, 2.4)
        if random.random() < 0.3:
            t2 = clamp(t2 + random.uniform(1, 4), 0, 100)
        state["mix_ticks"] = state.get("mix_ticks", 0) + 1
        if state["mix_ticks"] >= 3:
            state["phase"] = "TRANSFER_TO_FILTER"

    else:  # TRANSFER_TO_FILTER
        state["v1_open"] = False
        state["stirrer_rpm"] = 0.0
        state["wo1_percent"] = clamp(70 + random.uniform(-5, 5), 0, 100)
        state["pump_rpm"] = clamp(1450 + random.uniform(-20, 20), 0, 3000)
        transfer = min(random.uniform(8, 12), t2)
        t2 -= transfer
        tf = clamp(tf + transfer * 0.9, 0, 100)
        if t2 <= 12:
            state["phase"] = "FILL_B2"
            state["wo1_percent"] = 0.0
            state["pump_rpm"] = 0.0

    state["v2_open"] = tf > 3
    if state["v2_open"]:
        outflow = min(random.uniform(3, 6), tf)
        tf -= outflow

    state["tank1_level"] = clamp(t1, 0, 100)
    state["tank2_level"] = clamp(t2, 0, 100)
    state["filter_level"] = clamp(tf, 0, 100)
    state["cycles"] = state.get("cycles", 0) + 1
    return state


def draw_tank(ax, x0, y0, w, h, level_pct, levels, level_color, label):
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, edgecolor=TEXT, linewidth=1.8))
    fill_h = h * (level_pct / 100.0)
    ax.add_patch(Rectangle((x0, y0), w, fill_h, fill=True, facecolor=LIQUID, alpha=0.45))
    for name, thresh in levels:
        ty = y0 + h * (thresh / 100.0)
        lit = level_pct >= thresh
        color = level_color if lit else GRID_DIM
        ax.plot([x0 + w, x0 + w + 0.15], [ty, ty], color=color, linewidth=2)
        ax.text(x0 + w + 0.22, ty, name, color=color, fontsize=8, fontfamily="monospace", va="center")
    ax.text(x0, y0 + h + 0.3, label, color=TEXT, fontsize=11, fontweight="bold", fontfamily="monospace")
    ax.text(x0 + w / 2, y0 - 0.35, f"{level_pct:.0f}%", color=level_color, fontsize=10,
            fontweight="bold", fontfamily="monospace", ha="center")


def draw_valve(ax, x, y, open_state, label):
    size = 0.32
    color = GREEN if open_state else "#555566"
    ax.add_patch(Polygon([(x - size, y - size), (x - size, y + size), (x, y)], closed=True,
                          facecolor=color, edgecolor=TEXT, linewidth=1))
    ax.add_patch(Polygon([(x + size, y - size), (x + size, y + size), (x, y)], closed=True,
                          facecolor=color, edgecolor=TEXT, linewidth=1))
    state_text = "OPEN" if open_state else "CLOSED"
    ax.text(x, y - size - 0.22, f"{label} ({state_text})", color=TEXT, fontsize=8,
            fontfamily="monospace", ha="center", va="top")


def draw_pump(ax, x, y, rpm, running):
    r = 0.45
    color = GREEN if running else GRID_DIM
    ax.add_patch(Circle((x, y), r, fill=False, edgecolor=color, linewidth=2))
    ax.add_patch(Polygon([(x - r * 0.4, y - r * 0.4), (x - r * 0.4, y + r * 0.4), (x + r * 0.5, y)],
                          closed=True, facecolor=color, alpha=0.7))
    ax.text(x, y - r - 0.55, "PUMP P1", color=TEXT, fontsize=8, fontfamily="monospace", ha="center")
    readout_box(ax, x - 0.6, y - r - 0.45, 1.2, 0.4, f"{rpm:.0f} RPM", color)


def draw_stirrer(ax, x, y, rpm, active):
    color = GREEN if active else GRID_DIM
    ax.add_patch(Circle((x, y), 0.16, fill=False, edgecolor=color, linewidth=2))
    ax.text(x, y, "M", color=color, fontsize=7, fontfamily="monospace", fontweight="bold",
            ha="center", va="center")
    ax.plot([x, x], [y - 0.16, y - 0.55], color=color, linewidth=1.5)
    readout_box(ax, x + 0.35, y - 0.2, 1.4, 0.4, f"{rpm:.2f} RPM", color)


def draw_pipe(ax, points, color=TEXT):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, color=color, linewidth=2)


def readout_box(ax, x, y, w, h, text, color=TEXT):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=PANEL_BG, edgecolor=GRID, linewidth=1))
    ax.text(x + w / 2, y + h / 2, text, color=color, fontsize=8, fontfamily="monospace",
            ha="center", va="center", fontweight="bold")


PHASE_LABELS = {
    "FILL_B2": "TRANSFER: TANK 1 -> TANK 2",
    "MIX": "MIXING (SOLIDS FEED + AGITATION)",
    "TRANSFER_TO_FILTER": "TRANSFER: TANK 2 -> FILTER 1",
}


def render(state):
    fig = plt.figure(figsize=(14, 9), dpi=150, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(0, 19.5)
    ax.set_ylim(0, 15)
    ax.axis("off")

    # Header
    ax.text(0.3, 14.5, f"{PLANT_NAME} // PROCESS CONTROL SYSTEM", color=CYAN, fontsize=20,
            fontweight="bold", fontfamily="monospace", va="center")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ax.text(19.2, 14.5, f"LAST UPDATE: {ts}", color=TEXT, fontsize=10,
            fontfamily="monospace", va="center", ha="right")
    phase_text = PHASE_LABELS.get(state["phase"], state["phase"])
    ax.text(0.3, 14.0, f"CYCLE #{state['cycles']}   |   PHASE: {phase_text}", color=ORANGE,
            fontsize=10, fontfamily="monospace", va="center")
    ax.plot([0.3, 19.2], [13.6, 13.6], color=GRID, linewidth=1)

    # Tank 1 (feed tank)
    draw_tank(ax, 1, 9.5, 3, 3, state["tank1_level"], LEVELS, RED, "TANK 1 (B1) - FEED TANK")
    ax.annotate("", xy=(2.5, 12.5), xytext=(2.5, 13.2),
                arrowprops=dict(arrowstyle="->", color=TEXT, linewidth=1.5))
    ax.text(2.5, 13.3, "FEED (PRODUCT 0)", color=GREEN, fontsize=8, fontfamily="monospace", ha="center")

    # Pipe B1 -> V1 -> Tank 2
    draw_pipe(ax, [(2.5, 9.5), (2.5, 8.6), (6.3, 8.6)])
    draw_valve(ax, 6.3, 8.6, state["v1_open"], "V1")
    draw_pipe(ax, [(6.3, 8.6), (7.3, 8.6), (7.3, 7.6)])

    # Tank 2 (reactor)
    draw_tank(ax, 5.8, 4.6, 3, 3, state["tank2_level"], LEVELS_B2, GREEN, "TANK 2 (B2) - REACTOR")
    draw_stirrer(ax, 8.3, 7.9, state["stirrer_rpm"], state["phase"] == "MIX")
    ax.annotate("", xy=(5.8, 6.0), xytext=(4.9, 6.0),
                arrowprops=dict(arrowstyle="->", color=ORANGE, linewidth=1.5))
    ax.text(3.1, 6.0, "SOLIDS FEED", color=ORANGE, fontsize=8, fontfamily="monospace", va="center")

    # Pipe Tank2 -> WO1 -> Pump
    draw_pipe(ax, [(7.3, 4.6), (7.3, 3.3)])
    draw_valve(ax, 7.3, 3.3, state["wo1_percent"] > 5, "WO1")
    readout_box(ax, 6.7, 2.3, 1.2, 0.45, f"{state['wo1_percent']:.0f}%", ORANGE)
    ax.text(7.3, 2.0, "CONTROL VALVE", color=TEXT, fontsize=8, fontfamily="monospace", ha="center")
    draw_pipe(ax, [(7.3, 3.3), (11.0, 3.3)])
    draw_pump(ax, 11.0, 3.3, state["pump_rpm"], state["pump_rpm"] > 5)

    # Pipe Pump -> Filter 1
    draw_pipe(ax, [(11.45, 3.3), (14.0, 3.3), (14.0, 9.5)])

    # Filter 1
    draw_tank(ax, 14.5, 9.5, 3, 3, state["filter_level"], LEVELS, ORANGE, "FILTER 1 (F1)")
    ax.plot([14.8, 17.2], [9.9, 12.1], color=TEXT, alpha=0.35, linewidth=1, linestyle="--")

    # Pipe Filter -> V2 -> Product 1
    draw_pipe(ax, [(16.0, 9.5), (16.0, 8.4)])
    draw_valve(ax, 16.0, 8.4, state["v2_open"], "V2")
    draw_pipe(ax, [(16.0, 8.05), (16.0, 6.9)])
    ax.annotate("", xy=(16.0, 6.6), xytext=(16.0, 6.9),
                arrowprops=dict(arrowstyle="->", color=TEXT, linewidth=1.5))
    ax.text(16.0, 6.35, "PRODUCT 1", color=CYAN, fontsize=11, fontweight="bold",
            fontfamily="monospace", ha="center")

    fig.savefig(OUTPUT_PATH, facecolor=BG)
    plt.close(fig)


def main():
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    state = load_state()
    state = step(state)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    render(state)


if __name__ == "__main__":
    main()
