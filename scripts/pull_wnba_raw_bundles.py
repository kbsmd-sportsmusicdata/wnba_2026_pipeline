#!/usr/bin/env python3
"""Pull WNBA raw box score bundles plus wehoop play-by-play fallback."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import current_season_pipeline as current_season
import wnba_stats_client as wnba_stats


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "current_season" / "wnba_raw_sources_2026.json"
DEFAULT_WNBA_RAW_ROOT = ROOT / "data" / "raw" / "wnba_stats" / "current_season_2026"
DEFAULT_WEHOOP_RAW_ROOT = ROOT / "data" / "raw" / "wehoop" / "current_season_2026"
DEFAULT_SUMMARY_ROOT = ROOT / "data" / "raw" / "current_season_2026"


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def filter_to_season(frame: pd.DataFrame, season: str) -> pd.DataFrame:
    if "season" not in frame.columns:
        return frame.copy()
    return frame[frame["season"].astype(str) == str(season)].copy()


def ingest_wehoop_pbp(config: dict[str, Any], season: str, output_root: Path) -> dict[str, Any]:
    source_config = config["wehoop_sources"]["play_by_play"]
    tag = source_config["release_tag"]
    print(f"[raw-bundles] starting wehoop play_by_play tag={tag} season={season}", flush=True)
    release_payload = current_season.fetch_release_metadata(tag)
    asset = current_season.pick_release_asset(release_payload, season=season)
    asset_path = current_season.download_release_asset(asset, output_root / "play_by_play" / "raw")
    manifest_path = output_root / "play_by_play" / "manifest.json"
    current_season.write_json(
        manifest_path,
        {
            "tag": tag,
            "asset_name": asset["name"],
            "asset_url": asset["browser_download_url"],
        },
    )
    frame = current_season.load_release_frame(asset_path)
    frame = filter_to_season(frame, season=season)
    files = current_season.write_table(output_root / "play_by_play" / "normalized" / "play_by_play", frame)
    print(f"[raw-bundles] complete wehoop play_by_play rows={len(frame)}", flush=True)
    return {
        "tag": tag,
        "rows": int(len(frame)),
        "raw_asset": str(asset_path),
        "files": files,
    }


def run_raw_bundle_pull(
    config_path: Path = DEFAULT_CONFIG_PATH,
    season: str = "2026",
    wnba_output_root: Path = DEFAULT_WNBA_RAW_ROOT,
    wehoop_output_root: Path = DEFAULT_WEHOOP_RAW_ROOT,
    summary_root: Path = DEFAULT_SUMMARY_ROOT,
) -> dict[str, Any]:
    config = read_json(config_path)
    wnba_root = ROOT / config["paths"]["wnba_stats_raw_root"] if "wnba_stats_raw_root" in config["paths"] else wnba_output_root
    wehoop_root = ROOT / config["paths"]["wehoop_raw_root"] if "wehoop_raw_root" in config["paths"] else wehoop_output_root
    combined_summary_root = ROOT / config["paths"]["summary_root"] if "summary_root" in config["paths"] else summary_root

    print(f"[raw-bundles] starting WNBA stats box score pull season={season}", flush=True)
    wnba_summary = wnba_stats.run_wnba_stats_pull(
        season=str(season),
        season_type="Regular Season",
        output_root=wnba_root,
    )
    print(f"[raw-bundles] starting fallback PBP pull season={season}", flush=True)
    pbp_summary = ingest_wehoop_pbp(config=config, season=str(season), output_root=wehoop_root)

    summary = {
        "season": str(season),
        "wnba_stats": wnba_summary,
        "wehoop_play_by_play": pbp_summary,
    }
    current_season.write_json(combined_summary_root / "raw_bundle_summary.json", summary)
    print("[raw-bundles] summary written", flush=True)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pull WNBA raw box score bundles and wehoop play-by-play.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Raw bundle config JSON.")
    parser.add_argument("--season", default="2026", help="Season to pull.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_raw_bundle_pull(config_path=args.config, season=str(args.season))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
