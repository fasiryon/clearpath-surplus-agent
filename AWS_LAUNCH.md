# ClearPath website AWS launch runbook

Last verified: 2026-08-07

## Current deployment status (2026-08-07)

- Amplify app `clearpath-surplus` (appId `d225srxpadlxy`, account
  `466568847266`, region `us-east-1`) is live and connected to
  `github.com/fasiryon/clearpath-surplus-agent`, branch
  `feat/clearpath-aws-launch`, auto-build on push enabled.
- Live temporary URL:
  `https://feat-clearpath-aws-launch.d225srxpadlxy.amplifyapp.com`.
  Home, privacy, terms, robots.txt, sitemap.xml, and `/api/intake` all
  verified working.
- Supabase project `ClearPath Surplus` (`aczxhwsjyauqqxgxoeff`,
  us-east-1) holds `claim_inquiries` plus the existing agent tables
  (`surplus_cases`, `surplus_contacts`, `outreach_log`, `agent_tasks`,
  `agent_runs`). A real test inquiry was submitted through the live
  intake endpoint, confirmed as a single row, then deleted.
- **Domain purchase is blocked.** `aws route53domains register-domain`
  for `clearpathsurplus.com` failed twice (2026-08-07) with a generic
  `"We can't finish registering your domain. Contact AWS Support"`
  error, even though the same account successfully registered
  `liberiago.com` two days earlier with an identical request shape. No
  charge occurs on a `FAILED` registration. Needs an AWS Support case
  (link in the operation error) before retrying. Until resolved, the
  site stays on the temporary `amplifyapp.com` URL.
- Registrant on file for the eventual purchase: Farquema Siryon, 21
  Reaching Circle, Baltimore, MD 21221.

## Architecture

- AWS Amplify Hosting runs the Next.js website and server-side intake route.
- Amazon Route 53 registers and manages `clearpathsurplus.com`.
- Amplify provides the managed TLS certificate for the custom domain.
- Supabase stores `claim_inquiries`; its service-role key remains server-only.
- GitHub Actions continues to run the separate court-record agent.

Do not place the Supabase service-role key in a variable beginning with
`NEXT_PUBLIC_`. Do not copy LiberiaLearn production secrets into this app.

## SSR runtime environment variables

Amplify Hosting does not automatically pass non-`NEXT_PUBLIC_` environment
variables to the SSR compute runtime, even though the same variables ARE
visible during the build. `amplify.yml`'s build step writes `SUPABASE_URL`
and `SUPABASE_SERVICE_KEY` into `.env.production` (which Next.js loads at
runtime) so the `/api/intake` route can read them. AWS's own docs advise
against putting secrets in environment variables because deploy artifacts
containing `.env.production` are readable by anyone with access to the
Amplify app's build artifacts; the recommended alternative for AWS-native
resources is an SSR compute IAM role, but that doesn't apply to a
third-party secret like a Supabase service key. Restrict IAM access to this
Amplify app if that risk matters for this project.

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
