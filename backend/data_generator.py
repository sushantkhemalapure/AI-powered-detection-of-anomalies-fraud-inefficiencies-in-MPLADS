"""
data_generator.py

Generates a realistic, internally-consistent synthetic MPLADS dataset and
loads it into the SQLite database defined in db.py.

Why synthetic data? The public MPLADS dashboard (mplads.mospi.gov.in) does
not expose a bulk/API download of transaction-level sanction, expenditure
and progress data, and this environment has no network access to scrape
it. To keep the platform genuinely runnable and demonstrable end-to-end,
this script builds a statistically realistic stand-in dataset that follows
the real scheme's structure (MPs -> recommended works -> sanctions ->
expenditure -> progress -> utilization certificates) and deliberately
seeds a configurable percentage of records with well-known MPLADS misuse
/ inefficiency patterns, each tagged with `is_seeded_anomaly` /
`seeded_anomaly_type` for offline evaluation only.

IMPORTANT: the detection pipeline in backend/ml/ never reads those two
label columns - it scores every record from scratch using unsupervised
anomaly detection + rule-based checks, exactly as it would have to on a
real, unlabeled dataset. The labels exist purely so we can report
precision/recall for the README and the Ministry-facing "model
performance" panel, which is standard practice when demonstrating a
fraud-detection system without access to confirmed real-world fraud
cases.

Run directly:  python data_generator.py [--works 3000] [--anomaly-rate 0.09]
"""

import argparse
import json
import random
import sqlite3
from datetime import date, timedelta

import numpy as np

from db import connection_scope, init_db

random.seed(42)
np.random.seed(42)

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

STATES = {
    "Uttar Pradesh": "North", "Maharashtra": "West", "Bihar": "East",
    "West Bengal": "East", "Madhya Pradesh": "Central", "Tamil Nadu": "South",
    "Rajasthan": "North", "Karnataka": "South", "Gujarat": "West",
    "Andhra Pradesh": "South", "Odisha": "East", "Telangana": "South",
    "Kerala": "South", "Assam": "Northeast", "Punjab": "North",
    "Haryana": "North", "Chhattisgarh": "Central", "Jharkhand": "East",
    "Uttarakhand": "North", "Himachal Pradesh": "North",
}

DISTRICT_NAMES_POOL = [
    "North", "South", "East", "West", "Central", "Rural", "Urban",
    "Sadar", "Coastal", "Hill",
]

WORK_CATEGORIES = [
    "Drinking Water Supply", "Rural Road Construction", "Community Hall",
    "School Building / Classroom", "Primary Health Centre",
    "Street Lighting", "Sanitation & Sewerage", "Irrigation Facility",
    "Sports Infrastructure", "Anganwadi Centre", "Public Library",
    "Bridge / Culvert", "Solar Power Installation", "Crematorium/Cemetery",
    "Drainage System",
]

ASSET_TYPES = {
    "Drinking Water Supply": "Water Tank/Pipeline",
    "Rural Road Construction": "Road (km)",
    "Community Hall": "Building",
    "School Building / Classroom": "Building",
    "Primary Health Centre": "Building",
    "Street Lighting": "Fixtures (units)",
    "Sanitation & Sewerage": "Network",
    "Irrigation Facility": "Structure",
    "Sports Infrastructure": "Ground/Equipment",
    "Anganwadi Centre": "Building",
    "Public Library": "Building",
    "Bridge / Culvert": "Structure",
    "Solar Power Installation": "Plant (kW)",
    "Crematorium/Cemetery": "Facility",
    "Drainage System": "Network",
}

AGENCY_TYPES = ["District Rural Development Agency", "Municipal Corporation",
                "Public Works Department", "Zilla Parishad", "Gram Panchayat Union"]

PARTIES = ["INC", "BJP", "AAP", "DMK", "TMC", "SP", "BSP", "NCP", "SS", "JD(U)", "BJD", "IND"]

FIRST_NAMES = ["Rajesh", "Suresh", "Anita", "Priya", "Vikram", "Sunita", "Ramesh", "Kavita",
               "Arvind", "Meena", "Sanjay", "Geeta", "Deepak", "Rekha", "Manoj", "Pooja",
               "Ashok", "Lata", "Vinod", "Shobha", "Rakesh", "Usha", "Naveen", "Radha"]
