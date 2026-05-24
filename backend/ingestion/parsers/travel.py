"""
Corporate travel CSV parser (Concur / Navan format).

Handles:
- Air travel: haversine distance from IATA airport codes when distance is missing
- Booking class multipliers: economy 1x, premium economy 1.26x, business 2.40x, first 2.40x
- Hotel stays: nights from check-in / check-out dates, country-specific emission factors
- Ground transport: rental car, taxi/rideshare, rail
- Multi-segment trips linked by Trip ID

Expected DataSource.config shape:
{
    "column_map": { ... }   # override column names for Navan / other platforms
}

DEFRA 2024 class multipliers (per DEFRA GHG Conversion Factors 2024):
- economy: 1.0x (base factor for short/long haul)
- premium economy: 1.26x
- business: 2.40x
- first: 2.40x (same as business per DEFRA)

Radiative forcing multiplier of 2x applied to all flights (per DEFRA guidance for non-CO₂
effects at altitude). This doubles the CO₂e figure and is standard practice for Scope 3 Cat 6.
"""

import csv
import io
import math
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

# Static IATA airport coordinate lookup (subset — key global airports)
# Full dataset: OpenFlights airports.dat (~7,000 airports)
AIRPORT_COORDS = {
    "LHR": (51.4775, -0.4614),    # London Heathrow
    "LGW": (51.1481, -0.1903),    # London Gatwick
    "JFK": (40.6413, -73.7781),   # New York JFK
    "LAX": (33.9425, -118.4081),  # Los Angeles
    "CDG": (49.0097, 2.5479),     # Paris Charles de Gaulle
    "AMS": (52.3086, 4.7639),     # Amsterdam Schiphol
    "FRA": (50.0379, 8.5622),     # Frankfurt
    "MUC": (48.3538, 11.7861),    # Munich
    "SIN": (1.3644, 103.9915),    # Singapore Changi
    "DXB": (25.2532, 55.3657),    # Dubai
    "HKG": (22.3080, 113.9185),   # Hong Kong
    "NRT": (35.7720, 140.3929),   # Tokyo Narita
    "SYD": (33.9399, 151.1753),   # Sydney
    "ORD": (41.9742, -87.9073),   # Chicago O'Hare
    "ATL": (33.6407, -84.4277),   # Atlanta
    "DFW": (32.8998, -97.0403),   # Dallas Fort Worth
    "MIA": (25.7959, -80.2870),   # Miami
    "BOS": (42.3656, -71.0096),   # Boston Logan
    "SEA": (47.4502, -122.3088),  # Seattle
    "SFO": (37.6213, -122.3790),  # San Francisco
    "MAN": (53.3537, -2.2750),    # Manchester
    "EDI": (55.9500, -3.3725),    # Edinburgh
    "GLA": (55.8719, -4.4331),    # Glasgow
    "BHX": (52.4539, -1.7480),    # Birmingham
    "BRS": (51.3827, -2.7191),    # Bristol
    "MAD": (40.4719, -3.5626),    # Madrid
    "BCN": (41.2971, 2.0785),     # Barcelona
    "FCO": (41.8003, 12.2389),    # Rome Fiumicino
    "MXP": (45.6306, 8.7281),     # Milan Malpensa
    "ZRH": (47.4647, 8.5492),     # Zurich
    "VIE": (48.1103, 16.5697),    # Vienna
    "CPH": (55.6180, 12.6508),    # Copenhagen
    "ARN": (59.6519, 17.9186),    # Stockholm Arlanda
    "HEL": (60.3172, 24.9633),    # Helsinki
    "OSL": (60.1939, 11.1004),    # Oslo
    "WAW": (52.1657, 20.9671),    # Warsaw
    "PRG": (50.1008, 14.2600),    # Prague
    "BUD": (47.4298, 19.2611),    # Budapest
    "IST": (41.2753, 28.7519),    # Istanbul
    "DOH": (25.2731, 51.6081),    # Doha
    "AUH": (24.4330, 54.6511),    # Abu Dhabi
    "BOM": (19.0896, 72.8656),    # Mumbai
    "DEL": (28.5562, 77.1000),    # Delhi
    "BLR": (13.1986, 77.7066),    # Bangalore
    "PEK": (40.0799, 116.6031),   # Beijing
    "PVG": (31.1443, 121.8083),   # Shanghai Pudong
    "ICN": (37.4602, 126.4407),   # Seoul Incheon
    "YYZ": (43.6777, -79.6248),   # Toronto
    "YVR": (49.1967, -123.1815),  # Vancouver
    "MEX": (19.4363, -99.0721),   # Mexico City
    "GRU": (23.4356, -46.4731),   # São Paulo
    "EZE": (34.8222, -58.5358),   # Buenos Aires
    "JNB": (26.1392, 28.2460),    # Johannesburg
    "CPT": (33.9715, 18.6021),    # Cape Town
    "NBO": (-1.3192, 36.9275),    # Nairobi
    "LON": (51.5074, -0.1278),    # London (generic city code)
}

