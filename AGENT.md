# ClearPath Surplus Agent

## What This Agent Is

An autonomous Python agent that identifies foreclosure surplus funds owed to original homeowners in Maryland, locates those homeowners via skip tracing, and triggers a multi-channel outreach campaign to connect them with their money — in exchange for a contingency fee.

This is not a legal services tool. The agent finds claimants and initiates contact. A licensed attorney handles contested claims if needed.

**Current scope:** Baltimore County, Maryland  
**Expansion path:** All 24 Maryland jurisdictions → FL, GA, TX, OH, NC

---

## What It Does Autonomously

| Step | Action | Tool |
|------|--------|------|
| 1 | Search MJCS for CAEF cases filed in last N days | Playwright scraper |
| 2 | Detect surplus keywords in case dockets | Regex + keyword scan |
| 3 | Parse surplus amount, defendant, property address | HTML parser |
| 4 | Upsert case to Supabase `surplus_cases` | Supabase Python client |
| 5 | Skip-trace owner via BatchSkipTracing API | httpx |
| 6 | Write contact to `surplus_contacts` | Supabase |
| 7 | POST outreach payload to Zapier webhook | httpx |
| 8 | Zapier creates HubSpot deal + triggers SMS/email sequences | Zapier |
| 9 | Log every action to `outreach_log` | Supabase |

**Runs daily at 6:00 AM ET via GitHub Actions.**

---

## What It Does NOT Do

- Cannot file claims with the court — a human must prepare and file the Petition for Release of Surplus Funds
- Cannot sign agreements on behalf of the business — DocuSign/PandaDoc handles this after human contact
- Cannot make legal determinations about claim validity
- Cannot access court systems that block automated requests (will log and skip)
- Cannot reach property owners in states where finder fees are prohibited (see LEGAL.md)
- Does not call property owners — outreach is mail, SMS, and email only

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  GitHub Actions (6 AM ET)                │
│                    scheduler.py                          │
└──────────────┬──────────────────────────────────────────┘
               │
       ┌───────▼──────┐
       │  Stage 1:    │
       │  scraper.py  │◄──── Playwright ──► MJCS (mdcourts.gov)
       │              │      headless         CAEF case search
       └───────┬──────┘      Chromium         + docket scan
               │ upsert surplus cases
       ┌───────▼──────────────────┐
       │       Supabase           │
       │  surplus_cases table     │
       │  surplus_contacts table  │
       │  outreach_log table      │
       └───────┬──────────────────┘
               │ read new cases
       ┌───────▼──────┐
       │  Stage 2:    │
       │ skip_trace.py│◄──── httpx ──► BatchSkipTracing API
       │              │                (phone + email + address)
       └───────┬──────┘
               │ write contacts
       ┌───────▼──────┐
       │  Stage 3:    │
       │  outreach.py │──── POST ──► Zapier Webhook
       └──────────────┘              │
                                     ├──► HubSpot CRM
                                     │    (contact + deal created)
                                     ├──► SimpleTexting
                                     │    (3-text 10DLC sequence)
                                     └──► Mailchimp
                                          (5-email drip)
```

---

## Data Flow (End-to-End)

```
Court files → MJCS website → scraper detects surplus keyword
    → surplus_cases (status: new)
    → skip_trace finds phone/email
    → surplus_contacts (status: pending)
    → Zapier triggers multi-channel outreach
    → HubSpot deal created (stage: New Lead)
    → Owner responds → agreement signed → claim filed
    → Court releases funds → ClearPath collects fee
