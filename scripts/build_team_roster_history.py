#!/usr/bin/env python3
"""Fetch and save WNBA team roster history for 2023-2025 regular seasons.

This script saves a durable player-level roster table so we can reuse the
roster data without re-running ad hoc live calls.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


LEAGUE = "wnba"
SEASONS = [2023, 2024, 2025]
SEASON_TYPE = "Regular Season"

OUTPUT_ROOT = Path("data/doc2_roster_value/tables/team_roster_history")
PROVENANCE_ROOT = Path("data/pbpstats_jobs/wnba_team_roster_history")

TEAMS_URL = f"https://api.pbpstats.com/get-teams/{LEAGUE}"
TEAM_PLAYERS_URL = "https://api.pbpstats.com/get-team-players-for-season"

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

ABBR_TO_NAME = {abbr: name for name, abbr in TEAM_NAME_TO_ABBR.items()}


def build_session(timeout_retries: int = 5, backoff_factor: float = 0.6) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=timeout_retries,
        connect=timeout_retries,
        read=timeout_retries,
        status=timeout_retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session


def fetch_json(session: requests.Session, url: str, params: dict[str, Any] | None = None) -> tuple[Any, int, str]:
    response = session.get(url, params=params, timeout=90)
    status = response.status_code
    response.raise_for_status()
    return response.json(), status, response.url


def read_teams(session: requests.Session) -> list[dict[str, str]]:
    payload, _, _ = fetch_json(session, TEAMS_URL)
    teams = payload.get("teams", [])
    rows: list[dict[str, str]] = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = team.get("id")
        team_abbreviation = team.get("text")
        if not team_id or not team_abbreviation:
            continue
        rows.append(
            {
                "team_id": str(team_id),
                "team_abbreviation": str(team_abbreviation),
                "team_name": ABBR_TO_NAME.get(str(team_abbreviation), str(team_abbreviation)),
            }
        )
    return rows


def extract_player_map(payload: Any) -> list[tuple[int, str]]:
    players = []
    if not isinstance(payload, dict):
        return players
    raw_players = payload.get("players")
    if isinstance(raw_players, dict):
        for idx, (player_id, player_name) in enumerate(raw_players.items()):
            try:
                pid = int(player_id)
            except (TypeError, ValueError):
                continue
            players.append((pid, str(player_name)))
        return players
    if isinstance(raw_players, list):
        for idx, item in enumerate(raw_players):
            if isinstance(item, dict):
                player_id = item.get("player_id") or item.get("id")
                player_name = item.get("player_name") or item.get("name") or item.get("text")
                if player_id and player_name:
                    players.append((int(player_id), str(player_name)))
        return players
    return players


def ensure_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    PROVENANCE_ROOT.mkdir(parents=True, exist_ok=True)
    (PROVENANCE_ROOT / "raw" / "get-team-players-for-season").mkdir(parents=True, exist_ok=True)


def save_frame(frame: pd.DataFrame, stem: Path) -> list[str]:
    files: list[str] = []
    csv_path = stem.with_suffix(".csv")
    frame.to_csv(csv_path, index=False)
    files.append(str(csv_path))
    try:
        parquet_path = stem.with_suffix(".parquet")
        frame.to_parquet(parquet_path, index=False)
        files.append(str(parquet_path))
    except Exception:
        # parquet is a convenience artifact; the CSV is the canonical save
        pass
    return files


def roster_request_stem(season: int, team_id: str) -> str:
    return f"team_players__season-{season}__season_type-{SEASON_TYPE.replace(' ', '_')}__team_id-{team_id}"


def fetch_roster_rows(
    session: requests.Session,
    team_rows: list[dict[str, str]],
    season: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team in team_rows:
        params = {"Season": season, "SeasonType": SEASON_TYPE, "TeamId": team["team_id"]}
        request_url = TEAM_PLAYERS_URL
        status = None
        payload: Any = None
        response_url = None
        last_error: str | None = None
        for attempt in range(1, 6):
            try:
                payload, status, response_url = fetch_json(session, request_url, params=params)
                break
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt == 5:
                    payload = None
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    response_url = str(request_url)
                    break
                time.sleep(attempt * 2)

        raw_stem = roster_request_stem(season, team["team_id"])
        raw_path = PROVENANCE_ROOT / "raw" / "get-team-players-for-season" / f"{raw_stem}.json"

        record = {
            "league": LEAGUE,
            "season": season,
            "season_type": SEASON_TYPE,
            "team_id": team["team_id"],
            "team_abbreviation": team["team_abbreviation"],
            "team_name": team["team_name"],
            "request_url": response_url or request_url,
            "request_status": status,
            "request_params": params,
            "raw_path": str(raw_path),
            "ok": payload is not None and status == 200,
            "player_count": 0,
        }

        if payload is None:
            raw_path.write_text(
                json.dumps(
                    {
                        "error": last_error,
                        "request_params": params,
                        "request_url": response_url or request_url,
                        "request_status": status,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            continue

        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        player_rows = extract_player_map(payload)
        record["player_count"] = len(player_rows)
        rows.append(record)
        for player_index, (player_id, player_name) in enumerate(player_rows):
            rows.append(
                {
                    "league": LEAGUE,
                    "season": season,
                    "season_type": SEASON_TYPE,
                    "team_id": team["team_id"],
                    "team_abbreviation": team["team_abbreviation"],
                    "team_name": team["team_name"],
                    "player_id": player_id,
                    "player_name": player_name,
                    "player_order": player_index,
                    "request_url": response_url or request_url,
                    "request_status": status,
                    "request_params": params,
                    "raw_path": str(raw_path),
                }
            )

    return rows


def main() -> None:
    ensure_dirs()
    session = build_session()
    team_rows = read_teams(session)

    roster_rows: list[dict[str, Any]] = []
    request_manifest: list[dict[str, Any]] = []

    for season in SEASONS:
        season_rows = fetch_roster_rows(session, team_rows, season)
        roster_rows.extend([row for row in season_rows if "player_name" in row])
        request_manifest.extend([row for row in season_rows if "player_count" in row])

    roster_df = pd.DataFrame(roster_rows)
    if roster_df.empty:
        raise SystemExit("No roster rows were collected.")

    roster_df = roster_df.sort_values(["season", "team_abbreviation", "player_name"]).reset_index(drop=True)
    roster_df["season"] = roster_df["season"].astype(int)
    roster_df["player_id"] = pd.to_numeric(roster_df["player_id"], errors="coerce").astype("Int64")

    roster_stem = OUTPUT_ROOT / "team_roster_history"
    roster_files = save_frame(roster_df, roster_stem)

    summary_df = (
        roster_df.groupby(["season", "season_type", "team_id", "team_abbreviation", "team_name"], as_index=False)
        .agg(player_count=("player_name", "count"))
        .sort_values(["season", "team_abbreviation"])
        .reset_index(drop=True)
    )
    summary_files = save_frame(summary_df, OUTPUT_ROOT / "team_roster_history_summary")

    manifest = {
        "bundle_id": "team_roster_history_2023_2025",
        "league": LEAGUE,
        "seasons": SEASONS,
        "season_type": SEASON_TYPE,
        "output_root": str(OUTPUT_ROOT),
        "source_root": str(PROVENANCE_ROOT),
        "roster_files": roster_files,
        "summary_files": summary_files,
        "team_count": len(team_rows),
        "row_count": len(roster_df),
        "summary_row_count": len(summary_df),
        "request_manifest": request_manifest,
    }
    (OUTPUT_ROOT / "team_roster_history_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (PROVENANCE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
