#!/usr/bin/env python3
"""Build a notebook-style 2026 team roster grade HTML deliverable.

The notebook is driven from the current local Doc 2 tables, not the saved
Tableau extracts. Tableau outputs are loaded only as a QA/reference layer and
are never treated as the controlling source of truth for the notebook.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "case-studies"
OUT_PATH = OUT_DIR / "team_roster_grade_analysis_2026.html"
NOTEBOOK_DATA_DIR = ROOT / "data/doc2_roster_value/notebook/team_roster_grade_analysis_2026"
TABLEAU_DIR = ROOT / "data/doc2_roster_value/tableau"
TABLE_ROOT = ROOT / "data/doc2_roster_value/tables"

TEAM_GRADES_PATH = TABLE_ROOT / "team_roster_grades/team_roster_grades.csv"
VALUE_SCORES_PATH = TABLE_ROOT / "value_scores/value_scores.csv"
TEAM_ROSTERS_PATH = TABLE_ROOT / "team_rosters/team_rosters.csv"
TEAM_CAPS_PATH = TABLE_ROOT / "team_salary_cap/team_salary_cap.csv"
TABLEAU_TEAM_LEVEL_PATH = TABLEAU_DIR / "team_roster_team_level.csv"

TARGET_SEASON = 2026
VALUE_TIER_ORDER = ["Overvalued", "Risk", "Fair Value", "Strong Value", "Elite Value"]
GRADE_COLORS = {
    "A": "#34d399",
    "B": "#60a5fa",
    "C": "#fbbf24",
    "D": "#fb923c",
    "F": "#f87171",
}
VALUE_TIER_COLORS = {
    "Overvalued": "#ef4444",
    "Risk": "#f97316",
    "Fair Value": "#fbbf24",
    "Strong Value": "#38bdf8",
    "Elite Value": "#34d399",
}


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def esc(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return html.escape(str(value))


def fmt_num(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if digits == 0:
        return f"{int(round(float(value))):,}"
    return f"{float(value):,.{digits}f}"


def fmt_pct(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_pct_points(value: Any, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}%"


def fmt_currency(value: Any, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if digits == 0:
        return f"${int(round(float(value))):,}"
    return f"${float(value):,.{digits}f}"


def grade_from_rank(rank: int, total_teams: int) -> str:
    if total_teams <= 0:
        return "C"
    bucket = total_teams / 5.0
    if rank <= math.ceil(bucket):
        return "A"
    if rank <= math.ceil(bucket * 2):
        return "B"
    if rank <= math.ceil(bucket * 3):
        return "C"
    if rank <= math.ceil(bucket * 4):
        return "D"
    return "F"


def value_tier_from_score(score: Any) -> str:
    value = pd.to_numeric(pd.Series([score]), errors="coerce").iloc[0]
    if pd.isna(value):
        return "Risk"
    if value >= 80:
        return "Elite Value"
    if value >= 65:
        return "Strong Value"
    if value >= 50:
        return "Fair Value"
    if value >= 35:
        return "Risk"
    return "Overvalued"


def load_inputs() -> dict[str, pd.DataFrame]:
    tables = {
        "team_grades": pd.read_csv(TEAM_GRADES_PATH),
        "value_scores": pd.read_csv(VALUE_SCORES_PATH, dtype={"player_id": str, "team_id": str}),
        "team_rosters": pd.read_csv(TEAM_ROSTERS_PATH, dtype={"player_id": str, "team_id": str}),
        "team_caps": pd.read_csv(TEAM_CAPS_PATH, dtype={"team_id": str}),
    }
    if TABLEAU_TEAM_LEVEL_PATH.exists():
        tables["tableau_team_level"] = pd.read_csv(TABLEAU_TEAM_LEVEL_PATH)
    else:
        tables["tableau_team_level"] = pd.DataFrame()
    return tables


def build_player_universe(value_scores: pd.DataFrame, team_rosters: pd.DataFrame) -> pd.DataFrame:
    values = value_scores.copy()
    rosters = team_rosters.copy()
    values["season"] = num(values["season"])
    rosters["season"] = num(rosters["season"])
    values = values[values["season"] == TARGET_SEASON].copy()
    rosters = rosters[rosters["season"] == TARGET_SEASON].copy()

    for frame, columns in [
        (
            values,
            [
                "salary",
                "cap_hit",
                "expected_salary",
                "salary_gap",
                "salary_gap_pct",
                "production_score",
                "salary_efficiency_score",
                "scarcity_score",
                "playoff_score",
                "onoff_score",
                "value_score",
            ],
        ),
        (rosters, ["salary", "cap_hit", "age_2026", "years_service", "mpg"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = num(frame[column])

    roster_cols = [
        "player_id",
        "player_name",
        "team_id",
        "team_name",
        "season",
        "position_group",
        "projected_role",
        "actual_role",
        "team_abbreviation",
        "salary_tier",
        "salary",
        "cap_hit",
    ]
    roster_meta = (
        rosters[[column for column in roster_cols if column in rosters.columns]]
        .sort_values(["team_name", "player_name"])
        .drop_duplicates(["player_id", "team_id", "season"], keep="first")
    )
    merged = values.merge(
        roster_meta,
        on=["player_id", "team_id", "team_name", "season"],
        how="left",
        suffixes=("", "_roster"),
    )

    if "team_abbreviation" not in merged.columns:
        merged["team_abbreviation"] = pd.NA
    if "team_abbreviation_roster" in merged.columns:
        merged["team_abbreviation"] = merged["team_abbreviation"].fillna(merged["team_abbreviation_roster"])
    merged["position_group"] = merged.get("position_group", pd.Series(index=merged.index, dtype=object)).fillna("Unknown")
    merged["salary_tier_effective"] = merged["salary_tier"].fillna(merged.get("salary_tier_roster"))
    merged["salary_effective"] = num(merged["salary"]).fillna(num(merged.get("salary_roster")))
    merged["cap_hit_effective"] = num(merged["cap_hit"]).fillna(num(merged.get("cap_hit_roster")))
    merged["pay_reference"] = merged["salary_effective"].fillna(merged["cap_hit_effective"])
    merged["value_tier"] = merged["value_label"].fillna(merged["value_score"].apply(value_tier_from_score))
    merged["undervalued_flag"] = merged["undervalued_flag"].fillna(False).astype(bool)
    merged["overvalued_flag"] = merged["overvalued_flag"].fillna(False).astype(bool)
    merged["hidden_value_flag"] = (
        merged["hidden_talent_flag"].fillna(False).astype(bool)
        | (
            num(merged["value_score"]).fillna(0) >= 70
        )
        & merged["salary_tier_effective"].fillna("").str.contains("Minimum|Low|Rookie|Training", case=False, na=False)
    )
    return merged


def position_bucket(value: Any) -> str:
    text = str(value).strip().lower() if value is not None and not pd.isna(value) else ""
    if text.startswith("g"):
        return "Guard"
    if text.startswith("f"):
        return "Forward"
    if text.startswith("c"):
        return "Center"
    return "Unknown"


def build_team_analysis(inputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    players = build_player_universe(inputs["value_scores"], inputs["team_rosters"])
    team_grades = inputs["team_grades"].copy()
    team_caps = inputs["team_caps"].copy()
    tableau_team = inputs.get("tableau_team_level", pd.DataFrame()).copy()

    for frame, columns in [
        (
            team_grades,
            [
                "roster_count",
                "salary_cap",
                "total_cap_hit",
                "cap_space",
                "cap_used_pct",
                "avg_value_score",
                "median_value_score",
                "top_5_value_score_avg",
                "hidden_talent_players",
                "undervalued_players",
                "overvalued_players",
                "roster_grade_score",
                "value_per_million",
            ],
        ),
        (
            team_caps,
            [
                "salary_cap",
                "total_cap_hit",
                "cap_space",
                "cap_used_pct",
                "roster_count",
                "total_players",
                "team_total_salary",
                "team_salary_cap",
            ],
        ),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = num(frame[column])

    grade_lookup = team_grades.set_index("team_id", drop=False)
    cap_lookup = team_caps.set_index("team_id", drop=False)

    team_rows: list[dict[str, Any]] = []
    for team_id, group in players.groupby("team_id", dropna=False):
        ordered = group.sort_values(["value_score", "player_name"], ascending=[False, True]).copy()
        team_name = ordered["team_name"].iloc[0]
        team_grade_row = grade_lookup.loc[str(team_id)] if str(team_id) in grade_lookup.index else None
        team_cap_row = cap_lookup.loc[str(team_id)] if str(team_id) in cap_lookup.index else None
        salary_total = ordered["pay_reference"].sum(min_count=1)
        total_cap_hit = salary_total
        if team_cap_row is not None and pd.notna(team_cap_row.get("total_cap_hit")):
            total_cap_hit = float(team_cap_row["total_cap_hit"])
        salary_cap = None
        if team_cap_row is not None and pd.notna(team_cap_row.get("salary_cap")):
            salary_cap = float(team_cap_row["salary_cap"])
        elif team_grade_row is not None and pd.notna(team_grade_row.get("salary_cap")):
            salary_cap = float(team_grade_row["salary_cap"])

        top2_salary = ordered["pay_reference"].dropna().nlargest(2).sum()
        median_value = ordered["value_score"].median()
        mean_value = ordered["value_score"].mean()
        top_player = ordered.iloc[0]
        position_counts = ordered["position_group"].map(position_bucket).value_counts()

        team_rows.append(
            {
                "season": TARGET_SEASON,
                "team_id": str(team_id),
                "team_name": team_name,
                "team_abbr": ordered["team_abbreviation"].dropna().iloc[0] if ordered["team_abbreviation"].notna().any() else None,
                "roster_size": int(ordered["player_id"].nunique()),
                "cap_sheet_roster_count": float(team_cap_row["roster_count"]) if team_cap_row is not None and pd.notna(team_cap_row.get("roster_count")) else None,
                "cap_sheet_total_players": float(team_cap_row["total_players"]) if team_cap_row is not None and pd.notna(team_cap_row.get("total_players")) else None,
                "median_value_score": round(median_value, 2),
                "mean_value_score": round(mean_value, 2),
                "total_team_value": round(ordered["value_score"].sum(), 2),
                "cap_concentration_top2_pct": round((top2_salary / total_cap_hit) * 100.0, 2) if total_cap_hit and not pd.isna(total_cap_hit) else None,
                "total_salary": round(total_cap_hit, 2) if not pd.isna(total_cap_hit) else None,
                "salary_cap": round(salary_cap, 2) if salary_cap is not None else None,
                "cap_space": float(team_cap_row["cap_space"]) if team_cap_row is not None and pd.notna(team_cap_row.get("cap_space")) else None,
                "cap_used_pct": float(team_cap_row["cap_used_pct"]) if team_cap_row is not None and pd.notna(team_cap_row.get("cap_used_pct")) else None,
                "hidden_value_count": int(ordered["hidden_value_flag"].sum()),
                "n_undervalued": int(ordered["undervalued_flag"].sum()),
                "n_overvalued_adj": int(ordered["overvalued_flag"].sum()),
                "avg_salary_gap_pct": round(num(ordered["salary_gap_pct"]).mean(), 4),
                "n_guards": int(position_counts.get("Guard", 0)),
                "n_forwards": int(position_counts.get("Forward", 0)),
                "n_centers": int(position_counts.get("Center", 0)),
                "n_pos_unknown": int(position_counts.get("Unknown", 0)),
                "n_elite_value": int((ordered["value_tier"] == "Elite Value").sum()),
                "n_strong_value": int((ordered["value_tier"] == "Strong Value").sum()),
                "n_fair_value": int((ordered["value_tier"] == "Fair Value").sum()),
                "n_risk": int((ordered["value_tier"] == "Risk").sum()),
                "n_overvalued_tier": int((ordered["value_tier"] == "Overvalued").sum()),
                "top_player": top_player["player_name"],
                "top_player_value_score": round(float(top_player["value_score"]), 2) if pd.notna(top_player["value_score"]) else None,
                "raw_roster_grade_score": float(team_grade_row["roster_grade_score"]) if team_grade_row is not None and pd.notna(team_grade_row.get("roster_grade_score")) else None,
                "raw_roster_grade": team_grade_row["roster_grade"] if team_grade_row is not None and "roster_grade" in team_grade_row else None,
                "raw_value_per_million": float(team_grade_row["value_per_million"]) if team_grade_row is not None and pd.notna(team_grade_row.get("value_per_million")) else None,
            }
        )

    team_df = pd.DataFrame(team_rows)
    team_df = team_df.sort_values(["median_value_score", "mean_value_score", "total_team_value"], ascending=[False, False, False]).reset_index(drop=True)
    team_df["rank"] = range(1, len(team_df) + 1)
    team_df["team_grade"] = [grade_from_rank(rank, len(team_df)) for rank in team_df["rank"]]
    team_df["grade_color"] = team_df["team_grade"].map(GRADE_COLORS)

    value_mid = team_df["median_value_score"].median()
    cap_mid = team_df["cap_concentration_top2_pct"].median()

    def quadrant(row: pd.Series) -> str:
        high_value = row["median_value_score"] >= value_mid
        high_cap = row["cap_concentration_top2_pct"] >= cap_mid
        if high_value and not high_cap:
            return "Efficient Stars"
        if high_value and high_cap:
            return "Star-Dependent"
        if not high_value and not high_cap:
            return "Distributed Mediocrity"
        return "Cap Trapped"

    team_df["scatter_quadrant"] = team_df.apply(quadrant, axis=1)

    tier_rows: list[dict[str, Any]] = []
    for _, team_row in team_df.iterrows():
        team_players = players[players["team_name"] == team_row["team_name"]].copy()
        tier_counts = team_players["value_tier"].value_counts()
        for tier_order, tier in enumerate(VALUE_TIER_ORDER, start=1):
            count = int(tier_counts.get(tier, 0))
            tier_rows.append(
                {
                    "team_name": team_row["team_name"],
                    "team_abbr": team_row["team_abbr"],
                    "rank": int(team_row["rank"]),
                    "team_grade": team_row["team_grade"],
                    "value_tier": tier,
                    "tier_order": tier_order,
                    "player_count": count,
                    "roster_size": int(team_row["roster_size"]),
                    "pct_of_roster": round(count / max(int(team_row["roster_size"]), 1), 4),
                }
            )
    tier_df = pd.DataFrame(tier_rows)

    hidden_df = team_df[
        [
            "team_name",
            "team_abbr",
            "rank",
            "team_grade",
            "hidden_value_count",
            "roster_size",
            "median_value_score",
            "n_undervalued",
        ]
    ].copy()

    leaderboard_df = team_df[
        [
            "team_name",
            "team_abbr",
            "rank",
            "team_grade",
            "median_value_score",
            "mean_value_score",
            "hidden_value_count",
            "n_undervalued",
            "n_overvalued_adj",
            "total_salary",
        ]
    ].copy()

    scatter_df = team_df[
        [
            "team_name",
            "team_abbr",
            "rank",
            "team_grade",
            "median_value_score",
            "cap_concentration_top2_pct",
            "total_salary",
            "scatter_quadrant",
        ]
    ].copy()

    comparison_df = pd.DataFrame()
    comparison_meta = {
        "tableau_reference_available": not tableau_team.empty,
        "material_match": False,
        "grade_match_rate": None,
        "median_rank_diff": None,
        "median_value_diff": None,
    }
    if not tableau_team.empty:
        tableau = tableau_team.copy()
        for column in ["rank", "median_value_score", "mean_value_score", "cap_concentration_top2_pct", "hidden_value_count"]:
            if column in tableau.columns:
                tableau[column] = num(tableau[column])
        comparison_df = team_df.merge(
            tableau[
                [
                    "team_name",
                    "rank",
                    "team_grade",
                    "median_value_score",
                    "mean_value_score",
                    "cap_concentration_top2_pct",
                    "hidden_value_count",
                    "scatter_quadrant",
                ]
            ].rename(
                columns={
                    "rank": "tableau_rank",
                    "team_grade": "tableau_grade",
                    "median_value_score": "tableau_median_value_score",
                    "mean_value_score": "tableau_mean_value_score",
                    "cap_concentration_top2_pct": "tableau_cap_concentration_top2_pct",
                    "hidden_value_count": "tableau_hidden_value_count",
                    "scatter_quadrant": "tableau_scatter_quadrant",
                }
            ),
            on="team_name",
            how="left",
        )
        comparison_df["rank_diff"] = (comparison_df["rank"] - comparison_df["tableau_rank"]).abs()
        comparison_df["median_value_diff"] = (comparison_df["median_value_score"] - comparison_df["tableau_median_value_score"]).abs()
        comparison_df["grade_match"] = comparison_df["team_grade"] == comparison_df["tableau_grade"]
        comparison_df["quadrant_match"] = comparison_df["scatter_quadrant"] == comparison_df["tableau_scatter_quadrant"]
        grade_match_rate = float(comparison_df["grade_match"].mean()) if not comparison_df.empty else None
        median_rank_diff = float(comparison_df["rank_diff"].median()) if not comparison_df.empty else None
        median_value_diff = float(comparison_df["median_value_diff"].median()) if not comparison_df.empty else None
        material_match = bool(
            len(comparison_df) == len(team_df)
            and grade_match_rate is not None
            and median_rank_diff is not None
            and median_value_diff is not None
            and grade_match_rate >= 0.60
            and median_rank_diff <= 2.0
            and median_value_diff <= 1.5
        )
        comparison_meta.update(
            {
                "material_match": material_match,
                "grade_match_rate": grade_match_rate,
                "median_rank_diff": median_rank_diff,
                "median_value_diff": median_value_diff,
            }
        )

    return {
        "players": players,
        "team_level": team_df,
        "leaderboard": leaderboard_df,
        "scatter": scatter_df,
        "tier_stacked": tier_df,
        "hidden_value": hidden_df,
        "tableau_comparison": comparison_df,
        "comparison_meta": comparison_meta,
        "thresholds": {
            "value_median": value_mid,
            "cap_concentration_median": cap_mid,
        },
    }


def write_outputs(bundle: dict[str, Any]) -> None:
    NOTEBOOK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    bundle["team_level"].to_csv(NOTEBOOK_DATA_DIR / "team_roster_team_level_fresh.csv", index=False)
    bundle["leaderboard"].to_csv(NOTEBOOK_DATA_DIR / "team_value_leaderboard.csv", index=False)
    bundle["scatter"].to_csv(NOTEBOOK_DATA_DIR / "cap_concentration_vs_team_value.csv", index=False)
    bundle["tier_stacked"].to_csv(NOTEBOOK_DATA_DIR / "roster_tier_stacked_by_team.csv", index=False)
    bundle["hidden_value"].to_csv(NOTEBOOK_DATA_DIR / "hidden_value_talent_by_team.csv", index=False)
    bundle["tableau_comparison"].to_csv(NOTEBOOK_DATA_DIR / "tableau_comparison_summary.csv", index=False)


def leaderboard_svg(team_df: pd.DataFrame, width: int = 1040, bar_h: int = 28, gap: int = 12) -> str:
    left = 220
    right = 84
    top = 28
    bottom = 42
    height = top + bottom + len(team_df) * (bar_h + gap)
    inner_w = width - left - right
    min_score = float(team_df["median_value_score"].min())
    max_score = float(team_df["median_value_score"].max())
    span = max(max_score - min_score, 1.0)

    rows = []
    for idx, row in team_df.iterrows():
        y = top + idx * (bar_h + gap)
        width_pct = (float(row["median_value_score"]) - min_score) / span
        bar_w = max(28.0, inner_w * width_pct)
        rows.append(
            f"""
            <text x="{left - 14}" y="{y + 18}" text-anchor="end" class="chart-label">{int(row['rank'])}. {esc(row['team_name'])}</text>
            <rect x="{left}" y="{y}" width="{inner_w}" height="{bar_h}" rx="12" class="bar-track-chart" />
            <rect x="{left}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" rx="12" fill="{row['grade_color']}" />
            <text x="{left + bar_w + 10:.1f}" y="{y + 18}" class="chart-value">{fmt_num(row['median_value_score'], 2)}</text>
            <text x="{width - 10}" y="{y + 18}" text-anchor="end" class="chart-sub">Hidden value: {int(row['hidden_value_count'])}</text>
            """
        )
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Team value leaderboard">
      {''.join(rows)}
      <text x="{left}" y="{height - 12}" class="axis-note">Bar length = median player value score. Teams are ranked off the fresh local analysis, not the saved Tableau layer.</text>
    </svg>
    """


