"""Plot one indicator for one country from DuckDB and save it as a PNG.

Reads the `v_indicator_change` view, so run src/load_indicator.py first.
An example country (e.g. Peru) is used until the YAML config exists.

Usage:  python src/plot_indicator.py
"""

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt

COUNTRY = "PER"  # ISO3 code of the example country
INDICATOR = "FX.OWN.TOTL.ZS"
TITLE = "Account ownership (% of adults 15+)"
SOURCE = (
    "Source: The World Bank: World Development Indicators: Global Findex Database (CC BY 4.0).\n"
    "Findex is triennial: each point is a survey edition; years in between are not interpolated."
)

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "monitor.duckdb"
OUTPUT_DIR = ROOT / "output"

# Colors from a validated chart palette (light mode)
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = "#2a78d6"


def read_series(country, indicator):
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return con.execute(
            """
            SELECT year, value, change
            FROM v_indicator_change
            WHERE country_iso3 = ? AND indicator = ?
            ORDER BY year
            """,
            [country, indicator],
        ).df()
    finally:
        con.close()


def plot(data, country):
    fig, ax = plt.subplots(figsize=(8, 4.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    ax.plot(data["year"], data["value"], color=SERIES, linewidth=2, zorder=2)
    ax.scatter(
        data["year"], data["value"], s=64, color=SERIES,
        edgecolors=SURFACE, linewidths=2, zorder=3,  # surface ring around each point
    )

    # Label only the first and the latest value; the rest is read from the axis.
    for row in (data.iloc[0], data.iloc[-1]):
        ax.annotate(
            f"{row['value']:.1f}%\n({int(row['year'])})",
            (row["year"], row["value"]),
            textcoords="offset points", xytext=(0, 12),
            ha="center", va="bottom", fontsize=9, color=TEXT_PRIMARY,
        )

    # Percent of population: always show the full 0-100 scale.
    ax.set_ylim(0, 100)
    ax.set_xticks(data["year"])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, length=0, labelsize=9)

    ax.set_title(f"{TITLE} - {country}", loc="left", fontsize=12, color=TEXT_PRIMARY, pad=14)
    fig.text(0.01, 0.01, SOURCE, fontsize=7, color=TEXT_SECONDARY, va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    return fig


def main():
    data = read_series(COUNTRY, INDICATOR)
    if data.empty:
        raise SystemExit(f"No data for {COUNTRY}/{INDICATOR}. Run first: python src/load_indicator.py")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{INDICATOR}_{COUNTRY}.png"
    plot(data, COUNTRY).savefig(out_path, dpi=200)
    print(f"Chart saved to: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
