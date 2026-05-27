# Data Model

## Overview

The data model is organized around a clear tenant hierarchy:

```
Organization
  └── UserProfile (user ↔ org ↔ role mapping)
  └── DataSource (one per file upload)
       └── EmissionRecord (one per normalized row)
            └── AuditLog (one per state change)
```

---

## Organization

The root tenant. Every domain query is filtered by `organization_id`. This is enforced at the view layer (not the model layer) because Django's ORM doesn't have built-in row-level security.

| Field | Type | Rationale |
|---|---|---|
| `id` | UUID | UUIDs prevent enumeration attacks on tenant IDs |
| `name` | CharField | Human-readable |
| `slug` | SlugField (unique) | URL-safe identifier, auto-generated from name |
| `electricity_emission_factor` | FloatField | kg CO₂e/kWh. **Per-org configurable** because grid carbon intensity varies dramatically (UK: 0.207, US: 0.386, coal-heavy grids: 0.9+). Default is IEA 2023 world average (0.233). |
| `plant_code_map` | JSONField | SAP plant codes are opaque strings (e.g. "WERK01"). Without this lookup, location data is meaningless. Stored at org level because it's a one-time setup. |
| `field_mapping_overrides` | JSONField | Per-source-type column header remapping. Allows an org with a custom SAP ALV layout to map non-standard column names without changing the parser code. Structure: `{"SAP": {"MyQty": "quantity"}}` |

**Why not separate FieldMapping model?** For this prototype, storing overrides as a JSONField on Organization is sufficient and avoids over-engineering. A production system would benefit from a relational FieldMapping table with versioning, but that's in TRADEOFFS.md.

---

## UserProfile

Maps Django's built-in `User` to an `Organization + Role`. We deliberately **do not** extend or replace `auth.User`.

**Why not extend User?** Swapping `AUTH_USER_MODEL` in an existing project requires a new migration on every table that references User — including Django's own auth tables. It's risky and irreversible. The separate mapping approach is clean and supports future multi-org membership (one user in two orgs as an auditor).

| Field | Type | Rationale |
|---|---|---|
| `user` | OneToOneField → User | Standard Django user for authentication |
| `organization` | ForeignKey → Organization | Tenant binding |
| `role` | CharField (admin/analyst) | Role-based access control |
| `is_active` | BooleanField | Soft deactivation — we never delete users, for audit trail integrity |

**Role semantics:**
- `admin`: Upload data, manage team, view audit logs, configure org settings
- `analyst`: Review records (approve/reject/flag/note). Cannot upload or manage users.

---

## DataSource

One DataSource record per uploaded file. This is the "ingestion event" model.

