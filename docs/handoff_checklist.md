# Handoff Checklist

## Repository
- [ ] `.gitignore` blocks outputs, derived data, and `.env`
- [ ] `.env.template` exists with placeholder URI
- [ ] `requirements.txt` captures dependencies

## Docs
- [ ] `README.md` has overview + quickstart + safety notes
- [ ] `docs/student_guide.md` explains steps
- [ ] `docs/data_dictionary.md` documents shared CSVs
- [ ] `docs/troubleshooting.md` lists common issues
- [ ] `docs/sample_data/` contains non-PHI examples

## Scripts
- [ ] `scripts/run_pipeline.sh` runs full pipeline
- [ ] `scripts/export_csv.py` exports aggregated, shareable CSVs
- [ ] `scripts/render_figures.py` refreshes figures for Pages
- [ ] `scripts/update_readme.py` refreshes README summary

## GitHub Pages
- [ ] `docs/index.html` renders summary + figures
- [ ] `docs/site.css` styles the page
- [ ] Figures copied to `docs/figures/`
- [ ] Aggregated data in `docs/data/`

## Safety
- [ ] No PHI or raw derived data committed
- [ ] Outputs only include aggregated metrics
