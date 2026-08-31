"""CLI wrapper to (re)train the ML shadow model outside the API.

    python -m scripts.train_model

Same logic as ``POST /api/v1/ml/train`` — refuses to activate a model below
``settings.ml_min_samples`` labeled, final loan outcomes and says exactly why.
"""
from __future__ import annotations

import json

from app.database import SessionLocal
from app.services.ml.train import train_and_evaluate


def main() -> None:
    db = SessionLocal()
    try:
        report = train_and_evaluate(db, trained_by="cli")
    finally:
        db.close()

    print(f"status: {report.status}")
    if report.status == "trained_insufficient":
        print(report.reason)
        return

    print(f"version: {report.version}")
    print(f"samples: {report.n_samples} (train={report.n_train}, test={report.n_test}, "
          f"bad={report.n_positive}, good={report.n_negative})")
    print("metrics (activated model):")
    print(json.dumps(report.metrics, indent=2))
    print("baseline metrics (the model that lost the comparison):")
    print(json.dumps(report.baseline_metrics, indent=2))


if __name__ == "__main__":
    main()
