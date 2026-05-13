#!/usr/bin/env python3
"""Fix transaction IDs and build salary-ready review sidecars."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from build_doc2_roster_tables import normalize_name, resolve_player_id, slugify, write_table


TRANSACTIONS_MASTER_PATH = Path("data/basketball_reference_transactions/wnba_transactions_master_current_extract.csv")
TRANSACTIONS_TABLE_PATH = Path("data/doc2_roster_value/tables/transactions_2026/transactions_2026.csv")
TRANSACTIONS_TABLE_BASE = Path("data/doc2_roster_value/tables/transactions_2026/transactions_2026")
TRANSACTIONS_AUDIT_PATH = Path("data/doc2_roster_value/tables/transactions_2026/transactions_2026_player_id_audit.csv")

CONTRACTS_PATH = Path("data/doc2_roster_value/tables/contracts_2026/contracts_2026.csv")
TEAM_ROSTERS_PATH = Path("data/doc2_roster_value/tables/team_rosters/team_rosters.csv")
PLAYERS_MASTER_PATH = Path("data/doc2_roster_value/tables/players_master/players_master.csv")
MASTER_BIOS_PATH = Path("data/doc2_roster_value/tables/master_player_bios/master_player_bios_2026.csv")
EXPANSION_DRAFT_PATH = Path("data/doc2_roster_value/tables/expansion_draft_2026/expansion_draft_2026.csv")

CONTRACTS_SALARY_READY_BASE = Path("data/doc2_roster_value/tables/contracts_2026/contracts_2026_salary_ready")
TEAM_ROSTERS_SALARY_READY_BASE = Path("data/doc2_roster_value/tables/team_rosters/team_rosters_salary_ready")
PLAYERS_MASTER_SALARY_READY_BASE = Path("data/doc2_roster_value/tables/players_master/players_master_salary_ready")

SALARY_AUDIT_DIR = Path("data/doc2_roster_value/tables/salary_ready_audit")
SALARY_SYNC_AUDIT_PATH = SALARY_AUDIT_DIR / "salary_ready_sync_audit.csv"
SUMMARY_PATH = SALARY_AUDIT_DIR / "salary_ready_review_summary.json"


def build_identity_lookup() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    contracts = pd.read_csv(CONTRACTS_PATH)
    frames.append(
        contracts[["player_name", "player_id"]]
        .assign(team_name=contracts["team_name"], player_id_source=contracts["player_id_source"], identity_source="contracts_2026", priority=0)
    )

    team_rosters = pd.read_csv(TEAM_ROSTERS_PATH)
    frames.append(
        team_rosters[["player_name", "player_id"]]
        .assign(team_name=team_rosters["team_name"], player_id_source=team_rosters["player_id_source"], identity_source="team_rosters", priority=1)
    )

    players_master = pd.read_csv(PLAYERS_MASTER_PATH)
    frames.append(
        players_master[["player_name", "player_id"]]
        .assign(team_name=players_master["team_name"], player_id_source=players_master["player_id_source"], identity_source="players_master", priority=2)
    )

    master_bios = pd.read_csv(MASTER_BIOS_PATH)
    frames.append(
        master_bios[["player_name", "player_id"]]
        .assign(team_name=master_bios["team_2026"], player_id_source=master_bios["player_id_source"], identity_source="master_player_bios", priority=3)
    )

    expansion_draft = pd.read_csv(EXPANSION_DRAFT_PATH)
    if {"player_name", "player_id"}.issubset(expansion_draft.columns):
        frames.append(
            expansion_draft[["player_name", "player_id"]]
            .assign(
                team_name=expansion_draft.get("current_team"),
                player_id_source="expansion_draft_2026",
                identity_source="expansion_draft_2026",
                priority=4,
            )
        )

    lookup = pd.concat(frames, ignore_index=True)
    lookup = lookup.dropna(subset=["player_name", "player_id"]).copy()
    lookup["player_name_key"] = lookup["player_name"].map(normalize_name)
    lookup["player_id"] = lookup["player_id"].astype(str)
    lookup = lookup.sort_values(["player_name_key", "priority", "identity_source", "team_name", "player_id"])
    lookup = lookup.drop_duplicates(subset=["player_name_key", "player_id", "team_name"], keep="first")
    return lookup.reset_index(drop=True)


def choose_team_suffix(row: pd.Series) -> tuple[str | None, str]:
    if pd.notna(row.get("to_team")) and str(row.get("to_team")).strip():
        return str(row.get("to_team")).strip(), "to_team"
    if pd.notna(row.get("from_team")) and str(row.get("from_team")).strip():
        return str(row.get("from_team")).strip(), "from_team"
    if pd.notna(row.get("team_primary")) and str(row.get("team_primary")).strip():
        return str(row.get("team_primary")).strip(), "team_primary"
    return None, "unknown"


def synthesize_player_id(player_name: Any, team_name: str | None) -> str:
    suffix = slugify(team_name).lower() if team_name else "unknown_team"
    return f"player:{slugify(player_name).lower()}__{suffix}"


def build_transaction_id_audit(
    transactions: pd.DataFrame, master: pd.DataFrame, identity_lookup: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    transactions = transactions.copy()
    transactions["player_id"] = transactions["player_id"].astype("object")
    master_lookup = master[["transaction_id", "team_primary"]].copy()
    working = transactions.merge(master_lookup, on="transaction_id", how="left")

    blank_mask = working["player_id"].isna()
    audit_rows: list[dict[str, Any]] = []

    for index, row in working.loc[blank_mask].iterrows():
        team_name, team_source = choose_team_suffix(row)
        resolved_id, resolved_source = resolve_player_id(row["player_name"], identity_lookup, team_name)
        name_key = normalize_name(row["player_name"])
        lookup_matches = identity_lookup[identity_lookup["player_name_key"] == name_key]
        matched_existing = not lookup_matches.empty
        assignment_method = "matched_existing" if matched_existing else "synthetic_name"
        if not matched_existing:
            resolved_id = synthesize_player_id(row["player_name"], team_name)
            resolved_source = "synthetic_name"
        else:
            resolved_source = str(lookup_matches.iloc[0]["identity_source"])

        working.at[index, "player_id"] = resolved_id
        audit_rows.append(
            {
                "transaction_id": row["transaction_id"],
                "transaction_date": row["transaction_date"],
                "player_name": row["player_name"],
                "transaction_type": row["transaction_type"],
                "from_team": row.get("from_team"),
                "to_team": row.get("to_team"),
                "assigned_player_id": resolved_id,
                "assignment_method": assignment_method,
                "identity_source": resolved_source,
                "team_suffix_used": team_name,
                "team_suffix_source": team_source,
            }
        )

    updated_transactions = working.drop(columns=["team_primary"], errors="ignore")
    audit = pd.DataFrame(audit_rows)
    if not audit.empty:
        audit = audit.sort_values(["transaction_date", "player_name", "transaction_type"]).reset_index(drop=True)
    return updated_transactions, audit


def normalize_salary_tier(value: Any) -> Any:
    if pd.isna(value):
        return value
    return "Mid-Tier Rotation" if str(value) == "Mid" else value


def apply_contract_truth(
    destination: pd.DataFrame,
    contracts_truth: pd.DataFrame,
    fields: list[str],
    table_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    original = destination.copy()
    ready = destination.copy()
    ready["player_id_str"] = ready["player_id"].astype(str)
    truth = contracts_truth.copy()
    truth["player_id_str"] = truth["player_id"].astype(str)
    truth_fields = ["player_id_str"] + [field for field in fields if field in truth.columns]
    merged = ready.merge(truth[truth_fields], on="player_id_str", how="left", suffixes=("", "_truth"))

    for field in fields:
        truth_field = f"{field}_truth"
        if truth_field in merged.columns:
            merged[field] = merged[truth_field]

    merged = merged.drop(columns=["player_id_str"] + [c for c in merged.columns if c.endswith("_truth")])
    merged = merged[original.columns.tolist()]

    audit_rows: list[dict[str, Any]] = []
    merged_compare = merged.copy()
    original_compare = original.copy()
    for field in fields:
        if field in merged_compare.columns:
            if field in {"salary", "cap_hit", "salary_as_pct_cap", "pct_team"}:
                merged_compare[field] = pd.to_numeric(merged_compare[field], errors="coerce")
                original_compare[field] = pd.to_numeric(original_compare[field], errors="coerce")

    for idx in range(len(merged_compare)):
        changes = {}
        for field in fields:
            if field not in merged_compare.columns:
                continue
            old_value = original_compare.iloc[idx][field]
            new_value = merged_compare.iloc[idx][field]
            if pd.isna(old_value) and pd.isna(new_value):
                continue
            if old_value != new_value:
                changes[field] = {"old": None if pd.isna(old_value) else old_value, "new": None if pd.isna(new_value) else new_value}
        if changes:
            audit_rows.append(
                {
                    "table_name": table_name,
                    "player_id": merged.iloc[idx]["player_id"],
                    "player_name": merged.iloc[idx]["player_name"],
                    "team_name": merged.iloc[idx].get("team_name"),
                    "changed_fields": ",".join(changes.keys()),
                    "old_salary": changes.get("salary", {}).get("old"),
                    "new_salary": changes.get("salary", {}).get("new"),
                    "old_cap_hit": changes.get("cap_hit", {}).get("old"),
                    "new_cap_hit": changes.get("cap_hit", {}).get("new"),
                    "old_salary_as_pct_cap": changes.get("salary_as_pct_cap", {}).get("old"),
                    "new_salary_as_pct_cap": changes.get("salary_as_pct_cap", {}).get("new"),
                    "old_pct_team": changes.get("pct_team", {}).get("old"),
                    "new_pct_team": changes.get("pct_team", {}).get("new"),
                    "old_salary_tier": changes.get("salary_tier", {}).get("old"),
                    "new_salary_tier": changes.get("salary_tier", {}).get("new"),
                }
            )

    return merged, pd.DataFrame(audit_rows)


def main() -> None:
    identity_lookup = build_identity_lookup()

    master = pd.read_csv(TRANSACTIONS_MASTER_PATH)
    master = master.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)
    master.to_csv(TRANSACTIONS_MASTER_PATH, index=False)

    transactions = pd.read_csv(TRANSACTIONS_TABLE_PATH)
    blank_before = int(transactions["player_id"].isna().sum())
    updated_transactions, transaction_audit = build_transaction_id_audit(transactions, master, identity_lookup)
    blank_after = int(updated_transactions["player_id"].isna().sum())

    updated_transactions = updated_transactions.sort_values(["transaction_date", "transaction_id"]).reset_index(drop=True)
    updated_transactions.to_csv(TRANSACTIONS_TABLE_PATH, index=False)
    updated_transactions.to_parquet(TRANSACTIONS_TABLE_BASE.with_suffix(".parquet"), index=False)
    TRANSACTIONS_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    transaction_audit.to_csv(TRANSACTIONS_AUDIT_PATH, index=False)

    contracts = pd.read_csv(CONTRACTS_PATH)
    contracts_ready = contracts.copy()
    contracts_ready["salary_tier"] = contracts_ready["salary_tier"].map(normalize_salary_tier)
    contracts_audit = pd.DataFrame()
    if not contracts.equals(contracts_ready):
        contracts_audit = pd.DataFrame(
            [
                {
                    "table_name": "contracts_2026_salary_ready",
                    "player_id": row["player_id"],
                    "player_name": row["player_name"],
                    "team_name": row["team_name"],
                    "changed_fields": "salary_tier",
                    "old_salary": None,
                    "new_salary": None,
                    "old_cap_hit": None,
                    "new_cap_hit": None,
                    "old_salary_as_pct_cap": None,
                    "new_salary_as_pct_cap": None,
                    "old_pct_team": None,
                    "new_pct_team": None,
                    "old_salary_tier": "Mid",
                    "new_salary_tier": "Mid-Tier Rotation",
                }
                for _, row in contracts_ready[contracts["salary_tier"].astype(str).eq("Mid")].iterrows()
            ]
        )

    contracts_truth = contracts_ready.copy()

    team_rosters = pd.read_csv(TEAM_ROSTERS_PATH)
    team_rosters_ready, team_rosters_audit = apply_contract_truth(
        team_rosters,
        contracts_truth[contracts_truth["row_section"].astype(str) == "current_roster"].copy(),
        ["salary", "cap_hit", "salary_tier"],
        "team_rosters_salary_ready",
    )

    players_master = pd.read_csv(PLAYERS_MASTER_PATH)
    players_master_ready, players_master_audit = apply_contract_truth(
        players_master,
        contracts_truth,
        ["salary", "cap_hit", "salary_as_pct_cap", "pct_team", "salary_tier"],
        "players_master_salary_ready",
    )

    write_table(contracts_ready, CONTRACTS_SALARY_READY_BASE)
    write_table(team_rosters_ready, TEAM_ROSTERS_SALARY_READY_BASE)
    write_table(players_master_ready, PLAYERS_MASTER_SALARY_READY_BASE)

    SALARY_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    salary_audit = pd.concat([contracts_audit, team_rosters_audit, players_master_audit], ignore_index=True)
    salary_audit.to_csv(SALARY_SYNC_AUDIT_PATH, index=False)

    summary = {
        "transactions_rows": int(len(updated_transactions)),
        "transactions_blank_player_id_before": blank_before,
        "transactions_blank_player_id_after": blank_after,
        "transaction_audit_rows": int(len(transaction_audit)),
        "transactions_latest_date": str(pd.to_datetime(updated_transactions["transaction_date"]).max().date()),
        "contracts_salary_ready_rows": int(len(contracts_ready)),
        "team_rosters_salary_ready_rows": int(len(team_rosters_ready)),
        "players_master_salary_ready_rows": int(len(players_master_ready)),
        "salary_sync_audit_rows": int(len(salary_audit)),
        "team_rosters_salary_ready_missing_salary_rows": int(pd.to_numeric(team_rosters_ready["salary"], errors="coerce").isna().sum()),
        "players_master_salary_ready_missing_salary_rows": int(pd.to_numeric(players_master_ready["salary"], errors="coerce").isna().sum()),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
