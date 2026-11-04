"""Build funnel.db with FAKE leads shaped like the Zid+Salla sheet (Zid, Salla, LinkedIn; weekly Date Added cohorts).

Each lead is simulated day by day from its Date Added to TODAY, and every day is
written to status_snapshots, the same rows the real sync would append.
"""
import hashlib
import random
import sqlite3
from datetime import date, timedelta

from common import DB_PATH, HERE, STATUS_MAP, week_start

TODAY = date.today()
SOURCES = ["Zid", "Salla", "LinkedIn"]

random.seed(42)

WEEKS_BACK = 6  # cohorts: the current week plus 5 earlier weeks
# per-tab multiplier on forward progress, so the tab filter shows differences
TAB_SKILL = {"Zid": 0.9, "Salla": 0.7, "LinkedIn": 1.3}
TAB_WEIGHT = {"Zid": 0.45, "Salla": 0.35, "LinkedIn": 0.2}

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
            company = f"{random.choice(PREFIX)} {random.choice(SUFFIX_B2B)}"
            contact = f"{random.choice(FIRST)} {random.choice(LAST)}"
            key = f"{company}|{contact}"
        else:
            company = f"{random.choice(PREFIX)} {random.choice(SUFFIX_STORE)} {random.choice(SUFFIX_END)}"
            contact = None
            key = f"{company.lower().replace(' ', '')}.sa"
        lead_id = hashlib.sha1(f"{tab}|{key}".encode()).hexdigest()[:12]
        if lead_id not in used:
            used.add(lead_id)
            return lead_id, company, contact


def simulate(added, tab):
    """Return [(date, status)] from the day added through TODAY."""
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

    this_week = week_start(TODAY)
    used, leads, snapshots = set(), [], []
    for w in range(WEEKS_BACK):
        wk = this_week - timedelta(weeks=WEEKS_BACK - 1 - w)
        last_day = min(wk + timedelta(days=6), TODAY)
        n_days = (last_day - wk).days + 1
        total = random.randint(70, 110) if wk < this_week else 45
        for tab in SOURCES:
            for _ in range(round(total * TAB_WEIGHT[tab])):
                added = wk + timedelta(days=random.randrange(n_days))
                lead_id, company, contact = make_lead(tab, used)
                history = simulate(added, tab)
                leads.append((lead_id, tab, company, contact, history[-1][1],
                              added.isoformat(), wk.isoformat(), TODAY.isoformat()))
                snapshots += [(d.isoformat(), lead_id, s) for d, s in history]

    db.executemany("INSERT INTO leads VALUES (?,?,?,?,?,?,?,?)", leads)
    db.executemany("INSERT INTO status_snapshots VALUES (?,?,?)", snapshots)
    db.commit()
    print(f"{len(leads)} leads, {len(snapshots)} snapshots -> {DB_PATH.name}")


if __name__ == "__main__":
    main()
