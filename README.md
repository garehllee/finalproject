# Who leaves Yelp reviews?

Streamlit app comparing Yelp review counts to population (and income) across the 10 US metros in the Yelp Open Dataset.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Data
- `dataset/yelp_dataset.tar.part_*` – the split Yelp Open Dataset archive (source).
- `dataset/census/county_population_income_2018.csv` – 2018 county population + median household income (Census / USDA ERS, via the JieYingWu/COVID-19_US_County-level_Summaries repo).
- `dataset/census/us-10m.json` – US state/county TopoJSON (vega-datasets).
- `dataset/processed/*.csv` – small files the app reads. Rebuild with `python prep_data.py` (streams the business JSON out of the archive parts, matches each business to a county, joins census data).
