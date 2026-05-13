#!/usr/bin/env python3
"""Build a notebook-style Natasha Cloud case study HTML page.

The page is intentionally self-contained: all data is pulled from the
workspace's Doc 2 roster-value tables and rendered into one browser-openable
HTML file with inline CSS and SVG.
"""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "case-studies"
OUT_PATH = OUT_DIR / "natasha_cloud_case_study.html"

PLAYER_ID = "204333"
PLAYER_NAME = "Natasha Cloud"
TARGET_SEASON = 2026


def num(value):
    return pd.to_numeric(value, errors="coerce")


def fmt_currency(value: float | int | None, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if digits == 0:
        return f"${int(round(float(value))):,}"
    return f"${float(value):,.{digits}f}"


def fmt_salary_band(low: float | int | None, high: float | int | None) -> str:
    if low is None or high is None or pd.isna(low) or pd.isna(high):
        return "n/a"
    return f"${int(round(low)):,} - ${int(round(high)):,}"


def fmt_pct(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.{digits}f}%"


def fmt_num(value: float | int | None, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if digits == 0:
        return f"{int(round(float(value))):,}"
    return f"{float(value):,.{digits}f}"


def esc(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return html.escape(str(value))


def load_csv(path: Path, dtype=None) -> pd.DataFrame:
    return pd.read_csv(path, dtype=dtype)


def rank_percentile(series: pd.Series, value: float, higher_better: bool = True) -> float:
    clean = series.dropna()
    if clean.empty or pd.isna(value):
        return float("nan")
    pct = (clean.rank(pct=True, method="average") * 100).loc[clean.index[clean == value].tolist()]
    if len(pct):
        score = float(pct.iloc[0])
    else:
        # Fall back to a straightforward empirical percentile.
        if higher_better:
            score = float((clean <= value).mean() * 100)
        else:
            score = float((clean >= value).mean() * 100)
    return score if higher_better else 100.0 - score


def sparkline_svg(values: Sequence[float], width: int = 300, height: int = 96, color: str = "#f59e0b") -> str:
    clean = [float(v) for v in values if v is not None and not pd.isna(v)]
    if not clean:
        return f'<div class="spark-empty">No data</div>'
    pad_x = 14
    pad_y = 14
    inner_w = width - pad_x * 2
    inner_h = height - pad_y * 2
    min_v = min(clean)
    max_v = max(clean)
    if max_v == min_v:
        max_v = min_v + 1
    points = []
    for i, v in enumerate(clean):
        x = pad_x + (inner_w * (i / max(1, len(clean) - 1)))
        y = pad_y + inner_h - ((v - min_v) / (max_v - min_v) * inner_h)
        points.append((x, y))
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    bottom_y = pad_y + inner_h
    fill_path = path + f" L {points[-1][0]:.1f},{bottom_y:.1f} L {points[0][0]:.1f},{bottom_y:.1f} Z"
    grid_lines = []
    for frac in (0.25, 0.5, 0.75):
        y = pad_y + inner_h * frac
        grid_lines.append(f'<line x1="{pad_x}" y1="{y:.1f}" x2="{width - pad_x}" y2="{y:.1f}" class="spark-grid" />')
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{color}" stroke="rgba(255,255,255,.9)" stroke-width="1.2" />'
        for x, y in points
    )
    labels = "".join(
        f'<text x="{points[i][0]:.1f}" y="{height - 3}" text-anchor="middle" class="spark-label">{label}</text>'
        for i, label in enumerate(["2023", "2024", "2025"])
        if i < len(points)
    )
    if len(points) >= 4:
        labels += f'<text x="{points[-1][0]:.1f}" y="{height - 3}" text-anchor="middle" class="spark-label">PO</text>'
    last_value = clean[-1]
    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="Trend chart" class="sparkline">
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="{color}" stop-opacity="0.22"/>
          <stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      {''.join(grid_lines)}
      <path d="{fill_path}" fill="url(#spark-fill)" stroke="none"></path>
      <path d="{path}" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></path>
      {dots}
      <text x="{width - 12}" y="{pad_y + 10}" text-anchor="end" class="spark-value">{fmt_num(last_value, 1)}</text>
      {labels}
    </svg>
    """


def bar_row(label: str, value: float, max_value: float, suffix: str = "") -> str:
    pct = 0 if max_value == 0 or pd.isna(value) else min(max(float(value) / float(max_value), 0), 1)
    return f"""
    <div class="bar-row">
      <div class="bar-meta">
        <span class="bar-label">{esc(label)}</span>
        <span class="bar-value">{fmt_num(value, 1)}{suffix}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width:{pct * 100:.1f}%"></div>
      </div>
    </div>
    """


def scatter_svg(points: list[dict], highlight: dict, width: int = 820, height: int = 470) -> str:
    x_min, x_max = 20, 100
    y_min, y_max = 0, max(1400000, max((p["salary"] for p in points if not pd.isna(p["salary"])), default=0) * 1.05)
    pad_l, pad_r, pad_t, pad_b = 54, 18, 18, 52
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    def scale_x(v):
        return pad_l + (float(v) - x_min) / (x_max - x_min) * inner_w

    def scale_y(v):
        return pad_t + inner_h - (float(v) - y_min) / (y_max - y_min) * inner_h

    grid = []
    for xv in [30, 40, 50, 60, 70, 80, 90]:
        x = scale_x(xv)
        grid.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t + inner_h}" class="grid-line" />')
        grid.append(f'<text x="{x:.1f}" y="{height - 22}" text-anchor="middle" class="axis-label">{xv}</text>')
    for yv in [0, 250000, 500000, 750000, 1000000, 1250000, 1400000]:
        y = scale_y(yv)
        grid.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + inner_w}" y2="{y:.1f}" class="grid-line" />')
        label = "$0" if yv == 0 else f"${yv/1000000:.1f}M"
        grid.append(f'<text x="{pad_l - 10}" y="{y + 4:.1f}" text-anchor="end" class="axis-label">{label}</text>')

    color_map = {
        "Elite": "#22c55e",
        "Strong": "#38bdf8",
        "Fair": "#f59e0b",
        "Fragile": "#f97316",
        "Risk": "#f43f5e",
    }
    circles = []
    for p in points:
        if pd.isna(p["salary"]) or pd.isna(p["value"]):
            continue
        x = scale_x(p["value"])
        y = scale_y(p["salary"])
        color = color_map.get(p["label"], "#60a5fa")
        opacity = 0.28 if p.get("name") != highlight.get("name") else 1.0
        radius = 3.0 if p.get("name") != highlight.get("name") else 7.5
        stroke = "rgba(255,255,255,.85)" if p.get("name") == highlight.get("name") else "none"
        circles.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="1.5" />'
        )

    hx = scale_x(highlight["value"])
    hy = scale_y(highlight["salary"])
    band_y = scale_y(highlight["band_low"])
    band_y2 = scale_y(highlight["band_high"])
    return f"""
    <svg viewBox="0 0 {width} {height}" class="market-scatter" role="img" aria-label="Value versus salary scatter plot">
      {''.join(grid)}
      <line x1="{scale_x(60):.1f}" y1="{pad_t}" x2="{scale_x(60):.1f}" y2="{pad_t + inner_h}" class="ref-line" />
      <rect x="{pad_l}" y="{band_y2:.1f}" width="{inner_w}" height="{band_y - band_y2:.1f}" class="fair-band" />
      <text x="{pad_l + 10}" y="{band_y2 + 18:.1f}" class="band-label">Model fair band</text>
      <line x1="{pad_l}" y1="{hy:.1f}" x2="{hx - 18:.1f}" y2="{hy:.1f}" class="leader-line" />
      <circle cx="{hx:.1f}" cy="{hy:.1f}" r="8.5" fill="#f59e0b" stroke="#ffffff" stroke-width="1.6" />
      <circle cx="{hx:.1f}" cy="{hy:.1f}" r="18" fill="none" stroke="#f59e0b" stroke-width="1.2" stroke-opacity=".45" />
      <text x="{hx + 12:.1f}" y="{hy - 12:.1f}" class="highlight-label">{esc(highlight['name'])}</text>
      <text x="{hx + 12:.1f}" y="{hy + 4:.1f}" class="highlight-sub">{esc(highlight['sub'])}</text>
      {''.join(circles)}
    </svg>
    """


def table_html(headers: Sequence[str], rows: Sequence[Sequence[str]], table_class: str = "") -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return f"""
    <div class="table-wrap {table_class}">
      <table>
        <thead><tr>{head}</tr></thead>
        <tbody>
          {''.join(body)}
        </tbody>
      </table>
    </div>
    """


def percent_style(value: float) -> str:
    value = max(0, min(100, float(value)))
    hue = 34 if value >= 70 else 195 if value >= 55 else 15
    return f"background: linear-gradient(90deg, hsla({hue}, 95%, 58%, .95), hsla({hue}, 95%, 40%, .9)); width: {value:.1f}%"


def build() -> str:
    season_stats = load_csv(ROOT / "data/doc2_roster_value/tables/player_season_stats/player_season_stats.csv")
    value_scores = load_csv(ROOT / "data/doc2_roster_value/tables/value_scores/value_scores.csv", dtype=str)
    comparable_players = load_csv(ROOT / "data/doc2_roster_value/tables/comparable_players/comparable_players.csv", dtype=str)
    player_archetypes = load_csv(ROOT / "data/doc2_roster_value/tables/player_archetypes/player_archetypes.csv", dtype=str)
    onoff = load_csv(ROOT / "data/doc2_roster_value/tables/onoff_metrics/onoff_metrics.csv", dtype=str)
    contracts = load_csv(ROOT / "data/doc2_roster_value/tables/contracts_2026/contracts_2026.csv", dtype=str)
    salary_hist = load_csv(ROOT / "2024_2026_salaries_wnba_all_players.csv", dtype=str)

    # Numeric conversions for the columns we use.
    for df, cols in [
        (value_scores, ["salary", "cap_hit", "historical_salary_latest", "historical_salary_median", "historical_salary_mean", "historical_salary_min", "historical_salary_max", "recommended_salary_low", "recommended_salary_high", "salary_gap", "salary_gap_pct", "market_discount_pct", "production_score", "salary_efficiency_score", "scarcity_score", "playoff_score", "onoff_score", "value_score", "comp_count"]),
        (player_archetypes, ["salary", "cap_hit", "salary_as_pct_cap", "usage", "ts_pct", "mpg", "tov_pct", "ast_pct", "reb_pct", "stl_pct", "blk_pct", "three_par", "rim_rate", "playoff_games_career", "playoff_minutes_career", "high_leverage_experience_score", "onoff_impact_score", "on_minutes", "off_minutes"]),
        (season_stats, ["season", "games_played", "minutes", "mpg", "points", "ppg", "rebounds", "rpg", "assists", "apg", "steals", "spg", "blocks", "bpg", "turnovers", "tov_pg", "fgm", "fga", "fg_pct", "three_pm", "three_pa", "three_pct", "ftm", "fta", "ft_pct"]),
        (onoff, ["season", "on_minutes", "off_minutes", "pts_per100_poss_on", "pts_per100_poss_off", "pts_per100_poss_on_off", "assist_points_per100_poss_on_off", "fta_per100_poss_on_off", "turnovers_per100_poss_on_off", "assists_per100_poss_on_off", "ts_pct_on_off", "efg_pct_on_off", "usage_on_off", "on_net_rating", "off_net_rating", "net_rating_diff", "onoff_impact_score"]),
        (contracts, ["season", "salary", "cap_hit", "salary_as_pct_cap", "pct_team"]),
        (salary_hist, ["season", "season_plusone_salary_usd", "games_played", "minutes_total", "PER", "win_shares", "player_off_rtg", "player_def_rtg"]),
    ]:
        for col in cols:
            if col in df.columns:
                df[col] = num(df[col])

    if "ts_pct" not in season_stats.columns:
        season_stats["ts_pct"] = season_stats.apply(
            lambda r: r["points"] / (2 * (r["fga"] + 0.44 * r["fta"]))
            if pd.notna(r.get("points")) and pd.notna(r.get("fga")) and pd.notna(r.get("fta")) and (r["fga"] + 0.44 * r["fta"]) > 0
            else float("nan"),
            axis=1,
        )

    cloud_stats = season_stats[(season_stats["player_id"] == int(PLAYER_ID))].sort_values(["season", "season_type"]).copy()
    cloud_regular = cloud_stats[(cloud_stats["season"] == 2025) & (cloud_stats["season_type"] == "Regular Season")].iloc[0]
    cloud_playoffs = cloud_stats[(cloud_stats["season"] == 2025) & (cloud_stats["season_type"] == "Playoffs")].iloc[0]
    cloud_value = value_scores[value_scores["player_id"] == PLAYER_ID].iloc[0]
    cloud_arch = player_archetypes[player_archetypes["player_id"] == PLAYER_ID].iloc[0]
    cloud_contract = contracts[(contracts["player_id"] == PLAYER_ID) | (contracts["player_name"] == PLAYER_NAME)].iloc[0]
    cloud_onoff = onoff[(onoff["player_id"] == PLAYER_ID)].sort_values(["season", "season_type"])
    cloud_history = salary_hist[salary_hist["player_name"] == PLAYER_NAME].sort_values("season")
    cloud_salary_2025 = float(
        cloud_history.loc[cloud_history["season"] == 2024, "season_plusone_salary_usd"].iloc[0]
    )
    cloud_salary_2026 = float(
        cloud_history.loc[cloud_history["season"] == 2025, "season_plusone_salary_usd"].iloc[0]
    )
    cloud_team_name = cloud_contract.get("team_name") or cloud_value.get("team_name") or "Team TBD"
    cloud_current_salary = cloud_contract.get("salary")
    if pd.isna(cloud_current_salary):
        cloud_current_salary = cloud_value.get("salary")
    if pd.isna(cloud_current_salary):
        cloud_current_salary = cloud_salary_2026
    cloud_salary_reference_copy = "Canonical 2026 contract reference in current Doc 2 tables."
    if pd.notna(cloud_contract.get("notes")) and "season_plusone reference" in str(cloud_contract.get("notes")):
        cloud_salary_reference_copy = "Canonical 2026 contract row reconciled from the latest transaction log plus salary-history fallback."

    # League percentile profile for 2025 regular season, qualified by minutes.
    reg_2025 = season_stats[(season_stats["season"] == 2025) & (season_stats["season_type"] == "Regular Season") & (season_stats["minutes"] >= 300)].copy()
    pct_metrics = [
        ("ppg", "Scoring"),
        ("apg", "Playmaking"),
        ("spg", "Stocks"),
        ("fg_pct", "Efficiency"),
        ("three_pct", "Three-point"),
        ("ft_pct", "Free throws"),
        ("tov_pg", "Turnovers"),
        ("mpg", "Minutes"),
    ]
    percentile_rows = []
    percentile_values = {}
    for metric, _label in pct_metrics:
        if metric == "tov_pg":
            rank = reg_2025[metric].rank(pct=True, method="average")
            cloud_rank = float(rank.loc[reg_2025["player_id"] == int(PLAYER_ID)].iloc[0] * 100)
            score = 100.0 - cloud_rank
        else:
            rank = reg_2025[metric].rank(pct=True, method="average")
            score = float(rank.loc[reg_2025["player_id"] == int(PLAYER_ID)].iloc[0] * 100)
        percentile_values[metric] = score
        percentile_rows.append((metric, score))

    # Framework demand score: analyst judgment anchored in the doc's six inputs.
    production_strength = (percentile_values["apg"] + percentile_values["spg"] + percentile_values["fg_pct"] + percentile_values["three_pct"] + percentile_values["tov_pg"]) / 5
    demand_score = round(
        0.25 * 88
        + 0.20 * 82
        + 0.20 * production_strength
        + 0.15 * 68
        + 0.10 * 64
        + 0.10 * 58
    )
    demand_score = max(0, min(100, demand_score))

    # Similarity comps for the Cloud row.
    cloud_comps = (
        comparable_players[(comparable_players["player_id"] == PLAYER_ID) & (comparable_players["season"] == "2026")]
        .drop_duplicates("comparable_player_name")
        .sort_values("comp_rank")
        .head(3)
        .copy()
    )
    salary_lookup = {}
    for _, row in contracts.iterrows():
        if pd.notna(row.get("player_name")):
            salary_lookup.setdefault(row["player_name"], row)
    hist_lookup = {}
    for name, group in salary_hist.groupby("player_name"):
        numeric = group.dropna(subset=["season_plusone_salary_usd"]).sort_values("season")
        if not numeric.empty:
            hist_lookup[name] = numeric.iloc[-1]

    comp_rows = []
    for _, row in cloud_comps.iterrows():
        name = row["comparable_player_name"]
        contract_row = salary_lookup.get(name)
        hist_row = hist_lookup.get(name)
        salary = None
        salary_source = "model"
        if contract_row is not None and pd.notna(contract_row.get("salary")):
            salary = float(contract_row["salary"])
            salary_source = "2026 contract"
        elif hist_row is not None and pd.notna(hist_row.get("season_plusone_salary_usd")):
            salary = float(hist_row["season_plusone_salary_usd"])
            salary_source = f"{int(hist_row['season'])} season+1"
        comp_rows.append(
            {
                "rank": int(float(row["comp_rank"])),
                "name": name,
                "team": row["comparable_team_name"],
                "role": row["comparable_role_band"],
                "salary": salary,
                "salary_source": salary_source if salary is not None else "reserved / unavailable",
                "similarity": float(row["similarity_score"]),
                "basis": row["comp_basis"],
                "salary_gap": row.get("salary_gap", ""),
                "salary_gap_pct": row.get("salary_gap_pct", ""),
            }
        )

    # Add a light market peer section from the salary history bundle.
    season_market = (
        salary_hist.dropna(subset=["season_plusone_salary_usd"])
        .groupby("season")["season_plusone_salary_usd"]
        .agg(["count", "mean", "median", "min", "max"])
        .reset_index()
        .sort_values("season")
    )

    # Scatter data from value scores. Use the latest salary reference as the y-axis.
    scatter_points = []
    for _, row in value_scores.iterrows():
        salary = row.get("salary")
        if pd.isna(salary):
            salary = row.get("historical_salary_latest")
        value = row.get("value_score")
        if pd.isna(salary) or pd.isna(value):
            continue
        label = row.get("value_label")
        scatter_points.append(
            {
                "name": row.get("player_name") if pd.notna(row.get("player_name")) else row.get("player_id"),
                "salary": float(salary),
                "value": float(value),
                "label": str(label) if pd.notna(label) else "Risk",
            }
        )

    cloud_point = {
        "name": PLAYER_NAME,
        "salary": float(cloud_current_salary),
        "value": float(cloud_value["value_score"]),
        "label": str(cloud_value["value_label"]),
        "band_low": float(cloud_value["recommended_salary_low"]),
        "band_high": float(cloud_value["recommended_salary_high"]),
        "sub": f"Model value score {fmt_num(cloud_value['value_score'], 2)} | current 2026 salary {fmt_currency(cloud_current_salary)}",
    }

    # Section fragments.
    season_rows = []
    for _, row in cloud_stats.iterrows():
        if row["season_type"] == "Regular Season":
            season_tag = f"{int(row['season'])}"
        else:
            season_tag = f"{int(row['season'])} PO"
        season_rows.append(
            [
                esc(season_tag),
                esc(row["season_type"]),
                f"{int(row['games_played'])}",
                fmt_num(row["minutes"], 0),
                fmt_num(row["mpg"], 1),
                fmt_num(row["ppg"], 1),
                fmt_num(row["apg"], 1),
                fmt_num(row["rpg"], 1),
                fmt_num(row["spg"], 1),
                fmt_pct(row["fg_pct"], 1),
                fmt_pct(row["three_pct"], 1),
                fmt_pct(row["ft_pct"], 1),
            ]
        )

    comp_table_rows = []
    for row in comp_rows:
        salary_text = fmt_currency(row["salary"]) if row["salary"] is not None else "n/a"
        comp_table_rows.append(
            [
                f'<span class="comp-rank">#{row["rank"]}</span>',
                esc(row["name"]),
                esc(row["team"]),
                esc(row["role"]),
                esc(row["basis"]),
                f"{row['similarity']:.2f}",
                salary_text,
                esc(row["salary_source"]),
            ]
        )

    percentile_cards = []
    percentile_labels = {
        "ppg": "Scoring",
        "apg": "Playmaking",
        "spg": "Steals",
        "fg_pct": "FG%",
        "three_pct": "3PT%",
        "ft_pct": "FT%",
        "tov_pg": "Turnover control",
        "mpg": "Minutes",
    }
    for metric, label in pct_metrics:
        score = percentile_values[metric]
        percentile_cards.append(
            f"""
            <div class="percentile-card">
              <div class="percentile-head">
                <span>{esc(percentile_labels[metric])}</span>
                <strong>{score:.0f}th pct</strong>
              </div>
              <div class="bar-track percentile-track">
                <div class="bar-fill" style="{percent_style(score)}"></div>
              </div>
            </div>
            """
        )

    season_spark_cards = []
    spark_metrics = [
        ("ppg", "Points per game", "#f59e0b"),
        ("apg", "Assists per game", "#38bdf8"),
        ("mpg", "Minutes per game", "#22c55e"),
        ("ts_pct", "True shooting", "#a855f7"),
    ]
    season_spark_source = cloud_stats[cloud_stats["season_type"] == "Regular Season"].sort_values("season")
    for metric, title, color in spark_metrics:
        season_spark_cards.append(
            f"""
            <article class="mini-card">
              <div class="mini-kicker">{esc(title)}</div>
              <div class="mini-value">{fmt_pct(season_spark_source.iloc[-1][metric], 1) if metric == "ts_pct" else fmt_num(season_spark_source.iloc[-1][metric], 1)}</div>
              <div class="mini-sub">Latest regular season value</div>
              {sparkline_svg(list(season_spark_source[metric]), color=color)}
            </article>
            """
        )

    demand_bullets = [
        "Veteran lead-guard stability and half-court organization remain scarce.",
        "Point-of-attack defense, playmaking, and low-mistake decision-making still travel well into the playoffs.",
        "The framework model reads her as a premium starter profile, but not as a max-tier production bet.",
        "Expansion and contender builds still need a connector who can calm a young or unstable backcourt.",
    ]
    demand_cards = [
        ("Role scarcity", "High"),
        ("Team fit", "High"),
        ("Production strength", f"{production_strength:.0f}"),
        ("Playoff utility", "Solid"),
        ("Market activity", f"{len(comp_rows)} model comps"),
        ("Risk adjustment", "Moderate"),
    ]

    market_rows = [
        [
            esc(int(row["season"])),
            f"{int(row['count'])}",
            fmt_currency(row["mean"]),
            fmt_currency(row["median"]),
            fmt_currency(row["min"]),
            fmt_currency(row["max"]),
        ]
        for _, row in season_market.iterrows()
    ]

    # Salary bands are intentionally framed as a range ladder, not a final market verdict.
    band_rows = [
        ("Conservative", 235875, 275000, "A floor for cautious teams."),
        ("Market fair", 275000, 319125, "Closest to the model's recommended band."),
        ("Premium fit", 320000, 400000, "For teams paying for guard stability and playoff calm."),
        ("Stretch / premium", 400000, 555000, "Where the 2026 salary reference lives."),
    ]

    band_cards = []
    for label, low, high, note in band_rows:
        band_cards.append(
            f"""
            <div class="band-card">
              <div class="band-label">{esc(label)}</div>
              <div class="band-range">{fmt_currency(low)} - {fmt_currency(high)}</div>
              <div class="band-note">{esc(note)}</div>
            </div>
            """
        )

    current_ref_marker = f"""
    <div class="range-marker">
      <span class="marker-dot"></span>
      <span>Current 2026 salary reference {fmt_currency(cloud_current_salary)}</span>
    </div>
    """

    cloud_salary_lines = "".join(
        bar_row(label, salary, max(season_market["max"].max(), cloud_current_salary))
        for label, salary in [
            ("2025 salary reference", cloud_salary_2025),
            ("2026 salary reference", cloud_salary_2026),
        ]
    )

    market_scatter = scatter_svg(
        scatter_points,
        cloud_point,
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Natasha Cloud Case Study | WNBA Roster Value Framework</title>
  <style>
    :root {{
      --bg: #07111f;
      --bg-2: #0c1727;
      --panel: rgba(10, 20, 34, 0.88);
      --panel-2: rgba(12, 24, 39, 0.95);
      --line: rgba(148, 163, 184, 0.18);
      --text: #e5eefb;
      --muted: #93a4bc;
      --soft: #c5d0e2;
      --gold: #f59e0b;
      --gold-2: #fbbf24;
      --cyan: #38bdf8;
      --teal: #22c55e;
      --rose: #fb7185;
      --violet: #a855f7;
      --shadow: 0 20px 70px rgba(0, 0, 0, 0.28);
      --radius: 18px;
      --radius-sm: 12px;
      --content: 1240px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 14% 10%, rgba(245, 158, 11, 0.14), transparent 28%),
        radial-gradient(circle at 88% 12%, rgba(56, 189, 248, 0.11), transparent 22%),
        linear-gradient(180deg, #050b14 0%, var(--bg) 18%, #08111d 100%);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .page {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 24px 18px 48px;
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      gap: 24px;
    }}
    .sidebar {{
      position: sticky;
      top: 18px;
      align-self: start;
      background: linear-gradient(180deg, rgba(9, 17, 29, 0.98), rgba(12, 20, 34, 0.92));
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px 16px;
      box-shadow: var(--shadow);
    }}
    .brand {{
      display: flex;
      gap: 12px;
      align-items: center;
      margin-bottom: 18px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    .brand-mark {{
      width: 44px; height: 44px; border-radius: 14px;
      background: linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(56, 189, 248, 0.18));
      display: grid; place-items: center;
      color: var(--gold);
      border: 1px solid rgba(245, 158, 11, 0.22);
      font-weight: 700;
    }}
    .brand-title {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 1.35rem;
      line-height: 1.05;
    }}
    .brand-sub {{
      color: var(--muted);
      font-size: 0.84rem;
      margin-top: 4px;
    }}
    .sidebar-note {{
      color: var(--soft);
      font-size: 0.88rem;
      padding: 14px 12px;
      border-radius: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(148, 163, 184, 0.12);
      margin-bottom: 16px;
    }}
    .nav {{
      display: grid;
      gap: 6px;
      margin-bottom: 16px;
    }}
    .nav a {{
      padding: 10px 12px;
      border-radius: 12px;
      color: var(--soft);
      background: rgba(255,255,255,0.02);
      border: 1px solid transparent;
      transition: all 160ms ease;
    }}
    .nav a:hover {{
      transform: translateX(2px);
      border-color: rgba(245, 158, 11, 0.25);
      color: white;
      background: rgba(245, 158, 11, 0.06);
    }}
    .nav .small {{
      display: block;
      font-size: 0.74rem;
      color: var(--muted);
      margin-top: 2px;
    }}
    .sidebar-footer {{
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .content {{
      display: grid;
      gap: 18px;
    }}
    .hero, .section, .callout {{
      background: linear-gradient(180deg, rgba(11, 18, 30, 0.9), rgba(12, 20, 34, 0.82));
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 24px;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute; inset: auto -90px -90px auto;
      width: 280px; height: 280px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(245, 158, 11, 0.18), transparent 65%);
      pointer-events: none;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.22em;
      color: var(--gold-2);
      font-size: 0.72rem;
      margin-bottom: 12px;
    }}
    h1, h2, h3 {{
      font-family: Georgia, "Times New Roman", serif;
      font-weight: 700;
      line-height: 1.05;
      margin: 0;
    }}
    h1 {{
      font-size: clamp(2.5rem, 5vw, 5rem);
      letter-spacing: -0.03em;
    }}
    .hero-title-row {{
      display: flex;
      align-items: end;
      gap: 18px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }}
    .hero-chip {{
      font-size: 0.84rem;
      color: white;
      background: rgba(245, 158, 11, 0.11);
      border: 1px solid rgba(245, 158, 11, 0.28);
      padding: 8px 12px;
      border-radius: 999px;
    }}
    .thesis {{
      max-width: 980px;
      font-size: 1.05rem;
      color: var(--soft);
      margin-bottom: 18px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }}
    .stat-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid rgba(148, 163, 184, 0.18);
      background: rgba(255,255,255,0.03);
      min-height: 108px;
    }}
    .stat-label {{
      text-transform: uppercase;
      letter-spacing: 0.15em;
      font-size: 0.7rem;
      color: var(--muted);
      margin-bottom: 8px;
    }}
    .stat-value {{
      font-size: clamp(1.55rem, 2vw, 2.2rem);
      line-height: 1.1;
      margin-bottom: 6px;
    }}
    .stat-copy {{
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .section {{
      padding: 22px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }}
    .section-head p {{
      color: var(--muted);
      margin: 0;
      max-width: 820px;
    }}
    .section-id {{
      color: var(--gold-2);
      text-transform: uppercase;
      letter-spacing: 0.2em;
      font-size: 0.71rem;
      margin-bottom: 8px;
    }}
    .framework-grid {{
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 14px;
    }}
    .thread-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .thread-card {{
      border-radius: 18px;
      padding: 16px;
      border: 1px solid rgba(148, 163, 184, 0.15);
      background: rgba(255,255,255,0.03);
      min-height: 150px;
    }}
    .thread-num {{
      color: var(--gold);
      font-size: 0.76rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }}
    .thread-card h3 {{
      font-size: 1.35rem;
      margin-bottom: 10px;
    }}
    .thread-card p {{
      color: var(--soft);
      margin: 0;
    }}
    .criteria-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    .criteria-card {{
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(148, 163, 184, 0.15);
    }}
    .criteria-card strong {{
      display: block;
      margin-bottom: 4px;
    }}
    .criteria-card span {{
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .formula-strip {{
      display: grid;
      grid-template-columns: 25% 20% 15% 15% 10% 10% 5%;
      gap: 4px;
      border-radius: 18px;
      overflow: hidden;
      border: 1px solid rgba(245, 158, 11, 0.22);
    }}
    .formula-seg {{
      padding: 16px 12px;
      min-height: 100px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .formula-seg .pct {{
      font-size: 1.25rem;
      font-weight: 700;
    }}
    .formula-seg .label {{
      font-size: 0.84rem;
      color: rgba(255,255,255,0.94);
    }}
    .orange {{ background: linear-gradient(180deg, rgba(194, 98, 12, 0.92), rgba(124, 45, 18, 0.92)); }}
    .amber {{ background: linear-gradient(180deg, rgba(180, 83, 9, 0.88), rgba(99, 43, 13, 0.95)); }}
    .burnt {{ background: linear-gradient(180deg, rgba(120, 53, 15, 0.9), rgba(75, 31, 11, 0.95)); }}
    .slate {{ background: linear-gradient(180deg, rgba(51, 65, 85, 0.9), rgba(15, 23, 42, 0.95)); }}
    .violet {{ background: linear-gradient(180deg, rgba(88, 28, 135, 0.88), rgba(39, 10, 77, 0.95)); }}
    .green {{ background: linear-gradient(180deg, rgba(22, 101, 52, 0.88), rgba(6, 78, 59, 0.95)); }}
    .navy {{ background: linear-gradient(180deg, rgba(30, 41, 59, 0.95), rgba(15, 23, 42, 0.98)); }}
    .profile-grid {{
      display: grid;
      grid-template-columns: 0.9fr 1.35fr 0.85fr;
      gap: 14px;
    }}
    .profile-card, .panel {{
      border-radius: 18px;
      border: 1px solid rgba(148, 163, 184, 0.15);
      background: rgba(255,255,255,0.03);
      padding: 16px;
    }}
    .profile-face {{
      display: flex;
      gap: 14px;
      align-items: center;
      margin-bottom: 14px;
    }}
    .face-badge {{
      width: 78px;
      height: 78px;
      border-radius: 24px;
      background: radial-gradient(circle at 30% 25%, rgba(245, 158, 11, 0.34), rgba(56, 189, 248, 0.12) 60%, rgba(255,255,255,0.02) 100%);
      border: 1px solid rgba(245, 158, 11, 0.2);
      display: grid;
      place-items: center;
      font-family: Georgia, serif;
      font-size: 2rem;
      font-weight: 700;
      color: var(--gold);
    }}
    .profile-name {{
      font-size: 1.55rem;
      margin-bottom: 4px;
    }}
    .profile-role {{
      color: var(--soft);
      font-size: 0.95rem;
    }}
    .profile-meta {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 12px;
      margin-top: 10px;
    }}
    .meta-row {{
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 8px 0;
      border-top: 1px solid rgba(148, 163, 184, 0.12);
    }}
    .meta-row strong {{
      font-size: 0.84rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 600;
    }}
    .meta-row span {{
      color: var(--text);
      font-size: 0.95rem;
    }}
    .sparkline {{
      width: 100%;
      display: block;
      overflow: visible;
    }}
    .spark-grid {{
      stroke: rgba(148, 163, 184, 0.15);
      stroke-width: 1;
    }}
    .spark-label, .spark-value, .axis-label, .band-label, .highlight-label, .highlight-sub {{
      fill: var(--soft);
      font-size: 10px;
      letter-spacing: 0.02em;
    }}
    .spark-value {{
      font-size: 14px;
      font-weight: 700;
      fill: white;
    }}
    .mini-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }}
    .mini-card {{
      border-radius: 16px;
      padding: 14px;
      border: 1px solid rgba(148, 163, 184, 0.15);
      background: rgba(255,255,255,0.03);
    }}
    .mini-kicker {{
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.16em;
      margin-bottom: 8px;
    }}
    .mini-value {{
      font-size: 1.8rem;
      margin-bottom: 2px;
    }}
    .mini-sub {{
      color: var(--muted);
      font-size: 0.88rem;
      margin-bottom: 8px;
    }}
    .percentile-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .percentile-card {{
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(148, 163, 184, 0.15);
    }}
    .percentile-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
      align-items: baseline;
    }}
    .percentile-head span {{
      color: var(--soft);
    }}
    .percentile-head strong {{
      color: white;
      font-size: 0.95rem;
    }}
    .bar-track {{
      width: 100%;
      height: 12px;
      background: rgba(255,255,255,0.06);
      border-radius: 999px;
      overflow: hidden;
      position: relative;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: inherit;
    }}
    .percentile-track {{
      height: 10px;
    }}
    .bar-row + .bar-row {{
      margin-top: 10px;
    }}
    .bar-meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
      color: var(--soft);
      font-size: 0.9rem;
    }}
    .bar-label {{ color: var(--soft); }}
    .bar-value {{ color: white; font-weight: 600; }}
    .section-grid {{
      display: grid;
      gap: 12px;
    }}
    .demand-layout {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 14px;
    }}
    .score-ring {{
      width: 182px;
      height: 182px;
      border-radius: 50%;
      margin: 0 auto 12px;
      display: grid;
      place-items: center;
      background: conic-gradient(var(--gold) 0 {demand_score}%, rgba(148, 163, 184, 0.18) {demand_score}% 100%);
      position: relative;
    }}
    .score-ring::after {{
      content: "";
      position: absolute;
      inset: 14px;
      border-radius: 50%;
      background: linear-gradient(180deg, rgba(7, 17, 31, 0.96), rgba(12, 20, 34, 0.96));
      border: 1px solid rgba(148, 163, 184, 0.15);
    }}
    .score-ring .score {{
      position: relative;
      z-index: 1;
      text-align: center;
    }}
    .score-ring .score strong {{
      display: block;
      font-size: 2.35rem;
      color: white;
    }}
    .score-ring .score span {{
      display: block;
      color: var(--muted);
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}
    .demand-list {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}
    .bullet {{
      display: flex;
      gap: 10px;
      align-items: start;
      color: var(--soft);
    }}
    .bullet i {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--gold);
      flex: 0 0 10px;
      margin-top: 7px;
    }}
    .range-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .band-card {{
      padding: 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(148, 163, 184, 0.15);
    }}
    .band-label {{
      color: var(--gold-2);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      font-size: 0.72rem;
      margin-bottom: 8px;
    }}
    .band-range {{
      font-size: 1.45rem;
      margin-bottom: 6px;
      color: white;
    }}
    .band-note {{
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .range-ruler {{
      margin-top: 14px;
      height: 14px;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(245, 158, 11, 0.2), rgba(56, 189, 248, 0.22), rgba(34, 197, 94, 0.2));
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(148, 163, 184, 0.16);
    }}
    .range-ruler::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, rgba(7, 17, 31, 0.0), rgba(7, 17, 31, 0.28), rgba(7, 17, 31, 0.0));
      opacity: .6;
    }}
    .range-marker {{
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--soft);
      font-size: 0.9rem;
    }}
    .marker-dot {{
      width: 11px;
      height: 11px;
      border-radius: 50%;
      background: var(--rose);
      box-shadow: 0 0 0 4px rgba(251, 113, 133, 0.16);
      display: inline-block;
    }}
    .table-wrap {{
      overflow: auto;
      border-radius: 16px;
      border: 1px solid rgba(148, 163, 184, 0.15);
      background: rgba(255,255,255,0.03);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 820px;
    }}
    th, td {{
      text-align: left;
      padding: 12px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      vertical-align: top;
      color: var(--soft);
      font-size: 0.92rem;
    }}
    th {{
      color: white;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.72rem;
      position: sticky;
      top: 0;
      background: rgba(12, 20, 34, 0.96);
      z-index: 1;
    }}
    tr:last-child td {{ border-bottom: none; }}
    .comp-rank {{
      color: var(--gold-2);
      font-weight: 700;
    }}
    .market-grid {{
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 14px;
    }}
    .market-scatter {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .grid-line {{
      stroke: rgba(148, 163, 184, 0.12);
      stroke-width: 1;
    }}
    .ref-line {{
      stroke: rgba(245, 158, 11, 0.45);
      stroke-dasharray: 5 4;
      stroke-width: 1.3;
    }}
    .fair-band {{
      fill: rgba(56, 189, 248, 0.08);
    }}
    .leader-line {{
      stroke: rgba(245, 158, 11, 0.6);
      stroke-width: 1.2;
    }}
    .highlight-label {{
      fill: white;
      font-size: 12px;
      font-weight: 700;
    }}
    .highlight-sub {{
      fill: var(--muted);
      font-size: 10.5px;
    }}
    .axis-label, .band-label {{
      fill: var(--muted);
      font-size: 10px;
    }}
    .foot {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .callout {{
      padding: 18px 20px;
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 14px;
      align-items: center;
    }}
    .callout h3 {{
      font-size: 1.7rem;
      margin-bottom: 6px;
    }}
    .callout p {{
      margin: 0;
      color: var(--soft);
    }}
    .callout-badge {{
      border-radius: 18px;
      padding: 18px;
      text-align: center;
      background: linear-gradient(180deg, rgba(245, 158, 11, 0.12), rgba(56, 189, 248, 0.06));
      border: 1px solid rgba(245, 158, 11, 0.25);
    }}
    .callout-badge .big {{
      display: block;
      color: var(--gold-2);
      font-size: 1.9rem;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .callout-badge .small {{
      color: var(--soft);
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
    }}
    .footer {{
      color: var(--muted);
      font-size: 0.82rem;
      text-align: center;
      padding: 10px 0 0;
    }}
    @media (max-width: 1100px) {{
      .page {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
      }}
      .profile-grid, .framework-grid, .demand-layout, .market-grid, .callout {{
        grid-template-columns: 1fr;
      }}
      .hero-grid, .mini-grid, .criteria-grid, .range-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .thread-grid {{
        grid-template-columns: 1fr;
      }}
      .formula-strip {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}
    @media (max-width: 720px) {{
      .page {{
        padding: 14px 12px 28px;
      }}
      .hero, .section, .sidebar, .callout {{
        border-radius: 18px;
      }}
      .hero-grid, .mini-grid, .criteria-grid, .range-grid {{
        grid-template-columns: 1fr;
      }}
      .formula-strip {{
        grid-template-columns: 1fr;
      }}
      .profile-meta {{
        grid-template-columns: 1fr;
      }}
      table {{
        min-width: 760px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">NC</div>
        <div>
          <div class="brand-title">Natasha Cloud</div>
          <div class="brand-sub">WNBA roster value case study</div>
        </div>
      </div>
      <div class="sidebar-note">
        Built from the stable Doc 2 foundation first. The on/off branch stays clearly marked as provisional where the workspace only has partial coverage.
      </div>
      <nav class="nav">
        <a href="#overview">Overview <span class="small">Core question and thesis</span></a>
        <a href="#framework">Framework spine <span class="small">Threads, criteria, formula</span></a>
        <a href="#profile">Cloud profile <span class="small">Production, trend, utility</span></a>
        <a href="#demand">Demand and fit <span class="small">Scarcity, demand score, risk</span></a>
        <a href="#comparables">Comparable contracts <span class="small">Model comps and salary peers</span></a>
        <a href="#range">Fair salary range <span class="small">Model band and current reference</span></a>
        <a href="#market">Market structure <span class="small">Scatter and market shift</span></a>
        <a href="#takeaway">Takeaway <span class="small">Interpretation and next steps</span></a>
      </nav>
      <div class="sidebar-footer">
        <strong style="color:white;">Sources</strong><br />
        Doc 2 tables, salary history bundle, and pbpstats on/off outputs. All values shown are rendered from local workspace files.
      </div>
    </aside>

    <main class="content">
      <section class="hero" id="overview">
        <div class="eyebrow">WNBA 2026 roster value framework</div>
        <div class="hero-title-row">
          <h1>Natasha Cloud<br />Case Study</h1>
          <span class="hero-chip">Fair salary range + market demand + role scarcity</span>
        </div>
        <div class="thesis">
          Natasha Cloud profiles as a veteran organizer whose value is driven by playmaking stability, defensive versatility, and playoff utility. The framework model places her in a premium-starter band, while her 2026 {esc(cloud_team_name)} salary reference sits above the model's recommended range.
        </div>
        <div class="hero-grid">
          <div class="stat-card">
            <div class="stat-label">Model fair range</div>
            <div class="stat-value">{fmt_salary_band(cloud_value['recommended_salary_low'], cloud_value['recommended_salary_high'])}</div>
            <div class="stat-copy">Doc 2 value-scores output for the Cloud row.</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Current 2026 salary</div>
            <div class="stat-value">{fmt_currency(cloud_current_salary)}</div>
            <div class="stat-copy">{esc(cloud_salary_reference_copy)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Framework demand score</div>
            <div class="stat-value">{demand_score}/100</div>
            <div class="stat-copy">Analyst score using the doc's six-input demand rubric.</div>
          </div>
        </div>
      </section>

      <section class="section" id="framework">
        <div class="section-head">
          <div>
            <div class="section-id">1. Framework spine</div>
            <h2>Use the same story architecture as the roster-value framework.</h2>
          </div>
          <p>
            The case study mirrors the doc and diagram: core question first, then the four evaluation threads, the six player criteria, the weighted value score, and the roster-grade lens.
          </p>
        </div>
        <div class="framework-grid">
          <div class="thread-grid">
            <div class="thread-card">
              <div class="thread-num">Thread 1</div>
              <h3>Market Reset Value</h3>
              <p>Is Cloud priced below the new market, or is the current reference salary carrying a premium beyond the model band?</p>
            </div>
            <div class="thread-card">
              <div class="thread-num">Thread 2</div>
              <h3>Role Scarcity</h3>
              <p>How rare is a veteran lead guard who can organize offense, defend the point of attack, and keep playoff mistakes low?</p>
            </div>
            <div class="thread-card">
              <div class="thread-num">Thread 3</div>
              <h3>Roster Construction Fit</h3>
              <p>Which teams gain the most when a backcourt needs a stabilizer, connector, and decision-maker rather than a high-usage scorer?</p>
            </div>
            <div class="thread-card">
              <div class="thread-num">Thread 4</div>
              <h3>Pricing-Out Risk</h3>
              <p>Did the 2026 cap reset price out some veteran guard profiles, or did it simply reveal how teams pay for stability?</p>
            </div>
          </div>
          <div class="panel">
            <div class="section-id">6 player criteria</div>
            <div class="criteria-grid">
              <div class="criteria-card"><strong>Below-market salary</strong><span>Model range or actual salary gap to fair comp band.</span></div>
              <div class="criteria-card"><strong>Production strength</strong><span>Usage-adjusted production that survives context changes.</span></div>
              <div class="criteria-card"><strong>Role scarcity</strong><span>Hard-to-replace 2026 guard profile.</span></div>
              <div class="criteria-card"><strong>Hidden value</strong><span>Secondary strengths that show up in the table and on/off data.</span></div>
              <div class="criteria-card"><strong>Salary alignment</strong><span>Does salary track the role or outrun the model?</span></div>
              <div class="criteria-card"><strong>Risk adjustment</strong><span>Veteran stage, volatility, and regression risk.</span></div>
            </div>
            <div class="formula-strip">
              <div class="formula-seg orange"><div class="pct">25%</div><div class="label">Production percentile</div></div>
              <div class="formula-seg amber"><div class="pct">20%</div><div class="label">Salary value</div></div>
              <div class="formula-seg burnt"><div class="pct">15%</div><div class="label">Role scarcity</div></div>
              <div class="formula-seg burnt"><div class="pct">15%</div><div class="label">Hidden impact</div></div>
              <div class="formula-seg slate"><div class="pct">10%</div><div class="label">Scalability</div></div>
              <div class="formula-seg green"><div class="pct">10%</div><div class="label">Playoff utility</div></div>
              <div class="formula-seg navy"><div class="pct">5%</div><div class="label">Risk</div></div>
            </div>
          </div>
        </div>
      </section>

      <section class="section" id="profile">
        <div class="section-head">
          <div>
            <div class="section-id">2. Cloud profile</div>
            <h2>Her production still looks like a premium starter, even before the market lens.</h2>
          </div>
          <p>
            Regular-season trend lines show steady assist creation, solid scoring, and a more efficient 2025 shooting profile. The playoff line adds another layer of utility.
          </p>
        </div>
        <div class="profile-grid">
          <div class="profile-card">
            <div class="profile-face">
              <div class="face-badge">NC</div>
              <div>
                <div class="profile-name">{esc(PLAYER_NAME)}</div>
                <div class="profile-role">Veteran organizer | {esc(cloud_team_name)} | 2026</div>
              </div>
            </div>
            <div class="profile-meta">
              <div class="meta-row"><strong>Role band</strong><span>{esc(cloud_arch['role_band'])}</span></div>
              <div class="meta-row"><strong>Skill signature</strong><span>{esc(cloud_arch['skill_signature'])}</span></div>
              <div class="meta-row"><strong>Usage</strong><span>{fmt_num(cloud_arch['usage'], 1)}</span></div>
              <div class="meta-row"><strong>TS%</strong><span>{fmt_pct(cloud_arch['ts_pct'], 1)}</span></div>
              <div class="meta-row"><strong>MPG</strong><span>{fmt_num(cloud_arch['mpg'], 1)}</span></div>
              <div class="meta-row"><strong>Playoff utility</strong><span>{fmt_num(cloud_arch['high_leverage_experience_score'], 1)}</span></div>
              <div class="meta-row"><strong>2026 salary</strong><span>{fmt_currency(cloud_current_salary)}</span></div>
              <div class="meta-row"><strong>Model value score</strong><span>{fmt_num(cloud_value['value_score'], 2)} ({esc(cloud_value['value_label'])})</span></div>
            </div>
          </div>
          <div class="panel">
            <div class="mini-grid">
              {''.join(season_spark_cards)}
            </div>
            <div class="table-wrap">
              <table style="min-width: 760px;">
                <thead>
                  <tr>
                    <th>Season</th><th>Type</th><th>GP</th><th>Minutes</th><th>MPG</th><th>PPG</th><th>APG</th><th>RPG</th><th>SPG</th><th>FG%</th><th>3P%</th><th>FT%</th>
                  </tr>
                </thead>
                <tbody>
                  {"".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in season_rows)}
                </tbody>
              </table>
            </div>
          </div>
          <div class="panel">
            <div class="section-id">Playoff utility</div>
            <div class="stat-value" style="margin-bottom:8px;">{fmt_num(cloud_playoffs['mpg'], 1)} MPG</div>
            <div class="stat-copy" style="margin-bottom:12px;">2025 playoff burst: {fmt_num(cloud_playoffs['ppg'], 1)} PPG, {fmt_num(cloud_playoffs['apg'], 1)} APG, {fmt_num(cloud_playoffs['spg'], 1)} SPG.</div>
            <div class="bar-row">
              <div class="bar-meta"><span class="bar-label">Points</span><span class="bar-value">{fmt_num(cloud_playoffs['ppg'], 1)}</span></div>
              <div class="bar-track"><div class="bar-fill" style="width:{min(100, float(cloud_playoffs['ppg']) * 6):.1f}%; background: linear-gradient(90deg, #f59e0b, #fb7185);"></div></div>
            </div>
            <div class="bar-row">
              <div class="bar-meta"><span class="bar-label">Assists</span><span class="bar-value">{fmt_num(cloud_playoffs['apg'], 1)}</span></div>
              <div class="bar-track"><div class="bar-fill" style="width:{min(100, float(cloud_playoffs['apg']) * 10):.1f}%; background: linear-gradient(90deg, #38bdf8, #a855f7);"></div></div>
            </div>
            <div class="bar-row">
              <div class="bar-meta"><span class="bar-label">Steals</span><span class="bar-value">{fmt_num(cloud_playoffs['spg'], 1)}</span></div>
              <div class="bar-track"><div class="bar-fill" style="width:{min(100, float(cloud_playoffs['spg']) * 30):.1f}%; background: linear-gradient(90deg, #22c55e, #38bdf8);"></div></div>
            </div>
            <div class="demand-list" style="margin-top:16px;">
              <div class="bullet"><i></i><span>2025 regular season: {fmt_num(cloud_regular['ppg'], 1)} PPG, {fmt_num(cloud_regular['apg'], 1)} APG, {fmt_num(cloud_regular['spg'], 1)} SPG.</span></div>
              <div class="bullet"><i></i><span>2025 shooting: {fmt_pct(cloud_regular['fg_pct'], 1)} FG, {fmt_pct(cloud_regular['three_pct'], 1)} 3P, {fmt_pct(cloud_regular['ft_pct'], 1)} FT.</span></div>
              <div class="bullet"><i></i><span>2025 playoff sample: {int(cloud_playoffs['games_played'])} games and {fmt_num(cloud_playoffs['minutes'], 0)} minutes.</span></div>
            </div>
          </div>
        </div>
      </section>

      <section class="section" id="demand">
        <div class="section-head">
          <div>
            <div class="section-id">3. Demand and fit</div>
            <h2>Demand is high because the role is scarce, not because the box score is loud.</h2>
          </div>
          <p>
            This score is an analyst judgment built from the framework's demand rubric. It is intentionally separate from the value-score output so the story can distinguish market appetite from production model output.
          </p>
        </div>
        <div class="demand-layout">
          <div class="panel">
            <div class="score-ring">
              <div class="score">
                <strong>{demand_score}</strong>
                <span>Demand score</span>
              </div>
            </div>
            <div class="demand-list">
              {''.join(f'<div class="bullet"><i></i><span>{esc(text)}</span></div>' for text in demand_bullets)}
            </div>
          </div>
          <div class="panel">
            <div class="percentile-grid">
              {''.join(percentile_cards)}
            </div>
            <div class="foot">
              Percentiles are league-wide among 2025 regular-season players with at least 300 minutes. Turnover control is inverted so a lower turnover rate scores higher.
            </div>
          </div>
        </div>
      </section>

      <section class="section" id="comparables">
        <div class="section-head">
          <div>
            <div class="section-id">4. Comparable contracts</div>
            <h2>The model finds a small but useful comp set, and two of the three comps already have live 2026 salary references.</h2>
          </div>
          <p>
            The nearby comps are compact enough to explain in the notebook, and they make the salary-band argument more concrete than a broad league average would.
          </p>
        </div>
        {table_html(["Rank", "Comparable", "Team", "Role band", "Basis", "Similarity", "Salary reference", "Salary source"], comp_table_rows)}
        <div class="foot">
          Reserved or expansion-placeholder comps are kept in the table when they are part of the model neighborhood, but their salary cell is labeled when the bundle does not surface a current figure.
        </div>
      </section>

      <section class="section" id="range">
        <div class="section-head">
          <div>
            <div class="section-id">5. Fair salary range</div>
            <h2>Show the range ladder plainly, then place the current reference salary against it.</h2>
          </div>
          <p>
            The point of the section is not to hide the model. The point is to make the framework's recommendation legible and to show where the 2026 salary sits relative to it.
          </p>
        </div>
        <div class="range-grid">
          {''.join(band_cards)}
        </div>
        <div class="range-ruler"></div>
        {current_ref_marker}
        <div class="callout" style="margin-top:16px;">
          <div>
            <div class="section-id">Value score</div>
            <h3>{fmt_num(cloud_value['value_score'], 2)} on a 0-100 scale.</h3>
            <p>
              The current Doc 2 model reads Cloud as a premium starter, not an undervalued bargain. That is exactly why this case study is interesting: it separates role scarcity and market demand from the model's production-based fair band.
            </p>
          </div>
          <div class="callout-badge">
            <span class="big">{esc(cloud_value['value_label'])}</span>
            <span class="small">Framework value label</span>
          </div>
        </div>
      </section>

      <section class="section" id="market">
        <div class="section-head">
          <div>
            <div class="section-id">6. Market structure</div>
            <h2>Place Cloud inside the broader value-versus-salary market, then show how the league moved year to year.</h2>
          </div>
          <p>
            The scatter uses all players with usable value-score rows. Cloud is highlighted against the model fair band, so the notebook can show both market shape and individual fit in one view.
          </p>
        </div>
        <div class="market-grid">
          <div class="panel">
            {market_scatter}
            <div class="foot">
              X-axis: value score. Y-axis: salary reference. The highlighted dot uses the current 2026 salary reference from the salary-history bundle.
            </div>
          </div>
          <div class="panel">
            <div class="section-id">Market shift by season</div>
            <div class="table-wrap" style="margin-bottom:12px;">
              <table style="min-width: 580px;">
                <thead>
                  <tr>
                    <th>Season</th><th>Players</th><th>Mean salary</th><th>Median</th><th>Min</th><th>Max</th>
                  </tr>
                </thead>
                <tbody>
                  {"".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in market_rows)}
                </tbody>
              </table>
            </div>
            <div class="panel" style="padding:14px;">
              <div class="section-id">Cloud salary line</div>
              {cloud_salary_lines}
            </div>
          </div>
        </div>
      </section>

      <section class="section" id="takeaway">
        <div class="section-head">
          <div>
            <div class="section-id">7. Takeaway</div>
            <h2>The portfolio story is the tension between market demand and production-based fairness.</h2>
          </div>
          <p>
            The framework does not flatten Cloud into one label. It shows why the market might pay for her, what the model thinks that role is worth, and how to talk about the difference without hand-waving.
          </p>
        </div>
        <div class="callout">
          <div>
            <h3>Cloud reads as a contender-grade organizer whose value is strongest when a team needs calm, defense, and playmaking more than volume scoring.</h3>
            <p>
              That is the cleanest portfolio angle: start with the framework spine, show the production trend and percentiles, then use the comp table and salary band to explain why the current 2026 salary and the model fair band are not the same thing.
            </p>
          </div>
          <div class="callout-badge">
            <span class="big">{fmt_salary_band(cloud_value['recommended_salary_low'], cloud_value['recommended_salary_high'])}</span>
            <span class="small">Model fair range</span>
          </div>
        </div>
        <div class="footer">Natasha Cloud case study notebook | generated from local Doc 2 tables and salary history bundle</div>
      </section>
    </main>
  </div>
</body>
</html>
"""

    return html_doc


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
