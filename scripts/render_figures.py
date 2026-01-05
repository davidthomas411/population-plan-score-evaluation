#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description="Render figures for GitHub Pages")
    parser.add_argument("--skip-generate", action="store_true", help="Skip figure regeneration")
    args = parser.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outputs_figures = os.path.join(repo_root, "outputs", "figures")
    docs_figures = os.path.join(repo_root, "docs", "figures")
    os.makedirs(docs_figures, exist_ok=True)

    if not args.skip_generate:
        subprocess.run(["python3", os.path.join(repo_root, "scripts", "build_figures.py")], check=True)

    if not os.path.exists(outputs_figures):
        raise FileNotFoundError("outputs/figures not found. Run scripts/build_figures.py first.")

    for filename in os.listdir(outputs_figures):
        if not filename.lower().endswith(".png"):
            continue
        src = os.path.join(outputs_figures, filename)
        dst = os.path.join(docs_figures, filename)
        shutil.copy2(src, dst)

    print("Figures copied to docs/figures")


if __name__ == "__main__":
    main()
