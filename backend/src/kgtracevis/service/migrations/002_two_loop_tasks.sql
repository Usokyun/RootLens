-- Additive two-loop task/runtime storage. Does not alter existing run or KG data.
CREATE TABLE IF NOT EXISTS rootlens_tasks (
    task_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS rootlens_analyses (
    run_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
