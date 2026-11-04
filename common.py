from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "funnel.db"
TODAY = date(2026, 10, 29)

WEEK_START_DAY = 6  # Python weekday(): Mon=0 ... Sun=6. Change to 0 for Monday weeks.

# status -> furthest funnel stage reached (matches status_map in the DB)
STATUS_MAP = {
    "Not Contacted": 0,
    "Message Sent": 1,
    "No Response": 1,
    "Contacted": 2,
    "Replied": 3,
    "Not Interested": 3,
    "Meeting": 4,
    "Won": 5,
    # statuses in the "Zid+Salla" sheet's Status dropdown (exact spelling; blank = Not Contacted)
    "Whatsapp": 1,         # WhatsApp message sent
    "Called": 1,           # reached by phone (same funnel stage as Whatsapp: Connected)
    "Not interested": 0,   # Dead: shown in the Dead card, not counted in any funnel stage
    "Demo": 4,             # demo booked/held (counts as the Meeting stage)
}

SOURCES = ["Mawsool", "Sfere", "Zid", "Salla"]


def week_start(d: date) -> date:
    return d - timedelta(days=(d.weekday() - WEEK_START_DAY) % 7)
