# Agent Skills Reference

Every callable capability in the ClearPath Surplus agent with inputs, outputs, and side effects.

---

## scraper.py

### `search_court_cases(county, from_date, to_date, page)`
**Input:**
- `county: str` — County short name from counties.json (e.g., `"Baltimore County"`)
- `from_date: date` — Start of filing date range
- `to_date: date` — End of filing date range
- `page: Page` — Playwright Page object

**Output:** `list[CaseRecord]` — Parsed case rows from MJCS search results

**Side effects:** None (read-only scrape)

**Notes:** Handles pagination automatically; delays 1.5s between requests

---

### `detect_surplus(case, page)`
**Input:**
- `case: CaseRecord` — Must have `detail_url` populated
- `page: Page` — Playwright Page object

**Output:** `SurplusResult | None`
- Returns `None` if no surplus keywords found in docket
- Returns `SurplusResult` with confidence level ("high"/"medium"/"low"), keywords found, and parsed dollar amount

**Side effects:** Mutates `case.defendant_name`, `case.plaintiff_name`, `case.property_address`, `case.surplus_amount`, `case.raw_docket` if data is found on the detail page

---

### `upsert_case(case)`
**Input:** `case: CaseRecord` with `surplus_amount` set

**Output:** `None`

**Side effects:** Inserts or updates row in Supabase `surplus_cases` table with `status='new'`

---

### `run_scraper(county, lookback_days)`
**Input:**
- `county: str` — Active county to scrape
- `lookback_days: int` — Days back from today (default: 3)

**Output:** `list[CaseRecord]` — Cases where surplus was detected

**Side effects:** Upserts all detected surplus cases to Supabase; logs all activity to loguru

---

## skip_trace.py

### `skip_trace_owner(name, address, provider)`
**Input:**
- `name: str` — Full name of original property owner (defendant name from court)
- `address: str` — Last known address (property address)
- `provider: str` — `"batchskiptracing"` (default) or `"beenverified"`

**Output:** `SkipTraceResult | None`
- `best_phone: str | None`
- `best_email: str | None`
- `current_address: str | None`
- `provider: str`
- `raw_response: dict` — Full API response for debugging

**Side effects:** None (API call only, no DB writes)

**Error behavior:** Returns `None` on any API error; logs specific error with HTTP status

---

### `run_skip_tracer()`
**Input:** None (reads from Supabase)

**Output:** `int` — Count of contacts successfully traced

**Side effects:**
- Reads `surplus_cases` where `status='new'` and `surplus_amount >= MIN_SURPLUS_AMOUNT`
- Writes to `surplus_contacts` table
- Updates `surplus_cases.status` → `'skip_traced'`
- Logs each result

---

## outreach.py

### `trigger_outreach(contact)`
**Input:** `contact: dict` — Enriched contact row (surplus_contacts joined with surplus_cases)

**Output:** `bool` — True if Zapier webhook returned 2xx

**Side effects:** None (the Zapier zap handles downstream effects)

**Zapier zap output (configured separately in Zapier.com):**
1. HubSpot contact created
2. HubSpot deal created at stage "New Lead"
3. Contact added to SimpleTexting 10DLC drip sequence (3 texts, spaced 2–4 days)
4. Contact added to Mailchimp email sequence (5 emails, spaced 3–7 days)

---

### `log_outreach(db, contact_id, channel, template, success)`
**Input:** Supabase client, contact ID, channel name, template identifier, success flag

**Output:** `None`

**Side effects:** Inserts row to `outreach_log` table

---

### `run_outreach()`
**Input:** None (reads from Supabase)

**Output:** `int` — Count of contacts where outreach was triggered

**Side effects:**
- Reads `surplus_contacts` where `outreach_status='pending'`
- Updates `outreach_status` → `'mail_sent'` on success
- Updates `surplus_cases.status` → `'outreach_sent'`
- Writes to `outreach_log`

---

## hubspot_sync.py (direct API — Zapier backup)

### `create_hubspot_contact(first_name, last_name, phone, email, address)`
**Input:** Contact fields

**Output:** `str | None` — HubSpot contact ID, or None on failure

**Side effects:** Creates contact in HubSpot CRM; handles 409 (already exists) gracefully

---

### `create_hubspot_deal(deal_name, surplus_amount, contact_id)`
**Input:**
- `deal_name: str` — e.g., `"Surplus – 123 Main St (C-21-001234)"`
- `surplus_amount: float` — Full surplus (not fee)
- `contact_id: str` — HubSpot contact ID to associate

**Output:** `str | None` — HubSpot deal ID

**Side effects:** Creates deal in HubSpot; associates to contact

---

### `sync_to_hubspot(contact_db_id)`
**Input:** `contact_db_id: str` — Supabase `surplus_contacts.id`

**Output:** `str | None` — HubSpot contact ID

**Side effects:** Creates HubSpot contact + deal; stores `hubspot_contact_id` back in Supabase

---

## scheduler.py

### `run_pipeline()`
**Input:** None (reads all config from environment variables)

**Output:** `dict` — `{ "cases_found": int, "contacts_traced": int, "outreach_triggered": int }`

**Side effects:** Runs all three stages sequentially with logging

---

## What the Agent Cannot Do

| Capability | Reason | Workaround |
|------------|--------|------------|
| File Petition for Release of Surplus Funds | Requires physical court filing or attorney e-filing | Human/attorney files after agreement signed |
| Sign contingency agreements | Requires DocuSign/PandaDoc with human parties | Zapier triggers DocuSign after contact responds |
| Make legal determinations | Not a licensed attorney | Refer contested claims to Maryland attorney |
| Access courts that block scrapers | MJCS may add CAPTCHA or block IPs | Rotate user-agent; use residential proxy as last resort |
| Call property owners | TCPA compliance requires human judgment for calls | Outreach is mail + SMS + email only |
| Guarantee contact info accuracy | Skip trace data is probabilistic | Always verify before filing claim |
| Operate in states where finder fees are prohibited | Varies by state (see LEGAL.md) | Check fee cap status before expanding |
