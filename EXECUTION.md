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

The MJCS site at `https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis` is an older ASP.NET Web Forms application. Its form field names and HTML structure must be verified against the live site before the scraper will work.

```bash
# Run this in a Python REPL to inspect the live MJCS form
python -c "
import asyncio
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=False to SEE the browser
    page = browser.new_page()
    page.goto('https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis')
    input('Press Enter after inspecting the page...')
    browser.close()
"
```

**Things to verify in `src/scraper.py`:**

| Line | What to Check | Expected value (verify live) |
|------|--------------|------------------------------|
| `select[name="caseType"]` | Field name of case type dropdown | May be `caseType`, `type`, or other |
| `value="CAEF"` | Option value for foreclosure | May be `CAEF`, `CAE`, or descriptive text |
| `select[name="countyName"]` | Field name of county selector | May be `countyName`, `county`, `location` |
| `input[name="filingStart"]` | Start date field name | May be `filingStart`, `startDate`, `from` |
| `input[name="filingEnd"]` | End date field name | May be `filingEnd`, `endDate`, `to` |
| `input[type="submit"]` | Submit button selector | Verify it's unique on the page |
| `table.resultsTable` | Results table class | Open DevTools on results page |
| `table.docketTable` | Docket table class | Open DevTools on case detail page |

Update each selector in `scraper.py` after verifying against the live site.

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
