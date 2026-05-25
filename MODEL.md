# DATA MODEL — Breathe ESG Ingestion Platform

## Design Goals

1. **Multi-tenancy** — every row is scoped to an organization; no data bleeds between clients
2. **Source-of-truth tracking** — every EmissionRecord traces back to the exact raw row, ingestion job, and source config that produced it
3. **Scope 1/2/3 categorization** — enforced at the model level, not inferred at query time
4. **Unit normalization** — raw units preserved, normalized value stored separately; conversion is auditable
5. **Audit trail** — analyst actions are immutable events, never destructive updates

---

## Entity Overview

```
Organization
    └── DataSource (SAP config, utility account, travel platform)
            └── IngestionJob (one upload/pull run)
                    └── RawRecord (raw row, never mutated)
                            └── EmissionRecord (normalized, enriched)
                                    └── AnalystReview (approve/flag/reject)

AuditEvent (append-only log, FK to any of the above)
EmissionFactor (lookup table, versioned)
UnitConversion (lookup table)
```

---

## Tables

### `Organization`

The tenant root. Every other table has a direct or indirect FK here.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | varchar(255) | Client company name |
| slug | varchar(100) | URL-safe identifier |
| fiscal_year_start | smallint | Month (1–12); affects period bucketing |
| created_at | timestamptz | |
| is_active | boolean | Soft-delete for offboarding |

**Why UUID PKs everywhere:** integer PKs leak row counts to tenants and make cross-environment data migration messier.

---

### `DataSource`

One row per configured ingestion channel per org. A client with two SAP plants and one utility account has three rows here.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| org | FK → Organization | |
| source_type | enum | `SAP_FLAT_FILE`, `UTILITY_CSV`, `TRAVEL_CSV` |
| scope | enum | `SCOPE_1`, `SCOPE_2`, `SCOPE_3` |
| display_name | varchar(255) | Human label, e.g. "Hamburg Plant Fuel" |
| config | jsonb | Source-specific config (plant codes, meter IDs, column mappings) |
| created_at | timestamptz | |
| created_by | FK → User | |

**Why `config` is JSONB:** each source type has a completely different configuration shape. Normalizing these into typed columns would require a table per source type and a union query to read them. JSONB lets us store SAP plant code mappings, utility account numbers, and Concur export profile IDs in one place, validated by source-specific serializers in the application layer.

---

### `IngestionJob`

One row per upload event or scheduled pull. This is the "when did this batch arrive" record.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| data_source | FK → DataSource | |
| org | FK → Organization | Denormalized for query performance |
| triggered_by | FK → User | Who uploaded or which scheduled job |
| status | enum | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| raw_file_path | varchar(512) | S3/storage path to original file, immutable |
| file_hash | varchar(64) | SHA-256 of original file; detects re-uploads |
| row_count_raw | integer | Total rows parsed |
| row_count_ok | integer | Rows that produced valid EmissionRecords |
| row_count_failed | integer | Rows that errored |
| error_summary | jsonb | Aggregated parse errors |
| started_at | timestamptz | |
| completed_at | timestamptz | |

**Why store the file hash:** a facilities team re-uploading the same CSV twice is a common accident. We reject exact duplicates at the job level rather than letting them produce duplicate EmissionRecords.

---

### `RawRecord`

One row per parsed row from the source file. Never mutated after creation. This is the ground truth of what arrived.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| ingestion_job | FK → IngestionJob | |
| org | FK → Organization | Denormalized |
| row_number | integer | Line number in source file |
| raw_data | jsonb | Exact key-value dict of the parsed row |
| parse_status | enum | `OK`, `PARSE_ERROR`, `VALIDATION_ERROR`, `SKIPPED` |
| parse_errors | jsonb | Array of error objects with field + message |
| created_at | timestamptz | |

**Why keep raw rows:** when an analyst flags a suspicious value, the reviewer needs to see exactly what came in before any transformation. Storing only the normalized output makes debugging nearly impossible.

---

### `EmissionRecord`

The normalized, scope-tagged, unit-converted record. One row per valid RawRecord.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| org | FK → Organization | |
| raw_record | FK → RawRecord | One-to-one; nullable if manually entered |
| data_source | FK → DataSource | |
| scope | enum | `SCOPE_1`, `SCOPE_2`, `SCOPE_3` |
| category | varchar(100) | GHG Protocol category, e.g. "Stationary combustion", "Purchased electricity", "Business travel - air" |
| activity_description | varchar(255) | Human-readable, e.g. "Diesel - Hamburg Plant" |
| period_start | date | Normalized billing/activity period start |
| period_end | date | Normalized billing/activity period end |
| raw_quantity | numeric(18,6) | Quantity as it appeared in source |
| raw_unit | varchar(50) | Unit as it appeared in source (e.g. "L", "GAL", "kWh", "MWh") |
| quantity_normalized | numeric(18,6) | Converted to canonical unit |
| unit_normalized | varchar(20) | Canonical unit (kWh for energy, km for distance, litre for fuel) |
| co2e_kg | numeric(18,6) | Computed kg CO₂e; null until emission factor applied |
| emission_factor | FK → EmissionFactor | Which factor was used |
| emission_factor_override | jsonb | If analyst manually overrode the factor |
| review_status | enum | `PENDING`, `APPROVED`, `FLAGGED`, `REJECTED` |
| is_locked | boolean | True after analyst approval; blocks further edits |
| locked_at | timestamptz | |
| locked_by | FK → User | |
| is_manually_edited | boolean | True if analyst changed any field post-ingestion |
| edit_history | jsonb | Array of {field, old_value, new_value, user, timestamp} |
| created_at | timestamptz | |