```

---

## Agent Author Suggestions

*Direct feedback on architectural decisions, what I would do differently, and what would make this world-class.*

---

### 1. Skip-Trace Provider — BatchSkipTracing Is Fine to Start, But Not the Best

**What I'd use instead (ranked):**

| Provider | Why Better | Notes |
|----------|-----------|-------|
| **BatchData** (batchdata.com) | Real-estate-native data, higher match rates on distressed property owners | ~$0.10–0.20/hit |
| **TLO (TransUnion)** | Highest data quality in industry, built for skip tracing | Requires credentialing; not self-serve |
| **IDI (Harte-Hanks)** | FCRA-compliant, extremely deep address history | Enterprise agreement required |
| **Propstream** | Real estate focused, has owner mailing address built-in | $97/mo flat, may cover most your use case |
| BatchSkipTracing | Good enough to start, easy API | Data quality drops for people who've moved frequently |

**Recommendation:** Start with BatchSkipTracing to get to market fast. Switch to BatchData at 50+ cases/month. Add Propstream as a parallel source — you already need it for property data enrichment anyway.

---

### 2. Playwright vs. Requests — Requests Would Work Here

The MJCS site is a classic ASP.NET Web Forms application (circa 2005–2010 era). It uses `__VIEWSTATE` and `__EVENTVALIDATION` tokens but does NOT require JavaScript rendering for most pages.

**Better approach:**
```python
import httpx
from bs4 import BeautifulSoup