def scatter_svg(team_df: pd.DataFrame, value_mid: float, cap_mid: float, width: int = 1040, height: int = 520) -> str:
    left = 84
    right = 34
    top = 40
    bottom = 60
    inner_w = width - left - right
    inner_h = height - top - bottom
    x_min = max(0.0, float(team_df["cap_concentration_top2_pct"].min()) - 2.0)
    x_max = float(team_df["cap_concentration_top2_pct"].max()) + 2.0
    y_min = float(team_df["median_value_score"].min()) - 1.0
    y_max = float(team_df["median_value_score"].max()) + 1.0

    def sx(value: float) -> float:
        return left + ((value - x_min) / max(x_max - x_min, 1e-6)) * inner_w

    def sy(value: float) -> float:
        return top + inner_h - ((value - y_min) / max(y_max - y_min, 1e-6)) * inner_h

    notable = set()
    if not team_df.empty:
        notable.update(team_df.nsmallest(1, "cap_concentration_top2_pct")["team_name"].tolist())
        notable.update(team_df.nlargest(1, "cap_concentration_top2_pct")["team_name"].tolist())
        notable.update(team_df.nlargest(1, "median_value_score")["team_name"].tolist())
        notable.update(team_df.nsmallest(1, "median_value_score")["team_name"].tolist())

    x_ticks = []
    for tick in range(int(math.floor(x_min / 2.0) * 2), int(math.ceil(x_max / 2.0) * 2) + 1, 2):
        x = sx(float(tick))
        x_ticks.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + inner_h}" class="grid-line" />')
        x_ticks.append(f'<text x="{x:.1f}" y="{height - 26}" text-anchor="middle" class="axis-label">{tick}%</text>')

    y_ticks = []
    for tick in range(int(math.floor(y_min)), int(math.ceil(y_max)) + 1):
        y = sy(float(tick))
        y_ticks.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + inner_w}" y2="{y:.1f}" class="grid-line" />')
        y_ticks.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="axis-label">{tick}</text>')

    points = []
    for _, row in team_df.iterrows():
        x = sx(float(row["cap_concentration_top2_pct"]))
        y = sy(float(row["median_value_score"]))
        radius = 9
        points.append(
            f"""
            <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{row['grade_color']}" stroke="#f8fafc" stroke-width="1.8" />
            <text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" class="scatter-point-label">{esc(row['team_abbr'])}</text>
            """
        )
        if row["team_name"] in notable:
            points.append(
                f'<text x="{x + 12:.1f}" y="{y + 4:.1f}" class="scatter-annotation">{esc(row["team_name"])}</text>'
            )

    left_mid = x_min + (cap_mid - x_min) / 2.0
    right_mid = cap_mid + (x_max - cap_mid) / 2.0
    top_band = y_max - 0.1
    bottom_band = y_min + 0.9
    quad_labels = [
        ("Efficient Stars", sx(left_mid), sy(top_band)),
        ("Star-Dependent", sx(right_mid), sy(top_band)),
        ("Distributed Mediocrity", sx(left_mid), sy(bottom_band)),
        ("Cap Trapped", sx(right_mid), sy(bottom_band)),
    ]
    quadrants = "".join(
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" class="quadrant-label">{label}</text>'
        for label, x, y in quad_labels
    )

    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Cap concentration versus team value scatter">
      <rect x="{left}" y="{top}" width="{inner_w}" height="{inner_h}" class="chart-panel" />
      {''.join(x_ticks)}
      {''.join(y_ticks)}
      <line x1="{sx(cap_mid):.1f}" y1="{top}" x2="{sx(cap_mid):.1f}" y2="{top + inner_h}" class="ref-line" />
      <line x1="{left}" y1="{sy(value_mid):.1f}" x2="{left + inner_w}" y2="{sy(value_mid):.1f}" class="ref-line" />
      {quadrants}
      {''.join(points)}
      <text x="{left + inner_w / 2:.1f}" y="{height - 10}" text-anchor="middle" class="axis-note">Top-2 cap concentration percent</text>
      <text x="18" y="{top + inner_h / 2:.1f}" transform="rotate(-90 18 {top + inner_h / 2:.1f})" text-anchor="middle" class="axis-note">Median player value score</text>
    </svg>
    """


def stacked_bar_svg(tier_df: pd.DataFrame, width: int = 1040, row_h: int = 26, gap: int = 12) -> str:
    left = 220
    right = 44
    top = 48
    bottom = 46
    teams = tier_df["team_name"].drop_duplicates().tolist()
    height = top + bottom + len(teams) * (row_h + gap)
    inner_w = width - left - right

    rows = []
    for idx, team_name in enumerate(teams):
        y = top + idx * (row_h + gap)
        team_slice = tier_df[tier_df["team_name"] == team_name].sort_values("tier_order")
        roster_size = max(int(team_slice["roster_size"].iloc[0]), 1)
        cursor = left
        rows.append(f'<text x="{left - 14}" y="{y + 18}" text-anchor="end" class="chart-label">{esc(team_name)}</text>')
        rows.append(f'<rect x="{left}" y="{y}" width="{inner_w}" height="{row_h}" rx="12" class="bar-track-chart" />')
        for _, tier_row in team_slice.iterrows():
            share = float(tier_row["player_count"]) / roster_size
            if share <= 0:
                continue
            segment_w = inner_w * share
            color = VALUE_TIER_COLORS[tier_row["value_tier"]]
            rows.append(
                f'<rect x="{cursor:.1f}" y="{y}" width="{segment_w:.1f}" height="{row_h}" fill="{color}" rx="12" />'
            )
            if segment_w >= 34:
                rows.append(
                    f'<text x="{cursor + segment_w / 2:.1f}" y="{y + 18}" text-anchor="middle" class="segment-label">{int(tier_row["player_count"])}</text>'
                )
            cursor += segment_w
    legend = []
    legend_x = left
    for idx, tier in enumerate(VALUE_TIER_ORDER):
        x = legend_x + idx * 150
        legend.append(f'<rect x="{x}" y="16" width="14" height="14" rx="4" fill="{VALUE_TIER_COLORS[tier]}" />')
        legend.append(f'<text x="{x + 22}" y="28" class="legend-label">{esc(tier)}</text>')
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Roster tier stacked bar by team">
      {''.join(legend)}
      {''.join(rows)}
      <text x="{left}" y="{height - 12}" class="axis-note">Each bar sums to the fresh roster universe for that team. Tier cutoffs follow the live value-score pipeline.</text>
    </svg>
    """


