"""Fetch paired water-quality observations from the USGS NWIS public API."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SOURCE_URL = (
    "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=01463500"
    "&startDT=2025-10-01&endDT=2025-10-02&parameterCd=00300,00400&siteStatus=all"
)
STATION = "01463500"
FIRST_DAY = "2025-10-01"
OUTPUT_PATH = Path(__file__).parents[1] / "data" / "usgs_reference_readings.csv"
FIELDNAMES = [
    "station",
    "datetime",
    "dissolved_oxygen_mg_l",
    "ph",
    "source_mode",
    "source_verified",
    "quality_status",
    "source_qualifiers",
    "source_url",
]


def fetch_payload(url: str = SOURCE_URL) -> dict[str, Any]:
    """Return NWIS response JSON using only the Python standard library."""
    request = Request(
        url, headers={"Accept": "application/json", "User-Agent": "aquaculture-demo/1.0"}
    )
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed public HTTPS API URL
        payload: dict[str, Any] = json.load(response)
    return payload


def extract_paired_readings(payload: dict[str, Any], limit: int = 24) -> list[dict[str, str]]:
    """Pair dissolved oxygen and pH values that share an observation timestamp."""
    values_by_parameter: dict[str, dict[str, tuple[str, set[str]]]] = {"00300": {}, "00400": {}}

    for series in payload["value"]["timeSeries"]:
        parameter = series["variable"]["variableCode"][0]["value"]
        if parameter not in values_by_parameter:
            continue
        if series["sourceInfo"]["siteCode"][0]["value"] != STATION:
            continue
        for observation in series["values"][0]["value"]:
            timestamp = observation["dateTime"]
            value = observation["value"]
            if timestamp.startswith(FIRST_DAY) and value != "-999999":
                values_by_parameter[parameter][timestamp] = (
                    value,
                    set(observation.get("qualifiers", [])),
                )

    paired_timestamps = sorted(
        set(values_by_parameter["00300"]) & set(values_by_parameter["00400"])
    )[:limit]
    rows: list[dict[str, str]] = []
    for timestamp in paired_timestamps:
        oxygen, oxygen_qualifiers = values_by_parameter["00300"][timestamp]
        ph, ph_qualifiers = values_by_parameter["00400"][timestamp]
        qualifiers = sorted(oxygen_qualifiers | ph_qualifiers)
        utc_timestamp = (
            datetime.fromisoformat(timestamp).astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
        rows.append(
            {
                "station": STATION,
                "datetime": utc_timestamp,
                "dissolved_oxygen_mg_l": oxygen,
                "ph": ph,
                "source_mode": "external_observation",
                "source_verified": "true",
                "quality_status": "provisional" if "P" in qualifiers else "approved",
                "source_qualifiers": ",".join(qualifiers),
                "source_url": SOURCE_URL,
            }
        )
    return rows


def write_reference_csv(rows: list[dict[str, str]], path: Path = OUTPUT_PATH) -> None:
    """Write observations with their official-source provenance metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = extract_paired_readings(fetch_payload())
    if len(rows) != 24:
        raise RuntimeError(f"Expected 24 paired first-day observations, received {len(rows)}")
    write_reference_csv(rows)
    print(f"Wrote {len(rows)} paired USGS observations to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
