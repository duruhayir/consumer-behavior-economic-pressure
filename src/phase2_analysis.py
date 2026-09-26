"""Phase 2 exploratory and statistical analysis.

This module keeps the analytical choices explicit and deterministic. It does not
modify the Phase 1 master dataset and does not make causal or forecasting claims.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path

_EARLY_PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(_EARLY_PROJECT_ROOT / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy import stats
import statsmodels
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson, jarque_bera


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

PREDICTORS = ["inflation_yoy", "consumer_confidence"]
OUTCOMES = ["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]
COUNTRY_ORDER = ["NL", "DE", "FR"]
COUNTRY_NAMES = {"NL": "Netherlands", "DE": "Germany", "FR": "France"}
COUNTRY_COLORS = {"NL": "#2F6B8A", "DE": "#D4A72C", "FR": "#C95A7B"}
COUNTRY_LINESTYLES = {"NL": "-", "DE": "--", "FR": "-."}
CATEGORY_COLORS = {"Food": "#7A8B3A", "Non-food": "#D97732"}
SOURCE_NOTE = (
    "Source: Eurostat / European Commission; author calculations. "
    "Retail measures are real retail-sales volume proxies."
)


FIGURE_CONTRACTS = {
    "inflation_over_time.png": "Trend | 396 country-months | percentage points | country color + line style",
    "consumer_confidence_over_time.png": "Trend | 396 country-months | balance | country color + line style",
    "retail_total_yoy_over_time.png": "Trend | 360 analytical observations | percent YoY | country color + line style",
    "food_vs_nonfood_yoy_by_country.png": "Small-multiple trend | 720 category observations | percent YoY | category color + line style",
    "inflation_vs_total_retail_growth.png": "Scatter | 360 country-months | country color + marker | fitted lines descriptive only",
    "confidence_vs_total_retail_growth.png": "Scatter | 360 country-months | country color + marker | fitted lines descriptive only",
    "food_vs_nonfood_growth_comparison.png": "Scatter | 360 country-months | country color + marker | 45-degree reference",
}


def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH, parse_dates=["date"])
    expected_columns = {
        "country_code",
        "country",
        "date",
        *PREDICTORS,
        *OUTCOMES,
        "retail_total_index",
        "retail_food_index",
        "retail_nonfood_index",
        "consumer_confidence_lag1",
        "consumer_confidence_lag2",
        "consumer_confidence_lag3",
        "inflation_lag1",
        "inflation_lag2",
        "inflation_lag3",
    }
    missing = expected_columns - set(data.columns)
    if missing:
        raise ValueError(f"Phase 1 master dataset is missing columns: {sorted(missing)}")
    if len(data) != 396:
        raise ValueError(f"Expected 396 master rows, found {len(data)}")
    if data.duplicated(["country_code", "date"]).any():
        raise ValueError("Duplicate country-date rows found in Phase 1 master dataset")
    return data.sort_values(["country_code", "date"]).reset_index(drop=True)


def _save_table(frame: pd.DataFrame, filename: str) -> pd.DataFrame:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES_DIR / filename, index=False, float_format="%.10g")
    return frame


def descriptive_statistics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    variables = PREDICTORS + OUTCOMES
    rows = []
    for country_code in COUNTRY_ORDER:
        subset = data.loc[data["country_code"] == country_code]
        for variable in variables:
            series = subset[variable].dropna()
            rows.append(
                {
                    "country_code": country_code,
                    "country": COUNTRY_NAMES[country_code],
                    "variable": variable,
                    "n": int(series.count()),
                    "mean": series.mean(),
                    "median": series.median(),
                    "std": series.std(ddof=1),
                    "min": series.min(),
                    "p25": series.quantile(0.25),
                    "p75": series.quantile(0.75),
                    "max": series.max(),
                }
            )
    by_country = _save_table(pd.DataFrame(rows), "descriptive_statistics.csv")

    overall_rows = []
    for variable in variables:
        series = data[variable].dropna()
        overall_rows.append(
            {
                "scope": "Pooled descriptive",
                "variable": variable,
                "n": int(series.count()),
                "mean": series.mean(),
                "median": series.median(),
                "std": series.std(ddof=1),
                "min": series.min(),
                "p25": series.quantile(0.25),
                "p75": series.quantile(0.75),
                "max": series.max(),
            }
        )
    overall = _save_table(pd.DataFrame(overall_rows), "descriptive_statistics_overall.csv")
    return by_country, overall


def correlation_table(data: pd.DataFrame, method: str) -> pd.DataFrame:
    rows = []
    scopes = [("Pooled", data)] + [
        (country_code, data.loc[data["country_code"] == country_code])
        for country_code in COUNTRY_ORDER
    ]
    for scope, subset in scopes:
        for predictor in PREDICTORS:
            for outcome in OUTCOMES:
                pair = subset[[predictor, outcome]].dropna()
                if method == "pearson":
                    result = stats.pearsonr(pair[predictor], pair[outcome])
                elif method == "spearman":
                    result = stats.spearmanr(pair[predictor], pair[outcome])
                else:
                    raise ValueError(method)
                rows.append(
                    {
                        "scope": scope,
                        "predictor": predictor,
                        "outcome": outcome,
                        "method": method,
                        "coefficient": result.statistic,
                        "p_value": result.pvalue,
                        "n": len(pair),
                    }
                )
    filename = f"correlations_{method}.csv"
    return _save_table(pd.DataFrame(rows), filename)


def lag_correlations(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    predictor_roots = {
        "inflation": {0: "inflation_yoy", 1: "inflation_lag1", 2: "inflation_lag2", 3: "inflation_lag3"},
        "consumer_confidence": {
            0: "consumer_confidence",
            1: "consumer_confidence_lag1",
            2: "consumer_confidence_lag2",
            3: "consumer_confidence_lag3",
        },
    }
    scopes = [("Pooled", data)] + [
        (country_code, data.loc[data["country_code"] == country_code])
        for country_code in COUNTRY_ORDER
    ]
    for scope, subset in scopes:
        for predictor, lag_columns in predictor_roots.items():
            for lag, column in lag_columns.items():
                for outcome in OUTCOMES:
                    pair = subset[[column, outcome]].dropna()
                    pearson = stats.pearsonr(pair[column], pair[outcome])
                    spearman = stats.spearmanr(pair[column], pair[outcome])
                    rows.append(
                        {
                            "scope": scope,
                            "predictor": predictor,
                            "lag_months": lag,
                            "predictor_column": column,
                            "outcome": outcome,
                            "n": len(pair),
                            "pearson_r": pearson.statistic,
                            "pearson_p_value": pearson.pvalue,
                            "spearman_rho": spearman.statistic,
                            "spearman_p_value": spearman.pvalue,
                        }
                    )
    return _save_table(pd.DataFrame(rows), "lag_correlations.csv")


def _tidy_model(result, model_name: str, outcome: str, scope: str, covariance: str) -> pd.DataFrame:
    confidence = result.conf_int(alpha=0.05)
    return pd.DataFrame(
        {
            "model": model_name,
            "scope": scope,
            "outcome": outcome,
            "term": result.params.index,
            "coefficient": result.params.values,
            "standard_error": result.bse.values,
            "ci_lower_95": confidence.iloc[:, 0].values,
            "ci_upper_95": confidence.iloc[:, 1].values,
            "p_value": result.pvalues.values,
            "n": int(result.nobs),
            "r_squared": result.rsquared,
            "adjusted_r_squared": result.rsquared_adj,
            "covariance": covariance,
        }
    )


def pooled_regressions(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    tables = []
    models = {}
    for outcome in OUTCOMES:
        formula = f"{outcome} ~ inflation_yoy + consumer_confidence + C(country_code)"
        sample = data[[outcome, *PREDICTORS, "country_code"]].dropna()
        result = smf.ols(formula, data=sample).fit(cov_type="HC3")
        models[outcome] = result
        tables.append(_tidy_model(result, "Pooled country-FE OLS", outcome, "Pooled", "HC3"))
    table = _save_table(pd.concat(tables, ignore_index=True), "regression_pooled.csv")
    return table, models


def country_regressions(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[str, str], object]]:
    tables = []
    models = {}
    for country_code in COUNTRY_ORDER:
        country_data = data.loc[data["country_code"] == country_code]
        for outcome in OUTCOMES:
            formula = f"{outcome} ~ inflation_yoy + consumer_confidence"
            sample = country_data[[outcome, *PREDICTORS]].dropna()
            result = smf.ols(formula, data=sample).fit(
                cov_type="HAC", cov_kwds={"maxlags": 3, "use_correction": True}
            )
            models[(country_code, outcome)] = result
            tables.append(
                _tidy_model(
                    result,
                    "Country OLS",
                    outcome,
                    country_code,
                    "Newey-West HAC maxlags=3",
                )
            )
    table = _save_table(pd.concat(tables, ignore_index=True), "regression_by_country.csv")
    return table, models


def category_interaction_model(data: pd.DataFrame) -> tuple[pd.DataFrame, object, pd.DataFrame]:
    base = data[["country_code", "date", *PREDICTORS, "retail_food_yoy", "retail_nonfood_yoy"]].copy()
    food = base.rename(columns={"retail_food_yoy": "retail_yoy"}).assign(category="food", is_nonfood=0)
    nonfood = base.rename(columns={"retail_nonfood_yoy": "retail_yoy"}).assign(category="nonfood", is_nonfood=1)
    keep = ["country_code", "date", *PREDICTORS, "retail_yoy", "category", "is_nonfood"]
    long_data = pd.concat([food[keep], nonfood[keep]], ignore_index=True).dropna()
    long_data["country_month_cluster"] = (
        long_data["country_code"] + "_" + long_data["date"].dt.strftime("%Y-%m")
    )
    formula = (
        "retail_yoy ~ inflation_yoy + consumer_confidence + is_nonfood + "
        "inflation_yoy:is_nonfood + consumer_confidence:is_nonfood + C(country_code)"
    )
    result = smf.ols(formula, data=long_data).fit(
        cov_type="cluster",
        cov_kwds={"groups": long_data["country_month_cluster"], "use_correction": True},
    )
    table = _tidy_model(
        result,
        "Food/non-food interaction OLS",
        "retail_yoy",
        "Pooled long format",
        "Clustered by country-month",
    )
    table["effect_type"] = "model_parameter"
    derived_rows = []
    combinations = {
        "food_inflation_slope": {"inflation_yoy": 1.0},
        "nonfood_inflation_slope": {"inflation_yoy": 1.0, "inflation_yoy:is_nonfood": 1.0},
        "food_confidence_slope": {"consumer_confidence": 1.0},
        "nonfood_confidence_slope": {
            "consumer_confidence": 1.0,
            "consumer_confidence:is_nonfood": 1.0,
        },
    }
    covariance = np.asarray(result.cov_params())
    parameter_names = list(result.params.index)
    for label, terms in combinations.items():
        weights = np.zeros(len(parameter_names))
        for term, weight in terms.items():
            weights[parameter_names.index(term)] = weight
        estimate = float(weights @ result.params.values)
        standard_error = float(np.sqrt(weights @ covariance @ weights))
        z_value = estimate / standard_error
        derived_rows.append(
            {
                "model": "Food/non-food interaction OLS",
                "scope": "Pooled long format",
                "outcome": "retail_yoy",
                "term": label,
                "coefficient": estimate,
                "standard_error": standard_error,
                "ci_lower_95": estimate - stats.norm.ppf(0.975) * standard_error,
                "ci_upper_95": estimate + stats.norm.ppf(0.975) * standard_error,
                "p_value": 2 * stats.norm.sf(abs(z_value)),
                "n": int(result.nobs),
                "r_squared": result.rsquared,
                "adjusted_r_squared": result.rsquared_adj,
                "covariance": "Clustered by country-month",
                "effect_type": "derived_category_slope",
            }
        )
    table = pd.concat([table, pd.DataFrame(derived_rows)], ignore_index=True)
    table["category_observations"] = len(long_data)
    table["country_month_clusters"] = long_data["country_month_cluster"].nunique()
    _save_table(table, "category_interaction_model.csv")
    return table, result, long_data


def standardized_regressions(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    analytical = data.dropna(subset=PREDICTORS + OUTCOMES).copy()
    for predictor in PREDICTORS:
        analytical[f"z_{predictor}"] = (
            analytical[predictor] - analytical[predictor].mean()
        ) / analytical[predictor].std(ddof=1)
    tables = []
    models = {}
    for outcome in OUTCOMES:
        formula = (
            f"{outcome} ~ z_inflation_yoy + z_consumer_confidence + C(country_code)"
        )
        result = smf.ols(formula, data=analytical).fit(cov_type="HC3")
        models[outcome] = result
        tables.append(
            _tidy_model(
                result,
                "Pooled country-FE OLS with standardized predictors",
                outcome,
                "Pooled",
                "HC3",
            )
        )
    table = pd.concat(tables, ignore_index=True)
    table["standardization_note"] = "Predictors standardized across the 360-row pooled analytical sample; outcomes remain percentage points"
    return _save_table(table, "regression_standardized.csv"), models


def model_diagnostics(data: pd.DataFrame, pooled_models: dict[str, object]) -> pd.DataFrame:
    rows = []
    for outcome, result in pooled_models.items():
        residuals = np.asarray(result.resid)
        exog = np.asarray(result.model.exog)
        jb_stat, jb_p, skew, kurtosis = jarque_bera(residuals)
        bp_lm, bp_lm_p, bp_f, bp_f_p = het_breuschpagan(residuals, exog)
        bg_lm, bg_lm_p, bg_f, bg_f_p = acorr_breusch_godfrey(
            result, nlags=3, result_object=False
        )
        influence = result.get_influence()
        cooks = influence.cooks_distance[0]
        studentized = influence.resid_studentized_external
        max_pos = int(np.nanargmax(cooks))
        row_label = result.model.data.row_labels[max_pos]
        influential_row = data.loc[row_label]
        metric_values = [
            ("residual_skew", skew, "0 indicates symmetry"),
            ("residual_kurtosis", kurtosis, "3 is normal-reference kurtosis"),
            ("jarque_bera_p_value", jb_p, "small values indicate non-normal residuals"),
            ("breusch_pagan_p_value", bp_lm_p, "small values indicate heteroskedasticity"),
            ("durbin_watson", durbin_watson(residuals), "2 is no first-order autocorrelation reference"),
            ("breusch_godfrey_lag3_p_value", bg_lm_p, "small values indicate serial correlation through lag 3"),
            ("max_cooks_distance", cooks[max_pos], "inspect rather than automatically delete influential observations"),
            ("count_cooks_gt_4_over_n", int((cooks > 4 / len(cooks)).sum()), "heuristic influence count"),
            ("max_abs_external_studentized_residual", float(np.nanmax(np.abs(studentized))), "large absolute values flag extremes"),
        ]
        for metric, value, interpretation in metric_values:
            details = interpretation
            if metric == "max_cooks_distance":
                details += f"; max at {influential_row['country_code']} {influential_row['date'].date()}"
            rows.append(
                {
                    "model": "Pooled country-FE OLS",
                    "outcome": outcome,
                    "diagnostic": metric,
                    "value": value,
                    "reference": details,
                }
            )
        exog_names = result.model.exog_names
        for predictor in PREDICTORS:
            position = exog_names.index(predictor)
            rows.append(
                {
                    "model": "Pooled country-FE OLS",
                    "outcome": outcome,
                    "diagnostic": f"vif_{predictor}",
                    "value": variance_inflation_factor(exog, position),
                    "reference": "VIF near 1 is low; values above 5 merit concern",
                }
            )
    return _save_table(pd.DataFrame(rows), "model_diagnostics.csv")


def covid_robustness(data: pd.DataFrame) -> pd.DataFrame:
    exclusion_start = pd.Timestamp("2020-03-01")
    exclusion_end = pd.Timestamp("2021-12-01")
    ex_covid = data.loc[~data["date"].between(exclusion_start, exclusion_end)].copy()
    rows = []
    for sample_name, sample_data in (("Primary full sample", data), ("Excluding 2020-03 to 2021-12", ex_covid)):
        for outcome in OUTCOMES:
            pooled_sample = sample_data[[outcome, *PREDICTORS, "country_code"]].dropna()
            pooled = smf.ols(
                f"{outcome} ~ inflation_yoy + consumer_confidence + C(country_code)",
                data=pooled_sample,
            ).fit(cov_type="HC3")
            tidy = _tidy_model(pooled, "Pooled country-FE OLS", outcome, "Pooled", "HC3")
            tidy = tidy.loc[tidy["term"].isin(PREDICTORS)].copy()
            tidy.insert(0, "sample", sample_name)
            rows.append(tidy)
            for country_code in COUNTRY_ORDER:
                country_sample = sample_data.loc[sample_data["country_code"] == country_code]
                country_sample = country_sample[[outcome, *PREDICTORS]].dropna()
                result = smf.ols(
                    f"{outcome} ~ inflation_yoy + consumer_confidence", data=country_sample
                ).fit(cov_type="HAC", cov_kwds={"maxlags": 3, "use_correction": True})
                tidy = _tidy_model(
                    result,
                    "Country OLS",
                    outcome,
                    country_code,
                    "Newey-West HAC maxlags=3",
                )
                tidy = tidy.loc[tidy["term"].isin(PREDICTORS)].copy()
                tidy.insert(0, "sample", sample_name)
                rows.append(tidy)
    return _save_table(pd.concat(rows, ignore_index=True), "regression_robustness_ex_covid.csv")


def _style_axes(ax: plt.Axes, zero_line: bool = False) -> None:
    ax.grid(axis="y", color="#D9DEE3", linewidth=0.7, alpha=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#67727E")
    if zero_line:
        ax.axhline(0, color="#30363D", linewidth=0.8, alpha=0.8)


def _add_source_note(fig: plt.Figure) -> None:
    fig.text(0.01, 0.008, SOURCE_NOTE, ha="left", va="bottom", fontsize=8, color="#5E6770")


def _save_figure(fig: plt.Figure, filename: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    _add_source_note(fig)
    fig.savefig(FIGURES_DIR / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _time_series_plot(data: pd.DataFrame, column: str, title: str, ylabel: str, filename: str, zero_line: bool = False) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    for code in COUNTRY_ORDER:
        subset = data.loc[data["country_code"] == code]
        ax.plot(
            subset["date"],
            subset[column],
            label=COUNTRY_NAMES[code],
            color=COUNTRY_COLORS[code],
            linestyle=COUNTRY_LINESTYLES[code],
            linewidth=1.8,
        )
    ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-12-01"), color="#ADB5BD", alpha=0.13)
    ax.text(pd.Timestamp("2020-04-01"), ax.get_ylim()[1], "COVID/reopening window", va="top", fontsize=8, color="#5E6770")
    ax.set_title(title, loc="left", fontsize=14, weight="bold")
    ax.set_xlabel("Month")
    ax.set_ylabel(ylabel)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(frameon=False, ncol=3, loc="upper left")
    _style_axes(ax, zero_line=zero_line)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save_figure(fig, filename)


def create_figures(data: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titlesize": 14,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    _time_series_plot(
        data,
        "inflation_yoy",
        "Headline HICP inflation over time, 2015-2025",
        "Annual inflation rate (%)",
        "inflation_over_time.png",
    )
    _time_series_plot(
        data,
        "consumer_confidence",
        "Consumer confidence over time, 2015-2025",
        "Consumer Confidence Indicator (balance)",
        "consumer_confidence_over_time.png",
        zero_line=True,
    )
    _time_series_plot(
        data,
        "retail_total_yoy",
        "Total real retail-sales volume growth, 2016-2025",
        "Year-on-year growth (%)",
        "retail_total_yoy_over_time.png",
        zero_line=True,
    )

    fig, axes = plt.subplots(3, 1, figsize=(11, 10.5), sharex=True, sharey=True)
    for ax, code in zip(axes, COUNTRY_ORDER):
        subset = data.loc[data["country_code"] == code]
        ax.plot(subset["date"], subset["retail_food_yoy"], color=CATEGORY_COLORS["Food"], label="Food", linewidth=1.6)
        ax.plot(
            subset["date"], subset["retail_nonfood_yoy"], color=CATEGORY_COLORS["Non-food"],
            linestyle="--", label="Non-food excluding automotive fuel", linewidth=1.6
        )
        ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-12-01"), color="#ADB5BD", alpha=0.13)
        ax.set_title(COUNTRY_NAMES[code], loc="left", fontsize=11, weight="bold")
        ax.set_ylabel("YoY growth (%)")
        _style_axes(ax, zero_line=True)
    axes[0].legend(frameon=False, ncol=2, loc="upper left")
    axes[-1].set_xlabel("Month")
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("Food and non-food real retail-sales volume growth", x=0.07, ha="left", fontsize=14, weight="bold")
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    _save_figure(fig, "food_vs_nonfood_yoy_by_country.png")

    markers = {"NL": "o", "DE": "s", "FR": "^"}
    for predictor, x_label, title, filename in (
        (
            "inflation_yoy",
            "Annual HICP inflation rate (%)",
            "Inflation and total real retail-sales volume growth",
            "inflation_vs_total_retail_growth.png",
        ),
        (
            "consumer_confidence",
            "Consumer Confidence Indicator (balance)",
            "Consumer confidence and total real retail-sales volume growth",
            "confidence_vs_total_retail_growth.png",
        ),
    ):
        fig, ax = plt.subplots(figsize=(8.2, 6.2))
        for code in COUNTRY_ORDER:
            subset = data.loc[data["country_code"] == code, [predictor, "retail_total_yoy"]].dropna()
            ax.scatter(
                subset[predictor], subset["retail_total_yoy"], s=28, alpha=0.55,
                color=COUNTRY_COLORS[code], marker=markers[code], label=COUNTRY_NAMES[code]
            )
            slope, intercept = np.polyfit(subset[predictor], subset["retail_total_yoy"], 1)
            x_values = np.linspace(subset[predictor].min(), subset[predictor].max(), 100)
            ax.plot(x_values, intercept + slope * x_values, color=COUNTRY_COLORS[code], linestyle=COUNTRY_LINESTYLES[code], linewidth=1.5)
        ax.set_title(title, loc="left", fontsize=14, weight="bold")
        ax.set_xlabel(x_label)
        ax.set_ylabel("Total retail-volume growth (% YoY)")
        ax.legend(frameon=False, ncol=3, loc="upper left")
        _style_axes(ax, zero_line=True)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        _save_figure(fig, filename)

    fig, ax = plt.subplots(figsize=(8.2, 6.4))
    for code in COUNTRY_ORDER:
        subset = data.loc[data["country_code"] == code, ["retail_food_yoy", "retail_nonfood_yoy"]].dropna()
        ax.scatter(
            subset["retail_food_yoy"], subset["retail_nonfood_yoy"], s=30, alpha=0.55,
            color=COUNTRY_COLORS[code], marker=markers[code], label=COUNTRY_NAMES[code]
        )
    limits = [
        min(data["retail_food_yoy"].min(), data["retail_nonfood_yoy"].min()),
        max(data["retail_food_yoy"].max(), data["retail_nonfood_yoy"].max()),
    ]
    ax.plot(limits, limits, color="#30363D", linestyle="--", linewidth=1.1, label="Equal growth reference")
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_title("Food and non-food real retail-sales volume growth", loc="left", fontsize=14, weight="bold")
    ax.set_xlabel("Food retail-volume growth (% YoY)")
    ax.set_ylabel("Non-food retail-volume growth (% YoY)")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _style_axes(ax, zero_line=True)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save_figure(fig, "food_vs_nonfood_growth_comparison.png")


def write_execution_manifest(data: pd.DataFrame) -> None:
    digest = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()
    manifest = {
        "phase": 2,
        "source_dataset": str(DATA_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_sha256": digest,
        "master_rows": len(data),
        "analytical_rows_per_yoy_outcome": {outcome: int(data[outcome].notna().sum()) for outcome in OUTCOMES},
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
        "matplotlib": matplotlib.__version__,
        "figure_contracts": FIGURE_CONTRACTS,
        "covariance_estimators": {
            "pooled": "HC3",
            "country": "Newey-West HAC maxlags=3",
            "category_interaction": "clustered by country-month",
        },
        "covid_exclusion_window": "2020-03-01 through 2021-12-01 inclusive",
    }
    (TABLES_DIR / "phase2_execution_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def run_analysis() -> dict[str, object]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    data = load_data()
    descriptive_by_country, descriptive_overall = descriptive_statistics(data)
    pearson = correlation_table(data, "pearson")
    spearman = correlation_table(data, "spearman")
    lags = lag_correlations(data)
    pooled_table, pooled_models = pooled_regressions(data)
    country_table, country_models = country_regressions(data)
    interaction_table, interaction_model, long_data = category_interaction_model(data)
    standardized_table, standardized_models = standardized_regressions(data)
    diagnostics = model_diagnostics(data, pooled_models)
    robustness = covid_robustness(data)
    create_figures(data)
    write_execution_manifest(data)
    return {
        "data": data,
        "descriptive_by_country": descriptive_by_country,
        "descriptive_overall": descriptive_overall,
        "pearson": pearson,
        "spearman": spearman,
        "lags": lags,
        "pooled_table": pooled_table,
        "pooled_models": pooled_models,
        "country_table": country_table,
        "country_models": country_models,
        "interaction_table": interaction_table,
        "interaction_model": interaction_model,
        "long_data": long_data,
        "standardized_table": standardized_table,
        "standardized_models": standardized_models,
        "diagnostics": diagnostics,
        "robustness": robustness,
    }


if __name__ == "__main__":
    results = run_analysis()
    print(
        "Phase 2 analysis complete: "
        f"{len(results['data'])} master rows, "
        f"{len(list(FIGURES_DIR.glob('*.png')))} figures, "
        f"{len(list(TABLES_DIR.glob('*.csv')))} CSV tables available."
    )
