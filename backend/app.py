"""
app.py - Flask REST API for the MPLADS AI Monitoring & Analytics Platform.

Serves:
  - JSON API under /api/*  (dashboards, works, anomalies, alerts, compliance,
    early warning, map, AI briefing)
  - The static frontend (frontend/) at /

Run:  python app.py   (after data_generator.py and `python -m ml.train` have
                        been run once - see README.md)
"""

import csv
import io
import json
import os

from flask import Flask, Response, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from db import get_connection, init_db
from insights import answer_question, build_context_pack, generate_briefing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

init_db(reset=False)


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


def query(sql, params=()):
    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def parse_scope():
    return {
        "state_id": request.args.get("state_id"),
        "district_id": request.args.get("district_id"),
        "mp_id": request.args.get("mp_id"),
    }


def apply_scope(where, params, w="w", d="d"):
    s = parse_scope()
    if s["mp_id"]:
        where.append(f"{w}.mp_id = ?")
        params.append(s["mp_id"])
    elif s["district_id"]:
        where.append(f"{w}.district_id = ?")
        params.append(s["district_id"])
    elif s["state_id"]:
        where.append(f"{d}.state_id = ?")
        params.append(s["state_id"])
    return where, params


def where_sql(where):
    return ("WHERE " + " AND ".join(where)) if where else ""


WORK_JOINS = """
    FROM works w
    JOIN districts d ON w.district_id = d.district_id
    JOIN states s ON d.state_id = s.state_id
    JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
"""


# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    full = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(full):
        return send_from_directory(FRONTEND_DIR, path)
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# Reference / filter data
# ---------------------------------------------------------------------------

@app.route("/api/meta/states")
def meta_states():
    return jsonify(query("SELECT state_id, name, region FROM states ORDER BY name"))


@app.route("/api/meta/districts")
def meta_districts():
    state_id = request.args.get("state_id")
    if state_id:
        return jsonify(query(
            "SELECT district_id, state_id, name FROM districts WHERE state_id=? ORDER BY name",
            (state_id,),
        ))
    return jsonify(query("SELECT district_id, state_id, name FROM districts ORDER BY name"))


@app.route("/api/meta/mps")
def meta_mps():
    state_id = request.args.get("state_id")
    sql = """SELECT mp.mp_id, mp.name, mp.house, mp.party, mp.constituency, s.name as state_name
              FROM members_of_parliament mp JOIN states s ON mp.state_id = s.state_id"""
    params = ()
    if state_id:
        sql += " WHERE mp.state_id = ?"
        params = (state_id,)
    sql += " ORDER BY mp.name"
    return jsonify(query(sql, params))


@app.route("/api/meta/categories")
def meta_categories():
    return jsonify([r["work_category"] for r in query(
        "SELECT DISTINCT work_category FROM works ORDER BY work_category"
    )])


# ---------------------------------------------------------------------------
# Dashboard summary (role-aware: ministry / state / district / mp)
# ---------------------------------------------------------------------------

