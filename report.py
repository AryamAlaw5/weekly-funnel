"""Read funnel.db and write the report page (data embedded as JSON, rendered by template.html)."""
import json
import os
import sqlite3
from pathlib import Path

from common import DB_PATH, HERE, SHEET_URL, WINDOWS

KEYS = ["added", "message_sent", "replied", "interested", "icp", "meeting", "won", "no_reply", "dead", "not_icp"]
STAGES = [
    {"key": "added", "label": "Leads"},
    {"key": "message_sent", "label": "Called"},
    {"key": "replied", "label": "Replied"},
    {"key": "interested", "label": "Interested"},
    {"key": "icp", "label": "ICP"},
    {"key": "meeting", "label": "Demo booked"},
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

    dead = [
        {"day": d, "source": src, "status": st, "reason": rs, "n": n}
        for d, src, st, rs, n in db.execute("SELECT first_seen, source_tab, status, reason, n FROM v_dead_reasons")
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
        "dead": dead,
        "heyreach": json.loads(heyreach_file.read_text()) if heyreach_file.exists() and meta["source"] != "fake" else None,
    }
    html = (HERE / "template.html").read_text().replace("__DATA__", json.dumps(data))
    out = Path(os.environ.get("REPORT_OUT", HERE / "site" / "index.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out}: {len(funnel)} day/source rows, as of {meta['as_of']}")


if __name__ == "__main__":
    main()
