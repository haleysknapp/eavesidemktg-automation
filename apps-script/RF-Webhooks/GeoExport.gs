/**
 * RF — AccuLynx geo export  ·  FIXED 2026-08-07
 * ============================================================================
 * Two bugs in the previous version:
 *
 *  1. PAGINATION PARAM NAME. It sent  &recordStartIndex=  , which the AccuLynx
 *     API does not recognise and silently ignores — so every request returned
 *     page 1. The local `start` counter advanced fine, the API just never moved.
 *     Result: the same 25 records written 939 times = 23,475 rows, all created
 *     Jan 1-4 2022. The working param is  &pageStartIndex=  (proven in
 *     RF-acculynx-master.gs / rfm_fetchAll_).
 *
 *  2. ADDRESS SOURCE. It read the address off the CONTACT
 *     (contact.mailingAddress), which is empty on these records, so city /
 *     state / zip / street came back blank on all 23,475 rows. The job's own
 *     address is  job.locationAddress { street1, city, state, zipCode }.
 *
 * Also added: jobId (lets rows be de-duped and joined to the master cache),
 * resumable slices so a multi-year pull survives the 6-minute execution limit,
 * and 429 backoff.
 *
 * HOW TO RUN
 *   1. geoExportTestOne()  — proves both fixes before pulling anything.
 *   2. geoExportReset()    — clears the tab + cursor for a fresh pull.
 *   3. exportJobsGeo()     — run repeatedly until the log says GEO EXPORT COMPLETE.
 */

var GEO_TAB        = 'AccuLynx Geo Export';
var GEO_START_DATE = '2025-01-01';        // pull window start; end = today
var GEO_PAGE       = 25;                  // AccuLynx max page size
var GEO_SLICE_MS   = 4.5 * 60 * 1000;     // stay under the 6-minute limit
var GEO_HEADERS    = ['jobId', 'createdDate', 'milestoneDate', 'milestone',
                      'leadSource', 'city', 'state', 'zip', 'street'];

function exportJobsGeo() {
  var t0 = Date.now();
  var p  = PropertiesService.getScriptProperties();
  var key = p.getProperty('ACCULYNX_API_KEY');
  var ss  = SpreadsheetApp.openById(p.getProperty('AUDIT_SPREADSHEET_ID'));
  var sh  = ss.getSheetByName(GEO_TAB) || ss.insertSheet(GEO_TAB);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1, 1, GEO_HEADERS.length).setValues([GEO_HEADERS]);
  }

  var start = parseInt(p.getProperty('GEO_CURSOR') || '0', 10);
  var end   = Utilities.formatDate(new Date(), 'America/Denver', 'yyyy-MM-dd');
  var out = [], total = 0, done = false;

  while (true) {
    if (Date.now() - t0 > GEO_SLICE_MS) break;

    var url = 'https://api.acculynx.com/api/v2/jobs'
            + '?pageSize=' + GEO_PAGE
            + '&pageStartIndex=' + start            // <-- FIX 1
            + '&startDate=' + GEO_START_DATE
            + '&endDate=' + end
            + '&dateFilterType=CreatedDate&sortBy=CreatedDate&sortOrder=Ascending';

    var r = UrlFetchApp.fetch(url, {
      headers: { Authorization: 'Bearer ' + key }, muteHttpExceptions: true
    });
    if (r.getResponseCode() === 429) { Utilities.sleep(2000); continue; }
    if (r.getResponseCode() !== 200) {
      throw new Error('HTTP ' + r.getResponseCode() + ': ' + r.getContentText().slice(0, 300));
    }

    var d = JSON.parse(r.getContentText());
    total = d.count || 0;
    var items = d.items || [];
    for (var i = 0; i < items.length; i++) out.push(geoRow_(items[i]));

    start += GEO_PAGE;
    if (items.length < GEO_PAGE || start >= total) { done = true; break; }
  }

  if (out.length) {
    sh.getRange(sh.getLastRow() + 1, 1, out.length, GEO_HEADERS.length).setValues(out);
  }

  if (done) {
    p.deleteProperty('GEO_CURSOR');
    Logger.log('GEO EXPORT COMPLETE. sheet data rows=%s  API total=%s', sh.getLastRow() - 1, total);
  } else {
    p.setProperty('GEO_CURSOR', String(start));
    Logger.log('Slice done: wrote %s rows, next pageStartIndex=%s of %s — run exportJobsGeo() again.',
               out.length, start, total);
  }
}

function geoRow_(j) {
  var a = j.locationAddress || {};          // <-- FIX 2
  return [
    j.id || '',
    j.createdDate || '',
    j.milestoneDate || '',
    j.currentMilestone || '',
    (j.leadSource || {}).name || '',
    String(a.city || '').trim(),
    String((a.state && a.state.name) || a.state || '').trim(),
    String(a.zipCode || '').replace(/\D/g, '').slice(0, 5),
    String(a.street1 || '').trim()
  ];
}

function geoExportReset() {
  var p = PropertiesService.getScriptProperties();
  p.deleteProperty('GEO_CURSOR');
  var ss = SpreadsheetApp.openById(p.getProperty('AUDIT_SPREADSHEET_ID'));
  var sh = ss.getSheetByName(GEO_TAB) || ss.insertSheet(GEO_TAB);
  sh.clear();
  sh.getRange(1, 1, 1, GEO_HEADERS.length).setValues([GEO_HEADERS]);
  Logger.log('Geo export reset — tab cleared, cursor cleared. Now run exportJobsGeo().');
}

/* Proves BOTH fixes before we pull 24 months of data. */
function geoExportTestOne() {
  var p = PropertiesService.getScriptProperties();
  var key = p.getProperty('ACCULYNX_API_KEY');
  var end = Utilities.formatDate(new Date(), 'America/Denver', 'yyyy-MM-dd');
  var base = 'https://api.acculynx.com/api/v2/jobs?pageSize=2&startDate=' + GEO_START_DATE
           + '&endDate=' + end + '&dateFilterType=CreatedDate&sortBy=CreatedDate&sortOrder=Ascending';
  var opt = { headers: { Authorization: 'Bearer ' + key }, muteHttpExceptions: true };

  var d1 = JSON.parse(UrlFetchApp.fetch(base + '&pageStartIndex=0', opt).getContentText());
  var d2 = JSON.parse(UrlFetchApp.fetch(base + '&pageStartIndex=2', opt).getContentText());

  Logger.log('API count for %s..%s = %s', GEO_START_DATE, end, d1.count);
  Logger.log('page1 row0: %s', JSON.stringify(geoRow_(d1.items[0])));
  Logger.log('page2 row0: %s', JSON.stringify(geoRow_(d2.items[0])));
  Logger.log(d1.items[0].id === d2.items[0].id
    ? '*** FIX 1 FAILED — pagination still returning page 1 ***'
    : 'FIX 1 OK — pageStartIndex advances (different job ids)');
  var a = geoRow_(d1.items[0]);
  Logger.log((a[5] || a[7])
    ? 'FIX 2 OK — city/zip populated: ' + a[5] + ' ' + a[7]
    : '*** FIX 2 FAILED — address still blank ***');
}
