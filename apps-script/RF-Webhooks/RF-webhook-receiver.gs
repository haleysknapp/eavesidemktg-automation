/**
 * Roofing Force — Webhook receiver (Formidable + CTM -> Leads tab)
 * ---------------------------------------------------------------
 * One Apps Script Web App that accepts POSTs from the website form (Formidable)
 * and the call tracker (CTM), normalizes each into the Leads schema, dedupes,
 * and appends. Real-time, no daily pasting.
 *
 * This is the same transform/dedupe logic as RF-lead-ingest-runbook.md, in code.
 * It writes Y:Z (structured property address: street, zip) FIRST, then columns A:W (lead
 * data) — two SEPARATE writes (see appendLead_ for why the order matters). It never touches
 * X (dedupe_flag), AA (charge_status — LSA-only, left blank for web/CTM), or AE..AI (the
 * live array-formulas: channel_rollup/phone_norm/call_market/repeat_inquirer/first_touch).
 *
 * ============================================================================
 * CHANGE 2026-08-13 — REPEAT-CALLER DEFECT FIX. Read this before editing dedupe.
 * ----------------------------------------------------------------------------
 * THE BUG (Fix Queue #2 / #7b): keysFor_() built a phone key and appendLead_()
 * compared it against ALL history with NO TIME WINDOW. Any caller who had EVER
 * called before was dropped — permanently, silently — and doPost returned
 * HTTP 200 {ok:true, skipped:"duplicate"}, so CTM treated the drop as a success
 * and never retried. Measured effect: ~76% of paid callers had no CRM record.
 * A homeowner who called in April and called again in August ready to buy did
 * not exist in this system.
 *
 * THE FIX, two layers:
 *   1. CTM CALL ID (primary, exact). CTM already sends a unique `id` per call and
 *      this script was throwing it away. It is now stored in Leads column AK
 *      (ctm_call_id) and is the real duplicate test: same call id = same call =
 *      genuine duplicate delivery. Different call id = different call, always
 *      appended, even from the same number one minute later.
 *   2. TIME WINDOW (fallback, for anything with no call id — web forms, and any
 *      CTM payload where `id` is missing). Phone / email / name+date keys now
 *      only suppress a row if the earlier matching row is within
 *      DEDUPE_WINDOW_MIN minutes. That still catches double-submits and webhook
 *      retries, which arrive in seconds, while letting a real second inquiry
 *      through.
 *
 * ALSO FIXED: intermittent blank dates on CTM rows (Fix Queue #7b). `called_at`
 * sometimes arrives as whitespace or an unresolved Mustache token; the old code
 * passed it straight to new Date(), got NaN, and wrote a blank/garbage date, so
 * the lead fell out of every weekly window. parseDate_() now validates and falls
 * back to the received time, which is accurate to the second for a live webhook.
 *
 * SAFE TO RE-PASTE: no column indexes shift. AK self-creates with its header on
 * first run. Behaviour for genuine duplicates is unchanged.
 * ============================================================================
 *
 * DEPLOY (one time — see RF-Webhooks-Setup-Plan.md for the full walkthrough)
 * 1. Tracking spreadsheet -> Extensions -> Apps Script. Paste this file. Save.
 * 2. Project Settings -> Script Properties: add WEBHOOK_KEY = <a long random secret>.
 * 3. Deploy -> New deployment -> Web app. Execute as: Me. Who has access: Anyone.
 *    Copy the /exec URL — that's the endpoint both senders POST to.
 * 4. Configure Formidable + CTM to POST the payloads in §CONTRACT below (with key).
 * 5. Test with the test* functions, then send a real lead through each source.
 *
 * NOTE: pasting over this file does NOT require a new deployment. The existing
 * /exec URL keeps working and picks up the saved code.
 *
 * SECURITY: the shared secret lives in Script Properties, never in the sheet or in git.
 * Every POST must include "key" matching WEBHOOK_KEY or it is rejected.
 *
 * PAYLOAD CONTRACT (configure senders to POST JSON like this)
 *  Formidable (RF form 5): { key, source:"formidable", first_name, last_name, phone, email,
 *                street, city, state, zip, message, gclid, fbclid, traffic_source, utm_source,
 *                utm_medium, user_journey, created_at }
 *    - street/city/state/zip + message -> notes (col W) = "address | project description"
 *    - traffic_source = the referrer URL (drives organic/direct/referral when no gclid)
 *    - user_journey   = the page-visit trail; we pull the market + landing page from it
 *  CTM (Mustache body): { key, source:"ctm", id, caller_number, tracking_number, name, email,
 *                street, city, state, zip, called_at, ctm_source, gclid, utm_source, utm_medium,
 *                campaign, keyword }
 *    - id       = CTM's unique call id. REQUIRED for correct dedupe — if the CTM webhook
 *                 template does not send it, repeat callers fall back to the time window.
 *                 Stored in col AK (ctm_call_id).
 *    - tracking_number (the dialed DNI number) -> channel_rollup VLOOKUPs it in Source Map
 *    - street/city/state/zip -> caller address in notes; gclid/utm captured for web-originated calls
 *    - campaign = the Google Ads campaign CTM resolves from the gclid -> stored in utm_campaign (col Q)
 *    - keyword  = the Google Ads keyword -> appended to notes as "kw: ..." (no dedicated column)
 */

