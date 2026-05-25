# SOURCES — Real-World Data Source Research

For each of the three sources: what format was researched, what was learned, what the sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP — Fuel and Procurement Data

### Real-World Format Researched

SAP transaction **MB51 (Material Document List)** flat file export.

MB51 produces a goods movement history: every material receipt, issue, and transfer in a plant's inventory. For a sustainability use case, the relevant movements are:
- **Movement type 201** — goods issue to cost center (fuel consumed from storage tank)
- **Movement type 261** — goods issue to production order (fuel consumed in manufacturing)
- **Movement type 101** — goods receipt (fuel delivered to site)

The export is triggered via SAP GUI → MB51 → List → Export to Local File (spreadsheet/tab-delimited). In some client environments, this is automated as a background job (SM36) that drops a `.txt` to a file share on a schedule.

### What I Learned

- **Column headers depend on SAP's installed language.** A German SAP installation produces `Buchungsdatum` instead of `Posting Date`, `Werk` instead of `Plant`, `Materialnummer` instead of `Material`. The DataSource config layer stores a column name mapping for this reason.
- **Plant codes are opaque without a master data lookup.** "0010" might be Hamburg, "0020" might be Rotterdam. The sustainability lead needs to provide a plant-to-location mapping for carbon accounting to work.
- **Units are inconsistent even within one export.** Diesel may be in litres (L), kilograms (KG), or US gallons (GAL) depending on how the material master was configured. Natural gas may be in cubic metres (M3), MMBtu, or therms.
- **Material numbers are not self-describing.** Material "ROH-DIESEL-001" is obvious; "100045782" is not. The DataSource config stores an emissions-relevant material list maintained by the sustainability analyst.
- **Dates come in DD.MM.YYYY format** from European SAP installs, not ISO 8601.

### Sample Data Structure

```
Posting Date | Material | Material Description | Plant | Movement Type | Quantity | Unit | Batch | Cost Center
12.01.2024   | 100045782 | Diesel EN590        | 0010  | 201           | 5000.000 | L    |       | CC-OPS-001
15.01.2024   | 100045782 | Diesel EN590        | 0010  | 201           | 3200.000 | L    |       | CC-OPS-001
18.01.2024   | 100087431 | Natural Gas         | 0020  | 201           | 1250.000 | M3   |       | CC-HEAT-002
22.01.2024   | 100045782 | Diesel EN590        | 0010  | 201           | 4800.000 | L    |       | CC-OPS-001
```

**Why this sample looks this way:**
- A single plant consuming diesel for vehicle fleet and generators would see multiple goods issues per week (~3–5 movements for a mid-size operation)
- Quantities are in whole or one-decimal litres, matching how tank dip readings are typically recorded
- Cost centers vary (operations vs. heating vs. production) — relevant for internal attribution but not for Scope 1 total
- Natural gas in M3 is realistic for European sites; US sites would use CCF or therms

### What Would Break in a Real Deployment

1. **Material master gaps.** A new material gets added to the system mid-year; it's not in the emissions-relevant list. Its consumption is silently excluded. Fix: a "catch-all unknown materials" flag and an alert when an unrecognized material appears in the export.

2. **Movement type coverage.** MB51 with movement type 201 catches direct consumption from cost center. If the client uses movement type 261 (production order) or 551 (scrapping), those rows are missed. Fix: configurable movement type filter per DataSource.

3. **Reversal documents.** SAP records reversals as a separate document with negative quantity on the same movement type. A naïve sum overestimates consumption unless reversal documents (identified by `Reference Document` field being non-empty) are netted out.

4. **Split valuation.** Some plants track the same material in different quality grades with separate stock segments. MB51 can return duplicate-looking rows that are actually different batches. Fix: sum by material + plant + period, not by document.

5. **Company code vs. plant.** A client with multiple legal entities in SAP has multiple company codes, each with multiple plants. An export scoped to one company code misses affiliated entities. The sustainability analyst may not know to request a cross-company-code export.

---

## Source 2: Utility Data — Electricity

### Real-World Format Researched

