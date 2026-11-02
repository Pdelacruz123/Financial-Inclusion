"""Financial inclusion dashboard (Streamlit). One tab per view.

Uses data/monitor.duckdb if it exists (run src/load_indicator.py first);
otherwise it downloads the latest weekly release from GitHub.

Usage:  streamlit run src/dashboard.py
"""

import tempfile
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import requests
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
LOCAL_DB = ROOT / "data" / "monitor.duckdb"
RELEASE_DB_URL = (
    "https://github.com/Pdelacruz123/Financial-Inclusion/releases/latest/download/monitor.duckdb"
)

FINDEX_GROUPS = {
    "FX.OWN.TOTL.ZS": "All adults",
    "FX.OWN.TOTL.FE.ZS": "Women",
    "FX.OWN.TOTL.40.ZS": "Poorest 40%",
}
TOTAL = "FX.OWN.TOTL.ZS"  # the only group with a published sample size, so the only one with margins

SERIES_COLOR = "#2a78d6"
MUTED_COLOR = "#8a8984"
TEXT_COLOR = {"light": "#0b0b0b", "dark": "#f0efec"}

ATTRIBUTION = (
    "Data: The World Bank: World Development Indicators: Global Findex Database (CC BY 4.0). "
    "Margins of error from the Global Findex survey methodology, Table A.1. "
    "This project is not affiliated with or endorsed by the World Bank."
)


@st.cache_resource
def connect():
    path = LOCAL_DB
    if not path.exists():
        path = Path(tempfile.gettempdir()) / "financial-inclusion-monitor.duckdb"
        response = requests.get(RELEASE_DB_URL, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    return duckdb.connect(str(path), read_only=True)


def query(sql, params=None):
    # One cursor per query: the cached connection is shared between sessions.
    return connect().cursor().execute(sql, params or []).df()


def bar_label(row):
    text = f"{row['value']:.1f}"
    if pd.notna(row["margin"]):
        text += f" ±{row['margin']:.1f}"
    return f"{text}  ({row['edition']})"


def overview_chart(latest, median, median_label):
    # Domain goes past 100 only to leave room for the labels; ticks stop at 100.
    x_scale = alt.Scale(domain=[0, 125])
    x_axis = alt.Axis(values=list(range(0, 101, 20)), title="% of adults 15+")
    # Altair text marks do not follow the Streamlit theme, so pick the color ourselves.
    text_color = TEXT_COLOR.get(st.context.theme.type, TEXT_COLOR["light"])
    base = alt.Chart(latest).encode(
        y=alt.Y("name:N", sort="-x", title=None, axis=alt.Axis(labelLimit=250)),
        tooltip=[
            alt.Tooltip("name:N", title="Country"),
            alt.Tooltip("value:Q", title="% of adults", format=".1f"),
            alt.Tooltip("margin:Q", title="Margin of error (±)", format=".1f"),
            alt.Tooltip("edition:Q", title="Findex edition"),
            alt.Tooltip("survey_year:Q", title="Surveyed in"),
        ],
    )
    bars = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
        x=alt.X("value:Q", scale=x_scale, axis=x_axis),
        # Countries whose latest data is an older edition are drawn in grey.
        color=alt.condition("datum.is_current", alt.value(SERIES_COLOR), alt.value(MUTED_COLOR)),
    )
    margins = base.mark_rule(color=MUTED_COLOR, strokeWidth=2).encode(x="low:Q", x2="high:Q")
    labels = base.mark_text(align="left", dx=6, fontSize=12, color=text_color).encode(
        x="label_x:Q", text="label:N"
    )
    median_rule = (
        alt.Chart(pd.DataFrame({"median": [median], "text": [median_label]}))
        .mark_rule(color=MUTED_COLOR, strokeDash=[4, 4], strokeWidth=1.5)
        .encode(x="median:Q", tooltip=alt.Tooltip("text:N", title="Median"))
    )
    return (bars + margins + labels + median_rule).properties(height=26 * len(latest))


def data_notes(latest, indicator):
    notes = []
    gaps = query(
        """
        SELECT c.name, g.gap, g.latest_period
        FROM v_data_gaps AS g JOIN countries AS c USING (country_iso3)
        WHERE g.indicator = ?
        ORDER BY c.name
        """,
        [indicator],
    )
    for row in gaps.itertuples():
        if row.gap == "no data":
            notes.append(f"**{row.name}**: no data in Global Findex.")
        else:
            notes.append(
                f"**{row.name}**: latest edition is {row.latest_period}; "
                "it is shown but left out of the median."
            )
    for row in latest[latest["survey_year"] != latest["edition"]].itertuples():
        notes.append(f"**{row.name}**: {row.edition} edition, surveyed in {row.survey_year}.")
    if indicator == TOTAL:
        notes.append(
            "Margins of error (95%) are only available for the 2021 and 2024 editions."
        )
    else:
        notes.append(
            "The margin of error for this group is not published. It is larger than the "
            "margin for all adults, because fewer people in the survey belong to this group."
        )
    notes.append("Findex is a survey run every three years; years in between are not interpolated.")
    return notes


def overview():
    st.subheader("Account ownership: latest available data")
    st.caption(
        "Share of adults (15+) with an account at a financial institution or a "
        "mobile-money provider."
    )
    indicator = st.radio(
        "Group", list(FINDEX_GROUPS), format_func=FINDEX_GROUPS.get, horizontal=True
    )

    latest = query(
        """
        SELECT c.name, f.value, f.margin, f.edition, f.survey_year
        FROM v_findex_change AS f JOIN countries AS c USING (country_iso3)
        WHERE f.indicator = ?
        QUALIFY row_number() OVER (PARTITION BY f.country_iso3 ORDER BY f.edition DESC) = 1
        """,
        [indicator],
    )
    newest = latest["edition"].max()
    current = latest[latest["edition"] == newest]
    median = current["value"].median()
    median_label = f"Median of {len(current)} countries with {newest} data, unweighted: {median:.1f}"

    latest["is_current"] = latest["edition"] == newest
    latest["low"] = latest["value"] - latest["margin"]
    latest["high"] = latest["value"] + latest["margin"]
    latest["label_x"] = latest["high"].fillna(latest["value"])
    latest["label"] = latest.apply(bar_label, axis=1)

    st.altair_chart(overview_chart(latest, median, median_label), use_container_width=True)
    legend = (
        f"Dashed line: {median_label[0].lower() + median_label[1:]}. "
        f"Grey bars: latest data is from an edition older than {newest}."
    )
    if latest["margin"].notna().any():
        legend += " Thin lines: margin of error (95%)."
    st.markdown(legend)

    with st.expander("Data notes", expanded=True):
        st.markdown("\n".join(f"- {note}" for note in data_notes(latest, indicator)))

    with st.expander("Table"):
        st.dataframe(
            latest[["name", "value", "margin", "edition", "survey_year"]].sort_values(
                "value", ascending=False
            ),
            hide_index=True,
        )


st.set_page_config(page_title="Financial inclusion monitor", layout="wide")
st.title("Financial inclusion monitor: Latin America")

(overview_tab,) = st.tabs(["Overview"])
with overview_tab:
    overview()

st.divider()
st.caption(ATTRIBUTION)
