"""
parsers/utility.py

Utility Portal CSV Parser — Electricity consumption data.

Format decision: Portal CSV export.

We chose CSV export from utility portals (not PDF bills, not Green Button XML) because:
1. PDF parsing is brittle — layouts change with every utility, every year.
   pdfplumber/camelot works for structured tables but fails on scanned bills.
2. Green Button (ESPI XML) is technically the right format and is mandated for
   US utilities, but: (a) many clients don't know it exists, (b) it requires
   OAuth setup with each utility individually, (c) the UK/EU equivalent isn't
   standardized at all.
3. Portal CSV export is what facilities teams actually send. You log into the
   utility portal, select date range, click "Export". PG&E, National Grid,
   Centrica, Vattenfall all offer this. The file looks different everywhere,
   but the fields are consistent enough to map.

What we handle:
- Billing period data (not necessarily calendar months)
- kWh, MWh, GWh units
- Multiple meters per file (different buildings/locations)
- Missing demand column (not all utilities report peak demand)
- Account numbers and meter IDs for traceability

What we ignore:
- Tariff structure details (peak/off-peak split) — we sum to total usage
- Power factor / reactive energy
- Interval data (15-minute smart meter readings) — too granular for ESG reporting

Key challenge: Billing periods don't align with calendar months.
A bill from Jan 15 – Feb 14 spans two months. We use the billing_period_start
as the activity_date and flag if the period exceeds 45 days (suggests estimation).
"""

import io
import csv
import pandas as pd
from .base import ParsedRow, parse_date, parse_float

# ─── Field mapping ────────────────────────────────────────────────────────────
# Utility portal exports vary by provider, but these fields appear consistently.
# We map to normalized names.

UTILITY_FIELD_MAPPINGS = {
    # Account/meter identification
    'Account Number': 'account_number',
    'Account No': 'account_number',
    'Account No.': 'account_number',
    'Account': 'account_number',
    'Customer Account': 'account_number',
    'Account ID': 'account_number',

    'Meter Number': 'meter_id',
    'Meter No': 'meter_id',
    'Meter ID': 'meter_id',
    'Meter Serial': 'meter_id',
    'Meter': 'meter_id',
    'MPAN': 'meter_id',          # UK Meter Point Administration Number
    'ESI ID': 'meter_id',        # US Electric Service Identifier
    'Meter Point': 'meter_id',

    # Service address / site
    'Service Address': 'service_address',
    'Premise Address': 'service_address',
    'Site': 'service_address',
    'Location': 'service_address',
    'Address': 'service_address',
    'Facility': 'service_address',
    'Building': 'service_address',

    # Billing period
    'Start Date': 'period_start',
    'Bill Start Date': 'period_start',
    'Billing Start': 'period_start',
    'Period Start': 'period_start',
    'From Date': 'period_start',
    'Read Date From': 'period_start',
    'Service From': 'period_start',

    'End Date': 'period_end',
    'Bill End Date': 'period_end',
    'Billing End': 'period_end',
    'Period End': 'period_end',
    'To Date': 'period_end',
    'Read Date To': 'period_end',
    'Service To': 'period_end',
    'Bill Date': 'period_end',

    # Usage (the critical field)
    'Usage (kWh)': 'usage_kwh',
    'Energy Usage': 'usage_kwh',
    'Electricity Usage': 'usage_kwh',
    'Consumption': 'usage_kwh',
    'kWh': 'usage_kwh',
    'KWH': 'usage_kwh',
    'Total kWh': 'usage_kwh',
    'Net kWh': 'usage_kwh',
    'Total Usage': 'usage_kwh',
    'Usage': 'usage_kwh',
    'Electric Usage (kWh)': 'usage_kwh',
    'Electricity Consumed (kWh)': 'usage_kwh',

    # MWh variant
    'Usage (MWh)': 'usage_mwh',
    'MWh': 'usage_mwh',
    'Total MWh': 'usage_mwh',

    # Peak demand (optional, not used in emission calc but preserved)
    'Peak Demand': 'peak_demand_kw',
    'Demand (kW)': 'peak_demand_kw',
    'Max Demand': 'peak_demand_kw',
    'Billed Demand': 'peak_demand_kw',
    'kW': 'peak_demand_kw',

    # Cost (preserved for cross-referencing, not used in emissions)
    'Amount Due': 'amount_due',
    'Total Due': 'amount_due',
    'Bill Amount': 'amount_due',
    'Charge': 'amount_due',
    'Total Charges': 'amount_due',
    'Amount': 'amount_due',

    'Currency': 'currency',
    'Rate Schedule': 'rate_schedule',
    'Tariff': 'rate_schedule',
}


