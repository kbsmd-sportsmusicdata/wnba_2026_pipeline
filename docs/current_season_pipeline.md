# Current-Season 2026 Pipeline

## Purpose

This pipeline adds a current-season operating layer to the existing WNBA 2026 roster-value workspace.

It keeps `pbpstats` as the primary source for:

- team discovery
- roster discovery
- player and team on/off
- shot profile, shot context, pace, and possession context

It uses SportsDataverse release-backed `wehoop` assets as the fallback layer for:

- player game logs
- team game logs
- schedules

## Files

- Config:
  - `configs/current_season/wnba_current_season_2026.json`
- `pbpstats` bundle:
  - `configs/pbpstats/jobs/wnba_current_season_bundle.json`
- Ingestion:
  - `scripts/current_season_pipeline.py`
- Processing:
  - `scripts/process_current_season_pipeline.py`

## Data Flow

1. Run the current-season `pbpstats` bundle for 2026.
2. Pull `wehoop` release assets for player boxscores, team boxscores, and schedules.
3. Normalize both source families into shared master tables.
4. Append only unseen rows using stable keys.
5. Refresh downstream current-season outputs and BI exports.

## Master Tables

- `player_onoff_master.csv`
- `team_onoff_master.csv`
- `player_game_logs_master.csv`
- `team_game_logs_master.csv`
- `schedule_master.csv`
- `shot_profile_summary_master.csv`

## Dedupe Keys

- Player on/off:
  - `season + season_type + team_id + player_id + source_variant`
- Team on/off:
  - `season + season_type + team_id + player_id + source_variant`
- Player game logs:
  - `season + game_id + player_id`
- Team game logs:
  - `season + game_id + team_id`
- Schedule:
  - `season + game_id`

## Notes

- `pbpstats` shot data is part of v1 and should remain the canonical shot-profile layer.
- `wehoop` shots are intentionally left as optional follow-on enrichment, not a launch blocker.
- GitHub Actions use `--full-refresh` because the runner defaults to smoke caps unless the full flag is supplied.

