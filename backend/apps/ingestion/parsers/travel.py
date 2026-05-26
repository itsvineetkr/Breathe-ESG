"""
parsers/travel.py

Corporate Travel Parser — Navan (formerly TripActions) / Concur style CSV exports.

Format decision: Navan CSV export.

We chose Navan's export format because:
1. Navan is the fastest-growing corporate travel platform (2M+ travelers, 2024)
   and has displaced Concur in many enterprise clients.
2. Concur's export is structurally similar — same categories (air/hotel/car/rail),
   same fields, just different column names. Our field mapping handles both.
3. Navan provides a direct CSV export from their portal with no API auth required
   for historical data, making it realistic for "facilities team sends us a file".

What we handle:
- Flights: origin/destination airport codes, flight class, segment distance
  When distance is not provided (common), we calculate great-circle distance
  from airport IATA codes using a lookup table of major airports.
- Hotels: nightly rate, check-in/check-out dates, room-nights calculation
- Ground transport: car rental, taxi, rideshare
- Rail: train journeys

What we ignore:
- Per-leg itinerary for multi-stop flights (we sum the trip)
- Fare classes below economy (basic economy, premium economy nuances)
- Loyalty program routing (people take longer routes for miles — we use direct distance)
- Personal vs business day splits for bleisure travel

Key challenge: Airport code → distance.
Not all records have distance_km. We maintain a table of 50+ major airport
lat/long coordinates and compute great-circle (haversine) distance.
This is ~3% accurate vs actual flight paths (sufficient for ESG reporting).
"""

import io
import math
import pandas as pd
from datetime import date
from .base import ParsedRow, parse_date, parse_float

# ─── Field mapping (Navan + Concur + generic) ────────────────────────────────

TRAVEL_FIELD_MAPPINGS = {
    # Trip / booking ID
    'Trip ID': 'trip_id',
    'Booking ID': 'trip_id',
    'Report ID': 'trip_id',        # Concur
    'Reservation Number': 'trip_id',

    # Traveler
    'Traveler Name': 'traveler_name',
    'Employee Name': 'traveler_name',
    'Name': 'traveler_name',
    'Traveler': 'traveler_name',
    'Employee': 'traveler_name',

    'Traveler Email': 'traveler_email',
    'Employee Email': 'traveler_email',
    'Email': 'traveler_email',

    # Dates
    'Travel Date': 'travel_date',
    'Departure Date': 'travel_date',
    'Trip Start Date': 'travel_date',
    'Start Date': 'travel_date',
    'Check-in Date': 'travel_date',
    'Check In Date': 'travel_date',
    'Check In': 'travel_date',
    'Booking Date': 'booking_date',

    'Return Date': 'return_date',
    'Trip End Date': 'return_date',
    'End Date': 'return_date',
    'Check-out Date': 'return_date',
    'Check Out Date': 'return_date',
    'Check Out': 'return_date',

    # Segment type
    'Segment Type': 'segment_type',
    'Type': 'segment_type',
    'Travel Type': 'segment_type',
    'Mode': 'segment_type',
    'Category': 'segment_type',
    'Expense Type': 'segment_type',  # Concur

    # Flight-specific
    'Origin': 'origin',
    'Departure Airport': 'origin',
    'From': 'origin',
    'Origin Airport': 'origin',
    'From Airport': 'origin',

    'Destination': 'destination',
    'Arrival Airport': 'destination',
    'To': 'destination',
    'Destination Airport': 'destination',
    'To Airport': 'destination',

    'Flight Class': 'flight_class',
    'Cabin Class': 'flight_class',
    'Class': 'flight_class',
    'Service Class': 'flight_class',
    'Travel Class': 'flight_class',

    'Carrier': 'carrier',
    'Airline': 'carrier',
    'Airline Name': 'carrier',

    'Distance (km)': 'distance_km',
    'Distance': 'distance_km',
    'Miles': 'distance_miles',
    'Distance (miles)': 'distance_miles',

    # Hotel-specific
    'Hotel Name': 'hotel_name',
    'Property Name': 'hotel_name',
    'Hotel': 'hotel_name',
    'Property': 'hotel_name',
    'Nights': 'nights',
    'Number of Nights': 'nights',
    'Duration (nights)': 'nights',

    # Ground transport
    'Vendor': 'vendor',
    'Vendor Name': 'vendor',
    'Provider': 'vendor',

    # Cost (preserved, not used in emission calc)
    'Amount': 'amount',
    'Total Amount': 'amount',
    'Charge Amount': 'amount',
    'Cost': 'amount',
    'Currency': 'currency',
    'Cost Center': 'cost_center',
    'Department': 'cost_center',
}

