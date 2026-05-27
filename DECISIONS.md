# Design Decisions

## SAP: Flat file (ALV export) over IDoc/OData

**Chose:** SAP ABAP List Viewer (ALV) flat file export — semicolon or tab-delimited, produced by running MB51 (Material Document List) or ME2M (Purchase Orders by Material) and choosing "Spreadsheet" export.

**Why not IDoc?** IDocs require an SAP ALE/EDI middleware setup. That's a multi-week SAP Basis engagement. The sustainability team would need to involve the SAP technical team, which could take months to configure.

**Why not OData (SAP Gateway)?** S/4HANA has a `MM_MATERIAL_DOCUMENT_SRV` OData service, but it requires: (a) SAP Gateway enabled (not always on), (b) OAuth2/SAML auth setup with the client's SAP, (c) client's IT to whitelist our IP. Realistic setup time: 2–6 weeks.

**Why not BAPI?** Same problem — requires SAP RFC connectivity, which is blocked by most corporate firewalls and requires VPN/network peering.

**The realistic path:** The sustainability manager emails the SAP team, they run the report and send back a .xlsx or .csv. This is what actually happens in practice. We handle that file.

**What we handle specifically:**
- German and English column headers (SAP language setting varies)
- Semicolon and tab delimiters (ALV export options)
- European number format (1.234,56)
- German date format (DD.MM.YYYY)
- Movement type codes to distinguish consumption from procurement
- Plant code lookup via org-configurable map

**What we ignore:**
- Company code (we treat the whole org as one entity — multi-company-code is a future feature)
- WBS elements (project accounting not relevant for standard emissions reporting)
- Storage location (sub-plant detail not needed at GHG Protocol reporting granularity)
- Batch/serial number

**What I'd ask the PM:**
- "Do their SAP reports come in German or English headers by default?"
- "Do they want plant-level emissions broken out in reports, or consolidated?"
- "What date range are we ingesting — calendar year or fiscal year?"

---

## Utility: Portal CSV export over Green Button or PDF

**Chose:** Portal CSV export — the file a user downloads from the utility provider's online portal.

**Why not Green Button (ESPI XML)?**
Green Button is technically correct — it's a US DOE standard for smart meter data and is mandated for many US utilities. But in practice:
1. Most corporate users don't know it exists
2. Green Button OAuth setup requires registering an app with each utility individually
3. UK/EU equivalents are completely non-standardized (each utility has proprietary formats)
4. The ESPI XML schema is complex — deserializing it correctly is non-trivial

**Why not PDF bills?**
PDF parsing is fragile. Utility bills change layout every few years. `pdfplumber` and `camelot` can extract tabular data, but: (a) scanned/photographed PDFs fail entirely, (b) layout changes break extraction, (c) we'd need to maintain separate parsers for each utility. Portal CSV is the same data, cleaner.

**Key decision — billing period alignment:**
Utility bills don't align with calendar months. A bill covering Jan 15 – Feb 14 spans two months. We use `period_start` as the activity date (not period_end), because that's when the consumption began. We flag bills > 45 days as likely estimated readings.

**What would break in real deployment:**
- Utilities that only offer PDF bills (some smaller regional utilities)
- Interval data (15-minute smart meter readings) — our model is too coarse
- Multi-site accounts where one CSV row covers multiple meters

---

## Travel: Navan (formerly TripActions) CSV export over Concur API

**Chose:** Navan CSV export (supports Concur column names via field mapping).

**Why Navan over Concur?**
Navan has been growing rapidly since 2020 and is displacing Concur in mid-to-large enterprise. Their export format is cleaner than Concur's legacy format. We support Concur column names via the field mapping table anyway.

**Why CSV over Concur API?**
Concur's SAP Concur API requires: (a) an active SAP Concur subscription, (b) OAuth2 client credentials from the client's Concur admin, (c) API calls per travel category. Implementation time: 1 week minimum. For a prototype, CSV export covers the same data.

**Distance calculation for flights:**
The biggest challenge in travel data. Options considered:
1. **Expect distance in export** — not reliable, many exports omit it
2. **Use great-circle distance from airport codes** — chosen approach. Accurate to ~3% vs actual flight path. Good enough for ESG reporting; ICAO itself uses this method.
3. **Use an aviation distance API** — adds external dependency, latency, and cost per lookup

