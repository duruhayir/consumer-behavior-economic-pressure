"""Build the reader-facing Phase 2 notebook with nbformat."""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "02_eda_and_statistical_analysis.ipynb"


def md(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md(
        """
# Consumer Behavior Under Economic Pressure

## TL;DR

Using 360 country-month observations with valid year-on-year retail growth, the evidence is mixed rather than a single inflation story. Pooled inflation correlations were negative for total growth (Pearson **-0.250**, Spearman **-0.365**), but the adjusted total-growth coefficient was close to zero (**-0.046**, 95% CI [-0.342, 0.250]). The clearest inflation result was for food growth (**-0.786**, [-0.981, -0.591]).

Confidence was positively associated with total growth (**0.195**, [0.089, 0.302]) and non-food growth (**0.309**, [0.148, 0.470]) in the pooled adjusted models. The category interaction test found stronger confidence sensitivity for non-food, but inflation was more negatively associated with food—not non-food. Country estimates differed, and COVID/reopening observations materially affected some coefficients. These are observational associations, not causal effects.
"""
    ),
    md(
        """
## 1. Research Questions & Hypotheses

The questions and expectations were fixed before reviewing results:

- **RQ1 / H1:** Is higher inflation associated with weaker real retail-sales volume growth?
- **RQ2 / H2:** Is higher consumer confidence associated with stronger growth?
- **RQ3 / H3:** Is non-food growth more sensitive to inflation and confidence than food growth?
- **RQ4:** Do these relationships differ across the Netherlands, Germany, and France?

H1–H3 are hypotheses to test, not conclusions to prove. Retail measures are Eurostat volume-of-sales indices and therefore real retail-activity proxies—not nominal expenditure or total household consumption.
"""
    ),
    md(
        """
## 2. Analytical Dataset

The Phase 1 master dataset is the source of truth. This notebook does not download, rebuild, impute, or overwrite it. Models use only the pre-specified year-on-year retail-growth outcomes; raw retail index levels are limited to descriptive context.
"""
    ),
    code(
        """
from pathlib import Path
import sys
import pandas as pd
from IPython.display import Image, display

candidate = Path.cwd().resolve()
if not (candidate / "data" / "processed").exists():
    candidate = candidate.parent
PROJECT_ROOT = candidate
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from phase2_analysis import OUTCOMES, PREDICTORS, run_analysis

results = run_analysis()
data = results["data"]

assert len(data) == 396
assert data.duplicated(["country_code", "date"]).sum() == 0
assert all(data[outcome].notna().sum() == 360 for outcome in OUTCOMES)
print(f"Master rows: {len(data)}; countries: {sorted(data.country_code.unique())}")
print(f"Period: {data.date.min().date()} to {data.date.max().date()}")
print(f"Primary outcomes: {OUTCOMES}")
print(f"Primary predictors: {PREDICTORS}")
"""
    ),
    md(
        """
## 3. Descriptive Statistics

The first 12 structural YoY blanks per country are excluded automatically. The overall table and compact country table report valid N, center, spread, quartiles, and range.
"""
    ),
    code(
        """
display(results["descriptive_overall"].round(3))
display(
    results["descriptive_by_country"]
    .loc[:, ["country_code", "variable", "n", "mean", "median", "std", "min", "max"]]
    .round(3)
)
"""
    ),
    md(
        """
## 4. Time-Series Exploration

The shaded window marks March 2020–December 2021 descriptively. Those observations remain in every primary analysis.
"""
    ),
    code(
        """
for filename in [
    "inflation_over_time.png",
    "consumer_confidence_over_time.png",
    "retail_total_yoy_over_time.png",
]:
    display(Image(filename=str(PROJECT_ROOT / "outputs" / "figures" / filename), width=950))
"""
    ),
    md(
        """
## 5. Food vs Non-Food Patterns

Non-food growth is visibly more volatile, particularly during pandemic and reopening months. The shared vertical scale in the small multiples preserves honest cross-country magnitude comparisons.
"""
    ),
    code(
        """
for filename in [
    "food_vs_nonfood_yoy_by_country.png",
    "food_vs_nonfood_growth_comparison.png",
]:
    display(Image(filename=str(PROJECT_ROOT / "outputs" / "figures" / filename), width=950))
"""
    ),
    md(
        """
## 6. Correlation Analysis

Pearson measures linear association; Spearman measures monotonic rank association and is less dominated by extreme magnitudes. Pooled correlations are descriptive because repeated monthly observations are not independent.
"""
    ),
    code(
        """
pearson_compact = results["pearson"].pivot_table(
    index=["scope", "predictor"], columns="outcome", values="coefficient"
).round(3)
spearman_compact = results["spearman"].pivot_table(
    index=["scope", "predictor"], columns="outcome", values="coefficient"
).round(3)
display(pearson_compact.style.set_caption("Pearson correlations"))
display(spearman_compact.style.set_caption("Spearman correlations"))

for filename in ["inflation_vs_total_retail_growth.png", "confidence_vs_total_retail_growth.png"]:
    display(Image(filename=str(PROJECT_ROOT / "outputs" / "figures" / filename), width=800))
"""
    ),
    md(
        """
## 7. Lag Analysis

Lag 0–3 associations are exploratory and all are retained. A stronger lag is not presented as pre-specified or predictive.
"""
    ),
    code(
        """
pooled_lags = results["lags"].loc[
    results["lags"]["scope"].eq("Pooled"),
    ["predictor", "lag_months", "outcome", "n", "pearson_r", "spearman_rho"],
]
country_total_lags = results["lags"].loc[
    results["lags"]["scope"].ne("Pooled") & results["lags"]["outcome"].eq("retail_total_yoy"),
    ["scope", "predictor", "lag_months", "n", "pearson_r", "spearman_rho"],
]
display(pooled_lags.round(3))
display(country_total_lags.round(3))
print("Complete country x outcome x lag results: outputs/tables/lag_correlations.csv")
"""
    ),
    md(
        """
## 8. Primary Regression Models

Each pooled model estimates retail YoY growth on contemporaneous inflation and confidence plus country indicators. HC3 standard errors follow the pre-specified design. Coefficients remain associational.
"""
    ),
    code(
        """
pooled_primary = results["pooled_table"].loc[
    results["pooled_table"]["term"].isin(PREDICTORS),
    ["outcome", "term", "coefficient", "standard_error", "ci_lower_95", "ci_upper_95", "p_value", "n", "r_squared", "adjusted_r_squared"],
]
display(pooled_primary.round(4))

standardized = results["standardized_table"].loc[
    results["standardized_table"]["term"].isin(["z_inflation_yoy", "z_consumer_confidence"]),
    ["outcome", "term", "coefficient", "ci_lower_95", "ci_upper_95"],
]
display(standardized.round(3).style.set_caption("Secondary models: predictors standardized, outcomes in percentage points"))
"""
    ),
    md(
        """
## 9. Country-Level Results

Separate country models use Newey-West/HAC standard errors with `maxlags=3`. Coefficient differences are compared descriptively rather than used to rank countries.
"""
    ),
    code(
        """
country_primary = results["country_table"].loc[
    results["country_table"]["term"].isin(PREDICTORS),
    ["scope", "outcome", "term", "coefficient", "standard_error", "ci_lower_95", "ci_upper_95", "p_value", "n", "r_squared"],
]
display(country_primary.round(4))
"""
    ),
    md(
        """
## 10. Food vs Non-Food Interaction Test

The long-format model contains paired food and non-food observations for each country-month. Standard errors are clustered at country-month level. Interaction coefficients directly test whether slopes differ by category.
"""
    ),
    code(
        """
interaction_terms = [
    "inflation_yoy:is_nonfood", "consumer_confidence:is_nonfood",
    "food_inflation_slope", "nonfood_inflation_slope",
    "food_confidence_slope", "nonfood_confidence_slope",
]
interaction_display = results["interaction_table"].loc[
    results["interaction_table"]["term"].isin(interaction_terms),
    ["term", "effect_type", "coefficient", "standard_error", "ci_lower_95", "ci_upper_95", "p_value", "category_observations", "country_month_clusters"],
]
display(interaction_display.round(4))
"""
    ),
    md(
        """
## 11. Model Diagnostics

Diagnostics examine residual shape, heteroskedasticity, serial dependence, multicollinearity, and influence. Extreme observations are documented—not automatically removed.
"""
    ),
    code(
        """
diagnostic_focus = results["diagnostics"].loc[
    results["diagnostics"]["diagnostic"].isin([
        "jarque_bera_p_value", "breusch_pagan_p_value", "durbin_watson",
        "breusch_godfrey_lag3_p_value", "max_cooks_distance",
        "count_cooks_gt_4_over_n", "vif_inflation_yoy", "vif_consumer_confidence",
    ])
]
display(diagnostic_focus.pivot(index="diagnostic", columns="outcome", values="value").round(4))
"""
    ),
    md(
        """
## 12. Robustness Check

The pre-specified robustness check excludes March 2020–December 2021, but does not replace the primary models. The table compares full and exclusion samples transparently.
"""
    ),
    code(
        """
pooled_robustness = results["robustness"].loc[
    results["robustness"]["scope"].eq("Pooled"),
    ["sample", "outcome", "term", "coefficient", "ci_lower_95", "ci_upper_95", "n", "r_squared"],
]
display(pooled_robustness.round(4))
print("Full pooled and country-specific robustness results: outputs/tables/regression_robustness_ex_covid.csv")
"""
    ),
    md(
        """
## 13. Key Findings

1. **H1 was only partly supported.** Inflation had a clear negative adjusted association with food growth (-0.786 pp per one-point inflation increase), but not with total or non-food growth in the pooled model.
2. **H2 was supported for total and non-food.** Confidence coefficients were 0.195 pp for total and 0.309 pp for non-food growth, while the adjusted food coefficient was near zero.
3. **H3 was mixed.** Non-food was more volatile and more confidence-sensitive, but food—not non-food—had the stronger negative inflation slope.
4. **Country estimates differed.** Germany showed the clearest negative full-sample inflation coefficient for total growth; positive total-confidence coefficients were clearest in the Netherlands and France.
5. **Timing evidence is exploratory.** Inflation correlations with pooled total growth became more negative through lag 3, while confidence associations were generally strongest contemporaneously.
6. **Core pooled signs survived the COVID exclusion**, but food-confidence and several country coefficients changed, showing that exceptional observations matter.
"""
    ),
    md(
        """
## 14. Limitations

- Observational associations cannot establish causality.
- Retail sales volume is not total household consumption or nominal expenditure.
- Only three countries are included.
- Confidence and retail activity may influence each other.
- Omitted macroeconomic variables and common European shocks remain.
- COVID/reopening months are exceptional but retained in primary models.
- Overlapping annual growth rates create serial dependence; pooled HC3 errors do not correct it.
- Category definitions are broad, and this sample may not generalize to all economic environments.
- Correlation p-values assume more independence than the monthly time-series structure provides and are therefore secondary to magnitude and consistency.
"""
    ),
    md(
        """
## 15. Implications for Phase 3

The analysis is coherent enough to support a dashboard and final report if they preserve uncertainty and mixed evidence. Phase 3 should foreground the negative inflation–food relationship, positive confidence relationships with total/non-food growth, cross-country heterogeneity, and pandemic sensitivity. It should not collapse the results into a causal claim or a single “economic pressure” score.

Phase 2 stops here; no dashboard, final portfolio report, presentation, machine-learning model, or forecast is created.
"""
    ),
]

notebook = nbf.v4.new_notebook(
    cells=cells,
    metadata={
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.13"},
    },
)
NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, NOTEBOOK_PATH)
print(f"Wrote {NOTEBOOK_PATH}")
