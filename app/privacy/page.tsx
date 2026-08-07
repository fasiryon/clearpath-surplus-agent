import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Privacy Policy" };

export default function PrivacyPage() {
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL;

  return (
    <article className="legal-page">
      <div className="shell legal-shell">
        <p className="eyebrow">Privacy</p>
        <h1>Privacy policy</h1>
        <p className="updated">Effective August 7, 2026</p>
        <p className="legal-intro">This policy explains what ClearPath Surplus Solutions collects through this website and how that information is used. Please do not submit Social Security numbers, bank information, payment-card details, or identity documents through our intake form.</p>

        <h2>Information we collect</h2>
        <p>When you request a case review, we collect the information you choose to provide, which may include your name, phone number, email address, contact preference, foreclosed property address, county, court case number, and notes. Our hosting and database providers may also process basic technical data such as browser information, referring page, and request timestamps for security and operation of the site.</p>

        <h2>How we use information</h2>
        <p>We use submitted information to evaluate your inquiry, review relevant public records, contact you about the request, maintain business records, prevent abuse, and comply with applicable legal obligations. Submitting the form does not hire ClearPath or create a contingency-fee agreement.</p>

        <h2>Service providers and disclosure</h2>
        <p>We use service providers to host the website, store inquiries, monitor reliability, and support customer communication. These may include Amazon Web Services and Supabase. We may also disclose information when required by law, to protect rights or safety, or as part of a business transaction. We do not sell personal information for money.</p>

        <h2>Retention and security</h2>
        <p>We retain inquiry information for as long as reasonably needed to respond, operate the service, maintain required records, and resolve disputes. We use reasonable administrative and technical safeguards, but no internet transmission or storage system can be guaranteed completely secure.</p>

        <h2>Your choices</h2>
        <p>You may ask us to correct or delete information you submitted, subject to records we must retain for legal or operational reasons. You may also ask us to stop marketing contact. Reply STOP to an automated text where that option is provided.</p>

        <h2>Children</h2>
        <p>This service is intended for adults and is not directed to children under 18. We do not knowingly collect personal information from children.</p>

        <h2>Policy changes and contact</h2>
        <p>We may update this policy as the service changes. The effective date above will be revised when that happens. To submit a privacy request, {contactEmail ? <a href={`mailto:${contactEmail}`}>email ClearPath</a> : <>use the <Link href="/#check-my-case">website intake form</Link> and write “Privacy request” in the notes field</>}.</p>
      </div>
    </article>
  );
}
