import csv
import json
import math
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

RESULTS = "work/audit/results"
OUT = "work/figures"
METHOD = "dictation"

INK, MUTED, GRID = "#1a1a1a", "#6b6b6b", "#d9d9d9"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": INK, "axes.linewidth": 0.6, "pdf.fonttype": 42,
})
LABELS = {
    "initial_configuration": "Initial handshape", "final_configuration": "Final handshape",
    "movement_manner": "Movement manner", "movement_path": "Movement path", "movement_contact": "Contact",
    "movement_repetition": "Repetition", "non_manual_components": "Non-manuals",
    "initial_position": "Initial location", "initial_orientation": "Initial orientation",
    "final_position": "Final location", "final_orientation": "Final orientation",
}


def read(name):
    with open(os.path.join(RESULTS, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def wilson(p, n, z=1.96):
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def fig1_pipeline():
    steps = [
        ("Scanned PDF\n155 batches", "image + embedded\ntext layer"),
        ("Multimodal LLM\n+ rule prompt", "one batch per run"),
        ("JSON\nper batch", "inferred fields\nlogged with paths"),
        ("Schema +\ndataset checks", "closed catalogs,\nlocation rules"),
        ("Audit tool\n(human)", "entry next to\nextracted values"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 1.8))
    ax.set_xlim(-0.1, 10.1)
    ax.set_ylim(0, 2.3)
    ax.axis("off")
    w, gap = 1.75, (10 - 5 * 1.75) / 4
    for i, (title, sub) in enumerate(steps):
        x = i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.75), w, 0.95, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="white", ec=INK, lw=0.8))
        ax.text(x + w / 2, 1.22, title, ha="center", va="center", fontsize=6.8, color=INK, weight="bold")
        ax.text(x + w / 2, 0.38, sub, ha="center", va="center", fontsize=6.5, color=MUTED)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + w + 0.04, 1.22), (x + w + gap - 0.04, 1.22),
                                         arrowstyle="-|>", mutation_scale=8, color=INK, lw=0.8))
    x_last = 4 * (w + gap) + w / 2
    x_prompt = 1 * (w + gap) + w / 2
    ax.add_patch(FancyArrowPatch((x_last, 1.72), (x_prompt, 1.72), connectionstyle="arc3,rad=0.12",
                                 arrowstyle="-|>", mutation_scale=8, color=MUTED, lw=0.7, linestyle="--"))
    ax.text((x_last + x_prompt) / 2, 2.12, "review findings revise prompt and catalogs during the run",
            ha="center", va="bottom", fontsize=6.5, color=MUTED)
    save(fig, "fig1_pipeline")


def fig2_constructed_sign():
    path = os.path.join(OUT, "fig2_constructed_sign.json")
    with open(path, encoding="utf-8") as f:
        sign = json.load(f)
    inferred = {p.rsplit(".", 1)[-1] for p in sign["ocr_data"]["visually_deduced_fields"]}
    compact = {k: v for k, v in sign.items() if k != "meanings"}
    compact["ocr_data"] = dict(sign["ocr_data"])
    compact["ocr_data"]["visually_deduced_fields"] = ["…dominant_hand." + f for f in
                                                      ("initial_position", "initial_orientation",
                                                       "final_position", "final_orientation")]
    lines = json.dumps(compact, ensure_ascii=False, indent=2).split("\n")
    text = json.dumps(compact, ensure_ascii=False, indent=2)
    text = re.sub(r'\{\n\s+"(body|space|hand)": \[\n\s+("[^"]+")\n\s+\]\n\s+\}', r'{"\1": [\2]}', text)
    text = re.sub(r'\[\n\s+("[^"\n]+"),\n\s+("[^"\n]+")\n\s+\]', r'[\1, \2]', text)
    text = re.sub(r'\[\n\s+("[^"\n]+")\n\s+\]', r'[\1]', text)
    lines = text.split("\n")
    fig, ax = plt.subplots(figsize=(5.6, 0.155 * len(lines) + 0.3))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(lines))
    for i, line in enumerate(lines):
        y = len(lines) - i - 0.5
        key = re.match(r'\s*"([a-z_]+)"', line)
        if key and key.group(1) in inferred and "…" not in line:
            ax.add_patch(plt.Rectangle((0, y - 0.48), 1, 0.96, fc="#cfcfcf", ec="none"))
            ax.add_patch(plt.Rectangle((0, y - 0.48), 0.006, 0.96, fc=INK, ec="none"))
        ax.text(0.01, y, line, family="DejaVu Sans Mono", fontsize=6.2, va="center", color=INK)
    save(fig, "fig2_constructed_sign")


def fig4_accuracy():
    rows = [r for r in read("by_field.csv") if r["method"] == METHOD]
    order = ["initial_configuration", "final_configuration", "movement_manner", "movement_contact",
             "movement_repetition", "movement_path", "non_manual_components",
             "final_position", "final_orientation", "initial_orientation", "initial_position"]
    rows.sort(key=lambda r: order.index(r["field"]))
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    ys = list(range(len(rows)))[::-1]
    for y, r in zip(ys, rows):
        p, lo, hi = float(r["weighted_%"]), float(r["ci95_low"]), float(r["ci95_high"])
        written = r["group"] == "written"
        ax.plot([lo, hi], [y, y], color=INK if written else MUTED, lw=1.0, solid_capstyle="round")
        ax.plot(p, y, marker="o" if written else "s", ms=5, mfc=INK if written else "white",
                mec=INK, mew=1.0, ls="none")
        ax.text(101.5, y, f"{p:.0f}%  (n={r['n']})", va="center", fontsize=6.5, color=MUTED)
    ax.set_yticks(ys)
    ax.set_yticklabels([LABELS[r["field"]] for r in rows])
    ax.set_xlim(40, 100)
    ax.set_xlabel("Correct, % (weighted by stratum, 95% interval)")
    ax.grid(axis="x", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    split = ys[order.index("non_manual_components")] - 0.5
    ax.axhline(split, color=GRID, lw=0.8)
    ax.plot([], [], marker="o", ms=5, mfc=INK, mec=INK, ls="none", label="Written in the entry")
    ax.plot([], [], marker="s", ms=5, mfc="white", mec=INK, ls="none", label="Drawing only")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.16), ncol=2, frameon=False, fontsize=6.5,
              handletextpad=0.3)
    save(fig, "fig3_accuracy_by_field")


def fig5_calibration():
    rows = read("calibration.csv")
    labels = {"a": "≤ 0.65", "b": "0.70–0.75", "c": "0.80", "d": "≥ 0.85"}
    fig, ax = plt.subplots(figsize=(4.8, 2.4))
    xs = list(range(len(rows)))
    for x, r in zip(xs, rows):
        n, k = int(r["fields"]), int(r["wrong_fields"])
        lo, hi = wilson(k / n, n)
        ax.plot([x, x], [100 * lo, 100 * hi], color=INK, lw=1.0, solid_capstyle="round")
        ax.plot(x, 100 * k / n, marker="o", ms=5, color=INK, ls="none")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{labels[r['ocr_confidence_bin'][0]]}\n{r['signs']} signs" for r in rows])
    ax.set_xlabel("Self-reported ocr_confidence")
    ax.set_ylabel("Fields wrong, %")
    ax.set_ylim(0, 25)
    ax.set_xlim(-0.5, len(rows) - 0.5)
    ax.grid(axis="y", color=GRID, lw=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    save(fig, "fig4_calibration")


if __name__ == "__main__":
    fig1_pipeline()
    fig2_constructed_sign()
    fig4_accuracy()
    fig5_calibration()
    print(f"Figures written to {OUT}")
