import duckdb

# row_number() OVER () simply counts the rows and assigns 1, 2, 3, etc.
query = """
    COPY (
        SELECT row_number() OVER () AS id, * FROM 'data/berlin_pois.parquet'
    ) TO 'data/berlin_pois_with_ids.parquet' (FORMAT PARQUET);
"""

duckdb.sql(query)
print("Success! Created data/berlin_pois_with_ids.parquet")