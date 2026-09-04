"""
features.py

Builds a per-work feature table purely from the raw transactional tables
(works, expenditures, progress_reports, utilization_certificates, vendors).
This is the ONLY module that touches raw data for scoring purposes. Everything
downstream (rules + Isolation Forest) is unsupervised: it does not use fraud
or anomaly labels.
"""

import numpy as np
import pandas as pd

from db import get_connection

TODAY = pd.Timestamp("2026-08-31")


def load_raw_tables():
    conn = get_connection()
    works = pd.read_sql_query("SELECT * FROM works", conn)
    expenditures = pd.read_sql_query("SELECT * FROM expenditures", conn)
    progress = pd.read_sql_query("SELECT * FROM progress_reports", conn)
    ucs = pd.read_sql_query("SELECT * FROM utilization_certificates", conn)
    vendors = pd.read_sql_query("SELECT * FROM vendors", conn)
    mps = pd.read_sql_query("SELECT * FROM members_of_parliament", conn)
    districts = pd.read_sql_query("SELECT * FROM districts", conn)
    conn.close()

    for df, cols in [
        (works, ["recommended_date", "sanction_date", "expected_completion_date", "actual_completion_date"]),
        (expenditures, ["payment_date"]),
        (progress, ["report_date"]),
        (ucs, ["submitted_date"]),
    ]:
        for c in cols:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    return dict(works=works, expenditures=expenditures, progress=progress,
                ucs=ucs, vendors=vendors, mps=mps, districts=districts)


