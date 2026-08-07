import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: {
    default: "ClearPath Surplus Solutions | Maryland Foreclosure Surplus Help",
    template: "%s | ClearPath Surplus Solutions",
  },
  description:
    "ClearPath Surplus helps former Maryland homeowners verify and recover surplus funds that may remain after a foreclosure sale.",
  openGraph: {
    title: "ClearPath Surplus Solutions",
    description: "Reclaiming hidden funds with clarity and trust.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

function Logo() {
  return (
    <Link className="logo" href="/" aria-label="ClearPath Surplus Solutions home">
      <span className="logo-mark" aria-hidden="true">
        <svg viewBox="0 0 40 40" role="img">
          <path d="M8 20.5 20 9l12 11.5" />
          <path d="M12 18.5V31h16V18.5" />
          <path d="M17 31V21h6v10" />
          <path d="M7 34h26" />
        </svg>
      </span>
      <span>
        <strong>ClearPath</strong>
        <small>SURPLUS SOLUTIONS</small>
      </span>
    </Link>
  );
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const contactEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL;
  const legalBusinessName =
    process.env.NEXT_PUBLIC_LEGAL_BUSINESS_NAME || "ClearPath Surplus Solutions";

  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="shell nav-wrap">
            <Logo />
            <nav aria-label="Primary navigation">
              <Link href="/#how-it-works">How it works</Link>
              <Link href="/#questions">Questions</Link>
              <Link className="nav-cta" href="/#check-my-case">Check my case</Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <div className="shell footer-grid">
            <div>
              <Logo />
              <p className="footer-note">
                Reclaiming hidden funds with clarity and trust. A private finder service serving Maryland homeowners.
              </p>
            </div>
            <div>
              <p className="footer-label">Explore</p>
              <Link href="/#how-it-works">How it works</Link>
              <Link href="/#questions">Common questions</Link>
              <Link href="/#check-my-case">Request a review</Link>
            </div>
            <div>
              <p className="footer-label">Legal</p>
              <Link href="/privacy">Privacy policy</Link>
              <Link href="/terms">Terms &amp; disclosures</Link>
              {contactEmail && <a href={`mailto:${contactEmail}`}>Contact us</a>}
            </div>
          </div>
          <div className="shell footer-bottom">
            <p>© {new Date().getFullYear()} {legalBusinessName}. All rights reserved.</p>
            <p>Not a law firm · Not affiliated with any court or government agency</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
