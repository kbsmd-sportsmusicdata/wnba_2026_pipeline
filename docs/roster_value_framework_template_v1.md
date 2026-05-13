# WNBA Roster Value Framework — Master Template v1
### Comprehensive Starting Point for Player Analysis, Case Studies, and Roster Evaluation

**How to use this document:** This is the all-encompassing template. Every stat, section, and hidden value category that could ever be relevant lives here. When building a specific deliverable (a player case study, a team roster grade, a market analysis), pick the sections and metrics that serve the analytical question — do not use everything at once. Annotations throughout indicate data availability, calculability, and suggested priority per use case.

---

## Part 1 — Narrative Framework

### Section 0 — Why This Player / Roster Right Now
**Narrative job:** Open with stakes. One tight paragraph + one hard-number hook.

Answer:
- Who is this player (position, team, years in league)?
- What makes them interesting *right now* (contract year, breakout, role change, market inefficiency, expansion pressure)?
- What is the central argument or question this analysis will answer?

**Hook options:** Current salary figure, metric rank, year-over-year production jump, salary vs comparable player gap.

*No metrics required in this section — it is editorial framing only.*

---

### Section 1 — Contract Snapshot and Market Framing
**Narrative job:** Establish the financial stakes before any skill discussion.

**Data source:** contracts_2026, players_master, market_benchmarks

| Field | Source column | Status |
|---|---|---|
| Current salary | salary | AVAILABLE |
| Cap hit | cap_hit | AVAILABLE |
| Salary tier | salary_tier | AVAILABLE |
| Salary as % of team cap | salary_as_pct_cap | AVAILABLE |
| Contract type / status | contract_icon, status_full | AVAILABLE |
| Option flag | option_flag | AVAILABLE |
| Free agent status / next status | next_status | AVAILABLE |
| Guaranteed salary | guaranteed_salary | AVAILABLE |
| Historical salary (prior seasons) | historical_salary_* in value_scores | AVAILABLE |
| Expected salary (model) | expected_salary | AVAILABLE (provisional) |
| Recommended salary range | recommended_salary_low/high | AVAILABLE (provisional) |
| Market discount % vs comps | market_discount_pct | AVAILABLE (provisional) |

**Key callout visuals:**
- Single-value contract callout card (salary + tier + status)
- Year-over-year salary history bar
- League minimum / median salary reference line for context

---

### Section 2 — League-Wide Salary vs Impact Positioning
**Narrative job:** Show where the player sits in the full market before the reader hits any skill analysis.

**Data source:** value_scores, players_master, market_benchmarks

| Field | Source column | Status |
|---|---|---|
| Player value score (0-100) | value_score | AVAILABLE (provisional) |
| Value label | value_label | AVAILABLE (provisional) |
| Undervalued / hidden talent / overvalued flags | undervalued_flag, hidden_talent_flag, overvalued_flag | AVAILABLE |
| Production score | production_score | AVAILABLE (provisional) |
| Salary efficiency score | salary_efficiency_score | AVAILABLE (provisional) |

**Visual:** Scatterplot — X: salary, Y: value_score or production_score; color by salary_tier; highlight featured player; filter: MPG >= 10.

---

### Section 3 — Same-Salary Peers
**Narrative job:** Show surplus value against players earning similar money. Comes BEFORE the skill breakdown.

**Data source:** comparable_players, value_scores, players_master

| Field | Source column | Status |
|---|---|---|
| Comparable player name / team | comparable_player_name, comparable_team_name | AVAILABLE |
| Similarity score | similarity_score | AVAILABLE (provisional) |
| Same salary tier flag | same_salary_tier_flag | AVAILABLE |
| Salary gap vs comp | salary_gap, salary_gap_pct | AVAILABLE |
| Value score gap | onoff_gap, playoff_performance_gap | AVAILABLE |
| Comp basis | comp_basis | AVAILABLE |

**Visual:** Ranked table — players at similar salary tier, sorted by value_score descending. Highlight featured player.

---

### Section 4 — Same-Production Peers
**Narrative job:** Show salary gap against players producing at similar levels.

**Data source:** comparable_players, value_scores

Same fields as Section 3, filtered by same_archetype_family_flag = True and sorted by salary_gap descending.

**Visual:** Ranked table or bar chart — players near featured player's production_score, with salary alongside. Add salary delta column.

---

### Section 5 — Percentile Profile and Statistical Comp Table
**Narrative job:** Bridge from abstract value to basketball traits.

