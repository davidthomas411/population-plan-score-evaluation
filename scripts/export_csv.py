#!/usr/bin/env python3
import json
import os
from datetime import datetime

import pandas as pd


def load_csv(repo_root: str, rel_path: str) -> pd.DataFrame:
    path = os.path.join(repo_root, rel_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing required file: {rel_path}")
    return pd.read_csv(path)


def build_aggregate_curves(summary_df: pd.DataFrame) -> pd.DataFrame:
    agg = summary_df.groupby("N").agg(
        mae_median=("mae_median", "median"),
        mae_p25=("mae_median", lambda x: x.quantile(0.25)),
        mae_p75=("mae_median", lambda x: x.quantile(0.75)),
        ks_median=("ks_median", "median"),
        ks_p25=("ks_median", lambda x: x.quantile(0.25)),
        ks_p75=("ks_median", lambda x: x.quantile(0.75)),
        wasserstein_median=("wasserstein_median", "median"),
        wasserstein_p25=("wasserstein_median", lambda x: x.quantile(0.25)),
        wasserstein_p75=("wasserstein_median", lambda x: x.quantile(0.75)),
        bottom_decile_median=("bottom_decile_agreement_median", "median"),
        bottom_decile_p25=("bottom_decile_agreement_median", lambda x: x.quantile(0.25)),
        bottom_decile_p75=("bottom_decile_agreement_median", lambda x: x.quantile(0.75)),
    ).reset_index()
    return agg


def format_float(value: float, digits: int = 3) -> float:
    if value is None:
        return value
    return float(round(value, digits))


def build_abstract(stats: dict, agg_df: pd.DataFrame, nstar_df: pd.DataFrame) -> dict:
    n10 = agg_df[agg_df["N"] == 10]
    n100 = agg_df[agg_df["N"] == 100]
    mae_10 = format_float(n10["mae_median"].iloc[0]) if not n10.empty else None
    mae_100 = format_float(n100["mae_median"].iloc[0]) if not n100.empty else None
    agree_50 = None
    n50 = agg_df[agg_df["N"] == 50]
    if not n50.empty:
        agree_50 = format_float(n50["bottom_decile_median"].iloc[0])

    nstar_summary = ""
    if not nstar_df.empty:
        nstar_summary = (
            f"N* median {int(nstar_df['n_star'].median())} "
            f"(IQR {int(nstar_df['n_star'].quantile(0.25))}-"
            f"{int(nstar_df['n_star'].quantile(0.75))})."
        )

    purpose = (
        "Assess the stability of population-based plan scores across diverse "
        "radiotherapy protocols using approved DVH evaluations."
    )
    methods = (
        f"Retrospective analysis of {stats['approved_evaluations']:,} approved evaluations "
        f"({stats['approved_plans']:,} plans) across {stats['protocols_total']} protocols. "
        "Protocol-specific constraint percentiles were used to compute plan scores "
        "(weights = 1/priority; higher is better). Stability was evaluated with "
        "bootstrap sampling at N=10-100 and a fixed holdout test set (20% of plans, "
        "minimum 20 per protocol). Metrics included MAE, distribution distance, "
        "and bottom-decile agreement."
    )
    results_parts = [
        f"{stats['protocols_scored']} protocols had sufficient scored plans for stability analysis.",
        f"Median MAE improved from {mae_10} at N=10 to {mae_100} at N=100." if mae_10 and mae_100 else None,
        f"Median bottom-decile agreement reached {agree_50} by N=50." if agree_50 else None,
        nstar_summary or None,
    ]
    results = " ".join([part for part in results_parts if part])
    conclusions = (
        "Population plan score stability improves rapidly with modest sample sizes, "
        "with diminishing returns beyond approximately 50-100 plans for many protocols. "
        "Protocols with sparse or missing constraint mappings remain a limiting factor "
        "for broad generalization."
    )
    return {
        "purpose": purpose,
        "methods": methods,
        "results": results,
        "conclusions": conclusions,
    }


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_data_dir = os.path.join(repo_root, "docs", "data")
    os.makedirs(docs_data_dir, exist_ok=True)

    step1 = load_csv(repo_root, "outputs/step1_summary.csv").iloc[0]
    counts = load_csv(repo_root, "outputs/step1_counts_by_protocol.csv")
    step2 = load_csv(repo_root, "outputs/step2_reference_summary.csv")
    step3_summary = load_csv(repo_root, "outputs/step3_stability_summary.csv")
    step3_protocol = load_csv(repo_root, "outputs/step3_protocol_summary.csv")

    nstar_path = os.path.join(repo_root, "outputs", "step3_nstar_mae.csv")
    if os.path.exists(nstar_path):
        nstar_df = pd.read_csv(nstar_path)
    else:
        nstar_df = pd.DataFrame()

    counts.to_csv(os.path.join(docs_data_dir, "protocol_counts.csv"), index=False)
    step2[
        [
            "protocol",
            "plans",
            "constraints_total",
            "constraints_with_values",
            "plans_scored",
            "source",
        ]
    ].to_csv(os.path.join(docs_data_dir, "reference_summary.csv"), index=False)

    step3_summary.to_csv(os.path.join(docs_data_dir, "stability_summary.csv"), index=False)
    step3_protocol.to_csv(os.path.join(docs_data_dir, "protocol_summary.csv"), index=False)
    if not nstar_df.empty:
        nstar_df.to_csv(os.path.join(docs_data_dir, "nstar_mae.csv"), index=False)

    agg_df = build_aggregate_curves(step3_summary)
    agg_df.to_csv(os.path.join(docs_data_dir, "learning_curve.csv"), index=False)

    stats = {
        "approved_evaluations": int(step1["total_approved_evaluations"]),
        "approved_plans": int(step1["total_approved_plans"]),
        "protocols_total": int(step1["number_of_protocols"]),
        "protocols_with_constraints": int((step2["constraints_total"] > 0).sum()),
        "protocols_missing_constraints": int((step2["constraints_total"] == 0).sum()),
        "plans_scored": int(step2["plans_scored"].sum()),
        "protocols_scored": int(step3_protocol.shape[0]),
        "protocols_skipped": int(step1["number_of_protocols"] - step3_protocol.shape[0]),
        "plans_eligible_median": int(step3_protocol["plans_eligible"].median()),
        "plans_eligible_p25": int(step3_protocol["plans_eligible"].quantile(0.25)),
        "plans_eligible_p75": int(step3_protocol["plans_eligible"].quantile(0.75)),
    }

    abstract = build_abstract(stats, agg_df, nstar_df)

    top_protocols = (
        counts.sort_values("plan_count", ascending=False)
        .head(12)
        .to_dict(orient="records")
    )

    project_summary = {
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "stats": stats,
        "abstract": abstract,
        "top_protocols": top_protocols,
        "learning_curve": agg_df.to_dict(orient="records"),
    }

    with open(os.path.join(docs_data_dir, "project_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(project_summary, handle, indent=2)

    print("Exported aggregated CSVs and project_summary.json to docs/data/")


if __name__ == "__main__":
    main()
