"""Independent validation checks for Phase 2.5 outputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from scipy import stats
import statsmodels.formula.api as smf


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
MASTER = ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
NOTEBOOK = ROOT / "notebooks" / "02_5_panel_robustness.ipynb"
EXPECTED_MASTER_SHA256 = "c6cdd7ca0838af17732bf3539c372df93cadde8fd0ee8289e9934a02c71ab4e7"
OUTCOMES = ["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]
PREDICTORS = ["inflation_yoy", "consumer_confidence"]


checks: list[dict] = []


def check(name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})


data = pd.read_csv(MASTER, parse_dates=["date"])
digest = hashlib.sha256(MASTER.read_bytes()).hexdigest()
check("master_file_unchanged", digest == EXPECTED_MASTER_SHA256, digest)
check("master_grid", len(data) == 396 and not data.duplicated(["country_code", "date"]).any(), f"rows={len(data)}")

required = [
    TABLES / "regression_panel_robustness.csv",
    TABLES / "category_interaction_panel_robustness.csv",
    TABLES / "phase2_5_execution_manifest.json",
    ROOT / "outputs" / "PHASE2_5_ROBUSTNESS.md",
    NOTEBOOK,
]
check("required_outputs_exist", all(path.exists() for path in required), "; ".join(path.name for path in required if not path.exists()) or "all present")

panel = pd.read_csv(TABLES / "regression_panel_robustness.csv")
original = pd.read_csv(TABLES / "regression_pooled.csv")
manifest = json.loads((TABLES / "phase2_5_execution_manifest.json").read_text(encoding="utf-8"))
check("single_prespecified_bandwidth", manifest["bandwidths_tested"] == [3] and manifest["kernel"] == "bartlett", str(manifest["bandwidths_tested"]))
check("panel_output_shape", len(panel) == 12 and panel["n"].eq(360).all(), f"rows={len(panel)}, n={sorted(panel['n'].unique())}")

max_panel_diff = 0.0
max_se_diff = 0.0
for outcome in OUTCOMES:
    sample = data[["country_code", "date", outcome, *PREDICTORS]].dropna().sort_values(["country_code", "date"])
    indexed = sample.set_index(["country_code", "date"])
    for label, time_effects in (("Model A: entity FE", False), ("Model B: entity + time FE", True)):
        fitted = PanelOLS(indexed[outcome], indexed[PREDICTORS], entity_effects=True, time_effects=time_effects).fit(
            cov_type="kernel", kernel="bartlett", bandwidth=3, debiased=True
        )
        saved = panel.loc[panel["outcome"].eq(outcome) & panel["model"].eq(label)].set_index("term")
        max_panel_diff = max(max_panel_diff, float(np.max(np.abs(fitted.params[PREDICTORS] - saved.loc[PREDICTORS, "coefficient"]))))
        max_se_diff = max(max_se_diff, float(np.max(np.abs(fitted.std_errors[PREDICTORS] - saved.loc[PREDICTORS, "standard_error"]))))
check("independent_panel_coefficients", max_panel_diff < 1e-9, f"max_abs_diff={max_panel_diff:.3g}")
check("independent_panel_standard_errors", max_se_diff < 1e-9, f"max_abs_diff={max_se_diff:.3g}")

merged_a = panel.loc[panel["model"].eq("Model A: entity FE")].merge(
    original[["outcome", "term", "coefficient"]], on=["outcome", "term"], suffixes=("_robust", "_original")
)
a_diff = float((merged_a["coefficient_robust"] - merged_a["coefficient_original"]).abs().max())
check("model_a_preserves_phase2_coefficients", a_diff < 1e-9, f"max_abs_diff={a_diff:.3g}")
check("time_fe_design_identified", panel.loc[panel["time_effects"].eq(True), "transformed_design_rank"].eq(2).all(), "rank=2 for all Model B outcomes")

# Independently reconstruct the long interaction model and its Driscoll-Kraay covariance.
base = data[["country_code", "date", *PREDICTORS, "retail_food_yoy", "retail_nonfood_yoy"]]
food = base.rename(columns={"retail_food_yoy": "retail_yoy"}).assign(category="food", is_nonfood=0)
nonfood = base.rename(columns={"retail_nonfood_yoy": "retail_yoy"}).assign(category="nonfood", is_nonfood=1)
keep = ["country_code", "date", *PREDICTORS, "retail_yoy", "category", "is_nonfood"]
long_data = pd.concat([food[keep], nonfood[keep]], ignore_index=True).dropna().sort_values(["date", "country_code", "category"]).reset_index(drop=True)
long_data["time_code"] = pd.factorize(long_data["date"], sort=True)[0]
formula = "retail_yoy ~ inflation_yoy + consumer_confidence + is_nonfood + inflation_yoy:is_nonfood + consumer_confidence:is_nonfood + C(country_code)"
ols = smf.ols(formula, data=long_data).fit()
dk = ols.get_robustcov_results(cov_type="hac-groupsum", time=long_data["time_code"].to_numpy(), maxlags=3, kernel="bartlett", use_correction="hac", df_correction=True, use_t=False)
saved_interaction = pd.read_csv(TABLES / "category_interaction_panel_robustness.csv").set_index("term")
names = list(ols.params.index)
int_terms = ["inflation_yoy:is_nonfood", "consumer_confidence:is_nonfood"]
coef_diff = max(abs(dk.params[names.index(term)] - saved_interaction.loc[term, "coefficient"]) for term in int_terms)
se_diff = max(abs(dk.bse[names.index(term)] - saved_interaction.loc[term, "standard_error"]) for term in int_terms)
check("independent_interaction_coefficients", coef_diff < 1e-9, f"max_abs_diff={coef_diff:.3g}")
check("independent_interaction_standard_errors", se_diff < 1e-9, f"max_abs_diff={se_diff:.3g}")
check("interaction_sample", int(dk.nobs) == 720 and long_data["date"].nunique() == 120, f"n={int(dk.nobs)}, months={long_data['date'].nunique()}")

nb = nbformat.read(NOTEBOOK, as_version=4)
code_cells = [cell for cell in nb.cells if cell.cell_type == "code"]
executed = all(cell.get("execution_count") is not None for cell in code_cells)
errors = [out for cell in code_cells for out in cell.get("outputs", []) if out.get("output_type") == "error"]
check("notebook_executed", executed, f"executed={sum(cell.get('execution_count') is not None for cell in code_cells)}/{len(code_cells)}")
check("notebook_has_no_errors", not errors, f"errors={len(errors)}")

report = (ROOT / "outputs" / "PHASE2_5_ROBUSTNESS.md").read_text(encoding="utf-8")
check("report_records_fixed_specification", "bandwidth 3" in report and "No alternative bandwidth" in report, "Bartlett bandwidth 3 documented")
check("report_uses_associational_language", "causes" not in report.lower() and "causal effect" not in report.lower(), "no causal claim detected")

results = pd.DataFrame(checks)
results.to_csv(TABLES / "phase2_5_validation_checks.csv", index=False)
failed = results.loc[results["status"].eq("FAIL")]
print(results.to_string(index=False))
if not failed.empty:
    raise SystemExit(f"Phase 2.5 validation failed: {failed['check'].tolist()}")
print(f"All {len(results)} Phase 2.5 validation checks passed.")

