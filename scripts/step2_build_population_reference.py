#!/usr/bin/env python3
import os
import pickle
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from plan_score_pipeline import (  # noqa: E402
    build_protocol_constraints,
    build_protocol_standard_ref_map,
    build_reference_for_protocol,
    build_standard_constraints,
    get_mongo_client,
    load_alias_map,
    load_approved_plans,
    select_protocol_constraints,
    slugify,
)


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    plans = load_approved_plans(repo_root)

    client = get_mongo_client(repo_root)
    db = client["planeval"]

    alias_map = load_alias_map(db)
    standard_constraints_by_name, standard_constraints_by_id = build_standard_constraints(db)
    protocol_constraints = build_protocol_constraints(db)
    protocol_standard_ref_map = build_protocol_standard_ref_map(db)

    outputs_dir = os.path.join(repo_root, "outputs")
    references_dir = os.path.join(outputs_dir, "references")
    os.makedirs(references_dir, exist_ok=True)

    summary_rows = []
    plan_scores_rows = []

    for protocol, group in plans.groupby("protocol"):
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
            summary_rows.append(
                {
                    "protocol": protocol,
                    "plans": len(group),
                    "constraints_total": 0,
                    "constraints_with_values": 0,
                    "plans_scored": 0,
                    "source": source,
                }
            )
            continue

        reference, scores_df = build_reference_for_protocol(group, constraints, alias_map)
        reference["protocol"] = protocol
        reference["source"] = source

        slug = slugify(protocol)
        reference_path = os.path.join(references_dir, f"{slug}.pkl")
        with open(reference_path, "wb") as handle:
            pickle.dump(reference, handle)

        constraints_total = len(reference["constraint_meta"])
        constraints_with_values = len(reference["distributions"])
        plans_scored = scores_df["plan_score"].notna().sum()

        summary_rows.append(
            {
                "protocol": protocol,
                "plans": len(group),
                "constraints_total": constraints_total,
                "constraints_with_values": constraints_with_values,
                "plans_scored": int(plans_scored),
                "source": source,
            }
        )

        trimmed_scores = scores_df.drop(columns=["plan_constraints"])
        plan_scores_rows.append(trimmed_scores)

    summary_df = pd.DataFrame(summary_rows).sort_values("plans", ascending=False)
    summary_path = os.path.join(outputs_dir, "step2_reference_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    if plan_scores_rows:
        plan_scores_df = pd.concat(plan_scores_rows, ignore_index=True)
        plan_scores_path = os.path.join(outputs_dir, "step2_plan_scores.parquet")
        plan_scores_df.to_parquet(plan_scores_path, index=False)

    total_protocols = summary_df.shape[0]
    missing_protocols = (summary_df["constraints_total"] == 0).sum()
    scored_plans = summary_df["plans_scored"].sum()

    print("Step 2 validation summary")
    print(f"Protocols processed: {total_protocols}")
    print(f"Protocols missing constraints: {missing_protocols}")
    print(f"Plans with scores: {scored_plans}")
    print("\nTop protocols by plan count")
    print(summary_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
