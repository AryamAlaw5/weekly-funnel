"""Read funnel.db and write the report page (data embedded as JSON, rendered by template.html)."""
import json
import os
import sqlite3
from pathlib import Path

from common import DB_PATH, HERE, SHEET_URL, WINDOWS

KEYS = ["added", "message_sent", "contacted", "replied", "meeting", "won", "dead", "dead_with_note"]
STAGES = [
    {"key": "added", "label": "Leads"},
    {"key": "message_sent", "label": "Connected"},
    {"key": "replied", "label": "Replied"},
    {"key": "meeting", "label": "Demo"},
    {"key": "won", "label": "Won"},
]


def main():
    db = sqlite3.connect(DB_PATH)
    meta = dict(db.execute("SELECT key, value FROM meta"))
    funnel = [
        {"day": d, "source": s, **dict(zip(KEYS, vals))}
        for d, s, *vals in db.execute(
            f"SELECT first_seen, source_tab, {', '.join(KEYS)} FROM v_funnel_by_day ORDER BY first_seen")
    ]

    heyreach_file = HERE / "data" / "heyreach.json"
    data = {
        "asOf": meta["as_of"],
        "fake": meta["source"] == "fake",
        "unmapped": [s for s in meta["unmapped"].split("|") if s],
        "windows": WINDOWS,
        "sheetUrl": SHEET_URL,
        "sources": sorted({r["source"] for r in funnel}),
        "keys": KEYS,
        "stages": STAGES,
        "funnel": funnel,
        "heyreach": json.loads(heyreach_file.read_text()) if heyreach_file.exists() and meta["source"] != "fake" else None,
    }
    html = (HERE / "template.html").read_text().replace("__DATA__", json.dumps(data))
    out = Path(os.environ.get("REPORT_OUT", HERE / "site" / "index.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out}: {len(funnel)} day/source rows, as of {meta['as_of']}")


if __name__ == "__main__":
    main()
