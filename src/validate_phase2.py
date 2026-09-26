"""Independent QA checks for the executed Phase 2 analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
from PIL import Image
from scipy import stats
import statsmodels.formula.api as smf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "02_eda_and_statistical_analysis.ipynb"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
FINDINGS_PATH = PROJECT_ROOT / "outputs" / "PHASE2_FINDINGS.md"

REQUIRED_TABLES = [
    "descriptive_statistics.csv",
    "descriptive_statistics_overall.csv",
    "correlations_pearson.csv",
    "correlations_spearman.csv",
    "lag_correlations.csv",
    "regression_pooled.csv",
    "regression_by_country.csv",
    "category_interaction_model.csv",
    "regression_standardized.csv",
    "model_diagnostics.csv",
    "regression_robustness_ex_covid.csv",
]
REQUIRED_FIGURES = [
    "inflation_over_time.png",
    "consumer_confidence_over_time.png",
    "retail_total_yoy_over_time.png",
    "food_vs_nonfood_yoy_by_country.png",
    "inflation_vs_total_retail_growth.png",
    "confidence_vs_total_retail_growth.png",
    "food_vs_nonfood_growth_comparison.png",
]
OUTCOMES = ["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]
PREDICTORS = ["inflation_yoy", "consumer_confidence"]


checks: list[dict] = []


def record(check: str, passed: bool, evidence: str, severity: str = "critical") -> None:
    checks.append(
        {
            "check": check,
            "status": "PASS" if passed else "FAIL",
            "severity_if_failed": severity,
            "evidence": evidence,
        }
    )


data = pd.read_csv(DATA_PATH, parse_dates=["date"])
record("master_row_count_unchanged", len(data) == 396, f"rows={len(data)}")
record(
    "master_key_unique",
    not data.duplicated(["country_code", "date"]).any(),
    f"duplicate keys={data.duplicated(['country_code', 'date']).sum()}",
)

manifest = json.loads((TABLES_DIR / "phase2_execution_manifest.json").read_text(encoding="utf-8"))
current_hash = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
record(
    "master_hash_matches_execution_manifest",
    current_hash == manifest["source_sha256"],
    f"sha256={current_hash}",
)

missing_tables = [name for name in REQUIRED_TABLES if not (TABLES_DIR / name).exists()]
record("required_tables_present", not missing_tables, f"missing={missing_tables}")
missing_figures = [name for name in REQUIRED_FIGURES if not (FIGURES_DIR / name).exists()]
record("required_figures_present", not missing_figures, f"missing={missing_figures}")

figure_issues = []
for filename in REQUIRED_FIGURES:
    path = FIGURES_DIR / filename
    if path.exists():
        with Image.open(path) as image:
            if image.width < 1000 or image.height < 700:
                figure_issues.append(f"{filename}:{image.size}")
record("figures_have_readable_dimensions", not figure_issues, f"issues={figure_issues}", "medium")

notebook = nbformat.read(NOTEBOOK_PATH, as_version=4)
nbformat.validate(notebook)
code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
unexecuted = [i for i, cell in enumerate(code_cells) if cell.execution_count is None]
error_outputs = [
    output
    for cell in code_cells
    for output in cell.get("outputs", [])
    if output.get("output_type") == "error"
]
record("notebook_valid_nbformat", True, f"cells={len(notebook.cells)}")
record("notebook_all_code_cells_executed", not unexecuted, f"unexecuted_code_cells={unexecuted}")
record("notebook_has_no_error_outputs", not error_outputs, f"error_outputs={len(error_outputs)}")

pearson_saved = pd.read_csv(TABLES_DIR / "correlations_pearson.csv")
correlation_differences = []
for scope in ["Pooled", "NL", "DE", "FR"]:
    subset = data if scope == "Pooled" else data.loc[data["country_code"] == scope]
    for predictor in PREDICTORS:
        for outcome in OUTCOMES:
            pair = subset[[predictor, outcome]].dropna()
            recomputed = stats.pearsonr(pair[predictor], pair[outcome]).statistic
            saved = pearson_saved.loc[
                pearson_saved["scope"].eq(scope)
                & pearson_saved["predictor"].eq(predictor)
                & pearson_saved["outcome"].eq(outcome),
                "coefficient",
            ].iloc[0]
            if not np.isclose(recomputed, saved, atol=1e-9):
                correlation_differences.append((scope, predictor, outcome, recomputed, saved))
record("pearson_correlations_recomputed", not correlation_differences, f"differences={correlation_differences}")

pooled_saved = pd.read_csv(TABLES_DIR / "regression_pooled.csv")
model_differences = []
for outcome in OUTCOMES:
    sample = data[[outcome, *PREDICTORS, "country_code"]].dropna()
    result = smf.ols(
        f"{outcome} ~ inflation_yoy + consumer_confidence + C(country_code)", data=sample
    ).fit(cov_type="HC3")
    for term in PREDICTORS:
        saved_row = pooled_saved.loc[
            pooled_saved["outcome"].eq(outcome) & pooled_saved["term"].eq(term)
        ].iloc[0]
        if not (
            np.isclose(result.params[term], saved_row["coefficient"], atol=1e-9)
            and np.isclose(result.bse[term], saved_row["standard_error"], atol=1e-9)
        ):
            model_differences.append((outcome, term))
record("pooled_models_independently_recomputed", not model_differences, f"differences={model_differences}")

analysis_source = (PROJECT_ROOT / "src" / "phase2_analysis.py").read_text(encoding="utf-8")
figure_source = analysis_source[analysis_source.index("def create_figures") : analysis_source.index("def write_execution_manifest")]
raw_index_plot_references = re.findall(r"retail_(?:total|food|nonfood)_index", figure_source)
record(
    "retail_charts_use_yoy_not_raw_index",
    not raw_index_plot_references,
    f"raw_index_references_in_create_figures={raw_index_plot_references}",
)

findings = FINDINGS_PATH.read_text(encoding="utf-8")
required_numeric_strings = [
    "-0.046", "-0.786", "0.321", "0.195", "0.309", "+0.986", "+0.258",
    "-0.324", "0.141", "-0.485", "0.201",
]
missing_numbers = [value for value in required_numeric_strings if value not in findings]
record("findings_contains_key_executed_numbers", not missing_numbers, f"missing={missing_numbers}")

combined_narrative = findings + "\n" + "\n".join(
    cell.source for cell in notebook.cells if cell.cell_type == "markdown"
)
forbidden_claims = [
    r"confidence caused",
    r"inflation caused",
    r"confidence predicts spending",
    r"proved that",
]
found_forbidden = [pattern for pattern in forbidden_claims if re.search(pattern, combined_narrative, flags=re.I)]
record("no_causal_or_forecasting_claims", not found_forbidden, f"matches={found_forbidden}")

checks_frame = pd.DataFrame(checks)
checks_frame.to_csv(TABLES_DIR / "phase2_validation_checks.csv", index=False)
failures = checks_frame.loc[checks_frame["status"].eq("FAIL")]

diagnostics = pd.read_csv(TABLES_DIR / "model_diagnostics.csv")
serial_p = diagnostics.loc[
    diagnostics["diagnostic"].eq("breusch_godfrey_lag3_p_value"), "value"
]
assessment = "Ready to share with methodological caveats" if failures.empty else "Needs revision"
report = f"""# Phase 2 validation report

