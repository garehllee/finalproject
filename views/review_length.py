"""Page 2: How long are reviews at each star rating? (data built by prep_reviews.py)"""
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent.parent / "dataset"
RED = "#d62728"


@st.cache_data
def load_reviews():
    return pd.read_csv(DATA / "processed" / "review_sample.csv")


reviews = load_reviews()

st.title("What's in a review?")
st.markdown(
    "Do people write more when they're unhappy? Each box shows how long reviews are "
    "at one star rating, using a sample of real Yelp reviews."
)

# ---------------------------------------------------------------- filters (one row)
f1, f2, f3 = st.columns([1, 1, 2])
metro_choice = f1.selectbox("Metro area", ["All metros"] + sorted(reviews.metro.unique()))
scope = f2.radio("Businesses", ["All businesses", "Restaurants only"], horizontal=True)
year_min, year_max = int(reviews.year.min()), int(reviews.year.max())
years = f3.slider("Review year", year_min, year_max, (year_min, year_max))

df = reviews[reviews.year.between(*years)]
if metro_choice != "All metros":
    df = df[df.metro == metro_choice]
if scope == "Restaurants only":
    df = df[df.is_restaurant]

if df.empty:
    st.info("No reviews match these filters.")
    st.stop()

# ---------------------------------------------------------------- headline numbers
med = df.groupby("stars").words.median()
c1, c2, c3 = st.columns(3)
c1.metric("Reviews in view", f"{len(df):,}")
c2.metric("Median length, 1-star", f"{med.get(1, float('nan')):.0f} words")
c3.metric("Median length, 5-star", f"{med.get(5, float('nan')):.0f} words")

# ---------------------------------------------------------------- box plot
st.subheader("Review length by star rating")

# Pre-compute box-plot stats so the chart stays fast with 100k+ reviews.
stats = (
    df.groupby("stars").words
    .describe(percentiles=[0.25, 0.5, 0.75])
    .rename(columns={"25%": "q1", "50%": "median", "75%": "q3"})
    .reset_index()
)
iqr = stats.q3 - stats.q1
# Whiskers: furthest data point within 1.5 x IQR of the box (Tukey).
stats["lo"] = [
    df.loc[(df.stars == s) & (df.words >= q1 - 1.5 * i), "words"].min()
    for s, q1, i in zip(stats.stars, stats.q1, iqr)
]
stats["hi"] = [
    df.loc[(df.stars == s) & (df.words <= q3 + 1.5 * i), "words"].max()
    for s, q3, i in zip(stats.stars, stats.q3, iqr)
]
stats["label"] = stats.stars.map(lambda s: "★" * s)

x = alt.X("label:N", title="Star rating", sort=[("★" * s) for s in range(1, 6)],
          axis=alt.Axis(labelAngle=0, labelFontSize=14))
tooltip = [
    alt.Tooltip("label:N", title="Rating"),
    alt.Tooltip("count:Q", title="Reviews", format=","),
    alt.Tooltip("median:Q", title="Median words", format=",.0f"),
    alt.Tooltip("q1:Q", title="25th percentile", format=",.0f"),
    alt.Tooltip("q3:Q", title="75th percentile", format=",.0f"),
    alt.Tooltip("mean:Q", title="Mean words", format=",.0f"),
]
base = alt.Chart(stats).encode(x=x, tooltip=tooltip)
whisker = base.mark_rule(color="#555", strokeWidth=1.5).encode(
    y=alt.Y("lo:Q", title="Words in review"), y2="hi:Q"
)
caps = alt.layer(
    base.mark_tick(color="#555", size=24, thickness=1.5).encode(y="lo:Q"),
    base.mark_tick(color="#555", size=24, thickness=1.5).encode(y="hi:Q"),
)
box = base.mark_bar(size=56, color=RED, opacity=0.35, stroke=RED, strokeWidth=1.5,
                    cornerRadius=3).encode(y="q1:Q", y2="q3:Q")
median = base.mark_tick(color="#111", size=56, thickness=2.5).encode(y="median:Q")
labels = base.mark_text(dx=34, align="left", fontSize=12, color="#333").encode(
    y="median:Q", text=alt.Text("median:Q", format=",.0f")
)

chart = alt.layer(whisker, caps, box, median, labels).properties(height=440)
st.altair_chart(chart, width="stretch")
st.caption(
    "Box = middle 50% of reviews; dark line = median (number beside it); whiskers reach "
    "the longest and shortest reviews within 1.5× the box height. Very long outliers are hidden."
)

# ---------------------------------------------------------------- context bar chart
st.subheader("How many reviews get each rating?")
share = df.stars.value_counts(normalize=True).rename("share").reset_index()
share["label"] = share.stars.map(lambda s: "★" * s)
bars = alt.Chart(share).mark_bar(color=RED, opacity=0.8, cornerRadiusEnd=3, size=28).encode(
    y=alt.Y("label:N", title=None, sort=[("★" * s) for s in range(5, 0, -1)],
            axis=alt.Axis(labelFontSize=14)),
    x=alt.X("share:Q", title="Share of reviews", axis=alt.Axis(format="%", tickCount=5)),
    tooltip=[alt.Tooltip("label:N", title="Rating"),
             alt.Tooltip("share:Q", title="Share", format=".1%")],
)
bar_labels = bars.mark_text(align="left", dx=4, fontSize=12, color="#333").encode(
    text=alt.Text("share:Q", format=".0%")
)
st.altair_chart((bars + bar_labels).properties(height=220), width="stretch")

st.caption(
    "Source: Yelp Open Dataset reviews. The review file in the repo's archive is cut off, "
    f"so this page uses the first {len(reviews):,} reviews that can be read from it "
    f"({year_min}–{year_max})."
)