const SHEET_ID = '1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc';
const LEADS_TAB = 'Leads';
const LEADS_COLS = 23; // A:W

// Column AK (37) — CTM's unique call id. First free column past the live array-formula
// block (AE..AJ). Self-creates its header on first write. Nothing else reads or writes it.
const CTM_ID_COL = 37;
const CTM_ID_HEADER = 'ctm_call_id';

// How close together two rows with the same phone/email/name must be to count as the SAME
// event rather than a genuine second inquiry. Webhook retries and double-submits land within
// seconds. 30 minutes is deliberately generous; raising it starts dropping real callbacks.
const DEDUPE_WINDOW_MIN = 30;

function doGet() { return json_({ ok: true, msg: 'RF webhook receiver alive' }); }

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000); // serialize concurrent webhooks so ids/dedupe stay correct
  try {
    const body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    const key = PropertiesService.getScriptProperties().getProperty('WEBHOOK_KEY');
    if (!key || body.key !== key) return json_({ ok: false, error: 'bad key' });

    const src = (body.source || '').toLowerCase();
    const lead = src === 'ctm' ? normalizeCtm_(body)
               : src === 'formidable' ? normalizeForm_(body)
               : null;
    if (!lead) return json_({ ok: false, error: 'unknown source' });

    const res = appendLead_(lead);
    return json_(res);
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  } finally {
    lock.releaseLock();
  }
}

