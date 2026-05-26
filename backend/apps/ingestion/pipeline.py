"""
ingestion/pipeline.py

The ingestion pipeline: ParsedRow → EmissionRecord.

Steps:
1. Take a list of ParsedRow objects from a parser.
2. Apply unit normalization (if not already done by parser).
3. Apply emission factors to calculate co2e_kg.
4. Save to database as EmissionRecord objects.
5. Update DataSource statistics.
6. Write AuditLog entry for the upload.

Design note: This runs synchronously in the request/response cycle.
For files with >10k rows, this would need to move to a background worker (Celery).
In this prototype, we accept the tradeoff of blocking requests for large files.
A reasonable file size limit (50MB, set in settings.py) keeps parse times under 30s.
"""

from django.utils import timezone
from django.db import transaction

from apps.emissions.models import EmissionRecord
from apps.audit.models import AuditLog
from apps.ingestion.models import DataSource
from apps.ingestion.emission_factors import (
    FUEL_FACTORS, ELECTRICITY_FACTOR_DEFAULT, TRAVEL_FACTORS,
    get_flight_factor, normalize_unit
)
from apps.ingestion.parsers.base import ParsedRow
import math


def _sanitize_json(d: dict) -> dict:
    """
    Convert a pandas-produced dict to JSON-serializable form.
    pandas uses float('nan') for missing values; JSON has no NaN.
    We convert NaN → None (null in JSON).
    """
    result = {}
    for k, v in d.items():
        if isinstance(v, float) and math.isnan(v):
            result[str(k)] = None
        else:
            result[str(k)] = v
    return result


def _apply_emission_factor(parsed: ParsedRow, org) -> dict:
    """
    Compute emission factor and co2e_kg for a parsed row.
    Returns dict with keys: emission_factor, emission_factor_source, co2e_kg, normalized_quantity, normalized_unit.
    """
    result = {
        'emission_factor': None,
        'emission_factor_source': '',
        'co2e_kg': None,
        'normalized_quantity': parsed.normalized_quantity,
        'normalized_unit': parsed.normalized_unit,
        'extra_flags': [],
    }

    # ── Unit normalization (if parser didn't do it) ───────────────────────────
    if parsed.raw_quantity is not None and parsed.raw_unit and result['normalized_quantity'] is None:
        try:
            norm_qty, norm_unit = normalize_unit(parsed.raw_quantity, parsed.raw_unit)
            result['normalized_quantity'] = norm_qty
            result['normalized_unit'] = norm_unit
        except ValueError as e:
            result['extra_flags'].append(str(e))
            return result

    qty = result['normalized_quantity']
    if qty is None:
        return result

    # ── Scope 1: Fuel ─────────────────────────────────────────────────────────
    if parsed.scope == 'scope_1' and parsed.category in FUEL_FACTORS:
        factor_info = FUEL_FACTORS[parsed.category]
        result['emission_factor'] = factor_info['factor']
        result['emission_factor_source'] = factor_info['source']
        result['co2e_kg'] = qty * factor_info['factor']

    # ── Scope 2: Electricity ──────────────────────────────────────────────────
    elif parsed.scope == 'scope_2' and parsed.category == 'electricity':
        # Use org-specific factor if set, otherwise world average
        ef = org.electricity_emission_factor or ELECTRICITY_FACTOR_DEFAULT['factor']
        result['emission_factor'] = ef
        result['emission_factor_source'] = (
            f"Org-configured grid factor" if org.electricity_emission_factor
            else ELECTRICITY_FACTOR_DEFAULT['source']
        )
        result['co2e_kg'] = qty * ef

    # ── Scope 3: Travel ───────────────────────────────────────────────────────
    elif parsed.scope == 'scope_3':
        if parsed.category == 'flight' and parsed.distance_km:
            factor_info = get_flight_factor(parsed.flight_class, parsed.distance_km)
            result['emission_factor'] = factor_info['factor']
            result['emission_factor_source'] = factor_info['source']
            result['co2e_kg'] = parsed.distance_km * factor_info['factor']
        elif parsed.category == 'hotel' and qty:
            factor_info = TRAVEL_FACTORS['hotel']
            result['emission_factor'] = factor_info['factor']
            result['emission_factor_source'] = factor_info['source']
            result['co2e_kg'] = qty * factor_info['factor']
        elif parsed.category == 'ground_transport' and qty:
            factor_info = TRAVEL_FACTORS['taxi']
            result['emission_factor'] = factor_info['factor']
            result['emission_factor_source'] = factor_info['source']
            result['co2e_kg'] = qty * factor_info['factor']
        elif parsed.category == 'rail' and qty:
            factor_info = TRAVEL_FACTORS['rail']
            result['emission_factor'] = factor_info['factor']
            result['emission_factor_source'] = factor_info['source']
            result['co2e_kg'] = qty * factor_info['factor']
        else:
            result['extra_flags'].append(
                "Cannot calculate emissions: missing quantity or unknown category"
            )

    return result


@transaction.atomic
def run_pipeline(datasource: DataSource, parsed_rows: list[ParsedRow]) -> dict:
    """
    Convert a list of ParsedRow objects into EmissionRecord DB rows.

    Returns summary statistics.
    """
    org = datasource.organization
    records_to_create = []
    parse_log = []
    total = len(parsed_rows)
    parsed = 0
    failed = 0
    flagged = 0

    for pr in parsed_rows:
        # Fatal parse errors — row couldn't be read at all
        if pr.parse_error:
            failed += 1
            parse_log.append({'row': pr.row_number, 'error': pr.parse_error})
            continue

        # Apply emission factors
        ef_result = _apply_emission_factor(pr, org)
        all_flags = pr.flag_reasons + ef_result['extra_flags']
        is_flagged = pr.is_flagged or bool(ef_result['extra_flags'])

        # Resolve plant code to name if org has a plant code map
        location = pr.location
        if location and location in org.plant_code_map:
            location = f"{location} — {org.plant_code_map[location]}"

        record = EmissionRecord(
            organization=org,
            source=datasource,
            scope=pr.scope,
            category=pr.category,
            activity_date=pr.activity_date,
            activity_period_end=pr.activity_period_end,
            source_row_data=_sanitize_json(pr.source_row_data),
            source_row_number=pr.row_number,
            raw_quantity=pr.raw_quantity,
            raw_unit=pr.raw_unit,
            normalized_quantity=ef_result['normalized_quantity'],
            normalized_unit=ef_result['normalized_unit'],
            emission_factor=ef_result['emission_factor'],
            emission_factor_source=ef_result['emission_factor_source'],
            co2e_kg=ef_result['co2e_kg'],
            location=location,
            vendor=pr.vendor,
            description=pr.description,
            origin=pr.origin,
            destination=pr.destination,
            flight_class=pr.flight_class,
            distance_km=pr.distance_km,
            status=EmissionRecord.STATUS_PENDING,
            is_flagged=is_flagged,
            flag_reasons=all_flags,
        )
        records_to_create.append(record)
        parsed += 1
        if is_flagged:
            flagged += 1

    # Bulk insert for performance
    EmissionRecord.objects.bulk_create(records_to_create)

    # Update datasource stats
    datasource.total_rows = total
    datasource.parsed_rows = parsed
    datasource.failed_rows = failed
    datasource.flagged_rows = flagged
    datasource.status = DataSource.STATUS_COMPLETED
    datasource.parse_log = parse_log
    datasource.save()

    return {
        'total_rows': total,
        'parsed_rows': parsed,
        'failed_rows': failed,
        'flagged_rows': flagged,
        'parse_log': parse_log,
    }
