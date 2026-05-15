#!/usr/bin/env python3
"""WNBA.com stats client for game-level player/team boxscore pulls.

This client targets the public WNBA stats endpoints that mirror the NBA stats
request structure. It is intended as the primary source for:

- player boxscores: traditional, advanced, scoring
- team boxscores: traditional, advanced, misc

Play-by-play can remain on a separate fallback path for now.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "raw" / "wnba_stats" / "current_season_2026"
API_BASE = "https://stats.wnba.com/stats"
WNBA_LEAGUE_ID = "10"
DEFAULT_SEASON = "2026"
DEFAULT_SEASON_TYPE = "Regular Season"
DEFAULT_PER_MODE = "Totals"

PLAYER_BOX_ENDPOINT = "playergamelogs"
TEAM_BOX_ENDPOINT = "teamgamelogs"
PLAYER_MEASURES = (
    ("traditional", "Base"),
    ("advanced", "Advanced"),
    ("scoring", "Scoring"),
)
TEAM_MEASURES = (
    ("traditional", "Base"),
    ("advanced", "Advanced"),
    ("misc", "Misc"),
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Origin": "https://stats.wnba.com",
    "Pragma": "no-cache",
    "Referer": "https://stats.wnba.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def stats_get(session: requests.Session, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint}"
    response = session.get(url, params=params, timeout=60)
    response.raise_for_status()
    return response.json()


def normalize_result_sets(payload: dict[str, Any]) -> dict[str, pd.DataFrame]:
    datasets = payload.get("datasets")
    if isinstance(datasets, dict) and datasets:
        normalized: dict[str, pd.DataFrame] = {}
        for name, dataset in datasets.items():
            rows = dataset.get("rows", []) if isinstance(dataset, dict) else []
            normalized[name] = pd.DataFrame(rows)
        return normalized

    result_sets = payload.get("resultSets")
    if result_sets is None and payload.get("resultSet") is not None:
        result_sets = [payload["resultSet"]]
    if result_sets is None:
        raise ValueError("No datasets, resultSets, or resultSet found in WNBA stats response payload.")

    normalized: dict[str, pd.DataFrame] = {}
    for result in result_sets:
        name = result.get("name") or result.get("nameSet") or "results"
        headers = result.get("headers", [])
        rows = result.get("rowSet", [])
        normalized[name] = pd.DataFrame(rows, columns=headers)
    return normalized


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_frame(path: Path, frame: pd.DataFrame) -> list[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    csv_path = path.with_suffix(".csv")
    frame.to_csv(csv_path, index=False)
    written = [str(csv_path)]
    try:
        parquet_path = path.with_suffix(".parquet")
        frame.to_parquet(parquet_path, index=False)
        written.append(str(parquet_path))
    except Exception as e:
        print(f"[wnba-stats] warning: could not write parquet file: {e}", flush=True)
    return written


def common_boxscore_params(season: str, season_type: str, measure_type: str) -> dict[str, Any]:
    return {
        "DateFrom": "",
        "DateTo": "",
        "GameSegment": "",
        "LastNGames": "0",
        "LeagueID": WNBA_LEAGUE_ID,
        "Location": "",
        "MeasureType": measure_type,
        "Month": "0",
        "OpponentTeamID": "0",
        "Outcome": "",
        "PORound": "0",
        "PerMode": DEFAULT_PER_MODE,
        "Period": "0",
        "Season": str(season),
        "SeasonSegment": "",
        "SeasonType": season_type,
        "ShotClockRange": "",
        "VsConference": "",
        "VsDivision": "",
    }


def build_player_boxscore_params(season: str, season_type: str, measure_type: str) -> dict[str, Any]:
    params = common_boxscore_params(season=season, season_type=season_type, measure_type=measure_type)
    params["PlayerID"] = "0"
    params["TeamID"] = "0"
    return params


def build_team_boxscore_params(season: str, season_type: str, measure_type: str) -> dict[str, Any]:
    params = common_boxscore_params(season=season, season_type=season_type, measure_type=measure_type)
    params["PlayerID"] = "0"
    params["TeamID"] = "0"
    return params


def fetch_boxscore_family(
    session: requests.Session,
    endpoint: str,
    measures: tuple[tuple[str, str], ...],
    family: str,
    season: str,
    season_type: str,
    output_root: Path,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"family": family, "season": season, "season_type": season_type, "measures": {}}
    for measure_slug, measure_type in measures:
        print(
            f"[wnba-stats] requesting family={family} bundle={measure_slug} measure_type={measure_type} season={season}",
            flush=True,
        )
        params = (
            build_player_boxscore_params(season=season, season_type=season_type, measure_type=measure_type)
            if endpoint == PLAYER_BOX_ENDPOINT
            else build_team_boxscore_params(season=season, season_type=season_type, measure_type=measure_type)
        )
        payload = stats_get(session=session, endpoint=endpoint, params=params)
        raw_path = output_root / family / "raw" / measure_slug
        write_json(raw_path.with_suffix(".json"), payload)
        result_sets = normalize_result_sets(payload)
        files: list[str] = []
        for table_name, frame in result_sets.items():
            files.extend(write_frame(output_root / family / "normalized" / f"{measure_slug}__{table_name}", frame))
        summary["measures"][measure_slug] = {
            "endpoint": endpoint,
            "measure_type": measure_type,
            "rows": {table_name: len(frame) for table_name, frame in result_sets.items()},
            "files": files,
        }
        print(
            f"[wnba-stats] complete family={family} bundle={measure_slug} tables={list(result_sets.keys())}",
            flush=True,
        )
    return summary


def run_wnba_stats_pull(
    season: str = DEFAULT_SEASON,
    season_type: str = DEFAULT_SEASON_TYPE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    session = build_session()
    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        "season": season,
        "season_type": season_type,
        "player_boxscores": fetch_boxscore_family(
            session=session,
            endpoint=PLAYER_BOX_ENDPOINT,
            measures=PLAYER_MEASURES,
            family="player_boxscores",
            season=season,
            season_type=season_type,
            output_root=output_root,
        ),
        "team_boxscores": fetch_boxscore_family(
            session=session,
            endpoint=TEAM_BOX_ENDPOINT,
            measures=TEAM_MEASURES,
            family="team_boxscores",
            season=season,
            season_type=season_type,
            output_root=output_root,
        ),
    }
    write_json(output_root / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull WNBA.com stats boxscore datasets.")
    parser.add_argument("--season", default=DEFAULT_SEASON, help="Season to pull, e.g. 2026.")
    parser.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, help="Season type, e.g. Regular Season.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Output root for raw and normalized files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_wnba_stats_pull(
        season=str(args.season),
        season_type=str(args.season_type),
        output_root=args.output_root,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
