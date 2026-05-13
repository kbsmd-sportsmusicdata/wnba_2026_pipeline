import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import process_current_season_pipeline as processing


class CurrentSeasonProcessingTest(unittest.TestCase):
    def test_position_percentiles_fall_back_to_league_wide_for_missing_position(self) -> None:
        frame = pd.DataFrame(
            [
                {"player_id": "1", "player_name": "Guard A", "position_group": "Guard", "points_per_game": 20.0},
                {"player_id": "2", "player_name": "Guard B", "position_group": "Guard", "points_per_game": 10.0},
                {"player_id": "3", "player_name": "Unknown C", "position_group": None, "points_per_game": 15.0},
            ]
        )

        percentiles = processing.add_position_percentiles(
            frame=frame,
            metric_columns=("points_per_game",),
        )

        fallback_row = percentiles.loc[percentiles["player_id"] == "3"].iloc[0]
        self.assertTrue(bool(fallback_row["position_percentile_fallback_flag"]))
        self.assertGreaterEqual(fallback_row["points_per_game_pctile_pos"], 0.0)
        self.assertLessEqual(fallback_row["points_per_game_pctile_pos"], 100.0)

    def test_post_game_summary_builds_one_row_per_team_game(self) -> None:
        team_logs = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "team_id": "t1", "team_name": "Team 1", "points": 80},
                {"season": 2026, "game_id": "g1", "team_id": "t2", "team_name": "Team 2", "points": 75},
            ]
        )
        player_logs = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "team_id": "t1", "player_id": "p1", "player_name": "Player 1", "points": 22},
                {"season": 2026, "game_id": "g1", "team_id": "t1", "player_id": "p2", "player_name": "Player 2", "points": 18},
                {"season": 2026, "game_id": "g1", "team_id": "t2", "player_id": "p3", "player_name": "Player 3", "points": 19},
            ]
        )
        schedule = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "game_date": "2026-05-11", "season_type": "Regular Season"}
            ]
        )

        summary = processing.build_post_game_summary(
            team_game_logs=team_logs,
            player_game_logs=player_logs,
            schedule_master=schedule,
        )

        self.assertEqual(len(summary), 2)
        self.assertEqual(summary["top_scorer_name"].tolist(), ["Player 1", "Player 3"])
        self.assertEqual(summary["team_points"].tolist(), [80, 75])

    def test_bi_exports_have_unique_player_rows(self) -> None:
        player_summary = pd.DataFrame(
            [
                {"season": 2026, "player_id": "1", "player_name": "A", "team_id": "t1", "value_score": 55.0},
                {"season": 2026, "player_id": "2", "player_name": "B", "team_id": "t1", "value_score": 48.0},
            ]
        )
        team_grades = pd.DataFrame(
            [
                {"season": 2026, "team_id": "t1", "team_name": "Team 1", "roster_grade": "B"}
            ]
        )
        player_logs = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "player_id": "1", "team_id": "t1", "points": 20}
            ]
        )
        team_logs = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "team_id": "t1", "points": 80}
            ]
        )
        post_game = pd.DataFrame(
            [
                {"season": 2026, "game_id": "g1", "team_id": "t1", "team_points": 80}
            ]
        )
        shot_profile = pd.DataFrame(
            [
                {"season": 2026, "team_id": "t1", "player_id": "1", "at_rim_frequency": 0.3}
            ]
        )

        exports = processing.build_bi_exports(
            player_summary=player_summary,
            team_roster_grades=team_grades,
            player_game_logs=player_logs,
            team_game_logs=team_logs,
            post_game_summary=post_game,
            shot_profile_summary=shot_profile,
        )

        self.assertEqual(len(exports["player_value_summary"]), 2)
        self.assertEqual(
            len(exports["player_value_summary"][["season", "player_id"]].drop_duplicates()),
            2,
        )
        self.assertIn("shot_profile_summary", exports)


if __name__ == "__main__":
    unittest.main()
