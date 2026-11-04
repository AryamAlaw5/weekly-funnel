/**
 * Funnel snapshot exporter. Runs as a Google Apps Script (Extensions > Apps Script) and reads the "Zid+Salla" sheet.
 *
 * Reads the lead tabs (Zid, Salla, LinkedIn), replaces each lead with an anonymous keyed hash, and commits
 * one CSV per day to the GitHub repo. Names, phones, emails and notes never leave Google.
 *
 * Needs one Script property (Project Settings > Script properties):
 *   GITHUB_TOKEN  fine-grained token, this one repo only, "Contents: read and write"
 * ID_SALT (the secret that keeps hashed IDs unguessable) is created automatically on the first run.
 * Do not delete it later, or every lead gets a new ID and the history restarts.
 *
 * Always opens the sheet named by CONFIG.SHEET_ID, even if this script is bound to a different file.
 */
const CONFIG = {
  SHEET_ID: '1P6icIaxNl2jwX1J5v99pPo9Vrd2QIYdnUlWJQHdOht4', // "Zid+Salla" (replaced the old Mawsool/Sfere/Zid/Salla sheet)
  OWNER: 'AryamAlaw5',
  REPO: 'weekly-funnel-demo',
  BRANCH: 'main',
  FOLDER: 'data/snapshots',
  DAILY_HOUR: 6,
  // The sheet has no Date Added column yet. Leads with no date (or no column) get this date.
  DEFAULT_DATE_ADDED: '2026-11-02',
};

// Sheet tabs are matched by name prefix (case-insensitive); columns are matched by header text (case-insensitive).
// 'keys' build the anonymous lead ID. Zid/Salla list one row per store per app, so identical store+website
// rows are merged into ONE lead (the first non-blank status wins).
const TABS = [
  { match: 'zid', source: 'Zid', keys: ['store_name', 'store_website'], dedupe: true },
  { match: 'salla + zid linkedin', source: 'LinkedIn', keys: ['name', 'linkedin'], dedupe: false },
  { match: 'salla', source: 'Salla', keys: ['store_name', 'store_website'], dedupe: true },
];
const DATE_HEADERS = ['date added', 'date_added'];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Funnel report')
    .addItem('Push snapshot now', 'pushSnapshot')
    .addItem('Set up daily push', 'installDailyTrigger')
    .addToUi();
}

function pushSnapshot() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('Set GITHUB_TOKEN in Project Settings > Script properties.');
  let salt = props.getProperty('ID_SALT');
  if (!salt) {
    salt = Utilities.getUuid() + Utilities.getUuid();
    props.setProperty('ID_SALT', salt);
  }
  const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
  const tz = ss.getSpreadsheetTimeZone();
  const today = Utilities.formatDate(new Date(), tz, 'yyyy-MM-dd');

  const result = buildRows_(ss, salt, tz);
  const note = result.rows.length + ' leads' + (result.skipped.length ? ', ' + result.skipped.length + ' skipped' : '');
  commitFile_(CONFIG.FOLDER + '/' + today + '.csv', toCsv_(result.rows), token, 'Snapshot ' + today + ' (' + note + ')');

  Logger.log('Pushed ' + note + ' for ' + today);
  if (result.skipped.length) Logger.log('Skipped rows: ' + result.skipped.join('; '));
  return note;
}

function installDailyTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(function (t) { return t.getHandlerFunction() === 'pushSnapshot'; })
    .forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('pushSnapshot').timeBased().everyDays(1).atHour(CONFIG.DAILY_HOUR).create();
  Logger.log('Daily trigger set for about ' + CONFIG.DAILY_HOUR + ':00 (spreadsheet time zone).');
}

/* ---------- reading the sheet ---------- */

