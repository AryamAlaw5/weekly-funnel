# Weekly Funnel Report

Weekly outreach funnel, grouped by the week of Date Added.

## How data flows

1. **Sheet to repo.** `apps-script/Code.gs` runs as an Apps Script that reads the "Zid+Salla" sheet (tabs: zid, salla, Salla + Zid Linkedin). Once a day it hashes each lead
   into an anonymous ID and commits `data/snapshots/YYYY-MM-DD.csv` (lead_id, source_tab, date_added, status).
   Names, phones, emails and notes never leave Google. The sheet has no Date Added column yet, so every lead is dated
   2026-11-02 (`DEFAULT_DATE_ADDED`); add a `Date Added` column and real dates are used automatically.
   Snapshots from the old Mawsool/Sfere sheet were removed from `data/snapshots/` on 2026-11-04 (still in git history).
2. **Repo to report.** `.github/workflows/report.yml` runs on every push and daily:
   - `DEMO=0`: `python ingest.py` builds `funnel.db` from `data/snapshots/*.csv` (the build fails if there are none)
   - `DEMO=1`: `python seed_fake_data.py` builds a fake-data demo
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
