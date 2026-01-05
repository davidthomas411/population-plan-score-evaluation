# Troubleshooting

## MongoDB connection fails

- Confirm `.env` has a valid `PLANEVAL_MONGODB_URI`.
- Verify network access to the Mongo host.
- Confirm the account is read-only.

## Step 2 reports missing constraints

- Some protocols are not present in `protocols` or `standard_protocols`.
- These protocols are skipped in stability analysis.
- If needed, add a manual mapping table (future work).

## Stability experiment produces empty outputs

- Some protocols have too few eligible plans for the train/test split.
- Reduce `--test-min` or sample sizes in `scripts/step3_stability_experiment.py`.

## Port already in use

- Use a different port:

```bash
python3 -m http.server 8050
```

## Figures missing in GitHub Pages

- Re-run:

```bash
python3 scripts/render_figures.py
```

- Confirm the images exist in `docs/figures/`.
