import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_team_roster_grade_notebook as notebook


class TeamRosterGradeNotebookTest(unittest.TestCase):
    def test_bundle_reconciles_visual_datasets(self) -> None:
        bundle = notebook.build_bundle()
        team_df = bundle["team_level"]
        tier_df = bundle["tier_stacked"]
        hidden_df = bundle["hidden_value"]
        scatter_df = bundle["scatter"]
        comparison_meta = bundle["comparison_meta"]

        self.assertEqual(len(team_df), 15)

        ordered_names = team_df["team_name"].tolist()
        self.assertEqual(hidden_df["team_name"].tolist(), ordered_names)
        self.assertEqual(scatter_df["team_name"].tolist(), ordered_names)

        tier_totals = tier_df.groupby("team_name")["player_count"].sum()
        roster_sizes = team_df.set_index("team_name")["roster_size"]
        for team_name, roster_size in roster_sizes.items():
            self.assertEqual(int(tier_totals.loc[team_name]), int(roster_size))

        hidden_counts = hidden_df.set_index("team_name")["hidden_value_count"]
        aggregated_hidden = (
            bundle["players"]
            .groupby("team_name")["hidden_value_flag"]
            .sum()
            .astype(int)
        )
        for team_name, hidden_count in hidden_counts.items():
            self.assertEqual(int(hidden_count), int(aggregated_hidden.loc[team_name]))

        self.assertIn("material_match", comparison_meta)
        self.assertIn("tableau_reference_available", comparison_meta)


if __name__ == "__main__":
    unittest.main()
