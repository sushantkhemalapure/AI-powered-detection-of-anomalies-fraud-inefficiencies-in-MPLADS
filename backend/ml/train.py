"""
train.py

End-to-end pipeline:
  1. Load raw tables -> build feature table (features.py)
  2. Score every work with rules + Isolation Forest (risk_engine.py)
  3. Persist risk_scores + alerts back into SQLite
  4. Save the fitted model/scaler to disk (joblib) for reuse by the API
  5. Write a training summary. The bundled allocation dataset has no verified
     anomaly labels, so no fabricated precision/recall evaluation is produced.

Run:  python -m ml.train        (from the backend/ directory)
"""

import json
import os
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/

from db import connection_scope, init_db
from ml.features import build_feature_table
from ml.predict import attach_actions, fit_predictors
from ml.risk_engine import score_dataset, build_alerts

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")


def persist_risk_scores(conn, df: pd.DataFrame):
    cur = conn.cursor()
    cur.execute("DELETE FROM risk_scores")
    rows = [
        (int(r.work_id), float(r.risk_score), r.risk_band, float(r.isolation_score),
         json.dumps(r.triggered_rules), r.rule_explanation, pd.Timestamp.utcnow().isoformat())
        for r in df.itertuples()
    ]
    cur.executemany("""INSERT INTO risk_scores
        (work_id, risk_score, risk_band, isolation_score, triggered_rules, explanation, computed_at)
        VALUES (?,?,?,?,?,?,?)""", rows)


def persist_alerts(conn, alerts):
    cur = conn.cursor()
    cur.execute("DELETE FROM alerts")
    rows = [(a["work_id"], a["severity"], a["category"], a["message"], a["created_at"], "Open")
            for a in alerts]
    cur.executemany("""INSERT INTO alerts (work_id, severity, category, message, created_at, status)
        VALUES (?,?,?,?,?,?)""", rows)


def persist_predictions(conn, df: pd.DataFrame):
    cur = conn.cursor()
    cur.execute("DELETE FROM predictions")
    rows = [
        (int(r.work_id), float(r.delay_probability), float(r.overrun_probability),
         float(r.early_warning_score), r.recommended_action, r.predicted_at)
        for r in df.itertuples()
    ]
    cur.executemany("""INSERT INTO predictions
        (work_id, delay_probability, overrun_probability, early_warning_score,
         recommended_action, computed_at)
        VALUES (?,?,?,?,?,?)""", rows)


def training_summary(df: pd.DataFrame):
    """Describe the actual data scored without asserting label-based metrics."""
    bands = df["risk_band"].value_counts().to_dict()
    return {
        "total_records": int(len(df)),
        "risk_bands": {band: int(bands.get(band, 0)) for band in ("Low", "Medium", "High", "Critical")},
        "data_note": (
            "The imported allocation dataset contains no confirmed anomaly labels or "
            "work/payment/progress details. Scores identify unusual allocation patterns "
            "only and require human review."
        ),
    }


def run():
    init_db(reset=False)  # ensure predictions table exists on older databases
    os.makedirs(MODEL_DIR, exist_ok=True)
    print("Loading raw tables and engineering features...")
    features_df = build_feature_table()

    print(f"Scoring {len(features_df)} works (rule engine + Isolation Forest)...")
    scored_df, model, scaler = score_dataset(features_df)

    print("Fitting delay / cost-overrun early-warning models...")
    scored_df, delay_model, overrun_model, pred_scaler = fit_predictors(scored_df)
    scored_df = attach_actions(scored_df)

    alerts = build_alerts(scored_df)
    print(f"Generated {len(alerts)} alerts.")

    with connection_scope() as conn:
        persist_risk_scores(conn, scored_df)
        persist_alerts(conn, alerts)
        persist_predictions(conn, scored_df)

    joblib.dump({"model": model, "scaler": scaler}, os.path.join(MODEL_DIR, "isolation_forest.joblib"))
    if delay_model is not None:
        joblib.dump(
            {"delay_model": delay_model, "overrun_model": overrun_model, "scaler": pred_scaler},
            os.path.join(MODEL_DIR, "early_warning.joblib"),
        )

    report = training_summary(scored_df)
    with open(os.path.join(MODEL_DIR, "training_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    evaluation_path = os.path.join(MODEL_DIR, "evaluation_report.json")
    if os.path.exists(evaluation_path):
        os.remove(evaluation_path)
    if delay_model is None:
        warning_path = os.path.join(MODEL_DIR, "early_warning.joblib")
        if os.path.exists(warning_path):
            os.remove(warning_path)

    print("\n--- Training summary ---")
    for k, v in report.items():
        print(f"  {k}: {v}")
    print(f"\nModel artifacts saved to {MODEL_DIR}")
    print("Risk scores and alerts written to database.")


if __name__ == "__main__":
    run()