/* ---------- normalizers (raw payload -> Leads row object) ---------- */
function normalizeForm_(b) {
  const gclid = (b.gclid || '').trim();
  const fbclid = (b.fbclid || '').trim();
  const journey = b.user_journey || '';
  const referrer = lc_(b.traffic_source);
  const name = ((String(b.first_name || '').trim() + ' ' + String(b.last_name || '').trim()).trim()) || (b.name || '');
  const cs = [b.city, b.state].filter(Boolean).join(', ');
  const street = String(b.street || '').trim();
  const zip = String(b.zip || '').trim();
  let addr = [street, cs].filter(Boolean).join(', '); if (zip) addr += ' ' + zip; // full property address for CRM / AccuLynx match
  const msg = String(b.message || '').trim();
  const notes = [addr, msg].filter(Boolean).join(' | '); // "address | project description"
  return {
    channel: 'Web', lead_type: 'Form', prefix: 'WEB',
    date: parseDate_(b.created_at),                       // never NaN — see parseDate_
    name: name, email: lc_(b.email),
    phone: e164_(b.phone), caller_location: cs,
    sub_source: webSource_(gclid, fbclid, referrer),
    market: marketFromJourney_(journey) || marketFromText_(cs),
    landing_page: firstUrl_(journey), gclid: gclid,
    utm_source: b.utm_source || '', utm_medium: b.utm_medium || '', utm_campaign: b.utm_campaign || '',
    notes: notes, street: street, zip: zip,
    ctm_id: ''                                            // web forms have no call id
  };
}
function normalizeCtm_(b) {
  // CTM Mustache payload: id, caller_number, tracking_number, name, email, street, city,
  // state, zip(postal_code), called_at, ctm_source(=CTM source), gclid, utm_source, utm_medium,
  // campaign(=Google Ads campaign CTM resolved from the gclid), keyword.
  const cs = [b.city, b.state].filter(Boolean).join(', ');
  const street = String(b.street || '').trim();
  const zip = String(b.zip || '').trim();
  let addr = [street, cs].filter(Boolean).join(', '); if (zip) addr += ' ' + zip;
  const kw = String(b.keyword || '').trim();
  const name = b.name || ((String(b.first_name || '').trim() + ' ' + String(b.last_name || '').trim()).trim());
  return {
    channel: 'Call', lead_type: 'call', prefix: 'CALL',
    date: parseDate_(b.called_at),                        // was: b.called_at || new Date() — see parseDate_
    name: name, email: lc_(b.email),
    phone: e164_(b.caller_number), caller_location: cs,
    sub_source: b.ctm_source || '', market: '',           // market resolved by call_market formula from tracking_number
    tracking_number: prettyPhone_(b.tracking_number),     // MUST match Source Map format for channel_rollup VLOOKUP
    landing_page: '', gclid: (b.gclid || '').trim(),
    utm_source: b.utm_source || '', utm_medium: b.utm_medium || '',
    utm_campaign: b.campaign || b.utm_campaign || '',      // CTM resolves the Google Ads campaign from the gclid -> col Q
    notes: [addr, kw ? ('kw: ' + kw) : ''].filter(Boolean).join(' | '), // keyword appended to notes (no dedicated column)
    street: street, zip: zip,
    ctm_id: ctmId_(b)                                     // THE dedupe key for calls
  };
}

// CTM's unique per-call id. Accept the few names CTM templates use in the wild, and
// reject unresolved Mustache tokens ("{{id}}") so a broken template degrades to the
// time window instead of making every call look like the same call.
function ctmId_(b) {
  const raw = String(b.id || b.call_id || b.callId || b.activity_id || '').trim();
  if (!raw || /[{}]/.test(raw) || lc_(raw) === 'null' || lc_(raw) === 'undefined') return '';
  return raw;
}

