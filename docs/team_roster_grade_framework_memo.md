# Team-Level Roster Grade Framework
**WNBA 2026 — Player & Roster Intelligence System**
*Internal Framework Documentation — May 2026*

---

## Purpose

The Team-Level Roster Grade analysis aggregates individual player value scores into a structured snapshot of each franchise's roster construction quality. It answers three questions at once: *How much collective production does this roster deliver relative to what it's paid?* *Where is salary capital concentrated versus spread?* *Which teams are hiding undervalued talent, and which are overexposed?*

The output is designed to support draft targeting, trade evaluation, and free agency prioritization — not just retrospective grading.

---

## How Scores Roll Up

Each player carries a **value_score** (0–100) built from five weighted components:

| Component | Weight | What It Measures |
|---|---|---|
| Production Score | 42% | Position-specific percentile composite (TS%, AST%, Usage, REB%, STL%, BLK%, TOV%, MPG, HLE, On/Off, Playoff bonus) |
| Salary Efficiency | 24% | How far below or above market rate the player is paid |
| Scarcity | 12% | Archetype rarity across the league |
| Playoff Score | 10% | High-leverage experience + postseason TS% delta |
| On/Off Impact | 12% | Net rating differential with player on vs. off court |

Team grades are derived from the **median player value_score** across all rostered players, using a league-relative curve rather than absolute thresholds. A team's grade reflects the typical quality of a roster slot, not just star power at the top.

---

## Key Team-Level Metrics

**1. Median Value Score (primary grade signal)**
The middle player on the roster. Resistant to outlier inflation from one elite contract. Current league range: 43.7–49.0 (tight distribution; most teams cluster in the C–D band due to partial data coverage).

**2. Cap Concentration (top-2 salary % of team total)**
Measures how much of a team's payroll is locked into two players. Las Vegas leads at 35.7%; Chicago is most distributed at 22.6%. High concentration = risk if either player underperforms or misses time.

**3. Hidden Value Count**
Players with value_score ≥ 70 on a Minimum/Low/Rookie/Training Camp deal. These are your high-upside, low-cost assets. Current league leaders: Connecticut Sun (7), Golden State Valkyries (6).

**4. Undervalued vs. Overvalued Player Counts**
Directional read on whether a roster is getting more than it's paying for. Teams with high overvalued counts are cap-inefficient; teams with high undervalued counts have leverage in negotiations.

**5. Position Archetype Coverage (Gaps & Overlaps)**
Count of Guards, Forwards, and Centers per team by archetype family. Surfaces structural construction issues — e.g., a team with 9 Guards and 0 Centers has a clear gap; a team with 7 Forwards and 2 Guards lacks perimeter creation. Minnesota (3 Guards) and Washington (2 Guards) currently show the most concentrated frontcourt construction.

---

## Data Coverage Caveat

Position-specific percentiles are live for **133/300 players (44%)** with confirmed position_group data. Players without position data receive a league-wide percentile fallback, which tends to compress scores toward the median (44.09). As bio coverage expands, team grade separation will increase. Treat current team grades as relative rankings within the framework rather than absolute letter grades.

---

## Suggested Visuals

**1. Team Value Leaderboard (horizontal bar chart)**
One bar per team, sorted by median value_score. Color-code bars by grade band (green = top quartile, yellow = mid, red = bottom quartile). Add a secondary data label showing # of hidden value players.

**2. Cap Concentration vs. Team Value Scatter**
X-axis: top-2 cap concentration %. Y-axis: median value_score. Quadrant labels: *Efficient Stars* (high value, low concentration), *Star-Dependent* (high value, high concentration), *Distributed Mediocrity* (low value, low concentration), *Cap Trapped* (low value, high concentration).

**3. Roster Tier Stacked Bar by Team**
For each team, stack bars representing player counts in each value tier: Overvalued / Risk / Fair Value / Strong Value / Elite Value. Immediately shows roster depth distribution and where teams are thin at the top.

**4. Position Archetype Heatmap (teams × position group)**
Rows = teams, columns = Guard / Forward / Center. Cell = count of players at that position. Highlight cells below 3 (gap alert) in red, above 8 (stack/overlap) in blue. Indiana Fever (9 Guards) and Minnesota Lynx (3 Guards) are the clearest examples of positional imbalance today.

**5. Hidden Value Talent by Team (dot plot)**
One dot per team, X = hidden value count, size = total roster size. Teams in the upper right have the most efficient roster construction leverage.

**6. Salary Efficiency Distribution by Team (violin or box plot)**
Shows the spread of salary_efficiency_scores across each roster. Wide spread = uneven contracts. Narrow + high = consistent underpayment (cap advantage). Narrow + low = overpaying across the board.

---

## Major Overlaps and Gaps (Current 2026 Snapshot)

**Guard-heavy teams (potential overlap):** Indiana Fever (9G), Dallas Wings (7G), Toronto Tempo (6G), Portland Fire (6G)

**Guard-thin teams (creation gap risk):** Washington Mystics (2G), New York Liberty (3G), Minnesota Lynx (3G), Phoenix Mercury (3G)

**Center-absent teams (rim protection gap):** Atlanta Dream, Indiana Fever, Los Angeles Sparks, Minnesota Lynx, Washington Mystics — all carry 0 players classified as Center

**Cap-concentrated teams (star dependency):** Las Vegas Aces (35.7%), Indiana Fever (29.7%), Los Angeles Sparks (29.3%)

**Most cap-efficient construction:** Chicago Sky (22.6% top-2 concentration), Golden State Valkyries (22.8%)

---

*Framework built on WNBA 2026 value_scores pipeline. Run `post_pipeline_patches.py` after any pipeline rebuild to restore position-specific production scores, multi-year trends, and market comps override floor.*