function buildRows_(ss, salt, tz) {
  const rows = [];
  const skipped = [];
  const tabsSeen = [];

  ss.getSheets().forEach(function (sheet) {
    const name = sheet.getName();
    const lname = name.trim().toLowerCase();
    const cfg = TABS.slice().sort(function (a, b) { return b.match.length - a.match.length; })
      .filter(function (t) { return lname.indexOf(t.match) === 0; })[0];
    if (!cfg) return;
    tabsSeen.push(cfg.source);

    const values = sheet.getDataRange().getValues();
    if (values.length < 2) return;
    const header = values[0].map(function (h) { return String(h).trim().toLowerCase(); });
    const col = {};
    header.forEach(function (h, i) { if (!(h in col)) col[h] = i; });
    cfg.keys.concat(['status']).forEach(function (h) {
      if (!(h in col)) throw new Error('Tab "' + name + '" has no "' + h + '" column.');
    });
    const dateCol = DATE_HEADERS.map(function (h) { return col[h]; }).filter(function (i) { return i !== undefined; })[0];

    const seen = {};
    for (let r = 1; r < values.length; r++) {
      const row = values[r];
      const parts = cfg.keys.map(function (k) { return String(row[col[k]]).trim(); });
      if (parts.every(function (p) { return p === ''; })) continue;

      const rawDate = dateCol === undefined ? '' : row[dateCol];
      let dateAdded;
      if (String(rawDate).trim() === '') {
        dateAdded = CONFIG.DEFAULT_DATE_ADDED; // no date entered yet
      } else {
        dateAdded = parseDate_(rawDate, tz);
        if (!dateAdded) {
          skipped.push(cfg.source + ' row ' + (r + 1) + ' (bad Date Added)');
          continue;
        }
      }
      const status = String(row[col['status']]).trim();

      const base = [cfg.source].concat(parts).join('|').toLowerCase();
      if (cfg.dedupe && base in seen) {
        // same store listed again for another app: keep one lead, fill a missing status from the repeat
        const prev = rows[seen[base]];
        if (!prev[3] && status) prev[3] = status;
        continue;
      }
      // other tabs: identical keys get a #2, #3 ... suffix so they stay separate leads
      let idSource = base;
      if (!cfg.dedupe) {
        seen[base] = (seen[base] || 0) + 1;
        if (seen[base] > 1) idSource = base + '#' + seen[base];
      } else {
        seen[base] = rows.length;
      }
      rows.push([hmacHex_(idSource, salt).slice(0, 16), cfg.source, dateAdded, status]);
    }
  });

  const missing = TABS.filter(function (t) { return tabsSeen.indexOf(t.source) < 0; });
  if (missing.length) {
    throw new Error('Could not find tab(s): ' + missing.map(function (t) { return t.source; }).join(', '));
  }
  rows.forEach(function (r) { if (!r[3]) r[3] = 'Not Contacted'; });
  return { rows: rows, skipped: skipped };
}

const MONTHS_ = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };

// Text dates ("1 Nov 2026", "Nov 1, 2026", "2026-11-01") are read as written, with no time zone involved.
function parseDate_(v, tz) {
  if (v instanceof Date) return isNaN(v) ? null : Utilities.formatDate(v, tz, 'yyyy-MM-dd');
  const s = String(v).trim();
  if (!s) return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  let day, mon, year;
  let m = s.match(/^(\d{1,2})[\s\-\/]+([A-Za-z]{3,9})\.?[\s\-\/,]+(\d{4})$/);
  if (m) { day = m[1]; mon = m[2]; year = m[3]; }
  else if ((m = s.match(/^([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})$/))) { mon = m[1]; day = m[2]; year = m[3]; }
  if (!m) return null;

  const month = MONTHS_[mon.slice(0, 3).toLowerCase()];
  const d = Number(day);
  if (!month || d < 1 || d > 31) return null;
  return year + '-' + ('0' + month).slice(-2) + '-' + ('0' + d).slice(-2);
}

function hmacHex_(value, key) {
  return Utilities.computeHmacSha256Signature(value, key)
    .map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); })
    .join('');
}

function toCsv_(rows) {
  const esc = function (v) { return /[",\n]/.test(v) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v); };
  return [['lead_id', 'source_tab', 'date_added', 'status']].concat(rows)
    .map(function (r) { return r.map(esc).join(','); })
    .join('\n') + '\n';
}

/* ---------- writing to GitHub ---------- */

function commitFile_(path, content, token, message) {
  const url = 'https://api.github.com/repos/' + CONFIG.OWNER + '/' + CONFIG.REPO + '/contents/' + path;
  const headers = {
    Authorization: 'Bearer ' + token,
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
  };

  // replacing today's file needs the current file's sha
  let sha;
  const existing = UrlFetchApp.fetch(url + '?ref=' + CONFIG.BRANCH, { headers: headers, muteHttpExceptions: true });
  if (existing.getResponseCode() === 200) sha = JSON.parse(existing.getContentText()).sha;
  else if (existing.getResponseCode() !== 404) {
    throw new Error('GitHub lookup failed (' + existing.getResponseCode() + '): ' + existing.getContentText().slice(0, 200));
  }

  const body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: CONFIG.BRANCH,
  };
  if (sha) body.sha = sha;

  const res = UrlFetchApp.fetch(url, {
    method: 'put',
    headers: headers,
    contentType: 'application/json',
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error('GitHub commit failed (' + code + '): ' + res.getContentText().slice(0, 300));
  }
}
