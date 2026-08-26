# delivery-sql-suite

Sprint 0 of a data engineering curriculum. Sprint 1 turns this into a DuckDB
query suite over a synthetic delivery dataset.

## What it does
Counts the data rows in a CSV, excluding the header.

## Setup
Requires uv.

    uv sync
    uv run main.py

Outputs `5` for the included sample.