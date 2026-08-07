# ClearPath website AWS launch runbook

Last verified: 2026-08-07

## Architecture

- AWS Amplify Hosting runs the Next.js website and server-side intake route.
- Amazon Route 53 registers and manages `clearpathsurplus.com`.
- Amplify provides the managed TLS certificate for the custom domain.
- Supabase stores `claim_inquiries`; its service-role key remains server-only.
- GitHub Actions continues to run the separate court-record agent.

Do not place the Supabase service-role key in a variable beginning with
`NEXT_PUBLIC_`. Do not copy LiberiaLearn production secrets into this app.

## Verified AWS facts

- A live Route 53 availability query returned `AVAILABLE` for
  `clearpathsurplus.com` on 2026-08-07. Availability can change at any time.
- A live Route 53 price query returned $16 USD for .com registration and
  $16 USD for renewal. Registration and renewal charges are non-refundable.
- Route 53 currently charges $0.50 per hosted zone per month for the first 25
  zones, plus applicable DNS query charges.
- Amplify Hosting is usage-based. Check the AWS pricing page again before
  enabling paid options such as Amplify WAF.

## Human confirmations required before public launch

- Confirm whether the Maryland entity has actually been formed. Until then,
  use `ClearPath Surplus Solutions`, not the `LLC` suffix.
- Provide accurate domain registrant name, email, phone, and postal address.
- Create the public support email and provide a business mailing address.
- Confirm the AWS account that should own the domain and hosting. Current local
  credentials identify as an IAM user named `liberialearn-deploy`; use a
  ClearPath-scoped role and cost tags before creating production resources.
- Have Maryland-licensed counsel review the service agreement, fee disclosures,
  privacy policy, terms, and outreach templates.
- Assign an owner and response-time target for every website inquiry.

## Deployment

1. Run `npm ci`, `npm test`, `npm audit`, and `npm run build`.
2. Apply `db/migrations/003_claim_inquiries.sql` to the intended Supabase
   project and confirm row-level security is enabled.
3. Push the production branch to GitHub.
4. In AWS Amplify, choose Create new app, connect the GitHub repository, and
   select the production branch.
5. Let Amplify use `amplify.yml`. Keep the Standard build instance and
   confirm the artifact directory is `.next`.
6. Add these environment variables:

   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `NEXT_PUBLIC_SITE_URL` using the temporary Amplify URL
   - `NEXT_PUBLIC_CONTACT_EMAIL`
   - `NEXT_PUBLIC_LEGAL_BUSINESS_NAME`

7. Deploy and verify the home, privacy, terms, robots, sitemap, and intake
   routes on the temporary Amplify URL.
8. Submit a test inquiry and confirm exactly one row reaches
   `claim_inquiries`. Delete only that clearly marked test row afterward.

## Domain purchase and connection

1. Recheck availability immediately before purchase.
2. In Route 53, open Registered domains and choose Register domains.
3. Search for `clearpathsurplus.com`, choose one year, and review auto-renew.
4. Enter the confirmed registrant contact details and complete checkout.
5. In Amplify, open Hosting, Custom domains and add
   `clearpathsurplus.com`.
6. Map the root domain and `www` to the production branch. Redirect one host
   to the other so search engines see a single canonical site.
7. Set `NEXT_PUBLIC_SITE_URL=https://clearpathsurplus.com` and redeploy.
8. Wait for Amplify to show the domain and certificate as available, then test
   both HTTPS hostnames.

## Final public gate

- No invented recovery totals, testimonials, licenses, guarantees, or LLC
  status.
- Public business name, email, phone, and mailing address match official
  records and counsel-approved documents.
- Mobile layout has no horizontal overflow at 375 px.
- Keyboard navigation and visible focus states work.
- Privacy and terms pages name AWS and Supabase accurately.
- Intake rejects an oversized request, rejects an unavailable preferred contact
  method, and never exposes the Supabase service key.
- A real test inquiry is received and assigned to the response owner.
- Route 53 auto-renew, AWS Billing alerts, and Amplify access logs are reviewed.

## Rollback

If a deployment fails, use Amplify Hosting deployment history to redeploy the
last known-good build. If intake is failing, keep the informational site live,
temporarily disable the form CTA, and publish the verified support contact.
Do not expose a service key in client-side code as a workaround.
