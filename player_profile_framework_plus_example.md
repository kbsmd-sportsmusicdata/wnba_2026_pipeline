# Player Profile Framework for Deep-Dive Player Analysis

## Purpose and editorial thesis

This framework reverse-engineers the narrative and analytical flow used in Chris Gunther's *Veronica Burton* profile and translates it into a reusable player deep-dive template.[cite:1] The article is built around a clear thesis: the featured player is materially underpaid relative to on-court impact, and the rest of the piece assembles evidence that supports that valuation argument from multiple angles.[cite:1]

## Narrative flow

### 1. Open with the player, team context, and contract hook

Start with a concise identification block: player name, position, team, years in the league, and current contract status.[cite:1] The article quickly establishes stakes by pairing Burton's identity with a low salary figure and framing that salary as both a league-wide labor issue and a team-value inefficiency.[cite:1]

### 2. Frame the market inefficiency before the skill breakdown

Before discussing skills, show why the player matters economically.[cite:1] In the article, this comes through a salary-versus-value framing, then a restricted-free-agency setup, then comps to higher-paid guards to prime the reader for the central argument that production exceeds compensation.[cite:1]

### 3. Use peer comparisons to validate the valuation claim

After the thesis, place the player among league peers using both broad league context and narrow comps.[cite:1] The article moves from a leaguewide salary-value scatter, to a percentile comp table, to salary-band and RAPTOR-adjacent peer tables, creating a layered argument that Burton is mispriced from several analytical angles.[cite:1]

### 4. Transition from valuation to basketball reasons

Once the contract/value gap is established, shift to the question: *why do the metrics like this player so much?*[cite:1] This pivot is important because it moves the story from abstract value to observable basketball traits, which makes the analysis persuasive to readers who do not fully trust all-in-one metrics alone.[cite:1]

### 5. Break the profile into role-based strengths

The article then uses role-forward sections rather than a generic stat dump: elite passer, efficient scorer, defensive impact, and all-around lineup value.[cite:1] This structure works because each section links a basketball trait to one or two key metrics and then interprets what those numbers mean in team context.[cite:1]

### 6. Close with projection and contract implication

The final paragraphs return to the original thesis: Burton's expanded role, improved production, and winning impact justify a substantial raise.[cite:1] That closing loop makes the piece feel cohesive because the ending resolves the opening contract question with evidence gathered throughout the analysis.[cite:1]

## Reusable section order

Use this section order for a similar player deep dive.[cite:1]

1. Player identification and why this player now.[cite:1]
2. Contract snapshot and salary hook.[cite:1]
3. Leaguewide salary versus impact visual.[cite:1]
4. Historical or seasonal statistical comps.[cite:1]
5. Same-salary peer comparison.[cite:1]
6. Same-production salary comparison.[cite:1]
7. Skill section 1: primary offensive value creation.[cite:1]
8. Skill section 2: scoring efficiency and shot profile.[cite:1]
9. Skill section 3: defensive impact.[cite:1]
10. Skill section 4: lineup/on-off and role value.[cite:1]
11. Projection: future salary, role, and team fit.[cite:1]

## Section-by-section framework