**Data source:** advanced_player_metrics, comparable_players, player_archetypes

| Field | Source column | Status |
|---|---|---|
| TS% percentile (position) | ts_pctile_pos | AVAILABLE |
| Usage percentile (position) | usage_pctile_pos | AVAILABLE |
| Assist rate percentile (position) | ast_pctile_pos | AVAILABLE |
| Turnover rate percentile (position) | tov_pctile_pos | AVAILABLE |
| Rebound rate percentile (position) | reb_pctile_pos | AVAILABLE |
| Steal rate percentile (position) | stl_pctile_pos | AVAILABLE |
| Block rate percentile (position) | blk_pctile_pos | AVAILABLE |
| Archetype / role | archetype_label, archetype_family, role_band | AVAILABLE |
| Skill signature | skill_signature | AVAILABLE |

**Visual:** Heatmap percentile table — rows: featured player + 3-5 comps; columns: salary, key percentiles (TS%, AST%, TOV%, STL%, overall production), similarity score; color scale 0-100.

---

## Part 2 — Hidden Value Categories and Skill Sections

Priority ratings: HIGH (feature in most analyses) | MED (feature when relevant to player type) | GAP (needs new pull or not available for WNBA)

---

### Hidden Value Category 1 — Playmaking Stability
**Basketball question:** Does this player organize possessions, create for teammates, and protect the ball?

**Data sources:** advanced_player_metrics, player_season_stats, player totals (pbpstats)

#### Per-40 / Rate Stats
| Metric | Source | Status | Priority |
|---|---|---|---|
| Assist rate (AST%) | ast_pct in advanced_player_metrics | AVAILABLE | HIGH |
| Assist rate percentile (pos) | ast_pctile_pos | AVAILABLE | HIGH |
| Turnover rate (TOV%) | tov_pct | AVAILABLE | HIGH |
| Turnover rate percentile (pos) | tov_pctile_pos | AVAILABLE | HIGH |
| AST:TOV ratio | ast_tov_ratio | AVAILABLE | HIGH |
| Assists per 40 min | ast_per_40 | AVAILABLE | HIGH |
| Assists (season total) | assists in player_season_stats | AVAILABLE | HIGH |

#### Zone-Level Assist Breakdown
Tells the story of what kind of scoring this player creates — rim creation vs spacing gravity vs mid-range.

| Metric | Source | Status | Priority |
|---|---|---|---|
| Total assists | assists in player totals | AVAILABLE (2023-2025 RS + PO) | HIGH |
| Arc3 assists | arc3_assists | AVAILABLE | HIGH |
| Corner3 assists | corner3_assists | AVAILABLE | HIGH |
| At-rim assists | at_rim_assists | AVAILABLE | HIGH |
| Short mid-range assists | short_mid_range_assists | AVAILABLE | MED |
| Long mid-range assists | long_mid_range_assists | AVAILABLE | MED |
| 2PT assists | two_pt_assists | AVAILABLE | MED |
| 3PT assists | three_pt_assists | AVAILABLE | HIGH |
| Assist points created | assist_points | AVAILABLE | HIGH |

#### Assist Network (Passer to Scorer Pairs)
| Metric | Source | Status | Priority |
|---|---|---|---|
| Passer to scorer pairs (full season) | Requires get-shots EntityType=Player per player | GAP — needs new pull | MED |
| Passer to scorer pairs (clutch only) | Shot event files in wnba_shot_pace/normalized/get-shots | AVAILABLE for clutch situations only | MED |
| WORKAROUND: Zone-level assist breakdown as proxy | player totals | AVAILABLE | HIGH |

GAP NOTE: Full-season assist network graphs require a player-level shot pull via get-shots?EntityType=Player&EntityId=X. The current data has team-level clutch shot events (4Q/OT, margin +-3, 300-120 sec) that include assist_player to player pairs. For the Cloud case study, the zone-level assist breakdown is a strong substitute.

#### On/Off Playmaking Impact
| Metric | Source | Status | Priority |
|---|---|---|---|
| Team TOV% with player on vs off | team_tov_pct_diff in onoff_metrics | AVAILABLE (2025 RS+PO, 2024 PO) | HIGH |
| Team AST% with player on vs off | team_ast_pct_diff | AVAILABLE | HIGH |
| Assists per 100 poss on/off | assists_per100_poss_on/off/on_off | AVAILABLE | HIGH |

