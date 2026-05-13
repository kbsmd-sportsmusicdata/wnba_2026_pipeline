#!/usr/bin/env python3
"""Build the Doc 2 value chain tables.

This second-stage builder consumes the already-built salary core plus the
pbpstats season tables and materializes:

- onoff_metrics
- player_archetypes
- comparable_players
- value_scores
- team_roster_grades
- market_benchmarks
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_doc2_roster_tables as base  # noqa: E402


OUTPUT_ROOT = Path("data/doc2_roster_value")
TABLE_ROOT = OUTPUT_ROOT / "tables"
QUALITY_ROOT = OUTPUT_ROOT / "quality"
PBP_ONOFF_ROOT = Path("data/pbpstats_jobs/wnba_on_off/normalized/get-on-off")
SALARY_HISTORY_SOURCE = Path("2024_2026_salaries_wnba_all_players.csv")
DEFAULT_ONOFF_SEASONS = {"2024", "2025"}
DEFAULT_ONOFF_SEASON_TYPES = ("Regular Season", "Playoffs")
FINALIZED_INPUT_LAYERS = [
    "player_season_stats",
    "advanced_player_metrics",
    "playoff_experience",
    "team_rosters",
    "team_salary_cap",
    "contracts_2026",
    "transactions_2026",
    "team_roster_history",
    "expansion_draft_2026",
]
PROVISIONAL_OUTPUT_TABLES = [
    "onoff_metrics",
    "player_archetypes",
    "comparable_players",
    "value_scores",
    "team_roster_grades",
    "market_benchmarks",
]
BUILD_SEQUENCE = {
    "final_now": [
        "player_season_stats",
        "per-season percentiles",
        "team context",
        "salary-history joins",
    ],
    "provisional_now": PROVISIONAL_OUTPUT_TABLES,
    "backfill_later": [],
}
ONOFF_SENSITIVE_TABLES = set(PROVISIONAL_OUTPUT_TABLES)
ONOFF_INVENTORY_PATTERN = re.compile(
    r"player_on_off__get-on-off__season-(?P<season>\d+)__season_type-(?P<season_type>.+?)__team_id-(?P<team_id>\d+)__player_id-(?P<player_id>[^_]+)__"
)
ONOFF_LANE_SPECS = [
    ("reg_2025", "2025", "Regular Season"),
    ("playoffs_2025", "2025", "Playoffs"),
    ("reg_2024", "2024", "Regular Season"),
    ("playoffs_2024", "2024", "Playoffs"),
]
ONOFF_LANE_FIELDS = [
    "on_minutes",
    "off_minutes",
    "onoff_sample_flag",
    "onoff_impact_score",
    "on_net_rating",
    "off_net_rating",
    "net_rating_diff",
    "pts_per100_poss_on_off",
    "assist_points_per100_poss_on_off",
    "fta_per100_poss_on_off",
    "turnovers_per100_poss_on_off",
    "assists_per100_poss_on_off",
    "ts_pct_on_off",
    "efg_pct_on_off",
    "fg3_pct_on_off",
    "usage_on_off",
    "live_ball_turnover_pct_on_off",
    "shot_quality_avg_on_off",
    "seconds_per_poss_off_on_off",
    "seconds_per_poss_def_on_off",
]
PRIMARY_REGULAR_SEASON_FIELDS = [
    "on_minutes",
    "off_minutes",
    "onoff_sample_flag",
    "onoff_impact_score",
    "on_net_rating",
    "off_net_rating",
    "net_rating_diff",
    "pts_per100_poss_on_off",
    "assist_points_per100_poss_on_off",
    "fta_per100_poss_on_off",
    "turnovers_per100_poss_on_off",
    "assists_per100_poss_on_off",
    "ts_pct_on_off",
    "efg_pct_on_off",
    "fg3_pct_on_off",
    "usage_on_off",
    "live_ball_turnover_pct_on_off",
    "shot_quality_avg_on_off",
    "seconds_per_poss_off_on_off",
    "seconds_per_poss_def_on_off",
]


PLAYER_TABLE = TABLE_ROOT / "players_master" / "players_master.csv"
TEAM_ROSTER_TABLE = TABLE_ROOT / "team_rosters" / "team_rosters.csv"
TEAM_CAP_TABLE = TABLE_ROOT / "team_salary_cap" / "team_salary_cap.csv"
CONTRACTS_TABLE = TABLE_ROOT / "contracts_2026" / "contracts_2026.csv"
PLAYER_SEASON_STATS_TABLE = TABLE_ROOT / "player_season_stats" / "player_season_stats.csv"
ADVANCED_METRICS_TABLE = TABLE_ROOT / "advanced_player_metrics" / "advanced_player_metrics.csv"
PLAYOFF_EXPERIENCE_TABLE = TABLE_ROOT / "playoff_experience" / "playoff_experience.csv"
TRANSACTIONS_TABLE = TABLE_ROOT / "transactions_2026" / "transactions_2026.csv"
TEAM_ROSTER_HISTORY_TABLE = TABLE_ROOT / "team_roster_history" / "team_roster_history.csv"


TEAM_ONOFF_STAT_ALIASES = {
    "2pt FGM Assist%": "assisted2s_pct",
    "Non Putback 2pt FGM Assist%": "non_putbacks_assisted2s_pct",
    "3pt FGM Assist%": "assisted3s_pct",
    "3pt FG%": "fg3_pct",
    "Non-Heave 3pt FG%": "non_heave_fg3_pct",
    "2pt FG%": "fg2_pct",
    "eFG%": "efg_pct",
    "TS%": "ts_pct",
    "3PAr": "fg3_a_pct",
    "% of FG3A Blocked": "fg3_a_pct_blocked",
    "% of FG2A Blocked": "fg2_a_pct_blocked",
    "Live Ball TO%": "live_ball_turnover_pct",
    "DReb% - Missed FTs": "def_ft_rebound_pct",
    "OReb% - Missed FTs": "off_ft_rebound_pct",
    "DReb% - Missed 2s": "def_two_pt_rebound_pct",
    "OReb% - Missed 2s": "off_two_pt_rebound_pct",
    "DReb% - Missed 3s": "def_three_pt_rebound_pct",
    "OReb% - Missed 3s": "off_three_pt_rebound_pct",
    "DReb% - Missed FGs": "def_fg_rebound_pct",
    "OReb% - Missed FGs": "off_fg_rebound_pct",
    "At Rim OReb%": "off_at_rim_rebound_pct",
    "Short Mid-Range OReb%": "off_short_mid_range_rebound_pct",
    "Long Mid-Range OReb%": "off_long_mid_range_rebound_pct",
    "Arc 3 OReb%": "off_arc3_rebound_pct",
    "Corner 3 OReb%": "off_corner3_rebound_pct",
    "At Rim DReb%": "def_at_rim_rebound_pct",
    "Short Mid-Range DReb%": "def_short_mid_range_rebound_pct",
    "Long Mid-Range DReb%": "def_long_mid_range_rebound_pct",
    "Arc 3 DReb%": "def_arc3_rebound_pct",
    "Corner 3 DReb%": "def_corner3_rebound_pct",
    "Blocks Recovered %": "blocks_recovered_pct",
    "Seconds Per Possession - Offense": "seconds_per_poss_off",
    "Seconds Per Possession - Defense": "seconds_per_poss_def",
    "At Rim Shot Frequency": "at_rim_frequency",
    "At Rim FG%": "at_rim_accuracy",
    "At Rim % Assisted": "at_rim_pct_assisted",
    "Short Mid Range Shot Frequency": "short_mid_range_frequency",
    "Short Mid Range FG%": "short_mid_range_accuracy",
    "Short Mid Range % Assisted": "short_mid_range_pct_assisted",
    "Long Mid Range Shot Frequency": "long_mid_range_frequency",
    "Long Mid Range FG%": "long_mid_range_accuracy",
    "Long Mid Range % Assisted": "long_mid_range_pct_assisted",
    "Corner 3 Shot Frequency": "corner3_frequency",
    "Corner 3 FG%": "corner3_accuracy",
    "Corner 3 % Assisted": "corner3_pct_assisted",
    "Arc 3 Shot Frequency": "arc3_frequency",
    "Arc 3 FG%": "arc3_accuracy",
    "Arc 3 % Assisted": "arc3_pct_assisted",
    "At Rim or 3pt Shot Frequency": "at_rim_fg3_a_frequency",
    "Non-Heave Arc 3 FG%": "non_heave_arc3_accuracy",
    "Shot Quality": "shot_quality_avg",
    "Shooting Foul Drawn Rate": "shooting_fouls_drawn_pct",
    "3pt Shooting Foul Drawn Rate": "two_pt_shooting_fouls_drawn_pct",
    "2pt Shooting Foul Drawn Rate": "three_pt_shooting_fouls_drawn_pct",
    "Second Chance Points%": "second_chance_points_pct",
    "Penalty Points%": "penalty_points_pct",
    "Penalty Possessions%": "penalty_off_poss_pct",
    "Avg 2pt Shot Distance": "avg2pt_shot_distance",
    "Avg 3pt Shot Distance": "avg3pt_shot_distance",
    "Pts per 100 Possessions": "pts_per100_poss",
    "Pts per 100 Possessions - Defense": "pts_per100_poss_def",
    "Assist Points per 100 Possessions": "assist_points_per100_poss",
    "FTA per 100 Possessions": "fta_per100_poss",
    "TOs per 100 Possessions": "turnovers_per100_poss",
    "Assists per 100 Possessions": "assists_per100_poss",
    "Pace": "pace",
    "Second Chance Efficiency": "second_chance_efficiency",
    "Penalty Efficiency": "penalty_efficiency",
    "Second Chance Possessions Per 100 Possessions": "second_chance_poss_per100",
    "First Chance Points Per 100 Possessions": "first_chance_points_per100",
    "Second Chance Points Per 100 Possessions": "second_chance_points_per100",
}

PLAYER_ONOFF_SOURCE_FIELDS = {
    "results_pts_per100_poss": "pts_per100_poss",
    "results_assist_points_per100_poss": "assist_points_per100_poss",
    "results_fta_per100_poss": "fta_per100_poss",
    "results_turnovers_per100_poss": "turnovers_per100_poss",
    "results_assists_per100_poss": "assists_per100_poss",
    "results_ts_pct": "ts_pct",
    "results_efg_pct": "efg_pct",
    "results_fg3_pct": "fg3_pct",
    "results_fg2_pct": "fg2_pct",
    "results_usage": "usage",
    "results_live_ball_turnover_pct": "live_ball_turnover_pct",
    "results_def_rebound_pct": "def_rebound_pct",
    "results_off_rebound_pct": "off_rebound_pct",
    "results_second_chance_points_pct": "second_chance_points_pct",
    "results_penalty_points_pct": "penalty_points_pct",
    "results_penalty_off_poss_pct": "penalty_off_poss_pct",
    "results_avg2pt_shot_distance": "avg2pt_shot_distance",
    "results_avg3pt_shot_distance": "avg3pt_shot_distance",
    "results_shot_quality_avg": "shot_quality_avg",
    "results_seconds_per_poss_off": "seconds_per_poss_off",
    "results_seconds_per_poss_def": "seconds_per_poss_def",
    "results_at_rim_frequency": "at_rim_frequency",
    "results_at_rim_accuracy": "at_rim_accuracy",
    "results_at_rim_pct_assisted": "at_rim_pct_assisted",
    "results_arc3_frequency": "arc3_frequency",
    "results_arc3_accuracy": "arc3_accuracy",
    "results_arc3_pct_assisted": "arc3_pct_assisted",
    "results_corner3_frequency": "corner3_frequency",
    "results_corner3_accuracy": "corner3_accuracy",
    "results_corner3_pct_assisted": "corner3_pct_assisted",
    "results_shooting_fouls_drawn_pct": "shooting_fouls_drawn_pct",
    "results_two_pt_shooting_fouls_drawn_pct": "two_pt_shooting_fouls_drawn_pct",
    "results_three_pt_shooting_fouls_drawn_pct": "three_pt_shooting_fouls_drawn_pct",
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def ensure_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    QUALITY_ROOT.mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "onoff_metrics").mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "player_archetypes").mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "comparable_players").mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "value_scores").mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "team_roster_grades").mkdir(parents=True, exist_ok=True)
    (TABLE_ROOT / "market_benchmarks").mkdir(parents=True, exist_ok=True)


def historical_salary_tier(amount: Any) -> str | None:
    value = base.safe_float(amount)
    if value is None:
        return None
    if value < 80000:
        return "Minimum"
    if value < 125000:
        return "Low"
    if value < 200000:
        return "Rotation"
    if value < 300000:
        return "Starter"
    if value < 500000:
        return "Core"
    return "Star"


def load_salary_history() -> pd.DataFrame:
    if not SALARY_HISTORY_SOURCE.exists():
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "player_name_key",
                "season",
                "season_contract_year",
                "historical_salary_latest",
                "historical_salary_median",
                "historical_salary_mean",
                "historical_salary_min",
                "historical_salary_max",
                "historical_salary_rows",
                "historical_salary_latest_season",
                "historical_salary_latest_signing",
                "historical_salary_contract_years",
                "historical_salary_tier",
            ]
        )

    frame = pd.read_csv(SALARY_HISTORY_SOURCE)
    frame = frame.copy()
    frame["season"] = pd.to_numeric(frame.get("season"), errors="coerce")
    frame["season_contract_year"] = pd.to_numeric(frame["season"], errors="coerce") + 1
    frame["player_name_key"] = frame["player_name"].map(base.normalize_name)
    frame["historical_salary"] = pd.to_numeric(frame.get("season_plusone_salary_usd"), errors="coerce")
    frame["historical_signing"] = frame.get("season_plusone_signing")
    frame = frame.dropna(subset=["player_name_key"])

    player_lookup = pd.DataFrame()
    if PLAYER_TABLE.exists():
        player_lookup = pd.read_csv(PLAYER_TABLE)
        if not player_lookup.empty and "player_name_key" not in player_lookup.columns and "player_name" in player_lookup.columns:
            player_lookup["player_name_key"] = player_lookup["player_name"].map(base.normalize_name)
        elif not player_lookup.empty and "player_name_key" in player_lookup.columns:
            player_lookup["player_name_key"] = player_lookup["player_name_key"].astype(str)
        if not player_lookup.empty:
            player_lookup = player_lookup[[col for col in ["player_id", "player_name", "player_name_key"] if col in player_lookup.columns]].dropna(subset=["player_name_key"])
            player_lookup["player_id"] = player_lookup["player_id"].astype(str)

    if not player_lookup.empty:
        frame = frame.merge(player_lookup, on="player_name_key", how="left", suffixes=("", "_master"))
    else:
        frame["player_id"] = None
        frame["player_name_master"] = frame["player_name"]

    frame = frame.dropna(subset=["player_id"]).copy()
    frame["player_id"] = frame["player_id"].astype(str)
    frame = frame.sort_values(["player_id", "season_contract_year", "season", "historical_salary"], na_position="last")

    valid = frame.dropna(subset=["historical_salary"]).copy()
    if valid.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "player_name_key",
                "season",
                "season_contract_year",
                "historical_salary_latest",
                "historical_salary_median",
                "historical_salary_mean",
                "historical_salary_min",
                "historical_salary_max",
                "historical_salary_rows",
                "historical_salary_latest_season",
                "historical_salary_latest_signing",
                "historical_salary_contract_years",
                "historical_salary_tier",
            ]
        )

    latest = (
        valid.sort_values(["player_id", "season_contract_year", "season"])
        .groupby(["player_id"], as_index=False)
        .tail(1)
        .rename(
            columns={
                "historical_salary": "historical_salary_latest",
                "season": "historical_salary_latest_season",
                "season_contract_year": "historical_salary_latest_contract_year",
                "historical_signing": "historical_salary_latest_signing",
            }
        )
    )

    summary = (
        valid.groupby(["player_id"], as_index=False)
        .agg(
            player_name=("player_name", "first"),
            player_name_key=("player_name_key", "first"),
            historical_salary_rows=("historical_salary", "count"),
            historical_salary_median=("historical_salary", "median"),
            historical_salary_mean=("historical_salary", "mean"),
            historical_salary_min=("historical_salary", "min"),
            historical_salary_max=("historical_salary", "max"),
            historical_salary_first_season=("season", "min"),
            historical_salary_last_season=("season", "max"),
            historical_salary_first_contract_year=("season_contract_year", "min"),
            historical_salary_last_contract_year=("season_contract_year", "max"),
        )
    )

    contract_years = (
        valid.dropna(subset=["season_contract_year"])
        .assign(season_contract_year=lambda frame: frame["season_contract_year"].astype(int))
        .groupby(["player_id"], as_index=False)
        .agg(
            historical_salary_contract_years=("season_contract_year", lambda series: "|".join(str(int(value)) for value in sorted(set(series.dropna().astype(int))))),
        )
    )

    summary = summary.merge(contract_years, on="player_id", how="left")
    summary = summary.merge(latest[[
        "player_id",
        "historical_salary_latest",
        "historical_salary_latest_season",
        "historical_salary_latest_contract_year",
        "historical_salary_latest_signing",
    ]], on="player_id", how="left")
    summary["historical_salary_tier"] = summary["historical_salary_latest"].apply(historical_salary_tier)
    summary["historical_salary_latest"] = pd.to_numeric(summary["historical_salary_latest"], errors="coerce")
    summary["historical_salary_median"] = pd.to_numeric(summary["historical_salary_median"], errors="coerce")
    summary["historical_salary_mean"] = pd.to_numeric(summary["historical_salary_mean"], errors="coerce")
    summary["historical_salary_min"] = pd.to_numeric(summary["historical_salary_min"], errors="coerce")
    summary["historical_salary_max"] = pd.to_numeric(summary["historical_salary_max"], errors="coerce")
    summary["historical_salary_latest_contract_year"] = pd.to_numeric(summary.get("historical_salary_latest_contract_year"), errors="coerce")
    summary["historical_salary_latest_season"] = pd.to_numeric(summary.get("historical_salary_latest_season"), errors="coerce")
    summary["historical_salary_first_season"] = pd.to_numeric(summary.get("historical_salary_first_season"), errors="coerce")
    summary["historical_salary_last_season"] = pd.to_numeric(summary.get("historical_salary_last_season"), errors="coerce")
    summary["historical_salary_first_contract_year"] = pd.to_numeric(summary.get("historical_salary_first_contract_year"), errors="coerce")
    summary["historical_salary_last_contract_year"] = pd.to_numeric(summary.get("historical_salary_last_contract_year"), errors="coerce")
    summary["player_id"] = summary["player_id"].astype(str)
    return summary.sort_values(["historical_salary_latest", "historical_salary_median"], ascending=[False, False]).reset_index(drop=True)


def build_status_for_table(table_name: str, onoff_ready: bool) -> str:
    if table_name not in ONOFF_SENSITIVE_TABLES:
        return "final"
    return "final" if onoff_ready else "provisional"


def output_files_for(base_path: Path) -> list[Path]:
    return [base_path.with_suffix(".csv"), base_path.with_suffix(".parquet")]


def clear_output_table(base_path: Path) -> None:
    for path in output_files_for(base_path):
        if path.exists():
            path.unlink()


def write_or_clear_table(df: pd.DataFrame, base_path: Path) -> list[str]:
    if df.empty:
        clear_output_table(base_path)
        return []
    return write_table(df, base_path)


def expected_onoff_inventory() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(PBP_ONOFF_ROOT.glob("player_on_off__*.csv")):
        match = ONOFF_INVENTORY_PATTERN.search(path.name)
        if not match:
            continue
        season = match.group("season")
        if season not in DEFAULT_ONOFF_SEASONS:
            continue
        season_type = match.group("season_type").replace("_", " ")
        if season_type not in DEFAULT_ONOFF_SEASON_TYPES:
            continue
        rows.append(
            {
                "season": season,
                "season_type": season_type,
                "team_id": match.group("team_id"),
                "player_id": match.group("player_id"),
                "source_file": str(path),
            }
        )
    return pd.DataFrame(rows, columns=["season", "season_type", "team_id", "player_id", "source_file"])


def build_onoff_quality_report(onoff_metrics: pd.DataFrame, team_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    required_seasons = sorted(DEFAULT_ONOFF_SEASONS)
    required_combos = [(season, season_type) for season in required_seasons for season_type in DEFAULT_ONOFF_SEASON_TYPES]

    expected = expected_onoff_inventory()
    if expected.empty:
        summary = pd.DataFrame(
            [
                {
                    "season": None,
                    "season_type": None,
                    "expected_rows": 0,
                    "actual_rows": 0,
                    "missing_rows": 0,
                    "status": "missing",
                }
            ]
        )
        return summary, pd.DataFrame(columns=["season", "season_type", "team_id", "player_id", "player_name"]), ["No expected on/off inventory found"]

    actual = onoff_metrics.copy()
    if actual.empty:
        actual = pd.DataFrame(columns=["season", "season_type", "team_id", "player_id", "player_name"])
    for column in ["season", "season_type", "team_id", "player_id", "player_name"]:
        if column not in actual.columns:
            actual[column] = None
    actual["season"] = actual["season"].astype(str)
    actual["season_type"] = actual["season_type"].astype(str)
    actual["team_id"] = actual["team_id"].astype(str)
    actual["player_id"] = actual["player_id"].astype(str)
    actual_keyed = actual[["season", "season_type", "team_id", "player_id"]].drop_duplicates()
    expected_keyed = expected[["season", "season_type", "team_id", "player_id"]].drop_duplicates()

    merged = expected_keyed.merge(actual_keyed, on=["season", "season_type", "team_id", "player_id"], how="left", indicator=True)
    missing = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])

    if not missing.empty:
        name_lookup = team_history.copy() if not team_history.empty else pd.DataFrame(columns=["season", "team_id", "player_id", "player_name"])
        for column in ["season", "team_id", "player_id"]:
            if column in name_lookup.columns:
                name_lookup[column] = name_lookup[column].astype(str)
        if "player_name" in name_lookup.columns:
            name_lookup = name_lookup[["season", "team_id", "player_id", "player_name"]].drop_duplicates()
            missing = missing.merge(name_lookup, on=["season", "team_id", "player_id"], how="left")
        else:
            missing["player_name"] = None
    else:
        missing = pd.DataFrame(columns=["season", "season_type", "team_id", "player_id", "player_name"])

    expected_grouped = expected_keyed.groupby(["season", "season_type"], dropna=False).size().reset_index(name="expected_rows")
    actual_grouped = actual_keyed.groupby(["season", "season_type"], dropna=False).size().reset_index(name="actual_rows")
    missing_grouped = missing.groupby(["season", "season_type"], dropna=False).size().reset_index(name="missing_rows")
    summary = (
        pd.DataFrame(required_combos, columns=["season", "season_type"])
        .merge(expected_grouped, on=["season", "season_type"], how="left")
        .merge(actual_grouped, on=["season", "season_type"], how="left")
        .merge(missing_grouped, on=["season", "season_type"], how="left")
        .fillna({"expected_rows": 0, "actual_rows": 0, "missing_rows": 0})
    )
    for column in ["expected_rows", "actual_rows", "missing_rows"]:
        summary[column] = summary[column].astype(int)
    summary["status"] = np.where(summary["missing_rows"] == 0, "ready", "partial")

    issues: list[str] = []
    if len(onoff_metrics) < 100:
        issues.append(f"onoff_metrics row count {len(onoff_metrics)} is below the 100-row quality bar")
    missing_combos = summary[summary["missing_rows"] > 0]
    if not missing_combos.empty:
        combo_text = "; ".join(f"{row.season} | {row.season_type}: {row.missing_rows} missing" for row in missing_combos.itertuples())
        issues.append(f"On/off inventory gaps remain after build: {combo_text}")
    return summary, missing[["season", "season_type", "team_id", "player_id", "player_name"]], issues


def canonical_player_key(frame: pd.DataFrame) -> pd.Series:
    if "player_name_key" in frame.columns:
        return frame["player_name_key"].astype(str)
    if "player_name" in frame.columns:
        return frame["player_name"].map(base.normalize_name)
    if "name" in frame.columns:
        return frame["name"].map(base.normalize_name)
    return pd.Series([None] * len(frame), index=frame.index)


def build_name_lookup(*frames: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for frame in frames:
        if frame is None or frame.empty:
            continue
        temp = frame.copy()
        if "player_name_key" not in temp.columns:
            if "player_name" in temp.columns:
                temp["player_name_key"] = temp["player_name"].map(base.normalize_name)
            elif "name" in temp.columns:
                temp["player_name_key"] = temp["name"].map(base.normalize_name)
        if "player_id" in temp.columns and "player_name" in temp.columns:
            parts.append(temp[["player_id", "player_name", "player_name_key"]].dropna(subset=["player_name_key"]))
        elif "player_id" in temp.columns and "name" in temp.columns:
            temp = temp.rename(columns={"name": "player_name"})
            parts.append(temp[["player_id", "player_name", "player_name_key"]].dropna(subset=["player_name_key"]))
    if not parts:
        return pd.DataFrame(columns=["player_id", "player_name", "player_name_key"])
    lookup = pd.concat(parts, ignore_index=True)
    lookup["player_id"] = lookup["player_id"].astype(str)
    lookup = lookup.sort_values(["player_name_key", "player_name"]).drop_duplicates("player_name_key", keep="first")
    return lookup.reset_index(drop=True)


def normalize_ids(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out.columns:
            out[column] = out[column].astype(str)
    return out


def player_name_key_from_player_id(player_id: Any) -> str | None:
    text = "" if player_id is None else str(player_id)
    if not text:
        return None
    if text.startswith("player:") and "__" in text:
        slug = text.split("player:", 1)[1].split("__", 1)[0]
        return base.normalize_name(slug.replace("_", " "))
    return None


def safe_diff(left: Any, right: Any) -> float | None:
    left_value = base.safe_float(left)
    right_value = base.safe_float(right)
    if left_value is None or right_value is None:
        return None
    return left_value - right_value


def safe_ratio(numerator: Any, denominator: Any) -> float | None:
    numerator_value = base.safe_float(numerator)
    denominator_value = base.safe_float(denominator)
    if numerator_value is None or denominator_value in (None, 0):
        return None
    return numerator_value / denominator_value


def stat_value(frame: pd.DataFrame, stat_name: str, side: str = "on") -> float | None:
    if "stat" not in frame.columns:
        return None
    match = frame[frame["stat"].astype(str).str.lower() == stat_name.lower()]
    if match.empty:
        return None
    return base.safe_float(match.iloc[0].get(side))


def aggregate_player_onoff_series(value: Any) -> dict[str, float | None]:
    parsed = base.parse_jsonish(value)
    if not isinstance(parsed, list) or not parsed:
        return {"on": None, "off": None, "on_off": None, "minutes_on": None, "minutes_off": None}
    on_values: list[float] = []
    off_values: list[float] = []
    diff_values: list[float] = []
    minutes_on_values: list[float] = []
    minutes_off_values: list[float] = []
    for item in parsed:
        if not isinstance(item, Mapping):
            continue
        on_value = base.safe_float(item.get("On"))
        off_value = base.safe_float(item.get("Off"))
        diff_value = base.safe_float(item.get("On-Off"))
        minutes_on = base.safe_float(item.get("MinutesOn"))
        minutes_off = base.safe_float(item.get("MinutesOff"))
        if on_value is not None:
            on_values.append(on_value)
        if off_value is not None:
            off_values.append(off_value)
        if diff_value is not None:
            diff_values.append(diff_value)
        if minutes_on is not None:
            minutes_on_values.append(minutes_on)
        if minutes_off is not None:
            minutes_off_values.append(minutes_off)
    def mean(values: list[float]) -> float | None:
        return round(float(sum(values) / len(values)), 3) if values else None
    return {
        "on": mean(on_values),
        "off": mean(off_values),
        "on_off": mean(diff_values),
        "minutes_on": mean(minutes_on_values),
        "minutes_off": mean(minutes_off_values),
    }


def parse_team_onoff_file(path: Path, name_lookup: pd.DataFrame) -> dict[str, Any] | None:
    frame = pd.read_csv(path)
    if frame.empty:
        return None
    row = frame.iloc[0]
    player_id = str(row.get("player_id"))
    team_id = str(row.get("team_id"))
    season = int(row.get("season")) if pd.notna(row.get("season")) else None
    season_type = str(row.get("season_type") or "Regular Season")
    request_id = str(row.get("request_id") or path.stem)

    match = name_lookup[name_lookup["player_id"] == player_id]
    if match.empty:
        fallback_key = player_name_key_from_player_id(player_id)
        match = name_lookup[name_lookup["player_name_key"] == fallback_key] if fallback_key else match
        player_name = None
        player_name_key = fallback_key
    else:
        player_name = str(match.iloc[0]["player_name"])
        player_name_key = str(match.iloc[0]["player_name_key"])
    if match.empty:
        return None
    if not player_name:
        player_name = str(match.iloc[0]["player_name"])
        player_name_key = str(match.iloc[0]["player_name_key"])

    stat_rows = frame.copy()
    stat_rows["stat"] = stat_rows["stat"].astype(str)

    record: dict[str, Any] = {
        "player_id": player_id,
        "player_name": player_name,
        "player_name_key": player_name_key,
        "team_id": team_id,
        "season": season,
        "season_type": season_type,
        "request_id": request_id,
        "request_url": row.get("request_url"),
        "request_status": row.get("request_status"),
        "source_file": str(path),
        "on_minutes": None,
        "off_minutes": None,
    }

    for stat_name, stem in TEAM_ONOFF_STAT_ALIASES.items():
        record[f"{stem}_on"] = stat_value(stat_rows, stat_name, "on")
        record[f"{stem}_off"] = stat_value(stat_rows, stat_name, "off")
        record[f"{stem}_on_off"] = stat_value(stat_rows, stat_name, "on_off")

    pts_on = record.get("pts_per100_poss_on")
    pts_off = record.get("pts_per100_poss_off")
    pts_def_on = record.get("pts_per100_poss_def_on")
    pts_def_off = record.get("pts_per100_poss_def_off")
    if pts_on is not None and pts_def_on is not None:
        record["on_net_rating"] = round(float(pts_on) - float(pts_def_on), 3)
    else:
        record["on_net_rating"] = None
    if pts_off is not None and pts_def_off is not None:
        record["off_net_rating"] = round(float(pts_off) - float(pts_def_off), 3)
    else:
        record["off_net_rating"] = None
    if record["on_net_rating"] is not None and record["off_net_rating"] is not None:
        record["net_rating_diff"] = round(float(record["on_net_rating"]) - float(record["off_net_rating"]), 3)
    else:
        record["net_rating_diff"] = None
    record["on_off_ortg_diff"] = record.get("pts_per100_poss_on_off")
    record["on_off_drtg_diff"] = record.get("pts_per100_poss_def_on_off")
    record["team_ts_diff"] = record.get("ts_pct_on_off")
    record["team_efg_diff"] = record.get("efg_pct_on_off")
    record["team_3pt_pct_diff"] = record.get("fg3_pct_on_off")
    record["team_3pa_rate_diff"] = record.get("fg3_a_pct_on_off")
    record["team_tov_pct_diff"] = record.get("live_ball_turnover_pct_on_off")
    record["team_ast_pct_diff"] = record.get("assists_per100_poss_on_off")
    record["team_oreb_pct_diff"] = record.get("off_fg_rebound_pct_on_off")
    record["team_dreb_pct_diff"] = record.get("def_fg_rebound_pct_on_off")
    record["opp_ts_diff"] = record.get("pts_per100_poss_def_on_off")
    record["opp_rim_rate_diff"] = record.get("at_rim_frequency_def_on_off")
    record["opp_3pa_rate_diff"] = None
    if record.get("arc3_frequency_def_on_off") is not None or record.get("corner3_frequency_def_on_off") is not None:
        record["opp_3pa_rate_diff"] = safe_diff(record.get("arc3_frequency_def_on_off"), 0) or 0
        corner = base.safe_float(record.get("corner3_frequency_def_on_off"))
        if corner is not None:
            record["opp_3pa_rate_diff"] = round(float(record["opp_3pa_rate_diff"]) + float(corner), 3)
    record["pace_diff"] = record.get("pace_on_off")
    record["onoff_sample_flag"] = onoff_sample_flag(record.get("on_minutes"), record.get("off_minutes"))
    record["onoff_impact_score"] = onoff_impact_score(record)
    return record


def parse_player_onoff_file(path: Path, name_lookup: pd.DataFrame) -> dict[str, Any] | None:
    frame = pd.read_csv(path)
    if frame.empty:
        return None
    row = frame.iloc[0]
    player_id = str(row.get("player_id"))
    team_id = str(row.get("team_id"))
    season = int(row.get("season")) if pd.notna(row.get("season")) else None
    season_type = str(row.get("season_type") or "Regular Season")
    request_id = str(row.get("request_id") or path.stem)

    match = name_lookup[name_lookup["player_id"] == player_id]
    if match.empty:
        fallback_key = player_name_key_from_player_id(player_id)
        match = name_lookup[name_lookup["player_name_key"] == fallback_key] if fallback_key else match
    if match.empty:
        return None
    player_name = str(match.iloc[0]["player_name"])
    player_name_key = str(match.iloc[0]["player_name_key"])

    record: dict[str, Any] = {
        "player_id": player_id,
        "player_name": player_name,
        "player_name_key": player_name_key,
        "team_id": team_id,
        "season": season,
        "season_type": season_type,
        "request_id": request_id,
        "request_url": row.get("request_url"),
        "request_status": row.get("request_status"),
        "source_file": str(path),
        "on_minutes": None,
        "off_minutes": None,
    }

    # Use the teammate distribution as a player-context proxy when only the
    # contextual player_on_off files are available.
    for source_col, out_stem in PLAYER_ONOFF_SOURCE_FIELDS.items():
        if source_col not in frame.columns:
            continue
        aggregate = aggregate_player_onoff_series(row.get(source_col))
        record[f"{out_stem}_on"] = aggregate["on"]
        record[f"{out_stem}_off"] = aggregate["off"]
        record[f"{out_stem}_on_off"] = aggregate["on_off"]
        if record["on_minutes"] is None and aggregate["minutes_on"] is not None:
            record["on_minutes"] = aggregate["minutes_on"]
        if record["off_minutes"] is None and aggregate["minutes_off"] is not None:
            record["off_minutes"] = aggregate["minutes_off"]

    if record.get("pts_per100_poss_on") is not None and record.get("pts_per100_poss_def_on") is not None:
        record["on_net_rating"] = round(float(record["pts_per100_poss_on"]) - float(record["pts_per100_poss_def_on"]), 3)
    else:
        record["on_net_rating"] = None
    if record.get("pts_per100_poss_off") is not None and record.get("pts_per100_poss_def_off") is not None:
        record["off_net_rating"] = round(float(record["pts_per100_poss_off"]) - float(record["pts_per100_poss_def_off"]), 3)
    else:
        record["off_net_rating"] = None
    if record["on_net_rating"] is not None and record["off_net_rating"] is not None:
        record["net_rating_diff"] = round(float(record["on_net_rating"]) - float(record["off_net_rating"]), 3)
    else:
        record["net_rating_diff"] = None
    record["on_off_ortg_diff"] = record.get("pts_per100_poss_on_off")
    record["on_off_drtg_diff"] = record.get("pts_per100_poss_def_on_off")
    record["team_ts_diff"] = record.get("ts_pct_on_off")
    record["team_efg_diff"] = record.get("efg_pct_on_off")
    record["team_3pt_pct_diff"] = record.get("fg3_pct_on_off")
    record["team_3pa_rate_diff"] = record.get("fg3_a_pct_on_off")
    record["team_tov_pct_diff"] = record.get("live_ball_turnover_pct_on_off")
    record["team_ast_pct_diff"] = record.get("assists_per100_poss_on_off")
    record["team_oreb_pct_diff"] = record.get("off_rebound_pct_on_off")
    record["team_dreb_pct_diff"] = record.get("def_rebound_pct_on_off")
    record["opp_ts_diff"] = record.get("pts_per100_poss_def_on_off")
    record["opp_rim_rate_diff"] = record.get("at_rim_frequency_def_on_off")
    record["opp_3pa_rate_diff"] = None
    if record.get("arc3_frequency_def_on_off") is not None or record.get("corner3_frequency_def_on_off") is not None:
        record["opp_3pa_rate_diff"] = (record.get("arc3_frequency_def_on_off") or 0) + (record.get("corner3_frequency_def_on_off") or 0)
    record["pace_diff"] = record.get("seconds_per_poss_off_on_off")
    record["onoff_sample_flag"] = onoff_sample_flag(record.get("on_minutes"), record.get("off_minutes"))
    record["onoff_impact_score"] = onoff_impact_score(record)
    return record


def onoff_sample_flag(minutes_on: float | None, minutes_off: float | None) -> str:
    total = (minutes_on or 0.0) + (minutes_off or 0.0)
    if total < 100:
        return "small"
    if total < 500:
        return "medium"
    return "large"


def onoff_impact_score(row: dict[str, Any]) -> float | None:
    features = {
        "pts_per100_poss_on_off": 1.0,
        "ts_pct_on_off": 90.0,
        "efg_pct_on_off": 90.0,
        "usage_on_off": 40.0,
        "assists_per100_poss_on_off": 12.0,
        "turnovers_per100_poss_on_off": -12.0,
        "live_ball_turnover_pct_on_off": -20.0,
        "seconds_per_poss_off_on_off": -2.0,
        "seconds_per_poss_def_on_off": 2.0,
        "shot_quality_avg_on_off": 90.0,
    }
    score = 50.0
    weight_total = 0.0
    for field, weight in features.items():
        value = base.safe_float(row.get(field))
        if value is None:
            continue
        score += value * weight
        weight_total += abs(weight)
    if weight_total == 0:
        return None
    return round(max(0.0, min(100.0, score)), 2)


def build_onoff_metrics(players_master: pd.DataFrame) -> pd.DataFrame:
    team_history = pd.read_csv(TEAM_ROSTER_HISTORY_TABLE) if TEAM_ROSTER_HISTORY_TABLE.exists() else pd.DataFrame()
    team_rosters = pd.read_csv(TEAM_ROSTER_TABLE) if TEAM_ROSTER_TABLE.exists() else pd.DataFrame()
    name_lookup = build_name_lookup(players_master, team_history, team_rosters)
    team_paths = sorted(PBP_ONOFF_ROOT.glob("team_on_off__*.csv"))
    player_paths = sorted(PBP_ONOFF_ROOT.glob("player_on_off__*.csv"))

    team_records: list[dict[str, Any]] = []
    for path in team_paths:
        record = parse_team_onoff_file(path, name_lookup)
        if record:
            team_records.append(record)

    player_records: list[dict[str, Any]] = []
    for path in player_paths:
        record = parse_player_onoff_file(path, name_lookup)
        if record:
            player_records.append(record)

    if not team_records and not player_records:
        return pd.DataFrame(columns=["player_id", "player_name", "team_id", "season", "season_type"])
    records = team_records if len(team_records) >= len(player_records) else player_records
    frame = pd.DataFrame(records)
    if "season" in frame.columns:
        frame["season"] = frame["season"].astype(str)
        frame = frame[frame["season"].isin(DEFAULT_ONOFF_SEASONS)].copy()
    frame = frame.sort_values(["season", "team_id", "player_name"]).reset_index(drop=True)
    return frame


def choose_lane_rows(onoff_metrics: pd.DataFrame) -> pd.DataFrame:
    if onoff_metrics.empty:
        return pd.DataFrame(columns=["player_id", "season", "season_type"])
    frame = onoff_metrics.copy()
    frame["player_id"] = frame["player_id"].astype(str)
    frame["season"] = frame["season"].astype(str)
    frame["season_type"] = frame["season_type"].astype(str)
    frame = frame[frame["season"].isin(DEFAULT_ONOFF_SEASONS) & frame["season_type"].isin(DEFAULT_ONOFF_SEASON_TYPES)].copy()
    frame["on_minutes_numeric"] = pd.to_numeric(frame.get("on_minutes"), errors="coerce").fillna(0.0)
    frame["off_minutes_numeric"] = pd.to_numeric(frame.get("off_minutes"), errors="coerce").fillna(0.0)
    frame["lane_total_minutes"] = frame["on_minutes_numeric"] + frame["off_minutes_numeric"]
    frame = frame.sort_values(
        ["player_id", "season", "season_type", "lane_total_minutes", "team_id", "request_id", "source_file"],
        ascending=[True, False, True, False, False, False, False],
        na_position="last",
    )
    return frame.drop_duplicates(["player_id", "season", "season_type"], keep="first").reset_index(drop=True)


def build_onoff_feature_lanes(players_master: pd.DataFrame, onoff_metrics: pd.DataFrame) -> pd.DataFrame:
    player_ids = players_master[["player_id"]].copy()
    player_ids["player_id"] = player_ids["player_id"].astype(str)
    player_ids = player_ids.drop_duplicates().reset_index(drop=True)

    if onoff_metrics.empty:
        return player_ids

    best_rows = choose_lane_rows(onoff_metrics)
    lane_features = player_ids.copy()
    for prefix, season, season_type in ONOFF_LANE_SPECS:
        subset = best_rows[(best_rows["season"] == season) & (best_rows["season_type"] == season_type)].copy()
        if subset.empty:
            continue
        keep_columns = ["player_id"] + [column for column in ONOFF_LANE_FIELDS if column in subset.columns]
        subset = subset[keep_columns].copy()
        subset = subset.rename(columns={column: f"{prefix}_{column}" for column in keep_columns if column != "player_id"})
        lane_features = lane_features.merge(subset, on="player_id", how="left")

    for prefix, _season, _season_type in ONOFF_LANE_SPECS:
        for field in ONOFF_LANE_FIELDS:
            column = f"{prefix}_{field}"
            if column not in lane_features.columns:
                lane_features[column] = None

    lane_features["primary_regular_season_lane"] = np.where(
        pd.to_numeric(lane_features.get("reg_2025_onoff_impact_score"), errors="coerce").notna(),
        "reg_2025",
        np.where(pd.to_numeric(lane_features.get("reg_2024_onoff_impact_score"), errors="coerce").notna(), "reg_2024", None),
    )
    for field in PRIMARY_REGULAR_SEASON_FIELDS:
        lane_features[field] = lane_features.get(f"reg_2025_{field}")
        if f"reg_2024_{field}" in lane_features.columns:
            lane_features[field] = lane_features[field].combine_first(lane_features.get(f"reg_2024_{field}"))
    return lane_features


def build_playoff_performance_features(players_master: pd.DataFrame, player_season_stats: pd.DataFrame) -> pd.DataFrame:
    player_frame = players_master[["player_id", "position_group"]].copy()
    player_frame["player_id"] = player_frame["player_id"].astype(str)
    player_frame = player_frame.drop_duplicates("player_id").reset_index(drop=True)

    if player_season_stats.empty:
        for column in [
            "reg_2025_ts_pct",
            "playoffs_2025_ts_pct",
            "playoff_ts_pct_percentile",
            "playoff_ts_pct_vs_reg_delta",
            "playoff_performance_flag",
            "playoff_performance_bonus",
        ]:
            player_frame[column] = None
        return player_frame

    stats = player_season_stats.copy()
    stats["player_id"] = stats["player_id"].astype(str)
    stats["season"] = pd.to_numeric(stats["season"], errors="coerce")
    stats["minutes"] = pd.to_numeric(stats.get("minutes"), errors="coerce")
    stats["ts_pct"] = pd.to_numeric(stats.get("ts_pct"), errors="coerce")
    stats["season_type"] = stats["season_type"].astype(str)
    stats = stats.merge(player_frame, on="player_id", how="left")

    reg = (
        stats[(stats["season"] == 2025) & (stats["season_type"] == "Regular Season")][["player_id", "ts_pct", "minutes"]]
        .rename(columns={"ts_pct": "reg_2025_ts_pct", "minutes": "reg_2025_minutes"})
        .drop_duplicates("player_id")
    )
    playoffs = (
        stats[(stats["season"] == 2025) & (stats["season_type"] == "Playoffs")][["player_id", "position_group", "ts_pct", "minutes"]]
        .rename(columns={"ts_pct": "playoffs_2025_ts_pct", "minutes": "playoffs_2025_minutes"})
        .drop_duplicates("player_id")
    )
    playoff_pool = playoffs[(playoffs["playoffs_2025_minutes"].fillna(0) > 0) & playoffs["playoffs_2025_ts_pct"].notna()].copy()
    if not playoff_pool.empty:
        playoff_pool["playoff_ts_pct_percentile"] = playoff_pool.groupby("position_group")["playoffs_2025_ts_pct"].rank(pct=True) * 100.0
    else:
        playoff_pool["playoff_ts_pct_percentile"] = pd.Series(dtype=float)

    features = player_frame.merge(reg, on="player_id", how="left").merge(
        playoff_pool[["player_id", "playoffs_2025_ts_pct", "playoffs_2025_minutes", "playoff_ts_pct_percentile"]],
        on="player_id",
        how="left",
    )
    features["playoff_ts_pct_vs_reg_delta"] = pd.to_numeric(features["playoffs_2025_ts_pct"], errors="coerce") - pd.to_numeric(features["reg_2025_ts_pct"], errors="coerce")
    percentile_component = pd.to_numeric(features["playoff_ts_pct_percentile"], errors="coerce").fillna(0.0)
    delta_component = (pd.to_numeric(features["playoff_ts_pct_vs_reg_delta"], errors="coerce").fillna(0.0) * 1000.0).clip(lower=0.0, upper=15.0)
    minutes_component = pd.to_numeric(features["playoffs_2025_minutes"], errors="coerce").fillna(0.0).clip(upper=200.0) / 2.0
    features["playoff_performance_bonus"] = (percentile_component * 0.65 + delta_component * 1.5 + minutes_component * 0.10).clip(lower=0.0, upper=100.0).round(2)
    features["playoff_performance_flag"] = (
        (pd.to_numeric(features["playoff_ts_pct_percentile"], errors="coerce").fillna(0.0) >= 90.0)
        & (pd.to_numeric(features["playoffs_2025_minutes"], errors="coerce").fillna(0.0) >= 20.0)
    )
    return features


def service_band(years_service: Any) -> str | None:
    value = base.safe_float(years_service)
    if value is None:
        return None
    if value <= 1:
        return "rookie_scale"
    if value <= 3:
        return "early_career"
    if value <= 6:
        return "prime"
    if value <= 9:
        return "veteran"
    return "senior"


def role_band(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    return text


def skill_signature(row: pd.Series) -> str:
    ts = base.safe_float(row.get("ts_pct")) or 0.0
    usage = base.safe_float(row.get("usage")) or 0.0
    ast = base.safe_float(row.get("ast_pct")) or 0.0
    reb = base.safe_float(row.get("reb_pct")) or 0.0
    blk = base.safe_float(row.get("blk_pct")) or 0.0
    three_par = base.safe_float(row.get("three_par")) or 0.0
    rim = base.safe_float(row.get("rim_rate")) or 0.0
    if ast >= 0.18 and usage >= 0.20:
        return "creator"
    if three_par >= 0.45 and ts >= 0.55:
        return "spacing"
    if reb >= 0.18 and blk >= 0.04:
        return "paint_anchor"
    if reb >= 0.14 and ast >= 0.12:
        return "connector"
    if ts >= 0.58 and usage <= 0.18:
        return "efficient_support"
    if rim >= 0.28:
        return "rim_pressure"
    return "balanced"


def archetype_confidence(row: pd.Series) -> float:
    signals = 0
    for col in ["position_group", "archetype", "usage", "ts_pct", "ast_pct", "reb_pct"]:
        if pd.notna(row.get(col)):
            signals += 1
    if pd.notna(row.get("onoff_impact_score")):
        signals += 1
    return round(min(0.95, 0.45 + signals * 0.08), 2)


def archetype_reason(row: pd.Series) -> str:
    reasons = []
    if base.safe_float(row.get("ast_pct")) and base.safe_float(row.get("ast_pct")) >= 0.18:
        reasons.append("playmaking")
    if base.safe_float(row.get("three_par")) and base.safe_float(row.get("three_par")) >= 0.45:
        reasons.append("three-point volume")
    if base.safe_float(row.get("reb_pct")) and base.safe_float(row.get("reb_pct")) >= 0.16:
        reasons.append("rebounding")
    if base.safe_float(row.get("blk_pct")) and base.safe_float(row.get("blk_pct")) >= 0.04:
        reasons.append("rim protection")
    if base.safe_float(row.get("ts_pct")) and base.safe_float(row.get("ts_pct")) >= 0.55:
        reasons.append("efficiency")
    if not reasons:
        reasons.append("balanced profile")
    return ", ".join(reasons[:3])


def build_player_archetypes(
    players_master: pd.DataFrame,
    onoff_features: pd.DataFrame,
    playoff_performance: pd.DataFrame,
) -> pd.DataFrame:
    frame = players_master.copy()
    frame["player_id"] = frame["player_id"].astype(str)
    if not onoff_features.empty:
        onoff_features = onoff_features.copy()
        onoff_features["player_id"] = onoff_features["player_id"].astype(str)
        frame = frame.merge(onoff_features, on="player_id", how="left")
    if not playoff_performance.empty:
        playoff_performance = playoff_performance.copy()
        playoff_performance["player_id"] = playoff_performance["player_id"].astype(str)
        frame = frame.merge(playoff_performance.drop(columns=["position_group"], errors="ignore"), on="player_id", how="left")

    frame["archetype_family"] = frame["position_group"].fillna(frame.apply(base.infer_position_group, axis=1))
    frame["archetype_label"] = frame["archetype"].fillna(frame.apply(base.infer_archetype, axis=1))
    frame["role_band"] = frame["projected_role"].fillna(frame["actual_role"]).map(role_band)
    frame["service_band"] = frame["years_service"].map(service_band)
    frame["skill_signature"] = frame.apply(skill_signature, axis=1)
    frame["archetype_confidence"] = frame.apply(archetype_confidence, axis=1)
    frame["archetype_reason"] = frame.apply(archetype_reason, axis=1)
    frame["salary_band_rank"] = pd.to_numeric(frame.get("salary_as_pct_cap"), errors="coerce")
    output_columns = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "season",
        "position_group",
        "salary_tier",
        "salary",
        "cap_hit",
        "salary_as_pct_cap",
        "archetype_family",
        "archetype_label",
        "role_band",
        "service_band",
        "skill_signature",
        "archetype_confidence",
        "archetype_reason",
        "usage",
        "ts_pct",
        "mpg",
        "tov_pct",
        "ast_pct",
        "reb_pct",
        "stl_pct",
        "blk_pct",
        "three_par",
        "rim_rate",
        "playoff_games_career",
        "playoff_minutes_career",
        "high_leverage_experience_score",
        "onoff_impact_score",
        "onoff_sample_flag",
        "on_minutes",
        "off_minutes",
        "primary_regular_season_lane",
        "reg_2025_onoff_impact_score",
        "reg_2025_on_minutes",
        "reg_2025_off_minutes",
        "reg_2025_on_net_rating",
        "reg_2025_off_net_rating",
        "reg_2025_net_rating_diff",
        "reg_2025_ts_pct_on_off",
        "reg_2025_efg_pct_on_off",
        "reg_2025_usage_on_off",
        "playoffs_2025_onoff_impact_score",
        "playoffs_2025_on_minutes",
        "playoffs_2025_off_minutes",
        "playoffs_2025_on_net_rating",
        "playoffs_2025_off_net_rating",
        "playoffs_2025_net_rating_diff",
        "playoffs_2025_ts_pct_on_off",
        "playoffs_2025_efg_pct_on_off",
        "playoffs_2025_usage_on_off",
        "reg_2024_onoff_impact_score",
        "reg_2024_on_minutes",
        "reg_2024_off_minutes",
        "reg_2024_on_net_rating",
        "reg_2024_off_net_rating",
        "reg_2024_net_rating_diff",
        "reg_2024_ts_pct_on_off",
        "reg_2024_efg_pct_on_off",
        "reg_2024_usage_on_off",
        "playoffs_2024_onoff_impact_score",
        "playoffs_2024_on_minutes",
        "playoffs_2024_off_minutes",
        "playoffs_2024_on_net_rating",
        "playoffs_2024_off_net_rating",
        "playoffs_2024_net_rating_diff",
        "playoffs_2024_ts_pct_on_off",
        "playoffs_2024_efg_pct_on_off",
        "playoffs_2024_usage_on_off",
        "reg_2025_ts_pct",
        "playoffs_2025_ts_pct",
        "playoff_ts_pct_percentile",
        "playoff_ts_pct_vs_reg_delta",
        "playoff_performance_flag",
        "playoff_performance_bonus",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def percentile_score(series: pd.Series, reverse: bool = False) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.dropna().empty:
        return pd.Series([50.0] * len(values), index=values.index)
    ranks = values.rank(pct=True)
    if reverse:
        ranks = 1.0 - ranks
    return (ranks * 100).round(2).fillna(50.0)


def comparable_feature_frame(player_archetypes: pd.DataFrame) -> pd.DataFrame:
    frame = player_archetypes.copy()
    numeric_cols = [
        "salary_as_pct_cap",
        "usage",
        "ts_pct",
        "ast_pct",
        "reb_pct",
        "stl_pct",
        "blk_pct",
        "three_par",
        "rim_rate",
        "playoff_games_career",
        "playoff_minutes_career",
        "high_leverage_experience_score",
        "onoff_impact_score",
        "on_minutes",
        "off_minutes",
        "playoff_performance_bonus",
        "playoff_ts_pct_percentile",
        "playoff_ts_pct_vs_reg_delta",
    ]
    for column in numeric_cols:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    return frame


def build_comparable_players(player_archetypes: pd.DataFrame) -> pd.DataFrame:
    frame = comparable_feature_frame(player_archetypes)
    weights = {
        "usage": 1.2,
        "ts_pct": 1.4,
        "ast_pct": 1.2,
        "reb_pct": 1.0,
        "stl_pct": 0.8,
        "blk_pct": 0.8,
        "three_par": 1.0,
        "rim_rate": 0.8,
        "playoff_games_career": 0.5,
        "high_leverage_experience_score": 0.7,
        "salary_as_pct_cap": 0.9,
        "onoff_impact_score": 1.0,
        "playoff_performance_bonus": 0.6,
    }
    feat_cols = list(weights.keys())
    values = frame[feat_cols].copy()
    for column in feat_cols:
        if values[column].notna().any():
            values[column] = values[column].fillna(values[column].median())
        else:
            values[column] = 0.0
    z_values = pd.DataFrame(index=values.index)
    for column in feat_cols:
        col = pd.to_numeric(values[column], errors="coerce")
        std = col.std(ddof=0)
        if std and not math.isclose(std, 0.0):
            z_values[column] = (col - col.mean()) / std
        else:
            z_values[column] = 0.0

    groups = frame["archetype_family"].fillna("Unknown")
    role_groups = frame["role_band"].fillna("Unknown")
    records: list[dict[str, Any]] = []
    for idx, row in frame.iterrows():
        candidate_mask = (groups == groups.loc[idx]) & (frame["player_id"] != row["player_id"])
        if candidate_mask.sum() < 5:
            candidate_mask = (role_groups == role_groups.loc[idx]) & (frame["player_id"] != row["player_id"])
        if candidate_mask.sum() < 5:
            candidate_mask = frame["player_id"] != row["player_id"]
        candidates = frame[candidate_mask].copy()
        if candidates.empty:
            continue
        diffs = np.abs(z_values.loc[candidates.index, feat_cols].values - z_values.loc[idx, feat_cols].values)
        weight_arr = np.array([weights[col] for col in feat_cols], dtype=float)
        distances = (diffs * weight_arr).sum(axis=1) / weight_arr.sum()
        scores = np.clip(100.0 - distances * 16.0, 0.0, 100.0)
        candidates = candidates.assign(_similarity_score=scores)
        candidates = candidates.sort_values(["_similarity_score", "salary"], ascending=[False, True]).head(5)
        for rank, (_, comp) in enumerate(candidates.iterrows(), start=1):
            records.append(
                {
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "team_id": row["team_id"],
                    "team_name": row["team_name"],
                    "season": row["season"],
                    "player_archetype": row["archetype_label"],
                    "player_role_band": row["role_band"],
                    "comparable_player_id": comp["player_id"],
                    "comparable_player_name": comp["player_name"],
                    "comparable_team_id": comp["team_id"],
                    "comparable_team_name": comp["team_name"],
                    "comparable_archetype": comp["archetype_label"],
                    "comparable_role_band": comp["role_band"],
                    "comp_rank": rank,
                    "similarity_score": round(float(comp["_similarity_score"]), 2),
                    "same_team_flag": row["team_id"] == comp["team_id"],
                    "same_archetype_family_flag": row["archetype_family"] == comp["archetype_family"],
                    "same_salary_tier_flag": row["salary_tier"] == comp["salary_tier"],
                    "salary_gap": safe_diff(row["salary"], comp["salary"]),
                    "salary_gap_pct": safe_ratio(safe_diff(row["salary"], comp["salary"]), comp["salary"]),
                    "usage_gap": safe_diff(row["usage"], comp["usage"]),
                    "ts_gap": safe_diff(row["ts_pct"], comp["ts_pct"]),
                    "ast_gap": safe_diff(row["ast_pct"], comp["ast_pct"]),
                    "reb_gap": safe_diff(row["reb_pct"], comp["reb_pct"]),
                    "playoff_gap": safe_diff(row["high_leverage_experience_score"], comp["high_leverage_experience_score"]),
                    "onoff_gap": safe_diff(row["onoff_impact_score"], comp["onoff_impact_score"]),
                    "playoff_performance_gap": safe_diff(row.get("playoff_performance_bonus"), comp.get("playoff_performance_bonus")),
                    "comp_basis": f"{row['archetype_family'] or row['role_band']} similarity",
                }
            )
    return pd.DataFrame(records)


def build_value_scores(
    player_archetypes: pd.DataFrame,
    comparable_players: pd.DataFrame,
    salary_history_lookup: pd.DataFrame,
) -> pd.DataFrame:
    frame = player_archetypes.copy()
    frame["player_id"] = frame["player_id"].astype(str)
    comp_summary = pd.DataFrame(columns=["player_id", "expected_salary", "comp_count"])
    if not comparable_players.empty:
        comp_top = comparable_players.sort_values(["player_id", "comp_rank"]).groupby("player_id").head(5).copy()
        comp_with_salary = comp_top.merge(
            frame[["player_id", "salary"]].rename(columns={"player_id": "comparable_player_id", "salary": "comparable_salary"}),
            on="comparable_player_id",
            how="left",
        )
        comp_summary = (
            comp_with_salary.groupby("player_id", as_index=False)
            .agg(
                comp_count=("comparable_player_id", "count"),
                expected_salary=("comparable_salary", "median"),
            )
            .reset_index(drop=True)
        )

    frame = frame.merge(comp_summary, on="player_id", how="left")
    if not salary_history_lookup.empty:
        salary_history_lookup = salary_history_lookup.copy()
        salary_history_lookup["player_id"] = salary_history_lookup["player_id"].astype(str)
        frame = frame.merge(salary_history_lookup, on="player_id", how="left", suffixes=("", "_salary_history"))
    else:
        for column in [
            "historical_salary_latest",
            "historical_salary_median",
            "historical_salary_mean",
            "historical_salary_min",
            "historical_salary_max",
            "historical_salary_rows",
            "historical_salary_latest_season",
            "historical_salary_latest_contract_year",
            "historical_salary_latest_signing",
            "historical_salary_contract_years",
            "historical_salary_tier",
        ]:
            frame[column] = None

    if "expected_salary" not in frame.columns:
        frame["expected_salary"] = None
    if "comp_count" not in frame.columns:
        frame["comp_count"] = None
    frame["salary_history_reference_salary"] = pd.to_numeric(frame.get("historical_salary_latest"), errors="coerce").combine_first(
        pd.to_numeric(frame.get("historical_salary_median"), errors="coerce")
    )
    frame["salary_history_gap"] = pd.to_numeric(frame["salary"], errors="coerce") - frame["salary_history_reference_salary"]
    frame["salary_history_gap_pct"] = frame.apply(
        lambda row: safe_ratio(safe_diff(row.get("salary"), row.get("salary_history_reference_salary")), row.get("salary_history_reference_salary")),
        axis=1,
    )
    frame["salary_history_expected_salary"] = frame["salary_history_reference_salary"]
    frame["expected_salary_source"] = "comparables"
    fallback_mask = frame["comp_count"].fillna(0).astype(float) < 3
    fallback_mask |= frame["expected_salary"].isna()
    frame.loc[fallback_mask, "expected_salary"] = frame.loc[fallback_mask, "salary_history_expected_salary"]
    frame.loc[fallback_mask, "expected_salary_source"] = np.where(
        frame.loc[fallback_mask, "salary_history_expected_salary"].notna(),
        "salary_history",
        "current_salary",
    )

    percentile_cols = {
        "ts_pct": percentile_score(frame["ts_pct"]),
        "usage": percentile_score(frame["usage"]),
        "ast_pct": percentile_score(frame["ast_pct"]),
        "reb_pct": percentile_score(frame["reb_pct"]),
        "stl_pct": percentile_score(frame["stl_pct"]),
        "blk_pct": percentile_score(frame["blk_pct"]),
        "mpg": percentile_score(frame["mpg"]),
        "tov_pct": percentile_score(frame["tov_pct"], reverse=True),
        "high_leverage_experience_score": percentile_score(frame["high_leverage_experience_score"]),
        "onoff_impact_score": percentile_score(frame["onoff_impact_score"]),
        "playoff_performance_bonus": percentile_score(frame["playoff_performance_bonus"]),
    }
    for key, values in percentile_cols.items():
        frame[f"{key}_pct"] = values

    archetype_counts = frame["archetype_family"].fillna("Unknown").value_counts(dropna=False)
    max_count = float(archetype_counts.max() or 1)
    frame["scarcity_score"] = frame["archetype_family"].fillna("Unknown").map(lambda value: round((1.0 - (archetype_counts.get(value, 0) / max_count)) * 100.0, 2))

    def production_score(row: pd.Series) -> float:
        components = [
            row.get("ts_pct_pct"),
            row.get("usage_pct"),
            row.get("ast_pct_pct"),
            row.get("reb_pct_pct"),
            row.get("stl_pct_pct"),
            row.get("blk_pct_pct"),
            row.get("mpg_pct"),
            row.get("tov_pct_pct"),
            row.get("high_leverage_experience_score_pct"),
            row.get("onoff_impact_score_pct"),
            row.get("playoff_performance_bonus_pct"),
        ]
        weights = [1.4, 0.9, 1.1, 1.0, 0.8, 0.8, 0.8, 1.0, 0.9, 1.0, 0.6]
        available = [(comp, weight) for comp, weight in zip(components, weights) if pd.notna(comp)]
        if not available:
            return 50.0
        score = sum(comp * weight for comp, weight in available) / sum(weight for _, weight in available)
        return round(float(score), 2)

    frame["production_score"] = frame.apply(production_score, axis=1)

    def onoff_score(row: pd.Series) -> float:
        feats = [
            row.get("pts_per100_poss_on_off"),
            row.get("ts_pct_on_off"),
            row.get("efg_pct_on_off"),
            row.get("usage_on_off"),
            row.get("assists_per100_poss_on_off"),
            row.get("turnovers_per100_poss_on_off"),
            row.get("live_ball_turnover_pct_on_off"),
            row.get("seconds_per_poss_off_on_off"),
            row.get("seconds_per_poss_def_on_off"),
            row.get("shot_quality_avg_on_off"),
        ]
        weights = [1.0, 1.2, 1.0, 0.7, 0.8, -0.7, -0.7, -0.6, 0.4, 0.6]
        score = 50.0
        total = 0.0
        for feat, weight in zip(feats, weights):
            if pd.isna(feat):
                continue
            score += feat * weight
            total += abs(weight)
        if total == 0:
            return 50.0
        return round(max(0.0, min(100.0, score)), 2)

    if "pts_per100_poss_on_off" in frame.columns:
        frame["onoff_score_raw"] = frame.apply(onoff_score, axis=1)
        frame["onoff_score"] = percentile_score(frame["onoff_score_raw"])
    else:
        frame["onoff_score_raw"] = None
        frame["onoff_score"] = 50.0

    if frame["expected_salary"].notna().any():
        frame["salary_gap"] = pd.to_numeric(frame["salary"], errors="coerce") - pd.to_numeric(frame["expected_salary"], errors="coerce")
        frame["salary_gap_pct"] = frame.apply(
            lambda row: safe_ratio(safe_diff(row.get("salary"), row.get("expected_salary")), row.get("expected_salary")),
            axis=1,
        )
        frame["salary_efficiency_score"] = frame["salary_gap_pct"].fillna(0).apply(lambda value: round(max(0.0, min(100.0, 50.0 + 50.0 * (-value))), 2))
    else:
        frame["salary_gap"] = None
        frame["salary_gap_pct"] = None
        frame["salary_efficiency_score"] = 50.0

    frame["playoff_performance_score"] = frame["playoff_performance_bonus_pct"].fillna(50.0)
    frame["playoff_score"] = (
        frame["high_leverage_experience_score_pct"].fillna(50.0) * 0.75
        + frame["playoff_performance_score"] * 0.25
    ).round(2)
    frame["value_score"] = (
        frame["production_score"] * 0.42
        + frame["salary_efficiency_score"] * 0.24
        + frame["scarcity_score"] * 0.12
        + frame["playoff_score"] * 0.10
        + frame["onoff_score"] * 0.12
    ).round(2)

    def value_label(score: Any) -> str:
        value = base.safe_float(score) or 0.0
        if value >= 80:
            return "Elite Value"
        if value >= 65:
            return "Strong Value"
        if value >= 50:
            return "Fair Value"
        if value >= 35:
            return "Risk"
        return "Overvalued"

    frame["value_label"] = frame["value_score"].apply(value_label)
    frame["undervalued_flag"] = (frame["value_score"] >= 65) | (frame["salary_gap_pct"].fillna(0) > 0.10)
    frame["hidden_talent_flag"] = (frame["value_score"] >= 70) & (frame["salary_tier"].astype(str).str.contains("Minimum|Low|Rookie|Training", case=False, na=False))
    frame["overvalued_flag"] = (frame["value_score"] < 45) | (frame["salary_gap_pct"].fillna(0) < -0.10)
    frame["recommended_salary_low"] = frame["expected_salary"].fillna(pd.to_numeric(frame["salary"], errors="coerce")) * 0.85
    frame["recommended_salary_high"] = frame["expected_salary"].fillna(pd.to_numeric(frame["salary"], errors="coerce")) * 1.15
    frame["value_gap"] = frame["expected_salary"] - pd.to_numeric(frame["salary"], errors="coerce")
    frame["market_discount_pct"] = frame["salary_gap_pct"]
    output_columns = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "season",
        "salary_tier",
        "salary",
        "cap_hit",
        "expected_salary_source",
        "expected_salary",
        "salary_history_reference_salary",
        "salary_history_gap",
        "salary_history_gap_pct",
        "historical_salary_latest",
        "historical_salary_median",
        "historical_salary_mean",
        "historical_salary_min",
        "historical_salary_max",
        "historical_salary_rows",
        "historical_salary_latest_season",
        "historical_salary_latest_contract_year",
        "historical_salary_latest_signing",
        "historical_salary_contract_years",
        "historical_salary_tier",
        "recommended_salary_low",
        "recommended_salary_high",
        "salary_gap",
        "salary_gap_pct",
        "market_discount_pct",
        "production_score",
        "salary_efficiency_score",
        "scarcity_score",
        "playoff_performance_score",
        "playoff_score",
        "onoff_score",
        "value_score",
        "value_label",
        "undervalued_flag",
        "hidden_talent_flag",
        "overvalued_flag",
        "archetype_family",
        "archetype_label",
        "role_band",
        "service_band",
        "skill_signature",
        "comp_count",
        "playoff_ts_pct_percentile",
        "playoff_ts_pct_vs_reg_delta",
        "playoff_performance_flag",
        "playoff_performance_bonus",
        "reg_2025_onoff_impact_score",
        "playoffs_2025_onoff_impact_score",
        "reg_2024_onoff_impact_score",
        "playoffs_2024_onoff_impact_score",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def role_entropy(series: pd.Series) -> float:
    values = series.fillna("Unknown").value_counts(normalize=True)
    if values.empty:
        return 0.0
    entropy = -(values * np.log(values)).sum()
    max_entropy = math.log(len(values)) if len(values) > 1 else 1.0
    if max_entropy == 0:
        return 0.0
    return round(float(entropy / max_entropy * 100.0), 2)


def build_team_roster_grades(value_scores: pd.DataFrame, team_rosters: pd.DataFrame, team_caps: pd.DataFrame, transactions: pd.DataFrame, team_history: pd.DataFrame) -> pd.DataFrame:
    team_rosters = team_rosters.copy()
    team_rosters["player_id"] = team_rosters["player_id"].astype(str)
    value_scores = value_scores.copy()
    value_scores["player_id"] = value_scores["player_id"].astype(str)
    team_caps = team_caps.copy()
    team_caps["team_id"] = team_caps["team_id"].astype(str)

    tx = transactions.copy()
    tx["from_team_name"] = tx["from_team"].astype(str)
    tx["to_team_name"] = tx["to_team"].astype(str)

    history = team_history.copy()
    history["team_name"] = history["team_name"].astype(str)
    history["player_name_key"] = history["player_name"].map(base.normalize_name)

    rows: list[dict[str, Any]] = []
    for team_id, roster in team_rosters.groupby("team_id"):
        team_name = roster["team_name"].iloc[0]
        team_cap = team_caps[team_caps["team_id"] == str(team_id)]
        cap_row = team_cap.iloc[0] if not team_cap.empty else None
        roster_value = roster.merge(value_scores, on=["player_id", "player_name", "team_id", "team_name", "season"], how="left", suffixes=("", "_value"))
        roster_value["value_score"] = pd.to_numeric(roster_value.get("value_score"), errors="coerce")
        roster_value["salary"] = pd.to_numeric(roster_value.get("salary"), errors="coerce")
        roster_value["salary_tier"] = roster_value.get("salary_tier")
        roster_value["role_band"] = roster_value.get("projected_role").fillna(roster_value.get("actual_role"))
        current_names = set(roster_value["player_name"].map(base.normalize_name))
        history_matches = history[(history["team_name"] == team_name) & (history["player_name_key"].isin(current_names))]
        continuity_score = round((len(history_matches["player_name_key"].unique()) / max(1, roster_value["player_name"].nunique())) * 100.0, 2)
        tx_count = 0
        if not tx.empty:
            tx_count = int(((tx["from_team_name"] == team_name) | (tx["to_team_name"] == team_name)).sum())
        ro = roster_value.copy()
        if ro.empty:
            continue
        row = {
            "season": int(ro["season"].iloc[0]) if pd.notna(ro["season"].iloc[0]) else 2026,
            "team_id": team_id,
            "team_name": team_name,
            "team_abbreviation": ro["team_abbreviation"].iloc[0] if "team_abbreviation" in ro.columns else None,
            "roster_count": int(ro["player_id"].nunique()),
            "salary_cap": base.safe_float(cap_row.get("salary_cap")) if cap_row is not None else None,
            "total_cap_hit": base.safe_float(cap_row.get("total_cap_hit")) if cap_row is not None else None,
            "cap_space": base.safe_float(cap_row.get("cap_space")) if cap_row is not None else None,
            "cap_used_pct": base.safe_float(cap_row.get("cap_used_pct")) if cap_row is not None else None,
            "avg_value_score": round(ro["value_score"].mean(), 2),
            "median_value_score": round(ro["value_score"].median(), 2),
            "top_5_value_score_avg": round(ro["value_score"].sort_values(ascending=False).head(5).mean(), 2),
            "undervalued_players": int(ro["undervalued_flag"].fillna(False).sum()),
            "hidden_talent_players": int(ro["hidden_talent_flag"].fillna(False).sum()),
            "overvalued_players": int(ro["overvalued_flag"].fillna(False).sum()),
            "archetype_diversity": int(ro["archetype_family"].fillna("Unknown").nunique()),
            "role_entropy": role_entropy(ro["role_band"]),
            "continuity_score": continuity_score,
            "transaction_count": tx_count,
        }
        row["value_per_million"] = round((ro["value_score"].sum() / max(base.safe_float(row.get("total_cap_hit")) or 1.0, 1.0)) * 1_000_000.0, 2)
        rows.append(row)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["cap_efficiency_score"] = percentile_score(frame["value_per_million"])
    frame["balance_score"] = percentile_score(frame["role_entropy"])
    frame["continuity_score_rank"] = percentile_score(frame["continuity_score"])
    frame["transaction_penalty"] = percentile_score(frame["transaction_count"], reverse=True)
    frame["roster_grade_score"] = (
        frame["avg_value_score"] * 0.35
        + frame["top_5_value_score_avg"] * 0.20
        + frame["cap_efficiency_score"] * 0.20
        + frame["balance_score"] * 0.10
        + frame["continuity_score_rank"] * 0.10
        + frame["transaction_penalty"] * 0.05
    ).round(2)

    def roster_grade(score: Any) -> str:
        value = base.safe_float(score) or 0.0
        if value >= 80:
            return "A"
        if value >= 70:
            return "B"
        if value >= 60:
            return "C"
        if value >= 50:
            return "D"
        return "F"

    frame["roster_grade"] = frame["roster_grade_score"].apply(roster_grade)
    return frame[
        [
            "season",
            "team_id",
            "team_name",
            "team_abbreviation",
            "roster_count",
            "salary_cap",
            "total_cap_hit",
            "cap_space",
            "cap_used_pct",
            "avg_value_score",
            "median_value_score",
            "top_5_value_score_avg",
            "undervalued_players",
            "hidden_talent_players",
            "overvalued_players",
            "archetype_diversity",
            "role_entropy",
            "continuity_score",
            "transaction_count",
            "value_per_million",
            "cap_efficiency_score",
            "balance_score",
            "continuity_score_rank",
            "transaction_penalty",
            "roster_grade_score",
            "roster_grade",
        ]
    ].copy()


def experience_band(years_service: Any) -> str | None:
    value = base.safe_float(years_service)
    if value is None:
        return None
    if value <= 1:
        return "rookie_scale"
    if value <= 3:
        return "early_career"
    if value <= 6:
        return "prime"
    return "veteran"


def build_market_benchmarks(player_archetypes: pd.DataFrame, value_scores: pd.DataFrame) -> pd.DataFrame:
    frame = player_archetypes.merge(
        value_scores[
            [
                "player_id",
                "value_score",
                "value_label",
                "production_score",
                "salary_efficiency_score",
                "playoff_performance_score",
                "playoff_score",
                "onoff_score",
                "salary_gap_pct",
                "salary_history_reference_salary",
                "salary_history_gap",
                "salary_history_gap_pct",
                "historical_salary_latest",
                "historical_salary_median",
                "historical_salary_tier",
                "expected_salary_source",
                "recommended_salary_low",
                "recommended_salary_high",
                "undervalued_flag",
                "hidden_talent_flag",
                "overvalued_flag",
            ]
        ],
        on="player_id",
        how="left",
        suffixes=("", "_value"),
    )
    frame["experience_band"] = frame["service_band"].map(lambda value: value or "unknown")
    frame["salary_tier"] = frame["salary_tier"].fillna("Unknown")
    frame["archetype_family"] = frame["archetype_family"].fillna("Unknown")
    frame["role_band"] = frame["role_band"].fillna("Unknown")
    groups = ["archetype_family", "role_band", "salary_tier"]
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(groups, dropna=False):
        archetype_family, role_band_value, salary_tier = keys
        rows.append(
            {
                "archetype_family": archetype_family,
                "role_band": role_band_value,
                "salary_tier": salary_tier,
                "player_count": int(len(group)),
                "median_salary": round(pd.to_numeric(group["salary"], errors="coerce").median(), 2),
                "mean_salary": round(pd.to_numeric(group["salary"], errors="coerce").mean(), 2),
                "median_value_score": round(pd.to_numeric(group["value_score"], errors="coerce").median(), 2),
                "median_production_score": round(pd.to_numeric(group["production_score"], errors="coerce").median(), 2),
                "median_salary_efficiency_score": round(pd.to_numeric(group["salary_efficiency_score"], errors="coerce").median(), 2),
                "median_playoff_performance_score": round(pd.to_numeric(group["playoff_performance_score"], errors="coerce").median(), 2),
                "median_playoff_score": round(pd.to_numeric(group["playoff_score"], errors="coerce").median(), 2),
                "median_onoff_score": round(pd.to_numeric(group["onoff_score"], errors="coerce").median(), 2),
                "median_mpg": round(pd.to_numeric(group["mpg"], errors="coerce").median(), 2),
                "median_usage": round(pd.to_numeric(group["usage"], errors="coerce").median(), 4),
                "median_ts_pct": round(pd.to_numeric(group["ts_pct"], errors="coerce").median(), 4),
                "median_salary_as_pct_cap": round(pd.to_numeric(group["salary_as_pct_cap"], errors="coerce").median(), 4),
                "median_historical_salary_reference": round(pd.to_numeric(group["salary_history_reference_salary"], errors="coerce").median(), 2),
                "median_historical_salary_gap": round(pd.to_numeric(group["salary_history_gap"], errors="coerce").median(), 2),
                "median_historical_salary_gap_pct": round(pd.to_numeric(group["salary_history_gap_pct"], errors="coerce").median(), 4),
                "median_historical_salary_latest": round(pd.to_numeric(group["historical_salary_latest"], errors="coerce").median(), 2),
                "median_historical_salary_median": round(pd.to_numeric(group["historical_salary_median"], errors="coerce").median(), 2),
                "median_playoff_games": round(pd.to_numeric(group["playoff_games_career"], errors="coerce").median(), 2),
                "median_playoff_minutes": round(pd.to_numeric(group["playoff_minutes_career"], errors="coerce").median(), 2),
                "undervalued_rate": round(group["undervalued_flag"].fillna(False).mean(), 4),
                "hidden_talent_rate": round(group["hidden_talent_flag"].fillna(False).mean(), 4),
                "overvalued_rate": round(group["overvalued_flag"].fillna(False).mean(), 4),
                "historical_salary_tier_mode": group["historical_salary_tier"].mode(dropna=True).iloc[0] if not group["historical_salary_tier"].mode(dropna=True).empty else None,
                "expected_salary_source_mode": group["expected_salary_source"].mode(dropna=True).iloc[0] if not group["expected_salary_source"].mode(dropna=True).empty else None,
                "service_band_mode": group["service_band"].mode(dropna=True).iloc[0] if not group["service_band"].mode(dropna=True).empty else None,
                "value_band_mode": group["value_label"].mode(dropna=True).iloc[0] if not group["value_label"].mode(dropna=True).empty else None,
                "recommended_salary_low": round(pd.to_numeric(group["recommended_salary_low"], errors="coerce").median(), 2),
                "recommended_salary_high": round(pd.to_numeric(group["recommended_salary_high"], errors="coerce").median(), 2),
            }
        )
    return pd.DataFrame(rows).sort_values(["archetype_family", "role_band", "salary_tier"]).reset_index(drop=True)


def write_table(df: pd.DataFrame, base_path: Path) -> list[str]:
    return base.write_table(df, base_path)


def source_manifest() -> dict[str, Any]:
    return {
        "players_master": str(PLAYER_TABLE),
        "team_rosters": str(TEAM_ROSTER_TABLE),
        "team_salary_cap": str(TEAM_CAP_TABLE),
        "contracts_2026": str(CONTRACTS_TABLE),
        "player_season_stats": str(PLAYER_SEASON_STATS_TABLE),
        "advanced_player_metrics": str(ADVANCED_METRICS_TABLE),
        "playoff_experience": str(PLAYOFF_EXPERIENCE_TABLE),
        "transactions_2026": str(TRANSACTIONS_TABLE),
        "team_roster_history": str(TEAM_ROSTER_HISTORY_TABLE),
        "salary_history_source": str(SALARY_HISTORY_SOURCE),
        "pbpstats_onoff_player_files": [str(path) for path in sorted(PBP_ONOFF_ROOT.glob("player_on_off__*.csv"))],
    }


def table_specs() -> dict[str, list[str]]:
    return {
        "onoff_metrics": [
            "player_id",
            "player_name",
            "team_id",
            "season",
            "season_type",
            "request_id",
            "on_minutes",
            "off_minutes",
            "pts_per100_poss_on",
            "pts_per100_poss_off",
            "pts_per100_poss_on_off",
            "assist_points_per100_poss_on",
            "assist_points_per100_poss_off",
            "assist_points_per100_poss_on_off",
            "fta_per100_poss_on",
            "fta_per100_poss_off",
            "fta_per100_poss_on_off",
            "turnovers_per100_poss_on",
            "turnovers_per100_poss_off",
            "turnovers_per100_poss_on_off",
            "assists_per100_poss_on",
            "assists_per100_poss_off",
            "assists_per100_poss_on_off",
            "ts_pct_on",
            "ts_pct_off",
            "ts_pct_on_off",
            "efg_pct_on",
            "efg_pct_off",
            "efg_pct_on_off",
            "fg3_pct_on",
            "fg3_pct_off",
            "fg3_pct_on_off",
            "fg2_pct_on",
            "fg2_pct_off",
            "fg2_pct_on_off",
            "usage_on",
            "usage_off",
            "usage_on_off",
            "live_ball_turnover_pct_on",
            "live_ball_turnover_pct_off",
            "live_ball_turnover_pct_on_off",
            "def_rebound_pct_on",
            "def_rebound_pct_off",
            "def_rebound_pct_on_off",
            "off_rebound_pct_on",
            "off_rebound_pct_off",
            "off_rebound_pct_on_off",
            "second_chance_points_pct_on",
            "second_chance_points_pct_off",
            "second_chance_points_pct_on_off",
            "penalty_points_pct_on",
            "penalty_points_pct_off",
            "penalty_points_pct_on_off",
            "penalty_off_poss_pct_on",
            "penalty_off_poss_pct_off",
            "penalty_off_poss_pct_on_off",
            "avg2pt_shot_distance_on",
            "avg2pt_shot_distance_off",
            "avg2pt_shot_distance_on_off",
            "avg3pt_shot_distance_on",
            "avg3pt_shot_distance_off",
            "avg3pt_shot_distance_on_off",
            "shot_quality_avg_on",
            "shot_quality_avg_off",
            "shot_quality_avg_on_off",
            "seconds_per_poss_off_on",
            "seconds_per_poss_off_off",
            "seconds_per_poss_off_on_off",
            "seconds_per_poss_def_on",
            "seconds_per_poss_def_off",
            "seconds_per_poss_def_on_off",
            "at_rim_frequency_on",
            "at_rim_frequency_off",
            "at_rim_frequency_on_off",
            "at_rim_accuracy_on",
            "at_rim_accuracy_off",
            "at_rim_accuracy_on_off",
            "at_rim_pct_assisted_on",
            "at_rim_pct_assisted_off",
            "at_rim_pct_assisted_on_off",
            "arc3_frequency_on",
            "arc3_frequency_off",
            "arc3_frequency_on_off",
            "arc3_accuracy_on",
            "arc3_accuracy_off",
            "arc3_accuracy_on_off",
            "arc3_pct_assisted_on",
            "arc3_pct_assisted_off",
            "arc3_pct_assisted_on_off",
            "corner3_frequency_on",
            "corner3_frequency_off",
            "corner3_frequency_on_off",
            "corner3_accuracy_on",
            "corner3_accuracy_off",
            "corner3_accuracy_on_off",
            "corner3_pct_assisted_on",
            "corner3_pct_assisted_off",
            "corner3_pct_assisted_on_off",
            "shooting_fouls_drawn_pct_on",
            "shooting_fouls_drawn_pct_off",
            "shooting_fouls_drawn_pct_on_off",
            "two_pt_shooting_fouls_drawn_pct_on",
            "two_pt_shooting_fouls_drawn_pct_off",
            "two_pt_shooting_fouls_drawn_pct_on_off",
            "three_pt_shooting_fouls_drawn_pct_on",
            "three_pt_shooting_fouls_drawn_pct_off",
            "three_pt_shooting_fouls_drawn_pct_on_off",
            "onoff_sample_flag",
            "onoff_impact_score",
        ],
        "player_archetypes": [
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "season",
        "salary_tier",
        "salary",
        "cap_hit",
        "salary_as_pct_cap",
        "position_group",
        "archetype_family",
        "archetype_label",
        "role_band",
        "service_band",
        "skill_signature",
        "archetype_confidence",
        "archetype_reason",
        "usage",
        "ts_pct",
        "mpg",
        "tov_pct",
        "ast_pct",
        "reb_pct",
        "stl_pct",
        "blk_pct",
            "three_par",
            "rim_rate",
            "playoff_games_career",
            "playoff_minutes_career",
            "high_leverage_experience_score",
            "onoff_impact_score",
            "onoff_sample_flag",
            "on_minutes",
            "off_minutes",
            "primary_regular_season_lane",
            "reg_2025_onoff_impact_score",
            "reg_2025_on_minutes",
            "reg_2025_off_minutes",
            "reg_2025_on_net_rating",
            "reg_2025_off_net_rating",
            "reg_2025_net_rating_diff",
            "reg_2025_ts_pct_on_off",
            "reg_2025_efg_pct_on_off",
            "reg_2025_usage_on_off",
            "playoffs_2025_onoff_impact_score",
            "playoffs_2025_on_minutes",
            "playoffs_2025_off_minutes",
            "playoffs_2025_on_net_rating",
            "playoffs_2025_off_net_rating",
            "playoffs_2025_net_rating_diff",
            "playoffs_2025_ts_pct_on_off",
            "playoffs_2025_efg_pct_on_off",
            "playoffs_2025_usage_on_off",
            "reg_2024_onoff_impact_score",
            "reg_2024_on_minutes",
            "reg_2024_off_minutes",
            "reg_2024_on_net_rating",
            "reg_2024_off_net_rating",
            "reg_2024_net_rating_diff",
            "reg_2024_ts_pct_on_off",
            "reg_2024_efg_pct_on_off",
            "reg_2024_usage_on_off",
            "playoffs_2024_onoff_impact_score",
            "playoffs_2024_on_minutes",
            "playoffs_2024_off_minutes",
            "playoffs_2024_on_net_rating",
            "playoffs_2024_off_net_rating",
            "playoffs_2024_net_rating_diff",
            "playoffs_2024_ts_pct_on_off",
            "playoffs_2024_efg_pct_on_off",
            "playoffs_2024_usage_on_off",
            "reg_2025_ts_pct",
            "playoffs_2025_ts_pct",
            "playoff_ts_pct_percentile",
            "playoff_ts_pct_vs_reg_delta",
            "playoff_performance_flag",
            "playoff_performance_bonus",
        ],
        "comparable_players": [
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "season",
            "player_archetype",
            "player_role_band",
            "comparable_player_id",
            "comparable_player_name",
            "comparable_team_id",
            "comparable_team_name",
            "comparable_archetype",
            "comparable_role_band",
            "comp_rank",
            "similarity_score",
            "same_team_flag",
            "same_archetype_family_flag",
            "same_salary_tier_flag",
            "salary_gap",
            "salary_gap_pct",
            "usage_gap",
            "ts_gap",
            "ast_gap",
            "reb_gap",
            "playoff_gap",
            "onoff_gap",
            "playoff_performance_gap",
            "comp_basis",
        ],
        "value_scores": [
            "player_id",
            "player_name",
            "team_id",
            "team_name",
            "season",
            "salary_tier",
            "salary",
            "cap_hit",
            "expected_salary_source",
            "expected_salary",
            "salary_history_reference_salary",
            "salary_history_gap",
            "salary_history_gap_pct",
            "historical_salary_latest",
            "historical_salary_median",
            "historical_salary_mean",
            "historical_salary_min",
            "historical_salary_max",
            "historical_salary_rows",
            "historical_salary_latest_season",
            "historical_salary_latest_contract_year",
            "historical_salary_latest_signing",
            "historical_salary_contract_years",
            "historical_salary_tier",
            "recommended_salary_low",
            "recommended_salary_high",
            "salary_gap",
            "salary_gap_pct",
            "market_discount_pct",
            "production_score",
            "salary_efficiency_score",
            "scarcity_score",
            "playoff_performance_score",
            "playoff_score",
            "onoff_score",
            "value_score",
            "value_label",
            "undervalued_flag",
            "hidden_talent_flag",
            "overvalued_flag",
            "archetype_family",
            "archetype_label",
            "role_band",
            "service_band",
            "skill_signature",
            "comp_count",
            "playoff_ts_pct_percentile",
            "playoff_ts_pct_vs_reg_delta",
            "playoff_performance_flag",
            "playoff_performance_bonus",
            "reg_2025_onoff_impact_score",
            "playoffs_2025_onoff_impact_score",
            "reg_2024_onoff_impact_score",
            "playoffs_2024_onoff_impact_score",
        ],
        "team_roster_grades": [
            "season",
            "team_id",
            "team_name",
            "team_abbreviation",
            "roster_count",
            "salary_cap",
            "total_cap_hit",
            "cap_space",
            "cap_used_pct",
            "avg_value_score",
            "median_value_score",
            "top_5_value_score_avg",
            "undervalued_players",
            "hidden_talent_players",
            "overvalued_players",
            "archetype_diversity",
            "role_entropy",
            "continuity_score",
            "transaction_count",
            "value_per_million",
            "cap_efficiency_score",
            "balance_score",
            "continuity_score_rank",
            "transaction_penalty",
            "roster_grade_score",
            "roster_grade",
        ],
        "market_benchmarks": [
            "archetype_family",
            "role_band",
            "salary_tier",
            "player_count",
            "median_salary",
            "mean_salary",
            "median_value_score",
            "median_production_score",
            "median_salary_efficiency_score",
            "median_playoff_performance_score",
            "median_playoff_score",
            "median_onoff_score",
            "median_mpg",
            "median_usage",
            "median_ts_pct",
            "median_salary_as_pct_cap",
            "median_historical_salary_reference",
            "median_historical_salary_gap",
            "median_historical_salary_gap_pct",
            "median_historical_salary_latest",
            "median_historical_salary_median",
            "median_playoff_games",
            "median_playoff_minutes",
            "undervalued_rate",
            "hidden_talent_rate",
            "overvalued_rate",
            "historical_salary_tier_mode",
            "expected_salary_source_mode",
            "service_band_mode",
            "value_band_mode",
            "recommended_salary_low",
            "recommended_salary_high",
        ],
    }


def main() -> None:
    ensure_dirs()
    players_master = normalize_ids(read_csv(PLAYER_TABLE), ["player_id", "team_id"])
    team_rosters = normalize_ids(read_csv(TEAM_ROSTER_TABLE), ["player_id", "team_id"])
    team_caps = normalize_ids(read_csv(TEAM_CAP_TABLE), ["team_id"])
    contracts = normalize_ids(read_csv(CONTRACTS_TABLE), ["player_id", "team_id"])
    player_season_stats = normalize_ids(read_csv(PLAYER_SEASON_STATS_TABLE), ["player_id", "team_id"])
    advanced_metrics = normalize_ids(read_csv(ADVANCED_METRICS_TABLE), ["player_id", "team_id"])
    playoff_experience = normalize_ids(read_csv(PLAYOFF_EXPERIENCE_TABLE), ["player_id"])
    transactions = normalize_ids(read_csv(TRANSACTIONS_TABLE), [])
    team_history = normalize_ids(read_csv(TEAM_ROSTER_HISTORY_TABLE), ["player_id", "team_id"])
    salary_history_lookup = load_salary_history()

    # Build or refresh the on/off dependency first.
    onoff_metrics = build_onoff_metrics(players_master)
    onoff_files = write_table(onoff_metrics, TABLE_ROOT / "onoff_metrics" / "onoff_metrics")
    onoff_quality, onoff_missing, onoff_issues = build_onoff_quality_report(onoff_metrics, team_history)
    onoff_quality_files = write_table(onoff_quality, QUALITY_ROOT / "onoff_validation_report")
    onoff_quality_compat_files = write_table(onoff_quality, TABLE_ROOT / "onoff_metrics" / "onoff_metrics_validation")
    onoff_missing_files = write_or_clear_table(onoff_missing, QUALITY_ROOT / "onoff_missing_keys")
    onoff_missing_compat_files = write_or_clear_table(onoff_missing, TABLE_ROOT / "onoff_metrics" / "onoff_metrics_missing_keys")
    if onoff_issues:
        raise RuntimeError("On/off quality gate failed: " + "; ".join(onoff_issues))

    onoff_ready = True

    onoff_features = build_onoff_feature_lanes(players_master, onoff_metrics)
    playoff_performance = build_playoff_performance_features(players_master, player_season_stats)
    player_archetypes = build_player_archetypes(players_master, onoff_features, playoff_performance)
    comparable_players = build_comparable_players(player_archetypes)
    value_scores = build_value_scores(player_archetypes, comparable_players, salary_history_lookup)
    team_roster_grades = build_team_roster_grades(value_scores, team_rosters, team_caps, transactions, team_history)
    market_benchmarks = build_market_benchmarks(player_archetypes, value_scores)

    tables = {
        "player_archetypes": player_archetypes,
        "comparable_players": comparable_players,
        "value_scores": value_scores,
        "team_roster_grades": team_roster_grades,
        "market_benchmarks": market_benchmarks,
    }

    written_files: dict[str, list[str]] = {}
    for table_name, df in tables.items():
        written_files[table_name] = write_table(df, TABLE_ROOT / table_name / table_name)

    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.setdefault("tables", {})
    manifest["tables"]["onoff_metrics"] = {"rows": len(onoff_metrics), "files": onoff_files}
    for table_name, df in tables.items():
        manifest["tables"][table_name] = {"rows": len(df), "files": written_files[table_name]}
    manifest["table_statuses"] = {name: build_status_for_table(name, onoff_ready) for name in manifest["tables"]}
    manifest["input_layer_statuses"] = {name: "final" for name in FINALIZED_INPUT_LAYERS}
    manifest["build_sequence"] = {
        **BUILD_SEQUENCE,
        "provisional_now": [] if onoff_ready else PROVISIONAL_OUTPUT_TABLES,
        "backfill_later": [] if onoff_ready else ["2024 regular season on/off"],
    }
    manifest["finalized_input_layers"] = FINALIZED_INPUT_LAYERS
    manifest["provisional_output_tables"] = [] if onoff_ready else PROVISIONAL_OUTPUT_TABLES
    manifest["quality_reports"] = {
        "onoff_validation_report": onoff_quality_files,
        "onoff_missing_keys": onoff_missing_files,
        "onoff_validation_report_table_compat": onoff_quality_compat_files,
        "onoff_missing_keys_table_compat": onoff_missing_compat_files,
    }
    manifest["deferred_tables"] = []
    manifest["build_status"] = "final" if onoff_ready else "provisional"
    manifest["provisional_reason"] = None if onoff_ready else "On/off coverage remains incomplete"
    manifest.setdefault("source_manifest", {})
    manifest["source_manifest"]["pbpstats_onoff_player_files"] = [str(path) for path in sorted(PBP_ONOFF_ROOT.glob("player_on_off__*.csv"))]
    manifest["source_manifest"]["salary_history_source"] = str(SALARY_HISTORY_SOURCE)
    manifest["generated_at"] = pd.Timestamp.utcnow().isoformat()

    # Coverage report refresh.
    coverage_specs = table_specs()
    coverage_rows: list[dict[str, Any]] = []
    for table_name, df in {**{"onoff_metrics": onoff_metrics}, **tables}.items():
        coverage = base.coverage_from_frame(df, coverage_specs[table_name])
        min_rows_threshold = 100 if table_name in {"onoff_metrics", "player_archetypes", "comparable_players", "value_scores"} else 1
        coverage_rows.append(
            {
                "table_name": table_name,
                "rows": len(df),
                "build_status": build_status_for_table(table_name, onoff_ready),
                "required_fields": coverage["required_fields"],
                "present_fields": coverage["present_fields"],
                "non_null_fields": coverage["non_null_fields"],
                "coverage_pct": coverage["coverage_pct"],
                "status": "ready" if len(df) >= min_rows_threshold else "partial",
                "expected_rows": None,
                "actual_rows": None,
                "missing_rows": None,
                "min_rows_threshold": min_rows_threshold,
                "quality_report_validation": None,
                "quality_report_missing_keys": None,
                "source_files": "; ".join(
                    [
                        str(PLAYER_TABLE),
                        str(TEAM_ROSTER_TABLE),
                        str(TEAM_CAP_TABLE),
                        str(CONTRACTS_TABLE),
                        str(PLAYER_SEASON_STATS_TABLE),
                        str(ADVANCED_METRICS_TABLE),
                        str(PLAYOFF_EXPERIENCE_TABLE),
                        str(TRANSACTIONS_TABLE),
                        str(TEAM_ROSTER_HISTORY_TABLE),
                        *manifest["source_manifest"]["pbpstats_onoff_player_files"][:3],
                    ]
                ),
            }
        )
    coverage_df = pd.DataFrame(coverage_rows)
    coverage_files = write_table(coverage_df, OUTPUT_ROOT / "coverage_report")
    manifest["coverage_report"] = coverage_files
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(json.dumps(
        {
            "build_status": manifest["build_status"],
            "table_statuses": manifest["table_statuses"],
            "tables": {name: len(df) for name, df in {**{"onoff_metrics": onoff_metrics}, **tables}.items()},
            "coverage_report": coverage_files,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