| Section | Narrative job | Recommended questions to answer | Visual needed | Chart type | Metrics / encoding |
|---|---|---|---|---|---|
| Player intro | Introduce the player and define the stakes | Who is the player, what role do they play, why are they worth profiling now? | Optional | Hero image or none | No required metrics; can include position, age, team, years pro.[cite:1] |
| Contract hook | Establish the market inefficiency | What is the player making, what is their contract status, and why is that notable? | Yes | Single-value callout card or annotated salary graphic | Salary, contract type, years in league, free-agent status; optionally add league minimum or median salary for context.[cite:1] |
| League value positioning | Show underpayment or overperformance in broad context | Where does the player rank in impact relative to salary? | Yes | Scatterplot | X-axis: average annual value or current salary; y-axis: all-in-one impact metric such as RAPTOR, EPM, WAR, or win shares per 40/48; color: contract tier; highlight featured player; filter: minutes threshold.[cite:1] |
| Player comps | Show who the player statistically resembles | Which players from current or prior seasons look most similar by production profile? | Yes | Heatmap table or percentile comparison table | Rows: featured player plus 3-5 comps; columns: age, salary, offensive metric, points per 100, assist rate, defensive metric, overall impact metric, similarity score; color scale by percentile or z-score.[cite:1] |
| Same-salary peers | Show surplus value against players making similar money | How does the player compare with others in the same salary band? | Yes | Ranked table or bar chart | Rows: players at similar AAV; columns: player, impact metric, AAV; optional sort by impact metric descending.[cite:1] |
| Same-production peers | Show salary gap against players producing at similar levels | Which players with similar impact make much more? | Yes | Ranked table or bar chart | Rows: players near the featured player's impact metric; columns: player, impact metric, AAV; optional salary delta column.[cite:1] |
| Offensive engine / playmaking | Explain how the player drives offense | Does the player organize possessions, create for teammates, and limit mistakes? | Yes | Assist network plus ranked table | Visual 1: network graph with node size by touches or assists created, edges by assist connections among teammates; Visual 2 table with assists per 100, turnovers per 100, AST:TO ratio, rank, minutes threshold.[cite:1] |
| Scoring efficiency | Show selective and efficient scoring | Where do shots come from, and how efficient are they? | Yes | Shot distribution graphic plus ranked table | Visual 1: shot profile donut, waffle, or segmented bar using share of attempts or points from rim/paint, 3PT, FT, midrange; Visual 2 ranked table with free throws per 100, points per 100, FT share of points, rank.[cite:1] |
| Defensive impact | Translate all-in-one defensive value into tangible events | What events or lineup outcomes support the player's defensive reputation? | Optional but recommended | Radar, percentile table, or event-rate bar chart | Steal rate, block rate, stocks per 100, deflections, matchup difficulty, opponent turnover rate when on court, defensive RAPTOR or similar metric.[cite:1] |
| Lineup impact / role value | Show total team effect beyond box score | How much better is the team with this player on court, and in what ways? | Optional but recommended | On/off bar chart or slope chart | Team net rating on vs off, offensive rating on vs off, defensive rating on vs off, team 3PA rate, 3P%, rebounding rate, assist rate with player on vs off.[cite:1] |
| Projection and contract implication | Bring the story back to valuation | What should the next contract or market value look like? | Optional | Comp table or forecast band | Comparable player salaries, projected AAV range, age, role archetype, prior trend line in minutes and production.[cite:1] |

## Visual inventory from the Burton article

| Article moment | What the visual does | Chart type | Metrics / fields used |
|---|---|---|---|
| Burton producing above salary | Shows the player outperforming contract level relative to league peers.[cite:1] | Scatterplot.[cite:1] | X-axis: 2025 average annual contract value; y-axis: estimated 2025 RAPTOR; marks: all WNBA players with more than 500 minutes; color/grouping: rookie scale, regular max, super max; highlighted player: Veronica Burton.[cite:1] |
| Burton statistical comps | Demonstrates that Burton's profile resembles high-level guards.[cite:1] | Heatmap table / percentile comparison table.[cite:1] | Rows: Burton, Courtney Vandersloot, Natasha Cloud; columns: player, year, age, salary, offensive percentile, points per 100 percentile, assist percentage percentile, defensive percentile, RAPTOR percentile, similarity score; color scale: 0-100 percentile.[cite:1] |
| Same-salary comparison | Shows Burton lapping other players at her pay rate.[cite:1] | Ranked table.[cite:1] | Columns: player, RAPTOR, AAV in thousands; sorted to show Burton's RAPTOR versus other players making $78.83k.[cite:1] |
| Same-production comparison | Shows similar-impact players making far more.[cite:1] | Ranked table.[cite:1] | Columns: player, RAPTOR, AAV in thousands; includes players clustered around Burton's RAPTOR and their salaries.[cite:1] |
| Assist network | Visualizes Burton as the central hub of Golden State's offense.[cite:1] | Network graph.[cite:1] | Nodes: players; edges: assist connections between passer and scorer; emphasis on Burton as central node; likely weighted by assist frequency.[cite:1] |
| Passing value table | Supports elite playmaking claim while accounting for turnovers.[cite:1] | Ranked table.[cite:1] | Columns: rank, player, assists per 100 possessions, turnovers per 100 possessions, AST:TO ratio; filtered to players with minimum 500 minutes.[cite:1] |
| Shot profile graphic | Shows Burton concentrates attempts in efficient scoring zones.[cite:1] | Shot distribution graphic, likely segmented radial/pie-style chart.[cite:1] | Share of shot attempts from free throws, paint, and three-point range; article cites splits of 33%, 34%, and 33% respectively.[cite:1] |
| Free-throw scoring table | Quantifies how much of Burton's scoring comes from free throws.[cite:1] | Ranked table.[cite:1] | Columns: rank, player, free throws per 100 possessions, points per 100 possessions, FT percentage of points; filtered to minimum 500 minutes.[cite:1] |

