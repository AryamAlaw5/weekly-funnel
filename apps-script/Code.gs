/**
 * Funnel snapshot exporter. Runs inside the Sfere sheet (Extensions > Apps Script).
 *
 * Reads the four lead tabs, replaces each lead with an anonymous keyed hash, and commits
 * one CSV per day to the GitHub repo. Names, phones, emails and notes never leave Google.
 *
 * Needs two Script properties (Project Settings > Script properties):
 *   ID_SALT       any long random string; keeps the hashed IDs unguessable
 *   GITHUB_TOKEN  fine-grained token, this one repo only, "Contents: read and write"
 */
const CONFIG = {
  OWNER: 'AryamAlaw5',
  REPO: 'weekly-funnel-demo',
  BRANCH: 'main',
  FOLDER: 'data/snapshots',
  DAILY_HOUR: 6,
};

// Sheet tabs are matched by name prefix; columns are matched by header text.
const TABS = [
  { match: 'mawsool', source: 'Mawsool', keys: ['Company', 'Person Name'] },
  { match: 'sfere', source: 'Sfere', keys: ['Company', 'Person Name'] },
  { match: 'zid', source: 'Zid', keys: ['Store', 'Website'] },
  { match: 'salla', source: 'Salla', keys: ['Store Name', 'Website'] },
];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Funnel report')
    .addItem('Push snapshot now', 'pushSnapshot')
    .addItem('Set up daily push', 'installDailyTrigger')
    .addToUi();
}

function pushSnapshot() {
  const props = PropertiesService.getScriptProperties();
  const salt = props.getProperty('ID_SALT');
  const token = props.getProperty('GITHUB_TOKEN');
  if (!salt || !token) {
    throw new Error('Set ID_SALT and GITHUB_TOKEN in Project Settings > Script properties.');
  }
  const ss = SpreadsheetApp.getActiveSpreadsheet();
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
    const cfg = TABS.filter(function (t) { return name.trim().toLowerCase().indexOf(t.match) === 0; })[0];
    if (!cfg) return;
    tabsSeen.push(cfg.source);

    const values = sheet.getDataRange().getValues();
    if (values.length < 2) return;
    const header = values[0].map(function (h) { return String(h).trim(); });
    const col = {};
    header.forEach(function (h, i) { if (!(h in col)) col[h] = i; });
    cfg.keys.concat(['Status', 'Date Added']).forEach(function (h) {
      if (!(h in col)) throw new Error('Tab "' + name + '" has no "' + h + '" column.');
    });

    const seen = {};
    for (let r = 1; r < values.length; r++) {
      const row = values[r];
      const parts = cfg.keys.map(function (k) { return String(row[col[k]]).trim(); });
      if (parts.every(function (p) { return p === ''; })) continue;

      const dateAdded = parseDate_(row[col['Date Added']], tz);
      if (!dateAdded) {
        skipped.push(cfg.source + ' row ' + (r + 1) + ' (bad Date Added)');
        continue;
      }
      const status = String(row[col['Status']]).trim() || 'Not Contacted';

      // identical keys in one tab get a #2, #3 ... suffix so they stay separate leads
      const base = [cfg.source].concat(parts).join('|').toLowerCase();
      seen[base] = (seen[base] || 0) + 1;
      const idSource = seen[base] > 1 ? base + '#' + seen[base] : base;

      rows.push([hmacHex_(idSource, salt).slice(0, 16), cfg.source, dateAdded, status]);
    }
  });

  const missing = TABS.filter(function (t) { return tabsSeen.indexOf(t.source) < 0; });
  if (missing.length) {
    throw new Error('Could not find tab(s): ' + missing.map(function (t) { return t.source; }).join(', '));
  }
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
