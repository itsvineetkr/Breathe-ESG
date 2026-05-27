# Source Research

## Source 1: SAP Flat File (MB51/ME2M)

### What I researched

SAP has four main ways to export data relevant to ESG:

1. **ABAP List Viewer (ALV) flat file** — What we chose. The most common path: SAP user runs a standard transaction report (MB51 for material documents, ME2M for purchase orders), the list appears on screen, they choose "List → Export → Spreadsheet". Produces a semicolon or tab-delimited file.

2. **IDoc (Intermediate Document)** — SAP's native EDI format. XML or fixed-width. Requires ALE/middleware configuration on the SAP side. Typical setup: 2–6 weeks with SAP Basis involvement.

3. **OData Service** — Modern REST APIs in SAP S/4HANA. `MM_MATERIAL_DOCUMENT_SRV` service exposes MB51 data via OData v2/v4. Requires SAP Gateway, auth configuration, and the client's IT team. Realistic lead time: 4–12 weeks.

4. **BAPI** — Remote Function Call interface. Requires SAP RFC connectivity (port 3300), which is almost always firewall-blocked externally.

**Key learning:** SAP uses different column names based on language settings. An SAP configured in German (common in Europe) uses "Buchungsdatum" instead of "Posting Date", "Menge" instead of "Quantity", "Mengeneinheit" instead of "Unit of Measure". Our parser handles both via a comprehensive field mapping table with 50+ mapped fields.

**MB51 Movement Types:**
- 201: Goods issue to cost center (direct fuel consumption) → Scope 1
- 261: Goods issue for production order (manufacturing fuel) → Scope 1
- 101: Goods receipt from purchase order (procurement) → could be Scope 1 or Scope 3
- 202: Reversal of 201 (returned goods) → produces negative quantities, which we flag
- 221: Goods issue to project → Scope 1

### What the sample data looks like and why

