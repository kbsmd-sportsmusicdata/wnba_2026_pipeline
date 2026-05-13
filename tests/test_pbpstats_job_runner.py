import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pbpstats_job_runner as runner


class PbpstatsJobRunnerTest(unittest.TestCase):
    def test_explicit_seasons_do_not_expand_with_registry_minimums(self) -> None:
        bundle_payload = {
            "bundle_id": "test_bundle",
            "league": "wnba",
            "minimum_seasons": [2026],
            "season_types": ["Regular Season"],
            "jobs": [],
        }
        registry_payload = {
            "default_league": "wnba",
            "minimum_seasons": [2025, 2024, 2023],
            "requested_season_types": ["Regular Season", "Playoffs"],
            "fallback_season_type": "Regular Season",
            "families": {},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bundle_path = tmpdir_path / "bundle.json"
            registry_path = tmpdir_path / "registry.json"
            output_root = tmpdir_path / "output"
            runner.write_json(bundle_path, bundle_payload)
            runner.write_json(registry_path, registry_payload)

            with mock.patch.object(runner, "build_session"):
                summary = runner.run_bundle(
                    bundle_path=bundle_path,
                    registry_path=registry_path,
                    output_root=output_root,
                    seasons=["2026"],
                )

        self.assertEqual(summary["requested_seasons"], ["2026"])


if __name__ == "__main__":
    unittest.main()