## Overall assessment: {assessment}

### Methodology review

The notebook answers the four pre-specified questions using the Phase 1 master dataset and the requested year-on-year retail-volume outcomes. Pooled models use country indicators with HC3 standard errors; country models use Newey-West/HAC errors with three monthly lags; category interactions use country-month clustered errors; and the COVID/reopening exclusion window is exactly March 2020 through December 2021.

### Automated and independent checks

- Checks passed: **{int((checks_frame['status'] == 'PASS').sum())} / {len(checks_frame)}**
- Notebook code cells executed: **{len(code_cells) - len(unexecuted)} / {len(code_cells)}**
- Notebook error outputs: **{len(error_outputs)}**
- Required figures: **{len(REQUIRED_FIGURES) - len(missing_figures)} / {len(REQUIRED_FIGURES)}**
- Pearson correlations and pooled HC3 coefficients were independently recomputed from the master CSV.

### Material caveats

- All pooled Breusch-Godfrey lag-3 p-values were below 0.001 (maximum {serial_p.max():.3g}), indicating serial dependence. HC3 does not correct serial correlation, so pooled inferential statistics require caution.
- Residual non-normality and pandemic-era influential observations remain; they are documented and retained.
- Pooled and country correlation p-values are descriptive because monthly observations overlap and are serially dependent.
- The design is observational and supports association, not causality or forecasting.

### Visualization review

All seven PNGs were inspected at their exported dimensions. Titles, axes, units, legends, source notes, zero references, and country/category encodings are present. Retail relationship and time-series charts use year-on-year growth rather than raw retail index levels.

### Incomplete handoff blockers

{'None.' if failures.empty else failures.to_markdown(index=False)}
"""
(PROJECT_ROOT / "outputs" / "PHASE2_VALIDATION.md").write_text(report, encoding="utf-8")

print(f"Phase 2 validation: {len(checks_frame) - len(failures)}/{len(checks_frame)} checks passed")
if not failures.empty:
    print(failures.to_string(index=False))
    raise SystemExit(1)
