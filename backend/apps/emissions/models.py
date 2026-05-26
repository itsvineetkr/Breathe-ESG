"""
emissions/models.py

EmissionRecord is the central fact table of this system.
Every row that comes through the ingestion pipeline becomes an EmissionRecord.

Key design decisions:

1. We store BOTH raw and normalized quantities.
   Raw: exactly as it appeared in the source file.
   Normalized: converted to a standard base unit (liters, kWh, km, room_nights).
   This lets auditors verify the conversion arithmetic.

2. source_row_data (JSONField) stores the original row verbatim.
   If a client disputes a number, we can show exactly what came from their system.

3. emission_factor and co2e_kg are stored on the record, not computed at query time.
   Emission factors change year to year. Locking the factor at ingestion time means
   historical reports don't silently change when we update factors.
   emission_factor_source tracks which version of which standard was used.

4. Status is a simple 3-state machine: pending_review → approved | rejected.
   Only approved records are included in reports and carbon totals.
   Rejected records are kept (not deleted) for audit trail completeness.

5. reviewed_by / reviewed_at are set when an analyst acts on the record.
   Combined with AuditLog, this gives full who/when/what traceability.

6. Scope categorization follows GHG Protocol:
   Scope 1: Direct emissions (fuel combustion on-site or in owned vehicles)
   Scope 2: Indirect from purchased electricity/heat
   Scope 3: All other indirect (travel, supply chain, etc.)
"""

import uuid
from django.db import models
from apps.accounts.models import Organization, UserProfile
from apps.ingestion.models import DataSource


class EmissionRecord(models.Model):
    # ── Scope classification ──────────────────────────────────────────────────
    SCOPE_1 = 'scope_1'
    SCOPE_2 = 'scope_2'
    SCOPE_3 = 'scope_3'
    SCOPE_CHOICES = [
        (SCOPE_1, 'Scope 1 — Direct emissions'),
        (SCOPE_2, 'Scope 2 — Purchased electricity/heat'),
        (SCOPE_3, 'Scope 3 — Value chain & travel'),
    ]

    # ── Activity category ─────────────────────────────────────────────────────
    # Scope 1
    CATEGORY_DIESEL = 'diesel'
    CATEGORY_PETROL = 'petrol'
    CATEGORY_NATURAL_GAS = 'natural_gas'
    CATEGORY_LPG = 'lpg'
    CATEGORY_OTHER_FUEL = 'other_fuel'
    # Scope 2
    CATEGORY_ELECTRICITY = 'electricity'
    # Scope 3
    CATEGORY_FLIGHT = 'flight'
    CATEGORY_HOTEL = 'hotel'
    CATEGORY_GROUND_TRANSPORT = 'ground_transport'
    CATEGORY_RAIL = 'rail'
    CATEGORY_PROCUREMENT = 'procurement'
    CATEGORY_UNKNOWN = 'unknown'

    CATEGORY_CHOICES = [
        (CATEGORY_DIESEL, 'Diesel fuel'),
        (CATEGORY_PETROL, 'Petrol / Gasoline'),
        (CATEGORY_NATURAL_GAS, 'Natural gas'),
        (CATEGORY_LPG, 'LPG'),
        (CATEGORY_OTHER_FUEL, 'Other fuel'),
        (CATEGORY_ELECTRICITY, 'Electricity'),
        (CATEGORY_FLIGHT, 'Flight'),
        (CATEGORY_HOTEL, 'Hotel'),
        (CATEGORY_GROUND_TRANSPORT, 'Ground transport'),
        (CATEGORY_RAIL, 'Rail'),
        (CATEGORY_PROCUREMENT, 'Procurement'),
        (CATEGORY_UNKNOWN, 'Unknown — needs classification'),
    ]

    # ── Review status ─────────────────────────────────────────────────────────
    STATUS_PENDING = 'pending_review'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # ── Core fields ───────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='emission_records'
    )
    source = models.ForeignKey(
        DataSource, on_delete=models.CASCADE, related_name='records'
    )

    # ── Classification ────────────────────────────────────────────────────────
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_UNKNOWN)

    # ── Time ──────────────────────────────────────────────────────────────────
    activity_date = models.DateField(null=True, blank=True)
    activity_period_end = models.DateField(
        null=True, blank=True,
        help_text="For billing periods that span multiple days (e.g. utility bills)."
    )

    # ── Source of truth ───────────────────────────────────────────────────────
    source_row_data = models.JSONField(
        help_text="Original row from source file, verbatim. Never modified."
    )
    source_row_number = models.IntegerField(
        help_text="Row number in original file (1-indexed after header)."
    )

    # ── Raw quantities (as-received) ──────────────────────────────────────────
    raw_quantity = models.FloatField(null=True, blank=True)
    raw_unit = models.CharField(max_length=50, blank=True)

    # ── Normalized quantities (standard base unit) ────────────────────────────
    # Fuel → liters, Electricity → kWh, Distance → km, Hotel → room_nights
    normalized_quantity = models.FloatField(null=True, blank=True)
    normalized_unit = models.CharField(max_length=50, blank=True)

    # ── Emission calculation ──────────────────────────────────────────────────
    emission_factor = models.FloatField(
        null=True, blank=True,
        help_text="kg CO2e per normalized_unit. Locked at ingestion time."
    )
    emission_factor_source = models.CharField(
        max_length=100, blank=True,
        help_text="Source standard and year, e.g. 'DESNZ 2023' or 'ICAO 2023 + RFI'."
    )
    co2e_kg = models.FloatField(
        null=True, blank=True,
        help_text="kg CO2e = normalized_quantity × emission_factor. Only for approved records."
    )

    # ── Contextual metadata ───────────────────────────────────────────────────
    location = models.CharField(
        max_length=255, blank=True,
        help_text="Plant code, meter address, hotel, or city."
    )
    vendor = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=500, blank=True)

    # Travel-specific
    origin = models.CharField(max_length=10, blank=True, help_text="Airport IATA code")
    destination = models.CharField(max_length=10, blank=True, help_text="Airport IATA code")
    flight_class = models.CharField(max_length=20, blank=True)
    distance_km = models.FloatField(null=True, blank=True)

    # ── Review workflow ───────────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    is_flagged = models.BooleanField(default=False)
    flag_reasons = models.JSONField(
        default=list,
        help_text="List of flag reason strings from parser + manual flags."
    )
    analyst_notes = models.TextField(
        blank=True,
        help_text="Free-text notes added by analyst during review."
    )
    reviewed_by = models.ForeignKey(
        UserProfile, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_scope_display()} — {self.category} — {self.activity_date} — {self.co2e_kg} kg CO2e"

    @property
    def co2e_tonnes(self):
        if self.co2e_kg is not None:
            return self.co2e_kg / 1000.0
        return None

    class Meta:
        ordering = ['-activity_date', 'source']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'scope']),
            models.Index(fields=['organization', 'activity_date']),
            models.Index(fields=['source', 'status']),
        ]
