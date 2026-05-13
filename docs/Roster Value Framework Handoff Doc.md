# **WNBA 2026 Roster-Value Framework Handoff**

## **Project Snapshot:**

This repo builds a WNBA roster/value framework from three source layers:

* pbpstats season and on/off data for 2023-2025  
* validated 2026 salary/cap data plus historical salary history  
* Basketball Reference transaction and draft extracts for roster context

The system is split into two layers:

* a stable foundation that is safe to use now  
* a provisional on/off-dependent value chain that can be finalized later when the missing 2024 | Regular Season on/off backfill arrives

For the Natasha Cloud case study, the safe path is to start from the stable foundation now and only use on/off where it is already available. Do not block the case study on the missing 2024 regular-season on/off slice.

## **Current State**

Finalized now:

* player\_season\_stats  
* advanced\_player\_metrics  
* playoff\_experience  
* team\_rosters  
* team\_roster\_history  
* players\_master  
* contracts\_2026  
* team\_salary\_cap  
* transactions\_2026  
* expansion\_draft\_2026

Provisional now:

* onoff\_metrics  
* player\_archetypes  
* comparable\_players  
* value\_scores  
* team\_roster\_grades  
* market\_benchmarks

Latest saved provisional build shape:

* onoff\_metrics is 261 rows and currently contains 2025 | Regular Season and 2025 | Playoffs  
* player\_archetypes is 374 rows  
* comparable\_players is 1,870 rows  
* value\_scores is 374 rows  
* team\_roster\_grades is 15 rows  
* market\_benchmarks is 25 rows

Key decision:

* the current build is intentionally provisional  
* the missing 2024 | Regular Season on/off can be backfilled later without redesigning the rest of the chain

## **How the Pieces Fit**

* scripts/build\_doc2\_roster\_tables.py builds the stable Doc 2 foundation tables from the salary bundle, pbpstats season tables, roster history, and transaction/draft sources.  
* scripts/build\_doc2\_value\_chain.py builds the downstream value chain. It now marks the current run provisional and keeps the on/off-dependent tables separate from the finalized inputs.  
* scripts/build\_team\_roster\_history.py builds the 2023-2025 roster history from pbpstats discovery.  
* scripts/pbpstats\_job\_runner.py is the generic manifest-driven pbpstats runner with retries, presets, and raw/normalized/derived outputs.  
* scripts/pbpstats\_wnba\_retrieval.py is the WNBA-specific compatibility entrypoint.  
* configs/pbpstats/jobs/wnba\_roster\_value\_bundle.json and configs/pbpstats/endpoint\_registry.json define the pbpstats job families and request shapes.  
* docs/pbpstats\_job\_spec.md and docs/pbpstats\_doc2\_coverage.md explain the pipeline contract and schema coverage.  
* notebooks/pbpstats\_wnba\_retrieval.ipynb is the inspection notebook for endpoint shapes and smoke testing.

## **How to Continue**

For a Natasha Cloud case study, the recommended dependency order is:

1. Use the stable foundation tables now.  
2. Use 2025 regular season and playoffs on/off if needed for impact context.  
3. Treat the value chain tables as provisional unless you explicitly want to refresh them after the 2024 regular-season on/off backfill.  
4. Backfill 2024 | Regular Season on/off later, then rerun only the on/off-sensitive branch.

## **File Catalog**

### Core project docs and design files

* data\_schema\_doc\_2\_roster\_value\_2026.docx \- Master Doc 2 schema file. This is the source of truth for the roster-value dataset design and the table list we’ve been building against.  
* wnba\_2026\_roster\_value\_framework\_and\_data\_schema.md \- Narrative framework and schema guide for the WNBA roster/value project. It captures the project logic and table relationships in a human-readable form.  
* wnba\_2026\_roster\_value\_framework\_diagram.html \- Rendered framework diagram that visualizes the pipeline and table dependencies.  
* wnba\_2026\_framework\_figjam.mmd \- Mermaid source for the project diagram. Useful if you want to regenerate or edit the framework view.  
* roster\_continuity\_study\_summary\_evanmiya\_replication\_notes.md \- Notes from the roster-continuity study and EvanMiya-style replication context that informed the roster-value framing.

### Salary and cap sources

