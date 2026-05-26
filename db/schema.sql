-- ============================================================
-- ClearPath Surplus Agent — Supabase / PostgreSQL Schema
-- Run this in Supabase SQL Editor to initialize the database.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for fuzzy name search

-- ============================================================
-- ENUMS (as CHECK constraints for Supabase compatibility)
-- ============================================================

-- ============================================================
-- TABLE: surplus_cases
-- One row per unique court case where surplus may exist.
-- ============================================================
CREATE TABLE IF NOT EXISTS surplus_cases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_number         TEXT NOT NULL UNIQUE,
    county              TEXT NOT NULL,
    property_address    TEXT,
    defendant_name      TEXT,           -- original homeowner
    plaintiff_name      TEXT,           -- bank / lender
    filing_date         DATE,
    sale_date           DATE,
    surplus_amount      DECIMAL(12, 2),
    status              TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN (
                            'new',
                            'skip_traced',
                            'outreach_pending',
                            'outreach_sent',
                            'agreement_signed',
                            'claim_filed',
                            'funds_received',
                            'closed_no_contact',
                            'closed_declined',
                            'closed_no_surplus'
                        )),
    scrape_source       TEXT DEFAULT 'mjcs',
    raw_docket          JSONB DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- TABLE: surplus_contacts
-- Owner contact info discovered via skip trace.
-- One row per case (one contact attempt per case at a time).
-- ============================================================
CREATE TABLE IF NOT EXISTS surplus_contacts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id             UUID NOT NULL REFERENCES surplus_cases(id) ON DELETE CASCADE,
    owner_name          TEXT NOT NULL,
    phone               TEXT,
    email               TEXT,
    last_known_address  TEXT,           -- property address at time of foreclosure
    current_address     TEXT,           -- found via skip trace
    skip_trace_source   TEXT,
    skip_trace_date     TIMESTAMPTZ DEFAULT NOW(),
    outreach_status     TEXT NOT NULL DEFAULT 'pending'
                        CHECK (outreach_status IN (
                            'pending',
                            'mail_sent',
                            'sms_sent',
                            'email_sent',
                            'responded',
                            'do_not_contact'
                        )),
    hubspot_contact_id  TEXT,
    signed_agreement    BOOLEAN DEFAULT FALSE,
    agreement_date      DATE,
    fee_percentage      DECIMAL(5, 2) DEFAULT 40.00,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_case_contact UNIQUE (case_id)
);

-- ============================================================
-- TABLE: outreach_log
-- Immutable record of every outreach attempt (mail, sms, email).
-- ============================================================
CREATE TABLE IF NOT EXISTS outreach_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    contact_id          UUID NOT NULL REFERENCES surplus_contacts(id) ON DELETE CASCADE,
    channel             TEXT NOT NULL
                        CHECK (channel IN ('mail', 'sms', 'email', 'phone', 'zapier_webhook')),
    template_used       TEXT,
    sent_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    response_received   BOOLEAN DEFAULT FALSE,
    response_at         TIMESTAMPTZ,
    notes               TEXT
);

-- ============================================================
-- VIEW: pipeline_summary
-- Real-time pipeline health — group by status + county.
-- ============================================================
CREATE OR REPLACE VIEW pipeline_summary AS
SELECT
    sc.status,
    sc.county,
    COUNT(*)                                            AS case_count,
    SUM(sc.surplus_amount)                             AS total_surplus,
    AVG(sc.surplus_amount)                             AS avg_surplus,
    SUM(sc.surplus_amount * COALESCE(ct.fee_percentage, 40.0) / 100.0)
                                                        AS projected_revenue
FROM surplus_cases sc
LEFT JOIN surplus_contacts ct ON ct.case_id = sc.id
WHERE sc.surplus_amount IS NOT NULL
GROUP BY sc.status, sc.county
ORDER BY total_surplus DESC NULLS LAST;

-- ============================================================
-- VIEW: active_pipeline
-- Cases currently being worked (not closed).
-- ============================================================
CREATE OR REPLACE VIEW active_pipeline AS
SELECT
    sc.case_number,
    sc.county,
    sc.property_address,
    sc.defendant_name,
    sc.surplus_amount,
    sc.status AS case_status,
    ct.owner_name,
    ct.phone,
    ct.email,
    ct.outreach_status,
    ct.hubspot_contact_id,
    ct.signed_agreement,
    ct.fee_percentage,
    ROUND(sc.surplus_amount * ct.fee_percentage / 100.0, 2) AS projected_fee,
    sc.created_at,
    sc.updated_at
FROM surplus_cases sc
LEFT JOIN surplus_contacts ct ON ct.case_id = sc.id
WHERE sc.status NOT IN ('closed_no_contact', 'closed_declined', 'closed_no_surplus')
ORDER BY sc.surplus_amount DESC NULLS LAST;

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_cases_status      ON surplus_cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_county      ON surplus_cases(county);
CREATE INDEX IF NOT EXISTS idx_cases_surplus     ON surplus_cases(surplus_amount);
CREATE INDEX IF NOT EXISTS idx_cases_filing_date ON surplus_cases(filing_date);
CREATE INDEX IF NOT EXISTS idx_contacts_status   ON surplus_contacts(outreach_status);
CREATE INDEX IF NOT EXISTS idx_contacts_case     ON surplus_contacts(case_id);
CREATE INDEX IF NOT EXISTS idx_log_contact       ON outreach_log(contact_id);
CREATE INDEX IF NOT EXISTS idx_log_sent_at       ON outreach_log(sent_at);

-- Trigram index for fuzzy name matching
CREATE INDEX IF NOT EXISTS idx_cases_defendant_trgm
    ON surplus_cases USING GIN (defendant_name gin_trgm_ops);

-- ============================================================
-- TRIGGER: auto-update updated_at on row modification
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_cases_updated_at
    BEFORE UPDATE ON surplus_cases
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_contacts_updated_at
    BEFORE UPDATE ON surplus_contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Only authenticated users (your service role) can read/write.
-- ============================================================
ALTER TABLE surplus_cases     ENABLE ROW LEVEL SECURITY;
ALTER TABLE surplus_contacts  ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_log      ENABLE ROW LEVEL SECURITY;

-- Allow service role (your backend) full access
CREATE POLICY "service_role_all_cases"
    ON surplus_cases FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "service_role_all_contacts"
    ON surplus_contacts FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "service_role_all_log"
    ON outreach_log FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Authenticated users can read (for dashboard/reporting)
CREATE POLICY "authenticated_read_cases"
    ON surplus_cases FOR SELECT
    TO authenticated USING (TRUE);

CREATE POLICY "authenticated_read_contacts"
    ON surplus_contacts FOR SELECT
    TO authenticated USING (TRUE);

CREATE POLICY "authenticated_read_log"
    ON outreach_log FOR SELECT
    TO authenticated USING (TRUE);
