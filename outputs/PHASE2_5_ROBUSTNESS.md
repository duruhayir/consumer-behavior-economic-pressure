# Phase 2.5 — Panel robustness

## Why this check was necessary

Phase 2 diagnostics showed strong residual serial dependence in the pooled regressions: Durbin–Watson statistics were about 1.00–1.05 and Breusch–Godfrey lag-3 tests had p-values below 0.001. HC3 errors address heteroskedasticity but not that time dependence, and simultaneous shocks can affect all three countries. This pass therefore tests the same relationships with covariance methods designed for serial and cross-sectional dependence and with common month shocks explicitly absorbed.

## Scope and specification

This phase preserves the validated master dataset and all Phase 2 results. It uses the unchanged January 2016–December 2025 analytical sample: 360 country-month observations (3 countries × 120 months). Retail outcomes are year-on-year changes in real retail-sales **volume proxies**, not nominal consumer expenditure.

All robustness models were fixed in advance. Model A includes country fixed effects. Model B includes country and month fixed effects. Standard errors use Driscoll–Kraay covariance with a Bartlett kernel and bandwidth 3. No alternative bandwidth, sample, predictor set, or COVID exclusion was tested in this phase. Results are associations, not causal estimates.

## Main panel estimates

Values below are coefficient [95% confidence interval]. Phase 2 HC3 coefficients are included for comparison.

| Outcome | Predictor | Phase 2 HC3 | Model A: country FE + DK | Model B: country + month FE + DK | Assessment |
|---|---|---:|---:|---:|---|
| Total | Inflation | -0.046 | -0.046 [-0.481, 0.389] | -0.624 [-1.126, -0.121] | Model A stable; Model B materially changed |
| Total | Confidence | 0.195 | 0.195 [0.064, 0.327] | -0.025 [-0.207, 0.156] | Model A stable; Model B materially changed |
| Food | Inflation | -0.786 | -0.786 [-1.110, -0.462] | -0.657 [-1.179, -0.134] | Broadly stable in both models |
| Food | Confidence | -0.007 | -0.007 [-0.085, 0.071] | -0.004 [-0.120, 0.113] | Broadly stable near zero |
| Non-food | Inflation | 0.321 | 0.321 [-0.415, 1.058] | -0.578 [-1.314, 0.157] | Model A stable; Model B materially changed |
| Non-food | Confidence | 0.309 | 0.309 [0.090, 0.528] | -0.033 [-0.316, 0.250] | Model A stable; Model B materially changed |

Model A point estimates exactly equal the original HC3 estimates because only the covariance estimator changes. Under its Driscoll–Kraay uncertainty, food inflation, total confidence, and non-food confidence retain 95% intervals excluding zero. The other three intervals include zero.

Model B removes common month shocks and relies on country deviations within each month. Only the food–inflation association remains directionally and quantitatively stable. The negative total-inflation estimate is distinguishable from zero in Model B, but it is classified as materially changed because its magnitude differs sharply from the pre-existing estimate. Statistical significance alone is not treated as stability.

## Identification and collinearity

Both models retain full predictor rank (2 of 2). The transformed-design condition number is 4.00 for Model A and 3.50 for Model B, with transformed predictor correlations of -0.686 and -0.507, respectively. There is no numerical rank failure.

Month fixed effects remove much of the available variation: the transformed standard deviation falls from 2.762 to 0.959 for inflation and from 7.514 to 2.798 for confidence. Model B is identifiable, but it is based on only three contemporaneous country deviations per month. Its estimates should therefore be described as fragile and data-limited, not as definitive null or causal evidence.

## Food/non-food interaction robustness

The original interaction coefficients are preserved because this check changes only covariance estimation:

- Inflation × non-food: **0.986**, DK SE 0.410, 95% CI [0.182, 1.790], p=0.016. The original country-month-clustered SE was 0.229.
- Confidence × non-food: **0.258**, DK SE 0.115, 95% CI [0.032, 0.485], p=0.025. The original clustered SE was 0.073.

Both interaction directions survive, but inference is weaker because the uncertainty intervals widen. Derived slopes under the same covariance are: food inflation -0.725 [-1.058, -0.393], non-food inflation 0.261 [-0.456, 0.978], food confidence 0.022 [-0.065, 0.109], and non-food confidence 0.280 [0.077, 0.484].

## Readiness for Phase 3

The category-asymmetry story survives, especially the negative food–inflation association and the two food/non-food contrasts. The broader confidence story does **not** survive month fixed effects: total and non-food confidence estimates reverse toward zero. Phase 3 is ready to begin only with these limitations carried forward, associational wording retained, and prominent disclosure that the common-time-shock specification has just three countries.

For the future dashboard and report, the original HC3 results may be shown as the baseline, but the panel-robust estimates must appear alongside them. The narrative should emphasize category differences and must not present the positive total/non-food confidence coefficients as robust to common month effects. No Phase 3 artifact is created here.

