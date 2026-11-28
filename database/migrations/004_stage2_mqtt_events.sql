-- Version 4: isolate Stage 2 MQTT deliveries from the immutable Stage 1 baseline.
CREATE TABLE IF NOT EXISTS online_events (
    seq BIGINT NOT NULL PRIMARY KEY COMMENT 'Stage 2 event sequence from MQTT',
    type ENUM('station_status', 'trip_started', 'trip_ended') NOT NULL,
    ts_utc DATETIME NOT NULL COMMENT 'Timestamp converted to UTC from source -04:00',
    payload LONGTEXT NOT NULL COMMENT 'Raw MQTT event payload',
    validation_status ENUM('valid', 'warning', 'rejected') NOT NULL DEFAULT 'valid',
    validation_reason TEXT,
    source_line_number BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_online_events_type (type),
    INDEX idx_online_events_ts_utc (ts_utc),
    INDEX idx_online_events_validation (validation_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE OR REPLACE VIEW event_summary AS
SELECT
    type,
    validation_status,
    COUNT(*) AS count,
    MIN(ts_utc) AS earliest_utc,
    MAX(ts_utc) AS latest_utc
FROM (
    SELECT type, validation_status, ts_utc
    FROM events
    WHERE seq < 53725
    UNION ALL
    SELECT type, validation_status, ts_utc
    FROM online_events
) AS current_events
GROUP BY type, validation_status;
