"""Financial inclusion dashboard (Streamlit). One tab per view.

Uses data/monitor.duckdb if it exists (run src/load_indicator.py first);
otherwise it downloads the latest weekly release from GitHub.

Usage:  streamlit run src/dashboard.py
"""

import tempfile
import time
from datetime import timedelta
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
GROUP_COLOR = "#eb6834"  # second slot of the validated categorical palette
MUTED_COLOR = "#8a8984"
TEXT_COLOR = {"light": "#0b0b0b", "dark": "#f0efec"}

ATTRIBUTION = (
    "Data: The World Bank: World Development Indicators: Global Findex Database (CC BY 4.0). "
    "Margins of error from the Global Findex survey methodology, Table A.1. "
    "This project is not affiliated with or endorsed by the World Bank."
)


@st.cache_resource(ttl=timedelta(days=1))  # re-download once a day so the weekly release shows up
def connect():
    path = LOCAL_DB
    if not path.exists():
        # A new file per download: an open connection may still be reading the previous one.
        path = Path(tempfile.gettempdir()) / f"financial-inclusion-monitor-{int(time.time())}.duckdb"
        response = requests.get(RELEASE_DB_URL, timeout=60)
        response.raise_for_status()
        path.write_bytes(response.content)
    return duckdb.connect(str(path), read_only=True)


def query(sql, params=None):
    # One cursor per query: the cached connection is shared between sessions.
    return connect().cursor().execute(sql, params or []).df()


def margin_text(margins):
    """Readable margin for tooltips: Altair would print an empty value as "null"."""
    return margins.map(lambda m: "not available" if pd.isna(m) else f"±{m:.1f}")


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
            alt.Tooltip("margin_text:N", title="Margin of error (95%)"),
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
    latest["margin_text"] = margin_text(latest["margin"])

    st.altair_chart(overview_chart(latest, median, median_label), width="stretch")
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


def verdict(change, significant):
    """Plain-language reading of a change between editions (icon + text, never color alone)."""
    if pd.isna(change):
        return "No previous edition"
    if pd.isna(significant):
        return "Cannot assess: no margin"
    if not significant:
        return "● No significant change"
    return "▲ Increase" if change > 0 else "▼ Decrease"


def change_sentence(row):
    if pd.isna(row["change"]):
        return f"{int(row['edition'])} is the first edition with data."
    text = f"{int(row['previous_edition'])} → {int(row['edition'])}: {row['change']:+.1f} points. "
    if pd.isna(row["significant"]):
        return text + "A margin of error is not available for both editions, so this change cannot be assessed."
    if row["significant"]:
        return text + f"Significant: larger than the margin of the change (±{row['change_margin']:.1f})."
    return text + f"Not significant: smaller than the margin of the change (±{row['change_margin']:.1f})."


def evolution_chart(series):
    text_color = TEXT_COLOR.get(st.context.theme.type, TEXT_COLOR["light"])
    x = alt.X(
        "edition:Q",
        title="Findex edition",
        scale=alt.Scale(domain=[2010, 2025]),
        # No vertical grid: it would hide the grey margin lines drawn at each edition.
        axis=alt.Axis(values=series["edition"].tolist(), format="d", grid=False),
    )
    y = alt.Y("value:Q", title="% of adults 15+", scale=alt.Scale(domain=[0, 100]))
    base = alt.Chart(series).encode(
        x=x,
        tooltip=[
            alt.Tooltip("edition:Q", title="Findex edition", format="d"),
            alt.Tooltip("survey_year:Q", title="Surveyed in", format="d"),
            alt.Tooltip("value:Q", title="% of adults", format=".1f"),
            alt.Tooltip("margin_text:N", title="Margin of error (95%)"),
        ],
    )
    line = base.mark_line(color=SERIES_COLOR, strokeWidth=2).encode(y=y)
    margins = base.mark_rule(color=MUTED_COLOR, strokeWidth=2).encode(y="low:Q", y2="high:Q")
    points = base.mark_circle(color=SERIES_COLOR, size=90, opacity=1).encode(y=y)
    # Label only the latest edition; the rest is read from the axis or the tooltip.
    last_label = (
        alt.Chart(series.tail(1))
        .mark_text(dy=-16, fontSize=12, color=text_color)
        .encode(x=x, y=y, text="label:N")
    )
    return (line + margins + points + last_label).properties(height=320)


