"""
emission_factors.py

Emission factors used in CO2e calculations.

Sources:
- Fuel factors: UK DESNZ (formerly BEIS) GHG Conversion Factors 2023.
  URL: https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2023
  These are the most commonly used internationally for corporate reporting.

- Electricity: IEA World Energy Outlook 2023 global average (0.233 kg CO2e/kWh).
  Per-organization grid factor is configurable in Organization model.

- Flights: ICAO Carbon Emissions Calculator methodology.
  Short-haul <3700km, long-haul >3700km. Includes RFI (radiative forcing index) = 2.0
  for flights, which accounts for non-CO2 warming effects at altitude.

- Hotel: UK DESNZ 2023, "Hotel stay" category (31.2 kg CO2e per room night).

- Ground transport: UK DESNZ 2023 car averages, taxi category.

Units: All factors are in kg CO2e per [unit defined in factor key].

Why DESNZ over EPA: DESNZ factors are more granular for fuel types and are widely
accepted for international corporate ESG reporting (GHG Protocol aligned).
"""

# --- Scope 1: Direct fuel combustion ---
FUEL_FACTORS = {
    # kg CO2e per LITER
    'diesel': {
        'factor': 2.68,
        'source': 'DESNZ 2023',
        'category': 'diesel',
        'scope': 'scope_1',
        'normalized_unit': 'liters',
    },
    'petrol': {
        'factor': 2.31,
        'source': 'DESNZ 2023',
        'category': 'petrol',
        'scope': 'scope_1',
        'normalized_unit': 'liters',
    },
    'gasoline': {  # alias
        'factor': 2.31,
        'source': 'DESNZ 2023',
        'category': 'petrol',
        'scope': 'scope_1',
        'normalized_unit': 'liters',
    },
    # kg CO2e per CUBIC METER
    'natural_gas': {
        'factor': 2.04,
        'source': 'DESNZ 2023',
        'category': 'natural_gas',
        'scope': 'scope_1',
        'normalized_unit': 'm3',
    },
    # kg CO2e per LITER
    'lpg': {
        'factor': 1.56,
        'source': 'DESNZ 2023',
        'category': 'lpg',
        'scope': 'scope_1',
        'normalized_unit': 'liters',
    },
    'heating_oil': {
        'factor': 2.54,
        'source': 'DESNZ 2023',
        'category': 'other_fuel',
        'scope': 'scope_1',
        'normalized_unit': 'liters',
    },
}

# --- Scope 2: Purchased electricity ---
# Per-org configurable; this is the fallback world average.
ELECTRICITY_FACTOR_DEFAULT = {
    'factor': 0.233,   # kg CO2e per kWh
    'source': 'IEA 2023 world average',
    'category': 'electricity',
    'scope': 'scope_2',
    'normalized_unit': 'kwh',
}

# --- Scope 3: Business travel ---
TRAVEL_FACTORS = {
    'flight_economy_short': {
        # Short-haul (<3700km), economy, includes RFI=2.0
        'factor': 0.255,   # kg CO2e per passenger-km
        'source': 'ICAO 2023 + RFI',
        'category': 'flight',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
    'flight_economy_long': {
        # Long-haul (>3700km), economy, includes RFI=2.0
        'factor': 0.195,
        'source': 'ICAO 2023 + RFI',
        'category': 'flight',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
    'flight_business_short': {
        'factor': 0.680,   # business class ≈ 2.67x economy (GHG Protocol)
        'source': 'ICAO 2023 + RFI',
        'category': 'flight',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
    'flight_business_long': {
        'factor': 0.429,
        'source': 'ICAO 2023 + RFI',
        'category': 'flight',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
    'flight_first_long': {
        'factor': 0.585,   # first class ≈ 3x economy
        'source': 'ICAO 2023 + RFI',
        'category': 'flight',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
    'hotel': {
        'factor': 31.2,    # kg CO2e per room-night
        'source': 'DESNZ 2023',
        'category': 'hotel',
        'scope': 'scope_3',
        'normalized_unit': 'room_nights',
    },
    'taxi': {
        'factor': 0.149,   # kg CO2e per km, average taxi/private hire
        'source': 'DESNZ 2023',
        'category': 'ground_transport',
        'scope': 'scope_3',
        'normalized_unit': 'km',
    },
    'car_rental': {
        'factor': 0.168,   # average petrol car
        'source': 'DESNZ 2023',
        'category': 'ground_transport',
        'scope': 'scope_3',
        'normalized_unit': 'km',
    },
    'rail': {
        'factor': 0.035,   # national rail average
        'source': 'DESNZ 2023',
        'category': 'rail',
        'scope': 'scope_3',
        'normalized_unit': 'passenger_km',
    },
}


def get_flight_factor(flight_class: str, distance_km: float) -> dict:
    """Return the right flight emission factor based on class and distance."""
    flight_class = (flight_class or 'economy').lower()
    is_long_haul = distance_km > 3700

    if 'business' in flight_class:
        key = 'flight_business_long' if is_long_haul else 'flight_business_short'
    elif 'first' in flight_class:
        key = 'flight_first_long' if is_long_haul else 'flight_business_short'
    else:
        key = 'flight_economy_long' if is_long_haul else 'flight_economy_short'

    return TRAVEL_FACTORS[key]


# --- Unit conversion table ---
# All quantities get normalized to a base unit before applying emission factors.
# Base units: fuel→liters, electricity→kWh, gas→m3, distance→km
UNIT_CONVERSIONS = {
    # Volume (→ liters)
    'l': 1.0,
    'liter': 1.0,
    'liters': 1.0,
    'litre': 1.0,
    'litres': 1.0,
    'lt': 1.0,
    'gal': 3.78541,      # US gallon
    'gallon': 3.78541,
    'gallons': 3.78541,
    'imp_gal': 4.54609,  # Imperial gallon (UK)
    'usg': 3.78541,
    'm3': 1000.0,        # cubic meter → liters
    'cbm': 1000.0,
    'ft3': 28.3168,      # cubic feet → liters

    # Energy (→ kWh)
    'kwh': 1.0,
    'kw/h': 1.0,
    'mwh': 1000.0,
    'gwh': 1000000.0,
    'j': 2.77778e-7,
    'mj': 0.000277778,
    'gj': 0.277778,
    'therm': 29.3071,
    'btu': 2.93071e-4,
    'mbtu': 0.293071,

    # Mass (→ kg, for gas in kg)
    'kg': 1.0,
    'g': 0.001,
    't': 1000.0,
    'tonne': 1000.0,
    'mt': 1000.0,
    'lb': 0.453592,
    'lbs': 0.453592,

    # Distance (→ km)
    'km': 1.0,
    'kilometers': 1.0,
    'kilometres': 1.0,
    'mi': 1.60934,
    'miles': 1.60934,
    'mile': 1.60934,
    'nm': 1.852,         # nautical miles
}


def normalize_unit(quantity: float, unit: str) -> tuple[float, str]:
    """
    Convert quantity+unit to its normalized base unit.
    Returns (normalized_quantity, normalized_unit_name).
    Raises ValueError if unit is unknown.
    """
    unit_lower = unit.strip().lower()
    if unit_lower not in UNIT_CONVERSIONS:
        raise ValueError(f"Unknown unit: '{unit}'")
    factor = UNIT_CONVERSIONS[unit_lower]
    return quantity * factor, unit_lower