Portal CSV export from utility account management portals. Researched formats from:
- **PG&E (US):** "Green Button Download" CSV and "Usage Export" from MyEnergy portal
- **National Grid (UK):** Smart meter data export from account portal
- **EDF Energy (UK):** Account usage history CSV

### What I Learned

- **Billing periods don't align with calendar months.** A bill covering Feb 15 – Mar 18 is common. Some utilities bill every 28 days. Some switch between estimated and actual reads, creating periods of different lengths.
- **Multiple meters per account.** A large facility has sub-meters (lighting circuit, HVAC, production equipment). A CSV export often contains all meters with a `Meter ID` column. Carbon reporting typically wants total site consumption, which means summing across meters — but some meters may be double-counted if they're sub-meters of a parent meter.
- **Units vary.** kWh is standard but some industrial accounts report in MWh. Demand charges are in kW (power, not energy) — relevant for the bill but not for carbon accounting.
- **Estimated reads are flagged.** Most utility CSVs include a `Read Type` column: `A` (actual), `E` (estimated), `C` (customer-supplied). Estimated reads should be flagged for analyst review since they may be revised in the next bill.
- **The electricity emission factor depends on the reporting method.** Scope 2 has two accepted methods: location-based (grid average factor, e.g. UK national grid average) and market-based (supplier-specific factor, or residual mix if no contract). The ingestion layer needs to store which method was used.

### Sample Data Structure

```
Account Number | Meter ID    | Service Address           | Read Date  | Period Start | Period End | Usage (kWh) | Demand (kW) | Read Type | Tariff
ACC-00192837   | MTR-4820193 | Unit 12, Industrial Est.  | 2024-02-14 | 2024-01-15   | 2024-02-14 | 48320.00    | 210.5       | A         | HH-INDUSTRIAL
ACC-00192837   | MTR-4820193 | Unit 12, Industrial Est.  | 2024-03-15 | 2024-02-15   | 2024-03-15 | 51240.00    | 218.3       | A         | HH-INDUSTRIAL
ACC-00192837   | MTR-4820193 | Unit 12, Industrial Est.  | 2024-04-17 | 2024-03-16   | 2024-04-17 | 49810.00    | 207.9       | E         | HH-INDUSTRIAL
ACC-00192837   | MTR-5930284 | Unit 12, Industrial Est.  | 2024-02-14 | 2024-01-15   | 2024-02-14 | 12450.00    | 58.2        | A         | HH-INDUSTRIAL
```

**Why this sample looks this way:**
- Consumption of ~48–51 MWh/month is realistic for a medium industrial unit (~600–700 kW average load)
- One estimated read (April, Read Type E) — common when a meter reader couldn't access the site
- Two meters at the same address — this is a sub-meter scenario; the analyst needs to confirm whether MTR-5930284 is a sub-meter of MTR-4820193 (in which case summing both double-counts)
- Half-hourly (HH) tariff indicates a large commercial/industrial customer with smart metering

### What Would Break in a Real Deployment

1. **Sub-meter double-counting.** Without a meter hierarchy mapping, summing all meters at a site overestimates consumption. Fix: DataSource config stores a `parent_meter` mapping; sub-meters are excluded from Scope 2 total.

2. **Estimated reads never get actuals.** Some clients upload the same CSV monthly and an estimated read from six months ago was never corrected. The system needs to detect a revised actual read for a period that already has an estimated read and update accordingly.

3. **Multiple utility providers per site.** A large campus may split electricity supply between two utilities (or have an on-site generator). Each requires a separate DataSource config.

4. **Renewable tariff tracking.** If a client is on a 100% renewable tariff, their market-based Scope 2 factor is 0 — but only if the tariff is REGO-backed (UK) or has matching RECs (US). Verifying this requires a separate contract check, not just accepting the client's claim.

5. **International voltage/tariff differences.** US is 60Hz/120V/240V; Europe is 50Hz/230V. This doesn't affect kWh calculations but the emission factors are completely different per grid region.

---

## Source 3: Corporate Travel — Flights, Hotels, Ground Transport

### Real-World Format Researched

Concur Expense Report Extract and Travel Itinerary Report CSV formats. Also reviewed Navan (TripActions) export format documentation.