def evolution():
    st.subheader("Account ownership over time")
    st.caption("Did account ownership really change, or is the change smaller than the margin of error?")

    countries = query(
        """
        SELECT DISTINCT f.country_iso3, c.name
        FROM v_findex_change AS f
        JOIN countries AS c USING (country_iso3)
        ORDER BY c.name
        """
    )
    names = dict(zip(countries["country_iso3"], countries["name"]))
    country = st.selectbox("Country", list(names), format_func=names.get)

    indicator = st.radio(
        "Group",
        list(FINDEX_GROUPS),
        format_func=FINDEX_GROUPS.get,
        horizontal=True,
        key="evolution_group",  # the Overview tab has a radio with the same label and options
    )

    series = query(
        """
        SELECT edition, survey_year, value, margin,
               previous_edition, change, change_margin, significant
        FROM v_findex_change
        WHERE country_iso3 = ? AND indicator = ?
        ORDER BY edition
        """,
        [country, indicator],
    )
    series["low"] = series["value"] - series["margin"]
    series["high"] = series["value"] + series["margin"]
    series["label"] = series.apply(bar_label, axis=1)
    series["margin_text"] = margin_text(series["margin"])

    st.altair_chart(evolution_chart(series), width="stretch")
    st.markdown(f"**{names[country]}**: {change_sentence(series.iloc[-1])}")
    st.caption(
        "Lines only connect survey editions; values between editions were not measured. "
        "Grey vertical lines: margin of error (95%), available for the 2021 and 2024 editions only."
    )

    st.markdown("#### All countries: change from the previous edition")
    newest = int(query("SELECT max(edition) AS e FROM v_findex_change")["e"].iloc[0])
    table = query(
        """
        SELECT c.name AS country, f.previous_edition, f.previous_value, f.edition,
               f.value, f.change, f.change_margin, f.significant
        FROM v_findex_change AS f JOIN countries AS c USING (country_iso3)
        WHERE f.indicator = ? AND f.edition = ?
        ORDER BY f.change DESC
        """,
        [indicator, newest],
    )
    table["verdict"] = [verdict(c, s) for c, s in zip(table["change"], table["significant"])]
    one_decimal = "%.1f"
    st.dataframe(
        table.drop(columns="significant"),
        hide_index=True,
        column_config={
            "country": "Country",
            "previous_edition": st.column_config.NumberColumn("From", format="%d"),
            "previous_value": st.column_config.NumberColumn("Value", format=one_decimal),
            "edition": st.column_config.NumberColumn("To", format="%d"),
            "value": st.column_config.NumberColumn("Value ", format=one_decimal),
            "change": st.column_config.NumberColumn("Change (points)", format="%+.1f"),
            "change_margin": st.column_config.NumberColumn("Margin of change (±)", format=one_decimal),
            "verdict": "Verdict",
        },
    )
    notes = [
        f"Only countries with data in the {newest} edition are listed.",
        "A change counts as significant only when it is larger than the margin of the change, "
        "sqrt(m1² + m2²), because both surveys have their own error.",
    ]
    if indicator != TOTAL:
        notes.append(
            "The margin of error for this group is not published, so its changes cannot be assessed."
        )
    st.markdown("\n".join(f"- {note}" for note in notes))


