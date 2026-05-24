"""
Utility electricity CSV parser.

Handles portal CSV exports from utility portals (PG&E, National Grid, EDF format).

Key features:
- Billing period normalization (period_start / period_end as explicit dates)
- Estimated read flagging (Read Type E → flagged for analyst review)
- Unit normalization (MWh → kWh)
- Multi-meter awareness (stores Meter ID for analyst to resolve sub-meter hierarchy)

Expected DataSource.config shape:
{
    "column_map": {
        "Account Number": "Account Number",
        "Meter ID": "Meter ID",
        "Period Start": "Period Start",
        "Period End": "Period End",
        "Usage": "Usage (kWh)",
        "Read Type": "Read Type",
        "Unit": "kWh"           # or "MWh" if portal exports in MWh
    },
    "scope2_method": "location_based",  # or "market_based"
    "electricity_region": "GB",         # for emission factor lookup
    "exclude_meter_ids": []             # sub-meters to exclude from Scope 2 total
}
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


DEFAULT_COLUMN_MAP = {
    "Account Number": "Account Number",
    "Meter ID": "Meter ID",
    "Period Start": "Period Start",
    "Period End": "Period End",
    "Usage": "Usage (kWh)",
    "Read Type": "Read Type",
    "Tariff": "Tariff",
}

# Read types considered estimated (flagged for analyst review)
ESTIMATED_READ_TYPES = {"E", "ESTIMATED", "EST"}


def _parse_date(date_str: str) -> date:
    """Parse ISO 8601, UK (DD/MM/YYYY), or US (MM/DD/YYYY) date strings."""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: '{date_str}'")


def parse_utility_csv(file_content: str, config: dict) -> list[dict]:
    """
    Parse a utility portal CSV export.

    Returns list of result dicts with same schema as SAP parser.
    Billing periods are stored as explicit start/end dates — NOT snapped to calendar months.
    The analytics layer pro-rates consumption across months using day-weighted apportionment.
    """
    col_map = {**DEFAULT_COLUMN_MAP, **config.get("column_map", {})}
    scope2_method = config.get("scope2_method", "location_based")
    electricity_region = config.get("electricity_region", "GB")
    exclude_meter_ids = set(config.get("exclude_meter_ids", []))

    reader = csv.DictReader(io.StringIO(file_content))
    results = []

    for row_idx, row in enumerate(reader, start=2):
        raw_data = dict(row)

        def get(col_key):
            mapped = col_map.get(col_key, col_key)
            return (row.get(mapped) or row.get(col_key) or "").strip()

        errors = []

        # Sub-meter exclusion
        meter_id = get("Meter ID")
        if meter_id in exclude_meter_ids:
            results.append({
                "status": "skipped",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": [f"Meter '{meter_id}' is in exclude_meter_ids (sub-meter)"],
            })
            continue

        # Parse billing period
        period_start_str = get("Period Start")
        period_end_str = get("Period End")

        try:
            period_start = _parse_date(period_start_str)
        except ValueError as e:
            errors.append(f"period_start: {e}")
            period_start = None

        try:
            period_end = _parse_date(period_end_str)
        except ValueError as e:
            errors.append(f"period_end: {e}")
            period_end = None

        # Parse usage
        usage_str = get("Usage").replace(",", "").strip()
        try:
            raw_quantity = Decimal(usage_str)
        except InvalidOperation:
            errors.append(f"usage: cannot parse '{usage_str}'")
            raw_quantity = None

        # Unit normalization: MWh → kWh
        raw_unit = config.get("column_map", {}).get("Unit", "kWh").upper()
        if raw_unit == "MWH":
            quantity_normalized = raw_quantity * Decimal("1000") if raw_quantity else None
            unit_normalized = "kWh"
        else:
            quantity_normalized = raw_quantity
            unit_normalized = "kWh"

        # Estimated read flag
        read_type = get("Read Type").upper()
        is_estimated = read_type in ESTIMATED_READ_TYPES

        if errors:
            results.append({
                "status": "error",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": errors,
            })
            continue

        activity_description = f"Electricity — {get('Account Number')} Meter {meter_id}"
        if is_estimated:
            activity_description += " [ESTIMATED READ]"

        results.append({
            "status": "ok",
            "row_number": row_idx,
            "raw_data": raw_data,
            "errors": [],
            "activity_description": activity_description,
            "period_start": period_start,
            "period_end": period_end,
            "raw_quantity": raw_quantity,
            "raw_unit": raw_unit,
            "quantity_normalized": quantity_normalized,
            "unit_normalized": unit_normalized,
            "scope": "SCOPE_2",
            "category": "Purchased electricity",
            "activity": f"electricity_{electricity_region.lower()}",
            "meter_id": meter_id,
            "account_number": get("Account Number"),
            "read_type": read_type,
            "is_estimated": is_estimated,
            "scope2_method": scope2_method,
            "tariff": get("Tariff"),
        })

    return results