**Suggested ranked table columns:** rank | player | assists per 100 poss | turnovers per 100 poss | AST:TOV ratio | min filter: 600+

---

### Hidden Value Category 2 — Scoring Efficiency and Shot Profile
**Basketball question:** Where do shots come from, how efficient are they, and why does that profile matter in team context?

**Data sources:** advanced_player_metrics, player totals (pbpstats)

#### Shot Zone Distribution
Core shot profile breakdown — equivalent to the PPF shot distribution graphic.

| Metric | Source | Status | Priority |
|---|---|---|---|
| At-rim FGM/FGA | at_rim_fgm, at_rim_fga in player totals | AVAILABLE (2023-2025) | HIGH |
| At-rim frequency (% of total FGA) | at_rim_frequency | AVAILABLE | HIGH |
| At-rim accuracy | at_rim_accuracy | AVAILABLE | HIGH |
| Short mid-range FGM/FGA | short_mid_range_fgm/fga | AVAILABLE | MED |
| Short mid-range frequency | short_mid_range_frequency | AVAILABLE | MED |
| Long mid-range FGM/FGA | long_mid_range_fgm/fga | AVAILABLE | MED |
| Long mid-range frequency | long_mid_range_frequency | AVAILABLE | MED |
| Corner3 FGM/FGA | corner3_fgm/fga | AVAILABLE | HIGH |
| Corner3 frequency | corner3_frequency | AVAILABLE | HIGH |
| Corner3 accuracy | corner3_accuracy | AVAILABLE | HIGH |
| Arc3 FGM/FGA | arc3_fgm/fga | AVAILABLE | HIGH |
| Arc3 frequency | arc3_frequency | AVAILABLE | HIGH |
| Arc3 accuracy | arc3_accuracy | AVAILABLE | HIGH |
| 3PT attempt rate (3PAr) | three_par in advanced_player_metrics | AVAILABLE | HIGH |
| Rim rate | rim_rate | AVAILABLE | HIGH |
| Mid-range rate | midrange_rate | AVAILABLE | MED |
| Average 2PT shot distance | avg2pt_shot_distance in onoff_metrics | AVAILABLE | MED |
| Shot quality average | shot_quality_avg in player totals | AVAILABLE | MED |

**Suggested visual:** Segmented bar or donut showing share of FGA from each zone: at_rim / short_mid / long_mid / corner3 / arc3. Add FTA as a separate segment.

#### Efficiency Metrics
| Metric | Source | Status | Priority |
|---|---|---|---|
| True shooting % (TS%) | ts_pct in advanced_player_metrics | AVAILABLE | HIGH |
| TS% percentile (position) | ts_pctile_pos | AVAILABLE | HIGH |
| Effective FG% (eFG%) | efg_pct | AVAILABLE | HIGH |
| Points per 40 min | pts_per_40 | AVAILABLE | HIGH |
| Usage rate | usage_pct | AVAILABLE | HIGH |
| Usage percentile (position) | usage_pctile_pos | AVAILABLE | HIGH |
| Assisted 2s % | assisted2s_pct in player totals | AVAILABLE | MED |
| Assisted 3s % | assisted3s_pct | AVAILABLE | MED |

#### FT Scoring Efficiency
Key for players whose scoring comes disproportionately from the free throw line.

| Metric | Source | Status | Priority |
|---|---|---|---|
| FTA (season total) | fta in player_season_stats and player totals | AVAILABLE | HIGH |
| FT% | ft_pct in player_season_stats | AVAILABLE | HIGH |
| FT points | ft_points in player totals | AVAILABLE | HIGH |
| FT points as % of total points | CALCULABLE: ft_points / points | CALCULABLE | HIGH |
| FTAs per 100 poss | CALCULABLE: fta / off_poss * 100 | CALCULABLE | HIGH |
| FT rate (FTA/FGA) | ftr in advanced_player_metrics | AVAILABLE | HIGH |
| 2PT shooting fouls drawn | two_pt_shooting_fouls_drawn in player totals | AVAILABLE | MED |
| 3PT shooting fouls drawn | three_pt_shooting_fouls_drawn | AVAILABLE | MED |

**Suggested ranked table columns:** rank | player | FTs per 100 poss | points per 100 poss | FT% of total points | min filter

---

### Hidden Value Category 3 — Defensive Disruption
**Basketball question:** What defensive events does this player generate, and what do they do to opponent efficiency?

