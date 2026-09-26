"""Phase 2.5 panel/time-series robustness checks.

Preserves the Phase 2 HC3 and category-interaction results and adds only the
pre-specified Bartlett bandwidth-3 Driscoll-Kraay specifications.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from scipy import stats
import statsmodels.formula.api as smf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
ORIGINAL_POOLED_PATH = TABLES_DIR / "regression_pooled.csv"
ORIGINAL_INTERACTION_PATH = TABLES_DIR / "category_interaction_model.csv"

PREDICTORS = ["inflation_yoy", "consumer_confidence"]
OUTCOMES = ["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]
BANDWIDTH = 3
KERNEL = "bartlett"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data = pd.read_csv(DATA_PATH, parse_dates=["date"])
    original = pd.read_csv(ORIGINAL_POOLED_PATH)
    interaction = pd.read_csv(ORIGINAL_INTERACTION_PATH)
    if len(data) != 396 or data.duplicated(["country_code", "date"]).any():
        raise ValueError("Phase 1 master dataset no longer matches the validated 396-row panel")
    expected = {
        ("retail_total_yoy", "inflation_yoy"): -0.04598505175,
        ("retail_total_yoy", "consumer_confidence"): 0.1952942564,
        ("retail_food_yoy", "inflation_yoy"): -0.7859183316,
        ("retail_food_yoy", "consumer_confidence"): -0.006675891905,
        ("retail_nonfood_yoy", "inflation_yoy"): 0.3214251745,
        ("retail_nonfood_yoy", "consumer_confidence"): 0.308959344,
    }
    for (outcome, term), value in expected.items():
        found = original.loc[
            original["outcome"].eq(outcome) & original["term"].eq(term), "coefficient"
        ].iloc[0]
        if not np.isclose(found, value, atol=1e-9):
            raise ValueError(f"Original HC3 result changed for {outcome}/{term}: {found}")
    return data.sort_values(["country_code", "date"]), original, interaction


def transformed_design_diagnostics(sample: pd.DataFrame, time_effects: bool) -> dict[str, float | int]:
    x = sample[PREDICTORS].astype(float)
    entity_mean = sample.groupby("country_code")[PREDICTORS].transform("mean")
    transformed = x - entity_mean
    if time_effects:
        time_mean = sample.groupby("date")[PREDICTORS].transform("mean")
        transformed = x - entity_mean - time_mean + x.mean()
    matrix = transformed.to_numpy()
    return {
        "transformed_design_rank": int(np.linalg.matrix_rank(matrix)),
        "transformed_condition_number": float(np.linalg.cond(matrix)),
        "transformed_sd_inflation": float(transformed["inflation_yoy"].std(ddof=1)),
        "transformed_sd_confidence": float(transformed["consumer_confidence"].std(ddof=1)),
        "transformed_predictor_correlation": float(
            transformed["inflation_yoy"].corr(transformed["consumer_confidence"])
        ),
    }


def stability_classification(
    original_coefficient: float,
    original_ci_lower: float,
    original_ci_upper: float,
    robust_coefficient: float,
    robust_ci_lower: float,
    robust_ci_upper: float,
    identified: bool = True,
) -> str:
    if not identified:
        return "no longer identifiable once common time effects are controlled"
    same_direction = (
        np.sign(original_coefficient) == np.sign(robust_coefficient)
        or abs(original_coefficient) < 0.05
        or abs(robust_coefficient) < 0.05
    )
    tolerance = max(0.10, 0.35 * abs(original_coefficient))
    magnitude_stable = abs(robust_coefficient - original_coefficient) <= tolerance
    original_excludes_zero = original_ci_lower * original_ci_upper > 0
    robust_excludes_zero = robust_ci_lower * robust_ci_upper > 0
    if same_direction and magnitude_stable:
        if original_excludes_zero and not robust_excludes_zero:
            return "direction stable but inference weaker"
        return "direction and magnitude broadly stable"
    return "materially changed"


def fit_panel_models(data: pd.DataFrame, original: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows: list[dict] = []
    models: dict[tuple[str, str], object] = {}
    for outcome in OUTCOMES:
        sample = data[["country_code", "date", outcome, *PREDICTORS]].dropna().copy()
        sample = sample.sort_values(["country_code", "date"])
        panel = sample.set_index(["country_code", "date"])
        for model_label, time_effects in (
            ("Model A: entity FE", False),
            ("Model B: entity + time FE", True),
        ):
            diagnostics = transformed_design_diagnostics(sample, time_effects)
            identified = diagnostics["transformed_design_rank"] == len(PREDICTORS)
            if not identified:
                for term in PREDICTORS:
                    original_row = original.loc[
                        original["outcome"].eq(outcome) & original["term"].eq(term)
                    ].iloc[0]
                    rows.append(
                        {
                            "outcome": outcome,
                            "model": model_label,
                            "term": term,
                            "coefficient": np.nan,
                            "standard_error": np.nan,
                            "ci_lower_95": np.nan,
                            "ci_upper_95": np.nan,
                            "p_value": np.nan,
                            "n": len(sample),
                            "entities": sample["country_code"].nunique(),
                            "time_periods": sample["date"].nunique(),
                            "r_squared": np.nan,
                            "r_squared_within": np.nan,
                            "r_squared_between": np.nan,
                            "r_squared_overall": np.nan,
                            "entity_effects": True,
                            "time_effects": time_effects,
                            "covariance_method": "Driscoll-Kraay",
                            "kernel": KERNEL,
                            "bandwidth": BANDWIDTH,
                            "original_hc3_coefficient": original_row["coefficient"],
                            "coefficient_change_vs_hc3": np.nan,
                            "stability_vs_original_hc3": stability_classification(
                                original_row["coefficient"],
                                original_row["ci_lower_95"],
                                original_row["ci_upper_95"],
                                np.nan,
                                np.nan,
                                np.nan,
                                identified=False,
                            ),
                            **diagnostics,
                        }
                    )
                continue
            model = PanelOLS(
                panel[outcome],
                panel[PREDICTORS],
                entity_effects=True,
                time_effects=time_effects,
                drop_absorbed=False,
                check_rank=True,
            )
            result = model.fit(
                cov_type="kernel", kernel=KERNEL, bandwidth=BANDWIDTH, debiased=True
            )
            models[(outcome, model_label)] = result
            confidence = result.conf_int(level=0.95)
            for term in PREDICTORS:
                original_row = original.loc[
                    original["outcome"].eq(outcome) & original["term"].eq(term)
                ].iloc[0]
                coefficient = result.params[term]
                ci_lower = confidence.loc[term, "lower"]
                ci_upper = confidence.loc[term, "upper"]
                rows.append(
                    {
                        "outcome": outcome,
                        "model": model_label,
                        "term": term,
                        "coefficient": coefficient,
                        "standard_error": result.std_errors[term],
                        "ci_lower_95": ci_lower,
                        "ci_upper_95": ci_upper,
                        "p_value": result.pvalues[term],
                        "n": int(result.nobs),
                        "entities": sample["country_code"].nunique(),
                        "time_periods": sample["date"].nunique(),
                        "r_squared": result.rsquared,
                        "r_squared_within": result.rsquared_within,
                        "r_squared_between": result.rsquared_between,
                        "r_squared_overall": result.rsquared_overall,
                        "entity_effects": True,
                        "time_effects": time_effects,
                        "covariance_method": "Driscoll-Kraay",
                        "kernel": KERNEL,
                        "bandwidth": BANDWIDTH,
                        "original_hc3_coefficient": original_row["coefficient"],
                        "coefficient_change_vs_hc3": coefficient - original_row["coefficient"],
                        "stability_vs_original_hc3": stability_classification(
                            original_row["coefficient"],
                            original_row["ci_lower_95"],
                            original_row["ci_upper_95"],
                            coefficient,
                            ci_lower,
                            ci_upper,
                        ),
                        **diagnostics,
                    }
                )
    table = pd.DataFrame(rows)
    table.to_csv(TABLES_DIR / "regression_panel_robustness.csv", index=False, float_format="%.10g")
    return table, models


def interaction_robustness(
    data: pd.DataFrame, original_interaction: pd.DataFrame
) -> tuple[pd.DataFrame, object]:
    base = data[
        ["country_code", "date", *PREDICTORS, "retail_food_yoy", "retail_nonfood_yoy"]
    ].copy()
    food = base.rename(columns={"retail_food_yoy": "retail_yoy"}).assign(
        category="food", is_nonfood=0
    )
    nonfood = base.rename(columns={"retail_nonfood_yoy": "retail_yoy"}).assign(
        category="nonfood", is_nonfood=1
    )
    keep = ["country_code", "date", *PREDICTORS, "retail_yoy", "category", "is_nonfood"]
    long_data = pd.concat([food[keep], nonfood[keep]], ignore_index=True).dropna()
    long_data = long_data.sort_values(["date", "country_code", "category"]).reset_index(drop=True)
    long_data["time_code"] = pd.factorize(long_data["date"], sort=True)[0]
    formula = (
        "retail_yoy ~ inflation_yoy + consumer_confidence + is_nonfood + "
        "inflation_yoy:is_nonfood + consumer_confidence:is_nonfood + C(country_code)"
    )
    base_result = smf.ols(formula, data=long_data).fit()
    robust = base_result.get_robustcov_results(
        cov_type="hac-groupsum",
        time=long_data["time_code"].to_numpy(),
        maxlags=BANDWIDTH,
        kernel=KERNEL,
        use_correction="hac",
        df_correction=True,
        use_t=False,
    )
    names = list(base_result.params.index)
    covariance = np.asarray(robust.cov_params())
    confidence = np.asarray(robust.conf_int(alpha=0.05))
    rows = []
    requested = ["inflation_yoy:is_nonfood", "consumer_confidence:is_nonfood"]
    combinations = {
        "food_inflation_slope": {"inflation_yoy": 1.0},
        "nonfood_inflation_slope": {
            "inflation_yoy": 1.0,
            "inflation_yoy:is_nonfood": 1.0,
        },
        "food_confidence_slope": {"consumer_confidence": 1.0},
        "nonfood_confidence_slope": {
            "consumer_confidence": 1.0,
            "consumer_confidence:is_nonfood": 1.0,
        },
    }
    for term in requested:
        position = names.index(term)
        original_row = original_interaction.loc[
            original_interaction["term"].eq(term)
            & original_interaction["effect_type"].eq("model_parameter")
        ].iloc[0]
        rows.append(
            {
                "term": term,
                "effect_type": "interaction_parameter",
                "coefficient": robust.params[position],
                "standard_error": robust.bse[position],
                "ci_lower_95": confidence[position, 0],
                "ci_upper_95": confidence[position, 1],
                "p_value": robust.pvalues[position],
                "n": int(robust.nobs),
                "cross_section_series": 6,
                "time_periods": long_data["date"].nunique(),
                "covariance_method": "Driscoll-Kraay (statsmodels hac-groupsum)",
                "kernel": KERNEL,
                "bandwidth": BANDWIDTH,
                "original_clustered_standard_error": original_row["standard_error"],
                "original_clustered_ci_lower_95": original_row["ci_lower_95"],
                "original_clustered_ci_upper_95": original_row["ci_upper_95"],
            }
        )
    for label, terms in combinations.items():
        weights = np.zeros(len(names))
        for term, weight in terms.items():
            weights[names.index(term)] = weight
        estimate = float(weights @ robust.params)
        standard_error = float(np.sqrt(weights @ covariance @ weights))
        z_value = estimate / standard_error
        rows.append(
            {
                "term": label,
                "effect_type": "derived_category_slope",
                "coefficient": estimate,
                "standard_error": standard_error,
                "ci_lower_95": estimate - stats.norm.ppf(0.975) * standard_error,
                "ci_upper_95": estimate + stats.norm.ppf(0.975) * standard_error,
                "p_value": 2 * stats.norm.sf(abs(z_value)),
                "n": int(robust.nobs),
                "cross_section_series": 6,
                "time_periods": long_data["date"].nunique(),
                "covariance_method": "Driscoll-Kraay (statsmodels hac-groupsum)",
                "kernel": KERNEL,
                "bandwidth": BANDWIDTH,
                "original_clustered_standard_error": np.nan,
                "original_clustered_ci_lower_95": np.nan,
                "original_clustered_ci_upper_95": np.nan,
            }
        )
    table = pd.DataFrame(rows)
    table.to_csv(
        TABLES_DIR / "category_interaction_panel_robustness.csv",
        index=False,
        float_format="%.10g",
    )
    return table, robust


def write_manifest(panel_table: pd.DataFrame, interaction_table: pd.DataFrame) -> None:
    manifest = {
        "phase": 2.5,
        "sample": "Unchanged Phase 2 analytical sample: 2016-01 through 2025-12",
        "entities": ["NL", "DE", "FR"],
        "time_periods": 120,
        "bandwidths_tested": [BANDWIDTH],
        "kernel": KERNEL,
        "panel_covariance": "linearmodels PanelOLS Driscoll-Kraay kernel covariance",
        "interaction_covariance": "statsmodels hac-groupsum Driscoll-Kraay covariance",
        "panel_rows": len(panel_table),
        "interaction_rows": len(interaction_table),
        "model_hunting_guardrail": "No alternate bandwidth, predictor, sample, or COVID exclusion was tested",
    }
    (TABLES_DIR / "phase2_5_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def run_robustness() -> dict[str, object]:
    data, original, original_interaction = load_inputs()
    panel_table, panel_models = fit_panel_models(data, original)
    interaction_table, interaction_model = interaction_robustness(data, original_interaction)
    write_manifest(panel_table, interaction_table)
    return {
        "data": data,
        "original": original,
        "panel_table": panel_table,
        "panel_models": panel_models,
        "interaction_table": interaction_table,
        "interaction_model": interaction_model,
    }


if __name__ == "__main__":
    results = run_robustness()
    print(
        "Phase 2.5 robustness complete: "
        f"{len(results['panel_table'])} panel coefficient rows and "
        f"{len(results['interaction_table'])} interaction rows."
    )