**Why denormalize `scope` here even though it's on DataSource:** a single SAP file can contain both Scope 1 fuel rows and Scope 3 procurement rows. The source-level scope is a default; the record-level scope is the truth.

**Why store `co2e_kg` as a materialized column, not computed on read:** analysts and auditors query this constantly. Computing it on the fly across millions of rows with factor lookups is a performance trap.

---

### `EmissionFactor`

Lookup table for GHG conversion factors. Versioned so historical records aren't retroactively changed.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| source | varchar(100) | "DEFRA 2024", "EPA eGRID 2023", "ICAO 2023" |
| category | varchar(100) | Matches EmissionRecord.category |
| fuel_type / activity | varchar(100) | e.g. "diesel", "natural_gas", "short_haul_economy" |
| region | varchar(50) | Country or grid region where applicable |
| factor_kg_co2e | numeric(12,8) | kg CO₂e per unit |
| unit | varchar(20) | Per what unit (per litre, per kWh, per km) |
| valid_from | date | |
| valid_to | date | Null = currently active |

---

### `UnitConversion`

| Column | Type | Notes |
|--------|------|-------|
| id | serial | PK |
| from_unit | varchar(50) | |
| to_unit | varchar(50) | |
| factor | numeric(18,10) | Multiply from_unit by factor to get to_unit |

Seed data covers: L↔GAL, kWh↔MWh, mi↔km, imperial gallons vs US gallons, BTU↔kWh.

---

### `AnalystReview`

An explicit event when an analyst takes action. Separate from the `review_status` field on EmissionRecord — that's the current state; this table is the history.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| emission_record | FK → EmissionRecord | |
| org | FK → Organization | |
| reviewer | FK → User | |
| action | enum | `APPROVED`, `FLAGGED`, `REJECTED`, `EDITED`, `NOTE_ADDED` |
| comment | text | Required for FLAGGED and REJECTED |
| created_at | timestamptz | Immutable |

---

### `AuditEvent`

Append-only log. Nothing is ever deleted from this table.

| Column | Type | Notes |
|--------|------|-------|
| id | bigserial | PK |
| org | FK → Organization | |
| actor | FK → User | Null for system events |
| event_type | varchar(100) | e.g. `JOB_STARTED`, `RECORD_APPROVED`, `FACTOR_OVERRIDDEN` |
| object_type | varchar(50) | `IngestionJob`, `EmissionRecord`, etc. |
| object_id | UUID | |
| payload | jsonb | Full before/after state for mutations |
| created_at | timestamptz | DB default, application cannot override |

---

## Multi-Tenancy Strategy

**Row-level isolation with org_id FK on every table.**

Chosen over schema-per-tenant because:
- Prototype scale doesn't justify the migration complexity of schema-per-tenant
- Django ORM's `select_related` and `prefetch_related` don't work cleanly across schemas
- All queries go through a `get_queryset()` override on every ViewSet that applies `.filter(org=request.user.org)` — one enforcement point

The risk: a bug in that filter leaks data. Mitigated by a middleware assertion that every queryset on multi-tenant models carries an org filter (testable at the ORM level).

---

## Scope Categorization Logic

| Source | Default Scope | Notes |
|--------|--------------|-------|
| SAP — fuel (diesel, petrol, natural gas) | Scope 1 | Stationary or mobile combustion |
| SAP — purchased goods/services | Scope 3, Cat 1 | Only if procurement data included |
| Utility — electricity | Scope 2 | Market-based or location-based, flagged for analyst choice |
| Travel — flights | Scope 3, Cat 6 | Business travel |
| Travel — hotels | Scope 3, Cat 6 | |
| Travel — ground (rental car, taxi) | Scope 3, Cat 6 | Unless company-owned vehicle = Scope 1 |

---

## Audit Trail Flow

```
Analyst approves record
    → EmissionRecord.review_status = APPROVED
    → EmissionRecord.is_locked = True
    → AnalystReview row created (action=APPROVED)
    → AuditEvent row created (event_type=RECORD_APPROVED, payload={record_id, reviewer_id, timestamp})
```

Locking is enforced at the serializer level: a locked record raises a `PermissionDenied` on any field mutation. Only a superuser can unlock (and that action is itself audited).
