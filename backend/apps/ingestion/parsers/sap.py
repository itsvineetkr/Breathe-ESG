"""
parsers/sap.py

SAP Flat File Parser — MB51 / ME2M style exports.

Format decision: We handle SAP's ABAP List Viewer (ALV) export format, which is
the most common way sustainability teams actually extract data from SAP. The SAP
team runs report MB51 (Material Document List) or ME2M (Purchase Orders by Material),
then exports as "Spreadsheet" (which produces a tab-separated or semicolon-separated file).

We do NOT attempt IDoc/BAPI/OData integration. Reasons:
1. IDoc requires SAP middleware setup that's outside our scope.
2. OData services exist (SAP S/4HANA) but require SAP Gateway config per client.
3. Flat file export is how 90% of ESG data from SAP actually arrives in practice —
   a sustainability manager emails you a .xlsx or .csv from their desktop.

What we handle:
- MB51: Material document list (goods movements = fuel consumption)
  Movement types: 201/261 = goods issue (consumption), 101 = GR from vendor (procurement)
- ME2M: Purchase order lines (procurement spend on fuel, utilities, etc.)
- Both German and English column headers (SAP language setting varies by client)
- Semicolon (;) and tab (\t) delimiters
- European number format (1.234,56) and ISO date format (DD.MM.YYYY)
- Paging headers that ALV sometimes inserts mid-file

What we ignore:
- IDoc segments (require XML parsing + SAP-specific segment definitions)
- BAPI return structures
- SAP internal company codes (we map to org-level anyway)
- WBS elements (project accounting — not relevant for emissions)
"""

import io
import csv
from typing import Optional
import pandas as pd

from .base import ParsedRow, parse_date, parse_float, classify_material

# ─── Field mapping tables ────────────────────────────────────────────────────
#
# SAP column names vary by:
# 1. Language setting (EN = English, DE = German)
# 2. SAP release (ECC vs S/4HANA)
# 3. Client customization (they rename columns in ALV layouts)
#
# We maintain both EN and DE names. Org-level overrides can extend this.

SAP_FIELD_MAPPINGS = {
    # Date fields
    'Posting Date': 'posting_date',
    'Buchungsdatum': 'posting_date',
    'Belegdatum': 'posting_date',
    'Document Date': 'posting_date',
    'Pstng Date': 'posting_date',
    'Posting date': 'posting_date',

    # Quantity
    'Qty in UnE': 'quantity',
    'Quantity': 'quantity',
    'Menge': 'quantity',
    'Qty': 'quantity',
    'Amount': 'quantity',
    'Mng.i.EinheitBest.': 'quantity',
    'Quantity in Unit of Entry': 'quantity',

    # Unit of measure
    'Un': 'unit',
    'UoM': 'unit',
    'BUn': 'unit',
    'Unit': 'unit',
    'Base Unit': 'unit',
    'Einheit': 'unit',
    'Mengeneinheit': 'unit',
    'UOM': 'unit',
    'MEINS': 'unit',
    'Base unit of measure': 'unit',

    # Material / description
    'Material': 'material_code',
    'Materialnummer': 'material_code',
    'Material No.': 'material_code',
    'MATNR': 'material_code',

    'Short Text': 'material_description',
    'Material Description': 'material_description',
    'Kurztext': 'material_description',
    'Matbez.': 'material_description',
    'Bezeichnung': 'material_description',
    'Description': 'material_description',

    # Plant (facility/location)
    'Plant': 'plant_code',
    'Werk': 'plant_code',
    'WERKS': 'plant_code',

    # Movement type (determines if this is consumption or procurement)
    'Mvt': 'movement_type',
    'Movement Type': 'movement_type',
    'Bewegungsart': 'movement_type',
    'Mvmt Type': 'movement_type',
    'BwArt': 'movement_type',

    # Vendor (for procurement records)
    'Vendor': 'vendor',
    'Supplier': 'vendor',
    'Lieferant': 'vendor',
    'Vendor Name': 'vendor',

    # Document number (for traceability)
    'Mat. Doc.': 'document_number',
    'Material Document': 'document_number',
    'Belegnummer': 'document_number',
    'MBLNR': 'document_number',
    'Document Number': 'document_number',
}

# SAP movement types that represent fuel/material consumption (Scope 1 relevant)
# 201: Goods issue to cost center (direct consumption)
# 261: Goods issue for production order
# 221: Goods issue to project
CONSUMPTION_MOVEMENT_TYPES = {'201', '261', '221', '251', '601'}

# Movement types that represent procurement (Scope 3 potential)
PROCUREMENT_MOVEMENT_TYPES = {'101', '501', '521'}


def _detect_delimiter(content: str) -> str:
    """Detect whether the file uses tab or semicolon as delimiter."""
    sample = content[:2000]
    tab_count = sample.count('\t')
    semicolon_count = sample.count(';')
    comma_count = sample.count(',')
    return '\t' if tab_count > semicolon_count and tab_count > comma_count else (
        ';' if semicolon_count >= comma_count else ','
    )


