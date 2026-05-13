WNBA 2026 Cap Sheet Cleaned Dataset

Source: Her Hoop Stats WNBA Salary Cap Database
Source URL family: https://herhoopstats.com/salary-cap-sheet/wnba/team/2026/

Files:
1) wnba_2026_cap_sheet_contracts_clean_long.csv
   Long-format player/draftee contract records. One row per team-player-year.
   Key fields: team, row_type, player, season_year, salary_cap_hit, pct_of_cap, pct_of_team, status, core_years.

2) wnba_2026_cap_sheet_contracts_clean_wide.csv
   Wide-format player/draftee contract records. One row per team-player.
   Key fields repeat by year, e.g. salary_cap_hit_2026, pct_of_cap_2026, pct_of_team_2026, status_2026.

3) wnba_2026_team_summary_clean_long.csv
   Team-level rows from the cap sheet, including total salaries, total players, cap room, protected veteran counts, and core player info.

4) wnba_2026_cba_numbers_clean.csv
   Key CBA values repeated by team page. Values should be deduped by metric if you only need league-level CBA numbers.

5) wnba_2026_cap_sheet_notes.csv
   Source notes extracted from the table.

Cleaning notes:
- Removed embedded audio-player JavaScript text from player names.
- Collapsed the three repeated view modes because the uploaded file contained identical values across salary, pct_cap, and pct_team rows.
- Split combined value cells into salary_cap_hit, pct_of_cap, pct_of_team, and status fields.
- Future-year rows with unknown cap percentage placeholders ($???,???) keep pct_of_cap blank and retain the known pct_of_team when available.
- All values shown reflect cap hit, not base salary.
