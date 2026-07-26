import json
import os
import random
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "assets", "process_state.json")
OUTPUT_PATH = os.path.join(BASE_DIR, "assets", "scada.png")

BG = "#0d0221"
PANEL_BG = "#150a30"
GREEN = "#39FF14"
PURPLE = "#BC13FE"
CYAN = "#00F0FF"
RED = "#FF3355"
GRID = "#2a1f4d"
TEXT = "#e6e6f0"

HISTORY_LEN = 30

DEFAULT_STATE = {
    "temperature": 60.0,
    "pressure": 4.0,
    "tank_level": 65.0,
    "pump_running": True,
    "valve_open": True,
    "temp_history": [60.0],
    "press_history": [4.0],
    "cycles": 0,
}


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_STATE)


def clamp(value, low, high):
    return max(low, min(high, value))


def step(state):
    state["temperature"] = clamp(state["temperature"] + random.uniform(-1.8, 1.8), 15.0, 95.0)
    state["pressure"] = clamp(state["pressure"] + random.uniform(-0.35, 0.35), 0.0, 10.0)
    state["tank_level"] = clamp(state["tank_level"] + random.uniform(-3.5, 3.5), 0.0, 100.0)

    if random.random() < 0.08:
        state["pump_running"] = not state["pump_running"]
    if random.random() < 0.05:
        state["valve_open"] = not state["valve_open"]

    state.setdefault("temp_history", []).append(state["temperature"])
    state.setdefault("press_history", []).append(state["pressure"])
    state["temp_history"] = state["temp_history"][-HISTORY_LEN:]
    state["press_history"] = state["press_history"][-HISTORY_LEN:]
    state["cycles"] = state.get("cycles", 0) + 1
    return state


def alarm_status(state):
    if state["temperature"] > 85:
        return True, f"UEBERTEMPERATUR: {state['temperature']:.1f} C"
    if state["tank_level"] < 8:
        return True, f"TANK LEERLAUF: {state['tank_level']:.1f}%"
    if state["tank_level"] > 96:
        return True, f"TANK UEBERLAUF: {state['tank_level']:.1f}%"
    if state["pressure"] > 9.2:
        return True, f"UEBERDRUCK: {state['pressure']:.2f} bar"
    return False, "SYSTEM OK"


def style_panel(ax):
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=7)
    ax.grid(color=GRID, linewidth=0.5, alpha=0.5)


def lamp(ax, x, on, label):
    color = GREEN if on else RED
    ax.add_patch(Circle((x + 0.02, 0.5), 0.05, color=color, alpha=0.9))
    ax.text(x + 0.10, 0.5, label, color=TEXT, fontsize=11, fontfamily="monospace", va="center")


def render(state):
    is_alarm, alarm_text = alarm_status(state)

    fig = plt.figure(figsize=(12, 5), dpi=150, facecolor=BG)
    gs = fig.add_gridspec(
        3, 3, height_ratios=[0.6, 2, 0.9], hspace=0.55, wspace=0.35,
        left=0.05, right=0.97, top=0.90, bottom=0.08,
    )

    ax_header = fig.add_subplot(gs[0, :])
    ax_header.axis("off")
    ax_header.set_xlim(0, 1)
    ax_header.set_ylim(0, 1)
    ax_header.text(0.0, 0.6, "SKYDINSE // PROZESSLEITSYSTEM", color=CYAN,
                    fontsize=18, fontweight="bold", fontfamily="monospace", va="center")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ax_header.text(1.0, 0.6, f"LAST UPDATE: {ts}", color=TEXT, fontsize=11,
                    fontfamily="monospace", va="center", ha="right")
    ax_header.text(0.0, 0.05, f"CYCLE #{state['cycles']}", color=PURPLE, fontsize=9,
                    fontfamily="monospace", va="center")
    ax_header.axhline(0.0, color=GRID, linewidth=1)

    ax_t = fig.add_subplot(gs[1, 0])
    style_panel(ax_t)
    ax_t.plot(state["temp_history"], color=GREEN, linewidth=2)
    ax_t.fill_between(range(len(state["temp_history"])), state["temp_history"], color=GREEN, alpha=0.1)
    ax_t.set_title("TEMPERATUR", color=TEXT, fontsize=10, fontfamily="monospace", loc="left")
    ax_t.text(0.98, 0.9, f"{state['temperature']:.1f} C", color=GREEN, fontsize=16,
              fontweight="bold", fontfamily="monospace", transform=ax_t.transAxes, ha="right", va="top")

    ax_p = fig.add_subplot(gs[1, 1])
    style_panel(ax_p)
    ax_p.plot(state["press_history"], color=CYAN, linewidth=2)
    ax_p.fill_between(range(len(state["press_history"])), state["press_history"], color=CYAN, alpha=0.1)
    ax_p.set_title("DRUCK", color=TEXT, fontsize=10, fontfamily="monospace", loc="left")
    ax_p.text(0.98, 0.9, f"{state['pressure']:.2f} bar", color=CYAN, fontsize=16,
              fontweight="bold", fontfamily="monospace", transform=ax_p.transAxes, ha="right", va="top")

    ax_k = fig.add_subplot(gs[1, 2])
    ax_k.set_facecolor(PANEL_BG)
    ax_k.set_xlim(0, 1)
    ax_k.set_ylim(0, 100)
    ax_k.axis("off")
    ax_k.set_title("TANK", color=TEXT, fontsize=10, fontfamily="monospace", loc="left", y=1.02)
    level = state["tank_level"]
    level_color = RED if (level < 8 or level > 96) else PURPLE
    ax_k.add_patch(Rectangle((0.25, 0), 0.5, 100, fill=False, edgecolor=TEXT, linewidth=1.5))
    ax_k.add_patch(Rectangle((0.25, 0), 0.5, level, fill=True, facecolor=level_color, alpha=0.85))
    ax_k.text(0.5, 105, f"{level:.0f}%", color=level_color, fontsize=14, fontweight="bold",
              fontfamily="monospace", ha="center")

    ax_s = fig.add_subplot(gs[2, :2])
    ax_s.axis("off")
    ax_s.set_xlim(0, 1)
    ax_s.set_ylim(0, 1)
    lamp(ax_s, 0.05, state["pump_running"], "PUMPE P1: " + ("LAEUFT" if state["pump_running"] else "GESTOPPT"))
    lamp(ax_s, 0.55, state["valve_open"], "VENTIL V1: " + ("OFFEN" if state["valve_open"] else "ZU"))

    ax_a = fig.add_subplot(gs[2, 2])
    ax_a.axis("off")
    ax_a.set_xlim(0, 1)
    ax_a.set_ylim(0, 1)
    banner_color = RED if is_alarm else GREEN
    ax_a.add_patch(Rectangle((0, 0.15), 1, 0.7, fill=True, facecolor=banner_color, alpha=0.15,
                              edgecolor=banner_color, linewidth=1.5))
    ax_a.text(0.5, 0.5, alarm_text, color=banner_color, fontsize=11, fontweight="bold",
              fontfamily="monospace", ha="center", va="center")

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
