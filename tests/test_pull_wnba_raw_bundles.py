import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pull_wnba_raw_bundles as raw_bundles


class PullWnbaRawBundlesTest(unittest.TestCase):
    def test_filter_to_season_keeps_requested_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"season": 2025, "game_id": "1"},
                {"season": 2026, "game_id": "2"},
            ]
        )

        filtered = raw_bundles.filter_to_season(frame, season="2026")

        self.assertEqual(filtered["game_id"].tolist(), ["2"])

    def test_ingest_wehoop_pbp_writes_manifest_and_normalized_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir)
            config = {"wehoop_sources": {"play_by_play": {"release_tag": "espn_wnba_pbp"}}}
            frame = pd.DataFrame(
                [
                    {"season": 2026, "game_id": "g1", "event_id": 1},
                    {"season": 2025, "game_id": "g0", "event_id": 2},
                ]
            )

            with mock.patch.object(raw_bundles.current_season, "fetch_release_metadata", return_value={"assets": []}), mock.patch.object(
                raw_bundles.current_season,
                "pick_release_asset",
                return_value={"name": "pbp.parquet", "browser_download_url": "https://example.com/pbp.parquet"},
            ), mock.patch.object(
                raw_bundles.current_season,
                "download_release_asset",
                return_value=output_root / "play_by_play" / "raw" / "pbp.parquet",
            ), mock.patch.object(
                raw_bundles.current_season,
                "load_release_frame",
                return_value=frame,
            ):
                summary = raw_bundles.ingest_wehoop_pbp(config=config, season="2026", output_root=output_root)

            manifest = json.loads((output_root / "play_by_play" / "manifest.json").read_text(encoding="utf-8"))
            normalized = pd.read_csv(output_root / "play_by_play" / "normalized" / "play_by_play.csv")

            self.assertEqual(manifest["tag"], "espn_wnba_pbp")
            self.assertEqual(summary["rows"], 1)
            self.assertEqual(normalized["game_id"].tolist(), ["g1"])

    def test_run_raw_bundle_pull_returns_both_source_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_path = temp_root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "paths": {
                            "wnba_stats_raw_root": "data/raw/wnba_stats/current_season_2026",
                            "wehoop_raw_root": "data/raw/wehoop/current_season_2026",
                            "summary_root": "data/raw/current_season_2026",
                        },
                        "wehoop_sources": {"play_by_play": {"release_tag": "espn_wnba_pbp"}},
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(raw_bundles.wnba_stats, "run_wnba_stats_pull", return_value={"player_boxscores": {}}) as mock_stats, mock.patch.object(
                raw_bundles,
                "ingest_wehoop_pbp",
                return_value={"rows": 123},
            ) as mock_pbp:
                summary = raw_bundles.run_raw_bundle_pull(config_path=config_path, season="2026")

            self.assertIn("wnba_stats", summary)
            self.assertIn("wehoop_play_by_play", summary)
            mock_stats.assert_called_once()
            mock_pbp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
