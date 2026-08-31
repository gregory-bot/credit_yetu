"""Shadow-scoring inference: read-only, additive, never authoritative.

Loads whichever ``MLModelVersion`` currently has ``status == "shadow"`` (if
any) and scores a statement's already-computed financial summary against it.
The result is always returned as a clearly-labelled side channel — see
``app/api/v1/statements.py`` and ``app/api/v1/transactions.py`` — and is
never used to compute ``credit_score``, ``grade`` or the loan limit.
"""
from __future__ import annotations

import logging

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MLModelVersion
from app.services.ml.features import extract_features, to_vector

logger = logging.getLogger("ml.shadow")


def shadow_predict(db: Session, summary: dict, fraud_data: dict | None, avg_monthly_income: float) -> dict:
    row = db.scalar(select(MLModelVersion).where(MLModelVersion.status == "shadow"))
    if row is None:
        return {
            "status": "not_available",
            "reason": "No shadow model has been activated yet (not enough labeled loan outcomes). "
                      "Record outcomes via POST /api/v1/ml/outcomes/{reference_id}, "
                      "then POST /api/v1/ml/train.",
        }

    try:
        artifact = joblib.load(row.artifact_path)
    except Exception as exc:  # noqa: BLE001 - shadow scoring must never break the real score
        logger.warning("Could not load shadow model artifact %s: %s", row.artifact_path, exc)
        return {"status": "error", "reason": f"Could not load model artifact: {exc}"}

    feats = extract_features(summary, fraud_data, avg_monthly_income)
    vector = to_vector(feats)
    model = artifact["model"]
    scaler = artifact.get("scaler")
    X = scaler.transform([vector]) if scaler is not None else [vector]
    probability_bad = float(model.predict_proba(X)[0][1])

    return {
        "status": "shadow",
        "model_version": row.version,
        "algorithm": row.algorithm,
        "probability_of_default": round(probability_bad, 4),
        "predicted_label": "bad" if probability_bad >= 0.5 else "good",
        "trained_on_samples": row.n_samples,
        "test_metrics": row.metrics,
        "features_used": feats,
        "note": "Shadow prediction for monitoring/calibration only. It does not affect credit_score, "
                "grade or the loan limit above — the rule engine remains authoritative.",
    }