@app.route("/api/dashboard/summary")
def dashboard_summary():
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    base_join = "FROM works w JOIN districts d ON w.district_id = d.district_id " \
                "LEFT JOIN risk_scores rs ON rs.work_id = w.work_id"

    work_totals = query_one(f"""
        SELECT COUNT(*) as total_works,
               COALESCE(SUM(w.sanctioned_amount_lakh),0) as total_sanctioned_lakh,
               SUM(CASE WHEN w.status='Completed' THEN 1 ELSE 0 END) as completed_works,
               SUM(CASE WHEN w.status='Delayed' THEN 1 ELSE 0 END) as delayed_works,
               SUM(CASE WHEN w.status='InProgress' THEN 1 ELSE 0 END) as inprogress_works,
               SUM(CASE WHEN w.status='Sanctioned' THEN 1 ELSE 0 END) as sanctioned_works,
               SUM(CASE WHEN w.status='Recommended' THEN 1 ELSE 0 END) as recommended_works
        {base_join} {wsql}
    """, tuple(params))

    work_ids = [r["work_id"] for r in query(f"SELECT w.work_id {base_join} {wsql}", tuple(params))]
    if work_ids:
        placeholders = ",".join("?" * len(work_ids))
        exp_total = query_one(
            f"SELECT COALESCE(SUM(amount_lakh),0) as total FROM expenditures WHERE work_id IN ({placeholders})",
            tuple(work_ids),
        )
        total_expenditure_lakh = exp_total["total"]
    else:
        total_expenditure_lakh = 0

    totals = dict(work_totals)
    totals["total_expenditure_lakh"] = total_expenditure_lakh

    risk_breakdown = query(f"""
        SELECT COALESCE(rs.risk_band,'Unscored') as risk_band, COUNT(*) as count
        {base_join} {wsql}
        GROUP BY COALESCE(rs.risk_band,'Unscored')
    """, tuple(params))

    top_categories = query(f"""
        SELECT w.work_category, COUNT(*) as count, SUM(w.sanctioned_amount_lakh) as total_lakh
        {base_join} {wsql}
        GROUP BY w.work_category ORDER BY total_lakh DESC LIMIT 8
    """, tuple(params))

    alert_sql = f"""
        SELECT COUNT(*) as open_alerts
        FROM alerts a JOIN works w ON a.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        {wsql} {"AND" if where else "WHERE"} a.status='Open'
    """
    open_alerts = query_one(alert_sql, tuple(params))

    early = query_one(f"""
        SELECT COUNT(*) as c
        FROM predictions p
        JOIN works w ON p.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        {wsql} {"AND" if where else "WHERE"}
            w.status IN ('Recommended','Sanctioned','InProgress','Delayed')
            AND p.early_warning_score >= 45
            AND COALESCE(rs.risk_band,'Low') NOT IN ('High','Critical')
    """, tuple(params))

    return jsonify({
        "totals": totals,
        "risk_breakdown": risk_breakdown,
        "top_categories": top_categories,
        "open_alerts": open_alerts["open_alerts"] if open_alerts else 0,
        "early_warning_count": early["c"] if early else 0,
    })


@app.route("/api/dashboard/trend")
def dashboard_trend():
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    rows = query(f"""
        SELECT strftime('%Y-%m', w.sanction_date) as month,
               SUM(w.sanctioned_amount_lakh) as sanctioned_lakh
        FROM works w JOIN districts d ON w.district_id = d.district_id
        {wsql}
        GROUP BY month ORDER BY month
    """, tuple(params))
    exp_rows = query(f"""
        SELECT strftime('%Y-%m', e.payment_date) as month, SUM(e.amount_lakh) as expenditure_lakh
        FROM expenditures e
        JOIN works w ON e.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        {wsql}
        GROUP BY month ORDER BY month
    """, tuple(params))
    exp_map = {r["month"]: r["expenditure_lakh"] for r in exp_rows}
    months = sorted(set([r["month"] for r in rows if r["month"]] + list(exp_map.keys())))
    out = []
    san_map = {r["month"]: r["sanctioned_lakh"] for r in rows}
    for m in months:
        out.append({
            "month": m,
            "sanctioned_lakh": san_map.get(m, 0) or 0,
            "expenditure_lakh": exp_map.get(m, 0) or 0,
        })
    return jsonify(out)


@app.route("/api/dashboard/status")
def dashboard_status():
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    rows = query(f"""
        SELECT w.status, COUNT(*) as count
        FROM works w JOIN districts d ON w.district_id = d.district_id
        {wsql}
        GROUP BY w.status
    """, tuple(params))
    return jsonify(rows)


@app.route("/api/dashboard/state-ranking")
def dashboard_state_ranking():
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    rows = query(f"""
        SELECT s.name as state_name, COUNT(w.work_id) as total_works,
               ROUND(AVG(rs.risk_score),1) as avg_risk_score,
               SUM(CASE WHEN rs.risk_band IN ('High','Critical') THEN 1 ELSE 0 END) as high_risk_works,
               ROUND(SUM(w.sanctioned_amount_lakh),1) as total_sanctioned_lakh,
               SUM(CASE WHEN w.status='Delayed' THEN 1 ELSE 0 END) as delayed_works,
               ROUND(AVG(p.delay_probability)*100, 1) as avg_delay_prob_pct
        FROM works w
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        LEFT JOIN predictions p ON p.work_id = w.work_id
        {wsql}
        GROUP BY s.name ORDER BY avg_risk_score DESC
    """, tuple(params))
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Works listing + detail
# ---------------------------------------------------------------------------

