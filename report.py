"""Read funnel.db and write report.html (data embedded as JSON, rendered by template.html)."""
import json
import sqlite3
from collections import Counter
from datetime import date

from common import DB_PATH, HERE, week_start

KEYS = ["added", "message_sent", "contacted", "replied", "meeting", "won", "no_response", "not_interested"]
STAGES = [
    {"key": "added", "label": "Added"},
    {"key": "message_sent", "label": "Message Sent"},
    {"key": "contacted", "label": "Contacted"},
    {"key": "replied", "label": "Replied"},
    {"key": "meeting", "label": "Meeting"},
    {"key": "won", "label": "Won"},
]


def main():
    db = sqlite3.connect(DB_PATH)
    meta = dict(db.execute("SELECT key, value FROM meta"))
    as_of = date.fromisoformat(meta["as_of"])
    funnel = [
        {"week": w, "source": s, **dict(zip(KEYS, vals))}
        for w, s, *vals in db.execute(
            f"SELECT week_start, source_tab, {', '.join(KEYS)} FROM v_weekly_funnel ORDER BY week_start")
    ]

    moves = Counter()
    for changed_on, source, to_status in db.execute(
            "SELECT changed_on, source_tab, to_status FROM v_status_changes"):
        wk = week_start(date.fromisoformat(changed_on)).isoformat()
        moves[(wk, source, to_status)] += 1

    stage = dict(db.execute("SELECT status, stage_order FROM status_map"))
    move_cols = sorted({t for (_, _, t) in moves if t != "Not Contacted"}, key=lambda t: (stage.get(t, 0), t))
    weeks = sorted({r["week"] for r in funnel})
    current = week_start(as_of).isoformat()
    data = {
        "asOf": as_of.isoformat(),
        "fake": meta["source"] == "fake",
        "unmapped": [s for s in meta["unmapped"].split("|") if s],
        "currentWeek": current,
        "defaultWeek": "all",
        "weeks": weeks,
        "sources": sorted({r["source"] for r in funnel}),
        "keys": KEYS,
        "stages": STAGES,
        "funnel": funnel,
        "moveCols": move_cols,
        "moves": [{"week": w, "source": s, "to": t, "n": n} for (w, s, t), n in sorted(moves.items())],
    }
    html = (HERE / "template.html").read_text().replace("__DATA__", json.dumps(data))
    out = HERE / "site" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f"wrote {out.relative_to(HERE)}: {len(funnel)} cohort rows, {len(weeks)} weeks")


if __name__ == "__main__":
    main()
