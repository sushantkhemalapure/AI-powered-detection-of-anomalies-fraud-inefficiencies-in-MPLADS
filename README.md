# MPLADS Sentinel

An AI-powered monitoring platform for Smart India Hackathon Problem Statement 26102: detecting anomalies, fraud indicators and execution inefficiencies in MPLADS works.

The project turns sanctions, expenditures, vendor payments, progress reports and utilization certificates into an explainable 0–100 risk score. It is built for Ministry, State Nodal, District and MP views.

## What the demo delivers

- Explainable flags for cost overrun, stalled work, ghost-asset signals, duplicate works, payment concentration, missing UCs and vendor concentration.
- Isolation Forest anomaly detection for unusual combinations that fixed rules may miss.
- Early-warning queue for likely delays and overruns before they become high-risk cases.
- Compliance monitor for overdue works, missing UCs, pending sanctions, excess spend and stale progress reports.
- AI Command Centre with an auditable situation report and safe offline fallback.
- Geo Risk Monitor for prioritising field verification by location and risk score.
- Role-scoped dashboard, case drill-down, alert workflow and CSV alert export.

## Run locally

Requirements: Python 3.10+.

Windows PowerShell:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python app.py
```

Then open http://localhost:5000.

For a fresh demo database:

```powershell
cd backend
python data_generator.py --works 3200 --anomaly-rate 0.09
python -m ml.train
python app.py
```

Linux/macOS users can run `./run.sh` from the repository root.

## Important demo note

The bundled records are synthetic because public MPLADS reporting pages do not provide a transaction-level data API. Labels in the generated data are used only to evaluate the demo model; they are never read by the detector. In a deployment, replace the generator with a governed ETL integration to the authorised MPLADS MIS.

Risk scores and alerts are prompts for human review, not findings of fraud or misconduct.

See [architecture documentation](docs/ARCHITECTURE.md) for the data flow and repository layout.
