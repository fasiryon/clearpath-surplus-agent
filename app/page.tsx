import Link from "next/link";
import { IntakeForm } from "@/components/IntakeForm";

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 14 0M14 7l5 5-5 5" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M9 3h10l6 6v20H9z" />
      <path d="M19 3v7h6M13 16h8M13 21h8" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="14" cy="14" r="9" />
      <path d="m21 21 7 7M10.5 14h7M14 10.5v7" />
    </svg>
  );
}

function HandshakeIcon() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="m4 12 6-5 6 3 6-3 6 5-5 12-7 3-7-3z" />
      <path d="m10 16 5 4c1 1 3 1 4 0l3-3M4 12l5 4M28 12l-6 5" />
    </svg>
  );
}

const faqs = [
  {
    question: "What are foreclosure surplus funds?",
    answer:
      "When a foreclosed property sells for more than the mortgage, liens, and court-approved costs, money may remain. That balance is generally called surplus or excess proceeds and may be payable to the former owner or other eligible claimants.",
  },
  {
    question: "Can I check or claim the money myself?",
    answer:
      "Yes. You can contact the Circuit Court handling the foreclosure and ask about surplus funds and its claim process. You are never required to hire ClearPath or any other finder service.",
  },
  {
    question: "What does the initial review cost?",
    answer:
      "Nothing. We review the information you provide and relevant public court records at no charge. If funds appear available, we explain the next steps and any contingency fee in a written agreement before you decide whether to proceed.",
  },
  {
    question: "Is ClearPath a law firm or government office?",
    answer:
      "No. ClearPath Surplus Solutions is a private finder service. We are not a law firm and are not affiliated with a court, lender, or government agency. We do not provide legal advice or represent you in court.",
  },
  {
    question: "What information should I send?",
    answer:
      "For the first review, we only need your name, a way to contact you, and the foreclosed property address. A court case number is helpful but optional. Never send a Social Security number, bank details, or identity documents through this form.",
  },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <div className="hero-texture" aria-hidden="true" />
        <div className="shell hero-grid">
          <div className="hero-copy">
            <p className="eyebrow light">Maryland foreclosure surplus recovery</p>
            <h1>A foreclosure may be over. <em>Your money may still be waiting.</em></h1>
            <p className="brand-promise">Reclaiming hidden funds with clarity and trust.</p>
            <p className="hero-lede">
              If a foreclosed home sold for more than the debts and costs, the remaining funds may belong to the former owner. We help you verify the record and understand the path forward.
            </p>
            <div className="hero-actions">
              <Link className="button button-gold" href="#check-my-case">
                Check my case <ArrowIcon />
              </Link>
              <Link className="text-link light-link" href="#how-it-works">See how it works</Link>
            </div>
            <ul className="hero-assurances" aria-label="Service assurances">
              <li><span>✓</span> Free initial record review</li>
              <li><span>✓</span> No upfront cost</li>
              <li><span>✓</span> No obligation</li>
            </ul>
          </div>

          <aside className="record-card" aria-label="Illustration of surplus funds calculation">
            <div className="record-card-top">
              <span>PUBLIC COURT RECORD</span>
              <span className="record-dot" />
            </div>
            <div className="property-sketch" aria-hidden="true">
              <svg viewBox="0 0 360 175">
                <path d="M29 142h301M62 142V72l118-51 118 51v70M93 142V88h174v54M150 142v-38h60v38M115 99h24v23h-24zM221 99h24v23h-24z" />
                <path className="accent" d="m267 40 31 32M62 72 180 21l118 51" />
              </svg>
            </div>
            <div className="calculation">
              <div><span>Foreclosure sale</span><strong>+</strong></div>
              <div><span>Debts &amp; court costs</span><strong>−</strong></div>
              <div className="surplus-line"><span>Possible surplus</span><strong>Yours?</strong></div>
            </div>
            <p>We start with the record—not a promise.</p>
          </aside>
        </div>
      </section>

      <section className="trust-strip" aria-label="About ClearPath">
        <div className="shell trust-grid">
          <p><strong>Maryland-focused</strong><span>Local court-record review</span></p>
          <p><strong>Plain-language process</strong><span>Every step explained first</span></p>
          <p><strong>Your choice</strong><span>You may claim directly with the court</span></p>
        </div>
      </section>

      <section className="section how-section" id="how-it-works">
        <div className="shell">
          <div className="section-heading centered">
            <p className="eyebrow">A clear path, one step at a time</p>
            <h2>Start with facts. Decide with confidence.</h2>
            <p>We make the process understandable before asking you to make any decision.</p>
          </div>
          <div className="steps-grid">
            <article className="step-card">
              <span className="step-number">01</span>
              <div className="step-icon"><SearchIcon /></div>
              <h3>We review the record</h3>
              <p>Share the property address. We check available Maryland court records for a potential surplus tied to the foreclosure.</p>
            </article>
            <article className="step-card featured">
              <span className="step-number">02</span>
              <div className="step-icon"><DocumentIcon /></div>
              <h3>We explain what we find</h3>
              <p>If the record indicates funds may be available, we walk through the source, possible amount, and ways you can proceed.</p>
            </article>
            <article className="step-card">
              <span className="step-number">03</span>
              <div className="step-icon"><HandshakeIcon /></div>
              <h3>You choose the next step</h3>
              <p>Claim directly through the court or ask us to help coordinate the process. Any fee is disclosed in writing first.</p>
            </article>
          </div>
        </div>
      </section>

      <section className="section evidence-section">
        <div className="shell evidence-grid">
          <div className="evidence-copy">
            <p className="eyebrow">Evidence, not pressure</p>
            <h2>You deserve to know what’s real before you act.</h2>
            <p>
              Unexpected letters and calls after a foreclosure can be hard to trust. That is why our first conversation centers on information you can independently verify.
            </p>
            <ul className="check-list">
              <li><span>✓</span><div><strong>A specific property and court case</strong><p>We connect the inquiry to a public record—not a vague claim.</p></div></li>
              <li><span>✓</span><div><strong>Clear written terms</strong><p>No work begins under a contingency arrangement until you review and sign the agreement.</p></div></li>
              <li><span>✓</span><div><strong>No sensitive data at intake</strong><p>We will not ask for bank details, payment, or a Social Security number through this website.</p></div></li>
            </ul>
          </div>
          <div className="notice-card">
            <p className="notice-kicker">Your right to verify</p>
            <blockquote>“You may contact the Circuit Court directly to ask about surplus funds and claim them yourself, without using our service.”</blockquote>
            <div className="notice-rule" />
            <p>ClearPath Surplus Solutions is a private finder service. It is not a law firm and is not affiliated with the courts, the State of Maryland, a lender, or a government agency.</p>
          </div>
        </div>
      </section>

      <section className="section faq-section" id="questions">
        <div className="shell faq-grid">
          <div className="faq-intro">
            <p className="eyebrow">Common questions</p>
            <h2>Straight answers, without the fine-print fog.</h2>
            <p>Still unsure? Request a review and ask us anything. Submitting the form does not create an agreement.</p>
            <Link className="text-link" href="#check-my-case">Request a review <span>→</span></Link>
          </div>
          <div className="accordion-list">
            {faqs.map((faq, index) => (
              <details key={faq.question} open={index === 0}>
                <summary>{faq.question}<span aria-hidden="true">+</span></summary>
                <p>{faq.answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      <section className="section intake-section" id="check-my-case">
        <div className="shell intake-grid">
          <div className="intake-copy">
            <p className="eyebrow light">Free initial review</p>
            <h2>Let’s find out what the record says.</h2>
            <p>Tell us where the foreclosure happened. We’ll review the available information and follow up about what we find.</p>
            <div className="privacy-promise">
              <span aria-hidden="true">⌁</span>
              <div><strong>We limit what we collect.</strong><p>We use your submission to evaluate and respond to your request. See our <Link href="/privacy">privacy policy</Link>.</p></div>
            </div>
            <div className="contact-expectation">
              <p className="mini-label">What happens next</p>
              <p>A member of the ClearPath team reviews your submission before contacting you. No automated promise of funds is made.</p>
            </div>
          </div>
          <div className="form-card">
            <div className="form-heading">
              <span>CONFIDENTIAL INTAKE</span>
              <p>Fields marked * are required.</p>
            </div>
            <IntakeForm />
          </div>
        </div>
      </section>

      <section className="disclosure-band">
        <div className="shell">
          <p><strong>Important disclosure:</strong> ClearPath Surplus Solutions is a private finder service, not a law firm, and does not offer legal representation or legal advice. We are not affiliated with any court, government agency, lender, or real estate company. Eligibility and fund amounts must be verified through official records. Results are not guaranteed.</p>
        </div>
      </section>
    </>
  );
}