/* ---------- append (dedupe + id + write A:W) ---------- */
function appendLead_(lead) {
  const sh = SpreadsheetApp.openById(SHEET_ID).getSheetByName(LEADS_TAB);
  const maxRows = sh.getMaxRows();
  ensureCtmIdColumn_(sh);

  // Find the true last lead row by scanning column A (lead_id). DO NOT use getLastRow():
  // the live array-formula columns (X/AE/AF/AG) spill blank values to row 3000 and would
  // fool it into appending far below the real data, outside the formula range.
  const colA = sh.getRange(1, 1, maxRows, 1).getValues();
  let lastData = 1; // row 1 = header
  for (let i = colA.length - 1; i >= 1; i--) {
    if (String(colA[i][0]).trim() !== '') { lastData = i + 1; break; }
  }

  const existing = lastData > 1 ? sh.getRange(2, 1, lastData - 1, LEADS_COLS).getValues() : [];
  const ctmIds   = lastData > 1 ? sh.getRange(2, CTM_ID_COL, lastData - 1, 1).getValues() : [];
  const row = toRow_(lead);

  // ---- LAYER 1: exact — same CTM call id already written. This is the ONLY test that
  // fires for a call that carries an id, so repeat callers are never suppressed.
  if (lead.ctm_id) {
    for (let i = 0; i < ctmIds.length; i++) {
      if (String(ctmIds[i][0]).trim() === lead.ctm_id) {
        return { ok: true, skipped: 'duplicate', by: 'ctm_id', ctm_id: lead.ctm_id };
      }
    }
  }

  // ---- LAYER 2: time-windowed — for rows with no call id (web forms, id-less CTM payloads).
  // Same channel only (2026-06-13 rule: a Web form must not be dropped because its phone
  // matches a Call; the sheet's dedupe_flag formula handles cross-channel "count once").
  // Unlike the old code this compares timestamps, so only near-simultaneous repeats suppress.
  if (!lead.ctm_id) {
    const leadKeys = keysFor_(row);
    const leadTs = tsOf_(row[1], row[2]);
    for (let i = 0; i < existing.length; i++) {
      const r = existing[i];
      if (String(r[3] || '').trim() !== lead.channel) continue;
      // NOTE: this deliberately compares against ALL same-channel rows in the window, including
      // ones that carry a ctm_call_id. An id-less payload arriving minutes after an id-bearing
      // row from the same number is a redelivery of that same call — CTM sending the same event
      // through a template that dropped the id. Excluding id-bearing rows here would let those
      // through as phantom second leads.
      const rTs = tsOf_(r[1], r[2]);
      if (leadTs === null || rTs === null) continue;                // undated row: cannot window, so let it through
      if (Math.abs(leadTs - rTs) > DEDUPE_WINDOW_MIN * 60000) continue;
      const rKeys = keysFor_(r);
      if (leadKeys.some(k => rKeys.indexOf(k) !== -1)) {
        return { ok: true, skipped: 'duplicate', by: 'window', within_min: DEDUPE_WINDOW_MIN };
      }
    }
  }

  // id = prefix-### continuing from max
  let max = 0;
  const re = new RegExp('^' + lead.prefix + '-(\\d+)$');
  existing.forEach(r => { const m = String(r[0] || '').match(re); if (m) max = Math.max(max, +m[1]); });
  // pad to 3 digits but NEVER truncate — the old `('000'+n).slice(-3)` chopped CALL-1000 -> "000",
  // which re-parsed as 0 and froze every high-volume CALL id at CALL-000. padStart grows past 999.
  row[0] = lead.prefix + '-' + String(max + 1).padStart(3, '0');

  const target = lastData + 1;
  if (target > maxRows) sh.insertRowsAfter(maxRows, 200);
  // guard: if data ever reaches the formula spill limit, the helper columns (X/AE..AI)
  // and the audit mirror must be extended past row 3000 or new rows won't get classified.
  //
  // WRITE ORDER (hardened 2026-06-05): structured address (Y:Z) goes FIRST, then A:W.
  // The two writes must stay separate so we never overwrite X (dedupe_flag, col 24) which
  // sits between W and Y. Writing Y:Z first means a partial write can't drop the address:
  // the row only becomes "real" once col A (lead_id) lands in the A:W write, and lastData/
  // dedupe both scan col A — so an orphaned Y:Z (no A) is invisible and gets overwritten by
  // the next append. flush() forces the address write to commit before the row goes live.
  sh.getRange(target, 25, 1, 2).setValues([[lead.street || '', lead.zip || '']]); // Y (street), Z (zip)
  SpreadsheetApp.flush();
  sh.getRange(target, 1, 1, LEADS_COLS).setValues([row]); // A:W — col A (lead_id) makes the row live
  // ctm_call_id (AK) is written AFTER the row goes live, on purpose. If this write ever fails
  // the row still exists and is still counted; the only cost is that this one call falls back
  // to the time window next time. Losing the lead is the failure that matters, not losing the id.
  if (lead.ctm_id) sh.getRange(target, CTM_ID_COL).setValue(lead.ctm_id);
  // NOTE: charge_status (col AA) is LSA-only (it tracks LSA per-lead billing). Web/CTM leads
  // have no charge concept, so the webhook intentionally leaves AA blank.
  return { ok: true, lead_id: row[0], row: target, ctm_id: lead.ctm_id || null };
}

