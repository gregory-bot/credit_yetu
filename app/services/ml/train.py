"""Train and evaluate the ML shadow-scoring model on real loan outcomes.

Refuses to activate anything below ``settings.ml_min_samples`` labeled, final
outcomes, or when the rarer class has fewer than ``_MIN_MINORITY_CLASS``
examples — reporting an F1/accuracy computed on a handful of examples, or on
a test split missing a class entirely, would be exactly the fabricated
confidence this project exists to avoid. See README > "ML shadow-scoring".

Two models are always trained and compared honestly on the same held-out
test split:

  * ``logistic_regression``      — standardized features, interpretable
    coefficients, the credit-scoring industry's usual regulatory baseline.
  * ``hist_gradient_boosting``   — scikit-learn's boosted-tree classifier
    (no extra native dependency, handles nonlinearity/interactions natively).

Whichever wins on the test split (ROC-AUC, falling back to F1 when a class is
missing from the test set) is persisted as the active shadow model; the other
is kept alongside it as ``baseline_metrics`` for transparency.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoanOutcome, MLModelVersion, Score, Statement
from app.services.ml.features import FEATURE_NAMES, extract_features, to_vector

logger = logging.getLogger("ml.train")

# Final (non-"current") outcomes only — labels the training pipeline may use.
_FINAL_OUTCOMES = {"repaid": 0, "delinquent": 1, "defaulted": 1}
_MIN_MINORITY_CLASS = 8  # smallest acceptable count for the rarer label across the whole dataset


@dataclass
class TrainingReport:
    status: str                     # "activated" | "trained_insufficient"
    version: str
    reason: str | None = None
    n_samples: int = 0
    n_train: int = 0
    n_test: int = 0
    n_positive: int = 0
    n_negative: int = 0
    metrics: dict = field(default_factory=dict)
    baseline_metrics: dict = field(default_factory=dict)
    artifact_path: str | None = None


def _dataset(db: Session) -> tuple[list[list[float]], list[int]]:
    """Feature matrix + labels for every statement with a Score AND a final LoanOutcome."""
    rows = db.execute(
        select(Statement, Score, LoanOutcome)
        .join(Score, Score.statement_id == Statement.id)
        .join(LoanOutcome, LoanOutcome.statement_id == Statement.id)
        .where(LoanOutcome.outcome.in_(_FINAL_OUTCOMES.keys()))
    ).all()

    X: list[list[float]] = []
    y: list[int] = []
    for _stmt, score, outcome in rows:
        if not score.financial_summary:
            continue
        feats = extract_features(score.financial_summary, score.fraud_data, score.avg_monthly_income or 0.0)
        X.append(to_vector(feats))
        y.append(_FINAL_OUTCOMES[outcome.outcome])
    return X, y


def _ks_statistic(y_true, y_score) -> float:
    fpr, tpr, _ = roc_curve(y_true, y_score)
    return round(float(np.max(tpr - fpr)), 4)


def _evaluate(model, X_test, y_test) -> dict:
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }
    if len(set(y_test)) > 1:
        metrics["roc_auc"] = round(roc_auc_score(y_test, y_prob), 4)
        metrics["ks_statistic"] = _ks_statistic(y_test, y_prob)
    else:
        metrics["roc_auc"] = None
        metrics["ks_statistic"] = None
        metrics["warning"] = "Test split contains only one class; AUC/KS are undefined, not reported as 0."
    return metrics


def _persist_version(
    db: Session, version: str, algorithm: str, status: str,
    n_samples: int, n_train: int, n_test: int, n_positive: int, n_negative: int,
    metrics: dict, baseline_metrics: dict | None, artifact_path: str, trained_by: str | None,
) -> None:
    if status == "shadow":
        db.query(MLModelVersion).filter(MLModelVersion.status == "shadow").update({"status": "retired"})
    db.add(MLModelVersion(
        version=version, algorithm=algorithm, status=status,
        n_samples=n_samples, n_train=n_train, n_test=n_test,
        n_positive=n_positive, n_negative=n_negative,
        feature_names=FEATURE_NAMES, metrics=metrics, baseline_metrics=baseline_metrics or None,
        artifact_path=artifact_path or "", trained_by=trained_by,
    ))
    db.commit()


def train_and_evaluate(db: Session, trained_by: str | None = None) -> TrainingReport:
    X, y = _dataset(db)
    n_samples = len(y)
    n_positive = sum(y)
    n_negative = n_samples - n_positive
    # Microseconds + a short random suffix: two training calls in the same
    # second (e.g. a retry, or a rapid retrain) must never collide on the
    # unique `version` constraint.
    version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-{uuid.uuid4().hex[:6]}"

    if n_samples < settings.ml_min_samples or min(n_positive, n_negative) < _MIN_MINORITY_CLASS:
        reason = (
            f"Need >= {settings.ml_min_samples} labeled final outcomes with >= {_MIN_MINORITY_CLASS} "
            f"in the rarer class; have {n_samples} total ({n_positive} bad / {n_negative} good). "
            "Record more via POST /api/v1/ml/outcomes/{reference_id}."
        )
        _persist_version(db, version, "none", "trained_insufficient",
                          n_samples, 0, 0, n_positive, n_negative, {}, {}, "", trained_by)
        logger.info("Training skipped (%s): %s", version, reason)
        return TrainingReport(status="trained_insufficient", version=version, reason=reason,
                               n_samples=n_samples, n_positive=n_positive, n_negative=n_negative)

    X_arr, y_arr = np.array(X), np.array(y)
    X_train, X_test, y_train, y_test = train_test_split(
        X_arr, y_arr, test_size=settings.ml_test_size, random_state=settings.ml_random_state, stratify=y_arr,
    )

    # Interpretable baseline — the credit-scoring industry's usual regulatory default.
    scaler = StandardScaler().fit(X_train)
    logreg = LogisticRegression(max_iter=1000, class_weight="balanced")
    logreg.fit(scaler.transform(X_train), y_train)
    logreg_metrics = _evaluate(logreg, scaler.transform(X_test), y_test)

    # Boosted-tree candidate — usually stronger, still fully evaluated on the same split.
    hgb = HistGradientBoostingClassifier(random_state=settings.ml_random_state, class_weight="balanced")
    hgb.fit(X_train, y_train)
    hgb_metrics = _evaluate(hgb, X_test, y_test)

    hgb_score = hgb_metrics.get("roc_auc") if hgb_metrics.get("roc_auc") is not None else hgb_metrics["f1"]
    logreg_score = logreg_metrics.get("roc_auc") if logreg_metrics.get("roc_auc") is not None else logreg_metrics["f1"]

    if logreg_score > hgb_score:
        primary_name, primary_model, primary_scaler = "logistic_regression", logreg, scaler
        metrics, baseline_metrics = logreg_metrics, hgb_metrics
        baseline_metrics["algorithm"] = "hist_gradient_boosting"
    else:
        primary_name, primary_model, primary_scaler = "hist_gradient_boosting", hgb, None
        metrics, baseline_metrics = hgb_metrics, logreg_metrics
        baseline_metrics["algorithm"] = "logistic_regression"

    artifact_path = str(settings.ml_artifacts_path / f"{version}.joblib")
    joblib.dump({
        "version": version,
        "algorithm": primary_name,
        "model": primary_model,
        "scaler": primary_scaler,
        "feature_names": FEATURE_NAMES,
    }, artifact_path)

    _persist_version(
        db, version, primary_name, "shadow",
        n_samples, len(y_train), len(y_test), n_positive, n_negative,
        metrics, baseline_metrics, artifact_path, trained_by,
    )
    logger.info("Shadow model %s (%s) activated on %d samples: %s", version, primary_name, n_samples, metrics)
    return TrainingReport(
        status="activated", version=version, n_samples=n_samples, n_train=len(y_train), n_test=len(y_test),
        n_positive=n_positive, n_negative=n_negative, metrics=metrics, baseline_metrics=baseline_metrics,
        artifact_path=artifact_path,
    )
