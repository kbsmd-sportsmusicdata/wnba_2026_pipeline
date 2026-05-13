# Player & Roster Intel Framework - WNBA 2026

This workspace now includes a current-season 2026 ingestion and processing path built around:

- `pbpstats` as the canonical source for discovery, on/off, and shot/pace context
- SportsDataverse `wehoop` release assets as the fallback layer for player/team game logs and schedules
- append-safe master tables for current-season refreshes
- downstream BI-ready exports and post-game summaries

## Key Scripts

- `scripts/current_season_pipeline.py`
  - Runs the 2026 ingestion workflow
  - Pulls `pbpstats` discovery/on-off/shot data
  - Pulls `wehoop` release-backed player boxscore, team boxscore, and schedule data
  - Writes deduplicated master tables under `data/current_season_2026/masters/`

- `scripts/process_current_season_pipeline.py`
  - Refreshes downstream current-season outputs
  - Builds player summaries, post-game summaries, and BI-ready exports
  - Can also refresh the existing Doc 2 foundation/value-chain first

## Current-Season Commands

Full ingestion refresh with append-safe masters:

```bash
python3 scripts/current_season_pipeline.py --append --full-refresh
```

Current-season processing refresh:

```bash
python3 scripts/process_current_season_pipeline.py
```

Fast local processing run without rebuilding the full Doc 2/value-chain:

```bash
python3 scripts/process_current_season_pipeline.py --skip-doc2-refresh
```

## Main Output Locations

- Current-season master tables:
  - `data/current_season_2026/masters/`
- Current-season processed tables:
  - `data/current_season_2026/processed/`
- Current-season BI exports:
  - `data/current_season_2026/bi_exports/`
- Raw `pbpstats` assets and manifests:
  - `data/raw/pbpstats/current_season_2026/`
- Raw `wehoop` assets and manifests:
  - `data/raw/wehoop/current_season_2026/`

## Automation

GitHub Actions workflows are defined in `.github/workflows/` for:

- twice-weekly ingestion refresh
- downstream processing after successful ingestion

## Tests

```bash
python3 -m pytest tests/test_current_season_pipeline.py tests/test_current_season_processing.py -q
```

