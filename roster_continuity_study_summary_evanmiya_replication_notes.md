# Roster Continuity in the Portal Era: Summary and Replication Notes

## Overview

This document summarizes Evan Miyakawa’s article *Does Roster Retention Still Matter?* and uses his earlier article *How To Build A Roster In The Modern Portal Era* to reconstruct the analytical approach in more detail.[cite:1][cite:2]

The central update is that roster continuity appears to matter **less** for general high-major regular-season success than it did in his earlier study, but it still appears to matter for the very best teams and especially for national-title-level outcomes.[cite:1][cite:2]

## Main conclusions

- Talent remains the dominant driver of team performance; Miyakawa states that a team’s season is about 80% defined by roster quality before the year starts, with the remaining 20% driven by what happens during the season.[cite:1]
- Average continuity has dropped sharply; the typical high-major team went from about 50% of minutes played by returners two years earlier to only 32% in the most recent season, meaning 68% of production came from newcomers.[cite:1]
- Based on the 2026 update, there is no longer strong enough evidence to say that high-major teams in general should heavily prioritize retention in order to outperform expectations.[cite:1]
- However, continuity still appears important for elite postseason ceilings; all 2026 Final Four teams were above that season’s median returner-minutes rate, and 3 of the 4 Final Four teams in the previous season were also above the median.[cite:1]
- Across the last five seasons, 17 of 20 No. 1 seeds had top-15 preseason roster grades, 16 of 20 had roughly half or more of their minutes from returners, and 10 of the 12 most recent No. 1 seeds were above their season’s high-major median in returner-minutes share.[cite:1]
- Nine of the ten national title game participants in the last five seasons had above-average reliance on returning players relative to their season.[cite:1]

## What changed from the earlier study

The 2024 study covered the 2021-22 through 2023-24 seasons and focused on high-major men’s teams, using preseason roster quality and in-season minute allocation as the main variables.[cite:2]

That earlier study concluded more strongly that similarly talented teams built around returners usually outperformed similarly talented teams built around newcomers, and it recommended a practical benchmark of at least 50% of minutes from returning players.[cite:2]

The 2026 update effectively narrows that claim: continuity is no longer a broad prescription for all high-majors, but it still shows up consistently among top-end teams, especially No. 1 seeds, Final Four teams, and title-game participants.[cite:1][cite:2]

## Analytical approach

### Population and scope

- The studies focus on **high-major** men’s college basketball teams rather than all of Division I, because roster-building constraints differ meaningfully for mid-majors.[cite:2]
- The earlier study explicitly used a three-year sample: 2021-22, 2022-23, and 2023-24.[cite:2]
- The update adds the latest 2025-26 season and references trends over the last five seasons when discussing 1-seeds, title teams, and title-game teams.[cite:1]

### Core variables

Miyakawa identifies four main variables in the earlier study:[cite:2]

- Preseason roster score ranking.
- Percentage of minutes played by returning players.
- Percentage of minutes played by new transfers.
- Percentage of minutes played by freshmen.[cite:2]

The update emphasizes the same conceptual ingredients, though it discusses them more through the lens of returner-minutes share, median continuity by season, and preseason roster grade.[cite:1]

### How roster quality was measured

Preseason roster quality was measured with a *preseason roster score* built from each player’s preseason BPR projection, summed across the roster and weighted by expected playing time.[cite:2]

Expected minutes were assigned based on each player’s projected standing relative to teammates; the best players were typically projected around 30 minutes per game, while lower-rotation players were closer to 10 minutes per game.[cite:2]

This means the core talent metric is not simply recruiting rank or returning production. It is a projection-based estimate of how strong the full roster should be before games are played.[cite:2]

### How continuity was measured

The main continuity metric is the **percentage of team minutes during the season played by returning players**.[cite:1][cite:2]

That choice matters because it measures realized continuity in the actual rotation, not just who was listed on the roster at the start of the season.[cite:1][cite:2]

The related newcomer measures are the percentage of minutes played by transfers and the percentage played by freshmen.[cite:2]

### Comparison framework

The earlier article uses several comparison layers:[cite:2]

- Champions and No. 1 seeds across multiple seasons.
- Teams finishing in the top 10 versus high-majors missing the NCAA tournament.[cite:2]
- Teams grouped by preseason roster-score rank, then split by whether returners played at least 50% of minutes.[cite:2]
- Extreme case studies, such as teams with maximum continuity, minimal continuity, and unusually high freshman-minute shares.[cite:2]

The update places more emphasis on postseason ceiling groups: national champions, Final Four teams, No. 1 seeds, and title-game teams.[cite:1]

### Implied statistical logic

The articles do not present a full regression specification in the text that was accessible here, but the process clearly follows a **stratified comparison** approach.[cite:1][cite:2]