## Template for future player profiles

### Section 1: Why this player

Lead with one paragraph explaining why the player is interesting now: breakout season, contract year, role change, trade, playoff impact, or market inefficiency.[cite:1] Include one hard-number hook immediately, usually salary, impact metric rank, or a dramatic year-over-year jump.[cite:1]

### Section 2: Market value framing

Use one leaguewide chart and one comp table before getting into film or skill details.[cite:1] This creates an editorial premise that the rest of the article can prove, rather than beginning with disconnected basketball observations.[cite:1]

### Section 3: Offensive creation

Start with the player's clearest bankable skill, especially if it explains the all-in-one impact metrics.[cite:1] For lead guards, this will often be passing hub metrics, assist creation, turnover control, and teammate shooting or efficiency while the player is on court.[cite:1]

### Section 4: Scoring profile

Follow playmaking with shot selection and efficiency rather than raw points per game.[cite:1] The Burton piece works because it explains not only *how much* she scores, but *where* those shots come from and why that profile is efficient.[cite:1]

### Section 5: Defense and non-scoring value

Use this section to connect reputation, awards, and impact metrics to event stats or role responsibilities.[cite:1] The article does this more lightly than the offensive sections, but the framework should formalize it with at least one supporting defensive visual whenever data is available.[cite:1]

### Section 6: On/off value and durability

Broaden the frame from isolated skill to total lineup effect.[cite:1] Minutes, games played, usage, on/off net rating, and team-style changes with the player on court are especially useful for players whose impact exceeds their box-score usage.[cite:1]

### Section 7: Projection

Close by answering the practical question raised at the top: what should teams, agents, or readers conclude about the player's value?[cite:1] Tie the contract forecast or role projection directly back to the evidence from the previous sections.[cite:1]

## Best practices taken from the article

- Lead with an argument, not a biography.[cite:1]
- Use visuals early, before the dense skill analysis begins.[cite:1]
- Alternate between visual proof and explanatory prose so the reader never sits in text for too long.[cite:1]
- Make every section answer a specific basketball or valuation question.[cite:1]
- Use player comps as a bridge between abstract metrics and intuitive understanding.[cite:1]
- Return to the opening salary or value thesis at the end so the narrative closes cleanly.[cite:1]

## Suggested framework skeleton

```markdown
# [Player Name] — Player Profile Deep Dive

## Thesis
One paragraph explaining why this player is undervalued, overvalued, misunderstood, or newly important.

## Contract and market context
- Current salary.
- Contract type / free-agent timeline.
- League rank by salary.
- One scatterplot: salary vs impact.

## Statistical comps
- Best historical comp.
- Best current-season comp.
- One heatmap table with percentile profile and similarity score.

## Same-salary peers
- Ranked comparison of players with similar salary.

## Same-production peers
- Ranked comparison of players with similar impact.

## [Primary skill section]
- Describe the role.
- Add one visual proving the skill.
- Explain why the metric matters in team context.

## [Secondary skill section]
- Add shot profile or efficiency visual.
- Connect shot selection to role.

## Defense
- Add event-rate or percentile visual.
- Explain assignments, disruption, and scheme value.

## On/off impact
- Add on/off chart or lineup table.
- Show how the team changes with the player on court.

## Projection
- Contract estimate or role forecast.
- Team-fit implications.
```
