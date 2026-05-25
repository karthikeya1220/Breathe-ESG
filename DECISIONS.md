# DECISIONS — Breathe ESG Ingestion Platform

Every ambiguity resolved, what was chosen, and why.

---

## SAP: Which Export Format?

**Ambiguity:** SAP exposes data in many ways — IDocs over RFC, OData services, BAPI calls, flat file exports from transaction SE16/ME2M/MB51, and custom extracts via ABAP reports.

**Decision:** Flat file CSV/TXT export from SAP transaction MB51 (Material Document List) for fuel/inventory movements, and ME2M (Purchase Orders by Material) for procurement.

**Why:**
- IDocs require a middleware layer (SAP PI/PO or CIG) and RFC connectivity — a client's IT team controls this and onboarding takes weeks. Not realistic for a prototype.
- OData requires the ICF service to be activated and exposed, which many enterprise SAP environments have locked down.
- Flat file exports are what a sustainability analyst actually gets: they ask the SAP team for a data dump, and they get a `.txt` or `.csv` with a specific delimiter.
- This is the format I can realistically receive over email or file upload without VPN/RFC access.

**What I'd ask the PM:**
- Does the client have a dedicated SAP team willing to set up a recurring export job, or is this a one-time sustainability analyst request?
- Are plant codes consistent across their system, or do they vary by business unit / company code?
- What transaction/report does their SAP team use for fuel consumption data? MB51 covers goods movements; there may be a custom Z-report.

**What I ignored:**
- IDoc parsing (EDIFACT-like structure, requires segment definition knowledge)
- German column headers (SAP installs default to the login language; I assumed English or provided a column mapping config)
- Multi-currency procurement data (set aside; assumed single currency per org for prototype)
- Vendor master data linkage (Scope 3 Cat 1 requires supplier-level data; out of scope)

---

## SAP: Which Data Subset?

**Decision:** Fuel-relevant goods movements only — diesel (material type ROH or HIBE), petrol, natural gas, LPG. Identified by material group or material number prefix configured per DataSource.

**Why:** An MB51 export contains every inventory movement in the plant. Pulling all of it and trying to classify materials as emissions-relevant is an NLP problem. For the prototype, the config layer (DataSource.config JSONB) holds a list of material numbers or material groups that are emissions-relevant. The client's sustainability lead maintains this list.

**What I'd ask the PM:** Do they already have a list of emissions-relevant materials, or do we need to derive it from their material master?

---

## Utility: Which Ingestion Mode?

**Ambiguity:** Utility data can arrive as a portal CSV export, a PDF bill, a Green Button XML feed, or an API (some large utilities expose one).

**Decision:** Portal CSV export.

**Why:**
- PDF parsing is fragile — every utility formats their bill differently, table structures vary, and the failure modes are silent (wrong number extracted, looks plausible). Bad for an audit-ready product.
- Green Button XML is great but only adopted by a subset of US utilities and requires OAuth with each utility's portal separately.
- Most facilities teams already export CSVs from their utility portal (e.g., PG&E, National Grid, EDF all have data export functions). This is the path of least resistance.
- CSV gives us structured data we can validate on ingest.

**What I'd ask the PM:** Which utilities does this client use? Some large enterprise clients have dozens of meters across multiple utilities — do we need multi-utility support in v1?

**What I ignored:**
- PDF bill parsing
- Green Button XML (ESPI standard)
- Automated portal scraping
- Interval data (15-minute smart meter reads) — I normalize to monthly billing periods

---

## Utility: Billing Period Alignment

**Ambiguity:** Utility billing periods rarely align with calendar months (a "March bill" might cover Feb 15 – Mar 18). Carbon reporting is usually done by calendar quarter or fiscal year.

**Decision:** Store `period_start` and `period_end` as explicit dates on EmissionRecord. The analytics layer pro-rates consumption across calendar months using day-weighted apportionment.

**Why:** Forcing the ingestion layer to snap periods to calendar months loses information. The right place to handle this is in reporting queries, not at ingest time.

---

## Travel: Which Platform and Format?

**Ambiguity:** Concur, Navan (formerly TripActions), Egencia, AmEx GBT, and others. API or export?

**Decision:** CSV export from Concur Expense/Travel (the standard "Expense Report Extract" or "Travel Itinerary Report").