**Data sources:** advanced_player_metrics, onoff_metrics, player totals (pbpstats)

#### Individual Defensive Event Rates
| Metric | Source | Status | Priority |
|---|---|---|---|
| Steal rate (STL%) | stl_pct in advanced_player_metrics | AVAILABLE | HIGH |
| Steal rate percentile (position) | stl_pctile_pos | AVAILABLE | HIGH |
| Block rate (BLK%) | blk_pct | AVAILABLE | HIGH |
| Block rate percentile (position) | blk_pctile_pos | AVAILABLE | HIGH |
| Steals per 40 | stl_per_40 | AVAILABLE | HIGH |
| Blocks per 40 | blk_per_40 | AVAILABLE | HIGH |
| Steals (season total) | steals in player_season_stats | AVAILABLE | HIGH |
| Bad pass steals | bad_pass_steals in player totals | AVAILABLE | MED |
| Lost ball steals | lost_ball_steals | AVAILABLE | MED |
| Blocks recovered (tip kept alive) | recovered_blocks in player totals | AVAILABLE | MED |

#### Defensive Events NOT Available for WNBA
| Metric | Status | Notes |
|---|---|---|
| Deflections | GAP | pbpstats does not track WNBA deflections |
| Loose balls recovered | GAP | Not in any current data source |
| Contested shots (defensive) | GAP | No WNBA matchup/tracking data |
| Defensive matchup assignments | GAP | Requires Synergy or Second Spectrum |
| Opponent FG% at matchup | GAP | — |

#### On/Off Defensive Impact
| Metric | Source | Status | Priority |
|---|---|---|---|
| Defensive rating differential (on-off) | on_off_drtg_diff in onoff_metrics | AVAILABLE (2025 RS+PO, 2024 PO) | HIGH |
| Opponent TS% on vs off | opp_ts_diff | AVAILABLE | HIGH |
| Opponent rim rate on vs off | opp_rim_rate_diff | AVAILABLE | HIGH |
| Opponent 3PA rate on vs off | opp_3pa_rate_diff | AVAILABLE | HIGH |
| Opponent live-ball TOV% on vs off | live_ball_turnover_pct_on/off/on_off | AVAILABLE | MED |
| Def rebound rate on vs off | def_rebound_pct_on_off | AVAILABLE | MED |

**Suggested visual options:** Radar chart (STL%, BLK%, opp TS diff, opp rim rate diff, on/off drtg diff), or percentile bar chart, or ranked event-rate table.

---

### Hidden Value Category 4 — Floor Spacing and Gravity
**Basketball question:** Does the player's presence open the floor for teammates even without scoring?

**Data sources:** advanced_player_metrics, onoff_metrics

| Metric | Source | Status | Priority |
|---|---|---|---|
| 3PT attempt rate (3PAr) | three_par in advanced_player_metrics | AVAILABLE | HIGH |
| Arc3 frequency | arc3_frequency in player totals | AVAILABLE | HIGH |
| Corner3 frequency | corner3_frequency | AVAILABLE | HIGH |
| 3PT% (team) with player on vs off | team_3pt_pct_diff in onoff_metrics | AVAILABLE | HIGH |
| 3PA rate (team) with player on vs off | team_3pa_rate_diff | AVAILABLE | HIGH |
| Team eFG% with player on vs off | team_efg_diff | AVAILABLE | HIGH |
| Team TS% with player on vs off | team_ts_diff | AVAILABLE | HIGH |
| Catch-and-shoot gravity | GAP | Requires tracking/Synergy |
| Space creation per touch | GAP | Requires touch/tracking data |

NOTE: Floor spacing is best told through on/off eFG% and 3PA rate changes. If the team shoots better and takes more 3s with the player on the floor — even if the player isn't a shooter — that signals gravity.

---

### Hidden Value Category 5 — Possession Creation
**Basketball question:** Does the player create extra possessions through offensive rebounding, steals, or forcing live turnovers?

**Data sources:** advanced_player_metrics, player totals

| Metric | Source | Status | Priority |
|---|---|---|---|
| Offensive rebound rate (OREB%) | oreb_pct in advanced_player_metrics | AVAILABLE | HIGH |
| Offensive rebounds per 40 | CALCULABLE from player_season_stats | CALCULABLE | HIGH |
| Off rebound rate on vs off | off_rebound_pct_on_off in onoff_metrics | AVAILABLE | HIGH |
| Steal rate | stl_pct (see Category 3) | AVAILABLE | HIGH |
| Bad pass steals | bad_pass_steals in player totals | AVAILABLE | MED |
| Lost ball steals | lost_ball_steals | AVAILABLE | MED |
| Second chance points generated (team) | second_chance_points_pct_on_off in onoff_metrics | AVAILABLE | MED |
| Loose ball recoveries | GAP | — |
| Deflections | GAP | — |

