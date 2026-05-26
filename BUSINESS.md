# Business Model — ClearPath Surplus

## How the Business Works

ClearPath Surplus identifies homeowners who have unclaimed court surplus funds following a foreclosure sale. For every case where the court-supervised sale price exceeded the total liens:

```
Sale Price – (Mortgage Balance + Liens + Court Costs) = SURPLUS

Surplus is legally owed to the former homeowner.
ClearPath finds them. ClearPath helps them claim it.
ClearPath earns a contingency fee (30–40%) upon court release.
```

**No upfront cost to the claimant. No fee unless funds are recovered.**

---

## Fee Structure

See LEGAL.md for full fee schedule rationale.

| Surplus Amount | ClearPath Fee | Claimant Receives | Net to ClearPath (after ~$200 costs) |
|---------------|--------------|-------------------|--------------------------------------|
| $10,000 | 40% = $4,000 | $6,000 | ~$3,800 |
| $25,000 | 38% = $9,500 | $15,500 | ~$9,300 |
| $50,000 | 35% = $17,500 | $32,500 | ~$17,300 |
| $100,000 | 30% = $30,000 | $70,000 | ~$29,800 |

**Average Baltimore County surplus (estimated):** $18,000–$35,000  
**Average ClearPath fee per closed case:** $7,000–$12,000

---

## Pipeline Stages (HubSpot 9-Stage CRM)

| Stage | Label | Description | Est. Conversion |
|-------|-------|-------------|-----------------|
| 1 | **New Lead** | Case found, outreach sent | 100% entry |
| 2 | **Contacted** | Owner acknowledged receipt | 20–30% of leads |
| 3 | **Interested** | Owner verbally interested | 50% of contacted |
| 4 | **Agreement Sent** | DocuSign/PandaDoc sent | 60% of interested |
| 5 | **Agreement Signed** | Contingency agreement executed | 70% of sent |
| 6 | **Claim Filed** | Petition filed with court | 90% of signed |
| 7 | **Claim Under Review** | Court processing (30–90 days) | 85% of filed |
| 8 | **Funds Released** | Court releases to claimant | 90% of reviewed |
| 9 | **Closed / Paid** | Fee collected | 95% of released |

**Overall funnel conversion (lead → paid):** ~8–12%  
**Average time to close:** 3–6 months

---

## Revenue Projections

### Cases Worked = Cases Where Outreach Was Sent

| Cases Worked/Month | Contacted (25%) | Agreements Signed (5%) | Avg Fee | Monthly Revenue | Annual Revenue |
|-------------------|-----------------|------------------------|---------|-----------------|----------------|
| 10 | 2–3 | 0–1 | $9,000 | $0–$9,000 | $0–$108k |
| 25 | 6 | 1–2 | $9,000 | $9,000–$18,000 | $108k–$216k |
| 50 | 12 | 2–4 | $10,000 | $20,000–$40,000 | $240k–$480k |
| 100 | 25 | 5–8 | $11,000 | $55,000–$88,000 | $660k–$1.1M |

**Note:** Revenue lags 3–6 months behind cases worked (court processing time). Month 1 = investment. Month 4+ = returns.

**Conservative 12-month projection (Baltimore County only, starting slow):**
- Months 1–3: 0–1 closes = $0–$15k (ramp-up, learning curve)
- Months 4–6: 2–3 closes/month = $18k–$36k/month
- Months 7–12: 3–5 closes/month = $27k–$55k/month
- **Year 1 total: $150k–$350k** (highly variable; dependent on close rate)

---

## Cost Structure

### Per-Case Variable Costs

| Item | Cost | Notes |
|------|------|-------|
| Skip trace (BatchSkipTracing) | $0.25–$0.75 | Per hit |
| SimpleTexting (10DLC) | $0.08–0.15 | Per SMS, 3-text sequence |
| Mailchimp | ~$0.01/email | 5-email drip |
| Direct mail (if used) | $0.50–$1.50 | USPS first class |
| DocuSign/PandaDoc | $2–5 | Per agreement envelope |
| **Total per case** | **~$5–15** | Before agreement signing |
| Attorney review (contested claims) | $500–2,000 | Only for contested/complex cases |

### Monthly Fixed Costs

| Item | Monthly Cost |
|------|-------------|
| Supabase (Pro plan) | $25 |
| GitHub Actions | Free (2,000 min/month) |
| HubSpot (free tier) | $0 |
| Mailchimp (up to 500 contacts) | $0–$13 |
| SimpleTexting | $25/month + SMS |
| Squarespace | $23 |
| Google Workspace | $12 |
| **Total fixed** | **~$100–$120/month** |

### One-Time Setup Costs

| Item | Cost |
|------|------|
| BatchSkipTracing credit load | $100–500 |
| DocuSign/PandaDoc annual | $150–300 |
| Attorney (agreement template review) | $500–1,500 |
| Domain + SSL | $20 |
| **Total setup** | **~$800–$2,500** |

**Break-even:** 1 closed case covers 3–6 months of operating costs.

---

## Competitive Moat

What stops someone else from replicating this?

1. **Speed of outreach** — The agent runs daily and sends outreach within 24–48 hours of a case appearing in the court system. Manual operators check MJCS weekly or monthly.

2. **Data pipeline** — The Supabase database accumulates historical cases, including ones where earlier outreach failed. Re-engagement campaigns on old leads are high-ROI.

3. **Relationship with claimants** — First mover wins. If ClearPath contacts an owner first with a professional, plain-language offer, competitors showing up later are fighting uphill.

4. **Process reliability** — Human operators miss cases when sick, on vacation, or distracted. The agent runs at 6 AM every day without fail.

5. **Multi-county scale** — One human can work 1–2 counties manually. This agent runs 24 Maryland counties with the flip of a config switch.

---

## Scaling Roadmap

### Phase 1: Baltimore County (Months 1–3)
- Validate scraper against live MJCS
- Tune surplus detection (reduce false positives)
- Build outreach templates tested on 20–50 leads
- Establish close rate baseline

### Phase 2: Maryland Expansion (Months 4–6)
Add active counties in order:
1. Prince George's County (high volume)
2. Anne Arundel County (Annapolis suburbs)
3. Baltimore City (highest raw volume, but lower avg surplus)
4. Montgomery County (highest avg surplus amounts)

### Phase 3: Tax Sale Overages (Month 6+)
- Same operator, different trigger (county tax sales vs. mortgage foreclosures)
- Each Maryland county holds tax sales separately; process similar but different data source
- Add `tax_sale_overages` module to scraper

### Phase 4: Multi-State (Year 2)
Priority order by volume × no fee cap × data accessibility:
1. **Florida** (highest volume, no cap, largest surpluses)
2. **Ohio** (consistent volume, no cap)
3. **Illinois** (Cook County alone is massive)
4. Hire one operations person per 2–3 states

### Phase 5: Platform Play (Year 3)
- License "ClearPath OS" to other surplus recovery operators as SaaS
- $500–2,000/month/seat
- 100 operators × $1,000 = $100k MRR
