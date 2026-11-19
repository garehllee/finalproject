"""Sample Yelp reviews for the "What's in a review?" page.

The review file inside dataset/yelp_dataset.tar.part_* is cut off partway (the
archive in the repo is incomplete), so this reads reviews from the start of the
file until it has --limit of them.

Run:  python prep_reviews.py            # 150,000 reviews, ~30 s
Output: dataset/processed/review_sample.csv
"""
import argparse
import glob
import io
import json
import tarfile
from pathlib import Path

import pandas as pd

from prep_data import DATASET, OUT, _Parts

COUNTY_FILE = OUT / "county_reviews.csv"


def read_reviews(limit):
    parts = sorted(glob.glob(str(DATASET / "yelp_dataset.tar.part_*")))
    stream = io.BufferedReader(_Parts(parts), buffer_size=1 << 20)
    rows = []
    with tarfile.open(fileobj=stream, mode="r|gz") as tar:
        for member in tar:
            if not member.name.endswith("yelp_academic_dataset_review.json"):
                continue
            f = tar.extractfile(member)
            try:
                for line in f:
                    r = json.loads(line)
                    rows.append({
                        "review_id": r["review_id"],
                        "business_id": r["business_id"],
                        "stars": int(r["stars"]),
                        "words": len(r["text"].split()),
                        "useful": r["useful"],
                        "funny": r["funny"],
                        "cool": r["cool"],
                        "year": int(r["date"][:4]),
                    })
                    if len(rows) >= limit:
                        break
            except (EOFError, tarfile.ReadError, json.JSONDecodeError):
                pass  # reached the truncated end of the archive
            break
    return pd.DataFrame(rows)


def business_lookup():
    """business_id -> metro + restaurant flag (re-uses prep_data's matching)."""
    from prep_data import assign_metro, load_businesses

    b = load_businesses()
    b["is_restaurant"] = b.categories.fillna("").str.contains(r"\bRestaurants\b")
    b = assign_metro(b)
    return b[["business_id", "metro", "is_restaurant"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=150_000)
    args = ap.parse_args()
    reviews = read_reviews(args.limit)
    reviews = reviews.merge(business_lookup(), on="business_id", how="inner")
    reviews.drop(columns=["review_id", "business_id"]).to_csv(OUT / "review_sample.csv", index=False)
    print(f"Wrote {len(reviews):,} reviews")
    print(reviews.groupby("stars").words.describe().round(0))


if __name__ == "__main__":
    main()
