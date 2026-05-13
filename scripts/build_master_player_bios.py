#!/usr/bin/env python3
"""Build a 2026 master player bio export from the current roster universe."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


BASE_ROSTER_PATH = Path("data/doc2_roster_value/tables/team_rosters/team_rosters.csv")
PLAYER_BIOS_2025_PATH = Path("data/doc2_roster_value/tables/player_bios/player_bios_2025.csv")
TEAM_ROSTER_HISTORY_PATH = Path("data/doc2_roster_value/tables/team_roster_history/team_roster_history.csv")
PARQUET_ROSTER_PATH = Path("/Users/krystalbeasley/Downloads/rosters_2026.parquet")
RAW_POSITION_PATH = Path("player_info_raw_needs_join_2025_wnba - 2025_player_info_with_pos.csv")
RAW_AGE_PATH = Path("player_info_raw_needs_join_2025_wnba - 2025_player_bios_with_age.csv")
WBB_BOX_PATH = Path("/Users/krystalbeasley/projects/wbb-bis/data/raw/historical/player_box_2025.parquet")
OUTPUT_DIR = Path("data/doc2_roster_value/tables/master_player_bios")
OUTPUT_CSV_PATH = OUTPUT_DIR / "master_player_bios_2026.csv"
SUMMARY_PATH = OUTPUT_DIR / "master_player_bios_2026_summary.json"
UNMATCHED_COMBINED_PATH = OUTPUT_DIR / "master_player_bios_2026_unmatched_after_parquet_and_raw_pos.csv"
TEAM_CROSSCHECK_PATH = OUTPUT_DIR / "master_player_bios_2026_team_crosscheck.csv"


def normalize_name(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "", text)


def parse_numeric(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_height_inches(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        numeric = int(round(float(value)))
        return numeric if numeric > 0 else None

    text = str(value).strip()
    if not text:
        return None

    numeric = parse_numeric(text)
    if numeric is not None and numeric > 0:
        return int(round(numeric))

    normalized = (
        text.lower()
        .replace("feet", "'")
        .replace("foot", "'")
        .replace("ft.", "'")
        .replace("ft", "'")
        .replace("inches", '"')
        .replace("inch", '"')
        .replace("in.", '"')
        .replace("in", '"')
        .replace(" ", "")
    )
    for pattern in [
        r"^(?P<feet>\d+)'(?P<inches>\d+)(?:\"|)$",
        r"^(?P<feet>\d+)-(?P<inches>\d+)$",
    ]:
        match = re.match(pattern, normalized)
        if match:
            return int(match.group("feet")) * 12 + int(match.group("inches"))
    return None


def format_height_ft_in(height_inches: Any) -> str | None:
    numeric = parse_height_inches(height_inches)
    if numeric is None:
        return None
    feet, inches = divmod(numeric, 12)
    return f"{feet}'{inches}\""


def build_alias_id_set(team_roster_history: pd.DataFrame) -> set[str]:
    if team_roster_history.empty:
        return set()
    alias_counts = (
        team_roster_history.assign(player_id=lambda frame: frame["player_id"].astype(str))
        .groupby("player_id")["player_name"]
        .nunique()
    )
    return set(alias_counts[alias_counts > 1].index.astype(str))


def dedupe_parquet_by_name(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    working["name_key"] = working["full_name"].map(normalize_name)
    working["active_priority"] = working["status_name"].astype(str).str.lower().eq("active").astype(int)
    working = working.sort_values(
        ["name_key", "active_priority", "team_display_name", "athlete_id"],
        ascending=[True, False, True, True],
    )
    return working.drop_duplicates(subset=["name_key"], keep="first")


def dedupe_raw_position_by_name(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    working["name_key"] = working["Player_Name"].map(normalize_name)
    working["position_priority"] = (
        working["Position"].notna().astype(int) * 4
        + working["Position_full"].notna().astype(int) * 2
        + working["Height"].notna().astype(int)
    )
    working = working.sort_values(
        ["name_key", "position_priority", "Player_Name"],
        ascending=[True, False, True],
    )
    return working.drop_duplicates(subset=["name_key"], keep="first")


def dedupe_wbb_box_by_name(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return frame, pd.DataFrame(columns=["name_key", "position_pair_count"])

    working = frame.copy()
    working["name_key"] = working["athlete_display_name"].map(normalize_name)
    working["athlete_position_name"] = working["athlete_position_name"].replace("", pd.NA)
    working["athlete_position_abbreviation"] = working["athlete_position_abbreviation"].replace("", pd.NA)
    working = working[working["name_key"].ne("")]
    working = working[
        working["athlete_position_name"].notna() | working["athlete_position_abbreviation"].notna()
    ].copy()
    working["position_pair_key"] = (
        working["athlete_position_name"].fillna("")
        + "||"
        + working["athlete_position_abbreviation"].fillna("")
    )

    pair_counts = (
        working.groupby("name_key")["position_pair_key"]
        .nunique()
        .rename("position_pair_count")
        .reset_index()
    )
    eligible_keys = set(pair_counts.loc[pair_counts["position_pair_count"] == 1, "name_key"])

    eligible = working[working["name_key"].isin(eligible_keys)].copy()
    eligible = eligible.sort_values(
        ["name_key", "athlete_position_name", "athlete_position_abbreviation", "athlete_display_name"]
    )
    deduped = eligible.drop_duplicates(subset=["name_key"], keep="first")
    return deduped, pair_counts


def dedupe_player_bios_2025_by_id(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    working["player_id_str"] = working["player_id"].astype(str)
    working["age_priority"] = working["age_2026"].notna().astype(int)
    working = working.sort_values(["player_id_str", "age_priority", "player_name"], ascending=[True, False, True])
    return working.drop_duplicates(subset=["player_id_str"], keep="first")


def dedupe_raw_age_by_name(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    working = frame.copy()
    working["name_key"] = working["player_name"].map(normalize_name)
    working["age_priority"] = working["player_age"].notna().astype(int)
    working = working.sort_values(["name_key", "age_priority", "player_name"], ascending=[True, False, True])
    return working.drop_duplicates(subset=["name_key"], keep="first")


def build_master_player_bios() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    roster = pd.read_csv(BASE_ROSTER_PATH)
    roster_history = pd.read_csv(TEAM_ROSTER_HISTORY_PATH) if TEAM_ROSTER_HISTORY_PATH.exists() else pd.DataFrame()
    parquet = dedupe_parquet_by_name(pd.read_parquet(PARQUET_ROSTER_PATH))
    raw_pos = dedupe_raw_position_by_name(pd.read_csv(RAW_POSITION_PATH))
    wbb_box_raw = pd.read_parquet(
        WBB_BOX_PATH,
        columns=["athlete_display_name", "athlete_position_name", "athlete_position_abbreviation"],
    )
    wbb_box, wbb_box_pair_counts = dedupe_wbb_box_by_name(wbb_box_raw)
    player_bios_2025_raw = pd.read_csv(PLAYER_BIOS_2025_PATH)
    player_bios_2025 = dedupe_player_bios_2025_by_id(player_bios_2025_raw)
    raw_age = dedupe_raw_age_by_name(pd.read_csv(RAW_AGE_PATH))

    alias_ids = build_alias_id_set(roster_history)

    roster = roster.copy()
    roster["player_id_str"] = roster["player_id"].astype(str)
    roster["name_key"] = roster["player_name"].map(normalize_name)
    roster["pbpstats_player_id"] = roster["player_id"].astype(str).where(
        roster["player_id"].astype(str).str.fullmatch(r"\d+"), None
    )

    parquet = parquet.copy()
    parquet["name_key"] = parquet["full_name"].map(normalize_name)
    raw_pos = raw_pos.copy()
    raw_pos["name_key"] = raw_pos["Player_Name"].map(normalize_name)
    wbb_box = wbb_box.copy()
    wbb_box["name_key"] = wbb_box["athlete_display_name"].map(normalize_name)
    raw_age = raw_age.copy()
    raw_age["name_key"] = raw_age["player_name"].map(normalize_name)

    merged = roster.merge(
        parquet[
            [
                "name_key",
                "athlete_id",
                "full_name",
                "team_id",
                "team_abbreviation",
                "team_display_name",
                "position_abbreviation",
                "position_name",
                "height",
                "age",
                "date_of_birth",
                "status_name",
                "status_type",
            ]
        ].rename(
            columns={
                "athlete_id": "espn_athlete_id",
                "full_name": "parquet_full_name",
                "team_id": "parquet_team_id",
                "team_abbreviation": "parquet_team_abbreviation",
                "team_display_name": "parquet_team_display_name",
                "position_abbreviation": "parquet_position_abbreviation",
                "position_name": "parquet_position_name",
                "height": "parquet_height_raw",
                "age": "parquet_age",
                "date_of_birth": "parquet_date_of_birth",
                "status_name": "parquet_status_name",
                "status_type": "parquet_status_type",
            }
        ),
        on="name_key",
        how="left",
    )
    merged = merged.merge(
        raw_pos[
            [
                "name_key",
                "Player_Name",
                "Position_full",
                "Position",
                "Height",
            ]
        ].rename(
            columns={
                "Player_Name": "raw_pos_player_name",
                "Position_full": "raw_pos_position_full",
                "Position": "raw_pos_position_abbreviation",
                "Height": "raw_pos_height_raw",
            }
        ),
        on="name_key",
        how="left",
    )
    merged = merged.merge(
        wbb_box[
            [
                "name_key",
                "athlete_display_name",
                "athlete_position_name",
                "athlete_position_abbreviation",
            ]
        ].rename(
            columns={
                "athlete_display_name": "wbb_box_player_name",
                "athlete_position_name": "wbb_box_position_name",
                "athlete_position_abbreviation": "wbb_box_position_abbreviation",
            }
        ),
        on="name_key",
        how="left",
    )
    merged = merged.merge(
        player_bios_2025[
            [
                "player_id_str",
                "player_name",
                "age_2026",
            ]
        ].rename(
            columns={
                "player_name": "player_bios_2025_name",
                "age_2026": "player_bios_2025_age_2026",
            }
        ),
        on="player_id_str",
        how="left",
    )
    merged = merged.merge(
        raw_age[
            [
                "name_key",
                "player_name",
                "player_age",
            ]
        ].rename(
            columns={
                "player_name": "raw_age_player_name",
                "player_age": "raw_age_player_age",
            }
        ),
        on="name_key",
        how="left",
    )

    parquet_name_match_flag = merged["espn_athlete_id"].notna()
    raw_position_name_match_flag = (~parquet_name_match_flag) & merged["raw_pos_player_name"].notna()
    wbb_box_name_match_flag = (
        (~parquet_name_match_flag)
        & (~raw_position_name_match_flag)
        & merged["wbb_box_player_name"].notna()
    )

    height_from_parquet = merged["parquet_height_raw"].map(parse_height_inches)
    height_from_raw_pos = merged["raw_pos_height_raw"].map(parse_height_inches)

    position_abbreviation = (
        merged["parquet_position_abbreviation"]
        .combine_first(merged["raw_pos_position_abbreviation"])
        .combine_first(merged["wbb_box_position_abbreviation"])
    )
    position = (
        merged["parquet_position_name"]
        .combine_first(merged["raw_pos_position_full"])
        .combine_first(merged["wbb_box_position_name"])
    )
    position_full = (
        merged["parquet_position_name"]
        .combine_first(merged["raw_pos_position_full"])
        .combine_first(merged["wbb_box_position_name"])
    )
    height_raw_source = merged["parquet_height_raw"].combine_first(merged["raw_pos_height_raw"])
    height_inches = height_from_parquet.combine_first(height_from_raw_pos)

    parquet_age = pd.to_numeric(merged["parquet_age"], errors="coerce")
    player_bios_2025_age = pd.to_numeric(merged["player_bios_2025_age_2026"], errors="coerce")
    raw_age_value = pd.to_numeric(merged["raw_age_player_age"], errors="coerce")

    age_2026 = parquet_age.copy()
    age_match_method = pd.Series("unmatched", index=merged.index, dtype="object")
    age_match_method.loc[parquet_age.notna()] = "parquet_age"

    player_bios_2025_age_match_flag = age_2026.isna() & player_bios_2025_age.notna()
    age_2026.loc[player_bios_2025_age_match_flag] = player_bios_2025_age.loc[player_bios_2025_age_match_flag]
    age_match_method.loc[player_bios_2025_age_match_flag] = "player_bios_2025_id_exact"

    raw_age_name_match_flag = age_2026.isna() & raw_age_value.notna()
    age_2026.loc[raw_age_name_match_flag] = raw_age_value.loc[raw_age_name_match_flag]
    age_match_method.loc[raw_age_name_match_flag] = "raw_age_name_exact"

    bio_match_method = pd.Series("unmatched", index=merged.index, dtype="object")
    bio_match_method.loc[wbb_box_name_match_flag] = "wbb_box_name_exact"
    bio_match_method.loc[raw_position_name_match_flag] = "raw_pos_name_exact"
    bio_match_method.loc[parquet_name_match_flag] = "parquet_name_exact"

    parquet_match_method = parquet_name_match_flag.map(lambda matched: "name_exact" if matched else "unmatched")
    parquet_team_crosscheck_flag = (
        parquet_name_match_flag
        & merged["parquet_team_display_name"].notna()
        & (merged["team_name"] != merged["parquet_team_display_name"])
    )

    synthetic_id_flag = merged["player_id_source"].astype(str).eq("synthetic_name")
    missing_age_flag = age_2026.isna()
    missing_height_flag = height_inches.isna()
    missing_position_flag = position.isna() & position_full.isna()
    name_alias_flag = merged["pbpstats_player_id"].astype(str).isin(alias_ids)
    name_alias_flag = name_alias_flag | (
        merged["parquet_full_name"].notna()
        & (merged["name_key"] != merged["parquet_full_name"].map(normalize_name))
    )

    notes: list[str | None] = []
    for (
        synthetic,
        parquet_match,
        raw_pos_match,
        wbb_box_match,
        player_bios_age_match,
        raw_age_match,
        team_mismatch,
        alias_flag,
        missing_age,
        missing_height,
        missing_position,
    ) in zip(
        synthetic_id_flag.tolist(),
        parquet_name_match_flag.tolist(),
        raw_position_name_match_flag.tolist(),
        wbb_box_name_match_flag.tolist(),
        player_bios_2025_age_match_flag.tolist(),
        raw_age_name_match_flag.tolist(),
        parquet_team_crosscheck_flag.tolist(),
        name_alias_flag.tolist(),
        missing_age_flag.tolist(),
        missing_height_flag.tolist(),
        missing_position_flag.tolist(),
    ):
        row_notes: list[str] = []
        if synthetic:
            row_notes.append("synthetic_framework_id")
        if parquet_match:
            row_notes.append("parquet_name_exact_match")
        if raw_pos_match:
            row_notes.append("raw_position_name_exact_match")
        if wbb_box_match:
            row_notes.append("wbb_box_name_exact_match")
        if player_bios_age_match:
            row_notes.append("age_filled_from_player_bios_2025_id_exact")
        if raw_age_match:
            row_notes.append("age_filled_from_raw_age_name_exact")
        if team_mismatch:
            row_notes.append("parquet_team_differs_from_master_team")
        if alias_flag:
            row_notes.append("historical_name_alias_for_player_id")
        if missing_age:
            row_notes.append("missing_age_after_local_backfill")
        if missing_height:
            row_notes.append("missing_height_after_local_backfill")
        if missing_position:
            row_notes.append("missing_position_after_local_backfill")
        notes.append("; ".join(row_notes) if row_notes else None)

    output = pd.DataFrame(
        {
            "player_name": merged["player_name"],
            "player_id": merged["player_id"],
            "player_id_source": merged["player_id_source"],
            "pbpstats_player_id": merged["pbpstats_player_id"],
            "espn_wehoop_player_id": None,
            "espn_athlete_id": pd.to_numeric(merged["espn_athlete_id"], errors="coerce").astype("Int64"),
            "team_2026": merged["team_name"],
            "team_2026_abbr": merged["team_abbreviation"],
            "parquet_team_display_name": merged["parquet_team_display_name"],
            "parquet_team_abbreviation": merged["parquet_team_abbreviation"],
            "position_abbreviation": position_abbreviation,
            "position": position,
            "position_full": position_full,
            "height_raw_source": height_raw_source,
            "height_inches": height_inches,
            "height_ft_in": [format_height_ft_in(value) for value in height_inches],
            "age_2026": age_2026,
            "player_college": None,
            "player_country": None,
            "date_of_birth": merged["parquet_date_of_birth"],
            "parquet_status_name": merged["parquet_status_name"],
            "parquet_status_type": merged["parquet_status_type"],
            "bio_match_method": bio_match_method,
            "age_match_method": age_match_method,
            "parquet_name_match_flag": parquet_name_match_flag,
            "raw_position_name_match_flag": raw_position_name_match_flag,
            "wbb_box_name_match_flag": wbb_box_name_match_flag,
            "player_bios_2025_age_match_flag": player_bios_2025_age_match_flag,
            "raw_age_name_match_flag": raw_age_name_match_flag,
            "parquet_match_method": parquet_match_method,
            "parquet_team_crosscheck_flag": parquet_team_crosscheck_flag,
            "synthetic_id_flag": synthetic_id_flag,
            "team_changed_from_bio_flag": parquet_team_crosscheck_flag,
            "missing_age_flag": missing_age_flag,
            "missing_height_flag": missing_height_flag,
            "missing_position_flag": missing_position_flag,
            "name_alias_flag": name_alias_flag,
            "notes": notes,
        }
    )

    for column in [
        "parquet_name_match_flag",
        "raw_position_name_match_flag",
        "wbb_box_name_match_flag",
        "player_bios_2025_age_match_flag",
        "raw_age_name_match_flag",
        "parquet_team_crosscheck_flag",
        "synthetic_id_flag",
        "team_changed_from_bio_flag",
        "missing_age_flag",
        "missing_height_flag",
        "missing_position_flag",
        "name_alias_flag",
    ]:
        output[column] = output[column].map(bool)

    output["height_inches"] = pd.to_numeric(output["height_inches"], errors="coerce").round().astype("Int64")
    output["age_2026"] = pd.to_numeric(output["age_2026"], errors="coerce").round().astype("Int64")
    output = output.sort_values(["team_2026", "player_name", "player_id"], ascending=[True, True, True]).reset_index(
        drop=True
    )

    unmatched = output[output["bio_match_method"] == "unmatched"].copy()
    team_crosscheck = output[output["parquet_team_crosscheck_flag"]].copy()

    duplicate_player_id_rows = int(output["player_id"].duplicated().sum())
    duplicate_team_player_rows = int(output.duplicated(subset=["team_2026", "player_name", "player_id"]).sum())
    unique_teams = int(output["team_2026"].nunique(dropna=True))
    unique_rows = int(len(output))
    parquet_rows = int(len(parquet))
    parquet_unique_names = int(parquet["name_key"].nunique())
    raw_pos_rows = int(len(raw_pos))
    raw_pos_unique_names = int(raw_pos["name_key"].nunique())
    raw_pos_duplicate_name_rows = int(raw_pos["name_key"].duplicated().sum())
    wbb_box_rows = int(len(wbb_box))
    wbb_box_unique_names = int(wbb_box["name_key"].nunique())
    wbb_box_duplicate_name_rows = int(wbb_box["name_key"].duplicated().sum())
    player_bios_2025_raw_rows = int(len(player_bios_2025_raw))
    player_bios_2025_rows = int(len(player_bios_2025))
    raw_age_rows = int(len(raw_age))
    raw_age_unique_names = int(raw_age["name_key"].nunique())
    master_unique_names = int(output["player_name"].map(normalize_name).nunique())
    parquet_name_match_rows = int(output["parquet_name_match_flag"].sum())
    parquet_unmatched_pre_fallback_rows = int((~output["parquet_name_match_flag"]).sum())
    raw_position_name_fallback_rows = int(output["raw_position_name_match_flag"].sum())
    wbb_box_name_fallback_rows = int(output["wbb_box_name_match_flag"].sum())
    final_unmatched_rows = int((output["bio_match_method"] == "unmatched").sum())

    position_gap_candidates = roster.copy()
    position_gap_candidates["name_key"] = position_gap_candidates["player_name"].map(normalize_name)
    position_gap_candidates = position_gap_candidates.merge(
        parquet[["name_key", "athlete_id"]].rename(columns={"athlete_id": "parquet_athlete_id"}),
        on="name_key",
        how="left",
    )
    position_gap_candidates = position_gap_candidates.merge(
        raw_pos[["name_key", "Player_Name"]].rename(columns={"Player_Name": "raw_pos_player_name"}),
        on="name_key",
        how="left",
    )
    position_gap_candidates["would_be_parquet_match"] = position_gap_candidates["parquet_athlete_id"].notna()
    position_gap_candidates["would_be_raw_pos_match"] = (
        ~position_gap_candidates["would_be_parquet_match"]
    ) & position_gap_candidates["raw_pos_player_name"].notna()
    position_gap_candidates = position_gap_candidates[
        ~position_gap_candidates["would_be_parquet_match"] & ~position_gap_candidates["would_be_raw_pos_match"]
    ].copy()
    position_gap_candidate_keys = set(position_gap_candidates["name_key"])
    wbb_box_match_any_rows = int(wbb_box_raw.assign(name_key=wbb_box_raw["athlete_display_name"].map(normalize_name))[
        "name_key"
    ].isin(position_gap_candidate_keys).sum() > 0)
    wbb_box_position_gap_matches = int(output["wbb_box_name_match_flag"].sum())
    raw_wbb_position_candidates = wbb_box_raw.copy()
    raw_wbb_position_candidates["name_key"] = raw_wbb_position_candidates["athlete_display_name"].map(normalize_name)
    raw_wbb_position_candidates = raw_wbb_position_candidates[
        raw_wbb_position_candidates["name_key"].isin(position_gap_candidate_keys)
    ].copy()
    raw_wbb_position_candidates["position_pair_key"] = (
        raw_wbb_position_candidates["athlete_position_name"].fillna("")
        + "||"
        + raw_wbb_position_candidates["athlete_position_abbreviation"].fillna("")
    )
    wbb_gap_pair_counts = raw_wbb_position_candidates.groupby("name_key")["position_pair_key"].nunique()
    wbb_position_gap_exact_match_rows = int((wbb_gap_pair_counts == 1).sum())
    wbb_position_gap_ambiguous_match_rows = int((wbb_gap_pair_counts > 1).sum())

    summary = {
        "row_count": unique_rows,
        "team_count": unique_teams,
        "duplicate_player_id_rows": duplicate_player_id_rows,
        "duplicate_team_player_rows": duplicate_team_player_rows,
        "parquet_rows": parquet_rows,
        "parquet_unique_names": parquet_unique_names,
        "raw_position_rows": raw_pos_rows,
        "raw_position_unique_names": raw_pos_unique_names,
        "raw_position_duplicate_name_rows": raw_pos_duplicate_name_rows,
        "wbb_box_rows": wbb_box_rows,
        "wbb_box_unique_names": wbb_box_unique_names,
        "wbb_box_duplicate_name_rows": wbb_box_duplicate_name_rows,
        "player_bios_2025_raw_rows": player_bios_2025_raw_rows,
        "player_bios_2025_rows": player_bios_2025_rows,
        "raw_age_rows": raw_age_rows,
        "raw_age_unique_names": raw_age_unique_names,
        "master_unique_names": master_unique_names,
        "parquet_name_match_rows": parquet_name_match_rows,
        "parquet_unmatched_pre_fallback_rows": parquet_unmatched_pre_fallback_rows,
        "raw_position_name_fallback_rows": raw_position_name_fallback_rows,
        "wbb_box_name_fallback_rows": wbb_box_name_fallback_rows,
        "final_unmatched_rows": final_unmatched_rows,
        "parquet_team_crosscheck_rows": int(output["parquet_team_crosscheck_flag"].sum()),
        "position_coverage_rows": int((output["position"].notna() | output["position_full"].notna()).sum()),
        "position_abbreviation_coverage_rows": int(output["position_abbreviation"].notna().sum()),
        "age_coverage_rows": int(output["age_2026"].notna().sum()),
        "height_coverage_rows": int(output["height_inches"].notna().sum()),
        "synthetic_id_rows": int(output["synthetic_id_flag"].sum()),
        "name_alias_rows": int(output["name_alias_flag"].sum()),
        "age_match_method_counts": output["age_match_method"].value_counts(dropna=False).to_dict(),
        "bio_match_method_counts": output["bio_match_method"].value_counts(dropna=False).to_dict(),
        "parquet_match_method_counts": output["parquet_match_method"].value_counts(dropna=False).to_dict(),
        "missing_flag_counts": {
            "missing_age_flag": int(output["missing_age_flag"].sum()),
            "missing_height_flag": int(output["missing_height_flag"].sum()),
            "missing_position_flag": int(output["missing_position_flag"].sum()),
        },
        "wbb_position_gap_exact_match_rows": wbb_position_gap_exact_match_rows,
        "wbb_position_gap_ambiguous_match_rows": wbb_position_gap_ambiguous_match_rows,
    }

    if raw_pos_rows != 184:
        raise ValueError(f"Expected 184 raw position rows, found {raw_pos_rows}")
    if raw_pos_unique_names != 184:
        raise ValueError(f"Expected 184 unique raw position names, found {raw_pos_unique_names}")
    if raw_pos_duplicate_name_rows != 0:
        raise ValueError(f"Expected 0 duplicate raw position names, found {raw_pos_duplicate_name_rows}")
    if parquet_rows != 208:
        raise ValueError(f"Expected 208 parquet rows, found {parquet_rows}")
    if parquet_unique_names != 208:
        raise ValueError(f"Expected 208 unique parquet names, found {parquet_unique_names}")
    if player_bios_2025_raw_rows != 182:
        raise ValueError(f"Expected 182 raw player bios 2025 rows, found {player_bios_2025_raw_rows}")
    if raw_age_rows != 216:
        raise ValueError(f"Expected 216 raw age rows, found {raw_age_rows}")
    if raw_age_unique_names != 216:
        raise ValueError(f"Expected 216 unique raw age names, found {raw_age_unique_names}")
    if master_unique_names != 283:
        raise ValueError(f"Expected 283 unique master names, found {master_unique_names}")
    if parquet_name_match_rows != 200:
        raise ValueError(f"Expected 200 parquet name matches, found {parquet_name_match_rows}")
    if parquet_unmatched_pre_fallback_rows != 83:
        raise ValueError(
            f"Expected 83 parquet-unmatched rows before fallback, found {parquet_unmatched_pre_fallback_rows}"
        )
    if raw_position_name_fallback_rows != 23:
        raise ValueError(f"Expected 23 raw-position fallback matches, found {raw_position_name_fallback_rows}")
    if wbb_position_gap_exact_match_rows != 31:
        raise ValueError(
            f"Expected 31 exact WBB position matches among position gaps, found {wbb_position_gap_exact_match_rows}"
        )
    if wbb_position_gap_ambiguous_match_rows != 0:
        raise ValueError(
            f"Expected 0 ambiguous WBB position matches among position gaps, found {wbb_position_gap_ambiguous_match_rows}"
        )
    if wbb_box_name_fallback_rows != 31:
        raise ValueError(f"Expected 31 WBB box fallback matches, found {wbb_box_name_fallback_rows}")
    if final_unmatched_rows != 29:
        raise ValueError(f"Expected 29 final unmatched rows, found {final_unmatched_rows}")
    if unique_rows != 283:
        raise ValueError(f"Expected 283 output rows, found {unique_rows}")
    if unique_teams != 15:
        raise ValueError(f"Expected 15 teams, found {unique_teams}")
    if duplicate_player_id_rows != 0:
        raise ValueError(f"Expected no duplicate player_id rows, found {duplicate_player_id_rows}")
    if duplicate_team_player_rows != 0:
        raise ValueError(f"Expected no duplicate team/player rows, found {duplicate_team_player_rows}")
    if int(output["parquet_team_crosscheck_flag"].sum()) != 12:
        raise ValueError(f"Expected 12 team crosscheck mismatches, found {int(output['parquet_team_crosscheck_flag'].sum())}")
    if int((output["position"].notna() | output["position_full"].notna()).sum()) != 254:
        raise ValueError(
            "Expected 254 rows with position coverage, "
            f"found {int((output['position'].notna() | output['position_full'].notna()).sum())}"
        )
    if int(output["position_abbreviation"].notna().sum()) != 254:
        raise ValueError(f"Expected 254 rows with position abbreviation coverage, found {int(output['position_abbreviation'].notna().sum())}")
    if int(output["age_2026"].notna().sum()) != 223:
        raise ValueError(f"Expected 223 rows with age coverage, found {int(output['age_2026'].notna().sum())}")
    if int(output["height_inches"].notna().sum()) != 223:
        raise ValueError(f"Expected 223 rows with height coverage, found {int(output['height_inches'].notna().sum())}")
    if int(output["missing_age_flag"].sum()) != 60:
        raise ValueError(f"Expected 60 rows missing age, found {int(output['missing_age_flag'].sum())}")
    if int(output["missing_position_flag"].sum()) != 29:
        raise ValueError(f"Expected 29 rows missing position, found {int(output['missing_position_flag'].sum())}")
    if output["bio_match_method"].value_counts(dropna=False).to_dict() != {
        "parquet_name_exact": 200,
        "wbb_box_name_exact": 31,
        "unmatched": 29,
        "raw_pos_name_exact": 23,
    }:
        raise ValueError(f"Unexpected bio_match_method counts: {output['bio_match_method'].value_counts(dropna=False).to_dict()}")

    return output, unmatched, team_crosscheck, summary


def main() -> None:
    output, unmatched, team_crosscheck, summary = build_master_player_bios()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT_CSV_PATH, index=False)
    unmatched.to_csv(UNMATCHED_COMBINED_PATH, index=False)
    team_crosscheck.to_csv(TEAM_CROSSCHECK_PATH, index=False)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "csv_path": str(OUTPUT_CSV_PATH),
                "unmatched_path": str(UNMATCHED_COMBINED_PATH),
                "team_crosscheck_path": str(TEAM_CROSSCHECK_PATH),
                "summary_path": str(SUMMARY_PATH),
                **summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