def hidden_value_svg(hidden_df: pd.DataFrame, width: int = 1040, row_h: int = 30, gap: int = 12) -> str:
    left = 220
    right = 56
    top = 40
    bottom = 54
    height = top + bottom + len(hidden_df) * (row_h + gap)
    inner_w = width - left - right
    max_hidden = max(int(hidden_df["hidden_value_count"].max()), 1)

    x_ticks = []
    for tick in range(0, max_hidden + 1):
        x = left + (tick / max_hidden) * inner_w
        x_ticks.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + len(hidden_df) * (row_h + gap)}" class="grid-line" />')
        x_ticks.append(f'<text x="{x:.1f}" y="{height - 24}" text-anchor="middle" class="axis-label">{tick}</text>')

    dots = []
    for idx, row in hidden_df.iterrows():
        y = top + idx * (row_h + gap) + row_h / 2
        x = left + (int(row["hidden_value_count"]) / max_hidden) * inner_w
        radius = 7 + (int(row["roster_size"]) / max(hidden_df["roster_size"].max(), 1)) * 11
        dots.append(f'<text x="{left - 14}" y="{y + 4:.1f}" text-anchor="end" class="chart-label">{esc(row["team_name"])}</text>')
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{GRADE_COLORS[row["team_grade"]]}" fill-opacity="0.78" stroke="#f8fafc" stroke-width="1.6" />')
        dots.append(f'<text x="{x + radius + 8:.1f}" y="{y + 4:.1f}" class="chart-sub">{int(row["hidden_value_count"])} hidden | {int(row["n_undervalued"])} undervalued</text>')
    return f"""
    <svg viewBox="0 0 {width} {height}" class="chart-svg" role="img" aria-label="Hidden value talent by team">
      {''.join(x_ticks)}
      {''.join(dots)}
      <text x="{left + inner_w / 2:.1f}" y="{height - 8}" text-anchor="middle" class="axis-note">Hidden value count. Dot size scales with roster size.</text>
    </svg>
    """


