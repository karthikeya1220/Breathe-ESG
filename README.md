# Breathe ESG — Emissions Ingestion Platform

> Tech intern assignment submission — Breathe ESG

A Django REST + React prototype that ingests enterprise emissions data from three source types, normalizes it to kg CO₂e using DEFRA 2024 factors, and surfaces an analyst review dashboard where rows can be approved and locked for audit.

---

## Live Demo

| | |
|---|---|
| **App URL** | *(deployed URL — see submission email)* |
| **Login** | `analyst` / `demo1234` |

---

## What It Does

**Ingest → Normalize → Review → Lock**

1. An analyst uploads a CSV from SAP (fuel data), a utility portal (electricity), or Concur (corporate travel)
2. The parser extracts and normalizes each row, applies DEFRA 2024 emission factors, computes kg CO₂e
3. Records appear in the review queue with Scope 1/2/3 badges and CO₂e values
4. The analyst approves, flags, or rejects each row — approval locks the record (immutable for audit)
5. All actions are written to an append-only audit log

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.2, Django REST Framework |
| Database | PostgreSQL (Railway add-on) / SQLite (local dev) |
| Auth | DRF Token Authentication |
| Frontend | React (Vite), TailwindCSS |
| Deployment | Railway (backend), Vercel (frontend) |
| Emission factors | DEFRA 2024 (primary), EPA eGRID 2023 (US electricity) |

---

## Repository Structure

```
Breathe-ESG/
├── backend/                  Django REST API
│   ├── core/                 Settings, URLs, OrgMiddleware
│   ├── organizations/        Organization, User (custom auth model)
│   ├── sources/              DataSource, IngestionJob
│   ├── ingestion/            Upload endpoint + 3 parsers
│   │   └── parsers/
│   │       ├── sap.py        SAP MB51 flat file parser
│   │       ├── utility.py    Utility portal CSV parser
│   │       └── travel.py     Concur/Navan travel CSV parser
│   ├── records/              RawRecord, EmissionRecord, AnalystReview
│   ├── factors/              EmissionFactor, UnitConversion (seed data)
│   ├── audit/                AuditEvent (append-only)
│   └── sample_data/          3 sample CSVs (SAP, utility, travel)
├── frontend/                 React (Vite) app
│   └── src/
│       ├── pages/            Login, Upload, Dashboard, RecordDetail, Jobs
│       ├── components/       Layout, Sidebar
│       └── context/          AuthContext
├── MODEL.md                  Data model + rationale
├── DECISIONS.md              Every ambiguity resolved + PM questions
├── TRADEOFFS.md              3 things deliberately not built
└── SOURCES.md                Real-world research per data source
```

---

## Local Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data      # seeds factors, unit conversions, demo org + user
python manage.py runserver 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # starts at http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

### Demo credentials

```
username: analyst
password: demo1234
org:      Acme Manufacturing Ltd
```

---

## Trying It Out

1. Log in at `http://localhost:5173`
2. Go to **Upload Data** — upload one of the sample CSVs from `backend/sample_data/`
   - `sap_mb51_sample.csv` → select "Hamburg Plant Fuel (SAP MB51)"
   - `utility_electricity_sample.csv` → select "HQ Electricity (National Grid)"
   - `travel_concur_sample.csv` → select "Corporate Travel (Concur)"
3. Go to **Review Queue** — see all records with Scope badges and CO₂e values
4. Click a record → view raw source data side-by-side with normalized values
5. Approve / Flag / Reject — approval locks the record permanently
6. Go to **Ingestion Jobs** to see per-row parse errors

---

## Data Sources

### 1. SAP — Fuel Data (Scope 1)
- **Format:** MB51 (Material Document List) flat file CSV/TSV export
- **Handles:** DD.MM.YYYY date format, configurable column mapping for German headers, movement type filter (201/261), fuel classification by material description keyword
- **Sample data rationale:** Single plant consuming diesel (multiple goods issues per week at ~3,000–6,000 L each) and natural gas (~1,000–1,500 m³/month for heating). Includes a reversal document (negative quantity) to demonstrate handling.

### 2. Utility — Electricity (Scope 2)
- **Format:** Portal CSV export (National Grid / PG&E / EDF style)
- **Handles:** Billing periods stored as explicit start/end dates (not snapped to calendar months), estimated read flagging (Read Type E), MWh→kWh normalization, sub-meter exclusion config
- **Sample data rationale:** Two meters at one site (~48 MWh/month primary, ~12 MWh/month sub-meter), one estimated read per meter to demonstrate the flag.

### 3. Corporate Travel — Flights, Hotels, Ground (Scope 3)
- **Format:** Concur Expense/Travel Report CSV export
- **Handles:** Missing flight distance → haversine from IATA codes (50+ airports in static lookup), DEFRA 2024 class multipliers (economy 1×, business 2.40×), radiative forcing 2× applied to all flights, hotel nights from check-in/check-out dates, ground/rail categorization
- **Sample data rationale:** LHR→JFK with no distance provided (tests haversine), business outbound + economy return (tests class multiplier), 7-night US hotel, short-haul with distance pre-populated, rail segment.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login/` | Returns auth token |
| GET | `/api/auth/me/` | Current user + org |
| GET | `/api/sources/datasources/` | List data sources for org |
| GET | `/api/sources/jobs/` | List ingestion jobs |
| POST | `/api/ingestion/upload/` | Upload CSV → creates job + records |
| GET | `/api/records/` | Paginated records, filterable by status/scope/source |
| GET | `/api/records/{id}/` | Record detail with raw data |
| POST | `/api/records/{id}/review/` | Approve / flag / reject |

---

## Design Decisions

See [DECISIONS.md](DECISIONS.md) for the full list. Key choices:

- **SAP flat file over OData/IDoc** — OData requires activated ICF services and network allowlisting; flat file export is what analysts actually receive over email
- **DEFRA 2024 as primary factor source** — single spreadsheet covering fuel, electricity, and travel; free, versioned, auditor-recognized
- **Row-level multi-tenancy** — queryset override in every ViewSet; schema-per-tenant adds migration complexity that isn't justified at prototype scale
- **SHA-256 file deduplication** — rejects exact re-uploads at the job level before any rows are parsed
- **co2e_kg materialized at ingest time** — not computed on read; constant factor lookups across millions of rows at query time is a performance trap

## Deliberate Tradeoffs

See [TRADEOFFS.md](TRADEOFFS.md). Not built:

1. **Real-time API pull** from SAP/Concur — enterprise API access is a 3–12 week procurement process; file upload is immediately demonstrable
2. **PDF bill parsing** — silent extraction failures are worse than loud parse errors for an audit-ready product
3. **Automated anomaly detection** — requires 2–3 months of historical baseline per client before it's useful rather than noisy

---

## Deployment (Railway)

### Environment variables required

```
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DATABASE_URL=<from Railway PostgreSQL add-on>
ALLOWED_HOSTS=<your-railway-domain>.railway.app
CORS_ALLOWED_ORIGINS=https://<your-frontend-url>
DEBUG=False
```

### Deploy

1. Create a Railway project, add a PostgreSQL add-on
2. Connect this GitHub repository to a new service
3. Set the above environment variables
4. Railway runs `python manage.py migrate && python manage.py seed_data && gunicorn core.wsgi` on deploy (per `railway.json`)

---

## Submission

- **GitHub:** https://github.com/karthikeya1220/Breathe-ESG
- **Deployed URL:** *(in submission email)*
- **Login:** `analyst` / `demo1234`