We hardcode coordinates for 80+ major airports. For unknown codes, we flag the record. This covers ~90% of typical corporate routes; the analyst reviews the rest.

**Flight class emission factors:**
- Economy short-haul: 0.255 kg CO₂e/km (includes RFI = 2.0)
- Economy long-haul: 0.195 kg CO₂e/km
- Business short-haul: 0.680 kg CO₂e/km (2.67× economy, per GHG Protocol guidance)
- Long-haul/short-haul threshold: 3,700 km

Including RFI is the correct approach for Scope 3 Category 6 under GHG Protocol. Some corporate reporters exclude it (their choice), but the scientific consensus (IPCC AR5) supports including it.

**What we ignore:**
- Per-leg fuel burn (we use aggregate factors)
- Loyalty routing (some travelers fly JFK→CDG→SIN instead of direct)
- Bleisure travel personal day splits

---

## Authentication: Thin UserProfile wrapper, not custom User

**Chose:** Standard `django.contrib.auth.User` + `UserProfile` (OneToOne) for role/org mapping.

**Why not custom User model?**
Django documentation says to set a custom user model from project start. We're starting fresh — we could. But the UserProfile approach is deliberately more portable:
1. Easier to add SSO (SAML/OAuth) later — just create the profile on first login
2. Easier to support multiple org memberships (one User, multiple UserProfiles)
3. Less risk of migration conflicts with third-party packages that assume `auth.User`

**Role model:** Two roles only — admin and analyst. No granular permissions per source type. A real system might want "can approve SAP but not travel" permissions, but that's over-engineering for this prototype.

---

## Emission factors: DESNZ 2023 as primary source

**Chose:** UK Department for Energy Security and Net Zero (formerly BEIS) GHG Conversion Factors 2023 for fuel and transport. IEA 2023 for electricity. ICAO for flights.

**Why DESNZ over EPA?**
DESNZ publishes more granular fuel factors and updates annually. They're internationally accepted and used for corporate ESG reporting outside the US. The client is a European enterprise (SAP data with German headers), so DESNZ is appropriate.

**Why IEA for electricity?**
Grid emission factors vary by country and year. The IEA's world average (0.233 kg CO₂e/kWh) is a reasonable default. We make it configurable per org precisely because an org in Norway (0.009) and an org in Poland (0.760) should use their actual grid mix.

---

## Synchronous processing (no Celery)

**Chose:** Parse and normalize synchronously in the upload request.

**Why:** Celery + Redis is significant infrastructure. For files under 10k rows (typical SAP extract), parsing takes 1–5 seconds — acceptable in a web request. We set a 50MB file limit.

**What this breaks at scale:** Files with 100k+ rows (possible for a large enterprise with many plants over a year). Those would time out. That's documented in TRADEOFFS.md.

---

## Flagging: Parser flags, not exceptions

**Chose:** Flag suspicious rows instead of rejecting them.

**Why:** A negative quantity in SAP movement type 202 (reversal) is valid data — it means goods were returned. A 45-day billing period is unusual but not necessarily wrong. Rejecting these silently would lose data. Instead, we flag them and let the analyst decide. The analyst has domain context that the parser doesn't.

The review queue is the handoff point: parser raises concerns, analyst exercises judgment.

---

## What I'd ask the PM if I could

1. **Multi-company-code SAP:** Do they have subsidiary companies in SAP with separate company codes? If yes, we need to add `company_code` to DataSource and consider cross-company reporting.
2. **Fiscal vs calendar year:** Most emissions reporting is calendar year, but some clients report on a fiscal year. Affects date range filtering.
3. **Market-based vs location-based Scope 2:** GHG Protocol allows both methods. Market-based uses supplier-specific emission factors (from energy attribute certificates). Location-based uses grid averages. Which does this client report?
4. **Scope 3 completeness:** Are we ingesting all Scope 3 or just travel? Category 1 (purchased goods) would require spend data + EEIO factors.
5. **Audit standard:** Are reports going to GHG Protocol auditors, CDP, or internal only? Determines how strict we need to be about uncertainty quantification.