LAST_NAMES = ["Sharma", "Verma", "Yadav", "Reddy", "Patel", "Nair", "Iyer", "Gupta", "Singh",
              "Kumar", "Rao", "Das", "Chaudhary", "Mishra", "Pillai", "Joshi", "Naidu", "Bose"]

VENDOR_SUFFIXES = ["Constructions", "Infra Pvt Ltd", "Builders", "Engineering Works",
                    "Contractors", "Enterprises", "Infrastructure Ltd", "Associates"]

FISCAL_YEAR_START = date(2021, 4, 1)
FISCAL_YEAR_END = date(2026, 3, 31)


def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=random.randint(0, delta))


def make_description(category, district_name, seq):
    templates = {
        "Drinking Water Supply": f"Installation of overhead water tank and pipeline in {district_name} ward {seq}",
        "Rural Road Construction": f"Construction/upgradation of {random.choice([1,2,3])}.{random.randint(0,9)} km approach road near {district_name}",
        "Community Hall": f"Construction of community hall at {district_name} village {seq}",
        "School Building / Classroom": f"Construction of additional classroom block, Govt School {district_name} #{seq}",
        "Primary Health Centre": f"Renovation and equipment upgrade of PHC {district_name}",
        "Street Lighting": f"Installation of solar street lights ({random.randint(20,150)} units) in {district_name}",
        "Sanitation & Sewerage": f"Construction of sewerage line and soak pits in {district_name} sector {seq}",
        "Irrigation Facility": f"Construction of check dam / irrigation channel near {district_name}",
        "Sports Infrastructure": f"Development of playground with basic sports equipment at {district_name}",
        "Anganwadi Centre": f"Construction of Anganwadi centre building, {district_name} #{seq}",
        "Public Library": f"Construction/renovation of public reading room at {district_name}",
        "Bridge / Culvert": f"Construction of RCC culvert on village road, {district_name}",
        "Solar Power Installation": f"Installation of {random.choice([5,10,15,25])} kW solar power unit at {district_name} govt building",
        "Crematorium/Cemetery": f"Development of crematorium shed and boundary wall at {district_name}",
        "Drainage System": f"Construction of RCC drain along main road, {district_name} sector {seq}",
    }
    return templates[category]


# ---------------------------------------------------------------------------
# Reference table population
# ---------------------------------------------------------------------------

def build_reference_data(conn, mps_per_state_range=(2, 6), districts_per_state_range=(2, 4)):
    cur = conn.cursor()
    state_ids = {}
    for name, region in STATES.items():
        cur.execute("INSERT INTO states(name, region) VALUES (?,?)", (name, region))
        state_ids[name] = cur.lastrowid

    district_ids = []          # list of (district_id, state_id, name)
    for name, sid in state_ids.items():
        n_dist = random.randint(*districts_per_state_range)
        chosen = random.sample(DISTRICT_NAMES_POOL, n_dist)
        for dname in chosen:
            full_name = f"{name.split()[0]} {dname}"
            cur.execute("INSERT INTO districts(state_id, name) VALUES (?,?)", (sid, full_name))
            district_ids.append((cur.lastrowid, sid, full_name))

    mp_ids = []                 # list of (mp_id, state_id, name)
    for name, sid in state_ids.items():
        n_mp = random.randint(*mps_per_state_range)
        for i in range(n_mp):
            full_name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
            house = "Lok Sabha" if random.random() < 0.75 else "Rajya Sabha"
            cur.execute("""INSERT INTO members_of_parliament
                (name, house, state_id, constituency, party, term_start, annual_entitlement_lakh)
                VALUES (?,?,?,?,?,?,?)""",
                (full_name, house, sid, f"{name} Constituency {i+1}",
                 random.choice(PARTIES), "2024-06-01", 500.0))
            mp_ids.append((cur.lastrowid, sid, full_name))

    agency_ids = []              # (agency_id, district_id)
    for did, sid, dname in district_ids:
        for _ in range(random.randint(2, 3)):
            atype = random.choice(AGENCY_TYPES)
            cur.execute("INSERT INTO implementing_agencies(name, district_id, agency_type) VALUES (?,?,?)",
                        (f"{atype}, {dname}", did, atype))
            agency_ids.append((cur.lastrowid, did))

    vendor_ids = []               # (vendor_id, district_id)
    for did, sid, dname in district_ids:
        for _ in range(random.randint(4, 8)):
            vname = f"{random.choice(LAST_NAMES)} {random.choice(VENDOR_SUFFIXES)}"
            reg = f"GST{random.randint(10,37)}{random.randint(100000,999999)}"
            cur.execute("INSERT INTO vendors(name, registration_no, district_id, risk_flag) VALUES (?,?,?,0)",
                        (vname, reg, did))
            vendor_ids.append((cur.lastrowid, did))

    return {
        "states": state_ids,
        "districts": district_ids,
        "mps": mp_ids,
        "agencies": agency_ids,
        "vendors": vendor_ids,
    }


