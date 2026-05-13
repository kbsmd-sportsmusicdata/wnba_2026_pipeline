#!/usr/bin/env python3
"""Process current-season 2026 master tables into BI and post-game outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

import build_doc2_roster_tables
import build_doc2_value_chain


ROOT = Path(__file__).resolve().parents[1]
MASTER_ROOT = ROOT / "data" / "current_season_2026" / "masters"
OUTPUT_ROOT = ROOT / "data" / "current_season_2026" / "processed"
BI_ROOT = ROOT / "data" / "current_season_2026" / "bi_exports"

VALUE_SCORES_PATH = ROOT / "data" / "doc2_roster_value" / "tables" / "value_scores" / "value_scores.csv"
TEAM_GRADES_PATH = ROOT / "data" / "doc2_roster_value" / "tables" / "team_roster_grades" / "team_roster_grades.csv"
BIOS_PATH = ROOT / "data" / "doc2_roster_value" / "tables" / "master_player_bios" / "master_player_bios_2026.csv"


def write_table(path: Path, frame: pd.DataFrame) -> list[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path.with_suffix(".csv")
    frame.to_csv(csv_path, index=False)
    written = [str(csv_path)]
    try:
        parquet_path = path.with_suffix(".parquet")
        frame.to_parquet(parquet_path, index=False)
        written.append(str(parquet_path))
    except Exception:
        pass
    return written


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def position_bucket(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text.startswith("g"):
        return "Guard"
    if text.startswith("f"):
        return "Forward"
    if text.startswith("c"):
        return "Center"
    return str(value)


def add_position_percentiles(frame: pd.DataFrame, metric_columns: Iterable[str]) -> pd.DataFrame:
    output = frame.copy()
    output["position_group"] = output.get("position_group", pd.Series(index=output.index, dtype=object)).map(position_bucket)
    output["position_percentile_fallback_flag"] = output["position_group"].isna()
    for metric in metric_columns:
        pct_column = f"{metric}_pctile_pos"
        output[pct_column] = pd.NA
        valid_metric = pd.to_numeric(output[metric], errors="coerce")
        for position, group in output[~output["position_group"].isna()].groupby("position_group"):
            ranks = pd.to_numeric(group[metric], errors="coerce").rank(pct=True, method="average") * 100.0
            output.loc[group.index, pct_column] = ranks.round(2)
        if output["position_percentile_fallback_flag"].any():
            fallback_idx = output.index[output["position_percentile_fallback_flag"]]
            ranks = valid_metric.rank(pct=True, method="average") * 100.0
            output.loc[fallback_idx, pct_column] = ranks.loc[fallback_idx].round(2)
    return output


def build_post_game_summary(team_game_logs: pd.DataFrame, player_game_logs: pd.DataFrame, schedule_master: pd.DataFrame) -> pd.DataFrame:
    if team_game_logs.empty:
        return pd.DataFrame()
    players = player_game_logs.copy()
    if not players.empty:
        players["points"] = pd.to_numeric(players["points"], errors="coerce").fillna(0)
        top_scorers = (
            players.sort_values(["game_id", "team_id", "points", "player_name"], ascending=[True, True, False, True])
            .drop_duplicates(["game_id", "team_id"], keep="first")
            [["game_id", "team_id", "player_id", "player_name", "points"]]
            .rename(columns={"player_id": "top_scorer_id", "player_name": "top_scorer_name", "points": "top_scorer_points"})
        )
    else:
        top_scorers = pd.DataFrame(columns=["game_id", "team_id", "top_scorer_id", "top_scorer_name", "top_scorer_points"])
    summary = team_game_logs.copy()
    summary["team_points"] = pd.to_numeric(summary.get("points"), errors="coerce")
    summary = summary.merge(top_scorers, on=["game_id", "team_id"], how="left")
    if not schedule_master.empty:
        schedule = schedule_master[["season", "game_id", "game_date", "season_type"]].drop_duplicates(["season", "game_id"])
        summary = summary.merge(schedule, on=["season", "game_id"], how="left")
    summary = summary.sort_values(["game_id", "team_id"]).reset_index(drop=True)
    return summary


def build_player_current_value_summary(
    player_game_logs: pd.DataFrame,
    player_onoff: pd.DataFrame,
    bios: pd.DataFrame,
    value_scores: pd.DataFrame,
    shot_profile_summary: pd.DataFrame,
) -> pd.DataFrame:
    if player_game_logs.empty:
        return pd.DataFrame()
    logs = player_game_logs.copy()
    for column in ("points", "rebounds", "assists", "minutes"):
        logs[column] = pd.to_numeric(logs.get(column), errors="coerce")
    grouped = (
        logs.groupby(["season", "player_id", "player_name", "team_id", "team_name"], dropna=False)
        .agg(
            games_played=("game_id", "nunique"),
            points_per_game=("points", "mean"),
            rebounds_per_game=("rebounds", "mean"),
            assists_per_game=("assists", "mean"),
            minutes_per_game=("minutes", "mean"),
            latest_game_date=("game_date", "max"),
        )
        .reset_index()
    )

    bios_lookup = bios.copy()
    if not bios_lookup.empty:
        bios_lookup["player_id"] = bios_lookup["player_id"].astype(str)
        bios_lookup["position_group"] = bios_lookup.get("position", bios_lookup.get("position_full")).map(position_bucket)
        bios_lookup = bios_lookup[["player_id", "position_group", "team_2026_abbr"]].drop_duplicates("player_id")
        grouped = grouped.merge(bios_lookup, on="player_id", how="left")

    onoff_lookup = player_onoff.copy()
    if not onoff_lookup.empty:
        onoff_lookup["player_id"] = onoff_lookup["player_id"].astype(str)
        onoff_lookup["onoff_impact_score"] = pd.to_numeric(onoff_lookup.get("onoff_impact_score"), errors="coerce")
        onoff_lookup = (
            onoff_lookup.groupby("player_id", dropna=False)["onoff_impact_score"]
            .mean()
            .reset_index()
        )
        grouped = grouped.merge(onoff_lookup, on="player_id", how="left")

    value_lookup = value_scores.copy()
    if not value_lookup.empty:
        value_lookup["player_id"] = value_lookup["player_id"].astype(str)
        keep_cols = [
            "player_id",
            "salary",
            "value_score",
            "production_score",
            "salary_efficiency_score",
            "value_label",
            "undervalued_flag",
            "hidden_talent_flag",
            "overvalued_flag",
        ]
        grouped = grouped.merge(value_lookup[keep_cols].drop_duplicates("player_id"), on="player_id", how="left")

    shots = shot_profile_summary.copy()
    if not shots.empty:
        shots["player_id"] = shots["player_id"].astype(str)
        shot_keep = ["player_id", "attempts", "at_rim_frequency", "corner3_frequency", "arc3_frequency"]
        grouped = grouped.merge(shots[shot_keep].drop_duplicates("player_id"), on="player_id", how="left")

    grouped = add_position_percentiles(
        frame=grouped,
        metric_columns=("points_per_game", "rebounds_per_game", "assists_per_game", "minutes_per_game"),
    )
    return grouped.sort_values(["team_name", "player_name"]).reset_index(drop=True)


def build_bi_exports(
    player_summary: pd.DataFrame,
    team_roster_grades: pd.DataFrame,
    player_game_logs: pd.DataFrame,
    team_game_logs: pd.DataFrame,
    post_game_summary: pd.DataFrame,
    shot_profile_summary: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    game_dimension_columns = [column for column in ("season", "game_id", "game_date", "season_type") if column in post_game_summary.columns]
    return {
        "player_value_summary": player_summary.drop_duplicates(["season", "player_id"]).reset_index(drop=True),
        "player_percentile_summary": player_summary[
            [
                column
                for column in player_summary.columns
                if column in {
                    "season",
                    "player_id",
                    "player_name",
                    "team_id",
                    "team_name",
                    "position_group",
                    "position_percentile_fallback_flag",
                    "points_per_game_pctile_pos",
                    "rebounds_per_game_pctile_pos",
                    "assists_per_game_pctile_pos",
                    "minutes_per_game_pctile_pos",
                }
            ]
        ].drop_duplicates(["season", "player_id"]),
        "team_roster_grade_summary": team_roster_grades.drop_duplicates(["season", "team_id"]).reset_index(drop=True),
        "player_game_log_detail": player_game_logs.drop_duplicates(["season", "game_id", "player_id"]).reset_index(drop=True),
        "team_game_log_detail": team_game_logs.drop_duplicates(["season", "game_id", "team_id"]).reset_index(drop=True),
        "post_game_report_summary": post_game_summary.drop_duplicates(["season", "game_id", "team_id"]).reset_index(drop=True),
        "game_dimension_table": post_game_summary[game_dimension_columns].drop_duplicates(["season", "game_id"]).reset_index(drop=True),
        "shot_profile_summary": shot_profile_summary.drop_duplicates(["season", "team_id", "player_id"]).reset_index(drop=True),
    }


def run_processing(skip_doc2_refresh: bool = False) -> dict[str, Any]:
    if not skip_doc2_refresh:
        build_doc2_roster_tables.main()
        build_doc2_value_chain.main()

    player_game_logs = read_csv(MASTER_ROOT / "player_game_logs_master.csv")
    team_game_logs = read_csv(MASTER_ROOT / "team_game_logs_master.csv")
    player_onoff = read_csv(MASTER_ROOT / "player_onoff_master.csv")
    schedule_master = read_csv(MASTER_ROOT / "schedule_master.csv")
    shot_profile_summary = read_csv(MASTER_ROOT / "shot_profile_summary_master.csv")
    bios = read_csv(BIOS_PATH)
    value_scores = read_csv(VALUE_SCORES_PATH)
    team_grades = read_csv(TEAM_GRADES_PATH)

    player_summary = build_player_current_value_summary(
        player_game_logs=player_game_logs,
        player_onoff=player_onoff,
        bios=bios,
        value_scores=value_scores,
        shot_profile_summary=shot_profile_summary,
    )
    post_game_summary = build_post_game_summary(
        team_game_logs=team_game_logs,
        player_game_logs=player_game_logs,
        schedule_master=schedule_master,
    )
    exports = build_bi_exports(
        player_summary=player_summary,
        team_roster_grades=team_grades,
        player_game_logs=player_game_logs,
        team_game_logs=team_game_logs,
        post_game_summary=post_game_summary,
        shot_profile_summary=shot_profile_summary,
    )

    summary: dict[str, Any] = {"tables": {}, "skip_doc2_refresh": skip_doc2_refresh}
    summary["tables"]["player_current_value_summary"] = write_table(OUTPUT_ROOT / "player_current_value_summary", player_summary)
    summary["tables"]["post_game_summary"] = write_table(OUTPUT_ROOT / "post_game_summary", post_game_summary)
    for name, frame in exports.items():
        summary["tables"][name] = write_table(BI_ROOT / name, frame)

    manifest_path = OUTPUT_ROOT / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process current-season WNBA master tables into BI exports.")
    parser.add_argument("--skip-doc2-refresh", action="store_true", help="Skip rebuilding the Doc 2/value-chain foundation tables first.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_processing(skip_doc2_refresh=args.skip_doc2_refresh)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
