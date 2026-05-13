import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_doc2_roster_tables as roster_tables


class NatashaCloudContractSyncTest(unittest.TestCase):
    def test_signing_transaction_updates_team_and_salary_reference(self) -> None:
        contracts = pd.DataFrame(
            [
                {
                    "player_id": "204333",
                    "player_id_source": "team_roster_history",
                    "player_name": "Natasha Cloud",
                    "player_name_key": "natashacloud",
                    "team_id": "1611661313",
                    "team_id_source": "pbpstats_catalog",
                    "team_abbreviation": "NYL",
                    "team_name": "New York Liberty",
                    "season": 2026,
                    "salary": pd.NA,
                    "cap_hit": pd.NA,
                    "salary_as_pct_cap": pd.NA,
                    "pct_team": pd.NA,
                    "salary_tier": pd.NA,
                    "status": "UFA",
                    "status_full": "UFA",
                    "next_status": "UFA",
                    "row_section": "current_roster",
                    "counts_toward_salary_total": False,
                    "counts_toward_player_total": False,
                    "notes": pd.NA,
                }
            ]
        )
        transactions = pd.DataFrame(
            [
                {
                    "season": 2026,
                    "transaction_date": "2026-05-04",
                    "player_primary": "Natasha Cloud",
                    "transaction_type": "signing",
                    "raw_text": "The Chicago Sky signed Natasha Cloud.",
                    "to_team": "Chicago Sky",
                    "from_team": pd.NA,
                    "team_primary": "Chicago Sky",
                }
            ]
        )
        salary_history = pd.DataFrame(
            [
                {
                    "season": 2025,
                    "player_name": "Natasha Cloud",
                    "season_plusone_salary_usd": 555000.0,
                    "season_plusone_signing": "UFA",
                }
            ]
        )
        team_caps = pd.DataFrame(
            [
                {
                    "team_name": "Chicago Sky",
                    "team_total_salary": 6585832.0,
                    "team_salary_cap": 7000000.0,
                }
            ]
        )

        updated = roster_tables.reconcile_contract_context_from_transactions(
            contracts=contracts,
            transactions=transactions,
            salary_history=salary_history,
            team_caps=team_caps,
        )

        row = updated.iloc[0]
        self.assertEqual(row["team_name"], "Chicago Sky")
        self.assertEqual(row["team_abbreviation"], "CHI")
        self.assertEqual(str(row["team_id"]), "1611661329")
        self.assertEqual(row["salary"], 555000.0)
        self.assertEqual(row["cap_hit"], 555000.0)
        self.assertEqual(row["salary_tier"], "Mid-Tier Rotation")
        self.assertAlmostEqual(float(row["salary_as_pct_cap"]), 555000.0 / 7000000.0, places=6)
        self.assertAlmostEqual(float(row["pct_team"]), 555000.0 / 6585832.0, places=6)
        self.assertEqual(row["status"], "Signed")
        self.assertEqual(row["status_full"], "Signed")
        self.assertTrue(bool(row["counts_toward_salary_total"]))
        self.assertTrue(bool(row["counts_toward_player_total"]))
        self.assertIn("Chicago Sky signed Natasha Cloud", str(row["notes"]))


if __name__ == "__main__":
    unittest.main()