# ---------------------------------------------------------------------------
# Core work + financial lifecycle generation
# ---------------------------------------------------------------------------

ANOMALY_TYPES = [
    "cost_overrun", "ghost_asset", "fragmentation", "front_loaded_payment",
    "progress_mismatch", "year_end_rush", "missing_utilization_cert", "duplicate_work",
]
# stalled_delayed and vendor_concentration are seeded via dedicated passes
# below (see inject_stalled_delayed / inject_vendor_concentration) because
# they need to override the works' status/date logic and cross-work vendor
# assignment respectively, rather than a single independent per-row tweak.


def district_agencies(ref, district_id):
    return [a for a, d in ref["agencies"] if d == district_id]


def district_vendors(ref, district_id):
    return [v for v, d in ref["vendors"] if d == district_id]


def inject_stalled_delayed(work_rows, rate=0.025):
    """Force a subset of currently in-progress works to be badly overdue -
    still not complete, well past their expected completion date - the
    classic 'stalled project' signature."""
    candidates = [r for r in work_rows if r["status"] in ("InProgress", "Delayed")
                  and r["seeded_anomaly_type"] is None]
    n = max(1, int(len(work_rows) * rate))
    chosen = random.sample(candidates, min(n, len(candidates)))
    for r in chosen:
        overdue_days = random.randint(150, 600)
        new_expected = date(2026, 8, 31) - timedelta(days=overdue_days)
        # keep it after sanction date so the timeline stays coherent
        if new_expected <= r["sanction_date_obj"]:
            new_expected = r["sanction_date_obj"] + timedelta(days=30)
        r["expected_completion_date"] = new_expected.isoformat()
        r["expected_completion_obj"] = new_expected
        r["status"] = "Delayed"
        r["actual_completion_date"] = None
        r["actual_completion_obj"] = None
        r["is_seeded_anomaly"] = 1
        r["seeded_anomaly_type"] = "stalled_delayed"


def inject_vendor_concentration(work_rows, ref, rate_of_mps=0.12):
    """Pick a subset of MPs and route the majority of their works through a
    single 'favoured' vendor per district - the classic vendor-concentration
    / possible kickback signature. All works actually routed through the
    favoured vendor for a chosen MP are labelled as the seeded anomaly, since
    the pattern only becomes suspicious in aggregate across that MP's works."""
    mp_ids = list({r["mp_id"] for r in work_rows})
    n = max(1, int(len(mp_ids) * rate_of_mps))
    concentration_mps = set(random.sample(mp_ids, min(n, len(mp_ids))))
    favoured = {}  # (mp_id, district_id) -> vendor_id

    for r in work_rows:
        if r["mp_id"] not in concentration_mps:
            continue
        if r["seeded_anomaly_type"] is not None:
            continue  # don't overwrite an existing anomaly pattern on this work
        key = (r["mp_id"], r["district_id"])
        vendors = r["vendors"]
        if not vendors:
            continue
        if key not in favoured:
            favoured[key] = random.choice(vendors)
        if random.random() < 0.72:
            r["forced_vendor_id"] = favoured[key]
            r["is_seeded_anomaly"] = 1
            r["seeded_anomaly_type"] = "vendor_concentration"


