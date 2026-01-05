#!/usr/bin/env bash
set -euo pipefail

python3 scripts/step1_load_approved_plans.py
python3 scripts/step2_build_population_reference.py
python3 scripts/step3_stability_experiment.py
python3 scripts/build_figures.py
python3 scripts/build_webapp_assets.py
python3 scripts/export_csv.py
python3 scripts/render_figures.py
python3 scripts/update_readme.py

echo "Pipeline complete."
