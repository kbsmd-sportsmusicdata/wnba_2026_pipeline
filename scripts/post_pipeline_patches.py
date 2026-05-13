"""
post_pipeline_patches.py
========================
Run this script AFTER every build_doc2_value_chain.py execution to re-apply
three durable customizations that the pipeline wipes on each full rebuild.

Usage:
    python3 scripts/post_pipeline_patches.py

Patches applied (in order):
  1. Multi-year rate trend columns → player_archetypes
     (ast_pct/ts_pct/usage_pct across 2023-2025 RS + trend direction)
  2. Position-specific production_score → value_scores
     (replaces league-wide percentile formula with guard/forward/center pools)
  3. Market comps override floor → value_scores
     (effective_expected_salary = max(pipeline, override); re-derives salary_efficiency_score)

After all patches, value_score is recomputed with updated components.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
TABLES = os.path.join(BASE_DIR, "data", "doc2_roster_value", "tables")

APM_PATH          = os.path.join(TABLES, "advanced_player_metrics", "advanced_player_metrics.csv")
ARCHETYPES_PATH   = os.path.join(TABLES, "player_archetypes",       "player_archetypes.csv")
VALUE_SCORES_PATH = os.path.join(TABLES, "value_scores",            "value_scores.csv")
OVERRIDE_PATH     = os.path.join(TABLES, "market_comps_override",   "market_comps_override.csv")
PM_PATH           = os.path.join(TABLES, "players_master",         "players_master_salary_ready.csv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def percentile_score(series: pd.Series, reverse: bool = False) -> pd.Series:
    """Rank-based percentile 0-100, NaN-safe. reverse=True -> lower raw = higher score."""
    s = pd.to_numeric(series, errors="coerce")
    if reverse:
        s = -s
    ranked = s.rank(pct=True, na_option="keep") * 100
    return ranked.round(1)


def safe_ratio(numerator, denominator):
    try:
        num = float(numerator)
        den = float(denominator)
        if den == 0 or np.isnan(den):
            return None
        return num / den
    except (TypeError, ValueError):
        return None


def salary_eff(gap_pct):
    """Replicate pipeline formula: max(0, min(100, 50 + 50 * -gap_pct))"""
    try:
        v = float(gap_pct)
        return round(max(0.0, min(100.0, 50.0 + 50.0 * (-v))), 2)
    except (TypeError, ValueError):
        return 50.0


def value_label(score) -> str:
    try:
        v = float(score)
    except (TypeError, ValueError):
        v = 0.0
    if v >= 80:
        return "Elite Value"
    if v >= 65:
        return "Strong Value"
    if v >= 50:
        return "Fair Value"
    if v >= 35:
        return "Risk"
    return "Overvalued"


# ---------------------------------------------------------------------------
# Patch 1: Multi-year rate trend -> player_archetypes
# ---------------------------------------------------------------------------

def patch_multiyear_trends(pa: pd.DataFrame, apm: pd.DataFrame) -> pd.DataFrame:
    """
    Add ast_pct_yr2023/24/25, ts_pct_yr2023/24/25, usage_pct_yr2023/24/25,
    and ast_pct_trend_dir to player_archetypes.
    Source: APM table (Regular Season rows for 2023, 2024, 2025).
    """
    print("  [1] Applying multi-year trend columns to player_archetypes...")

    rs = apm[apm["season_type"] == "Regular Season"][
        ["player_id", "season", "ast_pct", "ts_pct", "usage_pct"]
    ].copy()
    rs["player_id"] = rs["player_id"].astype(str)
    pa["player_id"] = pa["player_id"].astype(str)

    # Drop any prior patch columns to avoid duplicate suffix issues
    for stat in ("ast_pct", "ts_pct", "usage_pct"):
        for yr in (2023, 2024, 2025):
            col = f"{stat}_yr{yr}"
            if col in pa.columns:
                pa.drop(columns=[col], inplace=True)

    for stat in ("ast_pct", "ts_pct", "usage_pct"):
        for yr in (2023, 2024, 2025):
            col = f"{stat}_yr{yr}"
            yr_data = (
                rs[rs["season"] == yr][["player_id", stat]]
                .rename(columns={stat: col})
            )
            pa = pa.merge(yr_data, on="player_id", how="left")

    # Trend direction based on 2023 -> 2025 AST%
    def trend_dir(row):
        v23 = pd.to_numeric(row.get("ast_pct_yr2023"), errors="coerce")
        v25 = pd.to_numeric(row.get("ast_pct_yr2025"), errors="coerce")
        if pd.isna(v23) or pd.isna(v25) or v23 == 0:
            return None
        delta_pct = (v25 - v23) / v23
        if delta_pct > 0.05:
            return "up"
        if delta_pct < -0.05:
            return "down"
        return "flat"

    if "ast_pct_trend_dir" in pa.columns:
        pa.drop(columns=["ast_pct_trend_dir"], inplace=True)
    pa["ast_pct_trend_dir"] = pa.apply(trend_dir, axis=1)

    has_2025 = pa["ast_pct_yr2025"].notna().sum()
    trend_counts = pa["ast_pct_trend_dir"].value_counts(dropna=False).to_dict()
    print(f"     ast_pct_yr2025 populated: {has_2025}/{len(pa)} players")
    print(f"     Trend direction breakdown: {trend_counts}")
    return pa


# ---------------------------------------------------------------------------
# Patch 2: Position-specific production_score -> value_scores
# ---------------------------------------------------------------------------

# Stat -> APM pctile column prefix
POS_PCTILE_MAP = {
    "ts_pct":  "ts_pctile",
    "usage":   "usage_pctile",
    "ast_pct": "ast_pctile",
    "reb_pct": "reb_pctile",
    "stl_pct": "stl_pctile",
    "blk_pct": "blk_pctile",
    "tov_pct": "tov_pctile",   # pre-reversed in APM (lower TOV -> higher pctile)
}

POS_SUFFIX = {
    "Guard":   "guard",
    "Forward": "forward",
    "Center":  "center",
}

# Weights matching build_doc2_value_chain.py production_score
PROD_COMPONENTS = [
    ("ts_pct",  1.4),
    ("usage",   0.9),
    ("ast_pct", 1.1),
    ("reb_pct", 1.0),
    ("stl_pct", 0.8),
    ("blk_pct", 0.8),
    ("mpg",     0.8),
    ("tov_pct", 1.0),
    ("hle",     0.9),
    ("onoff",   1.0),
    ("playoff_b", 0.6),
]


def compute_pos_specific_production(
    vs_row: pd.Series,
    apm_lookup: dict,
    pa_lookup: dict,
    league_pctiles: dict,
    pm_pos_lookup: dict = None,
) -> float:
    pid = str(vs_row["player_id"])
    apm_row = apm_lookup.get(pid, {})
    pa_row  = pa_lookup.get(pid, {})

    # Position priority: players_master (bio-derived) > player_archetypes > APM
    pm_pos = (pm_pos_lookup or {}).get(pid, "")
    pos = str(pm_pos or pa_row.get("position_group") or apm_row.get("position_group") or "").strip()
    pos_suffix = POS_SUFFIX.get(pos)

    components = []

    # Position-specific stats from APM
    for stat, weight in PROD_COMPONENTS:
        if stat in ("mpg", "hle", "onoff", "playoff_b"):
            continue  # handled via league_pctiles below

        pctile_base = POS_PCTILE_MAP[stat]
        val = None

        if pos_suffix:
            col = f"{pctile_base}_{pos_suffix}"
            raw = apm_row.get(col)
            try:
                v = float(raw)
                val = v if not np.isnan(v) else None
            except (TypeError, ValueError):
                val = None

        # Fallback to league-wide pos pctile (_pos suffix in APM)
        if val is None:
            col_pos = f"{pctile_base}_pos"
            raw = apm_row.get(col_pos)
            try:
                v = float(raw)
                val = v if not np.isnan(v) else None
            except (TypeError, ValueError):
                val = None

        if val is not None:
            components.append((val, weight))

    # League-wide stats from player_archetypes percentile lookup
    lp = league_pctiles.get(pid, {})
    for key, weight in [("mpg", 0.8), ("hle", 0.9), ("onoff", 1.0), ("playoff_b", 0.6)]:
        raw = lp.get(key)
        try:
            v = float(raw)
            if not np.isnan(v):
                components.append((v, weight))
        except (TypeError, ValueError):
            pass

    if not components:
        return 50.0
    score = sum(c * w for c, w in components) / sum(w for _, w in components)
    return round(float(score), 2)


def patch_position_production(vs: pd.DataFrame, apm: pd.DataFrame, pa: pd.DataFrame) -> pd.DataFrame:
    """Replace production_score with position-specific version; save original as production_score_league."""
    print("  [2] Switching production_score to position-specific percentiles...")

    # Save original
    vs["production_score_league"] = vs["production_score"].copy()

    # APM 2025 RS only
    apm_2025 = apm[
        (apm["season"] == 2025) & (apm["season_type"] == "Regular Season")
    ].copy()
    apm_2025["player_id"] = apm_2025["player_id"].astype(str)
    apm_lookup = apm_2025.set_index("player_id").to_dict(orient="index")

    # player_archetypes lookup
    pa_cp = pa.copy()
    pa_cp["player_id"] = pa_cp["player_id"].astype(str)
    pa_lookup = pa_cp.set_index("player_id").to_dict(orient="index")

    # players_master position lookup (most up-to-date positions, including bio-derived)
    pm_pos_lookup = {}
    if os.path.exists(PM_PATH):
        pm_df = pd.read_csv(PM_PATH)
        pm_df["player_id"] = pm_df["player_id"].astype(str)
        if "position_group" in pm_df.columns:
            pm_pos_lookup = pm_df.dropna(subset=["position_group"]).drop_duplicates("player_id").set_index("player_id")["position_group"].to_dict()

    # Compute league-wide percentiles for mpg / HLE / onoff / playoff_bonus
    pa_pctiles = pa_cp.copy()
    pa_pctiles["mpg_pct"]       = percentile_score(pa_pctiles["mpg"])
    pa_pctiles["hle_pct"]       = percentile_score(pa_pctiles["high_leverage_experience_score"])
    pa_pctiles["onoff_pct"]     = percentile_score(pa_pctiles["onoff_impact_score"])
    pa_pctiles["playoff_b_pct"] = percentile_score(pa_pctiles["playoff_performance_bonus"])

    league_pctiles = {}
    for _, row in pa_pctiles.iterrows():
        pid = str(row["player_id"])
        league_pctiles[pid] = {
            "mpg":       row.get("mpg_pct"),
            "hle":       row.get("hle_pct"),
            "onoff":     row.get("onoff_pct"),
            "playoff_b": row.get("playoff_b_pct"),
        }

    vs["player_id"] = vs["player_id"].astype(str)
    vs["production_score"] = vs.apply(
        lambda row: compute_pos_specific_production(row, apm_lookup, pa_lookup, league_pctiles, pm_pos_lookup),
        axis=1,
    )

    # Recompute value_score (salary_efficiency/scarcity/playoff/onoff unchanged at this step)
    vs["value_score"] = (
        vs["production_score"] * 0.42
        + vs["salary_efficiency_score"] * 0.24
        + vs["scarcity_score"] * 0.12
        + vs["playoff_score"] * 0.10
        + vs["onoff_score"] * 0.12
    ).round(2)
    vs["value_label"] = vs["value_score"].apply(value_label)

    vs["undervalued_flag"] = (vs["value_score"] >= 65) | (
        pd.to_numeric(vs.get("salary_gap_pct", 0), errors="coerce").fillna(0) > 0.10
    )
    vs["hidden_talent_flag"] = (vs["value_score"] >= 70) & (
        vs["salary_tier"].astype(str).str.contains("Minimum|Low|Rookie|Training", case=False, na=False)
    )
    vs["overvalued_flag"] = (vs["value_score"] < 45) | (
        pd.to_numeric(vs.get("salary_gap_pct", 0), errors="coerce").fillna(0) < -0.10
    )

    # Count players who received position-specific (not fallback) production scores
    n_pos_specific = vs.apply(
        lambda row: str((pm_pos_lookup or {}).get(str(row["player_id"]), "")
                        or pa_lookup.get(str(row["player_id"]), {}).get("position_group", "")
                        or "") in ("Guard", "Forward", "Center"),
        axis=1
    ).sum()
    n_pos = n_pos_specific  # kept for print statement below
    cloud_row = vs[vs["player_id"] == "204333"]
    if not cloud_row.empty:
        r = cloud_row.iloc[0]
        print(f"     Cloud: league={r['production_score_league']:.2f} -> pos-specific={r['production_score']:.2f}  value_score={r['value_score']:.2f}")
    print(f"     Players with position-specific production_score: {n_pos}/{len(vs)}")
    return vs


# ---------------------------------------------------------------------------
# Patch 3: Market comps override floor -> value_scores
# ---------------------------------------------------------------------------

def patch_market_override(vs: pd.DataFrame, override_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each player in market_comps_override.csv:
      effective_expected_salary = max(pipeline_expected, override_expected)
      Re-derive: salary_gap, salary_gap_pct, salary_efficiency_score
      Add: override_expected_salary, effective_expected_salary, override_active
      Recompute: value_score, value_label, flags
    """
    print("  [3] Wiring market comps override into value_scores...")

    vs["player_id"] = vs["player_id"].astype(str)
    vs["override_expected_salary"]  = np.nan
    vs["effective_expected_salary"] = pd.to_numeric(vs["expected_salary"], errors="coerce")
    vs["override_active"] = False

    for _, ov_row in override_df.iterrows():
        pid = str(ov_row["player_id"])
        ov_expected = pd.to_numeric(ov_row.get("expected_salary"), errors="coerce")
        if pd.isna(ov_expected):
            continue

        mask = vs["player_id"] == pid
        if not mask.any():
            print(f"     WARNING: player_id {pid} not found in value_scores, skipping.")
            continue

        vs.loc[mask, "override_expected_salary"] = ov_expected

        for idx in vs.index[mask]:
            pipeline_expected = pd.to_numeric(vs.at[idx, "expected_salary"], errors="coerce")
            effective = max(pipeline_expected, ov_expected) if pd.notna(pipeline_expected) else ov_expected
            vs.at[idx, "effective_expected_salary"] = effective
            vs.at[idx, "override_active"] = bool(effective > pipeline_expected) if pd.notna(pipeline_expected) else True

            salary = pd.to_numeric(vs.at[idx, "salary"], errors="coerce")
            gap = safe_ratio(salary - effective, effective) if pd.notna(salary) and pd.notna(effective) else None
            vs.at[idx, "salary_gap"]             = (salary - effective) if pd.notna(salary) and pd.notna(effective) else None
            vs.at[idx, "salary_gap_pct"]         = gap
            vs.at[idx, "market_discount_pct"]    = gap
            vs.at[idx, "salary_efficiency_score"] = salary_eff(gap) if gap is not None else 50.0

    # Recompute value_score after all override adjustments
    vs["value_score"] = (
        vs["production_score"] * 0.42
        + vs["salary_efficiency_score"] * 0.24
        + vs["scarcity_score"] * 0.12
        + vs["playoff_score"] * 0.10
        + vs["onoff_score"] * 0.12
    ).round(2)
    vs["value_label"] = vs["value_score"].apply(value_label)

    vs["undervalued_flag"] = (vs["value_score"] >= 65) | (
        pd.to_numeric(vs.get("salary_gap_pct", 0), errors="coerce").fillna(0) > 0.10
    )
    vs["hidden_talent_flag"] = (vs["value_score"] >= 70) & (
        vs["salary_tier"].astype(str).str.contains("Minimum|Low|Rookie|Training", case=False, na=False)
    )
    vs["overvalued_flag"] = (vs["value_score"] < 45) | (
        pd.to_numeric(vs.get("salary_gap_pct", 0), errors="coerce").fillna(0) < -0.10
    )

    n_active = int(vs["override_active"].sum())
    print(f"     Override active for {n_active} player(s)")

    for _, ov_row in override_df.iterrows():
        pid = str(ov_row["player_id"])
        row = vs[vs["player_id"] == pid]
        if not row.empty:
            r = row.iloc[0]
            flag = "ACTIVE" if r["override_active"] else "floor not reached"
            print(
                f"     {r['player_name']}: pipeline=${r['expected_salary']:,.0f}  "
                f"override=${r['override_expected_salary']:,.0f}  "
                f"effective=${r['effective_expected_salary']:,.0f}  "
                f"sal_eff={r['salary_efficiency_score']:.1f}  "
                f"value_score={r['value_score']:.2f}  [{flag}]"
            )
    return vs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("post_pipeline_patches.py")
    print("=" * 60)

    print("\nLoading tables...")
    apm         = pd.read_csv(APM_PATH)
    pa          = pd.read_csv(ARCHETYPES_PATH)
    vs          = pd.read_csv(VALUE_SCORES_PATH)
    override_df = pd.read_csv(OVERRIDE_PATH)
    print(f"  APM: {apm.shape}  |  Archetypes: {pa.shape}  |  Value scores: {vs.shape}  |  Override: {override_df.shape}")

    print("\nApplying patches...\n")
    pa = patch_multiyear_trends(pa, apm)
    vs = patch_position_production(vs, apm, pa)
    vs = patch_market_override(vs, override_df)

    print("\nSaving...")
    pa.to_csv(ARCHETYPES_PATH, index=False)
    vs.to_csv(VALUE_SCORES_PATH, index=False)
    print(f"  Saved: {ARCHETYPES_PATH}")
    print(f"  Saved: {VALUE_SCORES_PATH}")

    print("\n--- Final value scores (key players) ---")
    key_players = [
        "Natasha Cloud", "Courtney Vandersloot", "Jordin Canada",
        "Skylar Diggins", "Veronica Burton",
    ]
    summary_cols = [
        "player_name", "production_score_league", "production_score",
        "salary_efficiency_score", "override_active", "value_score", "value_label",
    ]
    existing_cols = [c for c in summary_cols if c in vs.columns]
    matches = vs[vs["player_name"].isin(key_players)][existing_cols].sort_values("value_score", ascending=False)
    if not matches.empty:
        print(matches.to_string(index=False))

    print("\n  All patches applied successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
