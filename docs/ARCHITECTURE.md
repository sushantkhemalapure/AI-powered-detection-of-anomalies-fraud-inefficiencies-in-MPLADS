# MPLADS Allocation Review architecture

```text
Bundled allocation CSV
        |
        v
data_loader.py --> SQLite store --> feature engineering
                                      |
                                      v
                           Isolation Forest outlier scoring
                                      |
                                      v
                     Flask JSON API --> allocation review web app
```

## Data flow

`data_loader.py` imports the supplied MP allocation records without fabricating missing fields. The training command scores allocation amounts and stores a review score, band, and alert for high-priority statistical outliers. The web app reads those records through the Flask API and supports national, state, constituency, and MP scopes.

## Source boundary

The current CSV provides State, MP, Constituency, and Allocated Amount. It does not provide project-level sanctions, payment or vendor data, progress reports, completion dates, utilisation certificates, coordinates, or labelled review outcomes. Execution monitoring, compliance checks, geo views, and fraud classification are therefore intentionally not presented as live features.

For any future work-level expansion, integrate authorised MPLADS MIS data and add authentication, audit logging, retention controls, and a human review workflow before relying on the results operationally.
