# pbpstats Job Spec

This project uses a manifest-driven pbpstats workflow with one generic runner, one endpoint registry, and one job bundle per use case.

## Operating Rules

- Minimum seasons: `2025`, `2024`, `2023`
- Season types: fetch `Regular Season` and `Playoffs` whenever the endpoint supports both
- Fallback: if playoffs are not supported, fetch `Regular Season`
- Every output row must include `season`, `season_type`, `league`, `endpoint`, `job_id`, `job_family`, `job_variant`, and request trace fields

## File Structure

```text
scripts/
  pbpstats_job_runner.py
  pbpstats_wnba_retrieval.py
configs/
  pbpstats/
    endpoint_registry.json
    jobs/
      wnba_roster_value_bundle.json
docs/
  pbpstats_job_spec.md
  pbpstats_doc2_coverage.md
notebooks/
  pbpstats_wnba_retrieval.ipynb
data/
  pbpstats_jobs/
    <job_id>/
      raw/
      normalized/
      derived/
      manifest.json
    bundle_summary.json
```

## Endpoint Registry

Each endpoint entry declares:

- `path`
- `supports_playoffs`
- `default_season_type`
- `emit_season_type_column`
- `response_tables`

## Job Bundle

Each job entry declares:

- `job_id`
- `family`
- `description`
- `output_profiles`
- `variants`

Variants define the endpoint-specific request shape and scope.

`get-on-off` team-scoped requests still require a `PlayerId`, so the runner
expands them against the discovered team roster before calling the API.

## Example Jobs

### Totals

```json
{
  "job_id": "wnba_totals",
  "family": "totals",
  "variants": [
    {
      "name": "player_totals",
      "endpoint": "get-totals",
      "scope": "season",
      "request_params": { "Type": "Player" }
    },
    {
      "name": "team_totals",
      "endpoint": "get-totals",
      "scope": "season",
      "request_params": { "Type": "Team" }
    }
  ]
}
```

### On/Off

```json
{
  "job_id": "wnba_on_off",
  "family": "on_off",
  "variants": [
    {
      "name": "player_on_off",
      "endpoint": "get-on-off",
      "scope": "team_player",
      "stat_type": "player",
      "request_params": {}
    },
    {
      "name": "team_on_off",
      "endpoint": "get-on-off",
      "scope": "team",
      "stat_type": "team",
      "request_params": {}
    }
  ]
}
```

### Shot/Pace

```json
{
  "job_id": "wnba_shot_pace",
  "family": "shot_pace",
  "variants": [
    {
      "name": "pace_by_season",
      "endpoint": "get-pace-efficiency-by-season",
      "scope": "season_type_only",
      "request_params": {}
    },
    {
      "name": "shot_query_summary",
      "endpoint": "get-shot-query-summary",
      "scope": "season",
      "request_params": {
        "Type": "Team",
        "FromMargin": -3,
        "ToMargin": 3,
        "FromTime": 300,
        "ToTime": 120,
        "PeriodGte": 4
      }
    },
    {
      "name": "shots",
      "endpoint": "get-shots",
      "scope": "team",
      "request_params": {
        "EntityType": "Team",
        "StartType": "All",
        "Blocked": false
      }
    },
    {
      "name": "possessions",
      "endpoint": "get-possessions",
      "scope": "team",
      "request_params": {
        "OffDef": "Offense",
        "FilterComparison": "Exactly",
        "FilterEvent": "OnFloor",
        "FilterValue": 5,
        "StartType": "All"
      }
    },
    {
      "name": "score_time_summary",
      "endpoint": "get-score-time-summary",
      "scope": "season",
      "request_params": {
        "Type": "Team",
        "FromMargin": -3,
        "ToMargin": 3,
        "FromTime": 300,
        "ToTime": 120,
        "PeriodGte": 4
      }
    }
  ]
}
```

## Workflow

1. Read the bundle.
2. Load the endpoint registry.
3. Expand seasons across `2025`, `2024`, and `2023`.
4. Expand season types across `Regular Season` and `Playoffs` when supported.
5. Fetch each endpoint.
6. Save raw JSON.
7. Flatten and save normalized tables.
8. Add derived rows and save analysis-ready tables.
9. Write a manifest with request ids, request params, and output paths.

## CLI Presets

- `totals`: totals-only smoke run
- `on_off`: discovery plus on/off family
- `shot_pace`: discovery plus shot/pace family
- `roster_value`: full bundle

Preset mode defaults to a smoke-sized request set unless explicit season or season-type arguments are supplied.
