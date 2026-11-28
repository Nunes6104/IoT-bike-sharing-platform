-- Version 3: persisted, versioned station/day clustering output.
CREATE TABLE IF NOT EXISTS ml_models (
    model_id CHAR(64) NOT NULL PRIMARY KEY,
    training_start DATE NOT NULL,
    training_end DATE NOT NULL,
    algorithm VARCHAR(32) NOT NULL,
    cluster_count SMALLINT UNSIGNED NOT NULL,
    feature_names LONGTEXT NOT NULL,
    artifact LONGTEXT NOT NULL,
    metrics LONGTEXT NOT NULL,
    active TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ml_models_active (active, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ml_profiles (
    model_id CHAR(64) NOT NULL,
    station_id VARCHAR(32) NOT NULL,
    window_start DATE NOT NULL,
    window_end DATE NOT NULL,
    city VARCHAR(64) NOT NULL,
    capacity SMALLINT UNSIGNED NOT NULL,
    cluster_id SMALLINT UNSIGNED NOT NULL,
    features LONGTEXT NOT NULL,
    flags LONGTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (model_id, station_id, window_start),
    INDEX idx_ml_profiles_window (window_start, window_end),
    INDEX idx_ml_profiles_cluster (model_id, window_start, cluster_id),
    CONSTRAINT fk_ml_profiles_model
        FOREIGN KEY (model_id) REFERENCES ml_models(model_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
