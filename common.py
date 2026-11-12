from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "funnel.db"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1P6icIaxNl2jwX1J5v99pPo9Vrd2QIYdnUlWJQHdOht4/edit"
WINDOWS = [7, 14, 30]  # "last N days" buttons; "All time" is always added

# status -> furthest funnel stage reached (loaded into the status_map table)
# 0 Leads, 1 Called, 2 Replied, 3 Interested, 4 ICP, 5 Demo booked, 6 Won
STATUS_MAP = {
    "Not Contacted": 0,
    "Called": 1,
    "Message Sent": 1,
    "Whatsapp": 1,
    "Contacted": 1,
    "No Response": 1,       # called, never replied (shown as "No reply")
    "Replied": 2,
    "Interested": 3,
    "ICP": 4,
    "Demo booked": 5,
    "Demo": 5,
    "Meeting": 5,
    "Won": 6,
    # dead ends: counted as Leads only, shown in the Dead card (reason = the "Reason" column)
    "Not Interested": 0,
    "Not ICP": 0,
}
DEAD_STATUSES = ("Not Interested", "Not ICP")
