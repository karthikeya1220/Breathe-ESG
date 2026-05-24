"""
SAP MB51 flat-file parser.

Handles:
- DD.MM.YYYY date format (European SAP installs)
- Configurable column name mapping (English/German headers)
- Movement type filter (201, 261, 101 — configurable per DataSource)
- Reversal document detection (negative quantities netted out)
- Material filter list from DataSource.config

Expected DataSource.config shape:
{
    "column_map": {
        "Posting Date": "Posting Date",   # or "Buchungsdatum" for German
        "Material": "Material",
        "Material Description": "Material Description",
        "Plant": "Plant",
        "Movement Type": "Movement Type",
        "Quantity": "Quantity",
        "Unit": "Unit",
        "Cost Center": "Cost Center"
    },
    "movement_types": ["201", "261"],
    "emissions_materials": ["100045782", "100087431"],  # if empty, all materials accepted
    "plant_map": {
        "0010": "Hamburg Plant",
        "0020": "Rotterdam Plant"
    },
    "delimiter": "\\t"   # tab-delimited by default
}
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


# Default column mapping (English SAP headers)
DEFAULT_COLUMN_MAP = {
    "Posting Date": "Posting Date",
    "Material": "Material",
    "Material Description": "Material Description",
    "Plant": "Plant",
    "Movement Type": "Movement Type",
    "Quantity": "Quantity",
    "Unit": "Unit",
    "Cost Center": "Cost Center",
}

# SAP movement types that represent consumption (goods issue)
DEFAULT_MOVEMENT_TYPES = ["201", "261"]

# Scope 1 fuel categories by material description keywords
FUEL_KEYWORDS = {
    "diesel": ("Stationary combustion", "diesel"),
    "petrol": ("Stationary combustion", "petrol"),
    "gasoline": ("Stationary combustion", "petrol"),
    "natural gas": ("Stationary combustion", "natural_gas"),
    "lpg": ("Stationary combustion", "lpg"),
    "fuel oil": ("Stationary combustion", "fuel_oil"),
}


def _parse_sap_date(date_str: str) -> date:
    """
    Parse DD.MM.YYYY (European SAP format) or ISO 8601 YYYY-MM-DD.
    Raises ValueError on unrecognised format.
    """
    date_str = date_str.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised SAP date format: '{date_str}'")


def _classify_material(description: str):
    """
    Map material description to (GHG category, activity key).
    Returns None if not emissions-relevant.
    """
    desc_lower = description.lower()
    for keyword, (category, activity) in FUEL_KEYWORDS.items():
        if keyword in desc_lower:
            return category, activity
    return None, None


def parse_sap_csv(file_content: str, config: dict) -> list[dict]:
    """
    Parse a SAP MB51 flat file export.

    Returns a list of result dicts:
    {
        "status": "ok" | "error" | "skipped",
        "row_number": int,
        "raw_data": dict,          # original row as-is
        "errors": list[str],       # non-empty on error
        # On success:
        "activity_description": str,
        "period_start": date,
        "period_end": date,
        "raw_quantity": Decimal,
        "raw_unit": str,
        "quantity_normalized": Decimal,
        "unit_normalized": str,
        "scope": "SCOPE_1",
        "category": str,
        "activity": str,
        "plant_name": str,
    }
    """
    col_map = {**DEFAULT_COLUMN_MAP, **config.get("column_map", {})}
    allowed_movement_types = [str(m) for m in config.get("movement_types", DEFAULT_MOVEMENT_TYPES)]
    emissions_materials = [str(m) for m in config.get("emissions_materials", [])]
    plant_map = config.get("plant_map", {})
    delimiter = config.get("delimiter", "\t")

    # Also accept comma-delimited files
    reader = csv.DictReader(io.StringIO(file_content), delimiter=delimiter)

    # If tab-delimited produced a single column, try comma
    if reader.fieldnames and len(reader.fieldnames) == 1:
        reader = csv.DictReader(io.StringIO(file_content), delimiter=",")

    results = []
    for row_idx, row in enumerate(reader, start=2):  # Row 1 = header
        raw_data = dict(row)

        def get(col_key):
            mapped = col_map.get(col_key, col_key)
            return (row.get(mapped) or row.get(col_key) or "").strip()

        errors = []

        # Movement type filter
        movement_type = get("Movement Type")
        if movement_type not in allowed_movement_types:
            results.append({
                "status": "skipped",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": [f"Movement type '{movement_type}' not in filter list {allowed_movement_types}"],
            })
            continue

        # Material filter (if configured)
        material_number = get("Material")
        if emissions_materials and material_number not in emissions_materials:
            results.append({
                "status": "skipped",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": [f"Material '{material_number}' not in emissions_materials list"],
            })
            continue

        # Parse date
        posting_date_str = get("Posting Date")
        try:
            posting_date = _parse_sap_date(posting_date_str)
        except ValueError as e:
            errors.append(f"posting_date: {e}")
            posting_date = None

        # Parse quantity (SAP uses period as decimal separator, comma for thousands)
        qty_str = get("Quantity").replace(",", "").replace(" ", "")
        try:
            raw_quantity = Decimal(qty_str)
        except InvalidOperation:
            errors.append(f"quantity: cannot parse '{qty_str}'")
            raw_quantity = None

        raw_unit = get("Unit").upper()
        material_description = get("Material Description")
        plant_code = get("Plant")
        plant_name = plant_map.get(plant_code, plant_code)

        # Classify fuel type
        category, activity = _classify_material(material_description)
        if not category and not errors:
            errors.append(f"material_description: '{material_description}' not recognised as emissions-relevant")

        if errors:
            results.append({
                "status": "error",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": errors,
            })
            continue

        # Reversal documents have negative quantity — valid, include as-is (they net out sums)
        # Normalize unit to litres where possible (conversions handled by UnitConversion table)
        unit_normalized = raw_unit
        quantity_normalized = raw_quantity

        results.append({
            "status": "ok",
            "row_number": row_idx,
            "raw_data": raw_data,
            "errors": [],
            "activity_description": f"{material_description} — {plant_name}",
            "period_start": posting_date,
            "period_end": posting_date,  # SAP: single posting date, not a range
            "raw_quantity": raw_quantity,
            "raw_unit": raw_unit,
            "quantity_normalized": quantity_normalized,
            "unit_normalized": unit_normalized,
            "scope": "SCOPE_1",
            "category": category,
            "activity": activity,
            "plant_name": plant_name,
            "cost_center": get("Cost Center"),
        })

    return results
