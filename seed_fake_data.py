"""Build funnel.db with FAKE leads shaped like the Zid+Salla sheet (Zid, Salla, LinkedIn; first seen over the last 45 days).

Each lead is simulated day by day from its first_seen day to TODAY, and every day is
written to status_snapshots, the same rows the real sync would append.
"""
import hashlib
import random
import sqlite3
from datetime import date, timedelta

from common import DB_PATH, HERE, STATUS_MAP

TODAY = date.today()
SOURCES = ["Zid", "Salla", "LinkedIn"]

random.seed(42)

DAYS_BACK = 45  # leads are first seen on a random day in the last 45 days
LEADS_PER_TAB = {"Zid": 120, "Salla": 90, "LinkedIn": 60}
# per-tab multiplier on forward progress, so the tab filter shows differences
TAB_SKILL = {"Zid": 0.9, "Salla": 0.7, "LinkedIn": 1.3}

# status -> [(next status, daily probability, is_forward)]
# Uses the sheet's dropdown (Whatsapp, Called, Demo, Not interested) plus Replied and Won so every stage shows up.
TRANSITIONS = {
    "Not Contacted": [("Whatsapp", 0.30, True), ("Called", 0.08, True)],
    "Whatsapp": [("Called", 0.06, True), ("Replied", 0.05, True), ("Not interested", 0.04, False)],
    "Called": [("Replied", 0.06, True), ("Not interested", 0.04, False)],
    "Replied": [("Demo", 0.06, True), ("Not interested", 0.05, False)],
    "Demo": [("Won", 0.04, True), ("Not interested", 0.04, False)],
}

PREFIX = ["Al Noor", "Najd", "Riyadh", "Gulf", "Desert", "Oasis", "Falcon", "Saffron", "Amber",
          "Tamar", "Qasr", "Layali", "Rimal", "Hijaz", "Jawhara", "Bayan", "Sahab", "Dar Al"]
SUFFIX_B2B = ["Trading", "Electronics", "Motors", "Foods", "Group", "Retail", "Industries", "Holding"]
SUFFIX_END = ["Store", "House", "Shop", "Co", "Hub", "Spot", "Line", "Box"]
SUFFIX_STORE = ["Oud", "Perfumes", "Fashion", "Coffee", "Abayas", "Gadgets", "Sweets", "Beauty", "Kids"]
FIRST = ["Ahmed", "Mohammed", "Fahad", "Sara", "Noura", "Khalid", "Maha", "Omar", "Layla", "Yousef",
         "Reem", "Faisal", "Huda", "Talal", "Abdullah", "Lama"]
LAST = ["Alharbi", "Alqahtani", "Alotaibi", "Alshehri", "Aldosari", "Almutairi", "Alzahrani", "Alghamdi"]


def make_lead(tab, used):
    while True:
        if tab == "LinkedIn":
            key = f"{random.choice(PREFIX)} {random.choice(SUFFIX_B2B)}|{random.choice(FIRST)} {random.choice(LAST)}"
        else:
            key = f"{random.choice(PREFIX)} {random.choice(SUFFIX_STORE)} {random.choice(SUFFIX_END)}"
        lead_id = hashlib.sha1(f"{tab}|{key}".encode()).hexdigest()[:12]
        if lead_id not in used:
            used.add(lead_id)
            return lead_id


def simulate(added, tab):
    """Return [(date, status)] from first_seen through TODAY."""
    status, history, day = "Not Contacted", [], added
    while day <= TODAY:
        history.append((day, status))
        for nxt, p, forward in TRANSITIONS.get(status, []):
            p = min(p * TAB_SKILL[tab], 0.95) if forward else p
            if random.random() < p:
                status = nxt
                break
        day += timedelta(days=1)
    return history


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = sqlite3.connect(DB_PATH)
    db.executescript((HERE / "schema.sql").read_text())
    db.executemany("INSERT INTO status_map VALUES (?, ?)", STATUS_MAP.items())
    db.executemany("INSERT INTO meta VALUES (?, ?)", [("source", "fake"), ("as_of", TODAY.isoformat()), ("unmapped", "")])

    used, leads, snapshots = set(), [], []
    for tab in SOURCES:
        for _ in range(LEADS_PER_TAB[tab]):
            first = TODAY - timedelta(days=random.randrange(DAYS_BACK))
            lead_id = make_lead(tab, used)
            history = simulate(first, tab)
            leads.append((lead_id, tab, history[-1][1], 0, first.isoformat(), TODAY.isoformat()))
            snapshots += [(d.isoformat(), lead_id, st) for d, st in history]

    db.executemany("INSERT INTO leads VALUES (?,?,?,?,?,?)", leads)
    db.executemany("INSERT INTO status_snapshots VALUES (?,?,?)", snapshots)
    db.commit()
    print(f"{len(leads)} leads, {len(snapshots)} snapshots -> {DB_PATH.name}")


if __name__ == "__main__":
    main()
