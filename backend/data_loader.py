"""Import the bundled MPLADS allocation dataset into the local database.

The source CSV contains one allocation record per MP/constituency.  It does
not contain individual works, payments, progress reports, vendors, dates, or
fraud labels, so this importer does not manufacture any of those values.  A
minimal ``works`` row is used as an allocation observation so the existing
unsupervised pipeline can train on the real allocated amounts.  Fields absent
from the CSV stay NULL or are marked ``Not provided``.

Run from ``backend/``:
    python data_loader.py
"""

import csv
import os

from db import connection_scope, init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATASET = os.path.join(
    os.path.dirname(BASE_DIR), "dataset", "Allocated Limit for Honble MPs (3).csv"
)


def amount_to_lakh(value: str) -> float:
    """Convert the source amount in rupees to lakh, without changing it."""
    return float(value.replace(",", "").replace("₹", "").strip()) / 100_000


def load_dataset(dataset_path: str = DEFAULT_DATASET) -> int:
    """Replace the local store with records from ``dataset_path``.

    Dates are left NULL because the source has no work or sanction dates.
    """
    dataset_path = os.path.abspath(dataset_path)
    if not os.path.isfile(dataset_path):
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    with open(dataset_path, newline="", encoding="utf-8-sig") as handle:
        records = list(csv.DictReader(handle))
    if not records:
        raise ValueError("Dataset contains no records.")

    init_db(reset=True)
    states, districts, mps = {}, {}, {}
    state_id = district_id = mp_id = work_id = agency_id = 0
    source_name = os.path.basename(dataset_path)
    skipped_rows = 0

    with connection_scope() as conn:
        for record in records:
            # The supplied export includes a grand-total footer and one record
            # with no allocation. They cannot be model observations, so retain
            # neither rather than inventing a replacement amount.
            try:
                int(record["Sr. No."].strip())
                state = record["State"].strip()
                constituency = record["Constituency"].strip()
                mp_name = record["Hon'ble Members of Parliaments"].strip()
                allocation_lakh = amount_to_lakh(record["Allocated AMOUNT ( ₹ )"])
                if not all((state, constituency, mp_name)):
                    raise ValueError("missing identifying field")
            except (KeyError, TypeError, ValueError):
                skipped_rows += 1
                continue

            if state not in states:
                state_id += 1
                states[state] = state_id
                conn.execute("INSERT INTO states (state_id, name, region) VALUES (?,?,?)",
                             (state_id, state, "Not provided"))
            state_key = (states[state], constituency)
            if state_key not in districts:
                district_id += 1
                districts[state_key] = district_id
                # The source calls this a constituency; it is stored in the
                # district field solely to support the existing scoped UI.
                conn.execute("INSERT INTO districts (district_id, state_id, name) VALUES (?,?,?)",
                             (district_id, states[state], constituency))
                agency_id += 1
                conn.execute("""INSERT INTO implementing_agencies
                                (agency_id, name, district_id, agency_type)
                                VALUES (?,?,?,?)""",
                             (agency_id, "Not provided", district_id, "Not provided"))

            mp_key = (states[state], mp_name, constituency)
            if mp_key not in mps:
                mp_id += 1
                mps[mp_key] = mp_id
                conn.execute("""INSERT INTO members_of_parliament
                                (mp_id, name, house, state_id, constituency, party, term_start,
                                 annual_entitlement_lakh)
                                VALUES (?,?,?,?,?,?,?,?)""",
                             (mp_id, mp_name, "Not provided", states[state], constituency,
                              "Not provided", None, allocation_lakh))

            work_id += 1
            conn.execute("""INSERT INTO works
                            (work_id, mp_id, district_id, agency_id, work_category, asset_type,
                             description, recommended_date, sanction_date, sanctioned_amount_lakh,
                             estimated_cost_lakh, expected_completion_date, actual_completion_date,
                             status, latitude, longitude, source_file)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (work_id, mps[mp_key], districts[state_key], districts[state_key],
                          "MPLADS allocation", "Allocation record",
                          f"Allocated MPLADS limit for {mp_name} ({constituency})",
                          None, None, allocation_lakh, allocation_lakh,
                          None, None, "Allocation", None, None, source_name))

    print(f"Skipped {skipped_rows} incomplete/footer rows without creating replacement data.")
    return work_id


if __name__ == "__main__":
    count = load_dataset()
    print(f"Imported {count} real allocation records from {DEFAULT_DATASET}")