In practical terms, Miyakawa first controls informally for team quality using preseason roster-score rank, then compares how teams with different continuity profiles perform inside similar talent bands.[cite:2]

He also uses season-relative benchmarks, such as whether a Final Four or No. 1-seed team was above the median returner-minutes percentage for that season, which is important because average continuity is declining over time.[cite:1]

## Results in more detail

### Earlier findings

From the earlier three-year study:[cite:2]

- Top-10 teams averaged about 60% of minutes from returners, versus 51% for high-majors that missed the NCAA tournament.[cite:2]
- Top-10 teams relied less on transfers, at 23% of minutes versus 35% for high-majors missing the tournament.[cite:2]
- Teams in the same preseason-talent bucket consistently finished better on average when returners played at least 50% of minutes.[cite:2]
- Among teams with top-35 preseason roster scores, teams above the 50% returner-minutes threshold finished around 18th on average, compared with around 25th for those below the threshold.[cite:2]
- Freshman-minute share did not appear to show the same clear relationship with team success.[cite:2]

### Updated findings

From the newer article:[cite:1]

- The average high-major continuity environment has changed enough that the old “prioritize retention broadly” conclusion no longer holds as strongly.[cite:1]
- Teams with strong continuity have sometimes underachieved, while some low-continuity teams have exceeded expectations, as long as they upgraded talent.[cite:1]
- For championship-level outcomes, continuity still shows up repeatedly: every champion from 2022 to 2025 had at least 49% of minutes from returners, and most recent Final Four and title-game teams were above their season’s average or median continuity marks.[cite:1]
- The notable exception is Michigan’s 2026 title team, which won with only 34% of minutes from returners and more than half of its production from newcomers, especially transfers.[cite:1]

## Replication design

### Recommended dataset structure

To reproduce this study, create one team-season table where each row is a team in a given season.[cite:1][cite:2]

Suggested fields:

| Field | Description |
|---|---|
| season | Season label, such as 2025-26. |
| team | Team name. |
| conference_group | High-major vs other grouping. |
| preseason_roster_score | Projection-based roster talent score.[cite:2] |
| preseason_roster_rank | National rank of preseason roster score.[cite:2] |
| end_of_season_team_rating | Final power rating / efficiency rating.[cite:2] |
| end_of_season_rank | Final national rank by that rating.[cite:2] |
| returner_minutes_pct | Share of team minutes played by returning players.[cite:1][cite:2] |
| transfer_minutes_pct | Share of team minutes played by incoming transfers.[cite:2] |
| freshman_minutes_pct | Share of team minutes played by freshmen.[cite:2] |
| n_transfers | Number of transfers added, if available.[cite:2] |
| ncaa_seed | NCAA tournament seed, if applicable.[cite:1][cite:2] |
| ncaa_round_reached | Tournament result, such as R32, S16, F4, runner-up, champion.[cite:1][cite:2] |
| season_median_returner_pct | Median returner-minutes share among peer teams that season.[cite:1] |
| above_season_median_returners | Indicator for whether the team exceeded that median.[cite:1] |

### Player-level inputs

A cleaner way to build the team-season table is from a player-season table with one row per player-team-season.[cite:2]

Suggested player-level fields:

- season.
- team.
- player.
- player_source, coded as returner, transfer, freshman, juco, international freshman, or other categories you need.
- preseason_player_projection, equivalent to a player-level quality metric such as BPR if available.[cite:2]
- actual_minutes_played or actual_minutes_share.
- projected_minutes or expected rotation role.[cite:2]
- prior_team and prior_season, to classify transfers and returners accurately.

From this table, aggregate actual minutes by source bucket to calculate returner, transfer, and freshman shares.[cite:1][cite:2]

### Reproducing the original comparisons

1. Restrict to high-major teams for the main analysis, matching the article’s population.[cite:2]
2. Build a preseason roster score from player projections, weighted by projected minutes or a comparable expected-role estimate.[cite:2]
3. Compute actual in-season minute shares for returners, transfers, and freshmen.[cite:1][cite:2]
4. Join end-of-season team rating and postseason outcome data.[cite:1][cite:2]
5. Group teams into preseason roster-rank buckets, then compare average final ranking for teams above and below a 50% returner-minutes threshold.[cite:2]
6. Repeat the postseason-ceiling analysis by checking whether Final Four teams, title-game teams, and 1-seeds were above their season’s median continuity level.[cite:1]
7. Add outlier case studies for teams with the most and least continuity, since those examples helped illustrate the earlier article’s findings.[cite:2]

### Statistical extensions

To make the replication more rigorous than the published write-up, consider these models:

