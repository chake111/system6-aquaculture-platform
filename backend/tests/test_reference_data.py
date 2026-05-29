import csv
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

DATA_PATH = Path(__file__).parents[1] / "data" / "usgs_reference_readings.csv"
SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "fetch_reference_readings.py"
EXPECTED_SOURCE_URL = (
    "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=01463500"
    "&startDT=2025-10-01&endDT=2025-10-02&parameterCd=00300,00400&siteStatus=all"
)
SCRIPT_SPEC = importlib.util.spec_from_file_location("fetch_reference_readings", SCRIPT_PATH)
assert SCRIPT_SPEC is not None and SCRIPT_SPEC.loader is not None
SCRIPT_MODULE = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(SCRIPT_MODULE)

extract_paired_readings = SCRIPT_MODULE.extract_paired_readings


def _time_series(parameter_code: str, values: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "sourceInfo": {"siteCode": [{"value": "01463500"}]},
        "variable": {"variableCode": [{"value": parameter_code}]},
        "values": [{"value": values}],
    }


def test_script_uses_approved_usgs_source_url() -> None:
    assert SCRIPT_MODULE.SOURCE_URL == EXPECTED_SOURCE_URL

    parsed_source_url = urlparse(SCRIPT_MODULE.SOURCE_URL)
    query = parse_qs(parsed_source_url.query)
    assert parsed_source_url.netloc == "waterservices.usgs.gov"
    assert query["sites"] == ["01463500"]
    assert set(query["parameterCd"][0].split(",")) == {"00300", "00400"}


def test_extract_paired_readings_correlates_oxygen_and_ph_by_timestamp() -> None:
    payload = {
        "value": {
            "timeSeries": [
                _time_series(
                    "00300",
                    [
                        {"dateTime": "2025-10-01T00:00:00.000-04:00", "value": "7.4"},
                        {"dateTime": "2025-10-01T01:00:00.000-04:00", "value": "7.3"},
                    ],
                ),
                _time_series(
                    "00400",
                    [
                        {"dateTime": "2025-10-01T00:00:00.000-04:00", "value": "7.2"},
                        {"dateTime": "2025-10-01T02:00:00.000-04:00", "value": "7.1"},
                    ],
                ),
            ]
        }
    }

    assert extract_paired_readings(payload, limit=24) == [
        {
            "station": "01463500",
            "datetime": "2025-10-01T04:00:00Z",
            "dissolved_oxygen_mg_l": "7.4",
            "ph": "7.2",
            "source_mode": "external_observation",
            "source_verified": "true",
            "quality_status": "approved",
            "source_qualifiers": "",
            "source_url": EXPECTED_SOURCE_URL,
        }
    ]


def test_committed_csv_contains_24_verified_official_paired_observations() -> None:
    with DATA_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

    assert {
        "station",
        "datetime",
        "dissolved_oxygen_mg_l",
        "ph",
        "source_mode",
        "source_verified",
        "quality_status",
        "source_qualifiers",
        "source_url",
    } <= set(reader.fieldnames or [])
    assert len(rows) == 24

    captured_at = [datetime.fromisoformat(row["datetime"]) for row in rows]
    assert captured_at == sorted(captured_at)
    assert len(set(captured_at)) == 24
    assert all(value.tzname() == "UTC" for value in captured_at)

    assert {row["station"] for row in rows} == {"01463500"}
    assert {row["source_mode"] for row in rows} == {"external_observation"}
    assert {row["source_verified"] for row in rows} == {"true"}
    assert {row["quality_status"] for row in rows} == {"provisional"}
    assert {row["source_qualifiers"] for row in rows} == {"P"}
    assert {row["source_url"] for row in rows} == {EXPECTED_SOURCE_URL}
    assert all(float(row["dissolved_oxygen_mg_l"]) > 0 for row in rows)
    assert all(float(row["ph"]) > 0 for row in rows)