* 2024\_2026\_salaries\_wnba\_all\_players.csv \- Historical salary source for 2024-2026. The salary/signing fields are season+1 aligned and are used for salary-history joins and benchmark logic.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2.zip \- Canonical 2026 salary/cap validation bundle archive. This is the most important current salary source set.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/README.txt \- Bundle readme describing the validated cap/salary package.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/VALIDATION\_REPORT.md \- Human-readable validation summary for the salary bundle.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/wnba\_2026\_player\_year\_contract\_status\_validated.csv \- Canonical validated player-year salary/cap table used as the core salary input.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/contracts\_2026.csv \- Validated current-year contract table.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/team\_salary\_cap.csv \- Validated team cap summary table.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/validation\_report\_2026\_summary.csv \- Summary table of validation results and coverage.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/validation\_report\_detail.csv \- Detailed validation rows with row-level issues and checks.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/field\_coverage\_audit.csv \- Field completeness audit for the validation bundle.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/missing\_ambiguous\_icon\_rows.csv \- Rows needing review because of missing or ambiguous icon/status handling.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/excluded\_special\_rows\_2026.csv \- Rows excluded from the canonical validated bundle.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/cba\_numbers\_by\_team.csv \- Team-level CBA numbers supporting the cap model.  
* wnba\_2026\_final\_cap\_validation\_bundle\_v2/wnba\_2026\_player\_year\_contract\_status\_2026\_only.csv \- 2026-only slice of the player-year contract status data.  
* wnba\_2026\_cap\_sheet\_long.csv \- Earlier long-form cap sheet extract used during the cap cleanup process.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset.zip \- Cleaned cap-sheet package from the earlier source cleanup stage.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/README\_data\_dictionary.txt \- Data dictionary for the cleaned cap sheet package.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/wnba\_2026\_cap\_sheet\_contracts\_clean\_long.csv \- Cleaned long-form contract table from the cap-sheet package.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/wnba\_2026\_cap\_sheet\_contracts\_clean\_wide.csv \- Cleaned wide-form contract table from the cap-sheet package.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/wnba\_2026\_cba\_numbers\_clean.csv \- Cleaned CBA numbers file from the cap-sheet package.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/wnba\_2026\_team\_summary\_clean\_long.csv \- Team summary output from the cleaned cap-sheet package.  
* wnba\_2026\_cap\_sheet\_cleaned\_dataset/wnba\_2026\_cap\_sheet\_notes.csv \- Notes and edge cases from the cleaned cap-sheet package.  
* wnba\_2026\_hhs\_cap\_sheet\_validation\_outputs.zip \- Earlier validation archive from the cap-sheet source work. Useful as historical reference if you need to trace the path from source to canonical bundle.

### Scripts and configs

* scripts/build\_team\_roster\_history.py \- Builds the 2023-2025 team roster history from pbpstats discovery output.  
* scripts/build\_doc2\_roster\_tables.py \- Builds the stable Doc 2 foundation tables, including salary-core outputs and season-history tables.  
* scripts/build\_doc2\_value\_chain.py \- Builds the downstream value chain. The current version is deliberately provisional because it depends on the still-missing 2024 regular-season on/off backfill.  
* scripts/pbpstats\_job\_runner.py \- Generic manifest-driven pbpstats runner with presets, retries, and raw/normalized/derived output writing.  
* scripts/pbpstats\_wnba\_retrieval.py \- WNBA-specific wrapper/compatibility entrypoint for the pbpstats pipeline.  
* configs/pbpstats/endpoint\_registry.json \- Endpoint registry describing pbpstats job families, parameters, and season-type support.  
* configs/pbpstats/jobs/wnba\_roster\_value\_bundle.json \- Bundle spec that ties together discovery, totals, on/off, and shot/pace jobs for the WNBA workflow.  
* docs/pbpstats\_job\_spec.md \- Human-readable job-spec document for the pbpstats pipeline and presets.  
* docs/pbpstats\_doc2\_coverage.md \- Coverage map that links Doc 2 schema fields to the currently available sources.  
* notebooks/pbpstats\_wnba\_retrieval.ipynb \- Notebook companion used to inspect pbpstats endpoint shapes and smoke test the retrieval workflow.

### Basketball Reference transaction inputs

* data/basketball\_reference\_transactions/wnba\_transactions\_master\_current\_extract.csv \- Master transaction extract used to build transaction and roster context tables.  
* data/basketball\_reference\_transactions/wnba\_transaction\_assets\_current\_extract.csv \- Transaction asset detail table used in the transactions output.  
* data/basketball\_reference\_transactions/wnba\_transactions\_extract\_summary.csv \- Summary of the transaction extract package.  
* data/basketball\_reference\_transactions/wnba\_draft\_pick\_base\_current\_extract.csv \- Draft-pick base extract used for the expansion draft table.  
* data/basketball\_reference\_transactions/ucla\_draft\_pick\_base\_current\_extract.csv \- Supporting draft-pick reference file that was part of the transaction/source cleanup.  
* data/basketball\_reference\_transactions/wnba\_transactions\_current\_extract\_package.zip \- Packaged transaction extract bundle for the current snapshot.

### pbpstats job bundles and manifests