- Linear regression: final team rating as a function of preseason roster score, returner-minutes share, transfer-minutes share, freshman-minutes share, and season fixed effects.
- Logistic regression: making the Final Four or title game as a function of preseason roster rank tier and continuity measures.
- Interaction terms: test whether continuity matters more for top-15 or top-25 preseason rosters than for the broader high-major field.
- Nonlinear effects: test whether the relationship changes around thresholds such as 40%, 50%, or 60% returner minutes.[cite:1][cite:2]

Those extensions fit the article’s logic well because the written findings suggest continuity has become more important for **ceiling outcomes** than for generic regular-season success.[cite:1]

## Adapting to women’s basketball

### Why the framework should transfer well

The framework is portable to WBB because it separates three concepts that also matter in women’s basketball: roster talent, continuity, and source of minutes.[cite:1][cite:2]

The key adaptation is that the transfer market, freshman impact curve, roster sizes, and conference structure in WBB can differ from MBB, so the thresholds should be re-estimated rather than copied directly.[cite:1][cite:2]

### WBB-specific recommendations

- Recalculate all thresholds within WBB, especially the season median returner-minutes rate and any benchmark like the 50% threshold; do not assume the men’s cut points apply unchanged.[cite:1][cite:2]
- Consider splitting true freshmen from international freshmen or late-arriving international prospects if those player types function differently in your dataset.[cite:2]
- Add coaching-change flags, because low continuity may sometimes be a consequence of a coaching transition rather than a strategic preference; this causality concern is raised directly in discussion of the earlier study.[cite:2]
- Consider separate models for high-major WBB, all power-conference WBB, and mid-major WBB, since the article itself limits scope because roster-building environments differ by resource tier.[cite:2]
- Add returning-star continuity measures, such as returning share of team minutes from players above a certain player-value threshold, because Dusty May’s quote in the update suggests the key is retaining the **right** players, not simply maximizing raw continuity.[cite:1]

### A stronger WBB version of the metric

For WBB, a useful refinement would be to decompose returner continuity into at least two pieces:

- Returner minutes share.
- Returner value share, such as the share of projected minutes or projected wins above replacement coming from returning players.[cite:1][cite:2]

That adjustment aligns with the article’s updated lesson. Michigan’s 2026 men’s title team had low raw continuity but elite incoming transfer talent, while the broader takeaway is that talent acquisition can offset low retention for some teams.[cite:1]

## Practical replication workflow

### Step-by-step

1. Build a player-season master table for all WBB teams you want to study.
2. Label each player as returner, transfer, freshman, or other newcomer category.
3. Create a preseason player projection metric, either from your own model or a public rating system, then convert it into a team preseason roster score using projected minutes weights.[cite:2]
4. Aggregate actual in-season minutes by player-source category.
5. Merge in final team ratings, NCAA tournament seeding, and rounds reached.
6. Standardize continuity within season by calculating the league or high-major median returner-minutes share.[cite:1]
7. Run two tracks of analysis: general team success and title-contender success.[cite:1][cite:2]
8. Compare results across eras, especially pre-portal, early-portal, and current portal/NIL seasons, because the update’s main argument is that the relationship changed as continuity rates dropped.[cite:1]

### Minimal reproducible outputs

At minimum, recreate these outputs:

- Scatterplot of preseason roster score vs end-of-season rating.[cite:1][cite:2]
- Scatterplot of returner-minutes share vs end-of-season rating.[cite:2]
- Scatterplot of transfer-minutes share vs end-of-season rating.[cite:2]
- Bucketed comparison of similarly talented teams above vs below a continuity threshold.[cite:2]
- Table of Final Four teams, title teams, and No. 1 seeds with preseason talent rank and returner-minutes share relative to the season median.[cite:1]

## Interpretation cautions

- The published articles are primarily observational and comparative; they do not prove a purely causal effect of continuity.[cite:1][cite:2]
- One comment highlighted a key alternative explanation: bad teams or coaching-change teams may have many transfers because they were already unstable, not necessarily the other way around.[cite:2]
- Because average continuity has dropped over time, season-relative benchmarks are more informative than raw thresholds alone.[cite:1]
- The update suggests the modern answer is conditional: chase talent first, then view continuity as a stronger differentiator among teams already good enough to contend.[cite:1]

## Best working hypothesis for WBB

A strong WBB adaptation would test two separate hypotheses rather than one broad question:[cite:1][cite:2]

- **Floor hypothesis:** among all teams, continuity may no longer strongly predict outperforming expectation once preseason talent is accounted for.[cite:1]
- **Ceiling hypothesis:** among top-tier preseason teams, above-average continuity may still increase the odds of Final Four and title-level outcomes.[cite:1]

That two-part framing matches the updated men’s result more closely than the earlier one-size-fits-all “50% returners” conclusion.[cite:1][cite:2]
