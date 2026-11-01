# Weekly Funnel Report

Weekly outreach funnel, grouped by the week of Date Added.

## How data flows

1. **Sheet to repo.** `apps-script/Code.gs` runs inside the Sfere sheet. Once a day it hashes each lead
   into an anonymous ID and commits `data/snapshots/YYYY-MM-DD.csv` (lead_id, source_tab, date_added, status).
   Names, phones, emails and notes never leave Google.
2. **Repo to report.** `.github/workflows/report.yml` runs on every push and daily:
   - if `data/snapshots/*.csv` exists: `python ingest.py` builds `funnel.db` from the snapshots
   - otherwise: `python seed_fake_data.py` builds a fake-data demo
   - then `python report.py` writes `site/index.html`, which is deployed to GitHub Pages.

## Status mapping

`common.py` maps each sheet status to the furthest funnel stage it counts as. A status that is not in the
map still counts as Added and shows a yellow notice on the report, so nothing disappears silently.

## Run locally

    python3 seed_fake_data.py && python3 report.py          # fake data
    SNAPSHOT_DIR=path/to/csvs python3 ingest.py && python3 report.py   # real snapshots
    python3 -m http.server 8765 --directory site

## Files

| File | Purpose |
|---|---|
| `apps-script/Code.gs` | runs in the sheet; pushes daily anonymous snapshots |
| `ingest.py` | snapshot CSVs to SQLite |
| `schema.sql` | tables, `status_map`, funnel and status-change views |
| `common.py` | week start day (Sunday) and the status to stage map |
| `seed_fake_data.py` | fake leads for the demo |
| `report.py` + `template.html` | builds the single-file report |
