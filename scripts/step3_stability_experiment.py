#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from plan_score_pipeline import (  # noqa: E402
    build_constraint_context,
    build_plan_constraints_df,
    build_protocol_constraints,
    build_protocol_standard_ref_map,
    build_reference_from_plan_constraints,
    build_standard_constraints,
    get_mongo_client,
    load_alias_map,
    load_approved_plans,
    score_plan_constraints_df,
    select_protocol_constraints,
)


def parse_sample_sizes(value: str) -> List[int]:
    sizes = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        sizes.append(int(part))
    return sizes


def stable_seed(name: str, base_seed: int) -> int:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return base_seed + int(digest[:8], 16)


def ks_distance(values_a: np.ndarray, values_b: np.ndarray) -> float:
    if values_a.size == 0 or values_b.size == 0:
        return float("nan")
    a_sorted = np.sort(values_a)
    b_sorted = np.sort(values_b)
    combined = np.sort(np.unique(np.concatenate([a_sorted, b_sorted])))
    cdf_a = np.searchsorted(a_sorted, combined, side="right") / a_sorted.size
    cdf_b = np.searchsorted(b_sorted, combined, side="right") / b_sorted.size
    return float(np.max(np.abs(cdf_a - cdf_b)))


def wasserstein_distance(values_a: np.ndarray, values_b: np.ndarray) -> float:
    if values_a.size == 0 or values_b.size == 0:
        return float("nan")
    n = min(values_a.size, values_b.size)
    a_sorted = np.sort(values_a)[:n]
    b_sorted = np.sort(values_b)[:n]
    return float(np.mean(np.abs(a_sorted - b_sorted)))


def bottom_decile_agreement(values_a: np.ndarray, values_b: np.ndarray) -> float:
    if values_a.size == 0 or values_b.size == 0:
        return float("nan")
    threshold_a = np.quantile(values_a, 0.1)
    threshold_b = np.quantile(values_b, 0.1)
    labels_a = values_a <= threshold_a
    labels_b = values_b <= threshold_b
    return float(np.mean(labels_a == labels_b))


