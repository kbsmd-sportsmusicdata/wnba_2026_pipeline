#!/usr/bin/env python3
"""Generic pbpstats job runner.

This module executes bundle specs that describe one or more pbpstats jobs.
It writes raw JSON, normalized CSV/Parquet, derived CSV/Parquet, and manifest
files under a per-job directory.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_BASE = "https://api.pbpstats.com"
DEFAULT_REGISTRY_PATH = Path("configs/pbpstats/endpoint_registry.json")
DEFAULT_BUNDLE_PATH = Path("configs/pbpstats/jobs/wnba_roster_value_bundle.json")
DEFAULT_OUTPUT_ROOT = Path("data/pbpstats_jobs")
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.4
DEFAULT_MINIMUM_SEASONS = ["2025", "2024", "2023"]
DEFAULT_REQUESTED_SEASON_TYPES = ["Regular Season", "Playoffs"]
DEFAULT_SMOKE_SEASONS = ["2025"]
DEFAULT_SMOKE_SEASON_TYPES = ["Regular Season"]
DEFAULT_SMOKE_TEAM_CAP = 1
DEFAULT_SMOKE_PLAYER_CAP = 1

PRESET_FAMILIES: dict[str, list[str]] = {
    "totals": ["totals"],
    "on_off": ["league_discovery", "on_off"],
    "shot_pace": ["league_discovery", "shot_pace"],
    "roster_value": ["league_discovery", "totals", "on_off", "shot_pace"],
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


save_json = write_json


def slugify(value: Any) -> str:
    text = str(value)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "all"


def to_snake_case(name: str) -> str:
    if not name:
        return name
    if name.isupper():
        return name.lower()
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    return name.replace("-", "_").lower()


def flatten_record(record: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in record.items():
        snake_key = to_snake_case(str(key))
        full_key = f"{prefix}_{snake_key}" if prefix else snake_key
        if isinstance(value, Mapping):
            flattened.update(flatten_record(value, full_key))
            continue
        if isinstance(value, list):
            if not value:
                flattened[full_key] = []
                continue
            if all(not isinstance(item, (Mapping, list)) for item in value):
                flattened[full_key] = value
                continue
            flattened[full_key] = json.dumps(value, ensure_ascii=False)
            continue
        flattened[full_key] = value
    return flattened


def build_session(timeout_seconds: int, retries: int, backoff_factor: float) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def endpoint_url(endpoint_path: str, league: str, **path_vars: Any) -> str:
    return f"{API_BASE}/{endpoint_path.format(league=league, **path_vars)}"


def request_json(session: requests.Session, url: str, params: dict[str, Any], timeout_seconds: int) -> tuple[Any, str, int]:
    try:
        response = session.get(url, params=params, timeout=timeout_seconds)
        status_code = response.status_code
        response.raise_for_status()
        return response.json(), response.url, status_code
    except requests.RequestException as exc:  # pragma: no cover - network/runtime dependent
        raise RuntimeError(f"Failed to fetch pbpstats payload from {url} with params {params}: {exc}") from exc


def stable_stem(endpoint: str, params: Mapping[str, Any], keep_keys: Iterable[str], suffix: str | None = None) -> str:
    parts = [endpoint]
    if suffix:
        parts.append(suffix)
    for key in keep_keys:
        if key in params and params[key] is not None:
            parts.append(f"{to_snake_case(str(key))}-{slugify(params[key])}")
    payload = json.dumps({k: params[k] for k in sorted(params)}, sort_keys=True, default=str)
    digest = sha1(payload.encode("utf-8")).hexdigest()[:8]
    parts.append(digest)
    return "__".join(parts)


def save_frame(path: Path, rows: list[dict[str, Any]], output_profile: list[str]) -> list[Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    written: list[Path] = []
    if any(profile in output_profile for profile in ("csv", "normalized_csv", "derived_csv", "flat_csv")):
        csv_path = path.with_suffix(".csv")
        frame.to_csv(csv_path, index=False)
        written.append(csv_path)
    if "parquet" in output_profile:
        parquet_path = path.with_suffix(".parquet")
        try:
            frame.to_parquet(parquet_path, index=False)
            written.append(parquet_path)
        except Exception:
            # Keep CSV as the guaranteed output if parquet tooling is unavailable.
            pass
    return written


def extract_tables(payload: Any) -> dict[str, list[dict[str, Any]]]:
    if isinstance(payload, list):
        rows = [flatten_record(item) if isinstance(item, Mapping) else {"value": item} for item in payload]
        return {"results": rows}

    if not isinstance(payload, Mapping):
        return {"results": [{"value": payload}]}

    players_value = payload.get("players")
    if isinstance(players_value, Mapping):
        player_rows = []
        for player_id, player_name in players_value.items():
            player_rows.append(
                {
                    "player_id": str(player_id),
                    "player_name": player_name,
                }
            )
        return {"players": player_rows}
    if isinstance(players_value, list):
        player_rows = []
        for row in players_value:
            if isinstance(row, Mapping):
                player_rows.append(flatten_record(row))
            else:
                player_rows.append({"value": row})
        return {"players": player_rows}

    table_keys = [key for key in ("results", "possessions", "player_results", "team_results", "single_row_table_data", "multi_row_table_data", "players", "teams", "career_totals", "header", "win_loss_record") if isinstance(payload.get(key), list)]
    if table_keys:
        tables: dict[str, list[dict[str, Any]]] = {}
        for key in table_keys:
            table_rows = payload.get(key) or []
            tables[key] = [flatten_record(row) if isinstance(row, Mapping) else {"value": row} for row in table_rows]
        return tables

    return {"results": [flatten_record(payload)]}


def add_request_metadata(rows: list[dict[str, Any]], metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    public_metadata = {key: value for key, value in metadata.items() if not str(key).startswith("_")}
    enriched: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        merged = dict(public_metadata)
        merged["request_row_index"] = index
        merged.update(row)
        enriched.append(merged)
    return enriched


def derive_rows(rows: list[dict[str, Any]], context: Mapping[str, Any], family: str, endpoint: str, table_name: str) -> list[dict[str, Any]]:
    derived: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item.setdefault("season", context.get("season"))
        item.setdefault("season_type", context.get("season_type"))
        item.setdefault("is_playoffs", str(item.get("season_type")) == "Playoffs")
        item.setdefault("league", context.get("league"))
        item.setdefault("endpoint", endpoint)
        item.setdefault("job_id", context.get("job_id"))
        item.setdefault("job_family", family)
        item.setdefault("job_variant", context.get("variant"))

        if family == "totals":
            games_played = item.get("games_played")
            minutes = item.get("minutes")
            if isinstance(games_played, (int, float)) and games_played:
                for src, dst in [("points", "ppg"), ("rebounds", "rpg"), ("assists", "apg"), ("steals", "spg"), ("blocks", "bpg"), ("turnovers", "tov_pg")]:
                    if src in item and dst not in item and isinstance(item[src], (int, float)):
                        item[dst] = round(float(item[src]) / float(games_played), 4)
                if isinstance(minutes, (int, float)) and "mpg" not in item:
                    item["mpg"] = round(float(minutes) / float(games_played), 4)

        if family == "on_off":
            on_minutes = item.get("on_minutes")
            off_minutes = item.get("off_minutes")
            if isinstance(on_minutes, (int, float)) and isinstance(off_minutes, (int, float)):
                total_minutes = on_minutes + off_minutes
                item["minutes_total"] = total_minutes
                if total_minutes:
                    item["on_minutes_share"] = round(on_minutes / total_minutes, 4)
                    item["off_minutes_share"] = round(off_minutes / total_minutes, 4)
            if "on_net_rating" in item and "off_net_rating" in item and "net_rating_diff" not in item:
                if isinstance(item["on_net_rating"], (int, float)) and isinstance(item["off_net_rating"], (int, float)):
                    item["net_rating_diff"] = round(float(item["on_net_rating"]) - float(item["off_net_rating"]), 4)
            if "minutes_on" in item and "minutes_off" in item:
                on_minutes_2 = item.get("minutes_on")
                off_minutes_2 = item.get("minutes_off")
                if isinstance(on_minutes_2, (int, float)) and isinstance(off_minutes_2, (int, float)):
                    total_minutes = on_minutes_2 + off_minutes_2
                    item["minutes_total"] = total_minutes
                    if total_minutes:
                        item["on_minutes_share"] = round(on_minutes_2 / total_minutes, 4)
                        item["off_minutes_share"] = round(off_minutes_2 / total_minutes, 4)

        if family == "shot_pace":
            if context.get("clutch_window"):
                item["window_label"] = context["clutch_window"]
            item["request_scope"] = context.get("scope")

        if family == "league_discovery":
            item["request_scope"] = context.get("scope")

        derived.append(item)
    return derived


def save_tables(base_dir: Path, endpoint: str, variant: str, payload: Any, context: Mapping[str, Any], family: str, output_profile: list[str]) -> dict[str, Any]:
    tables = extract_tables(payload)
    table_paths: list[str] = []
    derived_paths: list[str] = []
    table_counts: dict[str, int] = {}

    for table_name, rows in tables.items():
        if endpoint == "get-pace-efficiency-by-season" and table_name == "results" and context.get("_request_seasons"):
            allowed = {str(season) for season in context["_request_seasons"]}
            rows = [row for row in rows if str(row.get("season")) in allowed]
        enriched_rows = add_request_metadata(rows, context)
        stem = stable_stem(endpoint, context.get("request_params", {}), context.get("_stem_keys", []), None)
        normalized_path = base_dir / "normalized" / endpoint / f"{variant}__{stem}__{table_name}"
        table_paths.extend(str(path) for path in save_frame(normalized_path, enriched_rows, output_profile))
        table_counts[table_name] = len(enriched_rows)

        derived_rows = derive_rows(enriched_rows, context, family, endpoint, table_name)
        derived_path = base_dir / "derived" / endpoint / f"{variant}__{stem}__{table_name}"
        derived_paths.extend(str(path) for path in save_frame(derived_path, derived_rows, output_profile))

    return {"table_paths": table_paths, "derived_paths": derived_paths, "table_counts": table_counts}


def normalize_seasons(spec_seasons: Iterable[Any], minimum_seasons: Iterable[Any]) -> list[str]:
    ordered: list[str] = []
    for season in list(spec_seasons) + list(minimum_seasons):
        season_str = str(season)
        if season_str not in ordered:
            ordered.append(season_str)
    return ordered


def normalize_requested_season_types(spec_season_types: Iterable[Any] | None) -> list[str]:
    values = [str(item) for item in (spec_season_types or DEFAULT_REQUESTED_SEASON_TYPES)]
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def select_jobs(bundle_jobs: list[dict[str, Any]], preset: str | None) -> list[dict[str, Any]]:
    if not preset:
        return list(bundle_jobs)
    if preset not in PRESET_FAMILIES:
        raise ValueError(f"Unsupported preset: {preset}")
    wanted = PRESET_FAMILIES[preset]
    selected: list[dict[str, Any]] = []
    for job in bundle_jobs:
        if job.get("family") in wanted:
            selected.append(job)
    return selected


def season_type_plan(endpoint_meta: Mapping[str, Any], requested_season_types: list[str], fallback: str) -> list[str]:
    supported = requested_season_types if endpoint_meta.get("supports_playoffs", False) else [fallback]
    ordered: list[str] = []
    for item in supported:
        if item not in ordered:
            ordered.append(item)
    if not ordered:
        ordered.append(fallback)
    return ordered


def discovery_team_catalog(games_payload: Any, season: str, season_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(games_payload, Mapping):
        return rows
    seen: set[str] = set()
    for game in games_payload.get("results", []):
        if not isinstance(game, Mapping):
            continue
        for side in ("Home", "Away"):
            team_id = game.get(f"{side}TeamId")
            team_abbr = game.get(f"{side}TeamAbbreviation")
            if not team_id or str(team_id) in seen:
                continue
            seen.add(str(team_id))
            rows.append(
                {
                    "season": season,
                    "season_type": season_type,
                    "team_id": str(team_id),
                    "team_abbreviation": team_abbr,
                    "source_game_id": game.get("GameId")
                }
            )
    return rows


def discovery_player_catalog(players_payload: Any, season: str, season_type: str, team_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(players_payload, Mapping):
        return rows
    players_value = players_payload.get("players", [])
    if isinstance(players_value, Mapping):
        for player_id, player_name in players_value.items():
            rows.append(
                {
                    "season": season,
                    "season_type": season_type,
                    "team_id": team_id,
                    "player_id": str(player_id),
                    "player_name": player_name,
                }
            )
        return rows
    for player in players_value:
        if not isinstance(player, Mapping):
            continue
        rows.append(
            {
                "season": season,
                "season_type": season_type,
                "team_id": team_id,
                "player_id": str(player.get("id")),
                "player_name": player.get("text"),
            }
        )
    return rows


def dedupe_rows(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        signature = tuple(row.get(key) for key in keys)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped


def request_common_params(job: Mapping[str, Any], variant: Mapping[str, Any]) -> dict[str, Any]:
    params = {}
    params.update(job.get("common_params", {}))
    params.update(variant.get("request_params", {}))
    return params


def write_raw_payload(base_dir: Path, endpoint: str, variant: str, stem: str, payload: Any) -> Path:
    raw_path = base_dir / "raw" / endpoint / f"{variant}__{stem}.json"
    write_json(raw_path, payload)
    return raw_path


def build_metadata(league: str, job_id: str, family: str, variant: str, season: str | None, season_type: str, scope: str, endpoint: str, request_params: Mapping[str, Any], extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    metadata = {
        "league": league,
        "job_id": job_id,
        "job_family": family,
        "variant": variant,
        "endpoint": endpoint,
        "season": season,
        "season_type": season_type,
        "scope": scope,
        "request_params": dict(request_params),
    }
    if extra:
        metadata.update(extra)
    return metadata


def request_error_details(exc: Exception) -> dict[str, Any]:
    details = {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    cause = getattr(exc, "__cause__", None)
    response = getattr(cause, "response", None)
    if response is not None:
        details["status"] = getattr(response, "status_code", None)
        try:
            details["response_text"] = response.text[:500]
        except Exception:  # pragma: no cover - defensive
            details["response_text"] = None
    return details


def write_failure_payload(base_dir: Path, endpoint: str, variant: str, stem: str, details: Mapping[str, Any]) -> Path:
    error_path = base_dir / "raw" / endpoint / f"{variant}__{stem}__error.json"
    write_json(error_path, dict(details))
    return error_path


def run_endpoint_request(
    session: requests.Session,
    base_dir: Path,
    registry: Mapping[str, Any],
    league: str,
    job: Mapping[str, Any],
    variant: Mapping[str, Any],
    context: dict[str, Any],
    request_params: dict[str, Any],
    season: str | None,
    season_type: str,
    output_profile: list[str],
) -> dict[str, Any]:
    endpoint = variant["endpoint"]
    endpoint_meta = registry["families"][job["family"]]["endpoints"][endpoint]
    path = endpoint_url(endpoint_meta["path"], league, stat_type=variant.get("stat_type"))
    request_params = dict(request_params)
    stem_keys = ["season", "season_type", "scope"] + list(request_params.keys())
    stem = stable_stem(endpoint, request_params, stem_keys, suffix=variant["name"])

    metadata = build_metadata(
        league=league,
        job_id=job["job_id"],
        family=job["family"],
        variant=variant["name"],
        season=season,
        season_type=season_type,
        scope=variant["scope"],
        endpoint=endpoint,
        request_params=request_params,
        extra=context,
    )
    metadata["request_id"] = stem
    metadata["_stem_keys"] = stem_keys
    metadata["request_table"] = endpoint
    try:
        payload, final_url, status_code = request_json(session, path, request_params, DEFAULT_TIMEOUT_SECONDS)
        raw_path = write_raw_payload(base_dir, endpoint, variant["name"], stem, payload)
        metadata["request_url"] = final_url
        metadata["request_status"] = status_code
        table_result = save_tables(base_dir, endpoint, variant["name"], payload, metadata, job["family"], output_profile)
        return {
            "job_id": job["job_id"],
            "family": job["family"],
            "variant": variant["name"],
            "endpoint": endpoint,
            "request_url": final_url,
            "request_status": status_code,
            "request_id": stem,
            "ok": True,
            "raw_path": str(raw_path),
            "table_paths": table_result["table_paths"],
            "derived_paths": table_result["derived_paths"],
            "table_counts": table_result["table_counts"],
            "request_params": request_params,
            "season": season,
            "season_type": season_type,
        }
    except Exception as exc:  # pragma: no cover - live API / network dependent
        details = request_error_details(exc)
        raw_path = write_failure_payload(base_dir, endpoint, variant["name"], stem, details)
        return {
            "job_id": job["job_id"],
            "family": job["family"],
            "variant": variant["name"],
            "endpoint": endpoint,
            "request_url": path,
            "request_status": details.get("status"),
            "request_id": stem,
            "ok": False,
            "error": details,
            "raw_path": str(raw_path),
            "table_paths": [],
            "derived_paths": [],
            "table_counts": {},
            "request_params": request_params,
            "season": season,
            "season_type": season_type,
        }


def run_league_discovery_job(
    session: requests.Session,
    registry: Mapping[str, Any],
    bundle: Mapping[str, Any],
    job: Mapping[str, Any],
    output_root: Path,
    requested_seasons: list[str],
    requested_season_types: list[str],
    fallback_season_type: str,
    output_profile: list[str],
    max_team_ids_per_season: int | None,
    max_player_ids_per_team: int | None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    job_dir = output_root / job["job_id"]
    manifests: list[dict[str, Any]] = []
    discovery_cache: dict[str, list[dict[str, Any]]] = {
        "season_team_catalog": [],
        "team_player_catalog": []
    }

    variants = job["variants"]
    league = bundle["league"]
    family = job["family"]

    for season in requested_seasons:
        for variant in variants:
            endpoint = variant["endpoint"]
            endpoint_meta = registry["families"][family]["endpoints"][endpoint]
            season_types = season_type_plan(endpoint_meta, requested_season_types, fallback_season_type)
            if variant["scope"] == "season":
                for season_type in season_types:
                    request_params = request_common_params(job, variant)
                    request_params.update({"SeasonType": season_type, "Season": season})
                    record = run_endpoint_request(
                        session=session,
                        base_dir=job_dir,
                        registry=registry,
                        league=league,
                        job=job,
                        variant=variant,
                        context={"source": "discovery"},
                        request_params=request_params,
                        season=season,
                        season_type=season_type,
                        output_profile=output_profile,
                    )
                    manifests.append(record)
                    if endpoint == "get-games":
                        payload = read_json(Path(record["raw_path"]))
                        rows = discovery_team_catalog(payload, season, season_type)
                        discovery_cache["season_team_catalog"].extend(rows)
            elif variant["scope"] == "team":
                # We derive team ids from get-games payloads saved earlier.
                for season_type in season_types:
                    # Prefer cached team catalogs by season_type, else reuse any discovered team list.
                    team_rows = [row for row in discovery_cache["season_team_catalog"] if row["season"] == season and row["season_type"] == season_type]
                    team_ids = [row["team_id"] for row in team_rows]
                    if max_team_ids_per_season is not None:
                        team_ids = team_ids[:max_team_ids_per_season]
                    for team_id in team_ids:
                        request_params = request_common_params(job, variant)
                        request_params.update({"SeasonType": season_type, "Season": season, "TeamId": team_id})
                        record = run_endpoint_request(
                            session=session,
                            base_dir=job_dir,
                            registry=registry,
                            league=league,
                            job=job,
                            variant=variant,
                            context={"source": "discovery", "team_id": team_id},
                            request_params=request_params,
                            season=season,
                            season_type=season_type,
                            output_profile=output_profile,
                        )
                        manifests.append(record)
                        if endpoint == "get-team-players-for-season":
                            payload_rows = []
                            raw_path = Path(record["raw_path"])
                            if raw_path.exists():
                                payload = read_json(raw_path)
                                payload_rows = discovery_player_catalog(payload, season, season_type, team_id)
                            if max_player_ids_per_team is not None:
                                payload_rows = payload_rows[:max_player_ids_per_team]
                            discovery_cache["team_player_catalog"].extend(payload_rows)
            elif variant["scope"] == "season_type_only":
                for season_type in season_types:
                    request_params = request_common_params(job, variant)
                    request_params.update({"SeasonType": season_type})
                    record = run_endpoint_request(
                        session=session,
                        base_dir=job_dir,
                        registry=registry,
                        league=league,
                        job=job,
                        variant=variant,
                        context={"source": "discovery"},
                        request_params=request_params,
                        season=None,
                        season_type=season_type,
                        output_profile=output_profile,
                    )
                    manifests.append(record)

    if discovery_cache["season_team_catalog"]:
        discovery_cache["season_team_catalog"] = dedupe_rows(discovery_cache["season_team_catalog"], ("season", "season_type", "team_id"))
        save_frame(job_dir / "derived" / "season_team_catalog", discovery_cache["season_team_catalog"], output_profile)
    if discovery_cache["team_player_catalog"]:
        discovery_cache["team_player_catalog"] = dedupe_rows(discovery_cache["team_player_catalog"], ("season", "season_type", "team_id", "player_id"))
        save_frame(job_dir / "derived" / "team_player_catalog", discovery_cache["team_player_catalog"], output_profile)

    save_json(job_dir / "manifest.json", manifests)
    return manifests, discovery_cache


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_from_cached_games(job_dir: Path, season: str, season_type: str) -> list[dict[str, Any]]:
    catalog_dir = job_dir / "normalized" / "get-games"
    if not catalog_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for csv_path in catalog_dir.glob("*.csv"):
        try:
            frame = pd.read_csv(csv_path)
        except Exception:
            continue
        if "season" not in frame.columns or "season_type" not in frame.columns:
            continue
        match = frame[(frame["season"].astype(str) == str(season)) & (frame["season_type"].astype(str) == str(season_type))]
        for _, row in match.iterrows():
            for side in ("home", "away"):
                team_id = row.get(f"{side}_team_id")
                if pd.isna(team_id):
                    continue
                rows.append(
                    {
                        "season": str(row.get("season")),
                        "season_type": str(row.get("season_type")),
                        "team_id": str(team_id),
                        "team_abbreviation": row.get(f"{side}_team_abbreviation"),
                    }
                )
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = f"{row['season']}::{row['season_type']}::{row['team_id']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def run_totals_job(
    session: requests.Session,
    registry: Mapping[str, Any],
    bundle: Mapping[str, Any],
    job: Mapping[str, Any],
    output_root: Path,
    requested_seasons: list[str],
    requested_season_types: list[str],
    fallback_season_type: str,
    output_profile: list[str],
    _discovery_cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    job_dir = output_root / job["job_id"]
    manifests: list[dict[str, Any]] = []
    league = bundle["league"]
    family = job["family"]

    for variant in job["variants"]:
        endpoint = variant["endpoint"]
        endpoint_meta = registry["families"][family]["endpoints"][endpoint]
        season_types = season_type_plan(endpoint_meta, requested_season_types, fallback_season_type)
        for season in requested_seasons:
            for season_type in season_types:
                request_params = request_common_params(job, variant)
                request_params.update({"Season": season, "SeasonType": season_type})
                record = run_endpoint_request(
                    session=session,
                    base_dir=job_dir,
                    registry=registry,
                    league=league,
                    job=job,
                    variant=variant,
                    context={"source": "totals"},
                    request_params=request_params,
                    season=season,
                    season_type=season_type,
                    output_profile=output_profile,
                )
                manifests.append(record)

    save_json(job_dir / "manifest.json", manifests)
    return manifests


def run_on_off_job(
    session: requests.Session,
    registry: Mapping[str, Any],
    bundle: Mapping[str, Any],
    job: Mapping[str, Any],
    output_root: Path,
    requested_seasons: list[str],
    requested_season_types: list[str],
    fallback_season_type: str,
    output_profile: list[str],
    discovery_cache: dict[str, list[dict[str, Any]]],
    max_player_ids_per_team: int | None,
) -> list[dict[str, Any]]:
    job_dir = output_root / job["job_id"]
    manifests: list[dict[str, Any]] = []
    league = bundle["league"]
    family = job["family"]
    team_catalog = discovery_cache.get("season_team_catalog", [])
    player_catalog = discovery_cache.get("team_player_catalog", [])

    for variant in job["variants"]:
        endpoint = variant["endpoint"]
        endpoint_meta = registry["families"][family]["endpoints"][endpoint]
        season_types = season_type_plan(endpoint_meta, requested_season_types, fallback_season_type)
        stat_type = variant.get("stat_type", "team")
        for season in requested_seasons:
            for season_type in season_types:
                season_team_rows = [row for row in team_catalog if str(row["season"]) == str(season) and str(row["season_type"]) == str(season_type)]
                if not season_team_rows:
                    season_team_rows = discover_from_cached_games(job_dir, season, season_type)
                team_ids = [row["team_id"] for row in season_team_rows]
                if stat_type == "player":
                    season_player_rows = [row for row in player_catalog if str(row["season"]) == str(season) and str(row["season_type"]) == str(season_type)]
                    if max_player_ids_per_team is not None:
                        season_player_rows = season_player_rows[:max_player_ids_per_team]
                    for row in season_player_rows:
                        request_params = request_common_params(job, variant)
                        request_params.update({
                            "Season": season,
                            "SeasonType": season_type,
                            "TeamId": row["team_id"],
                            "PlayerId": row["player_id"],
                        })
                        record = run_endpoint_request(
                            session=session,
                            base_dir=job_dir,
                            registry=registry,
                            league=league,
                            job=job,
                            variant=variant,
                            context={"source": "on_off", "player_id": row["player_id"], "team_id": row["team_id"]},
                            request_params=request_params,
                            season=season,
                            season_type=season_type,
                            output_profile=output_profile,
                        )
                        manifests.append(record)
                else:
                    season_player_rows = [row for row in player_catalog if str(row["season"]) == str(season) and str(row["season_type"]) == str(season_type)]
                    player_rows_by_team: dict[str, list[dict[str, Any]]] = {}
                    for row in season_player_rows:
                        player_rows_by_team.setdefault(str(row["team_id"]), []).append(row)
                    for team_id in team_ids:
                        team_player_rows = player_rows_by_team.get(str(team_id), [])
                        if max_player_ids_per_team is not None:
                            team_player_rows = team_player_rows[:max_player_ids_per_team]
                        for player_row in team_player_rows:
                            request_params = request_common_params(job, variant)
                            request_params.update({
                                "Season": season,
                                "SeasonType": season_type,
                                "TeamId": team_id,
                                "PlayerId": player_row["player_id"],
                            })
                            record = run_endpoint_request(
                                session=session,
                                base_dir=job_dir,
                                registry=registry,
                                league=league,
                                job=job,
                                variant=variant,
                                context={"source": "on_off", "team_id": team_id, "player_id": player_row["player_id"]},
                                request_params=request_params,
                                season=season,
                                season_type=season_type,
                                output_profile=output_profile,
                            )
                            manifests.append(record)

    save_json(job_dir / "manifest.json", manifests)
    return manifests


def run_shot_pace_job(
    session: requests.Session,
    registry: Mapping[str, Any],
    bundle: Mapping[str, Any],
    job: Mapping[str, Any],
    output_root: Path,
    requested_seasons: list[str],
    requested_season_types: list[str],
    fallback_season_type: str,
    output_profile: list[str],
    discovery_cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    job_dir = output_root / job["job_id"]
    manifests: list[dict[str, Any]] = []
    league = bundle["league"]
    family = job["family"]
    team_catalog = discovery_cache.get("season_team_catalog", [])

    for variant in job["variants"]:
        endpoint = variant["endpoint"]
        endpoint_meta = registry["families"][family]["endpoints"][endpoint]
        season_types = season_type_plan(endpoint_meta, requested_season_types, fallback_season_type)
        scope = variant["scope"]

        if scope == "season_type_only":
            for season_type in season_types:
                request_params = request_common_params(job, variant)
                request_params.update({"SeasonType": season_type})
                record = run_endpoint_request(
                    session=session,
                    base_dir=job_dir,
                    registry=registry,
                    league=league,
                    job=job,
                    variant=variant,
                    context={"source": "shot_pace", "scope": scope, "season_type": season_type, "_request_seasons": requested_seasons},
                    request_params=request_params,
                    season=None,
                    season_type=season_type,
                    output_profile=output_profile,
                )
                manifests.append(record)
            continue

        for season in requested_seasons:
            for season_type in season_types:
                if scope == "season":
                    request_params = request_common_params(job, variant)
                    request_params.update({"Season": season, "SeasonType": season_type})
                    record = run_endpoint_request(
                        session=session,
                        base_dir=job_dir,
                        registry=registry,
                        league=league,
                        job=job,
                        variant=variant,
                        context={"source": "shot_pace", "scope": scope, "clutch_window": "4Q/OT | margin -3..3 | 300..120"},
                        request_params=request_params,
                        season=season,
                        season_type=season_type,
                        output_profile=output_profile,
                    )
                    manifests.append(record)
                elif scope == "team":
                    season_team_rows = [row for row in team_catalog if str(row["season"]) == str(season) and str(row["season_type"]) == str(season_type)]
                    if not season_team_rows:
                        season_team_rows = discover_from_cached_games(job_dir, season, season_type)
                    for row in season_team_rows:
                        request_params = request_common_params(job, variant)
                        request_params.update({"Season": season, "SeasonType": season_type})
                        if endpoint == "get-shots":
                            request_params.pop("TeamId", None)
                            request_params.setdefault("EntityType", "Team")
                            request_params.setdefault("EntityId", str(row["team_id"]))
                            request_params.setdefault("StartType", "All")
                            request_params.setdefault("Blocked", False)
                        elif endpoint == "get-possessions":
                            request_params.update(
                                {
                                    "TeamId": str(row["team_id"]),
                                    "OffDef": request_params.get("OffDef", "Offense"),
                                    "FilterComparison": request_params.get("FilterComparison", "Exactly"),
                                    "FilterEvent": request_params.get("FilterEvent", "OnFloor"),
                                    "FilterValue": request_params.get("FilterValue", 5),
                                    "StartType": request_params.get("StartType", "All"),
                                }
                            )
                            request_params.setdefault("TeamId", str(row["team_id"]))
                        record = run_endpoint_request(
                            session=session,
                            base_dir=job_dir,
                            registry=registry,
                            league=league,
                            job=job,
                            variant=variant,
                            context={"source": "shot_pace", "scope": scope, "team_id": row["team_id"], "clutch_window": "4Q/OT | margin -3..3 | 300..120"},
                            request_params=request_params,
                            season=season,
                            season_type=season_type,
                            output_profile=output_profile,
                        )
                        manifests.append(record)

    save_json(job_dir / "manifest.json", manifests)
    return manifests


def run_bundle(
    bundle_path: Path = DEFAULT_BUNDLE_PATH,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
    output_root: Path | None = None,
    preset: str | None = None,
    seasons: list[str] | None = None,
    season_types: list[str] | None = None,
    full: bool = False,
    max_team_ids_per_season: int | None = None,
    max_player_ids_per_team: int | None = None,
) -> dict[str, Any]:
    bundle = read_json(bundle_path)
    registry = read_json(registry_path)
    output_root = output_root or Path(bundle.get("output_root", DEFAULT_OUTPUT_ROOT))
    output_root.mkdir(parents=True, exist_ok=True)

    session = build_session(DEFAULT_TIMEOUT_SECONDS, DEFAULT_RETRIES, DEFAULT_BACKOFF_FACTOR)
    selected_jobs = select_jobs(bundle["jobs"], preset)
    if preset:
        preset_seasons = bundle.get("minimum_seasons", DEFAULT_MINIMUM_SEASONS) if full else DEFAULT_SMOKE_SEASONS
        preset_season_types = bundle.get("season_types", DEFAULT_REQUESTED_SEASON_TYPES) if full else DEFAULT_SMOKE_SEASON_TYPES
        requested_seasons = normalize_seasons(seasons or preset_seasons, [])
        requested_season_types = normalize_requested_season_types(season_types or preset_season_types)
        if not full and max_team_ids_per_season is None and preset in {"on_off", "shot_pace", "roster_value"}:
            max_team_ids_per_season = DEFAULT_SMOKE_TEAM_CAP
        if not full and max_player_ids_per_team is None and preset in {"on_off", "roster_value"}:
            max_player_ids_per_team = DEFAULT_SMOKE_PLAYER_CAP
    else:
        if seasons:
            requested_seasons = normalize_seasons(seasons, [])
        else:
            requested_seasons = normalize_seasons(bundle.get("minimum_seasons", []), registry.get("minimum_seasons", DEFAULT_MINIMUM_SEASONS))
        requested_season_types = normalize_requested_season_types(season_types or bundle.get("season_types", registry.get("requested_season_types", DEFAULT_REQUESTED_SEASON_TYPES)))
    fallback_season_type = registry.get("fallback_season_type", "Regular Season")
    league = bundle.get("league", registry.get("default_league", "wnba"))
    job_manifests: list[dict[str, Any]] = []
    discovery_cache: dict[str, list[dict[str, Any]]] = {"season_team_catalog": [], "team_player_catalog": []}
    summary: dict[str, Any] = {
        "bundle_id": bundle.get("bundle_id", bundle_path.stem),
        "preset": preset,
        "bundle_path": str(bundle_path),
        "registry_path": str(registry_path),
        "output_root": str(output_root),
        "league": league,
        "full": full,
        "requested_seasons": requested_seasons,
        "requested_season_types": requested_season_types,
        "selected_job_families": [job["family"] for job in selected_jobs],
        "jobs": [],
    }

    for job in selected_jobs:
        family = job["family"]
        output_profile = job.get("output_profiles", ["csv", "parquet"])
        if family == "league_discovery":
            manifests, cache = run_league_discovery_job(
                session=session,
                registry=registry,
                bundle=bundle,
                job=job,
                output_root=output_root,
                requested_seasons=requested_seasons,
                requested_season_types=requested_season_types,
                fallback_season_type=fallback_season_type,
                output_profile=output_profile,
                max_team_ids_per_season=max_team_ids_per_season,
                max_player_ids_per_team=max_player_ids_per_team,
            )
            discovery_cache["season_team_catalog"].extend(cache.get("season_team_catalog", []))
            discovery_cache["team_player_catalog"].extend(cache.get("team_player_catalog", []))
        elif family == "totals":
            manifests = run_totals_job(
                session=session,
                registry=registry,
                bundle=bundle,
                job=job,
                output_root=output_root,
                requested_seasons=requested_seasons,
                requested_season_types=requested_season_types,
                fallback_season_type=fallback_season_type,
                output_profile=output_profile,
                _discovery_cache=discovery_cache,
            )
        elif family == "on_off":
            manifests = run_on_off_job(
                session=session,
                registry=registry,
                bundle=bundle,
                job=job,
                output_root=output_root,
                requested_seasons=requested_seasons,
                requested_season_types=requested_season_types,
                fallback_season_type=fallback_season_type,
                output_profile=output_profile,
                discovery_cache=discovery_cache,
                max_player_ids_per_team=max_player_ids_per_team,
            )
        elif family == "shot_pace":
            manifests = run_shot_pace_job(
                session=session,
                registry=registry,
                bundle=bundle,
                job=job,
                output_root=output_root,
                requested_seasons=requested_seasons,
                requested_season_types=requested_season_types,
                fallback_season_type=fallback_season_type,
                output_profile=output_profile,
                discovery_cache=discovery_cache,
            )
        else:
            raise ValueError(f"Unsupported job family: {family}")

        job_summary = {
            "job_id": job["job_id"],
            "family": family,
            "records": len(manifests),
            "job_dir": str(output_root / job["job_id"]),
            "had_failures": any(not record.get("ok", True) for record in manifests),
        }
        if full and family == "on_off" and len(manifests) < 100:
            raise RuntimeError(
                f"Full on_off run produced only {len(manifests)} request records. "
                "This is too small to count as a valid 2023-2025 rebuild."
            )
        summary["jobs"].append(job_summary)
        job_manifests.extend(manifests)

    summary["records"] = len(job_manifests)
    write_json(output_root / "bundle_manifest.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pbpstats bundle spec.")
    parser.add_argument("--bundle-spec", type=Path, default=DEFAULT_BUNDLE_PATH, help="Bundle JSON file describing the jobs to run.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH, help="Endpoint registry JSON file.")
    parser.add_argument("--output-root", type=Path, default=None, help="Override the bundle output root.")
    parser.add_argument("--preset", choices=sorted(PRESET_FAMILIES.keys()), default=None, help="Optional preset that selects a job family bundle.")
    parser.add_argument("--full", action="store_true", help="Run the full requested season universe instead of smoke caps.")
    parser.add_argument("--season", dest="seasons", action="append", help="Season to include. May be repeated.")
    parser.add_argument("--season-start", type=int, help="Inclusive start year for a season range.")
    parser.add_argument("--season-end", type=int, help="Inclusive end year for a season range.")
    parser.add_argument("--season-type", dest="season_types", action="append", help='Season type to include. May be repeated.')
    parser.add_argument("--max-team-ids-per-season", type=int, default=None, help="Cap discovered team ids per season for smoke tests.")
    parser.add_argument("--max-player-ids-per-team", type=int, default=None, help="Cap discovered player ids per team for smoke tests.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.seasons and (args.season_start is not None or args.season_end is not None):
        raise SystemExit("Provide either repeated --season values or a --season-start/--season-end range, not both.")
    seasons: list[str] | None = None
    if args.seasons:
        seasons = [str(season) for season in args.seasons]
    elif args.season_start is not None or args.season_end is not None:
        if args.season_start is None or args.season_end is None:
            raise SystemExit("Provide both --season-start and --season-end, or neither.")
        seasons = [str(year) for year in range(args.season_start, args.season_end + 1)]

    started = time.perf_counter()
    summary = run_bundle(
        bundle_path=args.bundle_spec,
        registry_path=args.registry,
        output_root=args.output_root,
        preset=args.preset,
        seasons=seasons,
        season_types=args.season_types,
        full=args.full,
        max_team_ids_per_season=args.max_team_ids_per_season,
        max_player_ids_per_team=args.max_player_ids_per_team,
    )
    summary["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    write_json(Path(summary["output_root"]) / "bundle_summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
