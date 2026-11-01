"""Build funnel.db with fake leads shaped like the Sfere sheet (4 tabs, weekly Date Added cohorts).

Each lead is simulated day by day from its Date Added to TODAY, and every day is
written to status_snapshots, the same rows the real sync would append.
"""
import hashlib
import random
import sqlite3
from datetime import timedelta

from common import DB_PATH, HERE, SOURCES, STATUS_MAP, TODAY, week_start

random.seed(42)

WEEKS_BACK = 6  # cohorts: the current week plus 5 earlier weeks
# per-tab multiplier on forward progress, so the tab filter shows differences
TAB_SKILL = {"Mawsool": 1.0, "Sfere": 1.25, "Zid": 0.8, "Salla": 0.65}
TAB_WEIGHT = {"Mawsool": 0.3, "Sfere": 0.3, "Zid": 0.2, "Salla": 0.2}

# status -> [(next status, daily probability, is_forward)]
TRANSITIONS = {
    "Not Contacted": [("Message Sent", 0.30, True)],
    "Message Sent": [("Contacted", 0.06, True), ("No Response", 0.05, False)],
    "Contacted": [("Replied", 0.045, True), ("No Response", 0.03, False)],
    "Replied": [("Meeting", 0.06, True), ("Not Interested", 0.06, False)],
    "Meeting": [("Won", 0.035, True), ("Not Interested", 0.04, False)],
}

PREFIX = ["Al Noor", "Najd", "Riyadh", "Gulf", "Desert", "Oasis", "Falcon", "Saffron", "Amber",
          "Tamar", "Qasr", "Layali", "Rimal", "Hijaz", "Jawhara", "Bayan", "Sahab", "Dar Al"]
SUFFIX_B2B = ["Trading", "Electronics", "Motors", "Foods", "Group", "Retail", "Industries", "Holding"]
SUFFIX_STORE = ["Oud", "Perfumes", "Fashion", "Coffee", "Abayas", "Gadgets", "Sweets", "Beauty", "Kids"]
FIRST = ["Ahmed", "Mohammed", "Fahad", "Sara", "Noura", "Khalid", "Maha", "Omar", "Layla", "Yousef",
         "Reem", "Faisal", "Huda", "Talal", "Abdullah", "Lama"]
LAST = ["Alharbi", "Alqahtani", "Alotaibi", "Alshehri", "Aldosari", "Almutairi", "Alzahrani", "Alghamdi"]


def make_lead(tab, used):
    while True:
        if tab in ("Mawsool", "Sfere"):
            company = f"{random.choice(PREFIX)} {random.choice(SUFFIX_B2B)}"
            contact = f"{random.choice(FIRST)} {random.choice(LAST)}"
            key = f"{company}|{contact}"
        else:
            company = f"{random.choice(PREFIX)} {random.choice(SUFFIX_STORE)}"
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
