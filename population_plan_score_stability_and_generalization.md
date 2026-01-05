# Population Plan Score Stability and Generalization Study

## Project Goal

Evaluate the robustness, stability, and generalizability of a population-based
radiotherapy plan score across a wide variety of clinical protocols using a
large retrospective DVH evaluation dataset.

This project extends prior single-protocol population plan score work by:

1) Quantifying how many approved plans are required for a stable population reference
2) Comparing protocol-specific population references to a generic pooled reference
3) Testing whether pooled or shrinkage-based references remain useful for quality screening

---

## Key Constraints

- MongoDB access is READ-ONLY
- No writes back to MongoDB
- Use only clinically APPROVED plans
- Use only final approved evaluations per plan
- All outputs are local (CSV, figures, cached artifacts)
- Analysis must be protocol-aware
- Avoid overfitting and data leakage

---

## Data Source

MongoDB:

- Database: `planeval`
- Collection: `evaluations`

Each approved evaluation contains:

- protocol name
- DVH-based constraint evaluations
- achieved values vs limits
- overall plan score (from plan score template)
- approval flag

---

## Core Hypotheses

H1: Population plan score references stabilize as the number of approved plans (N) increases,
    following a diminishing-returns learning curve.

H2: Protocol-specific population references provide more accurate percentile ranking than
    a generic pooled reference, especially for fine-grained discrimination.

H3: Generic pooled references may still be useful for coarse quality screening (e.g. bottom decile),
    and shrinkage pooling can improve stability for protocols with limited sample size.

---

## Step-by-Step Implementation Plan

### Step 1 — Load Approved Plans

1. Connect to MongoDB in READ-ONLY mode.
2. Query `planeval.evaluations` for:
   - approved == true
3. Deduplicate to ONE evaluation per (patient_id, plan_id, protocol):
   - keep the most recent approved evaluation
4. Build a dataframe with:
   - plan_id (de-identified)
   - protocol
   - constraint evaluation data
   - composite plan score (from template)
5. Report:
   - total approved plans
   - number of protocols
   - plan count per protocol

STOP and validate counts before proceeding.

---

### Step 2 — Define Population Reference Construction

For a given set of plans:

- Construct the population reference required by the plan score method
- This may include:
  - empirical distributions of constraint metrics
  - normalization statistics
  - percentile mappings

Implement this as a reusable function: 

build_population_reference(plans_subset) -> reference_object

---

### Step 3 — Stability Experiment (Learning Curves)

For each protocol with sufficient plans:

1. Treat the full protocol dataset as the reference baseline.
2. For N in increasing sample sizes (e.g. 10, 20, 30, 50, 75, 100, …):
   a. Randomly sample N approved plans (bootstrap with replacement)
   b. Build a population reference from the sample
   c. Score a fixed held-out test set
3. Compute stability metrics:
   - mean absolute percentile error vs full reference
   - distribution distance (e.g. KS or Wasserstein)
   - agreement on bottom decile membership
4. Aggregate results across bootstrap runs.

Fit a saturating curve to estimate N* where improvements plateau.

---

### Step 4 — Protocol-Specific vs Generic Reference

1. Build:
   - protocol-specific population reference
   - generic pooled reference (all protocols combined)
2. For each plan:
   - compute percentile under both references
3. Quantify:
   - bias (generic − protocol percentile)
   - variance of differences
   - bottom-decile disagreement rate

Repeat analysis by protocol.

---

### Step 5 — Shrinkage / Blended Reference (Small-N Strategy)

For protocols with limited data:

1. Define a shrinkage reference:

R_shrink = w(N)*R_protocol + (1-w(N))*R_generic
where w(N) = N / (N + k)

2. Evaluate whether shrinkage improves stability metrics relative to:

- protocol-only reference
- generic-only reference

---

### Step 6 — Statistical Analysis

Apply simple, interpretable statistics:

- Bootstrap confidence intervals
- Learning curve fitting (exponential or inverse-sqrt)
- Paired comparisons between reference types
- Effect sizes where appropriate

Avoid complex modeling.

---

## Visualization and Figures (AAPM-Oriented)

Generate and save:

1. Learning curves:

- stability metric vs N (median + IQR)

2. Bias plots:

- generic vs protocol percentile differences

3. Outlier agreement plots:

- bottom-decile agreement vs N

4. Optional:

- protocol ranking by N* (plans required for stability)

Save figures to `outputs/figures/`.

---

## Web App / Dashboard (Incremental)

Build a lightweight local web app to:

- select protocol
- visualize learning curves
- compare generic vs protocol references
- display key figures as they are generated

Requirements:

- local-only
- no authentication
- simple plotting (e.g. Plotly, Altair)
- reloadable as new outputs are created

---

## Explicit Non-Goals

- No TPS integration
- No planner behavior modeling
- No plan optimization
- No MongoDB writes
- No clinical decision claims

---

## One-Sentence Summary

This study quantifies how many approved plans are required to construct stable
population-based plan scores across diverse protocols and evaluates when
protocol-specific versus pooled references are appropriate for quality assessment.