def build_feature_table(raw=None) -> pd.DataFrame:
    if raw is None:
        raw = load_raw_tables()
    works = raw["works"].copy()
    exp = raw["expenditures"]
    prog = raw["progress"]
    ucs = raw["ucs"]

    # ---- expenditure aggregates ----
    exp_agg = exp.groupby("work_id").agg(
        total_expenditure_lakh=("amount_lakh", "sum"),
        n_installments=("expenditure_id", "count"),
        first_payment_date=("payment_date", "min"),
        last_payment_date=("payment_date", "max"),
    ).reset_index()

    # first-installment share (front-loading indicator)
    exp_sorted = exp.sort_values(["work_id", "installment_no"])
    first_inst = exp_sorted.groupby("work_id").first()["amount_lakh"].rename("first_installment_amt")
    exp_agg = exp_agg.merge(first_inst, on="work_id", how="left")

    # share of expenditure paid in March (fiscal year-end rush)
    exp["is_march"] = exp["payment_date"].dt.month == 3
    march_share = exp.groupby("work_id")["is_march"].mean().rename("march_payment_share")
    exp_agg = exp_agg.merge(march_share, on="work_id", how="left")

    works = works.merge(exp_agg, on="work_id", how="left")
    works["total_expenditure_lakh"] = works["total_expenditure_lakh"].fillna(0.0)
    works["n_installments"] = works["n_installments"].fillna(0).astype(int)
    works["march_payment_share"] = works["march_payment_share"].fillna(0.0)
    works["first_installment_amt"] = works["first_installment_amt"].fillna(0.0)

    # ---- progress aggregates (latest report per work) ----
    if len(prog):
        latest_idx = prog.sort_values("report_date").groupby("work_id").tail(1)
        latest_prog = latest_idx[["work_id", "physical_progress_pct", "financial_progress_pct"]]
        latest_prog = latest_prog.rename(columns={
            "physical_progress_pct": "latest_physical_pct",
            "financial_progress_pct": "latest_financial_pct"})
        works = works.merge(latest_prog, on="work_id", how="left")
    else:
        works["latest_physical_pct"] = np.nan
        works["latest_financial_pct"] = np.nan
    works["latest_physical_pct"] = works["latest_physical_pct"].fillna(0.0)
    works["latest_financial_pct"] = works["latest_financial_pct"].fillna(0.0)

    # ---- utilization certificate flag ----
    uc_ids = set(ucs["work_id"].unique().tolist())
    works["has_uc"] = works["work_id"].isin(uc_ids)

    # ---- derived numeric features ----
    works["cost_overrun_ratio"] = np.where(
        works["sanctioned_amount_lakh"] > 0,
        (works["total_expenditure_lakh"] - works["sanctioned_amount_lakh"]) / works["sanctioned_amount_lakh"],
        0.0,
    )
    works["utilization_ratio"] = np.where(
        works["sanctioned_amount_lakh"] > 0,
        works["total_expenditure_lakh"] / works["sanctioned_amount_lakh"],
        0.0,
    )
    works["progress_gap"] = works["latest_financial_pct"] - works["latest_physical_pct"]  # positive = money ahead of work

    works["days_since_sanction"] = (TODAY - works["sanction_date"]).dt.days.clip(lower=0)
    works["expected_duration_days"] = (works["expected_completion_date"] - works["sanction_date"]).dt.days.clip(lower=1)
    works["overdue_days"] = np.where(
        (works["status"].isin(["InProgress", "Delayed"])) & (works["expected_completion_date"] < TODAY),
        (TODAY - works["expected_completion_date"]).dt.days,
        0,
    )
    works["overdue_ratio"] = works["overdue_days"] / works["expected_duration_days"].replace(0, 1)

    works["first_installment_share"] = np.where(
        works["total_expenditure_lakh"] > 0,
        works["first_installment_amt"] / works["total_expenditure_lakh"],
        0.0,
    )

    works["completed_without_uc"] = (works["status"] == "Completed") & (~works["has_uc"])
    works["high_ghost_flag"] = (works["utilization_ratio"] > 0.6) & (works["latest_physical_pct"] < 20)

    works["estimate_deviation_ratio"] = np.where(
        works["estimated_cost_lakh"] > 0,
        (works["sanctioned_amount_lakh"] - works["estimated_cost_lakh"]) / works["estimated_cost_lakh"],
        0.0,
    )
    works["sanction_lag_days"] = (works["sanction_date"] - works["recommended_date"]).dt.days.clip(lower=0)
    works["one_year_overdue"] = (
        works["status"].isin(["Sanctioned", "InProgress", "Delayed"])
        & (works["days_since_sanction"] > 365)
    )
    works["pending_sanction"] = (
        works["status"].isin(["Recommended"])
        & ((TODAY - works["recommended_date"]).dt.days > 90)
    )

    if len(prog):
        n_reports = prog.groupby("work_id").size().rename("n_progress_reports")
        works = works.merge(n_reports, on="work_id", how="left")
    else:
        works["n_progress_reports"] = 0
    works["n_progress_reports"] = works["n_progress_reports"].fillna(0).astype(int)
    works["stale_progress"] = (
        works["status"].isin(["InProgress", "Delayed"])
        & (works["n_progress_reports"] == 0)
        & (works["days_since_sanction"] > 60)
    )

    # ---- duplicate-description detection within same district+category ----
    dup_key = works["district_id"].astype(str) + "||" + works["work_category"] + "||" + works["description"].str.strip().str.lower()
    dup_counts = dup_key.value_counts()
    works["duplicate_group_size"] = dup_key.map(dup_counts)
    works["is_duplicate_desc"] = works["duplicate_group_size"] > 1

    # ---- fragmentation detection: same mp+district+category+near-identical sanction date, many small works ----
    frag_key = (works["mp_id"].astype(str) + "||" + works["district_id"].astype(str) + "||" +
                works["work_category"] + "||" + works["sanction_date"].dt.to_period("M").astype(str))
    frag_counts = frag_key.value_counts()
    works["fragmentation_group_size"] = frag_key.map(frag_counts)
    small_work_threshold = works["sanctioned_amount_lakh"].quantile(0.35)
    works["is_small_work"] = works["sanctioned_amount_lakh"] <= small_work_threshold
    works["is_fragmentation_suspect"] = (works["fragmentation_group_size"] >= 3) & works["is_small_work"]

    # ---- vendor concentration: share of an MP's total expenditure going to a single vendor ----
    vendor_pay = exp.merge(works[["work_id", "mp_id"]], on="work_id", how="left")
    vendor_mp_totals = vendor_pay.groupby(["mp_id", "vendor_id"])["amount_lakh"].sum().reset_index()
    mp_totals = vendor_pay.groupby("mp_id")["amount_lakh"].sum().rename("mp_total")
    vendor_mp_totals = vendor_mp_totals.merge(mp_totals, on="mp_id", how="left")
    vendor_mp_totals["vendor_share_of_mp"] = vendor_mp_totals["amount_lakh"] / vendor_mp_totals["mp_total"].replace(0, np.nan)
    top_vendor_share = vendor_mp_totals.sort_values("vendor_share_of_mp", ascending=False).groupby("mp_id").first()
    works = works.merge(
        top_vendor_share[["vendor_share_of_mp"]].rename(columns={"vendor_share_of_mp": "mp_top_vendor_share"}),
        left_on="mp_id", right_index=True, how="left")
    works["mp_top_vendor_share"] = works["mp_top_vendor_share"].fillna(0.0)
    # a work is "vendor concentration suspect" if its own vendor IS that MP's dominant vendor
    # and that dominant share is unusually high
    work_vendor = exp_sorted.groupby("work_id")["vendor_id"].first().rename("primary_vendor_id")
    works = works.merge(work_vendor, on="work_id", how="left")
    dominant_vendor = vendor_mp_totals.sort_values("vendor_share_of_mp", ascending=False).groupby("mp_id").first()["vendor_id"]
    works = works.merge(dominant_vendor.rename("mp_dominant_vendor_id"), left_on="mp_id", right_index=True, how="left")
    works["is_vendor_concentration_suspect"] = (
        (works["mp_top_vendor_share"] > 0.28) &
        (works["primary_vendor_id"] == works["mp_dominant_vendor_id"])
    )

    return works


FEATURE_COLUMNS_FOR_MODEL = [
    # Allocation-only source files do not include payment/progress fields.
    # The allocated amount is therefore a valid, source-provided signal for
    # detecting unusual allocation patterns.
    "sanctioned_amount_lakh",
    "cost_overrun_ratio", "utilization_ratio", "progress_gap", "overdue_ratio",
    "first_installment_share", "march_payment_share", "duplicate_group_size",
    "fragmentation_group_size", "mp_top_vendor_share", "n_installments",
    "estimate_deviation_ratio", "sanction_lag_days", "n_progress_reports",
    "latest_physical_pct",
]
