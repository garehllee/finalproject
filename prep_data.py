"""Build the small CSVs the Streamlit app reads.

Reads the Yelp business file straight out of the split archive in dataset/
(yelp_dataset.tar.part_000 ... part_010), matches each business to a US county,
and joins 2018 county population + median household income.

Run once (takes ~1 min):   python prep_data.py
Outputs:
    dataset/processed/county_reviews.csv   one row per county with Yelp businesses
    dataset/processed/metro_reviews.csv    one row per Yelp metro area
"""
import glob
import io
import json
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).parent
DATASET = ROOT / "dataset"
CENSUS = DATASET / "census"
OUT = DATASET / "processed"
COUNTY_GEOJSON_URL = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"

# The 11 metro areas in the Yelp Open Dataset (approximate city centers).
METROS = {
    "Philadelphia": (39.9526, -75.1652),
    "Tampa": (27.9506, -82.4572),
    "Indianapolis": (39.7684, -86.1581),
    "Nashville": (36.1627, -86.7816),
    "Tucson": (32.2226, -110.9747),
    "New Orleans": (29.9511, -90.0715),
    "Reno": (39.5296, -119.8138),
    "St. Louis": (38.6270, -90.1994),
    "Santa Barbara": (34.4208, -119.6982),
    "Boise": (43.6150, -116.2023),
    "Edmonton": (53.5461, -113.4938),  # Canada: no US census data, dropped below
}
MAX_KM_FROM_METRO = 150
MIN_BUSINESSES_PER_COUNTY = 25  # ignore stray counties with a handful of listings


class _Parts(io.RawIOBase):
    """Read the split archive parts as one continuous stream."""

    def __init__(self, paths):
        self.files = [open(p, "rb") for p in paths]
        self.i = 0

    def readable(self):
        return True

    def readinto(self, buf):
        while self.i < len(self.files):
            n = self.files[self.i].readinto(buf)
            if n:
                return n
            self.i += 1
        return 0


def load_businesses() -> pd.DataFrame:
    parts = sorted(glob.glob(str(DATASET / "yelp_dataset.tar.part_*")))
    stream = io.BufferedReader(_Parts(parts), buffer_size=1 << 20)
    with tarfile.open(fileobj=stream, mode="r|gz") as tar:
        for member in tar:
            if member.name.endswith("yelp_academic_dataset_business.json"):
                raw = tar.extractfile(member).read()
                return pd.read_json(io.BytesIO(raw), lines=True)
    raise FileNotFoundError("business json not found in dataset/ archive parts")


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def assign_metro(b: pd.DataFrame) -> pd.DataFrame:
    names = list(METROS)
    dists = np.column_stack(
        [haversine_km(b.latitude, b.longitude, *METROS[m]) for m in names]
    )
    b["metro"] = np.array(names)[dists.argmin(axis=1)]
    b = b[dists.min(axis=1) <= MAX_KM_FROM_METRO]
    return b[b.metro != "Edmonton"].copy()


def assign_county(b: pd.DataFrame) -> pd.DataFrame:
    geo_path = CENSUS / "geojson-counties-fips.json"
    if not geo_path.exists():
        urllib.request.urlretrieve(COUNTY_GEOJSON_URL, geo_path)
    feats = json.loads(geo_path.read_text(encoding="latin-1"))["features"]
    shapes = [shape(f["geometry"]) for f in feats]
    fips = np.array([int(f["id"]) for f in feats])
    tree = STRtree(shapes)
    pts = [Point(xy) for xy in zip(b.longitude, b.latitude)]
    pt_idx, poly_idx = tree.query(pts, predicate="within")
    b["fips"] = pd.NA
    b.iloc[pt_idx, b.columns.get_loc("fips")] = fips[poly_idx]
    bounds = pd.DataFrame(
        [s.bounds for s in shapes], columns=["min_lon", "min_lat", "max_lon", "max_lat"]
    ).assign(fips=fips)
    return b.dropna(subset=["fips"]).astype({"fips": int}), bounds


def main():
    OUT.mkdir(exist_ok=True)
    print("Reading businesses from dataset/ archive ...")
    b = load_businesses()
    b["is_restaurant"] = b.categories.fillna("").str.contains(r"\bRestaurants\b")
    b, bounds = assign_county(assign_metro(b))
    print(f"{len(b):,} US businesses matched to a metro + county")

    census = pd.read_csv(CENSUS / "county_population_income_2018.csv")

    def agg(df):
        return df.groupby(["metro", "fips"]).agg(
            businesses=("business_id", "size"),
            reviews=("review_count", "sum"),
            avg_stars=("stars", "mean"),
            lat=("latitude", "mean"),
            lon=("longitude", "mean"),
        )

    county = agg(b).join(
        agg(b[b.is_restaurant]).add_prefix("restaurant_")[
            ["restaurant_businesses", "restaurant_reviews", "restaurant_avg_stars"]
        ]
    ).reset_index()
    county = county.merge(census, on="fips", how="left").merge(bounds, on="fips", how="left")
    county = county[county.businesses >= MIN_BUSINESSES_PER_COUNTY]
    county[["restaurant_businesses", "restaurant_reviews"]] = (
        county[["restaurant_businesses", "restaurant_reviews"]].fillna(0).astype(int)
    )
    county.to_csv(OUT / "county_reviews.csv", index=False)

    metro = county.groupby("metro").agg(
        counties=("fips", "size"),
        businesses=("businesses", "sum"),
        reviews=("reviews", "sum"),
        restaurant_businesses=("restaurant_businesses", "sum"),
        restaurant_reviews=("restaurant_reviews", "sum"),
        population=("population", "sum"),
    ).reset_index()
    metro["lat"] = metro.metro.map(lambda m: METROS[m][0])
    metro["lon"] = metro.metro.map(lambda m: METROS[m][1])
    metro.to_csv(OUT / "metro_reviews.csv", index=False)
    print(metro.to_string(index=False))


if __name__ == "__main__":
    main()
