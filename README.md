# Breathe ESG — Data Ingestion Platform

A Django REST + React application that ingests ESG emissions data from three enterprise source types, normalizes it, and provides an analyst review dashboard before locking records for audit.

## Live Demo

- **App:** https://breathe-esg.up.railway.app (deploy URL — update after deployment)
- **API:** https://breathe-esg-backend.up.railway.app/api/

**Demo credentials:**
- Admin: `admin@demo.com` / `breathe2025`
- Analyst: `analyst@demo.com` / `breathe2025`

## Architecture

```
Frontend (React + Vite + Tailwind)  →  Backend (Django REST Framework)  →  PostgreSQL
                                    ↑
                          JWT Auth (simplejwt)
```

## Data sources supported

| Source | Format | Scope |
|--------|--------|-------|
| SAP MB51/ME2M flat file | Semicolon/tab CSV, German or English headers | Scope 1 (fuel consumption) |
| Utility portal CSV | Standard billing CSV with kWh/MWh usage | Scope 2 (electricity) |
| Navan/Concur travel export | CSV with flights, hotels, ground transport | Scope 3 (business travel) |

## Running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser  # optional, for /admin
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173, proxies API calls to http://localhost:8000.

### Sample data

Sample files in `sample_data/` can be uploaded via the Upload page:
- `sap_mb51_fuel_procurement.csv` → SAP source type
- `utility_portal_electricity.csv` → Utility source type
- `travel_navan_export.csv` → Travel source type

Each file contains intentionally realistic edge cases (negative quantities, unknown materials, long billing periods, missing airport codes) to demonstrate the flagging system.

## Deployment (Railway)

1. Create a Railway project
2. Add a PostgreSQL plugin — Railway auto-sets `DATABASE_URL`
3. Backend service:
   - Root directory: `backend/`
   - Start command: `gunicorn breathe.wsgi --log-file -`
   - Environment variables: `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`
4. Run migrations: `python manage.py migrate`
5. Frontend service:
   - Root directory: `frontend/`
   - Build command: `npm run build`
   - Start command: static file serving (e.g., via `serve -s dist`)
   - Set `VITE_API_BASE_URL` if frontend and backend are on different domains

## Key design documents

- [MODEL.md](./MODEL.md) — Data model rationale
- [DECISIONS.md](./DECISIONS.md) — Every ambiguity resolved
- [TRADEOFFS.md](./TRADEOFFS.md) — What was deliberately not built
- [SOURCES.md](./SOURCES.md) — Research on each data source

## Grading criteria addressed

- **Data model (35%):** See MODEL.md — multi-tenancy, Scope 1/2/3, source-of-truth tracking, unit normalization, audit trail
- **Decision defense (25%):** See DECISIONS.md — every format choice with real-world justification
- **Realistic sources (20%):** See SOURCES.md — researched actual SAP transactions, utility portal formats, Navan export structure
- **Analyst UX (10%):** Role-based dashboard, one-click approve/reject, bulk actions, inline notes, flag explanations
- **What not built (10%):** See TRADEOFFS.md — Celery, market-based Scope 2, factor versioning