# ─── Airport coordinates for haversine distance ──────────────────────────────
# Major airports: IATA code → (latitude, longitude)
# This covers ~80% of typical corporate travel routes.

AIRPORT_COORDS = {
    # North America
    'JFK': (40.6413, -73.7781), 'LGA': (40.7769, -73.8740), 'EWR': (40.6895, -74.1745),
    'LAX': (33.9416, -118.4085), 'SFO': (37.6213, -122.3790), 'ORD': (41.9742, -87.9073),
    'MDW': (41.7868, -87.7522), 'DFW': (32.8998, -97.0403), 'DAL': (32.8471, -96.8518),
    'ATL': (33.6407, -84.4277), 'MIA': (25.7959, -80.2870), 'FLL': (26.0726, -80.1528),
    'SEA': (47.4502, -122.3088), 'DEN': (39.8561, -104.6737), 'LAS': (36.0840, -115.1537),
    'PHX': (33.4373, -112.0078), 'IAH': (29.9902, -95.3368), 'HOU': (29.6454, -95.2789),
    'BOS': (42.3656, -71.0096), 'DCA': (38.8521, -77.0377), 'IAD': (38.9531, -77.4565),
    'BWI': (39.1754, -76.6682), 'MSP': (44.8820, -93.2218), 'DTW': (42.2162, -83.3554),
    'CLT': (35.2140, -80.9431), 'PHL': (39.8729, -75.2437), 'SLC': (40.7899, -111.9791),
    'PDX': (45.5898, -122.5951), 'SAN': (32.7338, -117.1933), 'OAK': (37.7213, -122.2208),
    'SJC': (37.3626, -121.9290), 'YYZ': (43.6777, -79.6248), 'YVR': (49.1967, -123.1815),
    'YUL': (45.4706, -73.7408), 'MEX': (19.4363, -99.0721),
    # Europe
    'LHR': (51.4700, -0.4543), 'LGW': (51.1537, -0.1821), 'STN': (51.8850, 0.2350),
    'CDG': (49.0097, 2.5479), 'ORY': (48.7233, 2.3794),
    'FRA': (50.0379, 8.5622), 'MUC': (48.3538, 11.7861), 'BER': (52.3667, 13.5033),
    'AMS': (52.3086, 4.7639), 'BRU': (50.9010, 4.4844),
    'MAD': (40.4936, -3.5668), 'BCN': (41.2974, 2.0833),
    'FCO': (41.8003, 12.2389), 'MXP': (45.6306, 8.7231),
    'ZRH': (47.4647, 8.5492), 'VIE': (48.1102, 16.5697),
    'CPH': (55.6180, 12.6508), 'ARN': (59.6519, 17.9186),
    'OSL': (60.1976, 11.1004), 'HEL': (60.3172, 24.9633),
    'WAW': (52.1657, 20.9671), 'PRG': (50.1008, 14.2600),
    'DUB': (53.4213, -6.2701), 'MAN': (53.3537, -2.2750),
    'LIS': (38.7742, -9.1342), 'ATH': (37.9364, 23.9445),
    'IST': (41.2608, 28.7418), 'SAW': (40.8986, 29.3092),
    # Asia-Pacific
    'HKG': (22.3080, 113.9185), 'SIN': (1.3644, 103.9915),
    'NRT': (35.7720, 140.3929), 'HND': (35.5494, 139.7798),
    'ICN': (37.4602, 126.4407), 'PVG': (31.1443, 121.8083),
    'PEK': (40.0725, 116.5975), 'CAN': (23.3924, 113.2988),
    'BOM': (19.0896, 72.8656), 'DEL': (28.5562, 77.1000),
    'BKK': (13.6900, 100.7501), 'KUL': (2.7456, 101.7099),
    'SYD': (33.9461, 151.1772), 'MEL': (37.6733, 144.8430),
    'AKL': (37.0082, 174.7850), 'DXB': (25.2528, 55.3644),
    'DOH': (25.2609, 51.6138), 'AUH': (24.4330, 54.6511),
    # South America
    'GRU': (-23.4356, -46.4731), 'GIG': (-22.8099, -43.2505),
    'BOG': (4.7016, -74.1469), 'SCL': (-33.3929, -70.7857),
    'LIM': (-12.0219, -77.1143), 'EZE': (-34.8222, -58.5358),
    # Africa
    'JNB': (-26.1367, 28.2411), 'CPT': (-33.9715, 18.6021),
    'NBO': (-1.3192, 36.9275), 'CAI': (30.1219, 31.4056),
    'LOS': (6.5774, 3.3212),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def airport_distance_km(origin: str, destination: str) -> tuple[float, bool]:
    """
    Return (distance_km, is_estimated).
    is_estimated=True means we calculated it, not provided by source data.
    Returns (None, False) if airport codes unknown.
    """
    o = origin.upper().strip()
    d = destination.upper().strip()
    if o in AIRPORT_COORDS and d in AIRPORT_COORDS:
        lat1, lon1 = AIRPORT_COORDS[o]
        lat2, lon2 = AIRPORT_COORDS[d]
        return haversine_km(lat1, lon1, lat2, lon2), True
    return None, False


def _remap_headers(df: pd.DataFrame, org_overrides: dict) -> pd.DataFrame:
    mapping = {**TRAVEL_FIELD_MAPPINGS, **org_overrides}
    rename_map = {}
    for col in df.columns:
        col_stripped = col.strip()
        if col_stripped in mapping:
            rename_map[col] = mapping[col_stripped]
    return df.rename(columns=rename_map)


def _classify_segment(segment_type: str) -> str:
    """Map raw segment type string to our category."""
    s = (segment_type or '').lower().strip()
    if any(k in s for k in ['air', 'flight', 'fly', 'plane', 'aviation']):
        return 'flight'
    if any(k in s for k in ['hotel', 'accommodation', 'lodging', 'motel', 'room']):
        return 'hotel'
    if any(k in s for k in ['rail', 'train', 'metro', 'subway', 'tram', 'eurostar']):
        return 'rail'
    if any(k in s for k in ['taxi', 'car', 'uber', 'lyft', 'rideshare', 'ground', 'vehicle', 'rental', 'hire']):
        return 'ground_transport'
    return 'unknown'


def parse_travel_file(file_content: bytes, org_field_overrides: dict = None) -> list[ParsedRow]:
    """
    Parse a Navan/Concur corporate travel CSV export.
    """
    org_field_overrides = org_field_overrides or {}
    results = []

    try:
        try:
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            content = file_content.decode('latin-1')

        if file_content[:4] in (b'\xd0\xcf\x11\xe0', b'PK\x03\x04'):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            sample = content[:2000]
            sep = '\t' if sample.count('\t') > sample.count(',') else ','
            df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)

    except Exception as e:
        return [ParsedRow(
            row_number=0,
            source_row_data={'error': str(e)},
            parse_error=f"Could not read file: {e}",
        )]

    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    df = _remap_headers(df, org_field_overrides)

    for idx, row in df.iterrows():
        row_num = idx + 2
        raw = row.to_dict()

        parsed = ParsedRow(row_number=row_num, source_row_data=raw)
        parsed.scope = 'scope_3'

        # ── Segment classification ────────────────────────────────────────────
        segment_type_raw = str(raw.get('segment_type', '')).strip()
        parsed.category = _classify_segment(segment_type_raw)

        if parsed.category == 'unknown':
            parsed.add_flag(
                f"Unknown travel segment type: '{segment_type_raw}' — analyst must classify"
            )

        # ── Date ──────────────────────────────────────────────────────────────
        parsed.activity_date = parse_date(str(raw.get('travel_date', '')))
        if not parsed.activity_date:
            # Fall back to booking date
            parsed.activity_date = parse_date(str(raw.get('booking_date', '')))
            if parsed.activity_date:
                parsed.add_flag("Using booking date as activity date — travel date not found")
            else:
                parsed.add_flag("No travel or booking date found")

        return_date = parse_date(str(raw.get('return_date', '')))
        if return_date:
            parsed.activity_period_end = return_date

        # ── Traveler / vendor / description ──────────────────────────────────
        traveler = str(raw.get('traveler_name', '')).strip()
        parsed.vendor = str(raw.get('vendor', raw.get('carrier', raw.get('hotel_name', '')))).strip()
        cost_center = str(raw.get('cost_center', '')).strip()
        parsed.description = f"{segment_type_raw} — {traveler}" + (f" ({cost_center})" if cost_center else "")

        # ── Category-specific processing ──────────────────────────────────────
        if parsed.category == 'flight':
            _process_flight(parsed, raw)
        elif parsed.category == 'hotel':
            _process_hotel(parsed, raw)
        elif parsed.category in ('ground_transport', 'rail'):
            _process_ground(parsed, raw, parsed.category)

        results.append(parsed)

    return results


