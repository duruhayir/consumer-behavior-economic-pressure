# Data sources and selections

Retrieval date: **2026-09-23** (`2026-09-23T19:30:54.763070+00:00` UTC)  
Provider: **Eurostat / European Commission only**  
API: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}`

The exact encoded request URLs, retrieval timestamp (UTC), returned dimensions/sizes, selections, and inspected labels are saved in `data/raw/download_manifest.json`. Short untouched schema probes are also retained in `data/raw/`.

## Retail sales volume

- Dataset: `sts_trtu_m`
- Frequency: `freq=M`
- Indicator: `indic_bt=VOL_SLS` (Volume of sales)
- Unit: `unit=I21` (Index, 2021=100)
- Adjustment: `s_adj=SCA` (seasonally and calendar adjusted)
- NACE Rev. 2:
  - `G47` → `retail_total_index`
  - `G47_FOOD` → `retail_food_index`
  - `G47_NFOOD_X_G473` → `retail_nonfood_index`
- Geography: `geo=NL,DE,FR`
- Time: `2015-01` through `2025-12`

Live schema inspection confirmed dimensions `freq, indic_bt, nace_r2, s_adj, unit, geo, time` and all requested codes. The index is explicitly treated as a real retail-sales **volume proxy**, not nominal expenditure or total household spending.

Official dataset page: https://ec.europa.eu/eurostat/databrowser/view/sts_trtu_m/default/table

Exact extract endpoint:

`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_trtu_m?lang=en&freq=M&indic_bt=VOL_SLS&nace_r2=G47&nace_r2=G47_FOOD&nace_r2=G47_NFOOD_X_G473&s_adj=SCA&unit=I21&geo=NL&geo=DE&geo=FR&sinceTimePeriod=2015-01&untilTimePeriod=2025-12`

## Inflation

- Dataset used: `prc_hicp_minr`
- Frequency: `freq=M`
- Unit: `unit=RCH_A` (annual rate of change, current month versus same month one year earlier)
- Current classification: `coicop18=TOTAL` (Total / all-items headline HICP)
- Geography: `geo=NL,DE,FR`
- Time: `2015-01` through `2025-12`
- Output: `inflation_yoy`

Live schema inspection found dimensions `freq, unit, coicop18, geo, time`. This is a documented schema change from the discontinued historical dataset `prc_hicp_manr`, where all-items used `coicop=CP00`. The historical dataset was discontinued after 2025 and replaced by `prc_hicp_minr`; the replacement cleanly supplies the required 2015–2025 observations, so it is used here.

Official dataset page: https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_minr/default/table

Exact extract endpoint:

`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_minr?lang=en&freq=M&unit=RCH_A&coicop18=TOTAL&geo=NL&geo=DE&geo=FR&sinceTimePeriod=2015-01&untilTimePeriod=2025-12`

## Consumer confidence

- Dataset: `ei_bsco_m`
- Frequency: `freq=M`
- Indicator: `indic=BS-CSMCI` (Consumer confidence indicator)
- Adjustment: `s_adj=SA` (seasonally adjusted, not calendar adjusted)
- Unit: `unit=BAL` (balance)
- Geography: `geo=NL,DE,FR`
- Time: `2015-01` through `2025-12`
- Output: `consumer_confidence`

Live schema inspection confirmed dimensions `freq, indic, s_adj, unit, geo, time` and the exact official Consumer Confidence Indicator. It is not the retail-trade confidence indicator or the broader Economic Sentiment Indicator.

Official dataset page: https://ec.europa.eu/eurostat/databrowser/view/ei_bsco_m/default/table  
Official BCS metadata: https://ec.europa.eu/eurostat/cache/metadata/en/ei_bcs_esms.htm

Exact extract endpoint:

`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ei_bsco_m?lang=en&freq=M&indic=BS-CSMCI&s_adj=SA&unit=BAL&geo=NL&geo=DE&geo=FR&sinceTimePeriod=2015-01&untilTimePeriod=2025-12`

## Reproducibility and source preservation

`src/download_data.py` always validates the live schemas before applying filters. A schema mismatch or unavailable required confidence series causes a hard stop; no substitute sentiment index is used. Bounded responses are stored byte-for-byte as returned by the official API. `src/prepare_data.py` creates the full calendar before merging, and `src/validate_data.py` saves explicit check evidence.
