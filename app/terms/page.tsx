import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Terms & Disclosures" };

export default function TermsPage() {
  return (
    <article className="legal-page">
      <div className="shell legal-shell">
        <p className="eyebrow">Legal</p>
        <h1>Terms &amp; disclosures</h1>
        <p className="updated">Effective August 7, 2026</p>
        <p className="legal-intro">ClearPath Surplus Solutions is a private finder service. We are not a law firm and are not affiliated with any court, government agency, lender, or real estate company.</p>

        <h2>Informational website</h2>
        <p>This website provides general information about foreclosure surplus funds and our private finder service. It is not legal, tax, or financial advice. Information may not apply to every case, and laws and court procedures can change.</p>

        <h2>No attorney-client or service relationship</h2>
        <p>Using this website or submitting an inquiry does not create an attorney-client relationship, hire ClearPath Surplus Solutions, authorize us to act for you, or create a contingency-fee agreement. Any paid service requires a separate written agreement that states the work and fee before services begin.</p>

        <h2>Your right to proceed independently</h2>
        <p>You may contact the Circuit Court handling a foreclosure to ask about surplus funds and applicable claim procedures. You are not required to use ClearPath or any other finder service, and you may be able to pursue a claim yourself without paying a finder fee.</p>

        <h2>No guarantee</h2>
        <p>A public record, preliminary review, estimated amount, or communication from ClearPath does not guarantee eligibility, ownership, recovery, timing, or a particular result. Competing claims, liens, court rulings, deadlines, and incomplete records may affect any recovery.</p>

        <h2>Acceptable use</h2>
        <p>You agree not to misuse the site, interfere with its operation, submit information you are not authorized to provide, impersonate another person, or attempt to access nonpublic systems or data.</p>

        <h2>Website availability</h2>
        <p>We may update, suspend, or discontinue parts of the website. To the extent permitted by law, the site is provided as available without warranties that it will always be uninterrupted or error-free.</p>

        <h2>Privacy and changes</h2>
        <p>Our <Link href="/privacy">privacy policy</Link> explains how website information is handled. We may revise these terms by posting an updated effective date. Continued use after an update means the revised website terms apply.</p>
      </div>
    </article>
  );
}