def _process_flight(parsed: ParsedRow, raw: dict):
    """Extract flight-specific fields and compute distance if missing."""
    parsed.origin = str(raw.get('origin', '')).upper().strip()
    parsed.destination = str(raw.get('destination', '')).upper().strip()
    parsed.flight_class = str(raw.get('flight_class', 'economy')).lower().strip()

    # Try to get distance from source data
    dist_km = parse_float(raw.get('distance_km'))
    dist_miles = parse_float(raw.get('distance_miles'))

    if dist_km and dist_km > 0:
        parsed.distance_km = dist_km
        parsed.raw_quantity = dist_km
        parsed.raw_unit = 'km'
        parsed.normalized_quantity = dist_km
        parsed.normalized_unit = 'km'
    elif dist_miles and dist_miles > 0:
        parsed.distance_km = dist_miles * 1.60934
        parsed.raw_quantity = dist_miles
        parsed.raw_unit = 'miles'
        parsed.normalized_quantity = parsed.distance_km
        parsed.normalized_unit = 'km'
    elif parsed.origin and parsed.destination:
        # Calculate from airport codes
        dist, estimated = airport_distance_km(parsed.origin, parsed.destination)
        if dist:
            parsed.distance_km = dist
            parsed.normalized_quantity = dist
            parsed.normalized_unit = 'km'
            parsed.add_flag(
                f"Distance calculated from airport codes ({parsed.origin}→{parsed.destination}: "
                f"{dist:.0f} km great-circle) — not from source data"
            )
        else:
            parsed.add_flag(
                f"Unknown airport codes '{parsed.origin}' or '{parsed.destination}' "
                "— cannot calculate distance, analyst must provide"
            )
    else:
        parsed.add_flag("No distance data and no airport codes — cannot calculate emissions")

    # Validate airport codes
    if parsed.origin and len(parsed.origin) != 3:
        parsed.add_flag(f"Origin '{parsed.origin}' is not a 3-letter IATA code")
    if parsed.destination and len(parsed.destination) != 3:
        parsed.add_flag(f"Destination '{parsed.destination}' is not a 3-letter IATA code")
    if not parsed.origin or not parsed.destination:
        parsed.add_flag("Missing origin or destination airport code")


