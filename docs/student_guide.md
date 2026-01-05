# Student Guide

This guide walks you through running the population plan score stability study locally.

## 1) Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment template:

```bash
cp .env.template .env
```

4. Add the **read-only** MongoDB URI to `.env`.

## 2) Run the Pipeline

```bash
bash scripts/run_pipeline.sh
```

This runs:
- Step 1: load and deduplicate approved evaluations
- Step 2: build protocol references + plan scores
- Step 3: stability experiment
- Figures and webapp data export
- README + GitHub Pages data refresh

## 3) View the Local Dashboard

```bash
python3 -m http.server 8050
```

Open `http://localhost:8050/webapp/`.

## 4) Update GitHub Pages Content

After new outputs are generated:

```bash
python3 scripts/export_csv.py
python3 scripts/render_figures.py
python3 scripts/update_readme.py
```

## 5) Safety Reminders

- MongoDB access is **READ-ONLY**.
- Do not commit PHI or raw derived data.
- Only aggregated metrics should be included in `docs/`.