@app.route("/api/works")
def list_works():
    risk_band = request.args.get("risk_band")
    status = request.args.get("status")
    category = request.args.get("category")
    search = request.args.get("q")
    sort = request.args.get("sort", "risk_score_desc")
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 25)), 200)

    where, params = apply_scope([], [])
    if risk_band:
        where.append("rs.risk_band = ?"); params.append(risk_band)
    if status:
        where.append("w.status = ?"); params.append(status)
    if category:
        where.append("w.work_category = ?"); params.append(category)
    if search:
        where.append("(w.description LIKE ? OR mp.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    wsql = where_sql(where)

    sort_map = {
        "risk_score_desc": "rs.risk_score DESC",
        "risk_score_asc": "rs.risk_score ASC",
        "amount_desc": "w.sanctioned_amount_lakh DESC",
        "date_desc": "w.sanction_date DESC",
        "warning_desc": "p.early_warning_score DESC",
    }
    order_sql = sort_map.get(sort, "rs.risk_score DESC")

    base = f"""FROM works w
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        LEFT JOIN predictions p ON p.work_id = w.work_id
        {wsql}"""

    total = query_one(f"SELECT COUNT(*) as c {base}", tuple(params))["c"]

    rows = query(f"""
        SELECT w.work_id, w.description, w.work_category, w.status,
               w.sanctioned_amount_lakh, w.sanction_date, w.expected_completion_date,
               w.latitude, w.longitude,
               mp.name as mp_name, s.name as state_name, d.name as district_name,
               COALESCE(rs.risk_score,0) as risk_score, COALESCE(rs.risk_band,'Unscored') as risk_band,
               COALESCE(p.delay_probability,0) as delay_probability,
               COALESCE(p.overrun_probability,0) as overrun_probability,
               COALESCE(p.early_warning_score,0) as early_warning_score
        {base}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
    """, tuple(params) + (page_size, (page - 1) * page_size))

    return jsonify({"total": total, "page": page, "page_size": page_size, "items": rows})


@app.route("/api/works/<int:work_id>")
def work_detail(work_id):
    work = query_one("""
        SELECT w.work_id, w.mp_id, w.district_id, w.agency_id, w.work_category, w.asset_type,
               w.description, w.recommended_date, w.sanction_date, w.sanctioned_amount_lakh,
               w.estimated_cost_lakh, w.expected_completion_date, w.actual_completion_date,
               w.status, w.latitude, w.longitude,
               mp.name as mp_name, mp.house, mp.party, s.name as state_name,
               d.name as district_name, ia.name as agency_name
        FROM works w
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN implementing_agencies ia ON w.agency_id = ia.agency_id
        WHERE w.work_id = ?
    """, (work_id,))
    if not work:
        return jsonify({"error": "not found"}), 404

    expenditures = query("""
        SELECT e.*, v.name as vendor_name FROM expenditures e
        LEFT JOIN vendors v ON e.vendor_id = v.vendor_id
        WHERE e.work_id = ? ORDER BY e.payment_date
    """, (work_id,))
    progress = query(
        "SELECT * FROM progress_reports WHERE work_id=? ORDER BY report_date", (work_id,)
    )
    uc = query_one("SELECT * FROM utilization_certificates WHERE work_id=?", (work_id,))
    risk = query_one("SELECT * FROM risk_scores WHERE work_id=?", (work_id,))
    if risk and risk.get("triggered_rules"):
        risk["triggered_rules"] = json.loads(risk["triggered_rules"])
    prediction = query_one("SELECT * FROM predictions WHERE work_id=?", (work_id,))
    alerts = query("SELECT * FROM alerts WHERE work_id=? ORDER BY created_at DESC", (work_id,))

    return jsonify({
        "work": work, "expenditures": expenditures, "progress": progress,
        "utilization_certificate": uc, "risk": risk, "prediction": prediction,
        "alerts": alerts,
    })


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------

@app.route("/api/anomalies")
def list_anomalies():
    limit = min(int(request.args.get("limit", 50)), 500)
    category = request.args.get("category")
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    rows = query(f"""
        SELECT rs.work_id, rs.risk_score, rs.risk_band, rs.isolation_score,
               rs.triggered_rules, rs.explanation,
               w.description, w.work_category, w.status, w.sanctioned_amount_lakh,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        FROM risk_scores rs
        JOIN works w ON rs.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        {wsql}
        ORDER BY rs.risk_score DESC
        LIMIT ?
    """, tuple(params) + (limit * 3 if category else limit,))
    for r in rows:
        r["triggered_rules"] = json.loads(r["triggered_rules"]) if r["triggered_rules"] else []
    if category:
        rows = [r for r in rows if category in r["triggered_rules"]][:limit]
    return jsonify(rows)


@app.route("/api/anomalies/rule-frequency")
def anomaly_rule_frequency():
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    rows = query(f"""
        SELECT rs.triggered_rules
        FROM risk_scores rs
        JOIN works w ON rs.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        {wsql}
        {"AND" if where else "WHERE"} rs.triggered_rules != '[]'
    """, tuple(params))
    counts = {}
    for r in rows:
        for code in json.loads(r["triggered_rules"]):
            counts[code] = counts.get(code, 0) + 1
    return jsonify([{"rule": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])])


