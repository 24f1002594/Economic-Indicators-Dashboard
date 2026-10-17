CREATE TABLE users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email VARCHAR(320) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE indicators (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100) NOT NULL,
    unit VARCHAR(64) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE source_metadata (
    source_key VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    source_url TEXT NOT NULL,
    refresh_interval_minutes INTEGER NOT NULL CHECK (refresh_interval_minutes >= 5),
    limitation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE observations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    indicator_id VARCHAR(100) NOT NULL REFERENCES indicators(id),
    source_key VARCHAR(100) NOT NULL REFERENCES source_metadata(source_key),
    period_label VARCHAR(100) NOT NULL,
    observation_date DATE NOT NULL,
    source_as_of_date DATE NOT NULL,
    value NUMERIC(20, 6) NOT NULL,
    unit VARCHAR(64) NOT NULL,
    comparison_value NUMERIC(20, 6),
    comparison_period_label VARCHAR(100),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    validation_notes TEXT,
    raw_payload JSONB,
    UNIQUE (indicator_id, source_key, period_label, source_as_of_date)
);

CREATE INDEX observations_indicator_date_idx
    ON observations (indicator_id, observation_date DESC);

CREATE INDEX observations_source_collected_idx
    ON observations (source_key, collected_at DESC);

CREATE TABLE collection_runs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_key VARCHAR(100) NOT NULL REFERENCES source_metadata(source_key),
    status VARCHAR(32) NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    records_received INTEGER NOT NULL DEFAULT 0 CHECK (records_received >= 0),
    records_stored INTEGER NOT NULL DEFAULT 0 CHECK (records_stored >= 0),
    error_message TEXT,
    details JSONB
);

CREATE INDEX collection_runs_source_started_idx
    ON collection_runs (source_key, started_at DESC);

CREATE TABLE refresh_status (
    source_key VARCHAR(100) PRIMARY KEY REFERENCES source_metadata(source_key),
    status VARCHAR(32) NOT NULL CHECK (status IN ('fresh', 'stale', 'unavailable')),
    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    stale_after_at TIMESTAMPTZ,
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIEW latest_valid_observations AS
SELECT DISTINCT ON (indicator_id)
    id,
    indicator_id,
    source_key,
    period_label,
    observation_date,
    source_as_of_date,
    value,
    unit,
    comparison_value,
    comparison_period_label,
    collected_at,
    validation_notes
FROM observations
WHERE is_valid = TRUE
ORDER BY indicator_id, source_as_of_date DESC, collected_at DESC;
