
import duckdb



query = """
SELECT
  CASE
    WHEN team_name = 'Search' THEN 'Discovery'  -- renamed 2026-01-15, same team
    ELSE team_name
  END AS team,
  count(*) AS issue_count
FROM 'data/issues.csv' AS i
JOIN 'data/teams.csv' AS t ON i.team_id = t.team_id
  WHERE issue_type = 'Bug' 

GROUP BY team 
    

ORDER BY issue_count DESC
"""

result = duckdb.sql(query)
print(result)