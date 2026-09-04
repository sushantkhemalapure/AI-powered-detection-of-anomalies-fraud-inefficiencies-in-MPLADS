"""
db.py - SQLite schema definition and connection helper for the MPLADS AI
Monitoring Platform.

We deliberately use Python's built-in sqlite3 module (no ORM) so the whole
backend runs with nothing more than Flask + pandas + scikit-learn. This
keeps the project trivially deployable ("pip install -r requirements.txt"
and go) instead of depending on a running Postgres/MySQL instance.

The schema mirrors, at a simplified level, the real-world MPLADS data
model: a Member of Parliament recommends "works" which are executed by an
"implementing agency" in a district, funded via "sanctions" against the
MP's annual entitlement, drawn down through "expenditures" (payments to
vendors), tracked with periodic "progress reports" and closed out with a
"utilization certificate".
"""

import os
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "mplads.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS states (
    state_id     INTEGER PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    region       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS districts (
    district_id  INTEGER PRIMARY KEY,
    state_id     INTEGER NOT NULL REFERENCES states(state_id),
    name         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members_of_parliament (
    mp_id           INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    house            TEXT NOT NULL CHECK(house IN ('Lok Sabha','Rajya Sabha')),
    state_id         INTEGER NOT NULL REFERENCES states(state_id),
    constituency     TEXT,
    party            TEXT,
    term_start       TEXT,
    annual_entitlement_lakh REAL NOT NULL DEFAULT 500.0
);

CREATE TABLE IF NOT EXISTS implementing_agencies (
    agency_id    INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    district_id  INTEGER NOT NULL REFERENCES districts(district_id),
    agency_type  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
    vendor_id     INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    registration_no TEXT,
    district_id   INTEGER REFERENCES districts(district_id),
    risk_flag     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS works (
    work_id                INTEGER PRIMARY KEY,
    mp_id                  INTEGER NOT NULL REFERENCES members_of_parliament(mp_id),
    district_id            INTEGER NOT NULL REFERENCES districts(district_id),
    agency_id              INTEGER NOT NULL REFERENCES implementing_agencies(agency_id),
    work_category          TEXT NOT NULL,
    asset_type             TEXT NOT NULL,
    description             TEXT NOT NULL,
    recommended_date        TEXT NOT NULL,
    sanction_date            TEXT,
    sanctioned_amount_lakh   REAL NOT NULL,
    estimated_cost_lakh      REAL NOT NULL,
    expected_completion_date TEXT,
    actual_completion_date   TEXT,
    status                   TEXT NOT NULL CHECK(status IN
                              ('Recommended','Sanctioned','InProgress','Completed','Delayed','Dropped')),
    latitude                 REAL,
    longitude                REAL,
    -- ground-truth label, used only for offline model evaluation / demo credibility.
    -- The detection pipeline itself NEVER reads this column - it is unsupervised.
    is_seeded_anomaly        INTEGER NOT NULL DEFAULT 0,
    seeded_anomaly_type      TEXT
);

CREATE TABLE IF NOT EXISTS expenditures (
    expenditure_id  INTEGER PRIMARY KEY,
    work_id         INTEGER NOT NULL REFERENCES works(work_id),
    vendor_id       INTEGER REFERENCES vendors(vendor_id),
    amount_lakh     REAL NOT NULL,
    payment_date    TEXT NOT NULL,
    installment_no  INTEGER NOT NULL,
    payment_mode    TEXT NOT NULL,
    voucher_no      TEXT
);

CREATE TABLE IF NOT EXISTS progress_reports (
    report_id             INTEGER PRIMARY KEY,
    work_id               INTEGER NOT NULL REFERENCES works(work_id),
    report_date           TEXT NOT NULL,
    physical_progress_pct REAL NOT NULL,
    financial_progress_pct REAL NOT NULL,
    remarks               TEXT
);

CREATE TABLE IF NOT EXISTS utilization_certificates (
    uc_id           INTEGER PRIMARY KEY,
    work_id         INTEGER NOT NULL REFERENCES works(work_id),
    submitted_date  TEXT,
    amount_certified_lakh REAL
);

-- Populated by the ML pipeline (backend/ml/train.py). Kept as its own
-- table so the API layer never has to re-run inference on a request.
CREATE TABLE IF NOT EXISTS risk_scores (
    work_id           INTEGER PRIMARY KEY REFERENCES works(work_id),
    risk_score        REAL NOT NULL,
    risk_band         TEXT NOT NULL,
    isolation_score   REAL NOT NULL,
    triggered_rules   TEXT NOT NULL,     -- JSON list of rule codes that fired
    explanation       TEXT NOT NULL,     -- human-readable summary
    computed_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id     INTEGER PRIMARY KEY,
    work_id      INTEGER NOT NULL REFERENCES works(work_id),
    severity     TEXT NOT NULL CHECK(severity IN ('Low','Medium','High','Critical')),
    category     TEXT NOT NULL,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open','Under Review','Resolved','Dismissed'))
);

-- Populated by the predictive layer (backend/ml/predict.py via train.py).
CREATE TABLE IF NOT EXISTS predictions (
    work_id              INTEGER PRIMARY KEY REFERENCES works(work_id),
    delay_probability    REAL NOT NULL,
    overrun_probability  REAL NOT NULL,
    early_warning_score  REAL NOT NULL,
    recommended_action   TEXT NOT NULL,
    computed_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_works_mp ON works(mp_id);
CREATE INDEX IF NOT EXISTS idx_works_district ON works(district_id);
CREATE INDEX IF NOT EXISTS idx_expenditures_work ON expenditures(work_id);
CREATE INDEX IF NOT EXISTS idx_progress_work ON progress_reports(work_id);
CREATE INDEX IF NOT EXISTS idx_alerts_work ON alerts(work_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
"""


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection_scope():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(reset: bool = False):
    """Create the database file and tables. If reset=True, wipes any
    existing database first (used when regenerating synthetic data)."""
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with connection_scope() as conn:
        conn.executescript(SCHEMA)
    return DB_PATH


if __name__ == "__main__":
    path = init_db(reset=True)
    print(f"Initialized empty database at {path}")
