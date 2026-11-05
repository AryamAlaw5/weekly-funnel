from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "funnel.db"
WINDOWS = [7, 14, 30]  # "last N days" buttons; "All time" is always added

# status -> furthest funnel stage reached (loaded into the status_map table)
STATUS_MAP = {
    "Not Contacted": 0,
    "Message Sent": 1,
    "No Response": 1,
    "Contacted": 2,
    "Replied": 3,
    "Not Interested": 3,
    "Meeting": 4,
    "Won": 5,
    # statuses in the "Zid+Salla" sheet's Status dropdown (blank = Not Contacted)
    "Whatsapp": 1,         # WhatsApp message sent
    "Called": 1,           # reached by phone (same stage as Whatsapp: Connected)
    "Not interested": 0,   # Dead: shown in the Dead card, not counted in any funnel stage
    "Demo": 4,             # demo booked/held (counts as the Meeting stage)
}