| Field | Type | Rationale |
|---|---|---|
| `id` | UUID | |
| `organization` | FK | Tenant isolation |
| `source_type` | CharField (SAP/UTILITY/TRAVEL) | Determines which parser is used |
| `name` | CharField | User-provided human name — distinct from filename because one org may upload multiple SAP extracts for different periods |
| `raw_file` | FileField | **Always preserved.** If normalization logic changes (e.g., we add a new unit conversion), we can re-parse from the original. This is the audit source of truth at the file level. |
| `original_filename` | CharField | Stored separately because FileField path gets hashed by upload_to function |
| `uploaded_by` | FK → UserProfile | Who uploaded it |
| `status` | CharField | processing → completed / failed. Synchronous in this prototype; would be a Celery task state in production |
| `total_rows` | IntegerField | File's total data rows |
| `parsed_rows` | IntegerField | Successfully normalized rows |
| `failed_rows` | IntegerField | Rows with fatal parse errors (couldn't extract any usable data) |
| `flagged_rows` | IntegerField | Rows that parsed but triggered validation warnings |
| `field_mapping_override` | JSONField | Per-upload override (takes precedence over org-level). Useful for a one-off file with unusual headers. |
| `parse_log` | JSONField | List of `{row: N, error: "..."}` for failed rows — shown in the UI for debugging |

---

## EmissionRecord

The central fact table. One row per normalized activity record.

### Why store both raw AND normalized quantities?

`raw_quantity` + `raw_unit`: Exactly as they appeared in the source file (e.g., `5000 L`, `48250 kWh`).
`normalized_quantity` + `normalized_unit`: Converted to a standard base unit (liters, kWh, km, room_nights).

An auditor must be able to verify: "You said 5000 liters of diesel = 13,400 kg CO₂e. Show me."
The answer requires showing the raw quantity, the conversion to normalized unit, and the emission factor. Without storing both, you cannot reconstruct the calculation.

### Why store `emission_factor` and `emission_factor_source` on the record?

Emission factors change year over year (DESNZ updates annually in June). If we compute factors at query time, historical reports silently change when we update the factor table. **Locking the factor at ingestion time** means a report from January 2025 produces the same number in January 2026. This is a GHG Protocol requirement for consistent reporting.

### Source of truth fields

| Field | Rationale |
|---|---|
| `source_row_data` | The original row as a JSON dict — verbatim from the source file. Never modified. Lets you reconstruct the exact data that produced any record. |
| `source_row_number` | Row number in the original file for cross-referencing during disputes. |

### Scope/Category

```
Scope 1 (direct): diesel, petrol, natural_gas, lpg, other_fuel
Scope 2 (electricity): electricity
Scope 3 (indirect): flight, hotel, ground_transport, rail, procurement
```

Category `unknown` flags rows where the parser could not classify the material. These always land in the review queue with a flag.

### Review workflow

Three-state machine:
```
pending_review → (analyst action) → approved
pending_review → (analyst action) → rejected
approved → (re-review) → rejected
```

`is_flagged` is orthogonal to `status`. A row can be flagged AND approved (flag = "warning was acceptable"). A row can be unflagged without changing status.

Only `approved` records with non-null `co2e_kg` contribute to reports.

### CO₂e calculation

`co2e_kg = normalized_quantity × emission_factor`

For flights: `co2e_kg = distance_km × emission_factor_per_passenger_km`

Flight emission factors include ICAO's Radiative Forcing Index (RFI = 2.0), which accounts for non-CO₂ warming effects at altitude (contrails, cirrus formation). This is standard practice for corporate travel reporting under GHG Protocol Scope 3 Category 6.

---

## AuditLog

Every state-changing action creates an AuditLog entry. This table is append-only — entries are never deleted.

| Field | Rationale |
|---|---|
| `record` | FK to EmissionRecord (nullable) — null for datasource-level events |
| `datasource` | FK to DataSource (nullable) — null for record-level events |
| `action` | Enum: upload, parse_complete, approve, reject, edit, flag, unflag, add_note, scope_change |
| `old_values` | JSON snapshot of the record before the action |
| `new_values` | JSON snapshot after the action |
| `user` | Who did it |
| `timestamp` | Auto-set |
| `notes` | Free text (analyst's explanation) |

The `old_values`/`new_values` pair lets you reconstruct a record's state at any point in time without a separate versioning system.

---

## Multi-tenancy enforcement

Every view function:
1. Gets `request.user.profile` (which contains the org)
2. Filters all querysets with `organization=profile.organization`
3. Checks `profile.is_admin` before admin-only operations

This is enforced in view code, not at the DB level. In production, we'd add a custom Manager that automatically applies organization filtering, similar to how Django's sites framework scopes by site. That's a TRADEOFFS.md item.

---

## Indexes

```python
# EmissionRecord
Index(['organization', 'status'])    # review queue queries
Index(['organization', 'scope'])     # report aggregations
Index(['organization', 'activity_date'])  # time-range queries
Index(['source', 'status'])          # per-dataset status counts
```

---

## What this model does NOT do

- **Per-user permissions beyond role**: All admins see all org data; all analysts see all org data. No sub-org isolation.
- **Record versioning**: We track changes via AuditLog old/new values, but cannot time-travel a record to an arbitrary previous state without replaying audit events.
- **Supplier-level Scope 3**: Category 1 (purchased goods and services) requires spend data and industry-average emission intensities — out of scope.
- **Currency normalization**: We store raw amounts in original currency for reference but don't use them in emission calculations.
