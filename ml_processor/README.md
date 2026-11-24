# ML Processor

This folder is reserved for the dedicated unsupervised station-profiling service described in the project architecture. Model training, feature engineering, clustering, persistence, and anomaly detection have **not** been implemented.

In the current Compose configuration, `ml-processor` runs `infrastructure/placeholder.py`; it does not subscribe to MQTT, query the database, or produce cluster assignments. The service remains separate so future ML work does not merge into the event processor.

Candidate offline features and the Stage 2 clustering goals are described in the approved milestone plan at [planing/milestone-4-plan.md](../planing/milestone-4-plan.md) and the project brief. No model results or operational recommendations should be inferred from the current placeholder.