def card_grid(cards: list[tuple[str, str, str]]) -> str:
    return "".join(
        f"""
        <article class="metric-card">
          <div class="metric-kicker">{esc(kicker)}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-sub">{esc(sub)}</div>
        </article>
        """
        for kicker, value, sub in cards
    )


def comparison_table_html(comparison_df: pd.DataFrame) -> str:
    if comparison_df.empty:
        return "<p class='muted'>Saved Tableau comparison extract not available in this workspace.</p>"
    headers = [
        "Team",
        "Fresh Rank",
        "Tableau Rank",
        "Rank Diff",
        "Fresh Grade",
        "Tableau Grade",
        "Fresh Median",
        "Tableau Median",
    ]
    rows = []
    for _, row in comparison_df.sort_values("rank").iterrows():
        rows.append(
            [
                esc(row["team_name"]),
                fmt_num(row["rank"], 0),
                fmt_num(row["tableau_rank"], 0),
                fmt_num(row["rank_diff"], 0),
                esc(row["team_grade"]),
                esc(row["tableau_grade"]),
                fmt_num(row["median_value_score"], 2),
                fmt_num(row["tableau_median_value_score"], 2),
            ]
        )
    head = "".join(f"<th>{title}</th>" for title in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"""
    <div class="table-wrap">
      <table>
        <thead><tr>{head}</tr></thead>
        <tbody>{''.join(body)}</tbody>
      </table>
    </div>
    """


def build_takeaways(team_df: pd.DataFrame) -> list[str]:
    top_team = team_df.iloc[0]
    bottom_team = team_df.iloc[-1]
    most_concentrated = team_df.sort_values("cap_concentration_top2_pct", ascending=False).iloc[0]
    least_concentrated = team_df.sort_values("cap_concentration_top2_pct", ascending=True).iloc[0]
    most_undervalued = team_df.sort_values(["n_undervalued", "median_value_score"], ascending=[False, False]).iloc[0]
    hidden_leader = team_df.sort_values(["hidden_value_count", "n_undervalued"], ascending=[False, False]).iloc[0]
    return [
        f"{top_team['team_name']} leads the fresh 2026 board with a median value score of {fmt_num(top_team['median_value_score'], 2)} and a league-best grade of {top_team['team_grade']}.",
        f"{most_concentrated['team_name']} is the most top-heavy cap build at {fmt_pct_points(most_concentrated['cap_concentration_top2_pct'], 1)}, while {least_concentrated['team_name']} is the most distributed at {fmt_pct_points(least_concentrated['cap_concentration_top2_pct'], 1)}.",
        f"{most_undervalued['team_name']} carries the deepest undervalued count in the live model with {int(most_undervalued['n_undervalued'])} players flagged as returning more value than price.",
        f"{hidden_leader['team_name']} currently tops the hidden-value chart at {int(hidden_leader['hidden_value_count'])}; if that number stays low league-wide, it is a signal that the current 2026 file is still identifying very little true below-market breakout talent.",
        f"{bottom_team['team_name']} lands at the bottom of the current snapshot with a {bottom_team['team_grade']} grade, reminding us that this notebook is grading the typical roster slot, not just headline star power.",
    ]


def build_html(bundle: dict[str, Any]) -> str:
    team_df = bundle["team_level"]
    comparison_df = bundle["tableau_comparison"]
    comparison_meta = bundle["comparison_meta"]
    thresholds = bundle["thresholds"]

    takeaways = build_takeaways(team_df)
    summary_cards = [
        ("Fresh team universe", fmt_num(len(team_df), 0), "All 15 teams rebuilt from current local roster-value tables"),
        ("Primary grade signal", "Median value score", "Letter grades are assigned on a league-relative quintile curve"),
        ("Median value range", f"{fmt_num(team_df['median_value_score'].min(), 2)} - {fmt_num(team_df['median_value_score'].max(), 2)}", "Current live spread across the league"),
        ("Tableau comparison", "Mismatch" if not comparison_meta["material_match"] else "Aligned", "Saved Tableau files stay QA-only unless they materially match the fresh calculation"),
    ]

    hero_top = team_df.iloc[0]
    hero_bottom = team_df.iloc[-1]
    comparison_copy = (
        f"Fresh vs. saved Tableau comparison: grade match rate {fmt_pct(comparison_meta['grade_match_rate'], 0)}; median rank diff {fmt_num(comparison_meta['median_rank_diff'], 1)}; median value diff {fmt_num(comparison_meta['median_value_diff'], 2)}."
        if comparison_meta["tableau_reference_available"]
        else "Saved Tableau team extract was not available, so the notebook is fully driven by the current local tables."
    )
    if comparison_meta["tableau_reference_available"] and not comparison_meta["material_match"]:
        comparison_copy += " The saved Tableau layer does not materially match the fresh analysis, so the notebook keeps the fresh local build as the source of truth."

    methodology_points = [
        "Team grades are rebuilt from the 2026 local value-score table and sorted by median player value score, which keeps the grade focused on the typical roster slot instead of one star contract.",
        "Cap concentration is recalculated as the share of total cap hit carried by each team’s top two salaries, using live salary rows with the team salary-cap table as the denominator.",
        "Roster tiers, undervalued counts, and hidden-value counts are all derived from the same fresh player universe so every chart and takeaway stays on one calculation path.",
        "Saved Tableau extracts are loaded only as a comparison check. If they drift materially from the fresh analysis, this notebook does not inherit those rankings.",
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>WNBA 2026 Team Roster Grade Analysis</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --paper: rgba(255,255,255,0.82);
      --paper-strong: rgba(255,255,255,0.93);
      --ink: #112031;
      --muted: #536277;
      --line: rgba(17,32,49,0.12);
      --line-strong: rgba(17,32,49,0.22);
      --navy: #18324b;
      --amber: #d97706;
      --shadow: 0 24px 70px rgba(17,32,49,0.10);
      --radius: 24px;
      --font-display: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      --font-body: "Avenir Next", "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: var(--font-body);
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(251,191,36,0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(96,165,250,0.14), transparent 24%),
        linear-gradient(180deg, #f9f5ee 0%, var(--bg) 100%);
    }}
    a {{ color: inherit; }}
    .page {{
      width: min(1420px, calc(100vw - 40px));
      margin: 24px auto 48px;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 22px;
      align-items: start;
    }}
    .sidebar {{
      position: sticky;
      top: 18px;
      padding: 22px;
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(24,50,75,0.98), rgba(17,32,49,0.94));
      color: #f8fafc;
      box-shadow: var(--shadow);
    }}
    .eyebrow {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: rgba(248,250,252,0.72);
      margin-bottom: 10px;
    }}
    .sidebar h1 {{
      margin: 0 0 12px;
      font-family: var(--font-display);
      font-size: 32px;
      line-height: 1.05;
    }}
    .sidebar p {{
      margin: 0 0 14px;
      color: rgba(248,250,252,0.8);
      line-height: 1.55;
      font-size: 14px;
    }}
    .nav {{
      margin-top: 24px;
      display: grid;
      gap: 10px;
    }}
    .nav a {{
      text-decoration: none;
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 999px;
      padding: 10px 14px;
      background: rgba(255,255,255,0.06);
      font-size: 13px;
    }}
    main {{
      display: grid;
      gap: 22px;
    }}
    .hero, .section {{
      padding: 28px 30px 30px;
      border-radius: 28px;
      background: var(--paper);
      backdrop-filter: blur(16px);
      box-shadow: var(--shadow);
      border: 1px solid rgba(255,255,255,0.4);
    }}
    .hero {{
      background:
        linear-gradient(135deg, rgba(24,50,75,0.96), rgba(40,62,87,0.92)),
        linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.02));
      color: #f8fafc;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: 1.3fr 0.9fr;
      gap: 20px;
      align-items: end;
    }}
    .hero h2 {{
      margin: 0 0 10px;
      font-family: var(--font-display);
      font-size: clamp(34px, 4vw, 54px);
      line-height: 0.98;
    }}
    .hero p {{
      margin: 0 0 12px;
      line-height: 1.65;
      color: rgba(248,250,252,0.84);
    }}
    .hero-note {{
      padding: 16px 18px;
      border-radius: 20px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.10);
    }}
    .metric-grid {{
      margin-top: 22px;
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }}
    .metric-card {{
      padding: 18px;
      border-radius: 20px;
      background: var(--paper-strong);
      border: 1px solid var(--line);
    }}
    .metric-kicker {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .metric-value {{
      font-family: var(--font-display);
      font-size: 30px;
      line-height: 1;
      margin-bottom: 6px;
      color: var(--navy);
    }}
    .metric-sub {{
      font-size: 13px;
      color: var(--muted);
      line-height: 1.5;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: end;
      margin-bottom: 18px;
    }}
    .section-id {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--amber);
      margin-bottom: 8px;
    }}
    .section h3 {{
      margin: 0;
      font-family: var(--font-display);
      font-size: 34px;
      line-height: 1.04;
    }}
    .section-head p, .section > p, .section li {{
      color: var(--muted);
      line-height: 1.65;
      font-size: 15px;
    }}
    .section > p {{ margin: 0 0 14px; }}
    .section ul {{
      margin: 12px 0 0 18px;
      padding: 0;
    }}
    .callout-row {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .callout {{
      padding: 16px 18px;
      border-radius: 20px;
      background: #fffdf8;
      border: 1px solid rgba(217,119,6,0.16);
    }}
    .callout strong {{
      display: block;
      margin-bottom: 6px;
      color: var(--navy);
    }}
    .chart-shell {{
      margin-top: 16px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(246,248,250,0.94));
      border: 1px solid var(--line);
      overflow-x: auto;
    }}
    .chart-svg {{
      width: 100%;
      min-width: 940px;
      height: auto;
      display: block;
    }}
    .chart-panel {{ fill: rgba(248,250,252,0.9); }}
    .bar-track-chart {{ fill: rgba(17,32,49,0.08); }}
    .grid-line {{
      stroke: rgba(17,32,49,0.10);
      stroke-width: 1;
    }}
    .ref-line {{
      stroke: rgba(217,119,6,0.6);
      stroke-width: 1.6;
      stroke-dasharray: 6 6;
    }}
    .chart-label {{
      font-size: 13px;
      fill: #112031;
      font-weight: 600;
    }}
    .chart-value {{
      font-size: 13px;
      fill: #112031;
      font-weight: 700;
    }}
    .chart-sub {{
      font-size: 12px;
      fill: #536277;
    }}
    .axis-label, .axis-note, .legend-label, .segment-label, .scatter-point-label, .scatter-annotation, .quadrant-label {{
      fill: #536277;
      font-size: 12px;
    }}
    .segment-label {{
      fill: #0f172a;
      font-weight: 700;
    }}
    .scatter-point-label {{
      fill: #112031;
      font-weight: 700;
    }}
    .scatter-annotation {{
      fill: #112031;
      font-size: 11px;
      font-weight: 600;
    }}
    .quadrant-label {{
      fill: rgba(17,32,49,0.38);
      font-size: 16px;
      font-weight: 700;
    }}
    .table-wrap {{
      overflow-x: auto;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.72);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 720px;
    }}
    th, td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
    }}
    th {{
      background: rgba(24,50,75,0.06);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(217,119,6,0.12);
      color: var(--amber);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .muted {{
      color: var(--muted);
    }}
    @media (max-width: 1120px) {{
      .page {{
        width: min(100vw - 26px, 980px);
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: relative;
        top: 0;
      }}
      .hero-grid, .metric-grid, .callout-row {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <div class="eyebrow">WNBA 2026 Notebook</div>
      <h1>Team Roster Grade Analysis</h1>
      <p>This notebook rebuilds the team roster grade story from the current local roster-value tables so the ranking, visuals, and narrative all stay on one fresh calculation path.</p>
      <p>{esc(comparison_copy)}</p>
      <nav class="nav">
        <a href="#overview">Overview</a>
        <a href="#method">Method</a>
        <a href="#leaderboard">Leaderboard</a>
        <a href="#scatter">Cap Concentration</a>
        <a href="#tiers">Roster Tiers</a>
        <a href="#hidden">Hidden Value</a>
        <a href="#appendix">Appendix</a>
      </nav>
    </aside>
    <main>
      <section class="hero" id="overview">
        <div class="hero-grid">
          <div>
            <div class="eyebrow">Fresh Team-Level Rollup</div>
            <h2>Median roster quality is the anchor, and the live local tables now drive every team-grade view.</h2>
            <p>The framework memo defines team grades around the middle roster slot, not the loudest star contract. This rebuild follows that logic: teams are ranked by the median player value score from the current 2026 value table, then grouped into a league-relative A-to-F curve.</p>
            <p>{esc(hero_top['team_name'])} sits at the top of the current board at {fmt_num(hero_top['median_value_score'], 2)}, while {esc(hero_bottom['team_name'])} anchors the bottom at {fmt_num(hero_bottom['median_value_score'], 2)}. The range is still tight, which matches the memo’s warning that partial coverage compresses separation.</p>
          </div>
          <div class="hero-note">
            <div class="eyebrow">Source-of-truth note</div>
            <p>The notebook uses <strong>fresh local tables</strong> as the source of truth. Saved Tableau extracts are compared for drift, but they are not allowed to overwrite the live ranking if the two paths materially disagree.</p>
            <div class="pill">{'Tableau QA mismatch' if not comparison_meta['material_match'] else 'Tableau QA aligned'}</div>
          </div>
        </div>
        <div class="metric-grid">
          {card_grid(summary_cards)}
        </div>
      </section>

      <section class="section" id="method">
        <div class="section-head">
          <div>
            <div class="section-id">1. Method snapshot</div>
            <h3>One calculation path for the ranking, visuals, and write-up</h3>
          </div>
          <div class="pill">2026 local build</div>
        </div>
        <p>The deliverable reads the updated <code>team_roster_grades</code>, <code>value_scores</code>, <code>team_rosters</code>, and <code>team_salary_cap</code> tables, then rebuilds the team view directly from those files. That keeps the HTML narrative aligned with the same tables you are updating elsewhere in the project.</p>
        <ul>
          {''.join(f'<li>{esc(point)}</li>' for point in methodology_points)}
        </ul>
        <div class="callout-row">
          <div class="callout">
            <strong>League midpoint used for the scatter</strong>
            Median value score split: {fmt_num(thresholds['value_median'], 2)}. Top-2 cap concentration split: {fmt_pct_points(thresholds['cap_concentration_median'], 1)}.
          </div>
          <div class="callout">
            <strong>Current model caveat</strong>
            Hidden-value counts are driven by the live model definition. If that count stays low or zero, the notebook preserves that signal instead of forcing a more dramatic story than the data supports today.
          </div>
        </div>
      </section>

      <section class="section" id="leaderboard">
        <div class="section-head">
          <div>
            <div class="section-id">2. Team Value Leaderboard</div>
            <h3>The cleanest read is still the middle roster slot</h3>
          </div>
        </div>
        <p>The leaderboard is sorted by median player value score. That makes it a roster-quality chart first, rather than a star-power chart. Hidden-value counts sit to the right as a quick read on whether each team is also finding cheap excess value.</p>
        <div class="chart-shell">
          {leaderboard_svg(team_df)}
        </div>
      </section>

      <section class="section" id="scatter">
        <div class="section-head">
          <div>
            <div class="section-id">3. Cap Concentration vs. Team Value</div>
            <h3>High-value teams are not all built the same way</h3>
          </div>
        </div>
        <p>The scatter separates teams by how much of the cap sits in the top two contracts and whether the median roster slot still grades well. It is a quick way to isolate star-dependent builds from teams getting similar quality with a more distributed payroll.</p>
        <div class="chart-shell">
          {scatter_svg(team_df, thresholds['value_median'], thresholds['cap_concentration_median'])}
        </div>
      </section>

      <section class="section" id="tiers">
        <div class="section-head">
          <div>
            <div class="section-id">4. Roster Tier Stacked Bar by Team</div>
            <h3>Depth quality becomes visible when every roster is broken into the same value tiers</h3>
          </div>
        </div>
        <p>This view keeps the leaderboard order but replaces the single team score with a full roster composition read. Teams with a broader fair-to-strong middle look sturdier than clubs that rely on one or two acceptable contracts while the rest of the roster sits in the risk band.</p>
        <div class="chart-shell">
          {stacked_bar_svg(bundle['tier_stacked'])}
        </div>
      </section>

      <section class="section" id="hidden">
        <div class="section-head">
          <div>
            <div class="section-id">5. Hidden Value Talent by Team</div>
            <h3>Cheap surplus talent is still the fastest leverage story in the model</h3>
          </div>
        </div>
        <p>The dot plot isolates which teams are turning low-cost contracts into real value. Dot size adds roster size context so a team with the same hidden-value count but a smaller roster reads as a more concentrated efficiency win.</p>
        <div class="chart-shell">
          {hidden_value_svg(bundle['hidden_value'])}
        </div>
      </section>

      <section class="section" id="appendix">
        <div class="section-head">
          <div>
            <div class="section-id">6. Takeaways and QA appendix</div>
            <h3>What stands out in the fresh build, and where the old presentation layer drifts</h3>
          </div>
        </div>
        <ul>
          {''.join(f'<li>{esc(item)}</li>' for item in takeaways)}
        </ul>
        <div class="callout-row">
          <div class="callout">
            <strong>Fresh source-of-truth outputs</strong>
            Notebook-support CSVs were written into <code>data/doc2_roster_value/notebook/team_roster_grade_analysis_2026/</code> so the visual extracts stay separate from the saved Tableau layer.
          </div>
          <div class="callout">
            <strong>Saved Tableau comparison</strong>
            {'The saved Tableau layer materially matches the fresh calculation, so it is directionally consistent with the notebook.' if comparison_meta['material_match'] else 'The saved Tableau layer does not materially match the fresh calculation, so the notebook keeps the fresh ranking and records the drift below.'}
          </div>
        </div>
        <div style="margin-top:18px">
          {comparison_table_html(comparison_df)}
        </div>
      </section>
    </main>
  </div>
</body>
</html>
"""


def build_bundle() -> dict[str, Any]:
    inputs = load_inputs()
    return build_team_analysis(inputs)


def validate_bundle(bundle: dict[str, Any]) -> None:
    team_df = bundle["team_level"]
    tier_df = bundle["tier_stacked"]
    hidden_df = bundle["hidden_value"]
    scatter_df = bundle["scatter"]

    if len(team_df) != 15:
        raise ValueError(f"Expected 15 teams, found {len(team_df)}")

    ordered_names = team_df["team_name"].tolist()
    if hidden_df["team_name"].tolist() != ordered_names:
        raise ValueError("Hidden-value dataset order does not match team ranking order.")
    if scatter_df["team_name"].tolist() != ordered_names:
        raise ValueError("Scatter dataset order does not match team ranking order.")

    tier_totals = tier_df.groupby("team_name")["player_count"].sum().reindex(ordered_names)
    roster_sizes = team_df.set_index("team_name")["roster_size"].reindex(ordered_names)
    if not tier_totals.equals(roster_sizes):
        raise ValueError("Roster tier counts do not reconcile back to team roster sizes.")


def build() -> str:
    bundle = build_bundle()
    validate_bundle(bundle)
    write_outputs(bundle)
    return build_html(bundle)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_output = build()
    OUT_PATH.write_text(html_output, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote notebook datasets to {NOTEBOOK_DATA_DIR}")


if __name__ == "__main__":
    main()