def _strip_alv_headers(lines: list[str]) -> list[str]:
    """
    SAP ALV sometimes inserts page break lines like:
    '|      Page 2     |' or blank lines between header repeats.
    Remove these so pandas can parse cleanly.
    """
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('|') and 'Page' in stripped:
            continue
        cleaned.append(line)
    return cleaned


def _remap_headers(df: pd.DataFrame, org_overrides: dict) -> pd.DataFrame:
    """
    Apply field mapping to normalize column names.
    Org-level overrides take precedence over built-in mappings.
    """
    mapping = {**SAP_FIELD_MAPPINGS, **org_overrides}
    rename_map = {}
    for col in df.columns:
        col_stripped = col.strip()
        if col_stripped in mapping:
            rename_map[col] = mapping[col_stripped]
    return df.rename(columns=rename_map)


def parse_sap_file(file_content: bytes, org_field_overrides: dict = None) -> list[ParsedRow]:
    """
    Parse a SAP MB51/ME2M flat file export.

    Args:
        file_content: Raw bytes of the uploaded file.
        org_field_overrides: Dict of {raw_header: normalized_field} from org config.

    Returns:
        List of ParsedRow objects (flagged or clean).
    """
    org_field_overrides = org_field_overrides or {}
    results = []

    try:
        # Decode — SAP exports are usually UTF-8 or Windows-1252 (Western Europe)
        try:
            content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            content = file_content.decode('windows-1252')

        # Handle Excel files
        if content[:2] in ('\xff\xfe', '\xfe\xff') or b'\x00' in file_content[:100]:
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            lines = content.splitlines()
            lines = _strip_alv_headers(lines)
            delimiter = _detect_delimiter('\n'.join(lines[:20]))
            df = pd.read_csv(io.StringIO('\n'.join(lines)), sep=delimiter, dtype=str)

    except Exception as e:
        # Fatal parse error — return a single error row
        return [ParsedRow(
            row_number=0,
            source_row_data={'error': str(e)},
            parse_error=f"Could not read file: {e}",
        )]

    # Clean whitespace from all string columns
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # Remap headers
    df = _remap_headers(df, org_field_overrides)

    for idx, row in df.iterrows():
        row_num = idx + 2  # +1 for header, +1 for 1-indexing
        raw = row.to_dict()

        parsed = ParsedRow(row_number=row_num, source_row_data=raw)

        # ── Date ──────────────────────────────────────────────────────────────
        date_val = raw.get('posting_date', '')
        parsed.activity_date = parse_date(str(date_val))
        if not parsed.activity_date:
            parsed.add_flag(f"Could not parse date: '{date_val}'")

        # ── Quantity ──────────────────────────────────────────────────────────
        qty_val = raw.get('quantity', '')
        parsed.raw_quantity = parse_float(qty_val)
        if parsed.raw_quantity is None:
            parsed.add_flag(f"Missing or unparseable quantity: '{qty_val}'")
        elif parsed.raw_quantity < 0:
            parsed.add_flag(f"Negative quantity ({parsed.raw_quantity}) — possible return/reversal")
        elif parsed.raw_quantity == 0:
            parsed.add_flag("Zero quantity — likely a header or totals row")

        # ── Unit ──────────────────────────────────────────────────────────────
        parsed.raw_unit = str(raw.get('unit', '')).strip()
        if not parsed.raw_unit:
            parsed.add_flag("Missing unit of measure")

        # ── Material / Description ────────────────────────────────────────────
        material_desc = str(raw.get('material_description', '')).strip()
        material_code = str(raw.get('material_code', '')).strip()
        parsed.description = material_desc or material_code

        # ── Plant code → location ─────────────────────────────────────────────
        plant_code = str(raw.get('plant_code', '')).strip()
        parsed.location = plant_code  # caller resolves plant code to name via org.plant_code_map

        # ── Vendor ────────────────────────────────────────────────────────────
        parsed.vendor = str(raw.get('vendor', '')).strip()

        # ── Scope/Category classification ─────────────────────────────────────
        # First try material description, then fall back to unit
        scope, category = classify_material(material_desc, parsed.raw_unit)
        parsed.scope = scope
        parsed.category = category

        # Movement type refines classification:
        # Consumption movements are typically Scope 1 (direct use)
        # Procurement movements could be Scope 3 (purchased goods)
        mvt = str(raw.get('movement_type', '')).strip()
        if mvt in PROCUREMENT_MOVEMENT_TYPES and scope == 'scope_1':
            # Procurement of fuel — may still be Scope 1 if they're buying for consumption,
            # but flag for analyst review since it's ambiguous.
            parsed.add_flag(
                f"Movement type {mvt} is a procurement receipt — "
                "verify this is direct fuel consumption (Scope 1) not stock transfer"
            )

        if not scope or category == 'unknown':
            parsed.add_flag(
                f"Could not classify material '{material_desc}' (unit: '{parsed.raw_unit}') "
                "into a scope/category — analyst must classify manually"
            )

        results.append(parsed)

    return results
