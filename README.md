# Sfere Weekly Funnel

Funnel for the last 7, 14 and 30 days (and all time), by source tab. Leads are dated by the first daily snapshot they appear in; the sheet needs no date column.

## How data flows

1. **Sheet to repo.** `apps-script/Code.gs` runs as an Apps Script that reads the "Zid+Salla" sheet (tabs: zid, salla, Salla + Zid Linkedin). Once a day it hashes each lead
   into an anonymous ID and commits `data/snapshots/YYYY-MM-DD.csv` (lead_id, source_tab, status, has_note).
   Names, phones, emails and note text never leave Google; only a has_note flag (Notes cell filled) is exported. A lead's date is the first snapshot it appears in; leads that
   were already in the first snapshot (2026-11-04) count as first seen that day.
   Snapshots from the old Mawsool/Sfere sheet were removed from `data/snapshots/` on 2026-11-04 (still in git history).
2. **Repo to report.** `.github/workflows/report.yml` runs on every push and daily:
   - `DEMO=0`: `python ingest.py` builds `funnel.db` from `data/snapshots/*.csv` (the build fails if there are none)
   - `DEMO=1`: `python seed_fake_data.py` builds a fake-data demo
   - then `python report.py` writes `site/index.html`, which is deployed to GitHub Pages.

## Status mapping

`common.py` maps each sheet status to the furthest funnel stage it counts as. A status that is not in the
map still counts as Added and shows a yellow notice on the report, so nothing disappears silently.

## Dead

The Dead box counts leads with something in the sheet's Notes column, plus leads whose status is "Not interested". Only the count is published.

## LinkedIn card

`data/heyreach.json` holds aggregate LinkedIn campaign counts (requests sent/accepted, messages started, replies per day) from the
HeyReach campaigns, read-only and shown as its own card, separate from the sheet funnel. No lead data is stored. It is refreshed
manually, not by the daily job.

## Run locally

    python3 seed_fake_data.py && python3 report.py          # fake data
    SNAPSHOT_DIR=path/to/csvs python3 ingest.py && python3 report.py   # real snapshots
    python3 -m http.server 8765 --directory site

## Files

| File | Purpose |
|---|---|
| `apps-script/Code.gs` | runs in the sheet; pushes daily anonymous snapshots |
| `ingest.py` | snapshot CSVs to SQLite |
| `schema.sql` | tables, `status_map`, funnel-by-day and status-change views |
| `common.py` | window lengths (7/14/30 days) and the status to stage map |
| `seed_fake_data.py` | fake leads for the demo |
| `report.py` + `template.html` | builds the single-file report |
