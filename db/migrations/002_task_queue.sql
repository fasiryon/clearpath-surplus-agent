-- ============================================================
-- Migration 002: Agent task queue + run tracking
-- Run AFTER 001 (schema.sql) — depends on no prior tables.
-- ============================================================

-- ============================================================
-- TABLE: agent_tasks
-- Central task queue. Workers atomically claim rows via
-- the claim_task() function below.
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_tasks (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    task_type       TEXT NOT NULL
                    CHECK (task_type IN (
                        'scrape', 'docket_analysis', 'skip_trace', 'outreach'
                    )),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'done', 'failed')),
    payload         JSONB NOT NULL DEFAULT '{}',
    priority        INT NOT NULL DEFAULT 5,
    state           TEXT,
    county          TEXT,
    worker_id       TEXT,
    task_key        TEXT UNIQUE,         -- idempotency key: seed with ON CONFLICT DO NOTHING
    claimed_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    result_payload  JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Fast claim lookup: task_type + status + priority + age
CREATE INDEX IF NOT EXISTS idx_tasks_claim
    ON agent_tasks (task_type, status, priority DESC, created_at ASC);

-- Lookup by county/state for monitoring
CREATE INDEX IF NOT EXISTS idx_tasks_county
    ON agent_tasks (state, county, task_type);

-- ============================================================
-- TABLE: agent_runs
-- One row per agent invocation for cost/performance tracking.
-- tokens_used is populated by docket_agent (Claude Haiku calls).
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_runs (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_type      TEXT NOT NULL,
    worker_id       TEXT,
    task_id         UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    cases_found     INT DEFAULT 0,
    tasks_seeded    INT DEFAULT 0,
    tokens_used     INT DEFAULT 0,       -- Claude Haiku token count
    error_count     INT DEFAULT 0,
    status          TEXT DEFAULT 'running'
                    CHECK (status IN ('running', 'done', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_runs_agent
    ON agent_runs (agent_type, started_at DESC);

-- ============================================================
-- FUNCTION: claim_task(p_task_type, p_worker_id)
-- Atomically claims one task using FOR UPDATE SKIP LOCKED.
-- Safe for concurrent workers — no double-claims possible.
-- Returns the claimed row as a result set.
-- ============================================================
CREATE OR REPLACE FUNCTION claim_task(
    p_task_type  TEXT,
    p_worker_id  TEXT
)
RETURNS SETOF agent_tasks
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    UPDATE agent_tasks
    SET
        status     = 'running',
        claimed_at = NOW(),
        worker_id  = p_worker_id
    WHERE id = (
        SELECT id
        FROM   agent_tasks
        WHERE  task_type = p_task_type
          AND  status    = 'pending'
        ORDER BY priority DESC, created_at ASC
        LIMIT  1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
END;
$$;

-- ============================================================
-- FUNCTION: complete_task(p_task_id, p_result)
-- Marks a task done and stores its result payload.
-- ============================================================
CREATE OR REPLACE FUNCTION complete_task(
    p_task_id UUID,
    p_result  JSONB
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE agent_tasks
    SET
        status         = 'done',
        completed_at   = NOW(),
        result_payload = p_result
    WHERE id = p_task_id;
END;
$$;

-- ============================================================
-- FUNCTION: fail_task(p_task_id, p_error)
-- Marks a task failed and stores the error string.
-- ============================================================
CREATE OR REPLACE FUNCTION fail_task(
    p_task_id UUID,
    p_error   TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    UPDATE agent_tasks
    SET
        status        = 'failed',
        completed_at  = NOW(),
        error_message = p_error
    WHERE id = p_task_id;
END;
$$;

-- ============================================================
-- RLS: task queue tables
-- ============================================================
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_tasks"
    ON agent_tasks FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "service_role_all_runs"
    ON agent_runs FOR ALL
    TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "authenticated_read_tasks"
    ON agent_tasks FOR SELECT
    TO authenticated USING (TRUE);

CREATE POLICY "authenticated_read_runs"
    ON agent_runs FOR SELECT
    TO authenticated USING (TRUE);

-- ============================================================
-- VIEW: task_queue_summary
-- Operational dashboard: pending tasks by type + county.
-- ============================================================
CREATE OR REPLACE VIEW task_queue_summary AS
SELECT
    task_type,
    status,
    state,
    county,
    COUNT(*)                            AS task_count,
    MIN(created_at)                     AS oldest_task,
    MAX(created_at)                     AS newest_task,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_count
FROM agent_tasks
GROUP BY task_type, status, state, county
ORDER BY task_type, status;
