"""Build the reader-facing Phase 2.5 robustness notebook."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "02_5_panel_robustness.ipynb"


def code(source: str):
    return nbf.v4.new_code_cell(source)


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source)


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
nb["cells"] = [
    markdown(
        """# Phase 2.5 — Panel robustness checks

**Scope.** This notebook preserves the Phase 2 dataset and estimates. It adds only the pre-specified panel robustness checks for serial and cross-sectional dependence. It does not rebuild the data, perform model selection, create a dashboard, or make causal claims.

**Headline.** With country fixed effects, the original point estimates are unchanged and the food–inflation, total-confidence, and non-food-confidence associations remain distinguishable from zero under Bartlett bandwidth-3 Driscoll–Kraay uncertainty. With both country and month fixed effects, only the negative food–inflation association remains stable; total and non-food estimates materially change. The food/non-food interaction contrasts retain their direction but have wider uncertainty."""
    ),
    markdown(
        """## Method and fixed specification

- Sample: Netherlands, Germany, and France; January 2016–December 2025; 360 country-month observations.
- Outcomes: year-on-year changes in Eurostat real retail-sales volume proxies (total, food, non-food).
- Predictors: headline HICP annual inflation and the Consumer Confidence Indicator.
- Model A: country fixed effects.
- Model B: country and month fixed effects.
- Covariance: Driscoll–Kraay, Bartlett kernel, bandwidth 3. No alternative bandwidths, samples, predictors, or exclusions were tried.
- Interpretation is associational. Retail measures are volume indices, not nominal household expenditure."""
    ),
    code(
        """from pathlib import Path
import sys
import pandas as pd
from IPython.display import display

ROOT = Path.cwd()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from phase2_5_panel_robustness import run_robustness

results = run_robustness()
panel = results["panel_table"].copy()
interaction = results["interaction_table"].copy()
print(f"Master rows: {len(results['data'])}; analytical rows per panel model: {panel['n'].unique().tolist()}")"""
    ),
    markdown("## Model A — country fixed effects with Driscoll–Kraay uncertainty"),
    code(
        """cols = ["outcome", "term", "coefficient", "standard_error", "ci_lower_95", "ci_upper_95", "p_value", "stability_vs_original_hc3"]
display(panel.loc[panel["model"].eq("Model A: entity FE"), cols].round(4))"""
    ),
    markdown(
        """Model A uses the same conditional mean specification as the Phase 2 country-fixed-effects regressions, so its coefficients match exactly. Only the covariance estimator changes. The negative food–inflation estimate remains the strongest result; confidence is positively associated with total and non-food retail growth. Total inflation, food confidence, and non-food inflation remain imprecisely estimated."""
    ),
    markdown("## Model B — country and month fixed effects"),
    code(
        """display(panel.loc[panel["model"].eq("Model B: entity + time FE"), cols].round(4))"""
    ),
    markdown(
        """Month effects remove shocks common to all three countries. Identification therefore comes only from country deviations within each month. Under this demanding comparison, the food–inflation coefficient stays negative and similar in magnitude. The total and non-food coefficients change materially, including reversals for confidence and non-food inflation; their confidence intervals include zero except for total inflation, whose negative estimate is not stable relative to Phase 2."""
    ),
    markdown("## Direct coefficient comparison"),
    code(
        """comparison = panel[["outcome", "model", "term", "original_hc3_coefficient", "coefficient", "coefficient_change_vs_hc3", "stability_vs_original_hc3"]]
display(comparison.round(4))"""
    ),
    markdown("## Identification diagnostics"),
    code(
        """diag_cols = ["model", "transformed_design_rank", "transformed_condition_number", "transformed_sd_inflation", "transformed_sd_confidence", "transformed_predictor_correlation"]
display(panel[diag_cols].drop_duplicates().round(4))"""
    ),
    markdown(
        """Both transformed designs have full rank (2 of 2), and condition numbers are modest. Model B has substantially less usable predictor variation after common month shocks are removed: transformed standard deviations fall from 2.76 to 0.96 for inflation and from 7.51 to 2.80 for confidence. The coefficients are identifiable, but only three countries contribute cross-country deviations in each month, so estimates with month effects should be treated as fragile rather than definitive."""
    ),
    markdown("## Food/non-food interaction robustness"),
    code(
        """display(interaction[["term", "effect_type", "coefficient", "standard_error", "ci_lower_95", "ci_upper_95", "p_value"]].round(4))"""
    ),
    markdown(
        """The interaction coefficients are unchanged by construction because this check replaces only the covariance estimator. Relative to country-month clustered Phase 2 uncertainty, Driscoll–Kraay standard errors rise from 0.229 to 0.410 for inflation×non-food and from 0.073 to 0.115 for confidence×non-food. Both 95% intervals still exclude zero, so the category contrasts survive, but with weaker precision. The derived pattern remains: food growth is negatively associated with inflation, while non-food growth is positively associated with confidence."""
    ),
    markdown(
        """## Phase 2.5 takeaway

The narrow story that survives is **category asymmetry**, especially the negative food–inflation association and the food/non-food contrasts. The broader claim that confidence independently tracks total or non-food retail growth is sensitive to controlling for common monthly shocks and should not be presented as generally robust. Phase 3 may proceed only if it carries these qualifications forward, retains associational language, and treats the three-country time-fixed-effects evidence as limited."""
    ),
]

NOTEBOOK.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, NOTEBOOK)
print(f"Wrote {NOTEBOOK}")

