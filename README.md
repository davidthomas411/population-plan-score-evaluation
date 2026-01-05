# Population Plan Score Evaluation

Project goal: quantify stability and generalization of population-based radiotherapy plan scores across protocols using approved DVH evaluations.

**Project Page (GitHub Pages):** https://davidthomas411.github.io/population-plan-score-evaluation/

## Overview

This repository contains scripts to:
- Load approved DVH evaluations (read-only).
- Build protocol-specific population references.
- Run stability experiments (learning curves).
- Generate figures and a local dashboard.

## Quickstart

1) Create and activate a virtual environment.
2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Create `.env` from the template and add the read-only Mongo URI:

```bash
cp .env.template .env
```

4) Run the pipeline:

```bash
bash scripts/run_pipeline.sh
```

5) View the local dashboard:

```bash
python3 -m http.server 8050
```

Open `http://localhost:8050/webapp/`.

## Safety Notes

- MongoDB access is **READ-ONLY**.
- Do not commit PHI or raw derived data.
- Public outputs should be aggregated metrics only.

## Auto-Generated Project Summary

<!-- AUTO_SUMMARY_START -->
**Last updated:** 2026-01-05T18:44:00Z

**Key metrics**
- Approved evaluations: 18316
- Approved plans: 7177
- Protocols total: 196
- Protocols scored: 41
- Plans scored: 4068

**AAPM abstract**
- Purpose: Assess the stability of population-based plan scores across diverse radiotherapy protocols using approved DVH evaluations.
- Methods: Retrospective analysis of 18,316 approved evaluations (7,177 plans) across 196 protocols. Protocol-specific constraint percentiles were used to compute plan scores (weights = 1/priority; higher is better). Stability was evaluated with bootstrap sampling at N=10-100 and a fixed holdout test set (20% of plans, minimum 20 per protocol). Metrics included MAE, distribution distance, and bottom-decile agreement.
- Results: 41 protocols had sufficient scored plans for stability analysis. Median MAE improved from 0.096 at N=10 to 0.02 at N=100. Median bottom-decile agreement reached 1.0 by N=50. N* median 75 (IQR 50-100).
- Conclusions: Population plan score stability improves rapidly with modest sample sizes, with diminishing returns beyond approximately 50-100 plans for many protocols. Protocols with sparse or missing constraint mappings remain a limiting factor for broad generalization.
<!-- AUTO_SUMMARY_END -->

## Repository Structure

```
src/                 Core scoring logic
scripts/             Pipeline + utility scripts
docs/                GitHub Pages site + student docs
webapp/              Local dashboard (interactive)
data/derived/         Local cached artifacts (ignored by git)
outputs/             Local outputs (ignored by git)
```

## Student Handoff

See:
- `docs/student_guide.md`
- `docs/handoff_checklist.md`
- `docs/troubleshooting.md`
- `docs/data_dictionary.md`
