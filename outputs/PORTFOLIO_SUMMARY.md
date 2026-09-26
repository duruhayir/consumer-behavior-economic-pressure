# Portfolio Summary

I examined how inflation and consumer confidence relate to real retail-sales growth in the Netherlands, Germany and France using monthly Eurostat data from 2015 to 2025. The project compares total retail with food and non-food categories, using retail volume indices rather than nominal turnover.

I built a reproducible Python workflow to inspect the source schemas, create a complete 396-row country-month panel, calculate year-on-year growth, validate missing values and produce analysis-ready outputs. The statistical work included descriptive analysis, Pearson and Spearman correlations, short lag comparisons, country fixed-effects regressions, country-level models, a food/non-food interaction model and COVID-period sensitivity checks.

The strongest result was a stable negative association between inflation and food retail-volume growth. In the model with country and month effects, a one-percentage-point increase in annual inflation was associated with about 0.66 percentage points lower annual food growth. Food and non-food also showed different inflation and confidence patterns.

The robustness check changed the confidence story: positive relationships in simpler models moved close to zero after shared monthly shocks were controlled for. I used pandas, NumPy, SciPy, statsmodels, linearmodels, matplotlib and Jupyter, then built two Tableau dashboards from the validated project extracts.

