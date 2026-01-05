#!/usr/bin/env python3
import os
from datetime import datetime

from pymongo import MongoClient
import pandas as pd


def load_dotenv(dotenv_path: str) -> None:
    if not os.path.exists(dotenv_path):
        return
    with open(dotenv_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def normalize_protocol_name(name: str | None) -> str | None:
    if not name:
        return None
    return " ".join(name.strip().lower().split())


def build_protocol_map(protocols_collection) -> dict[str, str]:
    protocol_map: dict[str, str] = {}
    cursor = protocols_collection.find(
        {},
        {"protocol_name": 1, "standard_ref.standard_name": 1, "_id": 0},
    )
    for doc in cursor:
        protocol_name = doc.get("protocol_name")
        standard_name = (doc.get("standard_ref") or {}).get("standard_name")
        if not protocol_name:
            continue
        normalized = normalize_protocol_name(protocol_name)
        if not normalized:
            continue
        protocol_map[normalized] = standard_name or protocol_name
    return protocol_map


def resolve_protocol(doc: dict, protocol_map: dict[str, str]) -> tuple[str, str | None]:
    standard_protocol = doc.get("standard_protocol")
    protocol_name = (doc.get("protocol") or {}).get("protocol_name")
    raw = None
    if isinstance(standard_protocol, str) and standard_protocol.strip():
        raw = standard_protocol.strip()
    elif isinstance(protocol_name, str) and protocol_name.strip():
        raw = protocol_name.strip()

    normalized = normalize_protocol_name(raw)
    canonical = protocol_map.get(normalized, raw) if normalized else raw
    return canonical or "UNKNOWN", raw


def select_most_recent(group: pd.DataFrame) -> pd.Series:
    sort_time = group["created_at"].copy()
    sort_time = sort_time.fillna(group["updated_at"])
    if group["attempt_number"].notna().any():
        ordered = group.assign(sort_time=sort_time).sort_values(
            ["attempt_number", "sort_time", "updated_at"],
            ascending=False,
            na_position="last",
        )
    else:
        ordered = group.assign(sort_time=sort_time).sort_values(
            ["sort_time", "updated_at"],
            ascending=False,
            na_position="last",
        )
    return ordered.iloc[0]


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(repo_root, ".env"))

    mongo_uri = os.environ.get("PLANEVAL_MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("PLANEVAL_MONGODB_URI is not set.")

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client["planeval"]

    protocol_map = build_protocol_map(db["protocols"])

    projection = {
        "_id": 0,
        "patient.patient_id": 1,
        "plan_id": 1,
        "attempt_number": 1,
        "created_at": 1,
        "updated_at": 1,
        "standard_protocol": 1,
        "protocol.protocol_name": 1,
        "approval.is_approved": 1,
        "results": 1,
    }
    cursor = db["evaluations"].find({"approval.is_approved": True}, projection)

    records = []
    for doc in cursor:
        patient = doc.get("patient") or {}
        patient_id = patient.get("patient_id")
        plan_id = doc.get("plan_id")
        protocol, protocol_raw = resolve_protocol(doc, protocol_map)
        records.append(
            {
                "patient_id": patient_id,
                "plan_id": plan_id,
                "protocol": protocol,
                "protocol_raw": protocol_raw,
                "attempt_number": doc.get("attempt_number"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "results": doc.get("results", []),
            }
        )

    df = pd.DataFrame(records)

    if df.empty:
        raise RuntimeError("No approved evaluations found.")

    deduped = (
        df.groupby(["patient_id", "plan_id", "protocol"], dropna=False, group_keys=False)
        .apply(select_most_recent)
        .reset_index(drop=True)
    )

    total_approved_evaluations = len(df)
    total_approved_plans = len(deduped)
    protocol_counts = (
        deduped["protocol"].value_counts(dropna=False).rename_axis("protocol").reset_index(name="plan_count")
    )
    number_of_protocols = len(protocol_counts)

    outputs_dir = os.path.join(repo_root, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)

    summary = pd.DataFrame(
        [
            {
                "total_approved_evaluations": total_approved_evaluations,
                "total_approved_plans": total_approved_plans,
                "number_of_protocols": number_of_protocols,
                "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        ]
    )
    summary.to_csv(os.path.join(outputs_dir, "step1_summary.csv"), index=False)
    protocol_counts.to_csv(os.path.join(outputs_dir, "step1_counts_by_protocol.csv"), index=False)

    parquet_path = os.path.join(outputs_dir, "approved_plans.parquet")
    jsonl_path = os.path.join(outputs_dir, "approved_plans.jsonl")
    try:
        deduped.to_parquet(parquet_path, index=False)
    except Exception:
        deduped.to_json(jsonl_path, orient="records", lines=True)

    print("Step 1 validation summary")
    print(summary.to_string(index=False))
    print("\nPlan count per protocol")
    print(protocol_counts.to_string(index=False))


if __name__ == "__main__":
    main()
