-- Bike-sharing IoT platform: versioned MySQL schema
-- Base schema version: 1 (online ingestion additions are in migrations/).
-- Created: 2024-11-20
-- Storage convention: all timestamps in UTC (zero-offset); original source offset preserved in raw payloads.

-- Enable UTF-8 for JSON storage
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version INT PRIMARY KEY NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Check if already applied
SELECT IF(
    EXISTS(SELECT 1 FROM schema_versions WHERE version = 1),
    'Schema version 1 already applied',
    'Applying schema version 1'
) AS status;

INSERT IGNORE INTO schema_versions (version, description)
VALUES (1, 'Initial schema: stations, events, quarantine');

-- Station reference data (83 Jersey City and Hoboken stations)
-- Primary key is the natural station_id from the GBFS feed
CREATE TABLE IF NOT EXISTS stations (
    station_id VARCHAR(32) NOT NULL PRIMARY KEY,
    payload LONGTEXT NOT NULL COMMENT 'Raw JSON from stations.json (complete record)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Events (station status updates and trip records)
-- Primary key is the event sequence number from the JSONL files
-- Sequence is globally unique and monotonically increasing across stage1 and stage2.
CREATE TABLE IF NOT EXISTS events (
    seq BIGINT NOT NULL PRIMARY KEY COMMENT 'Event sequence: unique across all stages, 1-73580',
    type ENUM('station_status', 'trip_started', 'trip_ended') NOT NULL,
    ts_utc DATETIME NOT NULL COMMENT 'Timestamp converted to UTC (from source -04:00)',
    payload LONGTEXT NOT NULL COMMENT 'Raw JSON from JSONL file (complete record with original -04:00 offset)',
    validation_status ENUM('valid', 'warning', 'rejected') NOT NULL DEFAULT 'valid',
    validation_reason TEXT COMMENT 'JSON array of issue objects: {severity, field, message}',
    source_line_number BIGINT COMMENT 'Line number in source JSONL file (1-indexed)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_ts_utc (ts_utc),
    INDEX idx_validation (validation_status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Rejected records (malformed JSON or hard validation errors)
-- Quarantined separately to preserve source lines and provenance
-- Key is (source_path, line_number) to prevent re-quarantining the same error
CREATE TABLE IF NOT EXISTS rejected_lines (
    source_path VARCHAR(512) NOT NULL COMMENT 'File path as provided to loader',
    line_number BIGINT NOT NULL COMMENT 'Line number in source file (1-indexed)',
    raw_text LONGTEXT NOT NULL COMMENT 'Exact original line from file',
    issues JSON NOT NULL COMMENT 'Array of validation issues: [{severity, field, message}]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_path, line_number),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Conflict log (key collision detection for idempotent imports)
-- Migration 002 adds a unique key so redelivery is auditable only once.
CREATE TABLE IF NOT EXISTS event_conflicts (
    seq BIGINT NOT NULL,
    old_hash VARCHAR(64) COMMENT 'SHA-256 of previous payload',
    new_hash VARCHAR(64) COMMENT 'SHA-256 of incoming payload',
    old_payload LONGTEXT COMMENT 'Previous JSON',
    new_payload LONGTEXT COMMENT 'Incoming JSON',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_seq (seq),
    INDEX idx_detected (detected_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Summary views (optional, for auditing)
CREATE OR REPLACE VIEW event_summary AS
SELECT
    type,
    validation_status,
    COUNT(*) as count,
    MIN(ts_utc) as earliest_utc,
    MAX(ts_utc) as latest_utc
FROM events
GROUP BY type, validation_status;

-- Ensure database uses UTC for all session operations
SET SESSION time_zone='+00:00';