---

### Hidden Value Category 6 — Lineup Portability and On/Off Impact
**Basketball question:** How much better is the team with this player on the court?

**Data sources:** onoff_metrics, player_archetypes

#### Core On/Off Metrics
| Metric | Source | Status | Priority |
|---|---|---|---|
| Net rating on | on_net_rating | AVAILABLE (2025 RS+PO, 2024 PO) | HIGH |
| Net rating off | off_net_rating | AVAILABLE | HIGH |
| Net rating differential (on minus off) | net_rating_diff | AVAILABLE | HIGH |
| Offensive rating differential | on_off_ortg_diff | AVAILABLE | HIGH |
| Defensive rating differential | on_off_drtg_diff | AVAILABLE | HIGH |
| On/off impact score (composite) | onoff_impact_score in player_archetypes | AVAILABLE | HIGH |
| On/off sample flag | onoff_sample_flag | AVAILABLE | HIGH |

#### Season-Specific On/Off Splits (stored in player_archetypes)
| Field | Status | Notes |
|---|---|---|
| reg_2025 on/off splits | AVAILABLE | 2025 regular season |
| playoffs_2025 on/off splits | AVAILABLE | 2025 playoffs |
| reg_2024 on/off splits | PROVISIONAL — missing 2024 RS on/off | Known gap; backfill pending |
| playoffs_2024 on/off splits | AVAILABLE | 2024 playoffs |
| 2023 regular season on/off | NOT COLLECTED | — |

#### Team Context On/Off
| Metric | Source | Status | Priority |
|---|---|---|---|
| Team TS% on vs off | team_ts_diff | AVAILABLE | HIGH |
| Team eFG% on vs off | team_efg_diff | AVAILABLE | HIGH |
| Team 3PT% on vs off | team_3pt_pct_diff | AVAILABLE | HIGH |
| Team 3PA rate on vs off | team_3pa_rate_diff | AVAILABLE | HIGH |
| Team TOV% on vs off | team_tov_pct_diff | AVAILABLE | HIGH |
| Team AST% on vs off | team_ast_pct_diff | AVAILABLE | HIGH |
| Team OREB% on vs off | team_oreb_pct_diff | AVAILABLE | HIGH |
| Team DREB% on vs off | team_dreb_pct_diff | AVAILABLE | HIGH |
| Pace on vs off | pace_diff | AVAILABLE | MED |

#### Lineup-Specific Portability (Gaps)
| Metric | Status | Notes |
|---|---|---|
| Performance with specific star players | GAP | Requires lineup combination data pull |
| Performance by lineup type (starter vs bench) | GAP | — |
| Lineup +/- by pairing | GAP | — |

**Suggested visual:** Slope chart or on/off bar chart — team net rating with player on vs off, split by season/season_type.

---

### Hidden Value Category 7 — Playoff Utility and High-Leverage Experience
**Basketball question:** Does the player's production hold up in high-stakes situations?

**Data sources:** playoff_experience, player_archetypes, onoff_metrics (playoff slices)

| Metric | Source | Status | Priority |
|---|---|---|---|
| Career playoff games | playoff_games_career | AVAILABLE | HIGH |
| Career playoff minutes | playoff_minutes_career | AVAILABLE | HIGH |
| Career playoff MPG | playoff_mpg_career | AVAILABLE | HIGH |
| Finals appearances | finals_games | AVAILABLE | HIGH |
| Championships | championship_count | AVAILABLE | HIGH |
| Playoff games last 3 years | playoff_last_3_years_games | AVAILABLE | HIGH |
| Playoff minutes last 3 years | playoff_last_3_years_minutes | AVAILABLE | HIGH |
| High-leverage experience score (0-100) | high_leverage_experience_score | AVAILABLE | HIGH |
| Playoff TS% (2025) | playoffs_2025_ts_pct in player_archetypes | AVAILABLE | HIGH |
| Playoff TS% percentile | playoff_ts_pct_percentile | AVAILABLE | HIGH |
| Playoff TS% vs regular season delta | playoff_ts_pct_vs_reg_delta | AVAILABLE | HIGH |
| Playoff performance flag | playoff_performance_flag | AVAILABLE | HIGH |
| Playoff performance bonus (score) | playoff_performance_bonus | AVAILABLE | HIGH |
| Playoff on/off net rating diff (2025) | playoffs_2025_net_rating_diff | AVAILABLE | HIGH |
| Playoff on/off net rating diff (2024) | playoffs_2024_net_rating_diff | AVAILABLE | HIGH |
| Playoff on/off impact score | playoffs_2025_onoff_impact_score | AVAILABLE | HIGH |