**Why:**
- Concur's REST API requires OAuth and a registered app in the SAP Concur App Center. Enterprise clients' IT teams often lock this down.
- Most corporate travel managers already pull monthly reports as CSVs for internal accounting.
- Concur's export format is well-documented and consistent enough to build a reliable parser.
- Navan has a cleaner API but lower enterprise market share for established clients.

**What I'd ask the PM:** Does the client use Concur or something else? If they use Navan, the column names differ slightly but the logic is the same.

---

## Travel: Distance for Flights

**Ambiguity:** Concur exports often give you origin and destination airport codes (e.g., LHR → JFK) but not the distance. Some rows include distance if the booking platform calculated it.

**Decision:** When distance is missing, calculate it from IATA airport codes using a static airport coordinate lookup (OpenFlights dataset, ~7,000 airports). Great-circle distance via haversine formula. Apply a radiative forcing multiplier of 2x for flights (per DEFRA guidance) to account for non-CO₂ effects at altitude.

**Why:** The alternative — calling a live API per row — introduces latency, a rate limit, and an external dependency in the ingestion pipeline. The haversine approximation is standard in carbon accounting for Scope 3 Cat 6.

**What I'd ask the PM:** Does the client want market-based or distance-based emission factors for flights? ICAO and DEFRA have different methodologies; this matters for audit.

---

## Emission Factors

**Decision:** Use UK DEFRA Conversion Factors (2024 edition) as the primary source. Supplement with EPA eGRID 2023 for US electricity grid emission factors.

**Why:**
- DEFRA publishes a single comprehensive spreadsheet covering fuel combustion, electricity, freight, and travel. It's free, auditor-recognized, and updated annually.
- EPA eGRID is the standard for US electricity Scope 2.
- Both are versioned, which is critical: `EmissionFactor.valid_from` / `valid_to` lets us recalculate historical records if a factor is revised.

**What I ignored:** GHG Protocol's own factor database (requires licensing), Ecoinvent (expensive), and supplier-specific factors (requires Scope 3 Cat 1 supplier engagement — out of scope).

---

## Multi-Tenancy: Row-Level vs Schema-Per-Tenant

**Decision:** Row-level isolation with `org` FK on every table, enforced via queryset override in Django ViewSets.

**Why:** Schema-per-tenant is the right long-term architecture for a SaaS platform at scale, but it adds significant complexity: separate migration management per tenant, connection pooling complications with PgBouncer, and Django ORM limitations with `using()`. At prototype scale with a handful of test organizations, row-level is defensible. See MODEL.md for details.

---

## Authentication

**Decision:** Django's built-in User model + DRF Token Authentication. Each user has an `org` FK that scopes their data access.

**Why:** JWT would be better for a production multi-service system, but adds library choices and refresh token complexity that distracts from the core data modeling problem. Token auth is auditable (tokens are revocable) and sufficient for a prototype.

---

## Review Workflow: Who Can Approve?

**Decision:** Any user with `role=ANALYST` or `role=ADMIN` in the org can approve records. Approval locks the record. There is no multi-step approval in v1.

**Why:** The assignment asks for analyst sign-off before audit. A two-step approval (analyst + manager) is realistic but out of scope. I record who approved and when, so upgrading to multi-step later only requires adding a second required AnalystReview action before is_locked flips.

---

## Deployment

**Decision:** Railway for deployment. PostgreSQL via Railway's managed Postgres add-on. Static files and uploaded CSVs via Railway's volume or S3-compatible storage.

**Why:** Railway supports Django out of the box with minimal config, auto-deploys from GitHub, and the free/hobby tier is sufficient for a prototype. Render is comparable; Railway's DX is slightly faster for Python.

---

## What I Would Ask the PM (Full List)

1. Do clients need to see each other's data? (Confirms multi-tenancy is genuinely required)
2. Is there a fiscal year offset, or do all clients report Jan–Dec?
3. For Scope 2 electricity: market-based or location-based method? (Different factors, affects methodology disclosure)
4. Does the client want to track and subtract renewable energy certificates (RECs)?
5. What does "locked for audit" mean operationally — does the auditor log in to our platform, or do we export a signed PDF?
6. Are there any existing emission factors the client has agreed with their auditor that we must use?
7. What's the volume? Rows per ingestion, number of meters, number of employees traveling? (Affects indexing strategy)
