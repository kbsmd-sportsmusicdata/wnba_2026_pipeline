# Doc 2 Coverage Map

This note maps the roster-value schema to pbpstats coverage.

## Direct or Mostly Direct from pbpstats

| Schema area | Likely source | Notes |
| --- | --- | --- |
| `player_season_stats` | `get-totals`, `get-all-season-stats` | Season totals and season-by-season history |
| `advanced_player_metrics` | `get-totals`, `get-all-season-stats`, `get-pace-efficiency-by-season` | Efficiency, rate, and pace context |
| `onoff_metrics` | `get-on-off`, `get-wowy-stats`, `get-wowy-combination-stats` | On/off and WOWY totals |
| `playoff_experience` | `get-totals`, `get-all-season-stats` | Games/minutes by season type |
| `team_rosters` | `get-games`, `get-team-players-for-season`, `get-all-players-for-league`, `get-teams` | Discovery and roster membership |

## Derived from pbpstats

| Schema area | Derived from | Notes |
| --- | --- | --- |
| `player_archetypes` | totals, on/off, shot, pace tables | Cluster or rules-based grouping |
| `comparable_players` | totals, on/off, shot profile | Similarity or neighbor scoring |
| `value_scores` | totals, on/off, pace, shot profile | Weighted value formula |
| `team_roster_grades` | player value scores plus roster context | Team-level aggregation |
| `market_benchmarks` | league-wide tables | Range and percentile comparisons |

## External or Non-pbpstats

| Schema area | Source type | Notes |
| --- | --- | --- |
| `players_master` | external | Canonical identity layer |
| `contracts_2026` | external | Salary and contract data |
| `team_salary_cap` | external | Cap and payroll context |
| `transactions_2026` | external | Movement and status history |
| `expansion_draft_2026` | external | Draft-specific context |

## Field-Level Notes

These are the main pbpstats-backed metrics that matter for the roster schema:

- `games_played`
- `mpg`
- `usage_pct`
- `ts_pct`
- `ast_pct`
- `tov_pct`
- `stl_pct`
- `blk_pct`
- `reb_pct`
- `on/off net rating`
- playoff games and playoff minutes

Derived metrics in this pipeline can add:

- per-game rates
- per-minute rates
- on/off differentials
- pace-adjusted or possession-adjusted fields
- playoff flags
- season type flags