#### Clutch Performance (Limited Coverage)
| Metric | Source | Status | Priority |
|---|---|---|---|
| Close-game shot behavior by zone | Shot event files (4Q/OT, +-3 margin, 300-120 sec) | AVAILABLE at team level; filter by player name field | MED |
| Individual close-game event stats | GAP at player level | Requires player-level shot pull | MED |

---

### Hidden Value Category 8 — Scalability
**Basketball question:** Is this player efficient in their current role, and does production suggest upside with a larger role?

**Data sources:** value_scores, advanced_player_metrics, player_archetypes

| Metric | Source | Status | Priority |
|---|---|---|---|
| Scalability score | Check value_scores table | PROVISIONAL | HIGH |
| Usage rate vs TS% relationship | Cross-reference from advanced_player_metrics | CALCULABLE | HIGH |
| Per-40 vs per-game efficiency gap | pts_per_40 vs ppg | CALCULABLE | MED |
| Production at current usage band | ts_pct at usage_pct band | CALCULABLE | HIGH |
| Year-over-year production trend (2023-2025) | player_season_stats across seasons | CALCULABLE | HIGH |
| Role band | role_band in player_archetypes | AVAILABLE | HIGH |

---

## Part 3 — Salary and Market Analysis Sections

### Section A — Comparable Player Analysis
**Data source:** comparable_players, value_scores, market_benchmarks

Comp types covered:
1. Statistical comps — same production profile (similarity_score)
2. Role/archetype comps — same_archetype_family_flag
3. Age/experience comps — via service_band, age_2026 filters
4. Contract comps — same_salary_tier_flag, salary_gap
5. Market demand comps — players signed quickly, expansion protected/selected (transactions_2026, expansion_draft_2026)

**Key comp table columns:** player | age | team | archetype | salary | TS% | AST% | STL% | on/off net diff | similarity score

---

### Section B — Salary Value Score Breakdown
**Data source:** value_scores

| Field | Source | Status |
|---|---|---|
| Production percentile score | production_score | AVAILABLE |
| Salary efficiency score | salary_efficiency_score | AVAILABLE |
| Scarcity score | scarcity_score | AVAILABLE |
| Playoff performance score | playoff_performance_score | AVAILABLE |
| Playoff score | playoff_score | AVAILABLE |
| On/off score | onoff_score | AVAILABLE |
| Final value score | value_score | AVAILABLE |
| Expected salary | expected_salary | AVAILABLE |
| Salary gap | salary_gap, salary_gap_pct | AVAILABLE |
| Market discount % | market_discount_pct | AVAILABLE |
| Recommended salary range | recommended_salary_low, recommended_salary_high | AVAILABLE |

---

### Section C — Market Benchmarks by Archetype / Role / Salary Tier
**Data source:** market_benchmarks

Available: median salary, median value score, median TS%/usage/mpg, undervalued/hidden talent/overvalued rates, recommended salary range — all by archetype_family + role_band + salary_tier.

---

### Section D — Age and Experience Band Analysis
**Narrative job:** Show how players at this career stage are being compensated. Essential for veteran case studies.

**Data source:** players_master, value_scores, contracts_2026

| Field | Source | Status |
|---|---|---|
| Age | age_2026 | AVAILABLE |
| Years of service | years_service | AVAILABLE |
| Service band | service_band | AVAILABLE |
| Salary vs age band average | CALCULABLE from value_scores + players_master | CALCULABLE |
| Salary vs experience band average | Same | CALCULABLE |

---

### Section E — Market Demand Analysis (Case Study Use)
**Narrative job:** Show whether the market wants players like this one — did similar profiles get signed, protected, or paid quickly?

**Data source:** transactions_2026, expansion_draft_2026, comparable_players

