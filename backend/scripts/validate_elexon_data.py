from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.services.elexon_client import client


def validate_dataset(dataset: str, start_date: date, end_date: date) -> dict:
    rows = client.fetch_dataset(dataset, start_date, end_date)
    issues = []
    if not rows:
        issues.append("No rows returned.")
    required = {"startTime", "generation"}
    if dataset == "WINDFOR":
        required.add("publishTime")
    for row in rows:
        for field in required:
            if field not in row:
                issues.append(f"Missing field {field} in row: {row}")
        if isinstance(row.get("generation"), (int, float)) and row["generation"] < 0:
            issues.append(f"Unexpected negative generation: {row}")
        if "startTime" in row and row["startTime"].endswith("Z") is False:
            issues.append(f"Unexpected startTime format: {row['startTime']}")
    return {"dataset": dataset, "count": len(rows), "issues": issues}


if __name__ == "__main__":
    result = validate_dataset("WINDFOR", date(2026, 1, 1), date(2026, 1, 2))
    print(json.dumps(result, indent=2))
