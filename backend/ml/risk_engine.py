"""
risk_engine.py

Combines two complementary detection layers into one explainable risk
score per work:

1. RULE ENGINE - domain-specific heuristics that mirror the checks a
   vigilant auditor would run (cost overruns, front-loaded / year-end
   payments, physical-vs-financial progress mismatch, duplicate/
   fragmented works, vendor concentration, stalled projects, missing
   utilization certificates). Each rule that fires contributes points
   and a human-readable reason - this is what makes alerts explainable
   rather than a black-box score.

2. UNSUPERVISED ML LAYER - an Isolation Forest trained on the numeric
   feature vector for every work. It has no notion of "fraud"; it simply
   learns what "normal" MPLADS works look like across the whole country
   and flags statistical outliers, which catches novel patterns the
   fixed rules don't anticipate.

Final risk_score (0-100) = weighted blend of the normalized isolation
score and the rule-engine point total, then bucketed into a risk band.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler

from ml.features import FEATURE_COLUMNS_FOR_MODEL

# ---------------------------------------------------------------------------
# 1. Rule engine
# ---------------------------------------------------------------------------

# (rule_code, points, label, condition_fn, message_fn)
def _rules():
    return [
        dict(code="COST_OVERRUN", points=25,
             cond=lambda r: r["cost_overrun_ratio"] > 0.20,
             msg=lambda r: f"Expenditure exceeds sanctioned amount by {r['cost_overrun_ratio']*100:.0f}% "
                            f"(sanctioned Rs.{r['sanctioned_amount_lakh']:.1f}L, spent Rs.{r['total_expenditure_lakh']:.1f}L)"),
        dict(code="GHOST_ASSET", points=30,
             cond=lambda r: r["high_ghost_flag"],
             msg=lambda r: f"{r['utilization_ratio']*100:.0f}% of funds drawn but physical progress reported "
                            f"only {r['latest_physical_pct']:.0f}% - possible non-existent / ghost asset"),
        dict(code="PROGRESS_MISMATCH", points=18,
             cond=lambda r: r["progress_gap"] > 25,
             msg=lambda r: f"Financial progress ({r['latest_financial_pct']:.0f}%) is "
                            f"{r['progress_gap']:.0f} points ahead of physical progress "
                            f"({r['latest_physical_pct']:.0f}%)"),
        dict(code="FRONT_LOADED_PAYMENT", points=18,
             cond=lambda r: r["first_installment_share"] > 0.65 and r["n_installments"] >= 2,
             msg=lambda r: f"{r['first_installment_share']*100:.0f}% of total payment released in the first "
                            f"installment, immediately after sanction"),
        dict(code="YEAR_END_RUSH", points=12,
             cond=lambda r: r["march_payment_share"] > 0.6,
             msg=lambda r: f"{r['march_payment_share']*100:.0f}% of payments concentrated in March "
                            f"(fiscal year-end), a common fund-parking signature"),
        dict(code="STALLED_OVERDUE", points=20,
             cond=lambda r: r["overdue_ratio"] > 0.5 and r["status"] in ("InProgress", "Delayed"),
             msg=lambda r: f"Work is {r['overdue_days']:.0f} days past its expected completion date "
                            f"and still marked '{r['status']}'"),
        dict(code="DUPLICATE_WORK", points=28,
             cond=lambda r: r["is_duplicate_desc"],
             msg=lambda r: f"Near-identical work description found {int(r['duplicate_group_size'])} times "
                            f"in the same district/category - possible duplicate billing"),
        dict(code="FRAGMENTATION", points=24,
             cond=lambda r: r["is_fragmentation_suspect"],
             msg=lambda r: f"One of {int(r['fragmentation_group_size'])} similarly small works sanctioned by the "
                            f"same MP in the same district/category within one month - possible splitting to "
                            f"avoid approval scrutiny"),
        dict(code="VENDOR_CONCENTRATION", points=22,
             cond=lambda r: r["is_vendor_concentration_suspect"],
             msg=lambda r: f"Primary vendor receives {r['mp_top_vendor_share']*100:.0f}% of this MP's total "
                            f"MPLADS expenditure - unusually concentrated"),
        dict(code="MISSING_UC", points=22,
             cond=lambda r: r["completed_without_uc"],
             msg=lambda r: "Work marked 'Completed' with funds drawn but no Utilization Certificate has "
                            "been filed"),
        dict(code="ONE_YEAR_OVERDUE", points=20,
             cond=lambda r: bool(r.get("one_year_overdue")),
             msg=lambda r: f"Open {int(r['days_since_sanction'])} days after sanction — MPLADS guidelines "
                            f"require completion within one year"),
        dict(code="PENDING_SANCTION", points=10,
             cond=lambda r: bool(r.get("pending_sanction")),
             msg=lambda r: "Recommended more than 90 days ago but still not sanctioned by the District Authority"),
        dict(code="ESTIMATE_DEVIATION", points=14,
             cond=lambda r: abs(r.get("estimate_deviation_ratio", 0) or 0) > 0.25,
             msg=lambda r: f"Sanctioned amount differs from the cost estimate by "
                            f"{abs(r['estimate_deviation_ratio'])*100:.0f}%"),
        dict(code="STALE_PROGRESS", points=12,
             cond=lambda r: bool(r.get("stale_progress")),
             msg=lambda r: "In-progress work with no progress report filed more than 60 days after sanction"),
    ]


def apply_rules(df: pd.DataFrame):
    rules = _rules()
    triggered_list = []
    points_list = []
    explanations = []
    for _, row in df.iterrows():
        fired = []
        pts = 0
        msgs = []
        for rule in rules:
            try:
                if rule["cond"](row):
                    fired.append(rule["code"])
                    pts += rule["points"]
                    msgs.append(rule["msg"](row))
            except Exception:
                continue
        triggered_list.append(fired)
        points_list.append(min(pts, 100))
        explanations.append(" | ".join(msgs) if msgs else "No rule-based red flags detected.")
    df = df.copy()
    df["rule_points"] = points_list
    df["triggered_rules"] = triggered_list
    df["rule_explanation"] = explanations
    return df


# ---------------------------------------------------------------------------
# 2. Isolation Forest layer
# ---------------------------------------------------------------------------

def fit_isolation_forest(df: pd.DataFrame, contamination=0.15, random_state=42):
    X = df[FEATURE_COLUMNS_FOR_MODEL].fillna(0.0).values
    scaler = RobustScaler()
    Xs = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=300,
        contamination=contamination,
        max_features=0.8,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(Xs)

    raw_scores = model.decision_function(Xs)          # higher = more normal
    anomaly_scores = -raw_scores                        # higher = more anomalous
    # normalize to 0-100 for readability
    lo, hi = anomaly_scores.min(), anomaly_scores.max()
    normalized = (anomaly_scores - lo) / (hi - lo + 1e-9) * 100

    return model, scaler, normalized


# ---------------------------------------------------------------------------
# 3. Combine into final risk score / band / alerts
# ---------------------------------------------------------------------------

RISK_BANDS = [
    (0, 25, "Low"),
    (25, 45, "Medium"),
    (45, 68, "High"),
    (68, 101, "Critical"),
]


def band_for(score):
    for lo, hi, name in RISK_BANDS:
        if lo <= score < hi:
            return name
    return "Critical"


# A single high-severity rule must be enough to put a work on the High
# (or Critical) review queue. Blending isolation-forest points alone
# previously left genuine red flags in Medium because 25 rule-points × 0.65
# plus a mid-range isolation score sat below the High cutoff of 45.
CRITICAL_RULES = {"GHOST_ASSET", "DUPLICATE_WORK"}
HIGH_RULES = {
    "COST_OVERRUN", "MISSING_UC", "STALLED_OVERDUE", "FRAGMENTATION",
    "VENDOR_CONCENTRATION", "PROGRESS_MISMATCH", "FRONT_LOADED_PAYMENT",
    "ONE_YEAR_OVERDUE",
}


def _floor_for_rules(triggered):
    rules = set(triggered or [])
    if rules & CRITICAL_RULES:
        return 72 if (len(rules & CRITICAL_RULES) >= 2 or "GHOST_ASSET" in rules) else 55
    if rules & HIGH_RULES:
        return 50
    if rules:
        return 32
    return 0


def score_dataset(df: pd.DataFrame, isolation_weight=0.30, rule_weight=0.70):
    df = apply_rules(df)
    model, scaler, iso_scores = fit_isolation_forest(df)
    df = df.copy()
    df["isolation_score"] = iso_scores
    # The bundled source is allocation-only: it has no payment, progress, or
    # vendor data from which the work-level rules can fire. In that case make
    # the real allocation amount's Isolation Forest outlier score visible as
    # a warning, rather than silently classifying every row as Low.
    allocation_only = df["status"].eq("Allocation").all()
    if allocation_only:
        blended = (0.75 * df["isolation_score"] + 0.25 * df["rule_points"]).clip(0, 100)
    else:
        blended = (isolation_weight * df["isolation_score"] + rule_weight * df["rule_points"]).clip(0, 100)
    floors = df["triggered_rules"].apply(_floor_for_rules)
    df["risk_score"] = np.maximum(blended, floors).clip(0, 100)
    df["risk_band"] = df["risk_score"].apply(band_for)
    return df, model, scaler


def build_alerts(df: pd.DataFrame):
    """Generate one alert per triggered rule for High/Critical risk works
    (keeps the alert feed focused on things that actually need attention),
    plus a single 'STATISTICAL_OUTLIER' alert for works the isolation
    forest strongly flags even without a specific rule firing."""
    alerts = []
    now = datetime.utcnow().isoformat()
    rules = {r["code"]: r for r in _rules()}
    for _, row in df.iterrows():
        if row["risk_band"] not in ("High", "Critical"):
            continue
        severity = "Critical" if row["risk_band"] == "Critical" else "High"
        for code in row["triggered_rules"]:
            rule = rules[code]
            alerts.append(dict(
                work_id=int(row["work_id"]),
                severity=severity,
                category=code,
                message=rule["msg"](row),
                created_at=now,
            ))
        if not row["triggered_rules"] and row["risk_band"] in ("High", "Critical"):
            allocation_record = row.get("status") == "Allocation"
            alerts.append(dict(
                work_id=int(row["work_id"]),
                severity=severity,
                category="STATISTICAL_OUTLIER",
                message=(
                    "Allocation amount is statistically unusual compared with the imported "
                    "MP allocation records. Verify the source value and supporting approval; "
                    "this is a review warning, not a finding of wrongdoing."
                    if allocation_record else
                    "Flagged as a statistical outlier versus similar works nationwide "
                    "(unusual combination of cost, timeline and payment pattern) even "
                    "though no single rule threshold was crossed."
                ),
                created_at=now,
            ))
    return alerts
