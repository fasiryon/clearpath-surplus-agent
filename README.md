# ClearPath Surplus

ClearPath combines a Python court-record and outreach pipeline with a customer-facing Next.js website. The website is configured for AWS Amplify Hosting and stores case-review requests in the same Supabase project used by the automation.

## Customer website

Requirements: Node.js 20.9 or newer.

```powershell
npm install
npm run dev
```

Open `http://localhost:3000`. The site includes a responsive landing page, transparent disclosures, privacy and terms pages, a server-side intake endpoint, and Supabase-backed inquiries with no service key exposed to the browser.

## Enable the intake form

1. Run [`db/migrations/003_claim_inquiries.sql`](db/migrations/003_claim_inquiries.sql) in the Supabase SQL Editor.
2. Set `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env.local` for local development.
3. Never prefix the service key with `NEXT_PUBLIC_`; it must remain server-only.

## Deploy on AWS

Use AWS Amplify Hosting because the customer intake endpoint requires a
server-side Next.js runtime. The checked-in `amplify.yml` uses Node.js 20,
`npm ci`, and the `.next` output expected by Amplify.

1. Push this branch to GitHub and connect the repository in AWS Amplify
   Hosting.
2. Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` as server-side environment
   variables. Add `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_CONTACT_EMAIL`, and
   `NEXT_PUBLIC_LEGAL_BUSINESS_NAME` as public build variables.
3. Deploy the branch and test the assigned `amplifyapp.com` URL.
4. Submit a test inquiry and confirm the row appears in Supabase
   `claim_inquiries`.
5. Register `clearpathsurplus.com` in Route 53 only after the registrant
   contact details and exact legal entity name are confirmed.
6. In Amplify, open Hosting, Custom domains, add `clearpathsurplus.com`, and
   map both the root domain and `www` to the production branch.
7. Set `NEXT_PUBLIC_SITE_URL=https://clearpathsurplus.com`, redeploy, and
   verify HTTPS, the canonical sitemap, and the intake form.

The Python workflow continues to run through GitHub Actions. Amplify hosts
only the website and intake endpoint. See `AWS_LAUNCH.md` for the complete
launch and rollback checklist.

## Before public launch

The repository does not currently contain the following required business details:

- legally registered business name and entity status. Do not set the public
  legal name to `ClearPath Surplus Solutions LLC` until formation is confirmed;
- customer support email and phone number;
- business mailing address (also needed for compliant commercial email);
- attorney-reviewed contingency agreement, fee disclosures, privacy policy, and outreach templates;
- a documented intake-response owner and response-time target.

Do not publish invented testimonials, recovery totals, licensing claims, or guarantees. Add those trust signals only after they can be documented.

## Python agent

See [`AGENT.md`](AGENT.md), [`EXECUTION.md`](EXECUTION.md), and [`LEGAL.md`](LEGAL.md) for the automation architecture, operating instructions, and legal checklist.
