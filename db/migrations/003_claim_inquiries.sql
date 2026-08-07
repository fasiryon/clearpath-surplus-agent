-- Migration 003: Customer website intake
-- Run in the Supabase SQL Editor before enabling the web form.

CREATE TABLE IF NOT EXISTS claim_inquiries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           TEXT NOT NULL,
    phone               TEXT,
    email               TEXT,
    contact_preference  TEXT NOT NULL DEFAULT 'phone'
                        CHECK (contact_preference IN ('phone', 'text', 'email')),
    property_address    TEXT NOT NULL,
    county              TEXT,
    case_number         TEXT,
    notes               TEXT,
    consent_to_contact  BOOLEAN NOT NULL DEFAULT FALSE,
    source              TEXT NOT NULL DEFAULT 'website',
    page_url            TEXT,
    user_agent          TEXT,
    status              TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN (
                            'new', 'reviewing', 'qualified', 'not_found',
                            'contacted', 'converted', 'closed'
                        )),
    assigned_to         TEXT,
    internal_notes      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT inquiry_has_contact CHECK (phone IS NOT NULL OR email IS NOT NULL),
    CONSTRAINT inquiry_consent_required CHECK (consent_to_contact = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_inquiries_status_created
    ON claim_inquiries (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_inquiries_property
    ON claim_inquiries USING GIN (property_address gin_trgm_ops);

CREATE OR REPLACE TRIGGER trg_inquiries_updated_at
    BEFORE UPDATE ON claim_inquiries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE claim_inquiries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_inquiries"
    ON claim_inquiries FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "authenticated_read_inquiries"
    ON claim_inquiries FOR SELECT
    TO authenticated USING (TRUE);

COMMENT ON TABLE claim_inquiries IS
    'Lead intake from the public ClearPath website. Never store SSNs, bank details, or identity documents here.';