def _remap_headers(df: pd.DataFrame, org_overrides: dict) -> pd.DataFrame:
    mapping = {**UTILITY_FIELD_MAPPINGS, **org_overrides}
    rename_map = {}
    for col in df.columns:
        col_stripped = col.strip()
        if col_stripped in mapping:
            rename_map[col] = mapping[col_stripped]
    return df.rename(columns=rename_map)


def parse_utility_file(file_content: bytes, org_field_overrides: dict = None) -> list[ParsedRow]:
    """
    Parse a utility portal CSV export for electricity data.
    """
    org_field_overrides = org_field_overrides or {}
    results = []

    try:
        try:
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            content = file_content.decode('latin-1')

        # Handle Excel
        if file_content[:4] in (b'\xd0\xcf\x11\xe0', b'PK\x03\x04'):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            # Detect delimiter
            sample = content[:2000]
            if sample.count('\t') > sample.count(','):
                sep = '\t'
            elif sample.count(';') > sample.count(','):
                sep = ';'
            else:
                sep = ','
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
        parsed.scope = 'scope_2'
        parsed.category = 'electricity'

        # ── Meter / account / location ────────────────────────────────────────
        meter_id = str(raw.get('meter_id', '')).strip()
        account = str(raw.get('account_number', '')).strip()
        address = str(raw.get('service_address', '')).strip()
        parsed.location = address or f"Meter {meter_id}" if meter_id else account
        parsed.description = f"Electricity — {address or meter_id or account}"

        # ── Billing period ────────────────────────────────────────────────────
        period_start = parse_date(str(raw.get('period_start', '')))
        period_end = parse_date(str(raw.get('period_end', '')))

        if period_start:
            parsed.activity_date = period_start
            parsed.activity_period_end = period_end
        elif period_end:
            parsed.activity_date = period_end
            parsed.add_flag("Only billing end date found — using end date as activity date")
        else:
            parsed.add_flag("No billing period dates found — cannot assign to time period")

        # Flag bills covering suspiciously long periods (>45 days = estimated reading)
        if period_start and period_end:
            delta = (period_end - period_start).days
            if delta > 45:
                parsed.add_flag(
                    f"Billing period is {delta} days — likely an estimated reading or missed bill"
                )
            elif delta < 20:
                parsed.add_flag(
                    f"Billing period is only {delta} days — possible partial month or data issue"
                )

        # ── Usage / quantity ──────────────────────────────────────────────────
        usage_kwh = parse_float(raw.get('usage_kwh'))
        usage_mwh = parse_float(raw.get('usage_mwh'))

        if usage_kwh is not None:
            parsed.raw_quantity = usage_kwh
            parsed.raw_unit = 'kWh'
            parsed.normalized_quantity = usage_kwh
            parsed.normalized_unit = 'kwh'
        elif usage_mwh is not None:
            parsed.raw_quantity = usage_mwh
            parsed.raw_unit = 'MWh'
            parsed.normalized_quantity = usage_mwh * 1000.0
            parsed.normalized_unit = 'kwh'
        else:
            # Last resort: look for any numeric column that might be usage
            parsed.add_flag("Could not find kWh or MWh usage column — check column names")

        if parsed.raw_quantity is not None:
            if parsed.raw_quantity < 0:
                parsed.add_flag(f"Negative electricity usage ({parsed.raw_quantity} kWh) — possible credit or data error")
            elif parsed.raw_quantity == 0:
                parsed.add_flag("Zero electricity usage — verify meter was active this period")
            elif parsed.raw_quantity > 1_000_000:
                parsed.add_flag(
                    f"Very high usage ({parsed.raw_quantity:,.0f} kWh) — verify unit is kWh not MWh"
                )

        results.append(parsed)

    return results