// Make sure column AK exists and is labelled. Runs on every append; costs one read.
function ensureCtmIdColumn_(sh) {
  if (sh.getMaxColumns() < CTM_ID_COL) {
    sh.insertColumnsAfter(sh.getMaxColumns(), CTM_ID_COL - sh.getMaxColumns());
  }
  const h = sh.getRange(1, CTM_ID_COL);
  if (String(h.getValue()).trim() === '') h.setValue(CTM_ID_HEADER);
}

// Leads A:W order
function toRow_(L) {
  return [
    '',                         // A lead_id (set later)
    ymd_(L.date), time_(L.date),// B date, C time
    L.channel, L.sub_source || '', L.market || '', L.lead_type || '',
    L.name || '', L.phone || '', L.email || '', L.caller_location || '',
    L.tracking_number || '', L.landing_page || '', L.gclid || '',
    L.utm_source || '', L.utm_medium || '', L.utm_campaign || '',
    '',                         // R first_or_repeat
    'new',                      // S status
    '', '', '',                 // T job_value, U closed_date, V acculynx_job_id
    L.notes || ''               // W notes (web: full property address)
  ];
}

/* ---------- dedupe keys (match the runbook) ---------- */
// existing row: channel=3,date=1,name=7,phone=8,email=9 (0-based)
// UNCHANGED from the deployed version. What changed is how appendLead_ USES these:
// they are now only consulted inside a time window, and only when there is no CTM call id.
function keysFor_(r) {
  const k = [];
  const p = norm10_(r[8]); if (p) k.push('P:' + p);
  const e = lc_(r[9]); if (e) k.push('E:' + e);
  const nm = lc_(r[7]); const dt = ymd_(r[1]);
  if (nm && dt) k.push('N:' + r[3] + '|' + dt + '|' + nm);
  return k;
}
function keysForLead_(L, row) { return keysFor_(row); }

/* ---------- helpers ---------- */
// Turn a Leads date + time cell pair into epoch ms, or null if it can't be placed in time.
//
// THE TYPE TRAP (found 2026-08-13 by verifyRepeatCallerFix failing test 3 in the live sheet):
// the webhook WRITES strings ('2026-07-30', '14:02:00'), but Leads column B is date-formatted
// and column C is time-formatted, so Sheets coerces them on write and getValues() READS THEM
// BACK AS Date OBJECTS. An earlier version handled the Date case by returning dateCell.getTime()
// — midnight, silently discarding the time of day in column C. So a row stored 2 minutes earlier
// compared as 14 hours earlier, blew past the 30-minute window, and a genuine duplicate got
// appended. Date and string forms MUST resolve identically. Do not simplify this function.
function tsOf_(dateCell, timeCell) {
  let y, mo, da;
  if (dateCell instanceof Date && !isNaN(dateCell)) {
    y = dateCell.getFullYear(); mo = dateCell.getMonth(); da = dateCell.getDate();
  } else {
    const m = String(dateCell == null ? '' : dateCell).trim().match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!m) return null;                       // undated row — cannot be placed in time
    y = +m[1]; mo = +m[2] - 1; da = +m[3];
  }

  let hh = 0, mi = 0, ss = 0;
  if (timeCell instanceof Date && !isNaN(timeCell)) {
    // Sheets returns a time-only cell as 1899-12-30 plus the time; only the clock part is real.
    hh = timeCell.getHours(); mi = timeCell.getMinutes(); ss = timeCell.getSeconds();
  } else {
    const t = String(timeCell == null ? '' : timeCell).trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/);
    if (t) { hh = +t[1]; mi = +t[2]; ss = t[3] ? +t[3] : 0; }
  }

  const dt = new Date(y, mo, da, hh, mi, ss);
  return isNaN(dt) ? null : dt.getTime();
}