def gaps_chart(table, group_label):
    # Long format: one row per country and series, so Altair draws a legend.
    points = table.melt(
        id_vars=["name", "edition", "gap"], value_vars=["all_adults", "group_value"],
        var_name="series", value_name="value",
    )
    points["series"] = points["series"].map({"all_adults": "All adults", "group_value": group_label})
    # labelOverlap=False: otherwise Vega hides every other country name when rows are tight.
    y = alt.Y("name:N", sort=alt.EncodingSortField("gap", order="descending"), title=None,
              axis=alt.Axis(labelLimit=250, labelOverlap=False))
    x_scale = alt.Scale(domain=[0, 100])
    x_axis = alt.Axis(values=list(range(0, 101, 20)), title="% of adults 15+")
    lines = alt.Chart(table).mark_rule(color=MUTED_COLOR, strokeWidth=2).encode(
        y=y, x=alt.X("group_value:Q", scale=x_scale, axis=x_axis), x2="all_adults:Q"
    )
    dots = alt.Chart(points).mark_circle(size=90, opacity=1).encode(
        y=y,
        x=alt.X("value:Q", scale=x_scale, axis=x_axis),
        color=alt.Color(
            "series:N",
            scale=alt.Scale(domain=["All adults", group_label], range=[SERIES_COLOR, GROUP_COLOR]),
            legend=alt.Legend(title=None, orient="top"),
        ),
        tooltip=[
            alt.Tooltip("name:N", title="Country"),
            alt.Tooltip("series:N", title="Group"),
            alt.Tooltip("value:Q", title="% of adults", format=".1f"),
            alt.Tooltip("gap:Q", title="Gap (points)", format=".1f"),
            alt.Tooltip("edition:Q", title="Findex edition", format="d"),
        ],
    )
    return (lines + dots).properties(height=28 * len(table))


def gaps():
    st.subheader("Gaps: who is left behind?")
    st.caption(
        "Points between the share of all adults with an account and the share in a group. "
        "The data has no figures for men or the richest 60%, so the gap is measured "
        "against all adults, not against the other half."
    )
    groups = {code: label for code, label in FINDEX_GROUPS.items() if code != TOTAL}
    indicator = st.radio(
        "Group", list(groups), format_func=groups.get, horizontal=True, key="gaps_group"
    )
    table = query(
        """
        SELECT c.name, t.edition, t.value AS all_adults, g.value AS group_value,
               t.value - g.value AS gap
        FROM v_findex_change AS t
        JOIN v_findex_change AS g
            ON g.country_iso3 = t.country_iso3 AND g.edition = t.edition AND g.indicator = ?
        JOIN countries AS c ON c.country_iso3 = t.country_iso3
        WHERE t.indicator = ?
        QUALIFY row_number() OVER (PARTITION BY t.country_iso3 ORDER BY t.edition DESC) = 1
        """,
        [indicator, TOTAL],
    )
    newest = table["edition"].max()
    outdated = table["edition"] != newest
    table.loc[outdated, "name"] = table["name"] + " (" + table["edition"].astype(str) + ")"
    st.altair_chart(gaps_chart(table, groups[indicator]), width="stretch")

    current = table[~outdated]
    st.markdown(
        f"Median gap of {len(current)} countries with {newest} data, unweighted: "
        f"**{current['gap'].median():.1f} points**. Sorted from the largest gap to the smallest."
    )
    notes = [
        "The margin of error for this group is not published and is larger than the national "
        "margin, so small gaps (a few points) may be survey noise.",
        "A gap below zero means the group is above all adults.",
    ]
    for row in table[outdated].itertuples():
        notes.append(f"**{row.name}**: latest edition is {row.edition}; left out of the median.")
    st.markdown("\n".join(f"- {note}" for note in notes))
    with st.expander("Table"):
        st.dataframe(
            table.sort_values("gap", ascending=False),
            hide_index=True,
            column_config={
                "name": "Country",
                "edition": st.column_config.NumberColumn("Edition", format="%d"),
                "all_adults": st.column_config.NumberColumn("All adults", format="%.1f"),
                "group_value": st.column_config.NumberColumn(groups[indicator], format="%.1f"),
                "gap": st.column_config.NumberColumn("Gap (points)", format="%.1f"),
            },
        )


st.set_page_config(page_title="Financial inclusion monitor", layout="wide")
st.title("Financial inclusion monitor: Latin America")

overview_tab, evolution_tab, gaps_tab = st.tabs(["Overview", "Evolution", "Gaps"])
with overview_tab:
    overview()
with evolution_tab:
    evolution()
with gaps_tab:
    gaps()

st.divider()
st.caption(ATTRIBUTION)
