"""
predict.py

Early-warning layer on top of the unsupervised risk engine.

Two Gradient Boosting classifiers are trained only on *closed* works
(Completed / Delayed), using features that would have been observable
while the work was still underway:

  - delay model  : will this work miss its expected completion date?
  - overrun model: will expenditure exceed the sanctioned amount by >15%?

Predictions are then applied to every open work so District / State /
Ministry dashboards can surface cases that are *heading* toward delay
or cost overrun before they become High-risk alerts.

Leak-safe features only: we do not train the delay model on overdue_ratio
or latest_physical_pct of completed works (those are 0 / 100 by definition
once a work is closed).
"""

from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import RobustScaler

PREDICT_FEATURES = [
    "first_installment_share",
    "march_payment_share",
    "n_installments",
    "sanctioned_amount_lakh",
    "estimated_cost_lakh",
    "expected_duration_days",
    "utilization_ratio",
    "progress_gap",
    "mp_top_vendor_share",
    "estimate_deviation_ratio",
    "sanction_lag_days",
]


def _closed_mask(df: pd.DataFrame) -> pd.Series:
    return df["status"].isin(["Completed", "Delayed"])


def _delay_label(df: pd.DataFrame) -> pd.Series:
    actual = pd.to_datetime(df["actual_completion_date"], errors="coerce")
    expected = pd.to_datetime(df["expected_completion_date"], errors="coerce")
    missed = (df["status"] == "Delayed") | (
        actual.notna() & expected.notna() & (actual > expected)
    )
    return missed.astype(int)


def _overrun_label(df: pd.DataFrame) -> pd.Series:
    return (df["cost_overrun_ratio"].fillna(0) > 0.15).astype(int)


def _matrix(df: pd.DataFrame) -> np.ndarray:
    return df[PREDICT_FEATURES].fillna(0.0).values


def fit_predictors(df: pd.DataFrame, random_state=42):
    """Fit delay + overrun models on closed works; score every row."""
    closed = df.loc[_closed_mask(df)].copy()
    if len(closed) < 40:
        # Too little history — fall back to heuristic-only scores.
        delay_p = _heuristic_delay(df)
        overrun_p = _heuristic_overrun(df)
        return df.assign(
            delay_probability=delay_p,
            overrun_probability=overrun_p,
        ), None, None, None

    X_closed = _matrix(closed)
    scaler = RobustScaler()
    Xs = scaler.fit_transform(X_closed)

    delay_model = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.08, random_state=random_state
    )
    overrun_model = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.08, random_state=random_state
    )
    delay_model.fit(Xs, _delay_label(closed).values)
    overrun_model.fit(Xs, _overrun_label(closed).values)

    X_all = scaler.transform(_matrix(df))
    delay_p = delay_model.predict_proba(X_all)[:, 1]
    overrun_p = overrun_model.predict_proba(X_all)[:, 1]

    # Blend a small current-state heuristic so in-progress overdue works
    # are not scored purely from historical payment patterns.
    delay_p = np.clip(0.7 * delay_p + 0.3 * _heuristic_delay(df), 0, 1)
    overrun_p = np.clip(0.75 * overrun_p + 0.25 * _heuristic_overrun(df), 0, 1)

    out = df.copy()
    out["delay_probability"] = delay_p
    out["overrun_probability"] = overrun_p
    return out, delay_model, overrun_model, scaler


def _heuristic_delay(df: pd.DataFrame) -> np.ndarray:
    overdue = df.get("overdue_ratio", pd.Series(0, index=df.index)).fillna(0).clip(0, 2) / 2
    phys = df.get("latest_physical_pct", pd.Series(0, index=df.index)).fillna(0)
    elapsed = df.get("days_since_sanction", pd.Series(0, index=df.index)).fillna(0)
    # Allocation-only imports have no completion duration. Treat that missing
    # field as unavailable (one neutral day) so the heuristic remains numeric
    # instead of storing NaN predictions.
    duration = df.get("expected_duration_days", pd.Series(1, index=df.index)).fillna(1).replace(0, 1)
    expected_phys = (elapsed / duration).clip(0, 1) * 100
    lag = ((expected_phys - phys) / 100).clip(0, 1)
    open_work = df["status"].isin(["InProgress", "Delayed", "Sanctioned"]).astype(float)
    return (0.55 * overdue + 0.45 * lag) * open_work


def _heuristic_overrun(df: pd.DataFrame) -> np.ndarray:
    ratio = df.get("cost_overrun_ratio", pd.Series(0, index=df.index)).fillna(0)
    util = df.get("utilization_ratio", pd.Series(0, index=df.index)).fillna(0)
    phys = df.get("latest_physical_pct", pd.Series(0, index=df.index)).fillna(0) / 100
    burn_ahead = (util - phys).clip(0, 1)
    already = (ratio > 0).astype(float)
    return np.clip(0.6 * already * ratio.clip(0, 1) + 0.4 * burn_ahead, 0, 1)


def early_warning_score(df: pd.DataFrame) -> pd.Series:
    delay = df["delay_probability"].fillna(0)
    overrun = df["overrun_probability"].fillna(0)
    open_work = df["status"].isin(["Recommended", "Sanctioned", "InProgress", "Delayed"])
    score = (0.6 * delay + 0.4 * overrun) * 100
    return np.where(open_work, score, 0.0)


def recommended_action(row) -> str:
    rules = row.get("triggered_rules") or []
    if isinstance(rules, str):
        import json
        try:
            rules = json.loads(rules)
        except Exception:
            rules = []
    actions = []
    if "GHOST_ASSET" in rules:
        actions.append("Order physical verification of the asset before any further payment.")
    if "COST_OVERRUN" in rules:
        actions.append("Stop further releases until a revised estimate is sanctioned.")
    if "DUPLICATE_WORK" in rules:
        actions.append("Match against the district work register; treat as possible double billing.")
    if "MISSING_UC" in rules:
        actions.append("Direct the District Authority to file the Utilization Certificate within 15 days.")
    if "STALLED_OVERDUE" in rules or "ONE_YEAR_OVERDUE" in rules:
        actions.append("Issue a notice to the Implementing Agency and schedule a review meeting.")
    if "VENDOR_CONCENTRATION" in rules:
        actions.append("Review tender history for this vendor across the MP's works.")
    if "FRAGMENTATION" in rules:
        actions.append("Examine whether these sanctions should have been a single work.")
    if "FRONT_LOADED_PAYMENT" in rules or "YEAR_END_RUSH" in rules:
        actions.append("Audit the payment schedule against physical milestones in the sanction order.")
    if "PENDING_SANCTION" in rules:
        actions.append("District Authority should complete feasibility and sanction, or return the recommendation.")
    if "STALE_PROGRESS" in rules:
        actions.append("Require the Implementing Agency to file a current progress report.")
    delay_p = float(row.get("delay_probability") or 0)
    overrun_p = float(row.get("overrun_probability") or 0)
    if delay_p >= 0.6 and not any("notice" in a.lower() or "review meeting" in a.lower() for a in actions):
        actions.append("Work is on a delay trajectory — request a catch-up plan from the agency.")
    if overrun_p >= 0.6 and "Stop further releases" not in " ".join(actions):
        actions.append("Expenditure is tracking above sanction — freeze incremental payments pending review.")
    if not actions:
        actions.append("Continue routine monitoring.")
    return " ".join(actions[:2])


def attach_actions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["early_warning_score"] = early_warning_score(out)
    out["recommended_action"] = out.apply(recommended_action, axis=1)
    out["predicted_at"] = datetime.utcnow().isoformat()
    return out
