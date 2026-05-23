"""Series-wide color tokens.

Mirrors the brand tokens defined in
`personal-website/src/app/globals.css` so static charts produced here read as
part of the same publication. If a token changes on the website side, update
it here too.
"""

# Light theme — primary publication context for static charts.
BG = "#faf8f4"
SURFACE = "#f3efe8"
BORDER = "#e2dcd0"
TEXT = "#1a1a1a"
TEXT_SECONDARY = "#4a4a4a"
MUTED = "#8a8478"
ACCENT = "#3a5a8c"
ALERT = "#b04a47"

# Sequential ramp for choropleths (low -> high). Hand-tuned from the
# accent blue toward the alert red so high values read as "more friction."
RAMP_SEQUENTIAL = [
    "#ebe6dd",
    "#c9d3e0",
    "#9fb5cd",
    "#7795b8",
    "#557aa1",
    "#3a5a8c",
    "#774b6f",
    "#b04a47",
]

# Diverging ramp for "above / below median" framings.
RAMP_DIVERGING = [
    "#3a5a8c",
    "#7fa8d9",
    "#c9d3e0",
    "#f3efe8",
    "#e8c5b4",
    "#d68682",
    "#b04a47",
]

# Categorical palette for up to 6 named CDs in a comparison chart.
CATEGORICAL = [
    "#3a5a8c",
    "#b04a47",
    "#7a8a4f",
    "#a07042",
    "#5d4a7a",
    "#4a8a85",
]


def for_matplotlib():
    """Apply series-default styling to matplotlib's rcParams.

    Call once at the top of a notebook / script before plotting so every
    chapter ships with the same typography and grid treatment.
    """
    import matplotlib as mpl

    mpl.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "axes.edgecolor": BORDER,
        "axes.labelcolor": TEXT,
        "axes.titlecolor": TEXT,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "grid.color": BORDER,
        "text.color": TEXT,
        "font.family": "serif",
        "font.serif": ["Source Serif 4", "Iowan Old Style", "Georgia", "serif"],
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "regular",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.facecolor": BG,
        "savefig.bbox": "tight",
        "savefig.dpi": 144,
    })
