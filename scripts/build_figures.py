#!/usr/bin/env python3
import os

import numpy as np
import pandas as pd


def ensure_figures_dir(repo_root: str) -> str:
    figures_dir = os.path.join(repo_root, "outputs", "figures")
    os.makedirs(figures_dir, exist_ok=True)
    return figures_dir


def load_step3_summary(repo_root: str) -> pd.DataFrame:
    path = os.path.join(repo_root, "outputs", "step3_stability_summary.csv")
    return pd.read_csv(path)


def load_step1_counts(repo_root: str) -> pd.DataFrame:
    path = os.path.join(repo_root, "outputs", "step1_counts_by_protocol.csv")
    return pd.read_csv(path)


def load_nstar(repo_root: str) -> pd.DataFrame:
    path = os.path.join(repo_root, "outputs", "step3_nstar_mae.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def build_aggregate_curves(summary_df: pd.DataFrame) -> pd.DataFrame:
    def iqr(series: pd.Series) -> float:
        return float(series.quantile(0.75) - series.quantile(0.25))

    agg = summary_df.groupby("N").agg(
        mae_median=("mae_median", "median"),
        mae_p25=("mae_median", lambda x: x.quantile(0.25)),
        mae_p75=("mae_median", lambda x: x.quantile(0.75)),
        ks_median=("ks_median", "median"),
        ks_p25=("ks_median", lambda x: x.quantile(0.25)),
        ks_p75=("ks_median", lambda x: x.quantile(0.75)),
        wasserstein_median=("wasserstein_median", "median"),
        wasserstein_p25=("wasserstein_median", lambda x: x.quantile(0.25)),
        wasserstein_p75=("wasserstein_median", lambda x: x.quantile(0.75)),
        bottom_decile_median=("bottom_decile_agreement_median", "median"),
        bottom_decile_p25=("bottom_decile_agreement_median", lambda x: x.quantile(0.25)),
        bottom_decile_p75=("bottom_decile_agreement_median", lambda x: x.quantile(0.75)),
        bottom_decile_iqr=("bottom_decile_agreement_median", iqr),
    ).reset_index()
    return agg


def plot_learning_curves(figures_dir: str, agg_df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    metrics = [
        ("mae", "Median Absolute Error"),
        ("ks", "KS Distance"),
        ("wasserstein", "Wasserstein Distance"),
        ("bottom_decile", "Bottom Decile Agreement"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=160)
    axes = axes.flatten()

    for ax, (metric_key, title) in zip(axes, metrics):
        median = agg_df[f"{metric_key}_median"]
        p25 = agg_df[f"{metric_key}_p25"]
        p75 = agg_df[f"{metric_key}_p75"]
        ax.plot(agg_df["N"], median, color="#1f5a5c", linewidth=2)
        ax.fill_between(agg_df["N"], p25, p75, color="#1f5a5c", alpha=0.2)
        ax.set_title(title)
        ax.set_xlabel("Sample size (N)")
        ax.set_ylabel("Metric")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
        if metric_key == "bottom_decile":
            ax.set_ylim(0.8, 1.01)

    fig.tight_layout()
    path = os.path.join(figures_dir, "fig_learning_curves.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_top_protocols(figures_dir: str, counts_df: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    top = counts_df.sort_values("plan_count", ascending=False).head(15).iloc[::-1]

    fig, ax = plt.subplots(figsize=(10, 7), dpi=160)
    ax.barh(top["protocol"], top["plan_count"], color="#b24a2b")
    ax.set_xlabel("Approved plans")
    ax.set_title("Top Protocols by Approved Plan Count")
    ax.grid(axis="x", linestyle="--", linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    path = os.path.join(figures_dir, "fig_top_protocols.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def plot_nstar_distribution(figures_dir: str, nstar_df: pd.DataFrame) -> None:
    if nstar_df.empty:
        return
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5), dpi=160)
    values = nstar_df["n_star"].dropna()
    ax.hist(values, bins=8, color="#5b6b2b", alpha=0.85, edgecolor="white")
    median = float(values.median()) if not values.empty else None
    if median is not None:
        ax.axvline(median, color="#1f5a5c", linestyle="--", linewidth=2, label=f"Median N* = {median:.0f}")
        ax.legend(frameon=False)
    ax.set_xlabel("N* (plateau sample size)")
    ax.set_ylabel("Protocol count")
    ax.set_title("Distribution of N* Across Protocols")
    ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.4)
    fig.tight_layout()
    path = os.path.join(figures_dir, "fig_nstar_distribution.png")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    figures_dir = ensure_figures_dir(repo_root)

    summary_df = load_step3_summary(repo_root)
    counts_df = load_step1_counts(repo_root)
    nstar_df = load_nstar(repo_root)

    if summary_df.empty:
        raise RuntimeError("Step 3 summary not found or empty.")

    agg_df = build_aggregate_curves(summary_df)

    plot_learning_curves(figures_dir, agg_df)
    plot_top_protocols(figures_dir, counts_df)
    plot_nstar_distribution(figures_dir, nstar_df)

    print("Figures written to outputs/figures")


if __name__ == "__main__":
    main()