// Always returns a usable Date. The old inline `b.called_at || new Date()` let whitespace,
// unresolved Mustache tokens and unparseable strings through, which then wrote a blank or
// garbage date and dropped the lead out of every windowed count (Fix Queue #7b).
function parseDate_(v) {
  const s = String(v == null ? '' : v).trim();
  if (!s || /[{}]/.test(s)) return new Date();           // missing, or an unresolved template token
  const d = new Date(s);
  if (!isNaN(d) && d.getFullYear() > 2000 && d.getFullYear() < 2100) return d;
  // last resort: a bare yyyy-mm-dd prefix, e.g. "2026-08-13 14:02:11 CDT"
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) { const d2 = new Date(+m[1], +m[2] - 1, +m[3]); if (!isNaN(d2)) return d2; }
  return new Date();                                      // webhook is live: "now" is accurate to the second
}

// attribution: gclid -> Paid Search; fbclid -> Paid Social; else infer from Traffic Source.
// NOTE: the form's Traffic Source field is EITHER a referrer URL (e.g. https://www.google.com/)
// OR a literal keyword the form writes ("Direct" when there is no referrer). Handle both.
function webSource_(gclid, fbclid, referrer) {
  if (gclid) return 'Paid Search';
  if (fbclid) return 'Paid Social';
  const r = lc_(referrer);
  if (!r || r === 'direct' || r === '(direct)' || r === 'none') return 'Direct';
  if (/roofingforce\.com/.test(r)) return 'Direct';                 // self-referral
  if (/chatgpt|openai|perplexity|gemini|copilot|claude/.test(r)) return 'AI Referral';
  if (/google|bing|yahoo|duckduckgo|ecosia|organic|search/.test(r)) return 'Organic Search';
  if (/facebook|instagram|fb\.com|paid_social/.test(r)) return 'Paid Social';
  return 'Referral';                                                // a real external referrer
}
// market from the page-visit trail (/locations/<slug>/), with a city/state fallback.
function marketFromJourney_(journey) {
  const j = lc_(journey);
  if (/fort-smith|mena/.test(j)) return 'FortSmith-Mena';
  if (/kansas-city|olathe|overland/.test(j)) return 'Olathe-KC';
  if (/springfield|joplin/.test(j)) return 'Joplin-SGF';
  if (/wichita/.test(j)) return 'Wichita';
  if (/st-louis|saint-louis|stlouis/.test(j)) return 'St-Louis';
  return '';
}
function marketFromText_(cs) {
  const t = lc_(cs);
  if (/wichita/.test(t)) return 'Wichita';
  if (/saint charles|st\.? *charles|st\.? *louis|saint louis/.test(t)) return 'St-Louis';
  if (/springfield|joplin|nixa|ozark|carthage/.test(t)) return 'Joplin-SGF';
  if (/fort smith|mena|pocola|van buren|greenwood|poteau/.test(t)) return 'FortSmith-Mena';
  if (/olathe|overland|kansas city|shawnee|lenexa|leawood|lawrence|gardner/.test(t)) return 'Olathe-KC';
  return 'Other';
}
function firstUrl_(journey) { const m = String(journey || '').match(/https?:\/\/[^\s|]+/); return m ? m[0] : ''; }
function e164_(v) { const d = norm10_(v); return d ? '+1' + d : ''; }
function prettyPhone_(v) { const d = norm10_(v); return d ? '(' + d.slice(0,3) + ') ' + d.slice(3,6) + '-' + d.slice(6) : (v || ''); }
function norm10_(v) { const x = String(v == null ? '' : v).replace(/[^0-9]/g, ''); return x.length >= 10 ? x.slice(-10) : ''; }
function lc_(v) { return String(v == null ? '' : v).trim().toLowerCase(); }
function ymd_(v) { if (!v) return ''; const d = new Date(v); return isNaN(d) ? String(v).slice(0,10) : Utilities.formatDate(d, 'America/Denver', 'yyyy-MM-dd'); }
function time_(v) { if (!v) return ''; const d = new Date(v); return isNaN(d) ? '' : Utilities.formatDate(d, 'America/Denver', 'H:mm:ss'); }
function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

