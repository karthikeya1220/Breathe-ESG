# TRADEOFFS — What Was Deliberately Not Built

Three things I chose not to build, and why.

---

## 1. Real-Time API Pull from Source Systems

**What it would mean:** Instead of file uploads, the platform would authenticate directly with SAP's OData service, each utility's portal API, and Concur's REST API. A scheduler (Celery beat) would pull data on a configurable cadence without any human uploading a file.

**Why I didn't build it:**

- **Enterprise API access is a 3–12 week procurement and IT security process.** SAP RFC/OData requires network allowlisting, a service account, and often a change request ticket. Utility APIs vary by provider and region — many large US utilities don't expose APIs at all. Concur's App Center registration requires SAP's approval. None of this is codebase work; it's client onboarding work.

- **The file upload model is honest about prototype scope.** If I built an API pull layer, it would either be fake (mocked responses that don't reflect real-world auth flows) or incomplete in ways that would mislead evaluation. A file upload interface is immediately demonstrable with real sample data.

- **The data model is API-pull-ready.** `DataSource.config` (JSONB) can store API credentials, `IngestionJob` already models "triggered by system vs triggered by user," and `RawRecord` is format-agnostic. Adding API pull is a new ingestion adapter, not a schema change.

**What I'd tell the PM:** File upload for v1, scheduled API pull for v2 once we've completed one full client onboarding and understood the credential management pattern.

---

## 2. PDF Bill Parsing for Utility Data

**What it would mean:** Instead of (or in addition to) CSV export, analysts could upload a utility bill PDF. The system would extract meter readings, billing periods, and consumption values automatically using OCR or a document AI model.

**Why I didn't build it:**

- **It's the hardest part of the problem with the highest failure rate.** Every utility formats their bills differently. OCR on PDFs with tables, multi-column layouts, and embedded graphics is genuinely difficult — even with Claude or GPT-4V, you need per-utility prompt engineering and a validation pass. A number extracted incorrectly from a bill looks plausible and will pass into the audit without triggering any error.

- **Silent failures are worse than loud ones.** A CSV parse error surfaces immediately. A PDF extraction error produces a wrong number with no indication it's wrong. For an audit-ready product, I'd rather force CSV (explicit, validatable) than accept PDF (convenient but unreliable) and give analysts false confidence.

- **The CSV path is already what most facilities teams use.** Portal CSV exports are available from every major utility I researched (see SOURCES.md). The PDF path is a convenience for clients whose facilities teams don't use portal exports — a real need, but a v2 problem.

**What I'd tell the PM:** PDF support is on the roadmap, but only with a mandatory human-in-the-loop review step where the extracted values are shown side-by-side with the original PDF page before ingestion. No silent auto-ingest of PDF-extracted numbers.

---

## 3. Automated Anomaly Detection / Suspicious Value Flagging

**What it would mean:** The system would automatically flag emission records that look statistically unusual — a meter showing 10x its normal consumption, a flight logged as 50,000 km, a fuel quantity in a unit that doesn't match the material. This would populate the "looks suspicious" column in the analyst dashboard without any manual review.

**Why I didn't build it:**

- **It requires historical baselines to be meaningful.** Statistical anomaly detection (z-score, IQR-based outlier detection, time-series comparison) only works once you have enough historical data per source to establish what "normal" looks like. A new client has no baseline. Flagging everything as suspicious on first ingestion destroys analyst trust in the system.

- **Rules-based heuristics without domain knowledge produce noise.** I could hard-code "flag if quantity > 10,000 litres per day" but that threshold is wrong for a shipping company and correct for a retail store. Getting this right requires client-specific calibration, which is a configuration and onboarding problem, not a code problem.

- **The analyst dashboard already surfaces the right signals.** Parse errors, unit mismatches, missing emission factors, and records with unusually high CO₂e contributions are all visible in the review queue through existing fields (parse_status, emission_factor FK being null, co2e_kg outliers via simple sort). Analysts can sort by CO₂e descending and spot outliers manually. That's good enough for v1.

**What I'd tell the PM:** Automated flagging is high-value but needs 2–3 months of ingested data per client before it becomes useful rather than noisy. Add it in v3, after we've shipped enough clients to have labeled examples of "this was flagged, this was fine."
