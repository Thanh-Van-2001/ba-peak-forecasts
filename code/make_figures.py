"""Figures. Reads out/ba_table.csv and out/results.json; writes paper/fig_bias.pdf and paper/fig_heat.pdf.
Run from the repository root: python -I code/make_figures.py"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({"font.size": 7.5, "font.family": "serif", "axes.linewidth": 0.6, "axes.edgecolor": "#555555",
                     "xtick.color": "#333333", "ytick.color": "#333333", "axes.labelcolor": "#222222",
                     "legend.frameon": False, "pdf.fonttype": 42})
GRID, ORANGE, BLUE, GRAY = "#dddddd", "#D55E00", "#0072B2", "#777777"
T = pd.read_csv("out/ba_table.csv", index_col=0)
P = T[T["primary"]].sort_values("bias_all")
R = json.load(open("out/results.json"))
LIM = (-17, 14)

# Fig 1: dumbbell of bias on actual-top days vs forecast-top days
fig, ax = plt.subplots(figsize=(3.45, 5.0))
y = np.arange(len(P))
clip = lambda v: np.clip(v, LIM[0] + 0.3, LIM[1] - 0.3)
for i, (b, r) in enumerate(P.iterrows()):
    ax.plot(clip([r["bias_A"], r["bias_F"]]), [i, i], color="#bbbbbb", lw=1.0, zorder=1)
ax.scatter(clip(P["null_bias_A"]), y, marker="|", s=30, color=GRAY, lw=1.0, zorder=2, label="actual-top, calibrated benchmark")
ax.scatter(clip(P["bias_A"]), y, marker="o", s=16, color=ORANGE, edgecolor="white", lw=0.5, zorder=3, label="days with top-5% actual peak")
ax.scatter(clip(P["bias_F"]), y, marker="s", s=14, color=BLUE, edgecolor="white", lw=0.5, zorder=3, label="days with top-5% forecast peak")
ax.axvline(0, color="#444444", lw=0.7)
ax.set_yticks(y)
ax.set_yticklabels(P.index, fontsize=6)
ax.set_ylim(-0.8, len(P) - 0.2)
ax.set_xlim(LIM)
ax.set_xlabel("Median $p_d$ (%); negative = forecast too low")
ax.grid(axis="x", color=GRID, lw=0.5)
for i, (b, r) in enumerate(P.iterrows()):
    if r[["bias_A", "bias_F", "null_bias_A"]].min() < LIM[0]:
        ax.annotate(f"off scale: {r['bias_A']:.0f} and {r['bias_F']:.0f}", (LIM[0] + 0.5, i), xytext=(6, -2.5),
                    textcoords="offset points", fontsize=5.5, color="#444444")
ax.legend(loc="upper left", fontsize=6, handletextpad=0.2, borderaxespad=0.3, markerscale=1.0)
fig.tight_layout(pad=0.3)
fig.savefig("paper/fig_bias.pdf")

# Fig 2: heat. (a) per-BA hot-minus-other difference; (b) error by day of hot spell
fig, axs = plt.subplots(1, 2, figsize=(3.45, 1.9), gridspec_kw={"width_ratios": [1.15, 1]})
h = np.sort(P["heat"].dropna().values)
ax = axs[0]
ax.scatter(np.clip(h, -6, 3), np.arange(len(h)), s=7, color=BLUE, zorder=3)
ph = R["secondary"]["pooled_heat"]
ax.axvspan(ph["lo"], ph["hi"], color="#cfe3f3", zorder=1)
ax.axvline(ph["mu"], color=BLUE, lw=1.0, zorder=2)
ax.axvline(0, color="#444444", lw=0.7)
ax.set_yticks([])
ax.set_xlim(-6, 3)
ax.set_xlabel("Hot $-$ other days (pp)")
ax.set_title("(a) one dot per BA", fontsize=7)
ax.grid(axis="x", color=GRID, lw=0.5)
ax = axs[1]
cols = [("heat_other", "other"), ("heat_run1", "1"), ("heat_run2", "2"), ("heat_run3", "3+")]
for i, (c, lab) in enumerate(cols):
    v = P[c].dropna()
    q1, q2, q3 = np.percentile(v, [25, 50, 75])
    ax.plot([i, i], [q1, q3], color=BLUE if i else GRAY, lw=2.2, solid_capstyle="round")
    ax.scatter([i], [q2], s=22, color="white", edgecolor=BLUE if i else GRAY, lw=1.2, zorder=3)
ax.axhline(0, color="#444444", lw=0.7)
ax.set_xticks(range(4))
ax.set_xticklabels([c[1] for c in cols])
ax.set_xlabel("Day of hot spell")
ax.set_ylabel("Median $p_d$ (%)")
ax.set_title("(b) median, IQR over BAs", fontsize=7)
ax.grid(axis="y", color=GRID, lw=0.5)
fig.tight_layout(pad=0.3, w_pad=0.8)
fig.savefig("paper/fig_heat.pdf")
print("ok")