/* ---------- tests (run from the editor — no trailing underscore so they show in the Run menu) ---------- */
function testForm() {
  const out = appendLead_(normalizeForm_({
    source:'formidable', first_name:'Test', last_name:'Web', email:'TEST@web.com', phone:'816-555-1212',
    street:'123 Test St', city:'Olathe', state:'Kansas', zip:'66061',
    message:'Need a full roof replacement, hail damage last month.',
    gclid:'EAItestgclid123', fbclid:'', traffic_source:'https://www.google.com/',
    utm_source:'', utm_medium:'',
    user_journey:'2026 June 2 12:09:04 | Fort Smith Roofers | https://roofingforce.com/locations/fort-smith/ | 7 seconds',
    created_at:'2026-06-02T10:15:00'
  }));
  Logger.log(out);
}
function testCtm() {
  const out = appendLead_(normalizeCtm_({
    source:'ctm', id:'TEST-CALL-0001', caller_number:'+18165551313', tracking_number:'(913) 270-3041',
    name:'Test Caller', street:'5 Test Ave', city:'Kansas City', state:'MO', zip:'64101',
    called_at:'2026-06-02T11:00:00', ctm_source:'Google Ads', gclid:'',
    campaign:'St. Louis - Search', keyword:'roofing contractor'
  }));
  Logger.log(out);
}

/**
 * THE VERIFICATION. Run this ONE function after pasting — it proves the defect is dead
 * without you having to wait for a real repeat caller. It writes three test rows, checks
 * the outcomes, then DELETES the rows it created. Read the log.
 *
 * Expected log:
 *   1. same caller, NEW call id, 90 days later  -> APPENDED   <- this is the fix
 *   2. same call id delivered twice (CTM retry) -> SKIPPED    <- real duplicates still caught
 *   3. no call id, same number 2 minutes later  -> SKIPPED    <- window fallback works
 */
function verifyRepeatCallerFix() {
  const sh = SpreadsheetApp.openById(SHEET_ID).getSheetByName(LEADS_TAB);
  const phone = '+18165550199';                       // a number that appears nowhere in Leads
  const created = [];
  const log = [];
  const base = {
    source:'ctm', caller_number: phone, tracking_number:'(913) 270-3041',
    name:'ZZ Verify', city:'Olathe', state:'Kansas', ctm_source:'Google Ads'
  };
  try {
    const a = appendLead_(normalizeCtm_(Object.assign({}, base,
      { id:'VERIFY-A', called_at:'2026-05-01T09:00:00' })));
    if (a.row) created.push(a.row);

    const b = appendLead_(normalizeCtm_(Object.assign({}, base,
      { id:'VERIFY-B', called_at:'2026-07-30T14:00:00' })));   // same caller, months later, new id
    if (b.row) created.push(b.row);

    const c = appendLead_(normalizeCtm_(Object.assign({}, base,
      { id:'VERIFY-B', called_at:'2026-07-30T14:00:05' })));   // CTM redelivers the SAME call

    const d = appendLead_(normalizeCtm_(Object.assign({}, base,
      { called_at:'2026-07-30T14:02:00' })));                  // no id at all, 2 min later
    if (d.row) created.push(d.row);

    log.push('1. repeat caller, new call id  -> ' + (b.row ? 'APPENDED  PASS' : 'SKIPPED  FAIL <<<'));
    log.push('2. same call id redelivered    -> ' + (c.skipped ? 'SKIPPED   PASS (' + c.by + ')' : 'APPENDED FAIL <<<'));
    log.push('3. no id, 2 min later          -> ' + (d.skipped ? 'SKIPPED   PASS (' + d.by + ')' : 'APPENDED FAIL <<<'));
  } catch (err) {
    log.push('ERROR: ' + err);
  } finally {
    // clean up newest-first so row numbers stay valid
    created.sort((x, y) => y - x).forEach(r => sh.deleteRow(r));
    log.push('cleaned up ' + created.length + ' test row(s)');
  }
  Logger.log(log.join('\n'));
}
