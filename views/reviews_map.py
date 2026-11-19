"""Page 1: Yelp reviews vs. population (data built by prep_data.py)."""
import json
import math
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent.parent / "dataset"
RED = "#d62728"

# ---------------------------------------------------------------- data
@st.cache_data
def load_data():
    metro = pd.read_csv(DATA / "processed" / "metro_reviews.csv")
    county = pd.read_csv(DATA / "processed" / "county_reviews.csv")
    census = pd.read_csv(DATA / "census" / "county_population_income_2018.csv")
    topo = json.loads((DATA / "census" / "us-10m.json").read_text())
    return metro, county, census, topo


metro, county, census, topo = load_data()


def per_1k(df, restaurants_only):
    prefix = "restaurant_" if restaurants_only else ""
    df = df.copy()
    df["shown_reviews"] = df[f"{prefix}reviews"]
    df["shown_businesses"] = df[f"{prefix}businesses"]
    df["reviews_per_1k"] = df.shown_reviews / df.population * 1000
    return df


def topo_data(feature):
    return alt.Data(values=topo, format=alt.DataFormat(type="topojson", feature=feature))


# ---------------------------------------------------------------- header + filters
st.title("Who leaves Yelp reviews?")
st.markdown(
    "Big cities get more reviews simply because more people live there. Dividing "
    "by population shows which places review **more than their size predicts**."
)

scope = st.radio("Businesses", ["All businesses", "Restaurants only"], horizontal=True)
restaurants_only = scope == "Restaurants only"

metro_df = per_1k(metro, restaurants_only)
county_df = per_1k(county, restaurants_only)

top = metro_df.sort_values("reviews_per_1k", ascending=False).iloc[0]
low = metro_df.sort_values("reviews_per_1k").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("Reviews in these 10 metros", f"{metro_df.shown_reviews.sum():,.0f}")
c2.metric(f"Most reviews per resident — {top.metro}", f"{top.reviews_per_1k:,.0f} per 1,000")
c3.metric(f"Fewest reviews per resident — {low.metro}", f"{low.reviews_per_1k:,.0f} per 1,000")

# ---------------------------------------------------------------- 1. national map
st.subheader("Reviews per 1,000 residents, by metro area")

size_max_metro = metro_df.reviews_per_1k.max()
states = (
    alt.Chart(topo_data("states"))
    .mark_geoshape(fill="#f4f4f4", stroke="#9a9a9a", strokeWidth=0.6)
)
metro_points = alt.Chart(metro_df).encode(
    longitude="lon:Q", latitude="lat:Q"
)
bubbles = metro_points.mark_circle(
    color=RED, opacity=0.6, stroke="white", strokeWidth=1.5
).encode(
    size=alt.Size(
        "reviews_per_1k:Q",
        title="Reviews per 1,000 residents",
        scale=alt.Scale(domain=[0, size_max_metro], range=[0, 4000]),
        legend=alt.Legend(orient="bottom-left", symbolFillColor=RED, symbolStrokeColor=RED,
                          symbolOpacity=0.6, format=",.0f", tickCount=3),
    ),
    tooltip=[
        alt.Tooltip("metro:N", title="Metro"),
        alt.Tooltip("reviews_per_1k:Q", title="Reviews per 1,000 residents", format=",.0f"),
        alt.Tooltip("shown_reviews:Q", title="Reviews", format=","),
        alt.Tooltip("shown_businesses:Q", title="Businesses", format=","),
        alt.Tooltip("population:Q", title="Population (2018)", format=","),
        alt.Tooltip("counties:Q", title="Counties"),
    ],
)
labels = metro_points.mark_text(dy=-4, fontSize=11, color="#333", baseline="bottom").encode(
    text="metro:N"
)
us_map = (
    alt.layer(states, bubbles, labels)
    .project(type="albersUsa")
    .properties(height=480)
    .configure_view(stroke=None)
)
st.altair_chart(us_map, width="stretch")
st.caption("Circle area is proportional to reviews per 1,000 residents. Hover a circle for details.")

# ---------------------------------------------------------------- 2. zoomed-in map
st.subheader("Zoom in: reviews vs. household income")
metro_choice = st.columns([1, 3])[0].selectbox(
    "Metro area", sorted(metro.metro), index=sorted(metro.metro).index("Philadelphia")
)
st.markdown(
    "Counties are shaded by median household income (darker = higher). Red circles "
    "sit at the center of each county's Yelp businesses; outlined counties make up the metro."
)

sel = county_df[county_df.metro == metro_choice]

