"""Fit, compare, serialize, and apply station-profile clustering models."""

import math
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from threadpoolctl import threadpool_limits

from ml_processor.features import FEATURE_NAMES


RANDOM_STATE = 6104
MODEL_FORMAT_VERSION = 2
MAX_CLUSTERS = 8
STABILITY_RUNS = 5
MIN_CLUSTER_PROFILES = 5


def train_model(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[int], dict[str, Any]]:
    """Train with a bounded BLAS/OpenMP pool to avoid container oversubscription."""
    with threadpool_limits(limits=1):
        return _train_model(rows)


def _train_model(
    rows: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[int], dict[str, Any]]:
    """Evaluate K-Means and Gaussian mixtures without claiming labelled accuracy."""
    matrix, transform = _prepare(rows)
    if len(matrix) < 3:
        raise ValueError("at least three station/day profiles are required for clustering")
    candidates = []
    upper = min(MAX_CLUSTERS, len(matrix) - 1)
    for algorithm in ("kmeans", "gaussian_mixture"):
        for clusters in range(2, upper + 1):
            estimator = _fit(algorithm, clusters, matrix, RANDOM_STATE)
            labels = estimator.predict(matrix) if algorithm == "gaussian_mixture" else estimator.labels_
            cluster_sizes = np.bincount(labels.astype(int), minlength=clusters)
            if (
                len(set(labels.tolist())) != clusters
                or int(cluster_sizes.min()) < MIN_CLUSTER_PROFILES
            ):
                continue
            silhouette = float(silhouette_score(matrix, labels))
            davies_bouldin = float(davies_bouldin_score(matrix, labels))
            stability = _stability(algorithm, clusters, matrix, labels)
            candidates.append({
                "algorithm": algorithm,
                "clusters": clusters,
                "silhouette": silhouette,
                "davies_bouldin": davies_bouldin,
                "stability_ari": stability,
                "minimum_cluster_share": int(cluster_sizes.min()) / len(matrix),
            })
    if not candidates:
        raise ValueError("no valid clustering candidate was produced from the profiles")

    rank_silhouette = _ranks(candidates, "silhouette", reverse=True)
    rank_davies = _ranks(candidates, "davies_bouldin", reverse=False)
    rank_stability = _ranks(candidates, "stability_ari", reverse=True)
    for index, candidate in enumerate(candidates):
        candidate["rank_sum"] = (
            rank_silhouette[index] + rank_davies[index] + rank_stability[index]
        )
    selected_index = min(
        range(len(candidates)),
        key=lambda index: (
            candidates[index]["rank_sum"],
            -candidates[index]["silhouette"],
            candidates[index]["davies_bouldin"],
            -candidates[index]["stability_ari"],
            candidates[index]["algorithm"],
            candidates[index]["clusters"],
        ),
    )
    selected = candidates[selected_index]
    fitted = _fit(
        selected["algorithm"], selected["clusters"], matrix, RANDOM_STATE
    )
    labels = fitted.predict(matrix) if selected["algorithm"] == "gaussian_mixture" else fitted.labels_
    artifact = {
        "format_version": MODEL_FORMAT_VERSION,
        "feature_names": transform["feature_names"],
        "imputation_medians": transform["imputation_medians"],
        "means": transform["means"],
        "scales": transform["scales"],
        "missing_indicator_indices": transform["missing_indicator_indices"],
        "algorithm": selected["algorithm"],
        "cluster_count": selected["clusters"],
        "random_state": RANDOM_STATE,
        "parameters": _serialize_estimator(fitted, selected["algorithm"]),
        "selection_rule": (
            "lowest sum of metric ranks: silhouette descending, Davies-Bouldin "
            "ascending, and five-run subsample adjusted-Rand stability descending"
        ),
    }
    return artifact, [int(label) for label in labels], {
        "selected": selected,
        "candidates": candidates,
        "profile_count": len(matrix),
        "excluded_empty_profiles": len(rows) - len(matrix),
        "feature_names": transform["feature_names"],
    }


