# Tradeoffs — Things Deliberately Not Built

## 1. Background processing (Celery/Redis)

**What it is:** Offloading file parsing to a background worker so uploads return immediately, with a job status endpoint the frontend polls.

**Why it matters:** For files with 100k+ rows (a large enterprise running a full-year SAP extract for all plants), synchronous parsing in the HTTP request will time out at the web server level (typically 30s). The user gets a 504 with no indication of what happened.

**Why I didn't build it:** Celery + Redis requires: a Redis instance, a Celery worker process, a periodic beat scheduler, and a task result backend. On Railway or Render, this means at minimum two additional services. Setup adds ~2 days to the prototype timeline. The tradeoff is a 50MB file limit and the assumption that files stay under ~10k rows (realistic for quarterly SAP extracts from a single facility).

**What the production version looks like:**
```python
# views.py
task = parse_and_normalize.delay(datasource.id)
return Response({'task_id': task.id, 'status': 'processing'})

# Separate GET /ingestion/jobs/<task_id>/ for polling
```

---

## 2. Market-based Scope 2 accounting

**What it is:** The GHG Protocol's "Scope 2 Guidance" defines two methods:

- **Location-based:** Use the average emission factor for the grid where electricity is consumed. Simple; what we've built.
- **Market-based:** Use supplier-specific emission factors from energy attribute certificates (EACs) — Renewable Energy Certificates (RECs) in the US, Guarantees of Origin (GOs) in Europe. If a company has purchased 100% wind power via GOs, their market-based Scope 2 can be zero even if the grid average is high.

**Why it matters:** For companies with sustainability commitments (RE100 members), market-based is the relevant metric. Auditors increasingly expect both methods. CDP's disclosure requires both.

**Why I didn't build it:** Market-based accounting requires:
1. A separate data input for EAC/GO certificates (new ingestion source type)
2. Matching certificates to meter consumption by period and volume
3. Residual mix factors for uncertificated electricity (country-specific, updated annually)
4. Two parallel emission calculation paths on every EmissionRecord

This is genuinely complex. The data model would need a `CertificateRecord` model and a many-to-many with `EmissionRecord`. I scoped it out deliberately and would propose it as Sprint 2.

---

## 3. Configurable emission factor versioning

**What it is:** Emission factor standards (DESNZ, IPCC, ICAO) update annually. A record ingested in January 2025 using DESNZ 2023 factors might need to be recalculated in July 2025 when DESNZ 2024 publishes.

**Why it matters:** Year-over-year comparison breaks if you transparently update factors — 2024 totals change under your feet. For audit defensibility, you need to know "what factor was used for this record, from which version of which standard."

**What we built:** We store `emission_factor` and `emission_factor_source` on each record at ingestion time. A human can read "DESNZ 2023" and know the factor is locked. But there's no automated mechanism to:
- Notify analysts when factors update
- Bulk-recalculate with new factors on demand
- Produce parallel reports showing "old factors vs new factors"

**What the production version looks like:**
```python
class EmissionFactorVersion(models.Model):
    standard = models.CharField()  # "DESNZ", "IPCC"
    year = models.IntegerField()
    effective_date = models.DateField()
    factors = models.JSONField()   # {diesel: 2.68, petrol: 2.31, ...}
    is_current = models.BooleanField()
```
Each EmissionRecord gets a FK to the `EmissionFactorVersion` used, enabling bulk recalculation when needed.

**Why I didn't build it:** This is a data governance feature — important for mature ESG programs but overkill for a prototype. The current approach (locking factors at ingestion time with a source string) gives auditors what they need without the complexity.

---

## Honorable mentions (not asked for, worth noting)

- **Re-ingestion:** If you change field mappings, you can't re-parse an old file without going through the upload flow again. A "re-parse" button on the DataSource detail would be useful.
- **Multi-factor electricity (time-of-use):** Some grid operators publish hourly carbon intensity. For organizations with smart meters, hourly matching gives more accurate Scope 2. Not built — requires interval data ingestion which we explicitly excluded.
- **Spend-based Scope 3 (Category 1):** Procurement data from SAP could be used with EEIO (Environmentally Extended Input-Output) factors for supply chain emissions. We ingest SAP procurement movement types but don't apply EEIO factors — that requires a NAICS/ISIC industry code mapping and a different factor table.
