# MPLADS Sentinel architecture

```text
Data sources / ETL
        |
        v
SQLite operational store
(works, sanctions, payments, progress, UCs, vendors)
        |
        +--> Feature engineering --> Rule engine + Isolation Forest --> risk scores / alerts
        |                                                        |
        |                                                        +--> delay and overrun early-warning scores
        v
Flask API and decision-support service
        |
        v
Role-scoped web dashboard
Ministry | State Nodal Authority | District Authority | MP
```

## Repository layout

```text
mplads-ai-platform/
├── backend/
│   ├── app.py                 # REST API and static-app host
│   ├── db.py                  # portable MPLADS data schema
│   ├── data_generator.py      # reproducible synthetic demo data
│   ├── insights.py            # auditable AI briefing / Q&A fallback
│   ├── ml/
│   │   ├── features.py        # transaction-to-feature pipeline
│   │   ├── risk_engine.py     # explainable anomaly rules + risk fusion
│   │   ├── predict.py         # early-warning predictors
│   │   └── train.py           # training, scoring and evaluation job
│   └── data/                  # SQLite store (replace with production ETL target)
├── frontend/
│   ├── index.html             # role-aware app shell
│   ├── css/style.css          # responsive design system
│   └── js/pages/              # independently testable dashboard views
├── docs/
│   └── ARCHITECTURE.md
├── README.md
└── run.sh
```

## Production hand-off

The synthetic generator is only a demonstration adapter. In production, an ETL connector should validate data from the MPLADS MIS and write the same logical entities: work recommendation/sanction, payments, progress reports, vendors, assets and utilization certificates. Access must be protected with SSO/RBAC, audit logs, encryption, and a human review workflow. Risk signals are decision support—not determinations of fraud.