* data/pbpstats\_jobs/bundle\_summary.json \- Overall summary across pbpstats job families and their success/failure state.  
* data/pbpstats\_jobs/wnba\_league\_discovery/manifest.json \- Discovery job manifest for team catalogs and team-player catalogs.  
* data/pbpstats\_jobs/wnba\_totals/manifest.json \- Totals job manifest for player and team season totals.  
* data/pbpstats\_jobs/wnba\_on\_off/manifest.json \- On/off job manifest. The current saved output is partial and intentionally treated as provisional.  
* data/pbpstats\_jobs/wnba\_shot\_pace/manifest.json \- Shot/pace job manifest for pace, shots, possessions, and score-time queries.  
* data/pbpstats\_jobs/wnba\_team\_roster\_history/manifest.json \- Roster-history discovery manifest used to build season-by-season team rosters.

### **Doc 2 output manifest and quality files**

* data/doc2\_roster\_value/manifest.json \- Master manifest for every Doc 2 table, build status, source manifest, and quality report location.  
* data/doc2\_roster\_value/coverage\_report.csv \- CSV coverage report summarizing each Doc 2 table’s field coverage and row counts.  
* data/doc2\_roster\_value/coverage\_report.parquet \- Parquet version of the Doc 2 coverage report.  
* data/doc2\_roster\_value/quality/onoff\_validation\_report.csv \- On/off quality gate report showing season/type coverage and row thresholds.  
* data/doc2\_roster\_value/quality/onoff\_validation\_report.parquet \- Parquet version of the on/off quality report.  
* data/doc2\_roster\_value/quality/onoff\_missing\_keys.csv \- Missing on/off key report for any season/team/player gaps.  
* data/doc2\_roster\_value/quality/onoff\_missing\_keys.parquet \- Parquet version of the missing-keys report.

### **Stable Doc 2 foundation tables**

* data/doc2\_roster\_value/tables/player\_season\_stats/player\_season\_stats.csv \- Final season-level totals table built from pbpstats.  
* data/doc2\_roster\_value/tables/advanced\_player\_metrics/advanced\_player\_metrics.csv \- Final advanced metrics table built from the totals layer.  
* data/doc2\_roster\_value/tables/playoff\_experience/playoff\_experience.csv \- Final playoff history and postseason experience table.  
* data/doc2\_roster\_value/tables/team\_rosters/team\_rosters.csv \- Salary-enriched current roster table for 2026\.  
* data/doc2\_roster\_value/tables/team\_roster\_history/team\_roster\_history.csv \- Season-by-season player roster history for 2023-2025.  
* data/doc2\_roster\_value/tables/players\_master/players\_master.csv \- Salary-enriched player identity base used by the value chain.  
* data/doc2\_roster\_value/tables/contracts\_2026/contracts\_2026.csv \- Final 2026 contract table built from the validated salary bundle.  
* data/doc2\_roster\_value/tables/team\_salary\_cap/team\_salary\_cap.csv \- Final team cap summary table built from the validated salary bundle.  
* data/doc2\_roster\_value/tables/transactions\_2026/transactions\_2026.csv \- Normalized 2026 transaction table for roster context.  
* data/doc2\_roster\_value/tables/expansion\_draft\_2026/expansion\_draft\_2026.csv \- Expansion draft table used for roster construction context.

### **Provisional on/off-dependent value chain tables**

* data/doc2\_roster\_value/tables/onoff\_metrics/onoff\_metrics.csv \- Provisional on/off summary table. The current saved build is 2025-only and is meant to be refreshed later when 2024 regular-season on/off is available.  
* data/doc2\_roster\_value/tables/player\_archetypes/player\_archetypes.csv \- Provisional archetype and role table built from the stable foundation plus current on/off coverage.  
* data/doc2\_roster\_value/tables/comparable\_players/comparable\_players.csv \- Provisional similarity/comps table used downstream for player value work.  
* data/doc2\_roster\_value/tables/value\_scores/value\_scores.csv \- Provisional player value model that combines production, salary, and salary-history context.  
* data/doc2\_roster\_value/tables/team\_roster\_grades/team\_roster\_grades.csv \- Provisional team-level roster quality and cap-efficiency summary.  
* data/doc2\_roster\_value/tables/market\_benchmarks/market\_benchmarks.csv \- Provisional market benchmark table grouped by archetype, role, and salary tier.

## **Notes for the Natasha Cloud Case Study**

* Use the stable foundation tables first.  
* If you need impact context, use the current 2025 on/off outputs and treat them as provisional context, not a final historical series.  
* The missing 2024 | Regular Season on/off slice can be added later without changing the rest of the framework.  
* The case study should stay season-aware and keep season / season\_type in every output row or summary.