`sap_mb51_fuel_procurement.csv` — semicolon-delimited, German headers (because the fictional client's SAP is configured for DE locale), dates in DD.MM.YYYY format.

**Intentionally realistic features:**
- Material codes (DI0001, BE0001, NG0001) as SAP assigns them — opaque, not self-describing
- German material names: "Diesel EN590", "Benzin 95 RON", "Heizöl EL" (heating oil)
- Plant codes: WERK01, WERK02, WERK03 — meaningless without the lookup table
- Movement type 202 producing a negative quantity (reversal) — triggers a flag
- One row with movement type 101 (procurement receipt) — triggers ambiguity flag
- One row with unknown material XX9999 — triggers classification failure
- One row with zero quantity (Erdgas) — triggers zero-quantity flag
- Mix of consumption (201/261) and procurement (101) to test parser logic

### What would break in real deployment

- SAP exports with page break lines inserted by ALV (we handle this, but edge cases remain)
- Clients with custom ALV display variants that rename or reorder columns
- SAP outputs using fixed-width format instead of delimiter (rare but exists)
- Material descriptions that don't clearly indicate fuel type (e.g., "MAT-0042" with no description) — requires manual plant master data lookup
- Split company codes across multiple files with different currency units

---

## Source 2: Utility Portal CSV (Electricity)

### What I researched

Major utility providers and their export options:

**UK:**
- **British Gas Business:** Portal CSV with columns: Site Name, MPAN, Period Start, Period End, kWh Consumed, Standing Charge, Unit Rate, Total Cost
- **National Grid / SSE:** Similar structure; some use "Read Date" instead of period dates
- **Octopus Energy:** More modern API (Octopus Kraken API) but CSV export available

**US:**
- **PG&E (Pacific Gas & Electric):** "Green Button Download My Data" (ESPI XML) and a portal CSV
- **Con Edison (NYC):** Portal with "Usage History" CSV: Account, Meter, Date, Peak kWh, Off-Peak kWh, Total kWh
- **Duke Energy:** Similar structure

**Germany:**
- **E.ON, RWE:** Portal exports in German, use "Verbrauch (kWh)" for consumption

**Key learning:** Billing periods are the main challenge. A meter is read on a cycle (every ~28–31 days), not on calendar month boundaries. A bill from January 8 to February 6 is entirely legitimate. Our model stores `activity_period_start` and `activity_period_end` separately for this reason.

**MPAN (UK):** Meter Point Administration Number — the unique identifier for a supply point in the UK. 21 digits, looks like `2100012345678` or in groups. Equivalent to ESI ID in the US or EAN in Germany.

### What the sample data looks like and why

`utility_portal_electricity.csv` — comma-delimited, English headers (this utility is a German operation using English portal software, common for multinationals).

**Intentionally realistic features:**
- Multiple meters at the same address (MTR-BER-001 and MTR-BER-002 at Berliner Str. 45) — different sub-meters for plant vs warehouse
- Hamburg Port meter (ACC-9901-22) with January 3 – February 2 billing period (non-calendar-month)
- Frankfurt depot (ACC-0011-55) with a 90-day billing period (January–March in one line) — triggers the "long billing period" flag
- Munich data centre (MTR-MUC-002) with zero usage — triggers zero-usage flag
- Bremen meter with a ~28-day period (Feb 15 – Mar 14) — normal, no flag
- Different rate schedules (Industrial Tariff A/B, Commercial Tariff C) — shows that a real export has tariff structure data we preserve but don't use

### What would break in real deployment

- Utilities that don't offer CSV export (some require calling customer service)
- Multi-rate (peak/off-peak) exports where kWh is split — need to sum them
- Interval data (smart meters) providing 15-minute readings — our model is too coarse
- Bills in non-kWh units (some industrial sites use MMBTU, BTU, or therms) — our unit table handles therms and BTU but is not exhaustive
- Solar feed-in credits creating negative values in the export

---

## Source 3: Corporate Travel Platform (Navan/Concur)

### What I researched

**Navan (formerly TripActions):**
- "Reports → Trip Reports → Export as CSV"
- Fields: Traveler, Booking Date, Travel Date, Segment Type (Air/Hotel/Car), Origin, Destination, Cabin, Carrier, Hotel Name, Check-in, Check-out, Amount, Currency, Cost Center
- Airport codes are IATA 3-letter codes (JFK, LHR, SIN)
- Distance NOT included in Navan's standard export — must be calculated

**Concur:**
- "Reporting → Standard Reports → Travel Detail Report → Export"
- Very similar fields; more legacy column naming ("Expense Type" instead of "Segment Type")
- Concur SAP Concur API (Oauth2) is available but requires 2FA setup per client

**Egencia (Expedia B2B):**
- CSV export available from portal
- Includes distance for flights on international routes, not domestic

**Key learning:** Almost no travel platform provides calculated distances in their standard export. They provide route (airport codes) or hotel city, but distance calculation is left to the reporting tool. This is why our `airport_distance_km()` function using haversine distance is necessary, not optional.

**GHG Protocol on Scope 3 Category 6 (Business Travel):**
The standard approach is:
1. Flights: distance × emission factor (kg CO₂e / passenger-km) × class multiplier
2. Hotels: nights × average hotel emission factor (per room-night)
3. Ground: distance × mode-specific factor

The ICAO Carbon Calculator uses the same approach but with more detailed aircraft type data (we use aggregate factors).

### What the sample data looks like and why

`travel_navan_export.csv` — Navan export format, comma-delimited.

**Intentionally realistic features:**
- Round-trip flights as separate rows (departure and return are separate records in Navan) — common pattern
- Mixed currencies (EUR, GBP, SGD, INR) — preserved but not used in calculations
- Marc Dubois FRA→JFK in business class — tests business class emission factor selection
- James Cooper LHR→SIN — long-haul economy, tests distance threshold (10,841 km > 3,700 km threshold)
- Julia Weber FRA→XYZ — unknown airport code, triggers flag "cannot calculate distance"
- Klaus Fischer BER→MUC with no distance field — tests airport code distance calculation
- Klaus Fischer Munich→Amsterdam by rail — tests rail segment handling
- Taxi records with only distance (no route), Anna Schmidt's Paris taxis — tests ground transport
- Hotel with check-in/out dates but no explicit nights count — tests nights calculation from dates
- Priya Patel hotel in Mumbai with INR amount — tests currency handling (amount preserved, not converted)
- Multiple cost centers — shows that department-level attribution is preserved in source_row_data

### What would break in real deployment

- Unknown airport codes (we have ~80 airports; there are ~9,000 IATA-coded airports globally)
- Domestic train journeys without distance (some platforms only record origin city, not distance)
- Rideshare (Uber/Lyft) without distance — these appear in Concur expense reports but rarely have distance data
- Multi-leg flights booked as one record (a single "JFK → CDG → AMS" booking appearing as one row, not two legs)
- Personal vs. business split for extended trips where employees add personal days — we can't distinguish without explicit marking
