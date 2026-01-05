import math
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from pymongo import MongoClient


LOWER_BETTER_OPS = {"<=", "<"}
HIGHER_BETTER_OPS = {">=", ">"}


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


def get_mongo_client(repo_root: str) -> MongoClient:
    load_dotenv(os.path.join(repo_root, ".env"))
    mongo_uri = os.environ.get("PLANEVAL_MONGODB_URI")
    if not mongo_uri:
        raise RuntimeError("PLANEVAL_MONGODB_URI is not set.")
    return MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.strip().lower().split())


def parse_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def normalize_operator(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if value in {"<=", "<", ">=", ">"}:
        return value
    return value.lower()


def direction_from_operator(operator: Optional[str]) -> Optional[str]:
    if not operator:
        return None
    if operator in LOWER_BETTER_OPS:
        return "lower"
    if operator in HIGHER_BETTER_OPS:
        return "higher"
    return None


def constraint_key(
    structure: Optional[str],
    metric_display: Optional[str],
    goal_operator: Optional[str],
    goal_value: Optional[float],
    variation_operator: Optional[str],
    variation_value: Optional[float],
    priority: Optional[int],
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[float], Optional[str], Optional[float], Optional[int]]:
    return (
        normalize_text(structure),
        normalize_text(metric_display),
        normalize_operator(goal_operator),
        goal_value,
        normalize_operator(variation_operator),
        variation_value,
        priority,
    )


def constraint_key_to_str(key: Tuple[Optional[str], Optional[str], Optional[str], Optional[float], Optional[str], Optional[float], Optional[int]]) -> str:
    parts = []
    for item in key:
        if item is None:
            parts.append("")
        else:
            parts.append(str(item))
    return "||".join(parts)


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = value.strip("_")
    return value or "UNKNOWN"


def build_protocol_map(protocols_collection) -> Dict[str, str]:
    protocol_map: Dict[str, str] = {}
    cursor = protocols_collection.find(
        {},
        {"protocol_name": 1, "standard_ref.standard_name": 1, "_id": 0},
    )
    for doc in cursor:
        protocol_name = doc.get("protocol_name")
        standard_name = (doc.get("standard_ref") or {}).get("standard_name")
        if not protocol_name:
            continue
        normalized = normalize_text(protocol_name)
        if not normalized:
            continue
        protocol_map[normalized] = standard_name or protocol_name
    return protocol_map


def load_alias_map(db) -> Dict[str, str]:
    alias_map: Dict[str, str] = {}
    cursor = db["custom_structure_aliases"].find({}, {"canonical": 1, "aliases": 1, "_id": 0})
    for doc in cursor:
        canonical = doc.get("canonical")
        if not canonical:
            continue
        canonical_norm = normalize_text(canonical)
        if canonical_norm:
            alias_map[canonical_norm] = canonical
        for alias in doc.get("aliases", []) or []:
            alias_norm = normalize_text(alias)
            if alias_norm:
                alias_map[alias_norm] = canonical
    return alias_map


def build_standard_constraints(db) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    constraints_by_name: Dict[str, List[Dict[str, Any]]] = {}
    constraints_by_id: Dict[str, List[Dict[str, Any]]] = {}
    cursor = db["standard_protocols"].find({}, {"protocol_name": 1, "constraints": 1, "_id": 1})
    for doc in cursor:
        protocol_name = doc.get("protocol_name")
        if not protocol_name:
            continue
        constraints: List[Dict[str, Any]] = []
        for constraint in doc.get("constraints", []) or []:
            structure = constraint.get("structure")
            objective = constraint.get("objective")
            priority = constraint.get("priority")
            goal_operator = constraint.get("goal_operator")
            goal_value = parse_numeric(constraint.get("goal_value"))
            variation_operator = constraint.get("variation_operator")
            variation_value = parse_numeric(constraint.get("variation_value"))
            constraints.append(
                {
                    "structure": structure,
                    "metric_display": objective,
                    "priority": priority,
                    "goal_operator": goal_operator,
                    "goal_value": goal_value,
                    "variation_operator": variation_operator,
                    "variation_value": variation_value,
                }
            )
        key_name = normalize_text(protocol_name) or protocol_name
        constraints_by_name[key_name] = constraints
        standard_id = doc.get("_id")
        if standard_id is not None:
            constraints_by_id[str(standard_id)] = constraints
    return constraints_by_name, constraints_by_id


def build_protocol_constraints(db) -> Dict[str, List[Dict[str, Any]]]:
    constraints_by_protocol: Dict[str, List[Dict[str, Any]]] = {}
    cursor = db["protocols"].find({}, {"protocol_name": 1, "constraints": 1, "_id": 0})
    for doc in cursor:
        protocol_name = doc.get("protocol_name")
        if not protocol_name:
            continue
        constraints: List[Dict[str, Any]] = []
        for constraint in doc.get("constraints", []) or []:
            structure = constraint.get("structure")
            metric = constraint.get("metric") or {}
            metric_display = metric.get("display") or constraint.get("objective")
            priority = constraint.get("priority")
            goal = constraint.get("goal") or {}
            variation = constraint.get("variation") or {}
            constraints.append(
                {
                    "structure": structure,
                    "metric_display": metric_display,
                    "priority": priority,
                    "goal_operator": goal.get("operator"),
                    "goal_value": parse_numeric(goal.get("value")),
                    "variation_operator": variation.get("operator"),
                    "variation_value": parse_numeric(variation.get("value")),
                }
            )
        constraints_by_protocol[normalize_text(protocol_name) or protocol_name] = constraints
    return constraints_by_protocol


def build_protocol_standard_ref_map(db) -> Dict[str, Dict[str, Optional[str]]]:
    mapping: Dict[str, Dict[str, Optional[str]]] = {}
    cursor = db["protocols"].find(
        {},
        {
            "protocol_name": 1,
            "standard_ref.standard_id": 1,
            "standard_ref.standard_name": 1,
            "_id": 0,
        },
    )
    for doc in cursor:
        protocol_name = doc.get("protocol_name")
        if not protocol_name:
            continue
        key = normalize_text(protocol_name)
        if not key:
            continue
        standard_ref = doc.get("standard_ref") or {}
        standard_id = standard_ref.get("standard_id")
        mapping[key] = {
            "standard_id": str(standard_id) if standard_id is not None else None,
            "standard_name": standard_ref.get("standard_name"),
        }
    return mapping


def build_protocol_structure_map(constraints: List[Dict[str, Any]]) -> Dict[str, str]:
    structure_map: Dict[str, str] = {}
    for constraint in constraints:
        structure = constraint.get("structure")
        norm = normalize_text(structure)
        if norm:
            structure_map[norm] = structure
    return structure_map


def tokenize(value: str) -> List[str]:
    return [token for token in re.split(r"[^A-Za-z0-9]+", value.lower()) if token]


def resolve_structure(
    raw_name: Optional[str],
    alias_map: Dict[str, str],
    protocol_structure_map: Dict[str, str],
) -> Optional[str]:
    if not raw_name:
        return None
    normalized = normalize_text(raw_name)
    if not normalized:
        return None
    alias = alias_map.get(normalized)
    if alias:
        return alias
    direct = protocol_structure_map.get(normalized)
    if direct:
        return direct

    raw_tokens = set(tokenize(raw_name))
    if not raw_tokens:
        return None
    best_match = None
    best_score = 0.0
    for norm_name, canonical in protocol_structure_map.items():
        target_tokens = set(tokenize(canonical))
        if not target_tokens:
            continue
        overlap = raw_tokens & target_tokens
        score = len(overlap) / max(len(raw_tokens), len(target_tokens))
        if score > best_score:
            best_score = score
            best_match = canonical
    if best_match and best_score > 0:
        return best_match
    return None


def build_constraint_lookup(constraints: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for constraint in constraints:
        priority = constraint.get("priority")
        try:
            priority_value = int(priority) if priority is not None else None
        except (TypeError, ValueError):
            priority_value = None
        key = constraint_key(
            constraint.get("structure"),
            constraint.get("metric_display"),
            constraint.get("goal_operator"),
            constraint.get("goal_value"),
            constraint.get("variation_operator"),
            constraint.get("variation_value"),
            priority_value,
        )
        key_str = constraint_key_to_str(key)
        if key_str in lookup:
            continue
        lookup[key_str] = {
            "structure": constraint.get("structure"),
            "metric_display": constraint.get("metric_display"),
            "goal_operator": normalize_operator(constraint.get("goal_operator")),
            "goal_value": constraint.get("goal_value"),
            "variation_operator": normalize_operator(constraint.get("variation_operator")),
            "variation_value": constraint.get("variation_value"),
            "priority": priority_value,
        }
    return lookup


def build_constraint_context(
    constraints: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str], Dict[str, str], Dict[str, float]]:
    constraint_lookup = build_constraint_lookup(constraints)
    protocol_structure_map = build_protocol_structure_map(constraints)
    directions: Dict[str, str] = {}
    weights: Dict[str, float] = {}
    for key_str, meta in constraint_lookup.items():
        direction = direction_from_operator(meta.get("goal_operator"))
        if not direction:
            continue
        directions[key_str] = direction
        priority = meta.get("priority")
        if priority is not None and isinstance(priority, int) and priority > 0:
            weights[key_str] = 1.0 / float(priority)
    return constraint_lookup, protocol_structure_map, directions, weights


def build_plan_constraints_df(
    plans: pd.DataFrame,
    constraint_lookup: Dict[str, Dict[str, Any]],
    alias_map: Dict[str, str],
    protocol_structure_map: Dict[str, str],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in plans.iterrows():
        plan_constraints = extract_plan_constraints(
            row.get("results"),
            constraint_lookup,
            alias_map,
            protocol_structure_map,
        )
        rows.append(
            {
                "patient_id": row.get("patient_id"),
                "plan_id": row.get("plan_id"),
                "protocol": row.get("protocol"),
                "protocol_raw": row.get("protocol_raw"),
                "matched_constraints": len(plan_constraints),
                "plan_constraints": plan_constraints,
            }
        )
    return pd.DataFrame(rows)


def build_reference_from_plan_constraints(
    plan_constraints_df: pd.DataFrame,
    constraint_lookup: Dict[str, Dict[str, Any]],
    directions: Dict[str, str],
    weights: Dict[str, float],
) -> Dict[str, Any]:
    distributions: Dict[str, List[float]] = {key: [] for key in constraint_lookup}
    for plan_constraints in plan_constraints_df["plan_constraints"]:
        if not isinstance(plan_constraints, dict):
            continue
        for key_str, value in plan_constraints.items():
            if key_str in distributions:
                distributions[key_str].append(value)

    sorted_distributions: Dict[str, np.ndarray] = {}
    for key_str, values in distributions.items():
        if not values:
            continue
        sorted_distributions[key_str] = np.sort(np.asarray(values, dtype=float))

    return {
        "constraint_meta": constraint_lookup,
        "distributions": sorted_distributions,
        "directions": directions,
        "weights": weights,
    }


def score_plan_constraints_df(
    plan_constraints_df: pd.DataFrame,
    reference: Dict[str, Any],
) -> pd.Series:
    distributions = reference.get("distributions", {})
    directions = reference.get("directions", {})
    weights = reference.get("weights", {})
    scores = []
    for plan_constraints in plan_constraints_df["plan_constraints"]:
        if not isinstance(plan_constraints, dict):
            scores.append(None)
            continue
        score = compute_plan_score(plan_constraints, distributions, directions, weights)
        scores.append(score)
    return pd.Series(scores, index=plan_constraints_df.index)


def extract_plan_constraints(
    results: Iterable[Dict[str, Any]],
    constraint_lookup: Dict[str, Dict[str, Any]],
    alias_map: Dict[str, str],
    protocol_structure_map: Dict[str, str],
) -> Dict[str, float]:
    matched: Dict[str, float] = {}
    if results is None:
        return matched
    if isinstance(results, float) and math.isnan(results):
        return matched
    if isinstance(results, np.ndarray):
        iterable = results.tolist()
    else:
        iterable = results
    for result in iterable or []:
        metric = result.get("metric") or {}
        metric_display = metric.get("display") or result.get("objective")
        raw_structure = result.get("structure_tg263") or result.get("structure")
        structure = resolve_structure(raw_structure, alias_map, protocol_structure_map)
        priority = result.get("priority")
        try:
            priority_value = int(priority) if priority is not None else None
        except (TypeError, ValueError):
            priority_value = None
        goal = result.get("goal") or {}
        variation = result.get("variation") or {}
        key = constraint_key(
            structure,
            metric_display,
            goal.get("operator"),
            parse_numeric(goal.get("value")),
            variation.get("operator"),
            parse_numeric(variation.get("value")),
            priority_value,
        )
        key_str = constraint_key_to_str(key)
        if key_str not in constraint_lookup:
            continue
        achieved = result.get("achieved") or {}
        achieved_value = parse_numeric(achieved.get("value"))
        if achieved_value is None:
            continue
        if key_str in matched:
            continue
        matched[key_str] = achieved_value
    return matched


def compute_percentile(value: float, sorted_values: np.ndarray, direction: str) -> float:
    n = len(sorted_values)
    if n == 0:
        return float("nan")
    if n == 1:
        base = 1.0
    else:
        rank = int(np.searchsorted(sorted_values, value, side="right"))
        if rank < 1:
            rank = 1
        if rank > n:
            rank = n
        base = (rank - 1) / (n - 1)
    if direction == "lower":
        return 1.0 - base
    return base


def compute_plan_score(
    plan_constraints: Dict[str, float],
    distributions: Dict[str, np.ndarray],
    directions: Dict[str, str],
    weights: Dict[str, float],
) -> Optional[float]:
    total_weight = 0.0
    total_score = 0.0
    for key_str, value in plan_constraints.items():
        dist = distributions.get(key_str)
        direction = directions.get(key_str)
        weight = weights.get(key_str)
        if dist is None or direction is None or weight is None:
            continue
        percentile = compute_percentile(value, dist, direction)
        total_score += weight * percentile
        total_weight += weight
    if total_weight == 0:
        return None
    return total_score / total_weight


def build_population_reference(
    plans: pd.DataFrame,
    constraints: List[Dict[str, Any]],
    alias_map: Dict[str, str],
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    constraint_lookup = build_constraint_lookup(constraints)
    protocol_structure_map = build_protocol_structure_map(constraints)
    distributions: Dict[str, List[float]] = {key: [] for key in constraint_lookup}
    directions: Dict[str, str] = {}
    weights: Dict[str, float] = {}
    for key_str, meta in constraint_lookup.items():
        direction = direction_from_operator(meta.get("goal_operator"))
        if not direction:
            continue
        directions[key_str] = direction
        priority = meta.get("priority")
        if priority is not None and priority > 0:
            weights[key_str] = 1.0 / float(priority)

    plan_scores: List[Dict[str, Any]] = []
    for _, row in plans.iterrows():
        plan_constraints = extract_plan_constraints(
            row.get("results"),
            constraint_lookup,
            alias_map,
            protocol_structure_map,
        )
        for key_str, value in plan_constraints.items():
            if key_str in distributions:
                distributions[key_str].append(value)
        plan_scores.append(
            {
                "patient_id": row.get("patient_id"),
                "plan_id": row.get("plan_id"),
                "protocol": row.get("protocol"),
                "protocol_raw": row.get("protocol_raw"),
                "matched_constraints": len(plan_constraints),
                "plan_constraints": plan_constraints,
            }
        )

    sorted_distributions: Dict[str, np.ndarray] = {}
    for key_str, values in distributions.items():
        if not values:
            continue
        sorted_distributions[key_str] = np.sort(np.asarray(values, dtype=float))

    reference = {
        "constraint_meta": constraint_lookup,
        "distributions": sorted_distributions,
        "directions": directions,
        "weights": weights,
    }

    plan_scores_df = pd.DataFrame(plan_scores)
    plan_scores_df["plan_score"] = plan_scores_df["plan_constraints"].apply(
        lambda x: compute_plan_score(x, sorted_distributions, directions, weights)
    )
    return reference, plan_scores_df


def select_protocol_constraints(
    protocol: str,
    protocol_raw: Optional[str],
    standard_constraints_by_name: Dict[str, List[Dict[str, Any]]],
    standard_constraints_by_id: Dict[str, List[Dict[str, Any]]],
    protocol_constraints: Dict[str, List[Dict[str, Any]]],
    standard_ref_map: Dict[str, Dict[str, Optional[str]]],
) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    protocol_norm = normalize_text(protocol) or protocol
    if protocol_norm in standard_constraints_by_name:
        return standard_constraints_by_name[protocol_norm], "standard_protocols_name"
    if protocol_norm in protocol_constraints:
        return protocol_constraints[protocol_norm], "protocols"

    candidate_names = []
    if protocol_raw:
        candidate_names.append(protocol_raw)
    candidate_names.append(protocol)
    for candidate in candidate_names:
        candidate_norm = normalize_text(candidate) or candidate
        ref = standard_ref_map.get(candidate_norm)
        if not ref:
            continue
        standard_id = ref.get("standard_id")
        standard_name = ref.get("standard_name")
        if standard_id and standard_id in standard_constraints_by_id:
            return standard_constraints_by_id[standard_id], "standard_protocols_id"
        if standard_name:
            standard_name_norm = normalize_text(standard_name) or standard_name
            if standard_name_norm in standard_constraints_by_name:
                return standard_constraints_by_name[standard_name_norm], "standard_protocols_ref_name"

    if protocol_raw:
        raw_norm = normalize_text(protocol_raw) or protocol_raw
        if raw_norm in protocol_constraints:
            return protocol_constraints[raw_norm], "protocols_raw"
    return None, "missing"


def load_approved_plans(repo_root: str) -> pd.DataFrame:
    parquet_path = os.path.join(repo_root, "outputs", "approved_plans.parquet")
    jsonl_path = os.path.join(repo_root, "outputs", "approved_plans.jsonl")
    if os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    if os.path.exists(jsonl_path):
        return pd.read_json(jsonl_path, lines=True)
    raise RuntimeError("Approved plans dataset not found. Run Step 1 first.")


def build_reference_for_protocol(
    plans: pd.DataFrame,
    constraints: List[Dict[str, Any]],
    alias_map: Dict[str, str],
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    reference, scores_df = build_population_reference(plans, constraints, alias_map)
    return reference, scores_df
