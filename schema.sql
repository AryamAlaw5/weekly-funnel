-- Weekly funnel schema. SQLite for the prototype; the shapes carry over to Postgres.

DROP VIEW  IF EXISTS v_weekly_funnel;
DROP VIEW  IF EXISTS v_status_changes;
DROP TABLE IF EXISTS status_snapshots;
DROP TABLE IF EXISTS leads;
DROP TABLE IF EXISTS status_map;
DROP TABLE IF EXISTS meta;

-- Which funnel stage each sheet status counts as. Edit this table, not the code,
-- when the team adds a status. stage_order is the furthest stage a lead has reached.
CREATE TABLE status_map (
  status      TEXT PRIMARY KEY,
  stage_order INTEGER NOT NULL      -- 0 added, 1 message sent, 2 contacted, 3 replied, 4 meeting, 5 won
);

-- Where the data came from: source (fake | sheet), as_of date, unmapped statuses.
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- One row per lead, current state (what the sheet shows today).
CREATE TABLE leads (
  lead_id    TEXT PRIMARY KEY,      -- stable hash of tab + company + contact/website
  source_tab TEXT NOT NULL,         -- Zid | Salla | LinkedIn (demo data uses Mawsool | Sfere | Zid | Salla)
  company    TEXT,                  -- fake data only; real snapshots are anonymous
  contact    TEXT,
  status     TEXT NOT NULL REFERENCES status_map(status),
  date_added DATE NOT NULL,
  week_start DATE NOT NULL,         -- cohort week, derived from date_added at ingest
  updated_at DATE NOT NULL
);
CREATE INDEX idx_leads_week ON leads(week_start, source_tab);

-- One row per lead per sync day. The sheet has no history, so this is where movement comes from.
CREATE TABLE status_snapshots (
  snapshot_date DATE NOT NULL,
  lead_id       TEXT NOT NULL REFERENCES leads(lead_id),
  status        TEXT NOT NULL,
  PRIMARY KEY (snapshot_date, lead_id)
);

-- Cohort funnel: leads grouped by the week of Date Added, counted by furthest stage reached.
CREATE VIEW v_weekly_funnel AS
SELECT
  l.week_start,
  l.source_tab,
  COUNT(*)                                          AS added,
  COUNT(*) FILTER (WHERE m.stage_order >= 1)        AS message_sent,
  COUNT(*) FILTER (WHERE m.stage_order >= 2)        AS contacted,
  COUNT(*) FILTER (WHERE m.stage_order >= 3)        AS replied,
  COUNT(*) FILTER (WHERE m.stage_order >= 4)        AS meeting,
  COUNT(*) FILTER (WHERE m.stage_order >= 5)        AS won,
  COUNT(*) FILTER (WHERE LOWER(l.status) = 'no response')  AS no_response,
  COUNT(*) FILTER (WHERE LOWER(l.status) = 'not interested') AS not_interested
FROM leads l
JOIN status_map m ON m.status = l.status
GROUP BY l.week_start, l.source_tab;

-- Every day-to-day status change, from consecutive snapshots.
CREATE VIEW v_status_changes AS
SELECT s.snapshot_date AS changed_on, s.lead_id, l.source_tab,
       s.prev_status AS from_status, s.status AS to_status
FROM (
  SELECT snapshot_date, lead_id, status,
         LAG(status) OVER (PARTITION BY lead_id ORDER BY snapshot_date) AS prev_status
  FROM status_snapshots
) s
JOIN leads l USING (lead_id)
WHERE s.prev_status IS NOT NULL AND s.prev_status <> s.status;
