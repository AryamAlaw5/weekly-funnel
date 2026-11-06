-- Funnel schema. SQLite; the shapes carry over to Postgres.

DROP VIEW  IF EXISTS v_funnel_by_day;
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS status_map;
DROP TABLE IF EXISTS meta;

-- Which funnel stage each status counts as. stage_order is the furthest stage a lead has reached.
CREATE TABLE status_map (
  status      TEXT PRIMARY KEY,
  stage_order INTEGER NOT NULL      -- 0 added, 1 message sent, 2 contacted, 3 replied, 4 meeting, 5 won
);

-- Where the data came from: source (fake | sheet), as_of date, unmapped statuses.
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- One row per lead, current state. The sheet has no date column: first_seen is the first
-- daily snapshot the lead appears in (leads already in the first snapshot count as first seen that day).
CREATE TABLE leads (
  lead_id    TEXT PRIMARY KEY,      -- anonymous hash of tab + company + contact/website
  source_tab TEXT NOT NULL,         -- Zid | Salla | LinkedIn
  status     TEXT NOT NULL REFERENCES status_map(status),
  has_note   INTEGER NOT NULL DEFAULT 0,  -- 1 if the sheet's Notes cell is filled (the note text itself is never exported)
  first_seen DATE NOT NULL,
  updated_at DATE NOT NULL
);
CREATE INDEX idx_leads_seen ON leads(first_seen, source_tab);

-- Leads grouped by the day first seen, counted by furthest stage reached.
CREATE VIEW v_funnel_by_day AS
SELECT
  l.first_seen,
  l.source_tab,
  COUNT(*)                                          AS added,
  COUNT(*) FILTER (WHERE m.stage_order >= 1)        AS message_sent,
  COUNT(*) FILTER (WHERE m.stage_order >= 3)        AS replied,
  COUNT(*) FILTER (WHERE m.stage_order >= 4)        AS meeting,
  COUNT(*) FILTER (WHERE m.stage_order >= 5)        AS won,
  COUNT(*) FILTER (WHERE LOWER(l.status) = 'not interested')                    AS dead,
  COUNT(*) FILTER (WHERE LOWER(l.status) = 'not interested' AND l.has_note = 1) AS dead_with_note
FROM leads l
JOIN status_map m ON m.status = l.status
GROUP BY l.first_seen, l.source_tab;
