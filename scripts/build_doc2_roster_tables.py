#!/usr/bin/env python3
"""Build the first-wave Doc 2 roster-value datasets.

This script materializes the schema areas that are currently supported well
enough by the saved pbpstats outputs plus the 2026 cap-sheet and transaction
extracts:

- player_season_stats
- advanced_player_metrics
- onoff_metrics
- playoff_experience
- team_rosters
- team_roster_history
- transactions_2026
- expansion_draft_2026

The deferred schema areas are intentionally not built here.
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


OUTPUT_ROOT = Path("data/doc2_roster_value")
PBP_STATS_ROOT = Path("data/pbpstats_jobs")
SALARY_BUNDLE_ROOT = Path("wnba_2026_final_cap_validation_bundle_v2")
SALARY_VALIDATED_ROWS = SALARY_BUNDLE_ROOT / "wnba_2026_player_year_contract_status_validated.csv"
SALARY_CONTRACTS_2026 = SALARY_BUNDLE_ROOT / "contracts_2026.csv"
SALARY_TEAM_CAP = SALARY_BUNDLE_ROOT / "team_salary_cap.csv"
SALARY_VALIDATION_SUMMARY = SALARY_BUNDLE_ROOT / "validation_report_2026_summary.csv"
TRANSACTIONS_MASTER = Path("data/basketball_reference_transactions/wnba_transactions_master_current_extract.csv")
DRAFT_PICK_BASE = Path("data/basketball_reference_transactions/wnba_draft_pick_base_current_extract.csv")
CAP_SHEET_CONTRACTS = Path("wnba_2026_cap_sheet_cleaned_dataset/wnba_2026_cap_sheet_contracts_clean_long.csv")
CAP_SHEET_TEAM_SUMMARY = Path("wnba_2026_cap_sheet_cleaned_dataset/wnba_2026_team_summary_clean_long.csv")
CBA_NUMBERS = Path("wnba_2026_cap_sheet_cleaned_dataset/wnba_2026_cba_numbers_clean.csv")
SALARY_HISTORY_SOURCE = Path("2024_2026_salaries_wnba_all_players.csv")
CURRENT_TEAM_CATALOG = Path("data/pbpstats_jobs/wnba_league_discovery/derived/season_team_catalog.csv")
TEAM_PLAYER_CATALOG = Path("data/pbpstats_jobs/wnba_league_discovery/derived/team_player_catalog.csv")
TEAM_ROSTER_HISTORY = Path("data/doc2_roster_value/tables/team_roster_history/team_roster_history.csv")
ONOFF_MIN_ROWS = 100
CURRENT_ROSTER_SECTION = "current_roster"


TEAM_NAME_TO_ABBR = {
    "Atlanta Dream": "ATL",
    "Chicago Sky": "CHI",
    "Connecticut Sun": "CON",
    "Dallas Wings": "DAL",
    "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND",
    "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS",
    "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL",
    "Phoenix Mercury": "PHX",
    "Portland Fire": "POR",
    "Seattle Storm": "SEA",
    "Toronto Tempo": "TOR",
    "Washington Mystics": "WAS",
}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def write_table(df: pd.DataFrame, base_path: Path) -> list[str]:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = base_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    written = [str(csv_path)]
    try:
        parquet_path = base_path.with_suffix(".parquet")
        df.to_parquet(parquet_path, index=False)
        written.append(str(parquet_path))
    except Exception:
        pass
    return written


def slugify(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "all"


def normalize_name(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def safe_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except Exception:
        return None


def safe_int(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def to_pct_diff(value: Any) -> float | None:
    numeric = safe_float(value)
    if numeric is None:
        return None
    return round(numeric, 6)


def safe_div(numerator: Any, denominator: Any) -> float | None:
    num = safe_float(numerator)
    den = safe_float(denominator)
    if num is None or den in (None, 0):
        return None
    return round(num / den, 6)


def parse_jsonish(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        try:
            return ast.literal_eval(text)
        except Exception:
            return None


def append_note(existing: Any, addition: Any) -> str | None:
    existing_text = "" if existing is None or (isinstance(existing, float) and pd.isna(existing)) else str(existing).strip()
    addition_text = "" if addition is None or (isinstance(addition, float) and pd.isna(addition)) else str(addition).strip()
    if not addition_text:
        return existing_text or None
    if not existing_text:
        return addition_text
    if addition_text in existing_text:
        return existing_text
    return f"{existing_text} | {addition_text}"


def infer_contract_salary_tier(value: Any) -> str | None:
    salary = safe_float(value)
    if salary is None:
        return None
    if salary < 300000:
        return "Minimum / Training Camp / Draftee Band"
    if salary < 400000:
        return "Low Rotation / Rookie Scale"
    if salary < 600000:
        return "Mid-Tier Rotation"
    if salary < 920000:
        return "High/Mid Starter"
    if salary < 1190000:
        return "Premium Starter"
    return "Max / Protected Veteran Top Tier"


def latest_transaction_team_lookup(transactions: pd.DataFrame) -> dict[tuple[str, int], dict[str, Any]]:
    if transactions.empty:
        return {}
    frame = transactions.copy()
    player_column = "player_primary" if "player_primary" in frame.columns else "player_name"
    frame["player_name_key"] = frame[player_column].map(normalize_name)
    frame["season_key"] = pd.to_numeric(frame.get("season"), errors="coerce").fillna(pd.to_datetime(frame.get("transaction_date"), errors="coerce").dt.year)
    frame["season_key"] = pd.to_numeric(frame["season_key"], errors="coerce")
    frame["transaction_date_sort"] = pd.to_datetime(frame.get("transaction_date"), errors="coerce")
    frame["transaction_type_norm"] = frame.get("transaction_type", pd.Series([None] * len(frame))).astype(str).str.strip().str.lower()
    frame["target_team"] = frame.get("to_team", pd.Series([None] * len(frame))).fillna(frame.get("team_primary"))
    frame["target_team"] = frame["target_team"].astype(str).replace({"nan": None}).str.strip()
    frame = frame[
        frame["player_name_key"].astype(bool)
        & frame["season_key"].notna()
        & frame["target_team"].notna()
        & frame["transaction_type_norm"].isin({"signing", "signed", "trade", "traded"})
    ].copy()
    if frame.empty:
        return {}
    frame = frame.sort_values(
        ["player_name_key", "season_key", "transaction_date_sort"],
        ascending=[True, True, True],
        na_position="last",
    )
    frame = frame.drop_duplicates(subset=["player_name_key", "season_key"], keep="last")
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for _, row in frame.iterrows():
        season_key = safe_int(row.get("season_key"))
        if season_key is None:
            continue
        lookup[(str(row["player_name_key"]), season_key)] = row.to_dict()
    return lookup


def salary_history_lookup(salary_history: pd.DataFrame) -> dict[tuple[str, int], dict[str, Any]]:
    if salary_history.empty:
        return {}
    frame = salary_history.copy()
    frame["player_name_key"] = frame["player_name"].map(normalize_name)
    frame["season"] = pd.to_numeric(frame.get("season"), errors="coerce")
    frame["contract_season"] = frame["season"].apply(lambda value: safe_int(value) + 1 if safe_int(value) is not None else None)
    frame["season_plusone_salary_usd"] = pd.to_numeric(frame.get("season_plusone_salary_usd"), errors="coerce")
    frame = frame.dropna(subset=["player_name_key", "contract_season", "season_plusone_salary_usd"]).copy()
    if frame.empty:
        return {}
    frame = frame.sort_values(["player_name_key", "contract_season", "season"], ascending=[True, True, False])
    frame = frame.drop_duplicates(subset=["player_name_key", "contract_season"], keep="first")
    lookup: dict[tuple[str, int], dict[str, Any]] = {}
    for _, row in frame.iterrows():
        contract_season = safe_int(row.get("contract_season"))
        if contract_season is None:
            continue
        lookup[(str(row["player_name_key"]), contract_season)] = row.to_dict()
    return lookup


def team_cap_lookup(team_caps: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if team_caps.empty:
        return {}
    frame = team_caps.copy()
    if "team_name" not in frame.columns:
        return {}
    frame = frame.dropna(subset=["team_name"]).drop_duplicates(subset=["team_name"], keep="first")
    return {str(row["team_name"]): row.to_dict() for _, row in frame.iterrows()}


def reconcile_contract_context_from_transactions(
    contracts: pd.DataFrame,
    transactions: pd.DataFrame,
    salary_history: pd.DataFrame,
    team_caps: pd.DataFrame,
) -> pd.DataFrame:
    if contracts.empty:
        return contracts.copy()

    frame = contracts.copy()
    if "notes" in frame.columns:
        frame["notes"] = frame["notes"].astype("object")
    if "player_name_key" not in frame.columns:
        frame["player_name_key"] = frame["player_name"].map(normalize_name)

    transaction_lookup = latest_transaction_team_lookup(transactions)
    history_lookup = salary_history_lookup(salary_history)
    cap_lookup = team_cap_lookup(team_caps)

    for idx, row in frame.iterrows():
        player_key = str(row.get("player_name_key") or "")
        season = safe_int(row.get("season"))
        if not player_key or season is None:
            continue

        latest_tx = transaction_lookup.get((player_key, season))
        fallback_salary_row = history_lookup.get((player_key, season))
        override_team = None if latest_tx is None else latest_tx.get("target_team")

        if override_team:
            override_team = str(override_team).strip()
            if override_team and override_team != str(row.get("team_name") or "").strip():
                resolved_team_id, resolved_team_source = resolve_team_id(override_team)
                frame.at[idx, "team_name"] = override_team
                frame.at[idx, "team_id"] = resolved_team_id
                frame.at[idx, "team_id_source"] = resolved_team_source
                frame.at[idx, "team_abbreviation"] = TEAM_NAME_TO_ABBR.get(override_team)
                cap_row = cap_lookup.get(override_team, {})
                if "team_slug" in frame.columns:
                    frame.at[idx, "team_slug"] = cap_row.get("team_slug") or slugify(override_team).lower()
                tx_note = latest_tx.get("raw_text")
                if tx_note:
                    frame.at[idx, "notes"] = append_note(frame.at[idx, "notes"], tx_note)
            status_override = {
                "signing": "Signed",
                "signed": "Signed",
                "trade": "Traded",
                "traded": "Traded",
            }.get(str(latest_tx.get("transaction_type_norm") or "").strip().lower())
            if status_override:
                for status_field in ["status", "status_full", "next_status"]:
                    if status_field in frame.columns:
                        frame.at[idx, status_field] = status_override

        current_salary = safe_float(frame.at[idx, "salary"]) if "salary" in frame.columns else None
        if current_salary is None and fallback_salary_row is not None:
            fallback_salary = safe_float(fallback_salary_row.get("season_plusone_salary_usd"))
            if fallback_salary is not None:
                frame.at[idx, "salary"] = fallback_salary
                if "cap_hit" in frame.columns:
                    frame.at[idx, "cap_hit"] = fallback_salary
                current_tier = frame.at[idx, "salary_tier"] if "salary_tier" in frame.columns else None
                if "salary_tier" in frame.columns and (pd.isna(current_tier) or not str(current_tier).strip()):
                    frame.at[idx, "salary_tier"] = infer_contract_salary_tier(fallback_salary)
                if "notes" in frame.columns:
                    reference_note = f"salary fallback from {safe_int(fallback_salary_row.get('season'))} season_plusone reference"
                    frame.at[idx, "notes"] = append_note(frame.at[idx, "notes"], reference_note)

        current_salary = safe_float(frame.at[idx, "salary"]) if "salary" in frame.columns else None
        current_team_name = str(frame.at[idx, "team_name"]) if pd.notna(frame.at[idx, "team_name"]) else None
        cap_row = cap_lookup.get(current_team_name) if current_team_name else None
        if current_salary is not None and cap_row is not None:
            salary_cap = safe_float(cap_row.get("team_salary_cap"))
            team_total_salary = safe_float(cap_row.get("team_total_salary"))
            if "salary_as_pct_cap" in frame.columns and salary_cap not in (None, 0):
                frame.at[idx, "salary_as_pct_cap"] = round(current_salary / salary_cap, 6)
            if "pct_team" in frame.columns and team_total_salary not in (None, 0):
                frame.at[idx, "pct_team"] = round(current_salary / team_total_salary, 6)

        if override_team and str(row.get("row_section") or "") == CURRENT_ROSTER_SECTION:
            if "counts_toward_player_total" in frame.columns:
                frame.at[idx, "counts_toward_player_total"] = True
            if current_salary is not None and "counts_toward_salary_total" in frame.columns:
                frame.at[idx, "counts_toward_salary_total"] = True

    return frame


def build_player_lookup(totals: pd.DataFrame) -> pd.DataFrame:
    frame = totals.copy()
    frame["player_key"] = frame["name"].map(normalize_name)
    frame["player_id"] = frame["entity_id"].astype(str)
    frame["team_id"] = frame["team_id"].astype(str)
    frame["season"] = frame["season"].astype(str)
    frame["season_sort"] = frame["season"].astype(int)
    frame["games_played_sort"] = pd.to_numeric(frame.get("games_played"), errors="coerce").fillna(0)
    frame["minutes_sort"] = pd.to_numeric(frame.get("minutes"), errors="coerce").fillna(0)
    frame = frame.sort_values(["player_key", "season_sort", "games_played_sort", "minutes_sort"], ascending=[True, False, False, False])
    frame = frame.drop_duplicates(subset=["player_key"], keep="first")
    return frame[["player_key", "player_id", "name", "team_id", "team_abbreviation", "season", "season_type"]]


def build_player_identity_lookup(player_totals: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if TEAM_ROSTER_HISTORY.exists():
        history = read_csv(TEAM_ROSTER_HISTORY)
        if not history.empty:
            history = history.copy()
            history["player_name_key"] = history["player_name"].map(normalize_name)
            history["player_id"] = history["player_id"].astype(str)
            history["player_id_source"] = "team_roster_history"
            history["source_priority"] = 0
            history["season_sort"] = pd.to_numeric(history.get("season"), errors="coerce").fillna(0)
            history["season_type_sort"] = history.get("season_type", pd.Series([None] * len(history))).astype(str).map({"Regular Season": 0, "Playoffs": 1}).fillna(9)
            frames.append(history[["player_name_key", "player_id", "player_id_source", "player_name", "team_abbreviation", "team_name", "season_sort", "season_type_sort", "source_priority"]])

    if not player_totals.empty:
        totals_lookup = build_player_lookup(player_totals).copy()
        totals_lookup = totals_lookup.rename(columns={"player_key": "player_name_key", "name": "player_name"})
        totals_lookup["player_id"] = totals_lookup["player_id"].astype(str)
        totals_lookup["player_id_source"] = "pbpstats_totals"
        totals_lookup["team_name"] = None
        totals_lookup["source_priority"] = 1
        totals_lookup["season_sort"] = pd.to_numeric(totals_lookup.get("season"), errors="coerce").fillna(0)
        totals_lookup["season_type_sort"] = totals_lookup.get("season_type", pd.Series([None] * len(totals_lookup))).astype(str).map({"Regular Season": 0, "Playoffs": 1}).fillna(9)
        frames.append(totals_lookup[["player_name_key", "player_id", "player_id_source", "player_name", "team_abbreviation", "team_name", "season_sort", "season_type_sort", "source_priority"]])

    if not frames:
        return pd.DataFrame(columns=["player_name_key", "player_id", "player_id_source", "player_name", "team_abbreviation", "team_name"])

    lookup = pd.concat(frames, ignore_index=True)
    lookup = lookup.sort_values(
        ["player_name_key", "source_priority", "season_sort", "season_type_sort"],
        ascending=[True, True, False, True],
    )
    lookup = lookup.drop_duplicates(subset=["player_name_key"], keep="first")
    return lookup.drop(columns=["season_sort", "season_type_sort", "source_priority"], errors="ignore").reset_index(drop=True)


def resolve_team_id(team_name: Any) -> tuple[str, str]:
    team_name_text = "" if team_name is None else str(team_name)
    team_id = lookup_pbpstats_team_id(team_name_text)
    if team_id:
        return str(team_id), "pbpstats_catalog"
    return f"team:{slugify(team_name_text).lower()}", "synthetic_slug"


def resolve_player_id(player_name: Any, player_lookup: pd.DataFrame, team_name: Any | None = None) -> tuple[str, str]:
    key = normalize_name(player_name)
    match = player_lookup[player_lookup["player_name_key"] == key]
    if not match.empty:
        row = match.iloc[0]
        return str(row.get("player_id")), str(row.get("player_id_source") or "lookup")
    suffix = slugify(team_name).lower() if team_name is not None else "unknown_team"
    return f"player:{slugify(player_name).lower()}__{suffix}", "synthetic_name"


def build_latest_player_context(player_totals: pd.DataFrame) -> pd.DataFrame:
    if player_totals.empty:
        return pd.DataFrame()
    frame = player_totals.copy()
    frame["player_name_key"] = frame["name"].map(normalize_name)
    frame["season_sort"] = pd.to_numeric(frame.get("season"), errors="coerce").fillna(0).astype(int)
    frame["season_type_sort"] = frame.get("season_type", pd.Series([None] * len(frame))).astype(str).map({"Regular Season": 0, "Playoffs": 1}).fillna(9)
    frame["games_played_sort"] = pd.to_numeric(frame.get("games_played"), errors="coerce").fillna(0)
    frame["minutes_sort"] = pd.to_numeric(frame.get("minutes"), errors="coerce").fillna(0)
    frame = frame.sort_values(
        ["player_name_key", "season_sort", "season_type_sort", "games_played_sort", "minutes_sort"],
        ascending=[True, False, True, False, False],
    )
    frame = frame.drop_duplicates(subset=["player_name_key"], keep="first")
    frame["player_id"] = frame["entity_id"].astype(str)
    frame["team_id"] = frame["team_id"].astype(str)
    frame["team_abbreviation"] = frame["team_abbreviation"].astype(str)
    frame["player_name"] = frame["name"].astype(str)
    frame["latest_context_season"] = frame["season"].astype(str)
    frame["latest_context_season_type"] = frame["season_type"].astype(str)
    frame["games_played"] = pd.to_numeric(frame.get("games_played"), errors="coerce")
    frame["minutes"] = pd.to_numeric(frame.get("minutes"), errors="coerce")
    frame["mpg"] = frame.apply(lambda row: safe_div(row.get("minutes"), row.get("games_played")), axis=1)
    for column in ["usage", "ts_pct", "efg_pct", "ast_pct", "tov_pct", "stl_pct", "blk_pct", "reb_pct", "three_par", "rim_rate"]:
        if column not in frame.columns:
            frame[column] = None
    frame["position_group"] = frame.apply(infer_position_group, axis=1)
    frame["archetype"] = frame.apply(infer_archetype, axis=1)
    frame["projected_role"] = frame.apply(infer_role, axis=1)
    frame["actual_role"] = frame["projected_role"]
    output_columns = [
        "player_name_key",
        "player_id",
        "player_name",
        "team_id",
        "team_abbreviation",
        "latest_context_season",
        "latest_context_season_type",
        "games_played",
        "minutes",
        "mpg",
        "usage",
        "ts_pct",
        "efg_pct",
        "ast_pct",
        "tov_pct",
        "stl_pct",
        "blk_pct",
        "reb_pct",
        "three_par",
        "rim_rate",
        "position_group",
        "archetype",
        "projected_role",
        "actual_role",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def lookup_player_id(player_name: Any, player_lookup: pd.DataFrame) -> str | None:
    key = normalize_name(player_name)
    match = player_lookup[player_lookup["player_key"] == key]
    if match.empty:
        return None
    return str(match.iloc[0]["player_id"])


def lookup_pbpstats_team_id(team_name: str) -> str | None:
    abbr = TEAM_NAME_TO_ABBR.get(team_name)
    if not abbr or not CURRENT_TEAM_CATALOG.exists():
        return None
    catalog = pd.read_csv(CURRENT_TEAM_CATALOG)
    match = catalog[catalog["team_abbreviation"].astype(str) == abbr]
    if match.empty:
        return None
    return str(match.iloc[0]["team_id"])


def build_player_season_stats(player_totals: pd.DataFrame) -> pd.DataFrame:
    frame = player_totals.copy()
    frame["player_id"] = frame["entity_id"].astype(str)
    frame["player_name"] = frame["name"].astype(str)
    frame["team_id"] = frame["team_id"].astype(str)
    frame["season"] = frame["season"].astype(str)
    frame["season_type"] = frame["season_type"].astype(str)
    frame["games_played"] = pd.to_numeric(frame.get("games_played"), errors="coerce")
    frame["minutes"] = pd.to_numeric(frame.get("minutes"), errors="coerce")
    frame["mpg"] = frame.apply(lambda row: safe_div(row.get("minutes"), row.get("games_played")), axis=1)
    frame["points"] = pd.to_numeric(frame.get("points"), errors="coerce")
    frame["ppg"] = frame.apply(lambda row: safe_div(row.get("points"), row.get("games_played")), axis=1)
    frame["rebounds"] = pd.to_numeric(frame.get("rebounds"), errors="coerce")
    frame["rpg"] = frame.apply(lambda row: safe_div(row.get("rebounds"), row.get("games_played")), axis=1)
    frame["assists"] = pd.to_numeric(frame.get("assists"), errors="coerce")
    frame["apg"] = frame.apply(lambda row: safe_div(row.get("assists"), row.get("games_played")), axis=1)
    frame["steals"] = pd.to_numeric(frame.get("steals"), errors="coerce")
    frame["spg"] = frame.apply(lambda row: safe_div(row.get("steals"), row.get("games_played")), axis=1)
    frame["blocks"] = pd.to_numeric(frame.get("blocks"), errors="coerce")
    frame["bpg"] = frame.apply(lambda row: safe_div(row.get("blocks"), row.get("games_played")), axis=1)
    frame["turnovers"] = pd.to_numeric(frame.get("turnovers"), errors="coerce")
    frame["tov_pg"] = frame.apply(lambda row: safe_div(row.get("turnovers"), row.get("games_played")), axis=1)
    frame["fgm"] = pd.to_numeric(frame.get("fg2m"), errors="coerce").fillna(0) + pd.to_numeric(frame.get("fg3m"), errors="coerce").fillna(0)
    frame["fga"] = pd.to_numeric(frame.get("fg2a"), errors="coerce").fillna(0) + pd.to_numeric(frame.get("fg3a"), errors="coerce").fillna(0)
    frame["fg_pct"] = frame.apply(lambda row: safe_div(row.get("fgm"), row.get("fga")), axis=1)
    frame["three_pm"] = pd.to_numeric(frame.get("fg3m"), errors="coerce")
    frame["three_pa"] = pd.to_numeric(frame.get("fg3a"), errors="coerce")
    frame["three_pct"] = frame.apply(lambda row: safe_div(row.get("three_pm"), row.get("three_pa")), axis=1)
    frame["ftm"] = pd.to_numeric(frame.get("ft_points"), errors="coerce")
    frame["fta"] = pd.to_numeric(frame.get("fta"), errors="coerce")
    frame["ft_pct"] = frame.apply(lambda row: safe_div(row.get("ftm"), row.get("fta")), axis=1)

    output_columns = [
        "player_id",
        "player_name",
        "team_id",
        "season",
        "season_type",
        "games_played",
        "games_started",
        "minutes",
        "mpg",
        "points",
        "ppg",
        "rebounds",
        "rpg",
        "assists",
        "apg",
        "steals",
        "spg",
        "blocks",
        "bpg",
        "turnovers",
        "tov_pg",
        "fgm",
        "fga",
        "fg_pct",
        "three_pm",
        "three_pa",
        "three_pct",
        "ftm",
        "fta",
        "ft_pct",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def build_advanced_player_metrics(player_totals: pd.DataFrame) -> pd.DataFrame:
    frame = player_totals.copy()
    frame["player_id"] = frame["entity_id"].astype(str)
    frame["season"] = frame["season"].astype(str)
    frame["season_type"] = frame["season_type"].astype(str)
    frame["team_id"] = frame["team_id"].astype(str)
    if "total_poss" in frame.columns:
        frame["possessions"] = pd.to_numeric(frame["total_poss"], errors="coerce")
    else:
        frame["possessions"] = pd.to_numeric(frame.get("off_poss"), errors="coerce")

    def numeric(column: str) -> pd.Series:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce")
        return pd.Series([None] * len(frame), index=frame.index, dtype="float64")

    # Directly available metrics.
    frame["usage_pct"] = numeric("usage")
    frame["ts_pct"] = numeric("ts_pct")
    frame["efg_pct"] = numeric("efg_pct")

    # Derived possession-based rates where the exact pbpstats field is not
    # present in the saved totals files.
    frame["ast_pct"] = numeric("ast_pct")
    frame["tov_pct"] = numeric("tov_pct")
    frame["ast_tov_ratio"] = numeric("ast_tov_ratio")
    frame["oreb_pct"] = numeric("oreb_pct")
    frame["dreb_pct"] = numeric("dreb_pct")
    frame["reb_pct"] = numeric("reb_pct")
    frame["stl_pct"] = numeric("stl_pct")
    frame["blk_pct"] = numeric("blk_pct")
    frame["ftr"] = numeric("ftr")
    frame["three_par"] = numeric("three_par")
    frame["rim_rate"] = numeric("rim_rate")
    frame["midrange_rate"] = numeric("midrange_rate")
    frame["pts_per_40"] = numeric("pts_per_40")
    frame["ast_per_40"] = numeric("ast_per_40")
    frame["reb_per_40"] = numeric("reb_per_40")
    frame["stl_per_40"] = numeric("stl_per_40")
    frame["blk_per_40"] = numeric("blk_per_40")

    if "points" in frame.columns:
        frame["pts_per_40"] = frame["pts_per_40"].fillna(pd.to_numeric(frame["points"], errors="coerce") / pd.to_numeric(frame.get("minutes"), errors="coerce") * 40.0)
    if "assists" in frame.columns:
        frame["ast_per_40"] = frame["ast_per_40"].fillna(pd.to_numeric(frame["assists"], errors="coerce") / pd.to_numeric(frame.get("minutes"), errors="coerce") * 40.0)
    if "rebounds" in frame.columns:
        frame["reb_per_40"] = frame["reb_per_40"].fillna(pd.to_numeric(frame["rebounds"], errors="coerce") / pd.to_numeric(frame.get("minutes"), errors="coerce") * 40.0)
    if "steals" in frame.columns:
        frame["stl_per_40"] = frame["stl_per_40"].fillna(pd.to_numeric(frame["steals"], errors="coerce") / pd.to_numeric(frame.get("minutes"), errors="coerce") * 40.0)
    if "blocks" in frame.columns:
        frame["blk_per_40"] = frame["blk_per_40"].fillna(pd.to_numeric(frame["blocks"], errors="coerce") / pd.to_numeric(frame.get("minutes"), errors="coerce") * 40.0)

    # Approximate the schema's advanced rates from the available counts when the
    # direct pbpstats field is absent.
    minutes = pd.to_numeric(frame.get("minutes"), errors="coerce")
    frame["ast_pct"] = frame["ast_pct"].fillna(pd.to_numeric(frame.get("assists"), errors="coerce") / frame["possessions"])
    frame["tov_pct"] = frame["tov_pct"].fillna(pd.to_numeric(frame.get("turnovers"), errors="coerce") / frame["possessions"])
    frame["ast_tov_ratio"] = frame["ast_tov_ratio"].fillna(pd.to_numeric(frame.get("assists"), errors="coerce") / pd.to_numeric(frame.get("turnovers"), errors="coerce"))
    frame["oreb_pct"] = frame["oreb_pct"].fillna(pd.to_numeric(frame.get("off_rebounds"), errors="coerce") / frame["possessions"])
    frame["dreb_pct"] = frame["dreb_pct"].fillna(pd.to_numeric(frame.get("def_rebounds"), errors="coerce") / frame["possessions"])
    frame["reb_pct"] = frame["reb_pct"].fillna(pd.to_numeric(frame.get("rebounds"), errors="coerce") / frame["possessions"])
    frame["stl_pct"] = frame["stl_pct"].fillna(pd.to_numeric(frame.get("steals"), errors="coerce") / frame["possessions"])
    frame["blk_pct"] = frame["blk_pct"].fillna(pd.to_numeric(frame.get("blocks"), errors="coerce") / frame["possessions"])
    frame["ftr"] = frame["ftr"].fillna(pd.to_numeric(frame.get("fta"), errors="coerce") / pd.to_numeric(frame.get("fga"), errors="coerce"))
    frame["three_par"] = frame["three_par"].fillna(pd.to_numeric(frame.get("fg3a"), errors="coerce") / pd.to_numeric(frame.get("fga"), errors="coerce"))
    if "at_rim_fga" in frame.columns:
        frame["rim_rate"] = frame["rim_rate"].fillna(pd.to_numeric(frame.get("at_rim_fga"), errors="coerce") / pd.to_numeric(frame.get("fga"), errors="coerce"))
    if "short_mid_range_fga" in frame.columns or "long_mid_range_fga" in frame.columns:
        mid = pd.to_numeric(frame.get("short_mid_range_fga"), errors="coerce").fillna(0) + pd.to_numeric(frame.get("long_mid_range_fga"), errors="coerce").fillna(0)
        frame["midrange_rate"] = frame["midrange_rate"].fillna(mid / pd.to_numeric(frame.get("fga"), errors="coerce"))

    output_columns = [
        "player_id",
        "season",
        "season_type",
        "team_id",
        "possessions",
        "usage_pct",
        "ts_pct",
        "efg_pct",
        "ast_pct",
        "tov_pct",
        "ast_tov_ratio",
        "oreb_pct",
        "dreb_pct",
        "reb_pct",
        "stl_pct",
        "blk_pct",
        "ftr",
        "three_par",
        "rim_rate",
        "midrange_rate",
        "pts_per_40",
        "ast_per_40",
        "reb_per_40",
        "stl_per_40",
        "blk_per_40",
        "ts_pctile_pos",
        "usage_pctile_pos",
        "ast_pctile_pos",
        "tov_pctile_pos",
        "reb_pctile_pos",
        "stl_pctile_pos",
        "blk_pctile_pos",
        "production_score",
    ]
    # Season-level percentile ranks make the table useful even when position
    # tags are not present in the saved totals export.
    for season_type in sorted(frame["season_type"].dropna().astype(str).unique()):
        mask = frame["season_type"].astype(str) == season_type
        for metric_col, pct_col in [
            ("ts_pct", "ts_pctile_pos"),
            ("usage_pct", "usage_pctile_pos"),
            ("ast_pct", "ast_pctile_pos"),
            ("tov_pct", "tov_pctile_pos"),
            ("reb_pct", "reb_pctile_pos"),
            ("stl_pct", "stl_pctile_pos"),
            ("blk_pct", "blk_pctile_pos"),
        ]:
            values = pd.to_numeric(frame.loc[mask, metric_col], errors="coerce")
            if values.notna().any():
                ranks = values.rank(pct=True)
                frame.loc[mask, pct_col] = (ranks * 100).round(2)
            else:
                frame.loc[mask, pct_col] = None

    # Composite score from the percentile and efficiency blend.
    blend = (
        frame["ts_pctile_pos"].fillna(0)
        + frame["usage_pctile_pos"].fillna(0)
        + frame["ast_pctile_pos"].fillna(0)
        + (100 - frame["tov_pctile_pos"].fillna(0))
        + frame["reb_pctile_pos"].fillna(0)
        + frame["stl_pctile_pos"].fillna(0)
        + frame["blk_pctile_pos"].fillna(0)
    ) / 7.0
    frame["production_score"] = blend.round(2)
    return frame[output_columns].copy()


def aggregate_playoff_experience(player_totals: pd.DataFrame) -> pd.DataFrame:
    playoff_rows = player_totals[player_totals["season_type"].astype(str) == "Playoffs"].copy()
    if playoff_rows.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "player_name",
                "playoff_games_career",
                "playoff_starts_career",
                "playoff_minutes_career",
                "playoff_mpg_career",
                "finals_games",
                "championship_count",
                "playoff_last_3_years_games",
                "playoff_last_3_years_minutes",
                "high_leverage_experience_score",
            ]
        )
    playoff_rows["player_id"] = playoff_rows["entity_id"].astype(str)
    playoff_rows["player_name"] = playoff_rows["name"].astype(str)
    playoff_rows["games_played"] = pd.to_numeric(playoff_rows.get("games_played"), errors="coerce")
    playoff_rows["minutes"] = pd.to_numeric(playoff_rows.get("minutes"), errors="coerce")
    grouped = playoff_rows.groupby(["player_id", "player_name"], dropna=False).agg(
        playoff_games_career=("games_played", "sum"),
        playoff_minutes_career=("minutes", "sum"),
        playoff_last_3_years_games=("games_played", "sum"),
        playoff_last_3_years_minutes=("minutes", "sum"),
    ).reset_index()
    grouped["playoff_starts_career"] = None
    grouped["playoff_mpg_career"] = grouped.apply(lambda row: safe_div(row.get("playoff_minutes_career"), row.get("playoff_games_career")), axis=1)
    grouped["finals_games"] = None
    grouped["championship_count"] = None
    grouped["high_leverage_experience_score"] = grouped.apply(
        lambda row: round(min(100.0, safe_float(row.get("playoff_games_career")) or 0.0) * 4 + (safe_float(row.get("playoff_minutes_career")) or 0.0) / 50.0, 2),
        axis=1,
    )
    return grouped[
        [
            "player_id",
            "player_name",
            "playoff_games_career",
            "playoff_starts_career",
            "playoff_minutes_career",
            "playoff_mpg_career",
            "finals_games",
            "championship_count",
            "playoff_last_3_years_games",
            "playoff_last_3_years_minutes",
            "high_leverage_experience_score",
        ]
    ].copy()


def read_onoff_team_rows() -> pd.DataFrame:
    paths = sorted(PBP_STATS_ROOT.glob("wnba_on_off/normalized/get-on-off/team_on_off__*.csv"))
    frames = [pd.read_csv(path) for path in paths if path.suffix == ".csv"]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_onoff_player_rows() -> pd.DataFrame:
    paths = sorted(PBP_STATS_ROOT.glob("wnba_on_off/normalized/get-on-off/player_on_off__*.csv"))
    frames = [pd.read_csv(path) for path in paths if path.suffix == ".csv"]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def read_expected_onoff_keys() -> pd.DataFrame:
    if not TEAM_PLAYER_CATALOG.exists():
        return pd.DataFrame(columns=["season", "season_type", "team_id", "player_id", "player_name"])
    frame = pd.read_csv(TEAM_PLAYER_CATALOG)
    for column in ["season", "season_type", "team_id", "player_id", "player_name"]:
        if column in frame.columns:
            frame[column] = frame[column].astype(str)
    keep_columns = [column for column in ["season", "season_type", "team_id", "player_id", "player_name", "team_abbreviation"] if column in frame.columns]
    return frame[keep_columns].copy()


def extract_minutes_from_player_onoff(frame: pd.DataFrame, target_player_name: str) -> tuple[float | None, float | None]:
    if frame.empty:
        return None, None
    result_columns = [column for column in frame.columns if column.startswith("results_")]
    if not result_columns:
        return None, None
    for column in result_columns:
        parsed = parse_jsonish(frame.iloc[0][column])
        if not isinstance(parsed, list):
            continue
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if normalize_name(item.get("Name")) == normalize_name(target_player_name):
                return safe_float(item.get("MinutesOn")), safe_float(item.get("MinutesOff"))
    return None, None


def metric_row_map(team_onoff_frame: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    stat_map: dict[str, dict[str, float | None]] = {}
    for _, row in team_onoff_frame.iterrows():
        stat = str(row.get("stat") or "").strip()
        if not stat:
            continue
        stat_map[stat] = {
            "on": safe_float(row.get("on")),
            "off": safe_float(row.get("off")),
            "on_off": safe_float(row.get("on_off")),
        }
    return stat_map


def onoff_sample_flag(minutes_on: float | None, minutes_off: float | None) -> str:
    total = (minutes_on or 0.0) + (minutes_off or 0.0)
    if total < 100:
        return "small"
    if total < 500:
        return "medium"
    return "large"


def validate_onoff_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    expected = read_expected_onoff_keys()
    key_columns = ["season", "season_type", "team_id", "player_id"]
    if expected.empty:
        validation = pd.DataFrame(
            [
                {
                    "table_name": "onoff_metrics",
                    "expected_rows": None,
                    "actual_rows": len(frame),
                    "missing_rows": None,
                    "coverage_pct": None,
                    "min_rows_threshold": ONOFF_MIN_ROWS,
                    "status": "partial",
                    "note": "expected discovery catalog missing",
                }
            ]
        )
        return validation, pd.DataFrame(columns=key_columns + ["player_name"]), expected

    expected_keys = expected[key_columns].drop_duplicates().copy()
    actual_keys = frame[key_columns].drop_duplicates().copy() if not frame.empty else pd.DataFrame(columns=key_columns)
    merged = expected_keys.merge(actual_keys, on=key_columns, how="left", indicator=True)
    missing = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
    if "player_name" in expected.columns and "player_name" not in missing.columns:
        missing = missing.merge(expected[key_columns + ["player_name"]].drop_duplicates(), on=key_columns, how="left")
    coverage_pct = round((len(actual_keys) / len(expected_keys)) * 100.0, 2) if len(expected_keys) else None
    validation = pd.DataFrame(
        [
            {
                "table_name": "onoff_metrics",
                "expected_rows": len(expected_keys),
                "actual_rows": len(actual_keys),
                "missing_rows": len(missing),
                "coverage_pct": coverage_pct,
                "min_rows_threshold": ONOFF_MIN_ROWS,
                "status": "ready" if len(frame) >= ONOFF_MIN_ROWS and len(missing) == 0 else "partial",
                "note": "full rebuild must cover the discovery universe and exceed the minimum row threshold",
            }
        ]
    )
    return validation, missing, expected_keys


def build_onoff_metrics(player_totals: pd.DataFrame) -> pd.DataFrame:
    team_onoff = read_onoff_team_rows()
    player_onoff = read_onoff_player_rows()
    if team_onoff.empty or player_onoff.empty:
        return pd.DataFrame(
            columns=[
                "player_id",
                "season",
                "team_id",
                "on_minutes",
                "off_minutes",
                "on_net_rating",
                "off_net_rating",
                "net_rating_diff",
                "on_off_ortg_diff",
                "on_off_drtg_diff",
                "team_ts_diff",
                "team_efg_diff",
                "team_3pt_pct_diff",
                "team_3pa_rate_diff",
                "team_tov_pct_diff",
                "team_ast_pct_diff",
                "team_oreb_pct_diff",
                "team_dreb_pct_diff",
                "opp_ts_diff",
                "opp_rim_rate_diff",
                "opp_3pa_rate_diff",
                "pace_diff",
                "onoff_sample_flag",
                "player_name",
                "season_type",
            ]
        )

    player_lookup = build_player_lookup(player_totals)
    records: list[dict[str, Any]] = []
    grouping_cols = ["season", "season_type", "team_id", "player_id", "request_id"]
    for (_, group) in team_onoff.groupby(grouping_cols, dropna=False):
        first = group.iloc[0]
        season = str(first.get("season"))
        season_type = str(first.get("season_type"))
        team_id = str(first.get("team_id"))
        target_player_id = str(first.get("player_id"))
        player_name_row = player_lookup[player_lookup["player_id"] == target_player_id]
        target_player_name = player_name_row.iloc[0]["name"] if not player_name_row.empty else None
        player_request = player_onoff[
            (player_onoff["season"].astype(str) == season)
            & (player_onoff["season_type"].astype(str) == season_type)
            & (player_onoff["team_id"].astype(str) == team_id)
            & (player_onoff["player_id"].astype(str) == target_player_id)
        ]
        minutes_on, minutes_off = extract_minutes_from_player_onoff(player_request, target_player_name or "")
        stat_map = metric_row_map(group)

        offense_on = stat_map.get("Pts per 100 Possessions", {}).get("on")
        offense_off = stat_map.get("Pts per 100 Possessions", {}).get("off")
        defense_on = stat_map.get("Pts per 100 Possessions - Defense", {}).get("on")
        defense_off = stat_map.get("Pts per 100 Possessions - Defense", {}).get("off")
        on_net_rating = None
        off_net_rating = None
        if offense_on is not None and defense_on is not None:
            on_net_rating = round(offense_on - defense_on, 6)
        if offense_off is not None and defense_off is not None:
            off_net_rating = round(offense_off - defense_off, 6)
        net_rating_diff = None
        if on_net_rating is not None and off_net_rating is not None:
            net_rating_diff = round(on_net_rating - off_net_rating, 6)

        seconds_off_on = stat_map.get("Seconds Per Possession - Offense", {}).get("on")
        seconds_off_off = stat_map.get("Seconds Per Possession - Offense", {}).get("off")
        pace_diff = None
        if seconds_off_on is not None and seconds_off_off is not None:
            # Positive means faster pace when the player is on the floor.
            pace_diff = round(seconds_off_off - seconds_off_on, 6)

        record = {
            "player_id": target_player_id,
            "player_name": target_player_name,
            "season": season,
            "season_type": season_type,
            "team_id": team_id,
            "on_minutes": minutes_on,
            "off_minutes": minutes_off,
            "on_net_rating": on_net_rating,
            "off_net_rating": off_net_rating,
            "net_rating_diff": net_rating_diff,
            "on_off_ortg_diff": round((offense_on or 0.0) - (offense_off or 0.0), 6) if offense_on is not None and offense_off is not None else None,
            "on_off_drtg_diff": round((defense_on or 0.0) - (defense_off or 0.0), 6) if defense_on is not None and defense_off is not None else None,
            "team_ts_diff": stat_map.get("TS%", {}).get("on_off"),
            "team_efg_diff": stat_map.get("eFG%", {}).get("on_off"),
            "team_3pt_pct_diff": stat_map.get("3pt FG%", {}).get("on_off"),
            "team_3pa_rate_diff": stat_map.get("3PAr", {}).get("on_off"),
            "team_tov_pct_diff": stat_map.get("Live Ball TO%", {}).get("on_off"),
            "team_ast_pct_diff": stat_map.get("Assists per 100 Possessions", {}).get("on_off"),
            "team_oreb_pct_diff": stat_map.get("OReb%", {}).get("on_off"),
            "team_dreb_pct_diff": stat_map.get("DReb%", {}).get("on_off"),
            "opp_ts_diff": stat_map.get("TS% - Defense", {}).get("on_off"),
            "opp_rim_rate_diff": stat_map.get("At Rim Shot Frequency - Defense", {}).get("on_off"),
            "opp_3pa_rate_diff": stat_map.get("3PAr - Defense", {}).get("on_off"),
            "pace_diff": pace_diff,
            "onoff_sample_flag": onoff_sample_flag(minutes_on, minutes_off),
        }
        records.append(record)

    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    return frame[
        [
            "player_id",
            "player_name",
            "season",
            "season_type",
            "team_id",
            "on_minutes",
            "off_minutes",
            "on_net_rating",
            "off_net_rating",
            "net_rating_diff",
            "on_off_ortg_diff",
            "on_off_drtg_diff",
            "team_ts_diff",
            "team_efg_diff",
            "team_3pt_pct_diff",
            "team_3pa_rate_diff",
            "team_tov_pct_diff",
            "team_ast_pct_diff",
            "team_oreb_pct_diff",
            "team_dreb_pct_diff",
            "opp_ts_diff",
            "opp_rim_rate_diff",
            "opp_3pa_rate_diff",
            "pace_diff",
            "onoff_sample_flag",
        ]
    ].copy()


def infer_position_group(row: pd.Series) -> str | None:
    reb = safe_float(row.get("reb_pct"))
    ast = safe_float(row.get("ast_pct"))
    blk = safe_float(row.get("blk_pct"))
    usage = safe_float(row.get("usage_pct"))
    three_par = safe_float(row.get("three_par"))
    rim_rate = safe_float(row.get("rim_rate"))
    if reb is None and ast is None:
        return None
    if reb is not None and reb >= 0.17 and blk is not None and blk >= 0.04:
        return "Center"
    if ast is not None and ast >= 0.18 and reb is not None and reb < 0.16:
        return "Guard"
    if reb is not None and reb >= 0.14 and ast is not None and ast >= 0.12:
        return "Wing"
    if three_par is not None and three_par >= 0.45 and rim_rate is not None and rim_rate < 0.25:
        return "Wing"
    if usage is not None and usage >= 0.24 and ast is not None and ast >= 0.15:
        return "Guard"
    return "Forward"


def infer_archetype(row: pd.Series) -> str | None:
    position_group = infer_position_group(row)
    usage = safe_float(row.get("usage_pct"))
    three_par = safe_float(row.get("three_par"))
    reb = safe_float(row.get("reb_pct"))
    ast = safe_float(row.get("ast_pct"))
    blk = safe_float(row.get("blk_pct"))
    ts = safe_float(row.get("ts_pct"))
    if position_group == "Center":
        return "Rim Protector" if blk and blk >= 0.05 else "Stretch Big"
    if position_group == "Guard":
        if ast and ast >= 0.25:
            return "Primary Creator"
        if three_par and three_par >= 0.5:
            return "3-Level Guard"
        return "Scoring Guard"
    if position_group == "Wing":
        if three_par and three_par >= 0.45 and ts and ts >= 0.55:
            return "3&D Wing"
        if ast and ast >= 0.18:
            return "Connector Wing"
        return "Versatile Wing"
    if reb and reb >= 0.20:
        return "Rebounding Forward"
    if usage and usage >= 0.22:
        return "Usage Forward"
    return "Rotation Forward"


def infer_role(row: pd.Series) -> str | None:
    mpg = safe_float(row.get("mpg"))
    if mpg is None:
        return None
    if mpg >= 28:
        return "Starter"
    if mpg >= 16:
        return "Rotation"
    if mpg >= 8:
        return "Bench"
    return "Development"


def tier_from_rank(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.dropna().empty:
        return pd.Series([None] * len(values), index=values.index)
    bins = min(4, int(values.dropna().nunique()))
    if bins <= 1:
        return pd.Series(["mid"] * len(values), index=values.index)
    labels = ["low", "mid", "upper_mid", "top"][:bins]
    ranked = pd.qcut(values.rank(method="first"), q=bins, labels=labels, duplicates="drop")
    return ranked.astype(str).replace("nan", None)


def build_contracts_2026(player_lookup: pd.DataFrame) -> pd.DataFrame:
    frame = read_csv(SALARY_CONTRACTS_2026).copy()
    frame["player_name_key"] = frame["player_name"].map(normalize_name)
    frame[["player_id", "player_id_source"]] = frame.apply(
        lambda row: pd.Series(resolve_player_id(row.get("player_name"), player_lookup, row.get("team_name"))), axis=1
    )
    frame[["team_id", "team_id_source"]] = frame["team_name"].apply(lambda value: pd.Series(resolve_team_id(value)))
    frame["team_abbreviation"] = frame["team_name"].map(TEAM_NAME_TO_ABBR)
    frame["season"] = pd.to_numeric(frame.get("season"), errors="coerce").astype("Int64")
    for column in ["salary", "cap_hit", "salary_as_pct_cap", "pct_team", "guaranteed_salary"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["salary_tier"] = frame["salary_tier"].replace("nan", None)
    frame["source_quality"] = frame.get("source_quality").astype(str).replace({"nan": None})
    frame["contract_icon_source"] = frame.get("contract_icon_source").astype(str).replace({"nan": None})
    output_columns = [
        "player_id",
        "player_id_source",
        "player_name",
        "player_name_key",
        "team_id",
        "team_id_source",
        "team_abbreviation",
        "team_name",
        "team_slug",
        "season",
        "salary",
        "cap_hit",
        "salary_as_pct_cap",
        "pct_team",
        "salary_tier",
        "contract_icon",
        "contract_icon_source",
        "source_quality",
        "option_flag",
        "tc_flag",
        "draftee_flag",
        "buyout_flag",
        "protected_veteran_flag",
        "protected_rookie_scale_flag",
        "unprotected_flag",
        "status",
        "status_full",
        "next_status",
        "core_years",
        "row_section",
        "counts_toward_salary_total",
        "counts_toward_player_total",
        "counts_toward_guaranteed_salary",
        "counts_toward_protected_veteran_total",
        "guaranteed_salary",
        "source_url",
        "source_name",
        "notes",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    team_caps = build_team_salary_cap()
    transactions = read_csv(TRANSACTIONS_MASTER) if TRANSACTIONS_MASTER.exists() else pd.DataFrame()
    salary_history = read_csv(SALARY_HISTORY_SOURCE) if SALARY_HISTORY_SOURCE.exists() else pd.DataFrame()
    frame = reconcile_contract_context_from_transactions(
        contracts=frame[output_columns].copy(),
        transactions=transactions,
        salary_history=salary_history,
        team_caps=team_caps,
    )
    return frame[output_columns].copy()


def build_team_salary_cap() -> pd.DataFrame:
    frame = read_csv(SALARY_TEAM_CAP).copy()
    frame["team_id"], frame["team_id_source"] = zip(*frame["team_name"].apply(resolve_team_id))
    frame["team_abbreviation"] = frame["team_name"].map(TEAM_NAME_TO_ABBR)
    frame["season"] = pd.to_numeric(frame.get("season"), errors="coerce").astype("Int64")
    for column in [
        "salary_cap",
        "total_cap_hit",
        "cap_space",
        "cap_used_pct",
        "total_players",
        "open_roster_slots",
        "guaranteed_salaries",
        "total_protected_veterans",
        "open_protected_veteran_slots",
        "avg_salary",
        "median_salary",
        "top_3_salary_share",
        "top_5_salary_share",
        "max_salary_count",
        "minimum_or_near_minimum_count",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["roster_count"] = frame["total_players"]
    frame["protected_veteran_count"] = frame["total_protected_veterans"]
    frame["team_total_salary"] = frame["total_cap_hit"]
    frame["team_salary_cap"] = frame["salary_cap"]
    output_columns = [
        "season",
        "team_id",
        "team_id_source",
        "team_abbreviation",
        "team_name",
        "team_slug",
        "salary_cap",
        "total_cap_hit",
        "cap_space",
        "cap_used_pct",
        "total_players",
        "roster_count",
        "open_roster_slots",
        "guaranteed_salaries",
        "total_protected_veterans",
        "protected_veteran_count",
        "open_protected_veteran_slots",
        "avg_salary",
        "median_salary",
        "top_3_salary_share",
        "top_5_salary_share",
        "max_salary_count",
        "minimum_or_near_minimum_count",
        "validation_pass",
        "source_url",
        "source_note",
        "team_total_salary",
        "team_salary_cap",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def build_players_master(player_totals: pd.DataFrame, player_lookup: pd.DataFrame) -> pd.DataFrame:
    contracts = build_contracts_2026(player_lookup)
    latest_context = build_latest_player_context(player_totals)
    team_caps = build_team_salary_cap()
    playoff_experience = aggregate_playoff_experience(player_totals)
    if not playoff_experience.empty:
        playoff_experience = playoff_experience.rename(columns={"player_name": "player_name_playoff"})
        playoff_experience["player_name_key"] = playoff_experience["player_name_playoff"].map(normalize_name)

    frame = contracts.merge(latest_context, on="player_name_key", how="left", suffixes=("", "_latest"))
    team_cap_lookup = team_caps[["team_id", "team_total_salary", "team_salary_cap"]].drop_duplicates()
    frame = frame.merge(team_cap_lookup, on="team_id", how="left", suffixes=("", "_team"))
    if not playoff_experience.empty:
        frame = frame.merge(
            playoff_experience[
                [
                    "player_name_key",
                    "playoff_games_career",
                    "playoff_minutes_career",
                    "playoff_mpg_career",
                    "finals_games",
                    "championship_count",
                    "playoff_last_3_years_games",
                    "playoff_last_3_years_minutes",
                    "high_leverage_experience_score",
                ]
            ],
            on="player_name_key",
            how="left",
        )
    else:
        for column in [
            "playoff_games_career",
            "playoff_minutes_career",
            "playoff_mpg_career",
            "finals_games",
            "championship_count",
            "playoff_last_3_years_games",
            "playoff_last_3_years_minutes",
            "high_leverage_experience_score",
        ]:
            frame[column] = None

    frame["years_service"] = frame["core_years"].apply(lambda value: len(str(value).split(",")) if pd.notna(value) and str(value).strip() else None)
    frame["age_2026"] = None
    frame["salary_tier"] = frame["salary_tier"].replace("nan", None)
    frame["roster_status"] = frame["row_section"].replace({"current_roster": "active"}).fillna("active")
    frame["roster_slot_type"] = frame["core_years"].apply(lambda value: "rookie" if isinstance(value, str) and value.startswith("2026") else "veteran")
    if "team_total_salary_team" in frame.columns:
        frame["team_total_salary"] = frame["team_total_salary"].fillna(frame["team_total_salary_team"])
        frame = frame.drop(columns=["team_total_salary_team"], errors="ignore")
    if "team_salary_cap_team" in frame.columns:
        frame["team_salary_cap"] = frame["team_salary_cap"].fillna(frame["team_salary_cap_team"])
        frame = frame.drop(columns=["team_salary_cap_team"], errors="ignore")
    output_columns = [
        "player_id",
        "player_id_source",
        "player_name",
        "player_name_key",
        "team_id",
        "team_id_source",
        "team_abbreviation",
        "team_name",
        "team_slug",
        "season",
        "salary",
        "cap_hit",
        "salary_as_pct_cap",
        "pct_team",
        "salary_tier",
        "contract_icon",
        "contract_icon_source",
        "source_quality",
        "option_flag",
        "tc_flag",
        "draftee_flag",
        "buyout_flag",
        "protected_veteran_flag",
        "protected_rookie_scale_flag",
        "unprotected_flag",
        "status",
        "status_full",
        "next_status",
        "core_years",
        "row_section",
        "counts_toward_salary_total",
        "counts_toward_player_total",
        "counts_toward_guaranteed_salary",
        "counts_toward_protected_veteran_total",
        "guaranteed_salary",
        "source_url",
        "source_name",
        "notes",
        "roster_status",
        "roster_slot_type",
        "position_group",
        "archetype",
        "age_2026",
        "years_service",
        "games_played",
        "minutes",
        "mpg",
        "usage",
        "ts_pct",
        "efg_pct",
        "ast_pct",
        "tov_pct",
        "stl_pct",
        "blk_pct",
        "reb_pct",
        "three_par",
        "rim_rate",
        "projected_role",
        "actual_role",
        "latest_context_season",
        "latest_context_season_type",
        "playoff_games_career",
        "playoff_minutes_career",
        "playoff_mpg_career",
        "high_leverage_experience_score",
        "team_total_salary",
        "team_salary_cap",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def build_team_rosters(player_totals: pd.DataFrame, player_lookup: pd.DataFrame) -> pd.DataFrame:
    players_master = build_players_master(player_totals, player_lookup)
    team_caps = build_team_salary_cap()
    frame = players_master[players_master["row_section"].astype(str) == CURRENT_ROSTER_SECTION].copy()
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "season",
                "team_id",
                "team_name",
                "player_id",
                "player_name",
                "roster_status",
                "roster_slot_type",
                "position_group",
                "archetype",
                "age_2026",
                "years_service",
                "salary",
                "cap_hit",
                "salary_tier",
                "mpg",
                "projected_role",
                "actual_role",
                "team_abbreviation",
                "team_total_salary",
                "team_salary_cap",
            ]
        )
    cap_lookup = team_caps[["team_id", "team_total_salary", "team_salary_cap"]].drop_duplicates()
    frame = frame.merge(cap_lookup, on="team_id", how="left", suffixes=("", "_team"))
    if "team_total_salary_team" in frame.columns:
        frame["team_total_salary"] = frame["team_total_salary"].fillna(frame["team_total_salary_team"])
        frame = frame.drop(columns=["team_total_salary_team"], errors="ignore")
    if "team_salary_cap_team" in frame.columns:
        frame["team_salary_cap"] = frame["team_salary_cap"].fillna(frame["team_salary_cap_team"])
        frame = frame.drop(columns=["team_salary_cap_team"], errors="ignore")
    output_columns = [
        "season",
        "team_id",
        "team_name",
        "player_id",
        "player_name",
        "roster_status",
        "roster_slot_type",
        "position_group",
        "archetype",
        "age_2026",
        "years_service",
        "salary",
        "cap_hit",
        "salary_tier",
        "mpg",
        "projected_role",
        "actual_role",
        "team_abbreviation",
        "team_total_salary",
        "team_salary_cap",
        "player_id_source",
        "team_id_source",
        "source_quality",
        "contract_icon_source",
        "row_section",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def normalize_transaction_type(value: Any) -> str | None:
    text = "" if value is None else str(value).strip().lower()
    mapping = {
        "expansion_draft": "expansion draft selection",
        "signed": "signed",
        "trade": "traded",
        "waived": "waived",
        "released": "waived",
    }
    return mapping.get(text, text or None)


def build_transactions_2026(player_lookup: pd.DataFrame) -> pd.DataFrame:
    frame = read_csv(TRANSACTIONS_MASTER)
    frame["player_id"] = frame.apply(
        lambda row: resolve_player_id(
            row.get("player_primary"),
            player_lookup,
            row.get("to_team") or row.get("from_team") or row.get("team_primary"),
        )[0],
        axis=1,
    )
    frame["player_name"] = frame["player_primary"]
    frame["transaction_type"] = frame["transaction_type"].astype(str).replace({"nan": None})
    frame["from_team"] = frame["from_team"].astype(str).replace({"nan": None})
    frame["to_team"] = frame["to_team"].astype(str).replace({"nan": None})
    frame["contract_value"] = pd.to_numeric(frame.get("contract_detail"), errors="coerce")
    frame["contract_years"] = None
    frame["salary_2026"] = None
    frame["market_signal"] = frame.apply(
        lambda row: "retained" if str(row.get("retention_flag")).lower() == "true" else "expansion" if str(row.get("is_expansion_team")).lower() == "true" else "movement",
        axis=1,
    )
    frame["notes"] = frame["raw_text"]
    output_columns = [
        "transaction_id",
        "transaction_date",
        "player_id",
        "player_name",
        "transaction_type",
        "from_team",
        "to_team",
        "contract_value",
        "contract_years",
        "salary_2026",
        "market_signal",
        "notes",
        "source_url",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def build_expansion_draft_2026(player_lookup: pd.DataFrame, player_totals: pd.DataFrame) -> pd.DataFrame:
    frame = read_csv(DRAFT_PICK_BASE)
    cap_contracts = read_csv(CAP_SHEET_CONTRACTS)
    cap_contracts = cap_contracts[cap_contracts["row_type"].astype(str) == "roster_player"].copy()
    cap_contracts = cap_contracts[pd.to_numeric(cap_contracts["season_year"], errors="coerce") == 2026].copy()
    cap_contracts["player_name_key"] = cap_contracts["player"].astype(str).str.replace(r"\s+\(.*\)$", "", regex=True).map(normalize_name)
    cap_contracts_lookup = cap_contracts[["player_name_key", "salary_cap_hit", "team", "core_years"]].copy()
    cap_contracts_lookup.columns = ["player_name_key", "salary_2026", "previous_team", "core_years"]

    latest_totals = player_totals[player_totals["season_type"].astype(str) == "Regular Season"].copy()
    latest_totals["player_name_key"] = latest_totals["name"].map(normalize_name)
    latest_totals["season"] = latest_totals["season"].astype(int)
    latest_totals["minutes"] = pd.to_numeric(latest_totals.get("minutes"), errors="coerce")
    latest_totals["mpg"] = latest_totals.apply(lambda row: safe_div(row.get("minutes"), row.get("games_played")), axis=1)
    latest_totals = latest_totals.sort_values(["player_name_key", "season", "minutes"], ascending=[True, False, False]).drop_duplicates("player_name_key", keep="first")
    for column in ["usage", "ts_pct", "efg_pct", "assists", "rebounds", "blocks", "three_par", "rim_rate"]:
        if column not in latest_totals.columns:
            latest_totals[column] = None
    latest_totals["position_group"] = latest_totals.apply(infer_position_group, axis=1)
    latest_totals["archetype"] = latest_totals.apply(infer_archetype, axis=1)
    latest_totals_lookup = latest_totals[["player_name_key", "position_group", "archetype", "mpg"]].copy()

    frame["player_id"] = frame["player_name"].apply(lambda value: lookup_player_id(value, player_lookup) or f"draft:{slugify(value).lower()}")
    frame["pick_number"] = pd.to_numeric(frame.get("draft_pick_overall"), errors="coerce")
    frame["expansion_team"] = frame["draft_team"].astype(str)
    frame["player_name_key"] = frame["player_name"].map(normalize_name)
    frame["position_group"] = None
    frame["archetype"] = None
    frame["mpg"] = None
    frame = frame.merge(cap_contracts_lookup, on="player_name_key", how="left")
    frame = frame.merge(latest_totals_lookup, on="player_name_key", how="left", suffixes=("", "_latest"))
    frame["previous_team"] = frame["current_team_from_feed"].astype(str).replace({"nan": None})
    frame["position_group"] = frame["position_group"].fillna(frame.get("position_group_latest"))
    frame["age_2026"] = None
    frame["years_service"] = pd.to_numeric(frame.get("draft_year"), errors="coerce")
    frame["years_service"] = frame["years_service"].apply(lambda value: 2026 - value + 1 if pd.notna(value) else None)
    frame["salary_2026"] = pd.to_numeric(frame.get("salary_2026"), errors="coerce")
    frame["protected_status"] = frame.get("preseason_retention_status")
    frame["archetype"] = frame["archetype"].fillna(frame.get("archetype_latest"))
    frame["selection_signal"] = frame["raw_text"].astype(str)
    output_columns = [
        "pick_number",
        "expansion_team",
        "player_id",
        "player_name",
        "previous_team",
        "position_group",
        "age_2026",
        "years_service",
        "salary_2026",
        "protected_status",
        "archetype",
        "selection_signal",
    ]
    for column in output_columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[output_columns].copy()


def coverage_from_frame(df: pd.DataFrame, required_columns: Iterable[str]) -> dict[str, Any]:
    required = [column for column in required_columns]
    present = [column for column in required if column in df.columns]
    non_null = 0
    if present and not df.empty:
        non_null = int(sum(df[present].notna().any(axis=0)))
    coverage = round((non_null / len(required)) * 100, 2) if required else 100.0
    return {
        "required_fields": len(required),
        "present_fields": len(present),
        "non_null_fields": non_null,
        "coverage_pct": coverage,
    }


def source_manifest() -> dict[str, Any]:
    return {
        "pbpstats_totals_files": [str(path) for path in sorted((PBP_STATS_ROOT / "wnba_totals/normalized/get-totals").glob("*.csv"))],
        "pbpstats_onoff_files": [str(path) for path in sorted((PBP_STATS_ROOT / "wnba_on_off/normalized/get-on-off").glob("*.csv"))],
        "pbpstats_team_player_catalog": str(TEAM_PLAYER_CATALOG),
        "team_roster_history": str(TEAM_ROSTER_HISTORY),
        "salary_validated_rows": str(SALARY_VALIDATED_ROWS),
        "salary_contracts_2026": str(SALARY_CONTRACTS_2026),
        "salary_team_cap": str(SALARY_TEAM_CAP),
        "salary_validation_summary": str(SALARY_VALIDATION_SUMMARY),
        "cap_sheet_contracts": str(CAP_SHEET_CONTRACTS),
        "cap_sheet_team_summary": str(CAP_SHEET_TEAM_SUMMARY),
        "cba_numbers": str(CBA_NUMBERS),
        "transactions_master": str(TRANSACTIONS_MASTER),
        "draft_pick_base": str(DRAFT_PICK_BASE),
    }


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    totals_files = sorted((PBP_STATS_ROOT / "wnba_totals/normalized/get-totals").glob("*.csv"))
    if not totals_files:
        raise SystemExit("No totals files found. Run the pbpstats totals job first.")

    totals_frames = [pd.read_csv(path) for path in totals_files]
    totals = pd.concat(totals_frames, ignore_index=True)
    player_totals = totals[totals["variant"].astype(str).str.contains("player_totals", na=False)].copy()
    team_totals = totals[totals["variant"].astype(str).str.contains("team_totals", na=False)].copy()
    player_lookup = build_player_lookup(player_totals)
    identity_lookup = build_player_identity_lookup(player_totals)

    tables: dict[str, pd.DataFrame] = {}
    tables["contracts_2026"] = build_contracts_2026(identity_lookup)
    tables["team_salary_cap"] = build_team_salary_cap()
    tables["players_master"] = build_players_master(player_totals, identity_lookup)
    tables["team_rosters"] = build_team_rosters(player_totals, identity_lookup)
    tables["player_season_stats"] = build_player_season_stats(player_totals)
    tables["advanced_player_metrics"] = build_advanced_player_metrics(player_totals)
    tables["onoff_metrics"] = build_onoff_metrics(player_totals)
    tables["playoff_experience"] = aggregate_playoff_experience(player_totals)
    if TEAM_ROSTER_HISTORY.exists():
        tables["team_roster_history"] = read_csv(TEAM_ROSTER_HISTORY)
    tables["transactions_2026"] = build_transactions_2026(identity_lookup)
    tables["expansion_draft_2026"] = build_expansion_draft_2026(player_lookup, player_totals)

    onoff_validation, onoff_missing, onoff_expected = validate_onoff_metrics(tables["onoff_metrics"])
    onoff_quality_reports = {
        "validation": write_table(onoff_validation, OUTPUT_ROOT / "tables" / "onoff_metrics" / "onoff_metrics_validation"),
        "missing_keys": write_table(onoff_missing, OUTPUT_ROOT / "tables" / "onoff_metrics" / "onoff_metrics_missing_keys"),
    }
    onoff_validation_row = onoff_validation.iloc[0].to_dict() if not onoff_validation.empty else {}
    onoff_status = str(onoff_validation_row.get("status") or "partial")
    onoff_expected_rows = onoff_validation_row.get("expected_rows")
    onoff_actual_rows = onoff_validation_row.get("actual_rows")
    onoff_missing_rows = onoff_validation_row.get("missing_rows")
    onoff_min_rows = onoff_validation_row.get("min_rows_threshold")

    table_specs = {
        "contracts_2026": [
            "player_id",
            "player_id_source",
            "player_name",
            "player_name_key",
            "team_id",
            "team_id_source",
            "team_abbreviation",
            "team_name",
            "team_slug",
            "season",
            "salary",
            "cap_hit",
            "salary_as_pct_cap",
            "pct_team",
            "salary_tier",
            "contract_icon",
            "contract_icon_source",
            "source_quality",
            "option_flag",
            "tc_flag",
            "draftee_flag",
            "buyout_flag",
            "protected_veteran_flag",
            "protected_rookie_scale_flag",
            "unprotected_flag",
            "status",
            "status_full",
            "next_status",
            "core_years",
            "row_section",
            "counts_toward_salary_total",
            "counts_toward_player_total",
            "counts_toward_guaranteed_salary",
            "counts_toward_protected_veteran_total",
            "guaranteed_salary",
            "source_url",
            "source_name",
            "notes",
        ],
        "team_salary_cap": [
            "season",
            "team_id",
            "team_id_source",
            "team_abbreviation",
            "team_name",
            "team_slug",
            "salary_cap",
            "total_cap_hit",
            "cap_space",
            "cap_used_pct",
            "total_players",
            "roster_count",
            "open_roster_slots",
            "guaranteed_salaries",
            "total_protected_veterans",
            "protected_veteran_count",
            "open_protected_veteran_slots",
            "avg_salary",
            "median_salary",
            "top_3_salary_share",
            "top_5_salary_share",
            "max_salary_count",
            "minimum_or_near_minimum_count",
            "validation_pass",
            "source_url",
            "source_note",
        ],
        "players_master": [
            "player_id",
            "player_id_source",
            "player_name",
            "player_name_key",
            "team_id",
            "team_id_source",
            "team_abbreviation",
            "team_name",
            "team_slug",
            "season",
            "salary",
            "cap_hit",
            "salary_as_pct_cap",
            "pct_team",
            "salary_tier",
            "contract_icon",
            "contract_icon_source",
            "source_quality",
            "option_flag",
            "tc_flag",
            "draftee_flag",
            "buyout_flag",
            "protected_veteran_flag",
            "protected_rookie_scale_flag",
            "unprotected_flag",
            "status",
            "status_full",
            "next_status",
            "core_years",
            "row_section",
            "counts_toward_salary_total",
            "counts_toward_player_total",
            "counts_toward_guaranteed_salary",
            "counts_toward_protected_veteran_total",
            "guaranteed_salary",
            "source_url",
            "source_name",
            "notes",
            "roster_status",
            "roster_slot_type",
            "position_group",
            "archetype",
            "age_2026",
            "years_service",
            "games_played",
            "minutes",
            "mpg",
            "usage",
            "ts_pct",
            "efg_pct",
            "ast_pct",
            "tov_pct",
            "stl_pct",
            "blk_pct",
            "reb_pct",
            "three_par",
            "rim_rate",
            "projected_role",
            "actual_role",
            "latest_context_season",
            "latest_context_season_type",
            "playoff_games_career",
            "playoff_minutes_career",
            "playoff_mpg_career",
            "high_leverage_experience_score",
            "team_total_salary",
            "team_salary_cap",
        ],
        "player_season_stats": [
            "player_id",
            "player_name",
            "team_id",
            "season",
            "season_type",
            "games_played",
            "games_started",
            "minutes",
            "mpg",
            "points",
            "ppg",
            "rebounds",
            "rpg",
            "assists",
            "apg",
            "steals",
            "spg",
            "blocks",
            "bpg",
            "turnovers",
            "tov_pg",
            "fgm",
            "fga",
            "fg_pct",
            "three_pm",
            "three_pa",
            "three_pct",
            "ftm",
            "fta",
            "ft_pct",
        ],
        "advanced_player_metrics": [
            "player_id",
            "season",
            "season_type",
            "team_id",
            "possessions",
            "usage_pct",
            "ts_pct",
            "efg_pct",
            "ast_pct",
            "tov_pct",
            "ast_tov_ratio",
            "oreb_pct",
            "dreb_pct",
            "reb_pct",
            "stl_pct",
            "blk_pct",
            "ftr",
            "three_par",
            "rim_rate",
            "midrange_rate",
            "pts_per_40",
            "ast_per_40",
            "reb_per_40",
            "stl_per_40",
            "blk_per_40",
            "ts_pctile_pos",
            "usage_pctile_pos",
            "ast_pctile_pos",
            "tov_pctile_pos",
            "reb_pctile_pos",
            "stl_pctile_pos",
            "blk_pctile_pos",
            "production_score",
        ],
        "onoff_metrics": [
            "player_id",
            "player_name",
            "season",
            "season_type",
            "team_id",
            "on_minutes",
            "off_minutes",
            "on_net_rating",
            "off_net_rating",
            "net_rating_diff",
            "on_off_ortg_diff",
            "on_off_drtg_diff",
            "team_ts_diff",
            "team_efg_diff",
            "team_3pt_pct_diff",
            "team_3pa_rate_diff",
            "team_tov_pct_diff",
            "team_ast_pct_diff",
            "team_oreb_pct_diff",
            "team_dreb_pct_diff",
            "opp_ts_diff",
            "opp_rim_rate_diff",
            "opp_3pa_rate_diff",
            "pace_diff",
            "onoff_sample_flag",
        ],
        "playoff_experience": [
            "player_id",
            "player_name",
            "playoff_games_career",
            "playoff_starts_career",
            "playoff_minutes_career",
            "playoff_mpg_career",
            "finals_games",
            "championship_count",
            "playoff_last_3_years_games",
            "playoff_last_3_years_minutes",
            "high_leverage_experience_score",
        ],
        "team_rosters": [
            "season",
            "team_id",
            "team_name",
            "player_id",
            "player_name",
            "roster_status",
            "roster_slot_type",
            "position_group",
            "archetype",
            "age_2026",
            "years_service",
            "salary",
            "cap_hit",
            "salary_tier",
            "mpg",
            "projected_role",
            "actual_role",
            "team_abbreviation",
            "team_total_salary",
            "team_salary_cap",
            "player_id_source",
            "team_id_source",
            "source_quality",
            "contract_icon_source",
            "row_section",
        ],
        "team_roster_history": [
            "league",
            "season",
            "season_type",
            "team_id",
            "team_abbreviation",
            "team_name",
            "player_id",
            "player_name",
            "player_order",
            "request_url",
            "request_status",
            "request_params",
            "raw_path",
        ],
        "transactions_2026": [
            "transaction_id",
            "transaction_date",
            "player_id",
            "player_name",
            "transaction_type",
            "from_team",
            "to_team",
            "contract_value",
            "contract_years",
            "salary_2026",
            "market_signal",
            "notes",
            "source_url",
        ],
        "expansion_draft_2026": [
            "pick_number",
            "expansion_team",
            "player_id",
            "player_name",
            "previous_team",
            "position_group",
            "age_2026",
            "years_service",
            "salary_2026",
            "protected_status",
            "archetype",
            "selection_signal",
        ],
    }

    coverage_rows: list[dict[str, Any]] = []
    written_files: dict[str, list[str]] = {}
    for table_name, df in tables.items():
        table_dir = OUTPUT_ROOT / "tables" / table_name
        written_files[table_name] = write_table(df, table_dir / table_name)
        spec = table_specs[table_name]
        coverage = coverage_from_frame(df, spec)
        status = "ready" if coverage["coverage_pct"] >= 75 or table_name in {"player_season_stats", "advanced_player_metrics", "transactions_2026", "expansion_draft_2026"} else "partial"
        if table_name == "onoff_metrics":
            status = onoff_status
        coverage_rows.append(
            {
                "table_name": table_name,
                "rows": len(df),
                "required_fields": coverage["required_fields"],
                "present_fields": coverage["present_fields"],
                "non_null_fields": coverage["non_null_fields"],
                "coverage_pct": coverage["coverage_pct"],
                "status": status,
                "expected_rows": onoff_expected_rows if table_name == "onoff_metrics" else None,
                "actual_rows": onoff_actual_rows if table_name == "onoff_metrics" else None,
                "missing_rows": onoff_missing_rows if table_name == "onoff_metrics" else None,
                "min_rows_threshold": onoff_min_rows if table_name == "onoff_metrics" else None,
                "quality_report_validation": onoff_quality_reports["validation"][0] if table_name == "onoff_metrics" else None,
                "quality_report_missing_keys": onoff_quality_reports["missing_keys"][0] if table_name == "onoff_metrics" else None,
                "source_files": "; ".join(
                    sorted(
                        {
                            str(value)
                            for value in [
                                *source_manifest()["pbpstats_totals_files"],
                                *source_manifest()["pbpstats_onoff_files"],
                                source_manifest()["salary_validated_rows"],
                                source_manifest()["salary_contracts_2026"],
                                source_manifest()["salary_team_cap"],
                                source_manifest()["salary_validation_summary"],
                                source_manifest()["cap_sheet_contracts"],
                                source_manifest()["cap_sheet_team_summary"],
                                source_manifest()["cba_numbers"],
                                source_manifest()["transactions_master"],
                                source_manifest()["draft_pick_base"],
                            ]
                        }
                    )
                ),
            }
        )

    coverage_df = pd.DataFrame(coverage_rows)
    coverage_written = write_table(coverage_df, OUTPUT_ROOT / "coverage_report")

    validation_issues: list[str] = []

    manifest = {
        "bundle_id": "doc2_roster_value_first_wave",
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "output_root": str(OUTPUT_ROOT),
        "source_manifest": source_manifest(),
        "tables": {name: {"rows": len(df), "files": written_files[name]} for name, df in tables.items()},
        "coverage_report": coverage_written,
        "quality_reports": onoff_quality_reports,
        "validation_issues": validation_issues,
        "build_status": "ready" if not validation_issues else "failed_validation",
        "deferred_tables": [
            "player_archetypes",
            "comparable_players",
            "value_scores",
            "team_roster_grades",
            "market_benchmarks",
        ],
    }
    with (OUTPUT_ROOT / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    if validation_issues:
        raise SystemExit("; ".join(validation_issues))

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
