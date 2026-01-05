#!/usr/bin/env python3
import json
import os


def render_summary(data: dict) -> str:
    stats = data.get("stats", {})
    abstract = data.get("abstract", {})
    lines = []
    lines.append(f"**Last updated:** {data.get('generated_at', 'unknown')}")
    lines.append("")
    lines.append("**Key metrics**")
    lines.append(f"- Approved evaluations: {stats.get('approved_evaluations', '--')}")
    lines.append(f"- Approved plans: {stats.get('approved_plans', '--')}")
    lines.append(f"- Protocols total: {stats.get('protocols_total', '--')}")
    lines.append(f"- Protocols scored: {stats.get('protocols_scored', '--')}")
    lines.append(f"- Plans scored: {stats.get('plans_scored', '--')}")
    lines.append("")
    lines.append("**AAPM abstract**")
    lines.append(f"- Purpose: {abstract.get('purpose', '--')}")
    lines.append(f"- Methods: {abstract.get('methods', '--')}")
    lines.append(f"- Results: {abstract.get('results', '--')}")
    lines.append(f"- Conclusions: {abstract.get('conclusions', '--')}")
    return "\n".join(lines)


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    summary_path = os.path.join(repo_root, "docs", "data", "project_summary.json")
    readme_path = os.path.join(repo_root, "README.md")

    if not os.path.exists(summary_path):
        raise FileNotFoundError("Missing docs/data/project_summary.json. Run scripts/export_csv.py first.")

    with open(summary_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    with open(readme_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    start_marker = "<!-- AUTO_SUMMARY_START -->"
    end_marker = "<!-- AUTO_SUMMARY_END -->"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise RuntimeError("README markers not found or invalid.")

    summary_text = render_summary(data)
    updated = (
        content[: start_idx + len(start_marker)]
        + "\n"
        + summary_text
        + "\n"
        + content[end_idx:]
    )

    with open(readme_path, "w", encoding="utf-8") as handle:
        handle.write(updated)

    print("README updated.")


if __name__ == "__main__":
    main()