### What I Learned

- **Flights often lack distance.** Concur's standard travel report gives you origin and destination city/airport, booking class, and ticket cost. Distance is sometimes included if the booking platform calculated it; often it's not.
- **Airport codes are IATA, not ICAO.** IATA codes (LHR, JFK, CDG) are what booking systems use. The OpenFlights dataset maps IATA codes to lat/lon coordinates and is freely available.
- **Hotel nights need nights stayed, not booking cost.** Concur records check-in and check-out dates. Nights stayed = check_out - check_in in days. The DEFRA factor for hotel stays is kg CO₂e per room-night by country, not by spend.
- **Ground transport is ambiguous.** "Ground transport" in a Concur report could be: rental car (Scope 3, emission factor by car type and fuel), taxi/rideshare (Scope 3, harder to factor precisely), rail (Scope 3, very different factor), or personal car mileage reimbursement (Scope 3, factor by vehicle type). The category column distinguishes some but not all of these.
- **Trip ID links segments.** A multi-leg trip (LHR → FRA → SIN) has one Trip ID with multiple segments. Layovers need to be handled as separate flight legs.
- **Booking class matters for some methodologies.** Business class has a higher per-seat emission factor than economy (less seats, more space per passenger). DEFRA provides multipliers: economy 1x, premium economy 1.26x, business 2.40x, first 2.40x.

### Sample Data Structure

```
Trip ID   | Employee ID | Category    | Departure Date | Origin | Destination | Class    | Distance (km) | Nights | Country   | Vendor
TRP-10291 | EMP-00341   | Air Travel  | 2024-01-15     | LHR    | JFK         | Business |               |        |           | British Airways
TRP-10291 | EMP-00341   | Air Travel  | 2024-01-22     | JFK    | LHR         | Economy  |               |        |           | American Airlines
TRP-10291 | EMP-00341   | Hotel       | 2024-01-15     |        |             |          |               | 7      | US        | Marriott
TRP-10292 | EMP-00892   | Air Travel  | 2024-01-18     | AMS    | MUC         | Economy  | 680           |        |           | KLM
TRP-10293 | EMP-00341   | Ground      | 2024-01-09     |        |             |          | 145           |        | GB        | Enterprise
TRP-10294 | EMP-00127   | Rail        | 2024-02-03     | LON    | MAN         | Standard | 302           |        | GB        | Avanti
```

**Why this sample looks this way:**
- LHR–JFK with no distance value is intentional — Concur does not always populate this. The system calculates it from IATA codes (haversine: ~5,539 km).
- Return leg is economy class (different factor than outbound business class)
- Hotel stay tied to the same Trip ID, 7 nights in the US
- One short-haul European flight (AMS–MUC) where Concur did supply a distance
- Ground rental car record with distance but no origin/destination
- Rail travel — included to show the category system handles it, even though the emission factor is much lower than air

### What Would Break in a Real Deployment

1. **Unknown airport codes.** Small regional airports or private airfields may not be in the OpenFlights dataset. The system flags these for manual distance entry.

2. **Expense data ≠ travel data.** Some clients use Concur for expense reporting, not travel booking. An employee who books their own flight and files an expense may not have origin/destination in the record — just "airfare, £450." No airport code, no distance calculable.

3. **Employee count vs. seat count.** Some travel is booked for a group (team offsite, 8 people on one booking). The Concur record may show one line with total cost. Without a headcount field, we'd undercount emissions.

4. **Frequent flyer upgrades.** An employee books economy, gets upgraded to business at the gate. Concur records the booked class (economy), not the flown class. This underestimates Scope 3 by up to 2.4x for those flights.

5. **Missing hotel country.** The DEFRA factor for hotels is country-specific. If the country field is blank (common for domestic travel records where the booker didn't populate it), we fall back to a global average — less accurate.

6. **Currency conversion for spend-based fallbacks.** If we ever need to use a spend-based emission factor (e.g., for hotel nights without country data), costs are in the employee's expense currency. A global client has employees submitting in USD, GBP, EUR, SGD. Spend-based factors require conversion to a common currency at the correct transaction date rate.
