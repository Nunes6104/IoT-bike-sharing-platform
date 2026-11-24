CREATE TABLE IF NOT EXISTS rejected_messages (
    source VARCHAR(32) NOT NULL,
    topic VARCHAR(512) NOT NULL DEFAULT '',
    payload_hash CHAR(64) NOT NULL,
    raw_payload_base64 LONGTEXT NOT NULL,
    issues JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source, topic, payload_hash),
    INDEX idx_rejected_message_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE UNIQUE INDEX uq_event_conflict_seq_new_hash
    ON event_conflicts (seq, new_hash);