def fit_inverse_sqrt(n_values: np.ndarray, y_values: np.ndarray) -> Tuple[float, float, float]:
    x = 1.0 / np.sqrt(n_values)
    design = np.column_stack([np.ones_like(x), x])
    coeffs, _, _, _ = np.linalg.lstsq(design, y_values, rcond=None)
    intercept, slope = coeffs
    y_pred = intercept + slope * x
    ss_res = float(np.sum((y_values - y_pred) ** 2))
    ss_tot = float(np.sum((y_values - np.mean(y_values)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(intercept), float(slope), r2


def estimate_n_star(
    n_values: np.ndarray,
    intercept: float,
    slope: float,
    plateau_fraction: float,
) -> int:
    predictions = intercept + slope / np.sqrt(n_values)
    max_pred = float(np.max(predictions))
    target = intercept + plateau_fraction * (max_pred - intercept)
    for n_value, pred in sorted(zip(n_values, predictions), key=lambda x: x[0]):
        if pred <= target:
            return int(n_value)
    return int(n_values[-1])


def summarize_group(group: pd.DataFrame, column: str) -> Dict[str, Any]:
    values = group[column].dropna()
    if values.empty:
        return {
            f"{column}_mean": float("nan"),
            f"{column}_median": float("nan"),
            f"{column}_p25": float("nan"),
            f"{column}_p75": float("nan"),
            f"{column}_iqr": float("nan"),
        }
    p25 = float(values.quantile(0.25))
    p75 = float(values.quantile(0.75))
    return {
        f"{column}_mean": float(values.mean()),
        f"{column}_median": float(values.median()),
        f"{column}_p25": p25,
        f"{column}_p75": p75,
        f"{column}_iqr": p75 - p25,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 3 stability experiment")
    parser.add_argument(
        "--sample-sizes",
        default="10,20,30,50,75,100",
        help="Comma-separated sample sizes",
    )
    parser.add_argument("--bootstraps", type=int, default=50, help="Bootstrap runs per N")
    parser.add_argument("--test-fraction", type=float, default=0.2, help="Test set fraction")
    parser.add_argument("--test-min", type=int, default=20, help="Minimum test size")
    parser.add_argument("--min-valid", type=int, default=10, help="Minimum valid plans per run")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument(
        "--plateau-fraction",
        type=float,
        default=0.05,
        help="Fraction of improvement range used to define N*",
    )
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outputs_dir = os.path.join(repo_root, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)

    sample_sizes = sorted(set(parse_sample_sizes(args.sample_sizes)))
    config = {
        "sample_sizes": sample_sizes,
        "bootstraps": args.bootstraps,
        "test_fraction": args.test_fraction,
        "test_min": args.test_min,
        "min_valid": args.min_valid,
        "seed": args.seed,
        "plateau_fraction": args.plateau_fraction,
    }
    with open(os.path.join(outputs_dir, "step3_config.json"), "w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2)

    plans = load_approved_plans(repo_root)

    client = get_mongo_client(repo_root)
    db = client["planeval"]

    alias_map = load_alias_map(db)
    standard_constraints_by_name, standard_constraints_by_id = build_standard_constraints(db)
    protocol_constraints = build_protocol_constraints(db)
    protocol_standard_ref_map = build_protocol_standard_ref_map(db)

    raw_rows: List[Dict[str, Any]] = []
    protocol_rows: List[Dict[str, Any]] = []
    test_split_rows: List[Dict[str, Any]] = []
    skipped_rows: List[Dict[str, Any]] = []

    protocol_order = plans["protocol"].value_counts().index.tolist()

    for protocol in protocol_order:
        group = plans[plans["protocol"] == protocol]
        protocol_raw = None
        raw_values = group["protocol_raw"].dropna().unique().tolist()
        if raw_values:
            protocol_raw = raw_values[0]

        constraints, source = select_protocol_constraints(
            protocol,
            protocol_raw,
            standard_constraints_by_name,
            standard_constraints_by_id,
            protocol_constraints,
            protocol_standard_ref_map,
        )
        if not constraints:
            skipped_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "reason": "missing_constraints",
                    "source": source,
                }
            )
            continue

        constraint_lookup, protocol_structure_map, directions, weights = build_constraint_context(constraints)

        plan_constraints_df = build_plan_constraints_df(
            group,
            constraint_lookup,
            alias_map,
            protocol_structure_map,
        )

        reference_full = build_reference_from_plan_constraints(
            plan_constraints_df,
            constraint_lookup,
            directions,
            weights,
        )

        plan_constraints_df["plan_score_full"] = score_plan_constraints_df(
            plan_constraints_df,
            reference_full,
        )

        eligible = plan_constraints_df[plan_constraints_df["plan_score_full"].notna()].reset_index(drop=True)
        eligible_count = len(eligible)

        if eligible_count == 0:
            skipped_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "reason": "no_scored_plans",
                    "source": source,
                }
            )
            continue

        min_train = min(sample_sizes) if sample_sizes else 0
        test_size = int(round(args.test_fraction * eligible_count))
        test_size = max(args.test_min, test_size)
        max_test = max(eligible_count - min_train, 0)
        if max_test == 0:
            skipped_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "reason": "insufficient_plans_for_split",
                    "source": source,
                }
            )
            continue

        test_size = min(test_size, max_test)
        if test_size <= 0:
            skipped_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "reason": "invalid_test_size",
                    "source": source,
                }
            )
            continue

        protocol_seed = stable_seed(protocol, args.seed)
        rng = np.random.default_rng(protocol_seed)
        permuted = rng.permutation(eligible_count)
        test_idx = permuted[:test_size]
        train_idx = permuted[test_size:]

        test_df = eligible.iloc[test_idx].reset_index(drop=True)
        train_df = eligible.iloc[train_idx].reset_index(drop=True)

        available_sizes = [size for size in sample_sizes if size <= len(train_df)]
        if not available_sizes:
            skipped_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "reason": "insufficient_train_plans",
                    "source": source,
                }
            )
            continue

        for _, row in test_df.iterrows():
            test_split_rows.append(
                {
                    "protocol": protocol,
                    "plan_id": row.get("plan_id"),
                    "patient_id": row.get("patient_id"),
                }
            )

        for sample_size in available_sizes:
            for bootstrap_id in range(args.bootstraps):
                sample_idx = rng.integers(0, len(train_df), size=sample_size)
                sample_df = train_df.iloc[sample_idx].reset_index(drop=True)
                reference_sample = build_reference_from_plan_constraints(
                    sample_df,
                    constraint_lookup,
                    directions,
                    weights,
                )
                sample_scores = score_plan_constraints_df(test_df, reference_sample)
                full_scores = test_df["plan_score_full"]

                valid_mask = sample_scores.notna() & full_scores.notna()
                valid_count = int(valid_mask.sum())
                if valid_count < args.min_valid:
                    continue

                sample_values = sample_scores[valid_mask].to_numpy(dtype=float)
                full_values = full_scores[valid_mask].to_numpy(dtype=float)

                mae = float(np.mean(np.abs(sample_values - full_values)))
                ks = ks_distance(sample_values, full_values)
                wass = wasserstein_distance(sample_values, full_values)
                decile_agree = bottom_decile_agreement(sample_values, full_values)

                raw_rows.append(
                    {
                        "protocol": protocol,
                        "N": sample_size,
                        "bootstrap_id": bootstrap_id,
                        "train_size": len(train_df),
                        "test_size": len(test_df),
                        "valid_plans": valid_count,
                        "mae": mae,
                        "ks": ks,
                        "wasserstein": wass,
                        "bottom_decile_agreement": decile_agree,
                    }
                )

        protocol_rows.append(
            {
                "protocol": protocol,
                "source": source,
                "plans_total": len(group),
                "plans_eligible": eligible_count,
                "train_size": len(train_df),
                "test_size": len(test_df),
                "constraints_total": len(constraint_lookup),
                "constraints_with_values": len(reference_full["distributions"]),
                "sample_sizes": ",".join(str(size) for size in available_sizes),
            }
        )

    raw_df = pd.DataFrame(raw_rows)
    raw_path = os.path.join(outputs_dir, "step3_stability_raw.csv")
    raw_df.to_csv(raw_path, index=False)

    summary_rows: List[Dict[str, Any]] = []
    if not raw_df.empty:
        grouped = raw_df.groupby(["protocol", "N"])
        for (protocol, sample_size), group in grouped:
            row = {
                "protocol": protocol,
                "N": sample_size,
                "bootstrap_runs": int(group.shape[0]),
                "valid_plans_median": float(group["valid_plans"].median()),
                "valid_plans_min": int(group["valid_plans"].min()),
            }
            for metric in ["mae", "ks", "wasserstein", "bottom_decile_agreement"]:
                row.update(summarize_group(group, metric))
            summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    summary_df = summary_df.sort_values(["protocol", "N"]).reset_index(drop=True)
    summary_path = os.path.join(outputs_dir, "step3_stability_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    nstar_rows: List[Dict[str, Any]] = []
    for protocol, group in summary_df.groupby("protocol"):
        group = group.sort_values("N")
        if group.shape[0] < 3:
            continue
        n_values = group["N"].to_numpy(dtype=float)
        y_values = group["mae_median"].to_numpy(dtype=float)
        intercept, slope, r2 = fit_inverse_sqrt(n_values, y_values)
        n_star = estimate_n_star(n_values, intercept, slope, args.plateau_fraction)
        nstar_rows.append(
            {
                "protocol": protocol,
                "n_star": n_star,
                "fit_intercept": intercept,
                "fit_slope": slope,
                "fit_r2": r2,
                "plateau_fraction": args.plateau_fraction,
            }
        )

    nstar_df = pd.DataFrame(nstar_rows)
    nstar_path = os.path.join(outputs_dir, "step3_nstar_mae.csv")
    nstar_df.to_csv(nstar_path, index=False)

    protocol_df = pd.DataFrame(protocol_rows)
    protocol_path = os.path.join(outputs_dir, "step3_protocol_summary.csv")
    protocol_df.to_csv(protocol_path, index=False)

    if skipped_rows:
        skipped_df = pd.DataFrame(skipped_rows)
        skipped_path = os.path.join(outputs_dir, "step3_protocols_skipped.csv")
        skipped_df.to_csv(skipped_path, index=False)

    test_split_df = pd.DataFrame(test_split_rows)
    test_split_path = os.path.join(outputs_dir, "step3_test_split.csv")
    test_split_df.to_csv(test_split_path, index=False)

    print("Step 3 validation summary")
    print(f"Protocols scored: {protocol_df.shape[0]}")
    print(f"Protocols skipped: {len(skipped_rows)}")
    print(f"Total bootstrap rows: {raw_df.shape[0]}")
    print("\nTop protocols by eligible plans")
    print(protocol_df.sort_values("plans_eligible", ascending=False).head(10).to_string(index=False))


if __name__ == "__main__":
    main()
