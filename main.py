
import duckdb



query = """
SELECT ISSUE_ID, FROM_STATUS, TO_STATUS, CHANGED_AT, CHANGED_BY, count(*)
FROM 'data/transitions.csv'
GROUP BY ISSUE_ID, FROM_STATUS, TO_STATUS, CHANGED_AT, CHANGED_BY
HAVING count(*) > 1
"""

result = duckdb.sql(query)
print(result)