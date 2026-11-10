"""One figure style for the whole repo: lab-report look, white background,
DIN-style lettering, a small fixed palette. Eye diagrams are drawn as
density (how often a trace passes each point), like a sampling scope.
"""
from __future__ import annotations

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap

INK = "#1b1f24"
GRID = "#d5d9de"
BLUE = "#1f5aa6"     # primary data
RED = "#c8421f"      # limits and chosen points
TEAL = "#1a7f72"
AMBER = "#b07d12"
GRAY = "#7a828c"     # references
SERIES = [GRAY, AMBER, TEAL, BLUE]
MONO = "Consolas"

EYE_CMAP = LinearSegmentedColormap.from_list(
    "eye", ["#dfe8f3", "#7fa6d6", "#1f5aa6", "#0d2f5e", "#c8421f"])


def apply() -> None:
    mpl.rcParams.update({
        "font.family": ["Bahnschrift", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "legend.frameon": False,
        "legend.fontsize": 8,
        "lines.linewidth": 1.6,
        "figure.dpi": 100,
        "savefig.dpi": 170,
        "savefig.bbox": "tight",
        "figure.constrained_layout.use": True,
    })