@app.route("/api/model/evaluation")
def model_evaluation():
    path = os.path.join(BASE_DIR, "ml", "artifacts", "evaluation_report.json")
    if not os.path.exists(path):
        return jsonify(None)
    with open(path) as f:
        return jsonify(json.load(f))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.route("/api/alerts")
def list_alerts():
    severity = request.args.get("severity")
    status = request.args.get("status", "Open")
    limit = min(int(request.args.get("limit", 100)), 500)
    where, params = apply_scope([], [])
    if severity:
        where.append("a.severity = ?"); params.append(severity)
    if status and status != "All":
        where.append("a.status = ?"); params.append(status)
    wsql = where_sql(where)
    rows = query(f"""
        SELECT a.*, w.description, w.work_category, mp.name as mp_name,
               s.name as state_name, d.name as district_name
        FROM alerts a
        JOIN works w ON a.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        {wsql}
        ORDER BY CASE a.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
                 a.created_at DESC
        LIMIT ?
    """, tuple(params) + (limit,))
    return jsonify(rows)


@app.route("/api/alerts/<int:alert_id>/status", methods=["POST"])
def update_alert_status(alert_id):
    payload = request.get_json(force=True) or {}
    new_status = payload.get("status")
    if new_status not in ("Open", "Under Review", "Resolved", "Dismissed"):
        return jsonify({"error": "invalid status"}), 400
    conn = get_connection()
    try:
        conn.execute("UPDATE alerts SET status=? WHERE alert_id=?", (new_status, alert_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/export/alerts.csv")
def export_alerts_csv():
    where, params = apply_scope([], [])
    status = request.args.get("status", "Open")
    if status and status != "All":
        where.append("a.status = ?"); params.append(status)
    wsql = where_sql(where)
    rows = query(f"""
        SELECT a.alert_id, a.severity, a.category, a.status, a.message, a.created_at,
               w.work_id, w.description, w.work_category, w.sanctioned_amount_lakh,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        FROM alerts a
        JOIN works w ON a.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        {wsql}
        ORDER BY a.severity, a.created_at DESC
    """, tuple(params))
    buf = io.StringIO()
    fields = ["alert_id", "severity", "category", "status", "work_id", "description",
              "work_category", "sanctioned_amount_lakh", "mp_name", "state_name",
              "district_name", "message", "created_at"]
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=mplads_alerts.csv"},
    )


# ---------------------------------------------------------------------------
# Early warning (predictive)
# ---------------------------------------------------------------------------

@app.route("/api/insights/early-warning")
def early_warning():
    limit = min(int(request.args.get("limit", 60)), 300)
    where, params = apply_scope([], [])
    where.append("w.status IN ('Recommended','Sanctioned','InProgress','Delayed')")
    wsql = where_sql(where)
    rows = query(f"""
        SELECT p.work_id, p.delay_probability, p.overrun_probability, p.early_warning_score,
               p.recommended_action,
               w.description, w.work_category, w.status, w.sanctioned_amount_lakh,
               w.expected_completion_date,
               mp.name as mp_name, s.name as state_name, d.name as district_name,
               COALESCE(rs.risk_band,'Unscored') as risk_band, COALESCE(rs.risk_score,0) as risk_score
        FROM predictions p
        JOIN works w ON p.work_id = w.work_id
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        {wsql}
        ORDER BY p.early_warning_score DESC
        LIMIT ?
    """, tuple(params) + (limit,))
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Compliance monitor (MPLADS guideline checks)
# ---------------------------------------------------------------------------

@app.route("/api/insights/compliance")
def compliance():
    where, params = apply_scope([], [])
    wsql = where_sql(where)

    one_year = query(f"""
        SELECT w.work_id, w.description, w.status, w.sanction_date, w.sanctioned_amount_lakh,
               CAST(julianday('now') - julianday(w.sanction_date) AS INT) as days_open,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        {WORK_JOINS} {wsql}
        {"AND" if where else "WHERE"}
            w.status IN ('Sanctioned','InProgress','Delayed')
            AND julianday('now') - julianday(w.sanction_date) > 365
        ORDER BY days_open DESC LIMIT 80
    """, tuple(params))

    missing_uc = query(f"""
        SELECT w.work_id, w.description, w.status, w.sanctioned_amount_lakh, w.actual_completion_date,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        {WORK_JOINS} {wsql}
        {"AND" if where else "WHERE"}
            w.status = 'Completed'
            AND w.work_id NOT IN (SELECT work_id FROM utilization_certificates)
        ORDER BY w.actual_completion_date DESC LIMIT 80
    """, tuple(params))

    pending = query(f"""
        SELECT w.work_id, w.description, w.status, w.recommended_date, w.sanctioned_amount_lakh,
               CAST(julianday('now') - julianday(w.recommended_date) AS INT) as days_pending,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        {WORK_JOINS} {wsql}
        {"AND" if where else "WHERE"}
            w.status = 'Recommended'
            AND julianday('now') - julianday(w.recommended_date) > 90
        ORDER BY days_pending DESC LIMIT 80
    """, tuple(params))

    overspend = query(f"""
        SELECT w.work_id, w.description, w.status, w.sanctioned_amount_lakh,
               ROUND(SUM(e.amount_lakh),2) as spent_lakh,
               ROUND(SUM(e.amount_lakh) - w.sanctioned_amount_lakh, 2) as excess_lakh,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        {WORK_JOINS}
        JOIN expenditures e ON e.work_id = w.work_id
        {wsql}
        GROUP BY w.work_id
        HAVING SUM(e.amount_lakh) > w.sanctioned_amount_lakh * 1.05
        ORDER BY excess_lakh DESC LIMIT 80
    """, tuple(params))

    stale = query(f"""
        SELECT w.work_id, w.description, w.status, w.sanction_date, w.sanctioned_amount_lakh,
               mp.name as mp_name, s.name as state_name, d.name as district_name
        {WORK_JOINS} {wsql}
        {"AND" if where else "WHERE"}
            w.status IN ('InProgress','Delayed')
            AND julianday('now') - julianday(w.sanction_date) > 60
            AND w.work_id NOT IN (SELECT work_id FROM progress_reports)
        LIMIT 80
    """, tuple(params))

    summary = {
        "one_year_overdue": query_one(f"""
            SELECT COUNT(*) as c {WORK_JOINS} {wsql}
            {"AND" if where else "WHERE"} w.status IN ('Sanctioned','InProgress','Delayed')
            AND julianday('now') - julianday(w.sanction_date) > 365
        """, tuple(params))["c"],
        "missing_uc": query_one(f"""
            SELECT COUNT(*) as c {WORK_JOINS} {wsql}
            {"AND" if where else "WHERE"} w.status='Completed'
            AND w.work_id NOT IN (SELECT work_id FROM utilization_certificates)
        """, tuple(params))["c"],
        "pending_sanction": query_one(f"""
            SELECT COUNT(*) as c {WORK_JOINS} {wsql}
            {"AND" if where else "WHERE"} w.status='Recommended'
            AND julianday('now') - julianday(w.recommended_date) > 90
        """, tuple(params))["c"],
        "expenditure_over_sanction": query_one(f"""
            SELECT COUNT(*) as c FROM (
                SELECT w.work_id {WORK_JOINS}
                JOIN expenditures e ON e.work_id = w.work_id
                {wsql}
                GROUP BY w.work_id
                HAVING SUM(e.amount_lakh) > w.sanctioned_amount_lakh * 1.05
            )
        """, tuple(params))["c"],
        "stale_progress": query_one(f"""
            SELECT COUNT(*) as c {WORK_JOINS} {wsql}
            {"AND" if where else "WHERE"} w.status IN ('InProgress','Delayed')
            AND julianday('now') - julianday(w.sanction_date) > 60
            AND w.work_id NOT IN (SELECT work_id FROM progress_reports)
        """, tuple(params))["c"],
    }

    return jsonify({
        "summary": summary,
        "one_year_overdue": one_year,
        "missing_uc": missing_uc,
        "pending_sanction": pending,
        "expenditure_over_sanction": overspend,
        "stale_progress": stale,
    })


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

@app.route("/api/map/works")
def map_works():
    where, params = apply_scope([], [])
    risk_band = request.args.get("risk_band")
    if risk_band:
        where.append("rs.risk_band = ?"); params.append(risk_band)
    wsql = where_sql(where)
    rows = query(f"""
        SELECT w.work_id, w.description, w.work_category, w.status,
               w.sanctioned_amount_lakh, w.latitude, w.longitude,
               mp.name as mp_name, s.name as state_name, d.name as district_name,
               COALESCE(rs.risk_band,'Unscored') as risk_band,
               COALESCE(rs.risk_score,0) as risk_score
        FROM works w
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        JOIN members_of_parliament mp ON w.mp_id = mp.mp_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        {wsql}
        {"AND" if where else "WHERE"} w.latitude IS NOT NULL AND w.longitude IS NOT NULL
        ORDER BY rs.risk_score DESC
        LIMIT 1500
    """, tuple(params))
    return jsonify(rows)


# ---------------------------------------------------------------------------
# AI briefing / Q&A (SpaceXAI when keyed, template otherwise)
# ---------------------------------------------------------------------------

def _briefing_inputs():
    # Reuse existing query functions by calling the same SQL with current scope.
    summary = dashboard_summary().get_json()
    where, params = apply_scope([], [])
    wsql = where_sql(where)
    ranking = query(f"""
        SELECT s.name as state_name, COUNT(w.work_id) as total_works,
               ROUND(AVG(rs.risk_score),1) as avg_risk_score,
               SUM(CASE WHEN rs.risk_band IN ('High','Critical') THEN 1 ELSE 0 END) as high_risk_works
        FROM works w
        JOIN districts d ON w.district_id = d.district_id
        JOIN states s ON d.state_id = s.state_id
        LEFT JOIN risk_scores rs ON rs.work_id = w.work_id
        {wsql}
        GROUP BY s.name ORDER BY avg_risk_score DESC LIMIT 5
    """, tuple(params))
    rule_freq = anomaly_rule_frequency().get_json()
    warnings = early_warning().get_json()
    compliance_data = compliance().get_json()
    alerts = list_alerts().get_json()
    return summary, ranking, rule_freq, warnings, compliance_data, alerts


@app.route("/api/insights/briefing")
def insights_briefing():
    role = request.args.get("role", "ministry")
    summary, ranking, rule_freq, warnings, compliance_data, alerts = _briefing_inputs()
    context = build_context_pack(summary, ranking, rule_freq, warnings, compliance_data, alerts)
    result = generate_briefing(context, role=role)
    result["context"] = context
    return jsonify(result)


@app.route("/api/insights/ask", methods=["POST"])
def insights_ask():
    payload = request.get_json(force=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question required"}), 400
    summary, ranking, rule_freq, warnings, compliance_data, alerts = _briefing_inputs()
    context = build_context_pack(summary, ranking, rule_freq, warnings, compliance_data, alerts)
    result = answer_question(question, context)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
