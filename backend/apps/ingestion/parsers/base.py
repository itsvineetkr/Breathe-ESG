"""
parsers/base.py

Base class and shared utilities for all three parsers.

Each parser's job:
1. Read the raw file into rows.
2. Remap headers using field mapping (org-configurable).
3. Extract and validate fields.
4. Return a list of ParsedRow objects (or flag them if invalid).

The parser does NOT compute emission factors or save to DB — that happens in
the ingestion pipeline (ingestion/views.py) after parsing.
"""

from dataclasses import dataclass, field
from typing import Optional
import re
from datetime import date


@dataclass
class ParsedRow:
    """
    Intermediate representation of a normalized parsed row.
    Not a Django model — just a data container passed to the DB write layer.
    """
    # Position in original file (1-indexed, header row = 0)
    row_number: int

    # Original row data preserved verbatim for audit trail
    source_row_data: dict

    # Activity classification
    scope: str = ''            # 'scope_1', 'scope_2', 'scope_3'
    category: str = ''         # 'diesel', 'electricity', 'flight', etc.

    # Dates
    activity_date: Optional[date] = None
    activity_period_end: Optional[date] = None

    # Quantities
    raw_quantity: Optional[float] = None
    raw_unit: str = ''
    normalized_quantity: Optional[float] = None
    normalized_unit: str = ''

    # Metadata
    location: str = ''         # plant, meter address, office
    vendor: str = ''
    description: str = ''

    # Travel-specific
    origin: str = ''           # airport code or city
    destination: str = ''
    flight_class: str = ''
    distance_km: Optional[float] = None

    # Validation
    is_flagged: bool = False
    flag_reasons: list = field(default_factory=list)
    parse_error: Optional[str] = None  # fatal error — row not usable

    def add_flag(self, reason: str):
        self.is_flagged = True
        self.flag_reasons.append(reason)


# ─── Shared date parsing ─────────────────────────────────────────────────────

DATE_FORMATS = [
    '%Y-%m-%d',   # ISO (2025-12-31)
    '%d.%m.%Y',   # SAP/German (31.12.2025)
    '%d/%m/%Y',   # UK (31/12/2025)
    '%m/%d/%Y',   # US (12/31/2025)
    '%Y%m%d',     # SAP compact (20251231)
    '%d-%m-%Y',   # dashes UK (31-12-2025)
    '%b %d, %Y',  # Jan 01, 2025
    '%d %b %Y',   # 01 Jan 2025
]


def parse_date(value: str) -> Optional[date]:
    """Try to parse a date string using a list of known formats."""
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            from datetime import datetime
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_float(value) -> Optional[float]:
    """
    Parse a float from a value that might contain commas, spaces, or
    European decimal notation (1.234,56 → 1234.56).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ('n/a', 'null', 'none', '-', ''):
        return None
    # European format: 1.234,56 → remove dots, replace comma with dot
    if re.match(r'^\d{1,3}(\.\d{3})*(,\d+)?$', s):
        s = s.replace('.', '').replace(',', '.')
    else:
        # Standard: remove commas and spaces used as thousand separators
        s = s.replace(',', '').replace(' ', '')
    try:
        return float(s)
    except ValueError:
        return None


# ─── Keyword-based source type / scope / category detection ─────────────────

SCOPE1_KEYWORDS = {
    'diesel': 'diesel',
    'gas oil': 'diesel',
    'petrol': 'petrol',
    'gasoline': 'petrol',
    'benzin': 'petrol',         # German
    'natural gas': 'natural_gas',
    'erdgas': 'natural_gas',    # German
    'lpg': 'lpg',
    'propane': 'lpg',
    'butane': 'lpg',
    'heating oil': 'heating_oil',
    'fuel oil': 'heating_oil',
    'heizöl': 'heating_oil',   # German
}

SCOPE2_KEYWORDS = {
    'kwh': 'electricity',
    'electricity': 'electricity',
    'strom': 'electricity',     # German
    'power': 'electricity',
    'electric': 'electricity',
    'mwh': 'electricity',
    'gwh': 'electricity',
    'energy': 'electricity',
}

SCOPE3_FLIGHT_KEYWORDS = ['flight', 'air', 'fly', 'airline', 'aviation', 'plane']
SCOPE3_HOTEL_KEYWORDS = ['hotel', 'accommodation', 'lodging', 'motel', 'inn']
SCOPE3_GROUND_KEYWORDS = ['taxi', 'car hire', 'car rental', 'uber', 'lyft', 'ground', 'vehicle']
SCOPE3_RAIL_KEYWORDS = ['rail', 'train', 'metro', 'subway', 'tram']


def classify_material(description: str, unit: str = '') -> tuple[str, str]:
    """
    Attempt to classify a material/activity into (scope, category) based on
    its description and unit. Returns ('', 'unknown') if unclear.
    """
    text = (description + ' ' + unit).lower()

    for kw, cat in SCOPE1_KEYWORDS.items():
        if kw in text:
            return 'scope_1', cat

    for kw, cat in SCOPE2_KEYWORDS.items():
        if kw in text:
            return 'scope_2', cat

    for kw in SCOPE3_FLIGHT_KEYWORDS:
        if kw in text:
            return 'scope_3', 'flight'
    for kw in SCOPE3_HOTEL_KEYWORDS:
        if kw in text:
            return 'scope_3', 'hotel'
    for kw in SCOPE3_GROUND_KEYWORDS:
        if kw in text:
            return 'scope_3', 'ground_transport'
    for kw in SCOPE3_RAIL_KEYWORDS:
        if kw in text:
            return 'scope_3', 'rail'

    return '', 'unknown'
