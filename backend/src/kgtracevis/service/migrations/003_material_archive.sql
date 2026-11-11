-- Preserve material identity, files, and extraction history. Existing rows remain active.
ALTER TABLE source_materials ADD COLUMN IF NOT EXISTS archived_at timestamptz;
