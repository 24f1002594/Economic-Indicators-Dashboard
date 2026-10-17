CREATE TABLE indicator_sources (
    indicator_id VARCHAR(100) PRIMARY KEY REFERENCES indicators(id) ON DELETE CASCADE,
    source_key VARCHAR(100) NOT NULL REFERENCES source_metadata(source_key) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX indicator_sources_source_idx ON indicator_sources (source_key);