def generate_works(conn, ref, n_works=3200, anomaly_rate=0.09):
    cur = conn.cursor()
    n_anomalous = int(n_works * anomaly_rate)
    anomaly_flags = [True] * n_anomalous + [False] * (n_works - n_anomalous)
    random.shuffle(anomaly_flags)

    work_rows = []   # collect for post-hoc fragmentation/duplicate pairing
    seq_counter = {}

    for i in range(n_works):
        mp_id, state_id, mp_name = random.choice(ref["mps"])
        eligible_districts = [d for d in ref["districts"] if d[1] == state_id]
        district_id, _, district_name = random.choice(eligible_districts)
        agencies = district_agencies(ref, district_id)
        vendors = district_vendors(ref, district_id)
        if not agencies or not vendors:
            continue
        agency_id = random.choice(agencies)
        category = random.choice(WORK_CATEGORIES)
        asset_type = ASSET_TYPES[category]
        seq_counter[district_id] = seq_counter.get(district_id, 0) + 1
        description = make_description(category, district_name, seq_counter[district_id])

        recommended_date = rand_date(FISCAL_YEAR_START, date(2025, 12, 31))
        sanction_date = recommended_date + timedelta(days=random.randint(15, 90))
        estimated_cost = round(np.random.lognormal(mean=3.4, sigma=0.6), 2)  # lakh
        estimated_cost = float(np.clip(estimated_cost, 3, 120))
        sanctioned_amount = round(estimated_cost * random.uniform(0.95, 1.05), 2)

        duration_days = random.randint(90, 480)
        expected_completion = sanction_date + timedelta(days=duration_days)

        is_anom = anomaly_flags[i]
        anomaly_type = random.choice(ANOMALY_TYPES) if is_anom else None

        # ---- status & completion progression (before anomaly-specific tweaks)
        elapsed = (date(2026, 8, 31) - sanction_date).days
        if elapsed < 0:
            status = "Recommended"
        elif elapsed < duration_days * 0.15:
            status = "Sanctioned"
        elif elapsed < duration_days:
            status = "InProgress"
        else:
            status = random.choices(["Completed", "Delayed"], weights=[0.82, 0.18])[0]

        actual_completion = None
        if status == "Completed":
            actual_completion = sanction_date + timedelta(days=int(duration_days * random.uniform(0.85, 1.15)))
            if actual_completion > date(2026, 8, 31):
                actual_completion = date(2026, 8, 31)

        lat = round(random.uniform(8.4, 34.5), 5)
        lon = round(random.uniform(69.0, 89.5), 5)

        work_rows.append(dict(
            mp_id=mp_id, district_id=district_id, agency_id=agency_id,
            work_category=category, asset_type=asset_type, description=description,
            recommended_date=recommended_date.isoformat(),
            sanction_date=sanction_date.isoformat(),
            sanctioned_amount_lakh=sanctioned_amount,
            estimated_cost_lakh=estimated_cost,
            expected_completion_date=expected_completion.isoformat(),
            actual_completion_date=actual_completion.isoformat() if actual_completion else None,
            status=status, latitude=lat, longitude=lon,
            is_seeded_anomaly=1 if is_anom else 0,
            seeded_anomaly_type=anomaly_type,
            district_name=district_name, vendors=vendors, sanction_date_obj=sanction_date,
            expected_completion_obj=expected_completion,
            actual_completion_obj=actual_completion,
            duration_days=duration_days,
            forced_vendor_id=None,
        ))

    # ---- fragmentation: pick some anomalous "fragmentation" rows and clone them
    #      into 2-3 siblings with smaller amounts, same category/district/mp, close dates
    frag_rows = [r for r in work_rows if r["seeded_anomaly_type"] == "fragmentation"]
    for base in frag_rows:
        n_pieces = random.randint(2, 3)
        piece_amt = round(base["sanctioned_amount_lakh"] / (n_pieces + 1), 2)
        base["sanctioned_amount_lakh"] = piece_amt
        base["estimated_cost_lakh"] = piece_amt
        for p in range(n_pieces):
            clone = dict(base)
            clone["description"] = base["description"] + f" (Phase {p+2})"
            clone["sanction_date"] = (base["sanction_date_obj"] + timedelta(days=random.randint(1, 10))).isoformat()
            work_rows.append(clone)

    # ---- duplicate_work: clone description almost verbatim within same district
    dup_rows = [r for r in work_rows if r["seeded_anomaly_type"] == "duplicate_work"]
    for base in dup_rows:
        clone = dict(base)
        clone["description"] = base["description"]  # identical description = duplicate claim
        clone["sanction_date"] = (base["sanction_date_obj"] + timedelta(days=random.randint(5, 40))).isoformat()
        clone["mp_id"] = random.choice([m for m, s, n in ref["mps"]])
        work_rows.append(clone)

    inject_stalled_delayed(work_rows, rate=0.025)
    inject_vendor_concentration(work_rows, ref, rate_of_mps=0.12)

    # ---- insert works
    inserted = []
    for r in work_rows:
        cur.execute("""INSERT INTO works
            (mp_id, district_id, agency_id, work_category, asset_type, description,
             recommended_date, sanction_date, sanctioned_amount_lakh, estimated_cost_lakh,
             expected_completion_date, actual_completion_date, status, latitude, longitude,
             is_seeded_anomaly, seeded_anomaly_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["mp_id"], r["district_id"], r["agency_id"], r["work_category"], r["asset_type"],
             r["description"], r["recommended_date"], r["sanction_date"], r["sanctioned_amount_lakh"],
             r["estimated_cost_lakh"], r["expected_completion_date"], r["actual_completion_date"],
             r["status"], r["latitude"], r["longitude"], r["is_seeded_anomaly"], r["seeded_anomaly_type"]))
        r["work_id"] = cur.lastrowid
        inserted.append(r)

    return inserted


def generate_financials(conn, ref, works):
    cur = conn.cursor()
    exp_id_seq = 1
    report_id_seq = 1
    uc_id_seq = 1

    for w in works:
        sanction_date = date.fromisoformat(w["sanction_date"])
        vendors = w["vendors"] if w["vendors"] else district_vendors(ref, w["district_id"])
        if w.get("forced_vendor_id"):
            vendor_id = w["forced_vendor_id"]
        else:
            vendor_id = random.choice(vendors) if vendors else None
        anomaly = w["seeded_anomaly_type"]

        sanctioned = w["sanctioned_amount_lakh"]
        status = w["status"]

        # decide how much of sanctioned amount has actually been drawn down
        if status in ("Recommended", "Sanctioned"):
            drawn_fraction = random.uniform(0, 0.15)
        elif status == "InProgress":
            drawn_fraction = random.uniform(0.2, 0.85)
        elif status == "Delayed":
            drawn_fraction = random.uniform(0.4, 0.95)
        else:  # Completed
            drawn_fraction = random.uniform(0.95, 1.0)

        total_expenditure = sanctioned * drawn_fraction

        # ---- anomaly-specific financial tweaks ----
        if anomaly == "cost_overrun":
            total_expenditure = sanctioned * random.uniform(1.25, 1.9)
        elif anomaly == "ghost_asset":
            total_expenditure = sanctioned * random.uniform(0.9, 1.05)  # money spent...
        elif anomaly == "front_loaded_payment":
            pass  # handled via installment split below
        elif anomaly == "vendor_concentration":
            pass  # handled by biasing vendor choice below

        n_installments = 1 if total_expenditure <= 0 else random.randint(1, 4)
        if anomaly == "front_loaded_payment":
            n_installments = max(n_installments, 2)

        # If this work should feed a vendor-concentration pattern, bias toward
        # a single "favoured" vendor for this MP across many works (handled globally below)
        remaining = total_expenditure
        for k in range(n_installments):
            if k == n_installments - 1:
                amt = remaining
            else:
                if anomaly == "front_loaded_payment" and k == 0:
                    amt = remaining * random.uniform(0.7, 0.9)
                else:
                    amt = remaining * random.uniform(0.2, 0.5)
            amt = round(max(amt, 0), 2)
            remaining = round(remaining - amt, 2)

            if anomaly == "front_loaded_payment" and k == 0:
                pay_date = sanction_date + timedelta(days=random.randint(0, 3))
            elif anomaly == "year_end_rush":
                # concentrate payment near fiscal year end (Mar 31 of some year)
                fy_candidates = [date(y, 3, 25) for y in range(2022, 2027)
                                  if date(y, 3, 25) >= sanction_date]
                pay_date = random.choice(fy_candidates) if fy_candidates else sanction_date + timedelta(days=300)
            else:
                span = max((date(2026, 8, 31) - sanction_date).days, 30)
                pay_date = sanction_date + timedelta(days=random.randint(10, span))

            cur.execute("""INSERT INTO expenditures
                (work_id, vendor_id, amount_lakh, payment_date, installment_no, payment_mode, voucher_no)
                VALUES (?,?,?,?,?,?,?)""",
                (w["work_id"], vendor_id, amt, pay_date.isoformat(), k + 1,
                 random.choice(["e-transfer", "cheque", "e-transfer", "e-transfer"]),
                 f"VCH{w['work_id']:05d}{k+1}"))
            exp_id_seq += 1
            if remaining <= 0:
                break

        # ---- progress reports ----
        n_reports = random.randint(1, 4) if status != "Recommended" else 0
        phys_progress = 0.0
        fin_progress = 0.0
        target_phys = {"Sanctioned": 5, "InProgress": random.uniform(20, 75),
                        "Delayed": random.uniform(15, 55), "Completed": 100,
                        "Recommended": 0}[status]
        target_fin = (total_expenditure / sanctioned * 100) if sanctioned else 0
        target_fin = min(target_fin, 100)

        if anomaly == "ghost_asset":
            target_phys = random.uniform(2, 12)   # money spent, almost nothing built
        if anomaly == "progress_mismatch":
            target_phys = target_phys * random.uniform(0.25, 0.5)
            target_fin = min(target_fin * random.uniform(1.5, 2.2), 100)

        for r in range(n_reports):
            frac = (r + 1) / n_reports
            phys_progress = round(target_phys * frac + random.uniform(-3, 3), 1)
            fin_progress = round(target_fin * frac + random.uniform(-3, 3), 1)
            phys_progress = float(np.clip(phys_progress, 0, 100))
            fin_progress = float(np.clip(fin_progress, 0, 100))
            report_date = sanction_date + timedelta(days=int((w["duration_days"] or 200) * frac))
            cur.execute("""INSERT INTO progress_reports
                (work_id, report_date, physical_progress_pct, financial_progress_pct, remarks)
                VALUES (?,?,?,?,?)""",
                (w["work_id"], report_date.isoformat(), phys_progress, fin_progress,
                 random.choice(["On track", "Material procurement in progress",
                                 "Awaiting local body clearance", "Work in progress",
                                 "Delayed due to monsoon", "Nearing completion"])))
            report_id_seq += 1

        # ---- utilization certificate ----
        should_have_uc = status == "Completed"
        missing_uc = anomaly == "missing_utilization_cert"
        if should_have_uc and not missing_uc:
            uc_date = date.fromisoformat(w["actual_completion_date"]) + timedelta(days=random.randint(15, 75))
            cur.execute("""INSERT INTO utilization_certificates
                (work_id, submitted_date, amount_certified_lakh) VALUES (?,?,?)""",
                (w["work_id"], uc_date.isoformat(), round(total_expenditure, 2)))
            uc_id_seq += 1
        # else: no UC row -> pipeline should catch this for completed-but-uncertified works


def run(n_works=3200, anomaly_rate=0.09, reset=True):
    init_db(reset=reset)
    with connection_scope() as conn:
        ref = build_reference_data(conn)
        works = generate_works(conn, ref, n_works=n_works, anomaly_rate=anomaly_rate)
        generate_financials(conn, ref, works)
    print(f"Generated {len(works)} works "
          f"({sum(1 for w in works if w['is_seeded_anomaly'])} seeded anomalies) "
          f"across {len(ref['mps'])} MPs and {len(ref['districts'])} districts.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--works", type=int, default=3200)
    ap.add_argument("--anomaly-rate", type=float, default=0.09)
    args = ap.parse_args()
    run(n_works=args.works, anomaly_rate=args.anomaly_rate)
