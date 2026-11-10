-- Additive migration. Does not initialize, clear, or reimport any existing data.
CREATE TABLE IF NOT EXISTS working_graphs (
    graph_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