def _process_hotel(parsed: ParsedRow, raw: dict):
    """Extract hotel-specific fields."""
    parsed.location = str(raw.get('hotel_name', raw.get('vendor', ''))).strip()

    # Calculate nights from check-in/out if not provided directly
    nights = parse_float(raw.get('nights'))
    if not nights and parsed.activity_date and parsed.activity_period_end:
        nights = (parsed.activity_period_end - parsed.activity_date).days

    if nights and nights > 0:
        parsed.raw_quantity = nights
        parsed.raw_unit = 'nights'
        parsed.normalized_quantity = nights
        parsed.normalized_unit = 'room_nights'
    elif nights == 0:
        parsed.add_flag("Zero nights — possible same-day booking or data error")
    else:
        parsed.add_flag("Could not determine number of hotel nights")

    if nights and nights > 30:
        parsed.add_flag(f"Very long hotel stay ({int(nights)} nights) — verify this is correct")


def _process_ground(parsed: ParsedRow, raw: dict, category: str):
    """Extract ground transport / rail fields."""
    dist_km = parse_float(raw.get('distance_km'))
    dist_miles = parse_float(raw.get('distance_miles'))

    if dist_km and dist_km > 0:
        parsed.raw_quantity = dist_km
        parsed.raw_unit = 'km'
        parsed.normalized_quantity = dist_km
        parsed.normalized_unit = 'km'
    elif dist_miles and dist_miles > 0:
        parsed.raw_quantity = dist_miles
        parsed.raw_unit = 'miles'
        parsed.normalized_quantity = dist_miles * 1.60934
        parsed.normalized_unit = 'km'
    else:
        parsed.add_flag(
            f"No distance provided for {category} segment — "
            "emissions cannot be calculated without distance"
        )