| Field | Source | Status |
|---|---|---|
| Transaction type (signed, traded, waived) | transactions_2026 | AVAILABLE |
| Expansion draft protected / selected / unprotected | expansion_draft_2026 | AVAILABLE |
| Time to signing (market velocity proxy) | DERIVABLE from transaction dates | CALCULABLE |

---

## Part 4 — Roster-Level Sections

### Team Roster Grade
**Data source:** team_roster_grades

Available: roster_grade (A-F), cap_efficiency_score, balance_score, continuity_score, undervalued/hidden_talent/overvalued player counts, archetype_diversity, value_per_million.

### Team Roster Distribution
**Data source:** team_rosters, players_master, player_archetypes

Available: position group distribution, archetype distribution, salary tier distribution, age band distribution (calculable), scarcity gap flagging.

### 2024-2026 Market Shift Analysis
**Data source:** team_roster_history, contracts_2026, historical salary file

Available: year-over-year roster composition, salary tier distribution shifts, average age/experience trends, veteran/mid-tier compression signals — all calculable across 2023-2026.

---

## Part 5 — Closing Section: Projection and Contract Implication

**Narrative job:** Return to the opening thesis. Answer the practical question raised in Section 0.

**Data source:** value_scores, comparable_players, market_benchmarks

Required outputs:
- Fair salary range table: conservative range | market-fair range | premium fit range | overpay threshold
- Closest comp contracts and what they mean for the argument
- Team fit implications (which roster types value this player most)
- Risk factors (age curve, injury history, sample size, role dependency)
- One-paragraph verdict that closes the loop opened in Section 0

---

## Part 6 — Data Gap Summary

| Gap | Severity | Workaround |
|---|---|---|
| Full-season assist network (passer to scorer pairs) | MED | Use zone-level assist breakdown (arc3/corner3/rim assists) as proxy. Full fix: pull get-shots?EntityType=Player for each player. |
| Deflections / loose balls | MED | Use steal rate + on/off opp TS% + opp live-ball TOV% as combined defensive event signal |
| Defensive matchup assignments | MED | Use opp_ts_diff, opp_rim_rate_diff, opp_3pa_rate_diff |
| Touches / ball movement | MED | Use assist_points + zone-level assists + usage rate as proxy |
| 2024 Regular Season on/off | MED | Use 2025 RS + 2024/2025 PO; flag as provisional. Backfill pending. |
| 2023 on/off (any) | LOW | Use 2023 totals/advanced stats only |
| Lineup-specific pair data | LOW | Use overall on/off net diff; note limitation |
| Contested shots (defensive) | MED | Use block rate + on/off opp accuracy metrics |
| Clutch individual player stats | LOW | Filter team-level shot event files by player name field |
| Tracking/gravity/touch metrics | LOW | Use 3PAr on/off and team eFG% on/off as gravity proxies |

---

## Part 7 — Template Usage Guide by Deliverable Type

### Player Case Study (e.g., Natasha Cloud)
Recommended section order: 0 > 1 > 2 > 3 > 4 > 5 > Playmaking > Defense > Scoring efficiency (if relevant) > Playoff utility > On/off lineup > Demand Analysis > Projection

Primary hidden value categories: Playmaking Stability, Defensive Disruption, Playoff Utility
Secondary: Floor Spacing (on/off 3PA rate), Scalability
Skip or minimize for Cloud: Possession Creation (not an OREB player), Shot profile center (not a volume scorer; FT profile more relevant than zone breakdown)

### Roster Value Grade (Team-Level)
Recommended section order: Team Roster Grade > Archetype Distribution > Age Distribution > Salary Tier Distribution > Hidden Talent Flagging > Cap Efficiency

### Market Structure Analysis
Recommended section order: 2024-2026 Market Shift > Salary Tier Distribution > Position Scarcity Map > Pricing-Out Analysis > Veteran vs Rookie Demand Signals

### Hidden Gems Watchlist
Recommended section order: League-Wide Salary vs Impact > Hidden Talent Flagged Players > Per-Archetype Benchmarks > Same-Salary Peer Tables > Ranked Value Scores

---

*Template version: v1 | May 2026*
*Built from: player_season_stats, advanced_player_metrics, onoff_metrics, player_archetypes, value_scores, comparable_players, market_benchmarks, playoff_experience, contracts_2026, players_master, team_roster_grades, team_rosters, transactions_2026, expansion_draft_2026 + pbpstats player totals (2023-2025 RS+PO) + shot event files (team-level, clutch window)*
