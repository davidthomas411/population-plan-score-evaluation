# Data Dictionary

This document describes the CSV files exported to `docs/data/` for public sharing.

## `protocol_counts.csv`

- `protocol`: Protocol name (canonical or resolved name)
- `plan_count`: Number of approved plans for the protocol

## `reference_summary.csv`

- `protocol`: Protocol name
- `plans`: Approved plans for the protocol
- `constraints_total`: Total constraints in the protocol definition
- `constraints_with_values`: Constraints with matched achieved values
- `plans_scored`: Plans with a computed plan score
- `source`: Where constraints were sourced (standard/protocol mapping)

## `stability_summary.csv`

Aggregated stability metrics across bootstrap runs.

- `protocol`: Protocol name
- `N`: Sample size used to build the reference
- `bootstrap_runs`: Number of bootstrap runs completed
- `valid_plans_median`: Median number of valid plans in each run
- `valid_plans_min`: Minimum valid plans in each run
- `mae_mean`, `mae_median`, `mae_p25`, `mae_p75`, `mae_iqr`
- `ks_mean`, `ks_median`, `ks_p25`, `ks_p75`, `ks_iqr`
- `wasserstein_mean`, `wasserstein_median`, `wasserstein_p25`, `wasserstein_p75`, `wasserstein_iqr`
- `bottom_decile_agreement_mean`, `bottom_decile_agreement_median`, `bottom_decile_agreement_p25`,
  `bottom_decile_agreement_p75`, `bottom_decile_agreement_iqr`

## `nstar_mae.csv`

- `protocol`: Protocol name
- `n_star`: Estimated sample size at stability plateau (MAE)
- `fit_intercept`: Inverse-sqrt fit intercept
- `fit_slope`: Inverse-sqrt fit slope
- `fit_r2`: Fit R^2
- `plateau_fraction`: Fraction of improvement range used to define N*

## `protocol_summary.csv`

- `protocol`: Protocol name
- `source`: Constraint source
- `plans_total`: Approved plans in protocol
- `plans_eligible`: Plans with non-null scores
- `train_size`: Training plans in stability split
- `test_size`: Test plans in stability split
- `constraints_total`: Total constraints in protocol
- `constraints_with_values`: Constraints with matched values
- `sample_sizes`: Sample sizes used for stability
