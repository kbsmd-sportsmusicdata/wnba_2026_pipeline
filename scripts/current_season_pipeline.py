#!/usr/bin/env python3
"""Run the 2026 current-season ingestion pipeline.

This module keeps pbpstats as the canonical source for discovery, on/off, and
shot/pace data while using SportsDataverse release assets as the fallback layer
for player/team game logs and schedule data.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

import pbpstats_job_runner as pbp_runner


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "current_season" / "wnba_current_season_2026.json"
DEFAULT_PBP_BUNDLE_PATH = ROOT / "configs" / "pbpstats" / "jobs" / "wnba_current_season_bundle.json"
DEFAULT_REGISTRY_PATH = ROOT / "configs" / "pbpstats" / "endpoint_registry.json"
DEFAULT_MASTER_ROOT = ROOT / "data" / "current_season_2026" / "masters"
DEFAULT_RAW_PBP_ROOT = ROOT / "data" / "raw" / "pbpstats" / "current_season_2026"
DEFAULT_RAW_WEHOOP_ROOT = ROOT / "data" / "raw" / "wehoop" / "current_season_2026"
DEFAULT_TIMEOUT = 60
GITHUB_RELEASE_API = "https://api.github.com/repos/{repo}/releases/tags/{tag}"

MASTER_TABLE_SPECS: dict[str, tuple[str, ...]] = {
    "player_onoff_master": ("season", "season_type", "team_id", "player_id", "source_variant"),
    "team_onoff_master": ("season", "season_type", "team_id", "player_id", "source_variant"),
    "player_game_logs_master": ("season", "game_id", "player_id"),
    "team_game_logs_master": ("season", "game_id", "team_id"),
    "schedule_master": ("season", "game_id"),
    "shot_profile_summary_master": ("season", "team_id", "player_id", "source_variant"),
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


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


def season_type_label(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Regular Season"
    text = str(value).strip().lower()
    if text in {"3", "playoff", "playoffs", "postseason"}:
        return "Playoffs"
    if text in {"2", "regular season", "regular_season", "regular"}:
        return "Regular Season"
    return str(value)


def coalesce_column(frame: pd.DataFrame, candidates: Iterable[str], default: Any = None) -> pd.Series:
    for column in candidates:
        if column in frame.columns:
            return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def ensure_string_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column not in output.columns:
            continue
        output[column] = output[column].where(~output[column].isna(), None)
        output[column] = output[column].map(lambda value: None if value is None else str(value))
    return output


def append_dedupe_frame(existing: pd.DataFrame, incoming: pd.DataFrame, key_columns: tuple[str, ...]) -> pd.DataFrame:
    if existing.empty:
        combined = incoming.copy()
    elif incoming.empty:
        combined = existing.copy()
    else:
        combined = pd.concat([existing, incoming], ignore_index=True, sort=False)
    if combined.empty:
        return combined
    combined = combined.drop_duplicates(subset=list(key_columns), keep="first").reset_index(drop=True)
    return combined


def load_existing_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def persist_master_table(path: Path, incoming: pd.DataFrame, key_columns: tuple[str, ...], append: bool) -> dict[str, Any]:
    existing = load_existing_csv(path) if append else pd.DataFrame()
    combined = append_dedupe_frame(existing=existing, incoming=incoming, key_columns=key_columns)
    written = write_table(path.with_suffix(""), combined)
    return {
        "rows_incoming": int(len(incoming)),
        "rows_existing": int(len(existing)),
        "rows_final": int(len(combined)),
        "files": written,
    }


def normalize_wehoop_player_boxscores(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame(
        {
            "season": coalesce_column(frame, ("season", "game_season")),
            "game_id": coalesce_column(frame, ("game_id", "id")).map(lambda value: str(value)),
            "game_date": coalesce_column(frame, ("date", "game_date", "start_date")),
            "season_type": coalesce_column(frame, ("season_type",)).map(season_type_label),
            "player_id": coalesce_column(frame, ("athlete_id", "player_id", "espn_athlete_id")).map(lambda value: str(value)),
            "player_name": coalesce_column(frame, ("athlete_display_name", "player_name", "athlete_name")),
            "team_id": coalesce_column(frame, ("team_id", "team.uid", "team_uid")).map(lambda value: str(value)),
            "team_name": coalesce_column(frame, ("team_display_name", "team_name")),
            "team_abbreviation": coalesce_column(frame, ("team_short_display_name", "team_abbreviation", "team_abbr")),
            "opponent_id": coalesce_column(frame, ("opponent_id", "opponent_uid")).map(lambda value: None if pd.isna(value) else str(value)),
            "opponent_name": coalesce_column(frame, ("opponent_display_name", "opponent_name")),
            "minutes": pd.to_numeric(coalesce_column(frame, ("minutes", "min")), errors="coerce"),
            "points": pd.to_numeric(coalesce_column(frame, ("points", "pts")), errors="coerce"),
            "rebounds": pd.to_numeric(coalesce_column(frame, ("rebounds", "reb")), errors="coerce"),
            "assists": pd.to_numeric(coalesce_column(frame, ("assists", "ast")), errors="coerce"),
            "source_system": "wehoop",
            "source_variant": "player_boxscores",
        }
    )
    return ensure_string_columns(normalized, ("season", "game_id", "player_id", "team_id", "opponent_id"))


def normalize_wehoop_team_boxscores(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame(
        {
            "season": coalesce_column(frame, ("season", "game_season")),
            "game_id": coalesce_column(frame, ("game_id", "id")).map(lambda value: str(value)),
            "game_date": coalesce_column(frame, ("date", "game_date", "start_date")),
            "season_type": coalesce_column(frame, ("season_type",)).map(season_type_label),
            "team_id": coalesce_column(frame, ("team_id", "team.uid", "team_uid")).map(lambda value: str(value)),
            "team_name": coalesce_column(frame, ("team_display_name", "team_name")),
            "team_abbreviation": coalesce_column(frame, ("team_short_display_name", "team_abbreviation", "team_abbr")),
            "opponent_id": coalesce_column(frame, ("opponent_id", "opponent_uid")).map(lambda value: None if pd.isna(value) else str(value)),
            "opponent_name": coalesce_column(frame, ("opponent_display_name", "opponent_name")),
            "points": pd.to_numeric(coalesce_column(frame, ("points", "pts")), errors="coerce"),
            "rebounds": pd.to_numeric(coalesce_column(frame, ("rebounds", "reb")), errors="coerce"),
            "assists": pd.to_numeric(coalesce_column(frame, ("assists", "ast")), errors="coerce"),
            "source_system": "wehoop",
            "source_variant": "team_boxscores",
        }
    )
    return ensure_string_columns(normalized, ("season", "game_id", "team_id", "opponent_id"))


def normalize_wehoop_schedule(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame(
        {
            "season": coalesce_column(frame, ("season", "game_season")),
            "game_id": coalesce_column(frame, ("game_id", "id")).map(lambda value: str(value)),
            "game_date": coalesce_column(frame, ("date", "game_date", "start_date")),
            "season_type": coalesce_column(frame, ("season_type",)).map(season_type_label),
            "home_team_id": coalesce_column(frame, ("home_team_id", "home_team.uid")).map(lambda value: str(value)),
            "home_team_name": coalesce_column(frame, ("home_team_display_name", "home_team_name")),
            "away_team_id": coalesce_column(frame, ("away_team_id", "away_team.uid")).map(lambda value: str(value)),
            "away_team_name": coalesce_column(frame, ("away_team_display_name", "away_team_name")),
            "source_system": "wehoop",
            "source_variant": "schedules",
        }
    )
    return ensure_string_columns(normalized, ("season", "game_id", "home_team_id", "away_team_id"))


def normalize_pbpstats_onoff(frame: pd.DataFrame, variant: str) -> pd.DataFrame:
    normalized = frame.copy()
    normalized["source_system"] = "pbpstats"
    normalized["source_variant"] = variant
    for column in ("season", "team_id", "player_id"):
        if column in normalized.columns:
            normalized[column] = normalized[column].map(lambda value: None if pd.isna(value) else str(value))
    if "season_type" in normalized.columns:
        normalized["season_type"] = normalized["season_type"].map(season_type_label)
    return normalized


def normalize_pbpstats_games(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = pd.DataFrame(
        {
            "season": coalesce_column(frame, ("season",)),
            "game_id": coalesce_column(frame, ("game_id", "source_game_id")).map(lambda value: str(value)),
            "game_date": coalesce_column(frame, ("date", "game_date", "start_time")),
            "season_type": coalesce_column(frame, ("season_type",)).map(season_type_label),
            "home_team_id": coalesce_column(frame, ("home_team_id",)).map(lambda value: None if pd.isna(value) else str(value)),
            "home_team_name": coalesce_column(frame, ("home_team_name", "home_team_display_name")),
            "away_team_id": coalesce_column(frame, ("away_team_id",)).map(lambda value: None if pd.isna(value) else str(value)),
            "away_team_name": coalesce_column(frame, ("away_team_name", "away_team_display_name")),
            "source_system": "pbpstats",
            "source_variant": "discovery_games",
        }
    )
    return ensure_string_columns(normalized, ("season", "game_id", "home_team_id", "away_team_id"))


def _zone_bucket(value: Any) -> str:
    text = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).lower()
    if "rim" in text:
        return "at_rim"
    if "corner" in text:
        return "corner3"
    if "arc" in text or "3" in text:
        return "arc3"
    return "other"


def summarize_pbpstats_shots(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "season",
                "team_id",
                "player_id",
                "attempts",
                "made",
                "at_rim_frequency",
                "corner3_frequency",
                "arc3_frequency",
                "source_system",
                "source_variant",
            ]
        )
    working = frame.copy()
    working["season"] = coalesce_column(working, ("season",))
    working["team_id"] = coalesce_column(working, ("team_id", "request_params_entity_id", "request_params_team_id")).map(
        lambda value: None if pd.isna(value) else str(value)
    )
    working["player_id"] = coalesce_column(
        working,
        ("player_id", "shooter_player_id", "shooter_id", "player1_id", "shooting_player_id"),
        default="team",
    ).map(lambda value: None if pd.isna(value) else str(value))
    working["made_flag"] = pd.to_numeric(
        coalesce_column(working, ("made", "is_make", "shot_made", "made_shot"), default=0),
        errors="coerce",
    ).fillna(0)
    zones = coalesce_column(
        working,
        ("shot_zone", "shot_zone_basic", "shot_type", "zone", "shot_value", "description"),
        default="other",
    ).map(_zone_bucket)
    working["zone_bucket"] = zones
    grouped = (
        working.groupby(["season", "team_id", "player_id"], dropna=False)
        .agg(
            attempts=("player_id", "size"),
            made=("made_flag", "sum"),
            at_rim_attempts=("zone_bucket", lambda values: int((values == "at_rim").sum())),
            corner3_attempts=("zone_bucket", lambda values: int((values == "corner3").sum())),
            arc3_attempts=("zone_bucket", lambda values: int((values == "arc3").sum())),
        )
        .reset_index()
    )
    grouped["at_rim_frequency"] = grouped["at_rim_attempts"] / grouped["attempts"].where(grouped["attempts"] != 0, 1)
    grouped["corner3_frequency"] = grouped["corner3_attempts"] / grouped["attempts"].where(grouped["attempts"] != 0, 1)
    grouped["arc3_frequency"] = grouped["arc3_attempts"] / grouped["attempts"].where(grouped["attempts"] != 0, 1)
    grouped["source_system"] = "pbpstats"
    grouped["source_variant"] = "shot_profile_summary"
    return grouped


def _requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/vnd.github+json"})
    return session


def fetch_release_metadata(tag: str, repo: str = "sportsdataverse/sportsdataverse-data") -> dict[str, Any]:
    session = _requests_session()
    response = session.get(GITHUB_RELEASE_API.format(repo=repo, tag=tag), timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json()


def pick_release_asset(release_payload: dict[str, Any], season: str | int) -> dict[str, Any]:
    assets = release_payload.get("assets", [])
    if not assets:
        raise RuntimeError(f"Release {release_payload.get('tag_name')} does not contain downloadable assets.")

    season_text = str(season)
    ranked = sorted(
        assets,
        key=lambda asset: (
            season_text not in str(asset.get("name", "")),
            not str(asset.get("name", "")).endswith(".parquet"),
            not str(asset.get("name", "")).endswith(".csv.gz"),
            not str(asset.get("name", "")).endswith(".csv"),
            not str(asset.get("name", "")).endswith(".zip"),
        ),
    )
    return ranked[0]


def download_release_asset(asset: dict[str, Any], target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / asset["name"]
    session = _requests_session()
    response = session.get(asset["browser_download_url"], timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    target_path.write_bytes(response.content)
    return target_path


def load_release_frame(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".parquet"):
        return pd.read_parquet(path)
    if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
        return pd.read_csv(path)
    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.endswith((".csv", ".parquet"))]
            if not members:
                raise RuntimeError(f"No tabular file found inside {path}")
            member = members[0]
            extract_path = path.parent / member
            archive.extract(member, path.parent)
            return load_release_frame(extract_path)
    raise RuntimeError(f"Unsupported release asset type: {path.name}")


def _glob_csvs(pattern: str) -> list[Path]:
    return sorted(path for path in ROOT.glob(pattern) if path.suffix == ".csv")


def _concat_frames(paths: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def run_pbpstats_current_season(
    bundle_path: Path,
    registry_path: Path,
    output_root: Path,
    season: str,
    full_refresh: bool,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    print(f"[current-season] starting pbpstats refresh for season={season} full_refresh={full_refresh}", flush=True)
    summary = pbp_runner.run_bundle(
        bundle_path=bundle_path,
        registry_path=registry_path,
        output_root=output_root,
        seasons=[str(season)],
        season_types=["Regular Season", "Playoffs"],
        full=full_refresh,
        max_team_ids_per_season=None if full_refresh else 2,
        max_player_ids_per_team=None if full_refresh else 2,
    )
    print(
        f"[current-season] pbpstats refresh complete requested_seasons={summary.get('requested_seasons')} records={summary.get('records')}",
        flush=True,
    )
    return summary


def ingest_wehoop_sources(config: dict[str, Any], season: str, raw_root: Path, since_date: str | None = None) -> dict[str, pd.DataFrame]:
    outputs: dict[str, pd.DataFrame] = {}
    for source_name, source_config in config["wehoop_sources"].items():
        print(f"[current-season] starting wehoop source={source_name} tag={source_config['release_tag']}", flush=True)
        tag = source_config["release_tag"]
        release_payload = fetch_release_metadata(tag)
        asset = pick_release_asset(release_payload, season=season)
        asset_path = download_release_asset(asset, raw_root / source_name / "raw")
        metadata_path = raw_root / source_name / "manifest.json"
        write_json(metadata_path, {"tag": tag, "asset_name": asset["name"], "asset_url": asset["browser_download_url"]})
        frame = load_release_frame(asset_path)
        if "season" in frame.columns:
            frame = frame[frame["season"].astype(str) == str(season)].copy()
        if since_date and "date" in frame.columns:
            frame = frame[frame["date"].astype(str) >= str(since_date)].copy()
        if source_name == "player_boxscores":
            normalized = normalize_wehoop_player_boxscores(frame)
        elif source_name == "team_boxscores":
            normalized = normalize_wehoop_team_boxscores(frame)
        elif source_name == "schedules":
            normalized = normalize_wehoop_schedule(frame)
        else:
            normalized = frame.copy()
        write_table(raw_root / source_name / "normalized" / source_name, normalized)
        outputs[source_name] = normalized
        print(f"[current-season] wehoop source={source_name} rows={len(normalized)} complete", flush=True)
    return outputs


def build_master_tables(
    pbp_output_root: Path,
    wehoop_outputs: dict[str, pd.DataFrame],
    master_root: Path,
    append: bool,
) -> dict[str, Any]:
    master_root.mkdir(parents=True, exist_ok=True)
    print("[current-season] building master tables", flush=True)
    player_onoff = normalize_pbpstats_onoff(
        _concat_frames((pbp_output_root / "wnba_current_season_on_off" / "derived" / "get-on-off").glob("player_on_off__*.csv")),
        variant="player_on_off",
    )
    team_onoff = normalize_pbpstats_onoff(
        _concat_frames((pbp_output_root / "wnba_current_season_on_off" / "derived" / "get-on-off").glob("team_on_off__*.csv")),
        variant="team_on_off",
    )
    pbp_games = normalize_pbpstats_games(
        _concat_frames((pbp_output_root / "wnba_current_season_league_discovery" / "normalized" / "get-games").glob("*.csv"))
    )
    shot_profile = summarize_pbpstats_shots(
        _concat_frames((pbp_output_root / "wnba_current_season_shot_pace" / "normalized" / "get-shots").glob("*.csv"))
    )

    schedule_master = wehoop_outputs.get("schedules", pd.DataFrame())
    if schedule_master.empty:
        schedule_master = pbp_games

    summaries = {
        "player_onoff_master": persist_master_table(
            master_root / "player_onoff_master.csv",
            incoming=player_onoff,
            key_columns=MASTER_TABLE_SPECS["player_onoff_master"],
            append=append,
        ),
        "team_onoff_master": persist_master_table(
            master_root / "team_onoff_master.csv",
            incoming=team_onoff,
            key_columns=MASTER_TABLE_SPECS["team_onoff_master"],
            append=append,
        ),
        "player_game_logs_master": persist_master_table(
            master_root / "player_game_logs_master.csv",
            incoming=wehoop_outputs.get("player_boxscores", pd.DataFrame()),
            key_columns=MASTER_TABLE_SPECS["player_game_logs_master"],
            append=append,
        ),
        "team_game_logs_master": persist_master_table(
            master_root / "team_game_logs_master.csv",
            incoming=wehoop_outputs.get("team_boxscores", pd.DataFrame()),
            key_columns=MASTER_TABLE_SPECS["team_game_logs_master"],
            append=append,
        ),
        "schedule_master": persist_master_table(
            master_root / "schedule_master.csv",
            incoming=schedule_master,
            key_columns=MASTER_TABLE_SPECS["schedule_master"],
            append=append,
        ),
        "shot_profile_summary_master": persist_master_table(
            master_root / "shot_profile_summary_master.csv",
            incoming=shot_profile,
            key_columns=MASTER_TABLE_SPECS["shot_profile_summary_master"],
            append=append,
        ),
    }
    write_json(master_root / "manifest.json", summaries)
    print("[current-season] master tables complete", flush=True)
    return summaries


def run_current_season_pipeline(
    config_path: Path = DEFAULT_CONFIG_PATH,
    season: str = "2026",
    family: str = "all",
    source_policy: str = "pbpstats_first",
    append: bool = True,
    full_refresh: bool = False,
    since_date: str | None = None,
) -> dict[str, Any]:
    config = read_json(config_path)
    pbp_output_root = ROOT / config["paths"].get("pbpstats_output_root", str(DEFAULT_RAW_PBP_ROOT.relative_to(ROOT)))
    wehoop_raw_root = ROOT / config["paths"].get("wehoop_raw_root", str(DEFAULT_RAW_WEHOOP_ROOT.relative_to(ROOT)))
    master_root = ROOT / config["paths"].get("master_root", str(DEFAULT_MASTER_ROOT.relative_to(ROOT)))

    summary: dict[str, Any] = {
        "season": str(season),
        "family": family,
        "source_policy": source_policy,
        "append": append,
        "full_refresh": full_refresh,
        "pbpstats": None,
        "wehoop_sources": [],
        "master_tables": None,
    }

    if family in {"all", "pbpstats"}:
        summary["pbpstats"] = run_pbpstats_current_season(
            bundle_path=ROOT / config["paths"]["pbpstats_bundle_path"],
            registry_path=ROOT / config["paths"]["pbpstats_registry_path"],
            output_root=pbp_output_root,
            season=str(season),
            full_refresh=full_refresh,
        )

    wehoop_outputs: dict[str, pd.DataFrame] = {}
    if family in {"all", "wehoop", "game_logs", "schedules"}:
        wehoop_outputs = ingest_wehoop_sources(config=config, season=str(season), raw_root=wehoop_raw_root, since_date=since_date)
        summary["wehoop_sources"] = sorted(wehoop_outputs.keys())

    if family == "masters" and not wehoop_outputs:
        for source_name in ("player_boxscores", "team_boxscores", "schedules"):
            csv_path = wehoop_raw_root / source_name / "normalized" / f"{source_name}.csv"
            if csv_path.exists():
                wehoop_outputs[source_name] = pd.read_csv(csv_path)

    if family in {"all", "masters", "pbpstats", "wehoop", "game_logs", "schedules"}:
        summary["master_tables"] = build_master_tables(
            pbp_output_root=pbp_output_root,
            wehoop_outputs=wehoop_outputs,
            master_root=master_root,
            append=append,
        )

    write_json(master_root / "pipeline_summary.json", summary)
    print("[current-season] pipeline summary written", flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the WNBA 2026 current-season ingestion pipeline.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Current-season pipeline config JSON.")
    parser.add_argument("--season", default="2026", help="Current season to refresh.")
    parser.add_argument(
        "--family",
        choices=("all", "pbpstats", "wehoop", "game_logs", "schedules", "masters"),
        default="all",
        help="Pipeline family to run.",
    )
    parser.add_argument("--source-policy", default="pbpstats_first", help="Source routing policy label to store in manifests.")
    parser.add_argument("--append", action="store_true", help="Append only new rows into master tables.")
    parser.add_argument("--full-refresh", action="store_true", help="Run the full season universe instead of a small smoke slice.")
    parser.add_argument("--since-date", default=None, help="Optional YYYY-MM-DD lower bound for schedule or game-log rows.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_current_season_pipeline(
        config_path=args.config,
        season=str(args.season),
        family=args.family,
        source_policy=args.source_policy,
        append=args.append,
        full_refresh=args.full_refresh,
        since_date=args.since_date,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
