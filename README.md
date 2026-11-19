# Who leaves Yelp reviews?

Streamlit app with two pages:
- **Reviews vs. population** (`views/reviews_map.py`) – reviews per resident by metro, and a county-level zoom shaded by income.
- **What's in a review?** (`views/review_length.py`) – review length by star rating.

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Data
- `dataset/yelp_dataset.tar.part_*` – the split Yelp Open Dataset archive (source).
- `dataset/census/county_population_income_2018.csv` – 2018 county population + median household income (Census / USDA ERS, via the JieYingWu/COVID-19_US_County-level_Summaries repo).
- `dataset/census/us-10m.json` – US state/county TopoJSON (vega-datasets).
- `dataset/processed/*.csv` – small files the app reads. Rebuild with `python prep_data.py` (streams the business JSON out of the archive parts, matches each business to a county, joins census data).
- `dataset/processed/review_sample.csv` – ~147k reviews read from the start of the (truncated) review file. Rebuild with `python prep_reviews.py`.