def predict_labels(artifact: dict[str, Any], rows: list[dict[str, Any]]) -> list[int]:
    """Apply a serialized transform and clustering model to station/day rows."""
    matrix, _ = _prepare(rows, artifact)
    if artifact["algorithm"] == "kmeans":
        centers = np.asarray(artifact["parameters"]["cluster_centers"], dtype=float)
        distances = ((matrix[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        return [int(value) for value in distances.argmin(axis=1)]
    weights = np.asarray(artifact["parameters"]["weights"], dtype=float)
    means = np.asarray(artifact["parameters"]["means"], dtype=float)
    covariances = np.asarray(artifact["parameters"]["covariances"], dtype=float)
    log_probabilities = []
    dimensions = matrix.shape[1]
    for weight, mean, variance in zip(weights, means, covariances):
        log_determinant = np.log(variance).sum()
        delta = matrix - mean
        exponent = (delta ** 2 / variance).sum(axis=1)
        log_probabilities.append(
            np.log(weight)
            - 0.5 * (dimensions * math.log(2 * math.pi) + log_determinant + exponent)
        )
    return [int(value) for value in np.argmax(np.stack(log_probabilities, axis=1), axis=1)]


def _prepare(
    rows: list[dict[str, Any]], artifact: dict[str, Any] | None = None
) -> tuple[np.ndarray, dict[str, Any]]:
    feature_names = artifact["feature_names"] if artifact else list(FEATURE_NAMES)
    raw = np.full((len(rows), len(feature_names)), np.nan, dtype=float)
    for row_index, row in enumerate(rows):
        values = row["features"]
        for column_index, name in enumerate(feature_names):
            value = values.get(name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric = float(value)
                if math.isfinite(numeric):
                    raw[row_index, column_index] = numeric
    if artifact:
        medians = np.asarray(artifact["imputation_medians"], dtype=float)
        means = np.asarray(artifact["means"], dtype=float)
        scales = np.asarray(artifact["scales"], dtype=float)
        missing_indices = artifact["missing_indicator_indices"]
    else:
        useful = np.isfinite(raw).any(axis=0)
        raw = raw[:, useful]
        feature_names = [name for name, keep in zip(feature_names, useful) if keep]
        if not feature_names:
            raise ValueError("no observed numeric station/day features are available")
        medians = np.nanmedian(raw, axis=0)
        missing_indices = [
            index for index in range(raw.shape[1])
            if np.isnan(raw[:, index]).any()
        ]
        filled = np.where(np.isnan(raw), medians, raw)
        means = filled.mean(axis=0)
        scales = filled.std(axis=0)
        scales[scales == 0] = 1.0
    missing = np.isnan(raw)
    filled = np.where(missing, medians, raw)
    standardized = (filled - means) / scales
    if missing_indices:
        standardized = np.concatenate(
            (standardized, missing[:, missing_indices].astype(float)), axis=1
        )
    matrix = standardized
    nonempty = np.isfinite(matrix).any(axis=1)
    matrix = matrix[nonempty]
    if len(matrix) != len(rows):
        raise ValueError("a prediction profile contains no usable numeric features")
    return matrix, {
        "feature_names": feature_names,
        "imputation_medians": medians.tolist(),
        "means": means.tolist(),
        "scales": scales.tolist(),
        "missing_indicator_indices": missing_indices,
    }


def _fit(algorithm: str, clusters: int, matrix: np.ndarray, seed: int):
    if algorithm == "kmeans":
        return KMeans(n_clusters=clusters, n_init=5, random_state=seed).fit(matrix)
    return GaussianMixture(
        n_components=clusters,
        covariance_type="diag",
        reg_covar=1e-5,
        n_init=1,
        random_state=seed,
    ).fit(matrix)


def _stability(
    algorithm: str, clusters: int, matrix: np.ndarray, baseline_labels: np.ndarray
) -> float:
    rng = np.random.default_rng(RANDOM_STATE)
    scores = []
    sample_size = max(clusters + 1, int(math.ceil(len(matrix) * 0.8)))
    for run in range(STABILITY_RUNS):
        indices = np.sort(rng.choice(len(matrix), size=sample_size, replace=False))
        estimator = _fit(algorithm, clusters, matrix[indices], RANDOM_STATE + run + 1)
        labels = estimator.predict(matrix)
        scores.append(adjusted_rand_score(baseline_labels, labels))
    return float(np.mean(scores))


def _ranks(
    candidates: list[dict[str, Any]], metric: str, reverse: bool
) -> dict[int, int]:
    ordered = sorted(
        range(len(candidates)),
        key=lambda index: (
            -candidates[index][metric] if reverse else candidates[index][metric],
            candidates[index]["algorithm"],
            candidates[index]["clusters"],
        ),
    )
    return {index: rank + 1 for rank, index in enumerate(ordered)}


def _serialize_estimator(estimator: Any, algorithm: str) -> dict[str, Any]:
    if algorithm == "kmeans":
        return {"cluster_centers": estimator.cluster_centers_.tolist()}
    return {
        "weights": estimator.weights_.tolist(),
        "means": estimator.means_.tolist(),
        "covariances": estimator.covariances_.tolist(),
    }
