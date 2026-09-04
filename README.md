# MPLADS Allocation Review

A source-backed explorer for the bundled MPLADS MP allocation-limit dataset. It lets a reviewer browse allocation records, search MPs, compare states, examine statistically unusual allocation amounts, track review alerts, and export the current allocation register.

## Included features

- Allocation record explorer with search, sorting, filters, drill-down, and CSV export.
- MP directory and state-level allocation comparison.
- Allocation distribution and source-coverage report.
- Explainable outlier-review queue using an unsupervised Isolation Forest.
- Review-alert workflow: Open, Under Review, Resolved, or Dismissed.

## Important data boundary

The bundled CSV is imported directly from `dataset/Allocated Limit for Honble MPs (3).csv`; no random or synthetic records are generated. It contains State, MP, Constituency, and Allocated Amount. Its total footer and incomplete row are skipped, leaving 542 usable records.

It does not contain individual project works, payments, dates, vendors, utilisation certificates, progress reports, verified coordinates, or confirmed anomaly labels. Therefore this version identifies unusual allocation patterns only. Scores and alerts are prompts to verify the source and approval record; they are not findings of fraud or misconduct.

## Run locally

Requirements: Python 3.10+.

From the repository root on Windows:

```powershell
.\run.ps1
```

Or run the steps manually:

```powershell
cd backend
..\venv\Scripts\python.exe data_loader.py
..\venv\Scripts\python.exe -m ml.train
..\venv\Scripts\python.exe app.py
```

Open http://localhost:5000.

See [architecture documentation](docs/ARCHITECTURE.md) for the data flow.