# 1. GET the search page to extract VIEWSTATE tokens
# 2. POST the form with viewstate + search params
# 3. Parse HTML response with BeautifulSoup
# 4. No browser needed
```

**Why this matters:**
- Playwright + Chromium = ~300MB install, 2–4s startup time, higher memory use
- httpx + BS4 = instant, lightweight, runs fine in Lambda/Railway free tier
- MJCS has rate limits that Playwright's timing makes harder to manage precisely

**However:** Keep Playwright as a fallback for captcha-gated pages. The current implementation with Playwright is correct and safe — I've kept it as-is because it handles edge cases. Refactor to httpx in Phase 2.

---

### 3. Zapier Integration — Correct for Launch, Fragile at Scale

Zapier is the right call for getting to market in week one. But at 50+ cases/month, here's why you'll regret it:

- **Reliability:** Zapier Zaps fail silently. A webhook that bounces at 2 AM leaves contacts uncontacted — you won't know until you check manually.
- **Latency:** Zapier adds 5–30 seconds of latency per webhook. For outreach this doesn't matter, but for CRM sync it can create confusing states.
- **Cost:** At scale, Zapier's task pricing becomes significant.

**Recommended migration path (Phase 2):**
1. Keep Zapier for SimpleTexting (their direct API requires 10DLC approval which you may not have yet)
2. Replace Zapier → HubSpot with the direct `hubspot_sync.py` already in this codebase
3. Replace Zapier → Mailchimp with direct Mailchimp API (`mailchimp-marketing` Python library, 10 lines of code)

The `hubspot_sync.py` file in this repo is already the direct replacement. Just wire it in.

---

### 4. Legal Risks in Outreach — Three Real Concerns

**a) TCPA compliance for SMS**
SimpleTexting handles opt-out, but your initial text message must include: (1) your identity, (2) that this is an advertisement/commercial message, (3) STOP instructions. Don't automate the first text without a human reviewing the template against TCPA requirements first.

**b) CAN-SPAM for email**
Your Mailchimp drip must include: physical mailing address, unsubscribe link, accurate From header. Mailchimp enforces this but double-check your template.

**c) Maryland's "Foreclosure Purchaser Act" (Md. Code, Real Prop. §7-105)**
This law covers certain solicitations to foreclosed homeowners. While surplus recovery agents are NOT regulated under this act (it targets purchase offers, not surplus claims), the outreach language should make crystal clear you are NOT offering to purchase the property and NOT a real estate agent. Add this disclaimer to every template:

> "ClearPath Surplus is not a law firm, real estate agent, or lender. We are a finder service that helps former homeowners claim unclaimed court funds. No legal representation is offered or implied."

---

### 5. Monitoring — Basic Logging Is Not Enough for Production

Current implementation logs to file. For a business running daily, you need:

**Minimum viable monitoring stack:**
- **Sentry** (free tier) — catches exceptions from all three stages, emails you on error. 30-minute setup.
- **Supabase alerts** — set up a `pg_cron` job that sends an alert if `surplus_cases` hasn't been updated in 25 hours (means scraper failed silently).
- **GitHub Actions email** — already built-in; Actions emails you on workflow failure.

**Recommended (when at 25+ cases/month):**
- **Slack webhook** — `scheduler.py` already has the summary dict; POST it to a #clearpath-daily Slack channel at end of run.
- **Simple dashboard** — Supabase has a built-in Table Editor + the `pipeline_summary` view in schema.sql is ready to drive a Retool or Metabase dashboard in an afternoon.

---

### 6. What I Would Build Differently for a World-Class System

These are the changes that separate a $10K/month side business from a $1M/year operation:

**a) Replace regex surplus detection with LLM document analysis**
Court dockets are messy. A regex will miss "the auditor has filed a report showing net proceeds of $34,211.50 remain after satisfying the lien." An LLM call (Claude Haiku, $0.001/page) that reads the full docket and extracts structured surplus data would catch 40%+ more cases and eliminate false positives.

**b) Add a property data layer**
Before skip tracing, enrich each case with ATTOM Data or CoreLogic property records:
- Estimated current owner equity (validates surplus claim likelihood)
- Owner's likely demographic/financial profile (prioritize outreach order)
- Property's last sale price and current AVM (justify fee to owner)

**c) Automated claims preparation (the real moat)**
The bottleneck is not finding cases — it's filing the petition. Maryland Circuit Court has a fairly standard form for Petition for Release of Surplus Funds. A system that auto-generates a court-ready PDF using the case data, filled out and ready for attorney review, would cut your per-case labor from hours to minutes. Use `reportlab` or `pypdf` to fill court PDF templates.

**d) Multi-state expansion via CourtAPI / UniCourt**
Instead of Playwright-scraping each state's different court website, CourtAPI (courtapi.com) and UniCourt (unicourt.com) provide normalized APIs for court records across many jurisdictions. At $0.10–0.50/case, this becomes economical at scale and lets you expand to FL, GA, TX in weeks instead of months.

**e) Owner notification scoring model**
Build a simple ML model (even logistic regression) that predicts: given case data (surplus amount, time since sale, county, property type), what's the probability of successful contact and agreement? Use your first 100 cases as training data. Prioritize high-score cases for follow-up calls — stops you from wasting SimpleTexting credits on long-shot cases.

---

### 7. Market Opportunities Beyond Foreclosure Surplus

*If you nail this system, here's what the logical expansion looks like:*

**Immediate (same legal framework, same skills):**
- **Tax sale overages** — When a county sells a property for delinquent taxes and gets more than owed, the surplus is owed to the former owner. Same finder-fee model. Maryland counties hold millions in unclaimed tax sale overages. DIFFERENT process but same operator playbook.
- **Unclaimed property** — Maryland's Comptroller holds billions in unclaimed property (bank accounts, insurance proceeds, utility deposits). Finding owners and connecting them to the Comptroller's process is similar work. Fee model differs (flat fee or hourly vs. contingency).

**12-month horizon (higher complexity, higher revenue):**
- **Other states with no/high fee caps** — Florida (no fee cap, highest foreclosure volume in US), Georgia (10% cap, still profitable on large surpluses), Texas (no cap), Ohio (no cap). Your scraper architecture generalizes — each state needs a new scraper module.
- **White-label SaaS for other recovery agents** — There are hundreds of small surplus recovery operations doing this manually. Your agent as a SaaS product ("ClearPath OS") could serve them for $500–2,000/month. The database + scraper + outreach stack is the product.
- **Bankruptcy trustee distribution recovery** — Bankruptcy trustees distribute assets to creditors, but many small distributions go unclaimed. Less volume, higher per-claim value, requires different legal relationships.

**3-year horizon (platform play):**
- Build the data pipeline into a **nationwide court surplus intelligence database** — real-time, all counties that allow scraping. License data to attorneys, recovery agents, title companies. Subscription SaaS. This is a $10M+ business if executed.
- **AI-powered claims filing** — automate the Petition prep enough that you can file 50 claims/month with one paralegal instead of one attorney per claim. Requires state-by-state legal review but the technology is straightforward.