# Booking class multipliers per DEFRA 2024
CLASS_MULTIPLIERS = {
    "economy": Decimal("1.0"),
    "economy class": Decimal("1.0"),
    "coach": Decimal("1.0"),
    "premium economy": Decimal("1.26"),
    "premium": Decimal("1.26"),
    "business": Decimal("2.40"),
    "business class": Decimal("2.40"),
    "first": Decimal("2.40"),
    "first class": Decimal("2.40"),
}

# Radiative forcing multiplier for all flights (DEFRA guidance)
RADIATIVE_FORCING_MULTIPLIER = Decimal("2.0")

# Category classification
CATEGORY_MAP = {
    "air travel": "Business travel - air",
    "air": "Business travel - air",
    "flight": "Business travel - air",
    "hotel": "Business travel - hotel",
    "accommodation": "Business travel - hotel",
    "ground": "Business travel - ground transport",
    "ground transport": "Business travel - ground transport",
    "car rental": "Business travel - ground transport",
    "rental car": "Business travel - ground transport",
    "taxi": "Business travel - ground transport",
    "rideshare": "Business travel - ground transport",
    "rail": "Business travel - rail",
    "train": "Business travel - rail",
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lookup_distance(origin: str, destination: str) -> tuple[float | None, str]:
    """
    Return (distance_km, method) where method is 'haversine' or 'unknown'.
    Returns (None, 'unknown_airport') if either airport code is not in the lookup.
    """
    origin = origin.upper().strip()
    dest = destination.upper().strip()
    coords_o = AIRPORT_COORDS.get(origin)
    coords_d = AIRPORT_COORDS.get(dest)
    if not coords_o:
        return None, f"unknown_airport:{origin}"
    if not coords_d:
        return None, f"unknown_airport:{dest}"
    dist = _haversine_km(coords_o[0], coords_o[1], coords_d[0], coords_d[1])
    return dist, "haversine"


def _parse_date(date_str: str) -> date:
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: '{date_str}'")


def _get_class_multiplier(booking_class: str) -> Decimal:
    return CLASS_MULTIPLIERS.get(booking_class.lower().strip(), Decimal("1.0"))


def parse_travel_csv(file_content: str, config: dict) -> list[dict]:
    """
    Parse a Concur / Navan corporate travel CSV export.

    Returns list of result dicts with same schema conventions as other parsers.

    For air travel:
    - If Distance column is present and non-zero → use it
    - If Distance is missing → calculate via haversine from IATA codes
    - Apply class multiplier and radiative forcing multiplier

    For hotels:
    - quantity = number of nights (check_out - check_in)
    - unit = "room_night"
    - emission factor lookup: activity = "hotel_{country_code.lower()}"

    For ground transport:
    - quantity = distance in km (if provided)
    - activity = "ground_transport" (rental car average)
    """
    DEFAULT_COLUMNS = {
        "Trip ID": "Trip ID",
        "Employee ID": "Employee ID",
        "Category": "Category",
        "Departure Date": "Departure Date",
        "Origin": "Origin",
        "Destination": "Destination",
        "Class": "Class",
        "Distance (km)": "Distance (km)",
        "Nights": "Nights",
        "Country": "Country",
        "Vendor": "Vendor",
        "Check In": "Check In",
        "Check Out": "Check Out",
    }
    col_map = {**DEFAULT_COLUMNS, **config.get("column_map", {})}

    reader = csv.DictReader(io.StringIO(file_content))
    results = []

    for row_idx, row in enumerate(reader, start=2):
        raw_data = dict(row)

        def get(col_key):
            mapped = col_map.get(col_key, col_key)
            return (row.get(mapped) or row.get(col_key) or "").strip()

        errors = []
        category_raw = get("Category").lower()
        category = CATEGORY_MAP.get(category_raw, "Business travel - other")

        departure_str = get("Departure Date") or get("Check In")
        try:
            departure_date = _parse_date(departure_str) if departure_str else None
        except ValueError as e:
            errors.append(f"departure_date: {e}")
            departure_date = None

        period_start = departure_date
        period_end = departure_date
        raw_quantity = None
        raw_unit = "km"
        quantity_normalized = None
        unit_normalized = "km"
        activity = "unknown"
        distance_method = "provided"
        employee_id = get("Employee ID")
        trip_id = get("Trip ID")
        vendor = get("Vendor")
        country = get("Country")

        if "air" in category_raw or "flight" in category_raw:
            # --- Flight segment ---
            origin = get("Origin")
            destination = get("Destination")
            booking_class = get("Class")
            class_multiplier = _get_class_multiplier(booking_class)

            # Distance: use provided value or calculate via haversine
            dist_str = get("Distance (km)").replace(",", "").strip()
            if dist_str:
                try:
                    distance_km = Decimal(dist_str)
                    distance_method = "provided"
                except InvalidOperation:
                    errors.append(f"distance: cannot parse '{dist_str}'")
                    distance_km = None
            else:
                if origin and destination:
                    dist_float, distance_method = _lookup_distance(origin, destination)
                    if dist_float is None:
                        errors.append(f"distance: {distance_method}")
                        distance_km = None
                    else:
                        distance_km = Decimal(str(round(dist_float, 2)))
                else:
                    errors.append("distance: no distance provided and no origin/destination to calculate from")
                    distance_km = None

            if distance_km is not None:
                # Apply class multiplier and radiative forcing
                adjusted_km = distance_km * class_multiplier * RADIATIVE_FORCING_MULTIPLIER
                raw_quantity = distance_km
                quantity_normalized = adjusted_km
                raw_unit = "km"
                unit_normalized = "km_adjusted"  # indicates class + RF multipliers applied

            # Classify as short haul (< 1500 km) or long haul
            if distance_km and distance_km < Decimal("1500"):
                activity = "short_haul_economy"
            else:
                activity = "long_haul_economy"
            # Override for business class
            if booking_class.lower() in ("business", "business class", "first", "first class"):
                activity = activity.replace("economy", "business")

            activity_description = (
                f"Flight {origin}→{destination} ({booking_class or 'Economy'}) "
                f"— {employee_id}"
            )
            if distance_method != "provided":
                activity_description += f" [dist:{distance_method}]"

        elif "hotel" in category_raw or "accommodation" in category_raw:
            # --- Hotel stay ---
            nights_str = get("Nights").strip()
            check_in_str = get("Check In") or get("Departure Date")
            check_out_str = get("Check Out")

            if nights_str:
                try:
                    nights = int(nights_str)
                except ValueError:
                    errors.append(f"nights: cannot parse '{nights_str}'")
                    nights = None
            elif check_in_str and check_out_str:
                try:
                    ci = _parse_date(check_in_str)
                    co = _parse_date(check_out_str)
                    nights = (co - ci).days
                    period_start = ci
                    period_end = co
                except ValueError:
                    errors.append("nights: cannot calculate from check-in/out dates")
                    nights = None
            else:
                errors.append("nights: no nights value and no check-in/out dates")
                nights = None

            if nights is not None:
                raw_quantity = Decimal(str(nights))
                quantity_normalized = raw_quantity
                raw_unit = "room_night"
                unit_normalized = "room_night"

            country_code = country.upper()[:2] if country else "GB"
            activity = f"hotel_{country_code.lower()}"
            activity_description = f"Hotel stay — {vendor or 'Unknown'} ({country or 'Unknown'}) — {employee_id}"

        else:
            # --- Ground transport / Rail ---
            dist_str = get("Distance (km)").replace(",", "").strip()
            if dist_str:
                try:
                    raw_quantity = Decimal(dist_str)
                    quantity_normalized = raw_quantity
                    raw_unit = "km"
                    unit_normalized = "km"
                except InvalidOperation:
                    errors.append(f"distance: cannot parse '{dist_str}'")

            if "rail" in category_raw or "train" in category_raw:
                activity = "rail"
            else:
                activity = "ground_transport"

            activity_description = f"{get('Category')} — {vendor or 'Unknown'} — {employee_id}"

        if errors:
            results.append({
                "status": "error",
                "row_number": row_idx,
                "raw_data": raw_data,
                "errors": errors,
            })
            continue

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
            "scope": "SCOPE_3",
            "category": category,
            "activity": activity,
            "trip_id": trip_id,
            "employee_id": employee_id,
            "vendor": vendor,
            "country": country,
        })

    return results
