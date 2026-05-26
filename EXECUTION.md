# Deployment & Execution Guide

## 1. Prerequisites

- Python 3.12+
- Git
- A GitHub account (for CI/CD)
- Supabase project (free tier works for launch)
- BatchSkipTracing account with API key
- Zapier account (free tier — 100 tasks/month; upgrade when volume increases)
- HubSpot account (free CRM)

---

## 2. Local Setup

### Clone and configure environment

```bash
git clone https://github.com/YOUR_USERNAME/clearpath-surplus-agent.git
cd clearpath-surplus-agent

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your actual keys
```

### Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
# or: .venv\Scripts\activate   # Windows

pip install -r requirements.txt
playwright install chromium --with-deps
```

### Initialize the Supabase database

1. Go to your Supabase project → SQL Editor
2. Paste the entire contents of `db/schema.sql`
3. Click "Run"
4. Verify tables exist: `surplus_cases`, `surplus_contacts`, `outreach_log`

---

## 3. Manual Test Run (Run Each Module Individually)

Always run in this order — each stage depends on the previous stage's DB output.

```bash
cd src

# Stage 1: Test scraper (dry run — will upsert cases to Supabase)
python scraper.py
# Confirm: check Supabase surplus_cases table for new rows

# Stage 2: Test skip tracer (only processes status='new' cases)
python skip_trace.py
# Confirm: check surplus_contacts table for new rows

# Stage 3: Test outreach (only processes outreach_status='pending' contacts)
python outreach.py
# Confirm: check outreach_log and verify HubSpot received the contact

# Run full pipeline manually
python scheduler.py
```

**Before running Stage 1 in production, complete the MJCS selector verification below.**

---

## 4. CRITICAL: Verify MJCS Selectors Before First Production Run

**Portal migration (2024-02-05):** The old ASP.NET `.jis` URL is permanently dead.
The new portal is a React SPA at:
```
https://casesearch.courts.state.md.us/casesearch/inquiry-search
```

`src/adapters/maryland_mjcs.py` has been rewritten for the new portal (Playwright-only,
no httpx). All selectors use aria roles and text content, not CSS class names.
Run the headed browser test below to verify them on the live site before first production run.

```bash
# Open a headed browser to visually verify the search flow
python -c "
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=800)
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 900})
        page = await ctx.new_page()
        await page.goto('https://casesearch.courts.state.md.us/casesearch/inquiry-search')
        input('Browser open — inspect the form, then press Enter to close')
        await browser.close()

asyncio.run(main())
"
```

**What to verify and where to fix if broken:**

| What | Where to update | Notes |
|------|----------------|-------|
| Disclaimer checkbox selector | `_accept_disclaimer()` | Look for `role=checkbox` or a specific label |
| "I Agree" / "Continue" button text | `_accept_disclaimer()` | Exact button label text |
| "Advanced Search" tab/link text | `_open_advanced_search()` | Exact label used on the tab |
| "Court System" label text | `_fill_search_form()` / `_set_dropdown()` | Exact `<label>` text for the dropdown |
| "County" label text | same | May be "Location", "Jurisdiction" |
| "Case Type" label text | same | May be "Category", "Type" |
| Date field labels | `_fill_date()` | May be "Filing Start", "From", etc. |
| Results table structure | `_parse_result_rows()` | Verify column order for case number, title, date |
| Detail page docket table | `_extract_case_detail()` | Verify column order for date and description |

Add `# VERIFIED [YYYY-MM-DD]` next to any selector you confirm in DevTools.

**Adapter smoke test (runs after Python is installed):**

```bash
python -c "
from src.adapters.maryland_mjcs import MarylandMJCSAdapter
import asyncio
a = MarylandMJCSAdapter(county='Baltimore County')
cases = asyncio.run(a.search_cases(lookback_days=30))
print(f'{len(cases)} cases found')
if cases:
    print('First case:', cases[0])
"
```

---

## 5. Production Deploy (Three Options)

### Option A: GitHub Actions (Recommended — Free)

1. Push code to GitHub
2. Go to repository Settings → Secrets and Variables → Actions
3. Add these **Repository Secrets:**

```
SUPABASE_URL
SUPABASE_SERVICE_KEY
BATCH_SKIP_TRACE_API_KEY
ZAPIER_OUTREACH_WEBHOOK
HUBSPOT_API_KEY
```

4. Add these **Repository Variables** (non-sensitive config):

```
ACTIVE_COUNTY = Baltimore County
SCRAPE_LOOKBACK_DAYS = 3
MIN_SURPLUS_AMOUNT = 5000
DEFAULT_FEE_PERCENTAGE = 40.0
```

5. Go to Actions tab → "ClearPath Daily Surplus Agent" → Enable workflow
6. Test with "Run workflow" button before relying on the daily cron

**Cost:** Free (GitHub Actions free tier = 2,000 min/month; this job takes ~5–10 min/day)

---

### Option B: Railway (Always-on, $5/month)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up

# Add environment variables via Railway dashboard
# Add a cron service: 0 10 * * * python src/scheduler.py
```

Use Railway if you need the agent to run more frequently than once/day or want persistent logs.

---

### Option C: Render (Free tier with cold starts)

Similar to Railway but has a free tier with cold starts (acceptable for a daily job).
Use Render's "Cron Job" service type. Point to `python src/scheduler.py`.

---

## 6. First-Run Checklist

Before enabling the daily cron, verify each item:

- [ ] `.env` filled in with all required keys
- [ ] Supabase schema applied (`db/schema.sql`)
- [ ] MJCS selectors verified against live site and updated in `scraper.py`
- [ ] Manual scraper run succeeded (rows in `surplus_cases`)
- [ ] Manual skip trace run succeeded (rows in `surplus_contacts`)
- [ ] Zapier webhook URL is active (test in Zapier's webhook tester)
- [ ] Zapier zap is turned ON
- [ ] HubSpot pipeline "ClearPath 9-stage" exists and stage IDs match `.env`
- [ ] SimpleTexting 10DLC number approved and sequence built
- [ ] Mailchimp drip sequence created and list ID in `.env`
- [ ] GitHub Secrets added (for GitHub Actions deploy)
- [ ] Contingency fee agreement template reviewed by Maryland attorney
- [ ] Outreach templates reviewed for TCPA/CAN-SPAM compliance

---

## 7. Daily Monitoring

**Check daily (5 minutes):**

1. **Supabase → Table Editor → `surplus_cases`**
   - Filter: `created_at > yesterday`
   - Expected: 1–20 new rows per day for Baltimore County
   - Red flag: 0 rows = scraper may be broken

2. **Supabase → Table Editor → `pipeline_summary` view**
   - Shows case counts by status and county
   - Watch for stuck cases (large count at 'skip_traced' = outreach not firing)

3. **GitHub Actions → Workflow runs**
   - Green check = success
   - Red X = look at logs; logs also uploaded as artifact on failure

4. **HubSpot → CRM → Deals**
   - New deals should appear daily if cases are being worked
   - Check deal stage distribution weekly

**Check weekly:**
- Supabase `outreach_log` for response rates
- SimpleTexting for any STOP replies (add to do_not_contact in Supabase)
- BatchSkipTracing account balance (reload when low)
