DROP VIEW latest_valid_observations;

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
ORDER BY
    indicator_id,
    (source_key <> 'development_fixture') DESC,
    source_as_of_date DESC,
    observation_date DESC,
    collected_at DESC;
