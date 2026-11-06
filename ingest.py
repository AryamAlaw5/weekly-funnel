"""Build funnel.db from the daily snapshot CSVs the sheet's Apps Script commits to data/snapshots/.

Each file is one day: lead_id, source_tab, status, has_note (1 if the sheet's Notes cell is filled). Older files may lack
has_note or have a date_added column; missing has_note counts as 0 and date_added is ignored.
The latest file gives each lead's current state; the first file a lead appears in gives its first_seen date.
"""
import csv
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

from common import DB_PATH, HERE, STATUS_MAP

SNAP_DIR = Path(os.environ.get("SNAPSHOT_DIR", HERE / "data" / "snapshots"))
REQUIRED = ["lead_id", "source_tab", "status"]
CANON = {k.lower(): k for k in STATUS_MAP}


def canon(status):
    """Match a status to the map ignoring case/extra spaces; unknown statuses stay as written (and get flagged)."""
    s = " ".join(status.split())
    return CANON.get(s.lower(), s)


def read_snapshot(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED) <= set(reader.fieldnames or []):
            sys.exit(f"{path.name}: expected columns {REQUIRED}, found {reader.fieldnames}")
        return [(r["lead_id"], r["source_tab"], canon(r["status"]), r.get("has_note") == "1") for r in reader]


def main():
    files = sorted(SNAP_DIR.glob("*.csv"))
    if not files:
        sys.exit(f"no snapshot files in {SNAP_DIR}")
    for f in files:
        date.fromisoformat(f.stem)  # file names must be YYYY-MM-DD.csv

    latest, first_seen, statuses = {}, {}, set()
    for f in files:
        for lead_id, source, status, has_note in read_snapshot(f):
            latest[lead_id] = (source, status, has_note)
            first_seen.setdefault(lead_id, f.stem)
            statuses.add(status)
    as_of = files[-1].stem
    unmapped = sorted(({v[1] for v in latest.values()} | statuses) - set(STATUS_MAP))

    DB_PATH.unlink(missing_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript((HERE / "schema.sql").read_text())
    db.executemany("INSERT INTO status_map VALUES (?, ?)", STATUS_MAP.items())
    # unknown statuses still count as "added" so no lead disappears; the report flags them
    db.executemany("INSERT INTO status_map VALUES (?, 0)", [(s,) for s in unmapped])
    db.executemany("INSERT INTO meta VALUES (?, ?)", [
        ("source", "sheet"), ("as_of", as_of), ("unmapped", "|".join(unmapped)),
    ])
    db.executemany("INSERT INTO leads VALUES (?,?,?,?,?,?)",
                   [(lid, src, st, int(note), first_seen[lid], as_of) for lid, (src, st, note) in latest.items()])
    db.commit()
    print(f"{len(latest)} leads, {len(files)} snapshot days (latest {as_of}), "
          f"{len(unmapped)} unmapped status(es){': ' + ', '.join(unmapped) if unmapped else ''}")


if __name__ == "__main__":
    main()