# Frame the selected metro's counties with some padding (Mercator projection).
W, H = 900, 560
pad = 0.25
min_lon, max_lon = sel.min_lon.min(), sel.max_lon.max()
min_lat, max_lat = sel.min_lat.min(), sel.max_lat.max()
dlon, dlat = max_lon - min_lon, max_lat - min_lat
min_lon, max_lon = min_lon - dlon * pad, max_lon + dlon * pad
min_lat, max_lat = min_lat - dlat * pad, max_lat + dlat * pad


def merc_y(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


scale = min(
    W / math.radians(max_lon - min_lon),
    H / (merc_y(max_lat) - merc_y(min_lat)),
)
center_lat = math.degrees(2 * math.atan(math.exp((merc_y(max_lat) + merc_y(min_lat)) / 2)) - math.pi / 2)
center = [(min_lon + max_lon) / 2, center_lat]
projection = dict(type="mercator", scale=scale, center=center, translate=[W / 2, H / 2])

income_lookup = alt.LookupData(census, "fips", ["county", "state", "median_income", "population"])
all_counties = (
    alt.Chart(topo_data("counties"))
    .mark_geoshape(stroke="white", strokeWidth=0.8)
    .transform_lookup(lookup="id", from_=income_lookup)
    .encode(
        color=alt.Color(
            "median_income:Q",
            title="Median household income",
            scale=alt.Scale(range=["#f5f5f5", "#6b6b6b"], domain=[30000, 110000], clamp=True),
            legend=alt.Legend(format="$,.0f", orient="right", gradientLength=160),
        ),
        tooltip=[
            alt.Tooltip("county:N", title="County"),
            alt.Tooltip("state:N", title="State"),
            alt.Tooltip("median_income:Q", title="Median household income", format="$,.0f"),
            alt.Tooltip("population:Q", title="Population (2018)", format=","),
        ],
    )
)
metro_outline = (
    alt.Chart(topo_data("counties"))
    .mark_geoshape(fillOpacity=0, stroke="#111", strokeWidth=1.6)
    .transform_filter(alt.FieldOneOfPredicate(field="id", oneOf=sel.fips.tolist()))
)
size_max_county = county_df.reviews_per_1k.max()  # same scale for every metro
county_bubbles = (
    alt.Chart(sel)
    .mark_circle(color=RED, opacity=0.8, stroke="white", strokeWidth=1.5)
    .encode(
        longitude="lon:Q",
        latitude="lat:Q",
        size=alt.Size(
            "reviews_per_1k:Q",
            title="Reviews per 1,000 residents",
            scale=alt.Scale(domain=[0, size_max_county], range=[0, 6000]),
            legend=alt.Legend(orient="right", symbolFillColor=RED, symbolStrokeColor=RED,
                              symbolOpacity=0.8, format=",.0f", tickCount=3),
        ),
        tooltip=[
            alt.Tooltip("county:N", title="County"),
            alt.Tooltip("reviews_per_1k:Q", title="Reviews per 1,000 residents", format=",.0f"),
            alt.Tooltip("shown_reviews:Q", title="Reviews", format=","),
            alt.Tooltip("shown_businesses:Q", title="Businesses", format=","),
            alt.Tooltip("median_income:Q", title="Median household income", format="$,.0f"),
            alt.Tooltip("population:Q", title="Population (2018)", format=","),
        ],
    )
)
zoom_map = (
    alt.layer(all_counties, metro_outline, county_bubbles)
    .project(**projection, clipExtent=[[0, 0], [W, H]])
    .properties(width=W, height=H)
    .resolve_scale(size="independent")
    .configure_view(stroke="#999")
)
st.altair_chart(zoom_map, width="content")
st.caption(
    "Circle sizes use the same scale for every metro, so you can compare across metros. "
    "Counties with fewer than 25 Yelp businesses are left out."
)

with st.expander(f"Data table — {metro_choice} counties"):
    table = sel[["county", "state", "shown_businesses", "shown_reviews", "population",
                 "reviews_per_1k", "median_income"]].rename(columns={
        "county": "County", "state": "State", "shown_businesses": "Businesses",
        "shown_reviews": "Reviews", "population": "Population",
        "reviews_per_1k": "Reviews per 1,000", "median_income": "Median income",
    }).sort_values("Reviews per 1,000", ascending=False)
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"Reviews per 1,000": st.column_config.NumberColumn(format="%.0f"),
                                "Median income": st.column_config.NumberColumn(format="$%d")})

st.caption(
    "Sources: Yelp Open Dataset (business `review_count`); 2018 county population and "
    "median household income (Census / USDA ERS). Edmonton is left out because it has "
    "no US census data."
)
