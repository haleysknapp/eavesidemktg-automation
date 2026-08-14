/**
 * Eaveside-Call-Grader.gs  —  central, multi-client, multi-provider call grader
 * =============================================================================
 * ONE standalone Apps Script project (Eaveside-owned, NOT bound to any client sheet).
 * Holds keys centrally, loops over configured clients, and for each: fetches new calls
 * from that client's provider (CTM / CallRail / ...) -> downloads recording -> transcribes
 * (Deepgram) -> grades (Claude) -> writes into THAT client's sheet.
 *
 * WHY standalone: the keys live here, never in a client sheet. You can share any client
 * sheet (even Editor, with the client's whole team) and there's nothing sensitive to find.
 * Adding a client = one entry in CLIENTS below + their key in Script Properties. No rebuild.
 *
 * SETUP (one time):
 *   1. script.google.com -> New project (NOT inside a sheet). Paste this file in.
 *   2. Project Settings -> Script Properties, add the SHARED keys:
 *        DEEPGRAM_API_KEY, ANTHROPIC_API_KEY
 *      and each client's provider key, e.g.:  RF_CTM_BASIC_AUTH = <token>
 *   3. Make sure this script's Google account has EDIT access to each client sheet.
 *   4. Run rfGrade_testOne() -> Execution log grades ONE call for the first client, no writes.
 *   5. Run rfGrade_installTrigger() -> every-30-min run across all clients.
 */
/**
 * ---------------------------------------------------------------------------
 * 2026-08-12 - ADDITIVE PATCH (columns only, no flow change)
 * ---------------------------------------------------------------------------
 * (a) Claude's `booked` flag is now PERSISTED. It used to survive only inside the
 *     composed next_step string ("BOOKED - not in AccuLynx, confirm"), so nothing
 *     downstream could rebuild that case by formula.
 * (b) next_step is now RECOMPUTABLE. It is still written exactly as before (col I),
 *     but the raw inputs _nextStep() derives from are now written alongside it, so
 *     `Lead Detail` can recompute the CURRENT next step by formula instead of
 *     reading a string frozen at grade time.
 *
 * NEW `Call Grades` columns, APPENDED at L..P. Columns A..K are untouched and keep
 * their existing positions/meanings - no existing index shifts.
 *     L  booked                (TRUE/FALSE)  Claude's booked signal
 *     M  job_market            served_market | out_of_area | ''
 *     N  acx_status_at_grade   Leads!AB as it read at grade time
 *     O  in_crm_at_grade       Leads!AC as it read at grade time (Y/'')
 *     P  dispute_eligible      (TRUE/FALSE)  LSA + junk lead_type
 *
 * N and O are grade-time SNAPSHOTS, kept for audit/diff. A live-refreshing formula
 * should read Leads!AB/AC through leads_row (col J), not these.
 *
 * Missing columns are self-healing: _ensureGradeCols() widens the sheet and writes
 * the L..P headers on the next run if they are absent. It only ever touches columns
 * 12..16 and never rewrites A..K.
 * ---------------------------------------------------------------------------
 */

// ======================= CLIENT CONFIG =======================
// Add a client by copying a block. provider: 'ctm' (working) | 'callrail' (adapter stub).
var CLIENTS = [
  {
    id: 'roofing-force',
    provider: 'ctm',
    account: '425821',                 // CTM account id (or CallRail account id)
    keyProp: 'RF_CTM_BASIC_AUTH',      // Script Property holding this client's provider key
    sheetId: '1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc',
    leadsTab: 'Leads',
    gradeTab: 'Call Grades',
    // Leads columns (1-based) to stamp: AN..AS
    cols: {grade:40, quality:41, summary:42, insurance:43, next_step:44, callid:45}
  }
  // ,{ id:'client-two', provider:'callrail', account:'<callrail acct>', keyProp:'C2_CALLRAIL_KEY',
  //    sheetId:'<their sheet id>', leadsTab:'Leads', gradeTab:'Call Grades', cols:{...} }
];

var MODEL = 'claude-sonnet-5';
var BATCH_PER_CLIENT = 50;
var LOOKBACK_HOURS = 48;
var MIN_TALK = 15;

// ---------------------------------------------------------------------------
// 2026-08-13 - GEOGRAPHY FIX
// ---------------------------------------------------------------------------
// The model was writing job_market='out_of_area' on calls with no geographic
// objection at all (67 of 674; 38 with a blank objection). The prompt already
// listed the served towns and already said "when unsure prefer served_market" -
// it was ignored. So the served-town list is now DATA, not prose:
//   * MARKETS below is the single source of truth. GRADE_PROMPT is BUILT from it,
//     reconciled against rf_served_zips.csv (IN + BORDER = served). Hot Springs
//     is no longer cited as out-of-area - it is BORDER, next to served Mount Ida.
//   * _resolveGeo() overrides the model AFTER it returns, by table lookup.
//   * out_of_area now requires corroboration from `objection`. Scope problems
//     (mobile home, attic vent) are service_type/out_of_scope, never geography.
// New model output keys: caller_town, objection, missed_lead.
// New `Call Grades` columns: AD missed_lead, AE objection, AF geo_source. NOT Q/R/S -
// Q..AC are live calc columns owned by the sheet and are never touched by this script.
// ---------------------------------------------------------------------------
var MARKETS = [
  {name:'Kansas City', radius:'~26mi', towns:['Adrian', 'Archie', 'Basehor', 'Bates City', 'Belton', 'Blue Springs', 'Bonner Springs', 'Bucyrus', 'Butler', 'Camden Point', 'Cameron', 'Carrollton', 'Centerview', 'Chillicothe', 'Cleveland', 'Clinton', 'De Soto', 'Deepwater', 'Drexel', 'Easton', 'Eudora', 'Excelsior Springs', 'Faucett', 'Fort Leavenworth', 'Freeman', 'Gardner', 'Grain Valley', 'Grandview', 'Greenwood', 'Harrisonville', 'Henrietta', 'Holden', 'Holt', 'Independence', 'Kansas City', 'Kearney', 'Kincaid', 'Lacygne', 'Lane', 'Lansing', 'Lathrop', 'Leavenworth', 'Leawood', 'Lees Summit', 'Lenexa', 'Lexington', 'Liberty', 'Linwood', 'Lone Jack', 'Louisburg', 'Maysville', 'Mayview', 'Miami', 'Mission', 'Mound City', 'Oak Grove', 'Odessa', 'Olathe', 'Osawatomie', 'Overland Park', 'Paola', 'Platte City', 'Plattsburg', 'Pleasant Hill', 'Pleasanton', 'Prairie Village', 'Rantoul', 'Raymore', 'Riverside', 'Saint Joseph', 'Savannah', 'Shawnee', 'Smithville', 'Spring Hill', 'Stilwell', 'Tonganoxie', 'Trimble', 'Warrensburg', 'Wathena', 'Wellington', 'Wellsville', 'Weston']},
  {name:'Joplin', radius:'~36mi', towns:['Afton', 'Alba', 'Arcadia', 'Asbury', 'Baxter Springs', 'Carl Junction', 'Carterville', 'Carthage', 'Chetopa', 'Coffeyville', 'Columbus', 'Commerce', 'Crestline', 'Diamond', 'Duenweg', 'Erie', 'Fairland', 'Fairview', 'Fort Scott', 'Frontenac', 'Galena', 'Galesburg', 'Girard', 'Golden City', 'Goodman', 'Granby', 'Grove', 'Harwood', 'Iola', 'Jasper', 'Joplin', 'Lamar', 'Liberal', 'Lockwood', 'Mc Cune', 'Miami', 'Monett', 'Mound Valley', 'Mulberry', 'Neosho', 'Nevada', 'Oronogo', 'Oswego', 'Parsons', 'Pierce City', 'Pittsburg', 'Quapaw', 'Redfield', 'Reeds', 'Riverton', 'Sarcoxie', 'Scammon', 'Seneca', 'Stark City', 'Vinita', 'Webb City', 'Weir', 'Welch', 'Wentworth', 'Wyandotte']},
  {name:'NW Arkansas', radius:'~28mi', towns:['Anderson', 'Bella Vista', 'Bentonville', 'Cassville', 'Cave Springs', 'Centerton', 'Colcord', 'Elkins', 'Eucha', 'Eureka Springs', 'Everton', 'Farmington', 'Fayetteville', 'Garfield', 'Gentry', 'Golden', 'Gravette', 'Harrison', 'Hindsville', 'Hiwasse', 'Huntsville', 'Jasper', 'Jay', 'Kansas', 'Lampe', 'Lincoln', 'Lowell', 'Noel', 'Pea Ridge', 'Pineville', 'Purdy', 'Rogers', 'Saint Paul', 'Salina', 'Seligman', 'Shell Knob', 'Siloam Springs', 'South West City', 'Springdale', 'Sulphur Springs', 'Washburn', 'Watts', 'Wesley', 'West Fork', 'Western Grove', 'Westville', 'Wheaton', 'Winslow']},
  {name:'Fort Smith', radius:'~35mi', towns:['Alma', 'Altus', 'Arkoma', 'Barling', 'Bokoshe', 'Booneville', 'Branch', 'Cameron', 'Cedarville', 'Charleston', 'Chester', 'Clarksville', 'Dover', 'Evansville', 'Fort Smith', 'Gans', 'Gore', 'Greenwood', 'Hackett', 'Hartford', 'Howe', 'Huntington', 'Keota', 'Kinta', 'Knoxville', 'Lavaca', 'Magazine', 'Mansfield', 'Marble City', 'Mcalester', 'Mccurtain', 'Monroe', 'Mountainburg', 'Mulberry', 'Muldrow', 'Natural Dam', 'Ozark', 'Panama', 'Paris', 'Park Hill', 'Pocola', 'Porum', 'Poteau', 'Quinton', 'Ratcliff', 'Red Oak', 'Roland', 'Rudy', 'Russellville', 'Sallisaw', 'Shady Point', 'Spiro', 'Stigler', 'Stilwell', 'Subiaco', 'Tahlequah', 'Van Buren', 'Vian', 'Wister']},
  {name:'Mena', radius:'~24mi', towns:['Amity', 'Arkadelphia', 'Ashdown', 'Boles', 'Broken Bow', 'Caddo Gap', 'Clayton', 'Cove', 'De Queen', 'Dierks', 'Eagletown', 'Gillham', 'Glenwood', 'Grannis', 'Hatfield', 'Havana', 'Heavener', 'Hodgen', 'Honobia', 'Horatio', 'Hot Springs National Park', 'Idabel', 'Langley', 'Mena', 'Mount Ida', 'Murfreesboro', 'Nashville', 'Norman', 'Oden', 'Parks', 'Pearcy', 'Pencil Bluff', 'Rosston', 'Sims', 'Smithville', 'Story', 'Talihina', 'Texarkana', 'Tuskahoma', 'Valliant', 'Vandervoort', 'Waldron', 'Watson', 'Wickes', 'Wright City']},
  {name:'St. Louis', radius:'~35mi', towns:['Alhambra', 'Alton', 'Arnold', 'Ashley', 'Aviston', 'Ballwin', 'Barnhart', 'Belleville', 'Bethalto', 'Bismarck', 'Bloomsdale', 'Bourbon', 'Breese', 'Bridgeton', 'Centralia', 'Chesterfield', 'Collinsville', 'Columbia', 'Coulterville', 'Cuba', 'Defiance', 'Dupo', 'East Carondelet', 'East Saint Louis', 'Edwardsville', 'Eureka', 'Fairview Heights', 'Farmington', 'Fenton', 'Festus', 'Florissant', 'Glencoe', 'Godfrey', 'Granite City', 'Hazelwood', 'Herculaneum', 'High Ridge', 'Hillsboro', 'Hoffman', 'House Springs', 'Imperial', 'Lake Saint Louis', 'Lebanon', 'Litchfield', 'Maryland Heights', 'Maryville', 'Mascoutah', 'Moro', 'New Baden', 'O Fallon', 'Perryville', 'Pevely', 'Red Bud', 'Saint Charles', 'Saint Jacob', 'Saint Louis', 'Saint Peters', 'Salem', 'Sorento', 'Sparta', 'Springfield', 'Staunton', 'Trenton', 'Troy', 'Valley Park', 'Valmeyer', 'Vandalia', 'Washington', 'Waterloo', 'Wentzville', 'Wood River', 'Worden']},
  {name:'Springfield', radius:'~22mi', towns:['Ash Grove', 'Aurora', 'Ava', 'Billings', 'Blue Eye', 'Bois D Arc', 'Branson', 'Brookline', 'Camdenton', 'Clever', 'Climax Springs', 'El Dorado Springs', 'Fair Grove', 'Fordland', 'Galena', 'Greenfield', 'Hartville', 'Highlandville', 'Hollister', 'Kimberling City', 'Mansfield', 'Marionville', 'Marshfield', 'Mount Vernon', 'Mountain Grove', 'Nixa', 'Oldfield', 'Ozark', 'Reeds Spring', 'Republic', 'Rogersville', 'Seymour', 'Sparta', 'Spokane', 'Springfield', 'Strafford', 'Theodosia', 'Verona', 'Walnut Grove', 'Willard']},
  {name:'Topeka', radius:'~37mi', towns:['Allen', 'Atchison', 'Auburn', 'Baldwin City', 'Burlingame', 'Carbondale', 'Emporia', 'Eskridge', 'Hiawatha', 'Junction City', 'Lawrence', 'Le Roy', 'Lecompton', 'Lyndon', 'Manhattan', 'Mc Louth', 'Meriden', 'Nortonville', 'Ottawa', 'Overbrook', 'Ozawkie', 'Perry', 'Pomona', 'Princeton', 'Quenemo', 'Scranton', 'Seneca', 'Topeka', 'Valley Falls']},
  {name:'Wichita', radius:'~6mi', towns:['Arkansas City', 'Belle Plaine', 'Bentley', 'Clearwater', 'Florence', 'Haysville', 'Hillsboro', 'Kechi', 'Maize', 'Mcpherson', 'Newton', 'Salina', 'Sedgwick', 'Valley Center', 'Wichita']},
];

// Towns that appear ONLY as OUT in the 24-month footprint. Anything not in either
// table is UNKNOWN -> we do not guess out_of_area.
var CLEAR_OUT_TOWNS = ['Atlanta', 'Benton', 'Bethany', 'Big Sandy', 'Boulder', 'Bradley', 'Brainerd', 'Cabot', 'Cassopolis', 'Central', 'Conway', 'Corsicana', 'Deerfield Beach', 'Draper', 'East Peoria', 'El Paso', 'Fortville', 'Gardena', 'Haviland', 'Heber Springs', 'Houston', 'Jefferson City', 'Killeen', 'Kinsley', 'La Grange', 'Las Vegas', 'Lehi', 'Little Rock', 'Live Oak', 'Lubbock', 'Marion', 'Melbourne', 'Mundelein', 'Ness City', 'New Era', 'New Orleans', 'New York', 'Norfolk', 'North Little Rock', 'Oklahoma City', 'Orange Park', 'Orland Park', 'Placentia', 'Plumerville', 'Salt Lake City', 'San Antonio', 'San Diego', 'San Francisco', 'San Leandro', 'Sandy', 'Seminole', 'Sheridan', 'South Beloit', 'Spanish Fork', 'Sperry', 'Springville', 'Syracuse', 'Tulsa', 'Tuscaloosa', 'Viola', 'Woodward', 'Yukon'];

function _townKey(t){ return (''+(t||'')).toLowerCase().replace(/[^a-z ]/g,'').replace(/\s+/g,' ').trim(); }
var SERVED_TOWNS = (function(){ var m={}; MARKETS.forEach(function(k){ k.towns.forEach(function(t){ m[_townKey(t)]=k.name; }); }); return m; })();
var OUT_TOWNS = (function(){ var m={}; CLEAR_OUT_TOWNS.forEach(function(t){ if(!SERVED_TOWNS[_townKey(t)]) m[_townKey(t)]=true; }); return m; })();

var GRADE_PROMPT =
"You grade an inbound phone call for a roofing company. lead_type (one of): real_lead (genuine roofing-work "+
"prospect; out-of-area is STILL real_lead, grade D), out_of_scope, spam_robocall, solicitation_vendor, "+
"existing_customer (a returning customer wanting NEW work is real_lead), wrong_number, job_seeker, not_reached "+
"(dead air/hang-up/voicemail with no message; a voicemail stating a real roofing need is real_lead). If real_lead, "+
"quality_grade A/B/C/D (A=hot/urgent/insurance/in-area), else null. Also: service_type, job_market "+
"(served_market/out_of_area/null), caller_town, objection, missed_lead, booked (true/false), "+
"insurance_claim (true/false), summary (1-2 sentences), confidence (0-1). "+
"caller_town: the town/city the CALLER states the JOB is in, exactly as said, or null if never stated. "+
"Do not infer it from area code, from the office the rep mentions, or from the ad. Null is the correct "+
"answer for most calls. "+
"objection (one of): location, price, timeline, just_looking, out_of_scope, none. Use `location` ONLY when the "+
"caller or the rep says the job is outside the service area. Use `out_of_scope` when the rep declines the work, "+
"refers the caller elsewhere, or says the company does not do that kind of job. "+
"service_type (one of): roof_replace, roof_repair, gutters, material_only (caller wants to BUY materials with no "+
"installation), mobile_home (mobile home, trailer, single-wide or double-wide), small_repair (a single vent, one "+
"flashing, a short gutter section, or similar low-ticket single-item work), inspection, commercial, other. "+
"job_market: use served_market unless the caller names a town and that town is clearly in another region. "+
"NEVER use out_of_area for a scope problem. Mobile home / trailer / double-wide roofs, attic turbine vents, "+
"gutters, small repairs and other work the company may not take are service_type + objection=out_of_scope, "+
"with job_market left as served_market or null. A caller who is simply price shopping is objection=price or "+
"just_looking, NOT out_of_area. "+
"missed_lead (true/false): true when a genuine roofing prospect ended the call without the rep capturing a name, "+
"phone or address, or without booking - including when the rep was unsure whether the town is served and did not "+
"find out. This is the operational-failure flag; set it independently of lead quality. "+
"SERVICE AREA (7,047 won jobs Jan2025-Aug2026, reconciled with the 24-month served-ZIP footprint): RF serves "+
"9 markets. A caller is IN-AREA if their town is within the market radius below OR in its served-town list. "+
"Border OK/KS/AR towns near Fort Smith, Topeka and Mena ARE served. Only mark out_of_area when the town is "+
"clearly in another region entirely (Little Rock, Tulsa, Oklahoma City, Dallas, Houston). When unsure, prefer "+
"served_market. Served markets and towns: "+
MARKETS.map(function(k){ return k.name+' ('+k.radius+'): '+k.towns.join(', '); }).join(' | ')+". "+
"Return ONLY JSON with keys: lead_type, quality_grade, service_type, job_market, caller_town, objection, "+
"missed_lead, booked, insurance_claim, summary, confidence.";

// ---------------------------------------------------------------------------
// 2026-08-13 - SCOPE POLICY
// ---------------------------------------------------------------------------
// Scope was being laundered through geography: "we don't do that" came out as
// out_of_area. These are separate questions and now have separate answers.
//
// Each verdict below is derived from what the reps ACTUALLY DID across 514 graded
// calls (May-Jul 2026), not from an assumption about the business:
//   material_only  declined 8/8 - slate, terra cotta, rubber membrane, standing
//                  seam, discount shingles, metal siding. Every market. Settled.
//   small_repair   declined or referred out; the bent-gutter call is explicit:
//                  "RF only does full gutter replacements."
//   gutters        NOT out of scope - full gutter replacement is quoted and booked
//                  repeatedly. The line is job SIZE, not the category.
//   mobile_home    UNRESOLVED. 4792070431 (Jun 17, Fort Smith) was BOOKED for a full
//                  metal roof; 9186476641 (Jul 31) was written off. Same company,
//                  same month, opposite answers. Flagged for a human, not guessed.
// Change a verdict by editing this map - nothing else needs to move.
var SCOPE_POLICY = {
  material_only: 'out',        // supply/materials with no installation
  small_repair:  'out',        // single vent, one flashing, a bent gutter section
  mobile_home:   'unclear',    // <- Chad decides; grader will not guess
  gutters:       'in',
  roof_replace:  'in',
  roof_repair:   'in',
  inspection:    'in',
  commercial:    'in',
  other:         'in'
};

// Returns '' when in scope, else the next_step to write.
function _scopeStep(g){
  var st  = (''+(g.service_type||'')).toLowerCase().replace(/[^a-z]+/g,'_');
  var obj = (''+(g.objection||'')).toLowerCase();
  var verdict = SCOPE_POLICY[st];
  if(verdict === 'unclear') return 'SCOPE UNCLEAR - '+st+' - confirm with client';
  if(verdict === 'out')     return 'OUT OF SCOPE - '+st;
  // The model saw the rep decline but the service_type is not in the map. Surface it
  // rather than silently treating it as a callable lead.
  if(obj === 'out_of_scope') return 'OUT OF SCOPE - review ('+(st||'unspecified')+')';
  return '';
}

// Authoritative geography, applied AFTER the model returns. Returns a short provenance
// string written to `geo_source` so a wrong call can be traced to the rule that made it.
function _resolveGeo(g){
  var town = _townKey(g.caller_town);
  var obj  = (''+(g.objection||'')).toLowerCase();
  if(town && SERVED_TOWNS[town]){ g.job_market='served_market'; return 'town:'+SERVED_TOWNS[town]; }
  if(town && OUT_TOWNS[town]){    g.job_market='out_of_area';   return 'town:out'; }
  if((''+(g.job_market||'')).toLowerCase()=='out_of_area'){
    // out_of_area with no supporting location objection, or with no town ever named, is the
    // exact failure mode this fix exists for. Fall back to the prompt's own tie-break rule
    // ("when unsure, prefer served_market") for a real prospect; blank for junk lead types.
    var real = g.lead_type=='real_lead' || g.lead_type=='existing_customer';
    if(obj!='location'){ g.job_market = real?'served_market':''; return 'cleared:no-location-objection'; }
    if(!town){ g.job_market = real?'served_market':''; return 'cleared:no-town-named'; }
    return 'model:corroborated';
  }
  if(!g.job_market && town) g.job_market='served_market';   // named a town we do not know -> prefer served
  return 'model';
}

// (For a non-roofing client, give that client its own prompt via a client.rubric field and use it here.)

// ======================= ENTRY POINTS =======================
function rfGrade_testOne(){ _runClient(CLIENTS[0], 1, true); }
function rfGrade_run(){ CLIENTS.forEach(function(c){ try{ _runClient(c, BATCH_PER_CLIENT, false);}catch(e){ Logger.log(c.id+' error: '+e); } }); }
function rfGrade_installTrigger(){
  ScriptApp.getProjectTriggers().forEach(function(t){ if(t.getHandlerFunction()=='rfGrade_run') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('rfGrade_run').timeBased().everyHours(1).create();  // hourly is plenty
  Logger.log('Trigger installed.');
}

// ======================= CORE (provider-agnostic) =======================
function _runClient(client, limit, dry){
  var props = PropertiesService.getScriptProperties();
  var dg = props.getProperty('DEEPGRAM_API_KEY'), an = props.getProperty('ANTHROPIC_API_KEY');
  var provKey = props.getProperty(client.keyProp);
  if(!dg || !an || !provKey){ Logger.log(client.id+': missing a key (DEEPGRAM/ANTHROPIC/'+client.keyProp+').'); return; }

  var ss = SpreadsheetApp.openById(client.sheetId);
  var gradeSheet = _ensureGradeTab(ss, client.gradeTab);
  var graded = _gradedIds(gradeSheet);

  var calls = ADAPTERS[client.provider].fetchCalls(client, provKey);   // <-- provider adapter
  var done = 0;
  for(var i=0;i<calls.length && done<limit;i++){
    var c = calls[i];                            // normalized: {id, recordingUrl, source, phone, date, talk}
    if(graded[String(c.id)]) continue;
    // Same phone on the same day was graded before (under a different call_id) and the two
    // verdicts disagreed 56 times. One grade per phone+date.
    var pdKey = c.phone+'|'+c.date;
    if(c.phone && graded['pd:'+pdKey]){ Logger.log(client.id+' '+c.id+': skip dup '+pdKey); continue; }
    if((c.talk||0) < MIN_TALK || !c.recordingUrl) continue;

    var audio = ADAPTERS[client.provider].download(c, provKey);
    if(!audio){ Logger.log(client.id+' '+c.id+': no audio'); continue; }
    var transcript = _deepgram(audio.bytes, audio.type, dg);
    if(!transcript){ Logger.log(client.id+' '+c.id+': transcribe fail'); continue; }
    var g = _claude(transcript, {source:c.source, phone:c.phone, date:c.date, talk:c.talk}, an);
    if(!g || !g.lead_type){ Logger.log(client.id+' '+c.id+': grade fail'); continue; }
    var geoSrc = _resolveGeo(g);   // table lookup overrides the model's job_market

    if(dry){
      Logger.log('--- DRY RUN '+client.id+' call '+c.id+' ---');
      Logger.log('transcript: '+transcript.substring(0,300));
      Logger.log('grade: '+JSON.stringify(g));
      return;
    }
    var stamped = _stampLead(ss, client, c.phone, c.date, g, c.id);
    gradeSheet.appendRow([c.id, c.date, c.source||'', c.phone, g.lead_type, g.quality_grade||'',
                          g.insurance_claim?'Y':'', (g.summary||'').substring(0,120), stamped.next_step, stamped.row||'', new Date(),
                          // 2026-08-12: cols L..P. Everything above this line is byte-identical to
                          // the previous version - A..K keep their exact positions and values.
                          _truthy(g.booked), g.job_market||'', stamped.al||'', stamped.inacx||'',
                          _disputeEligible(c.source, g.lead_type)]);
    // AD..AF written separately so the append never reaches into the calc block Q..AC.
    gradeSheet.getRange(gradeSheet.getLastRow(), EXT_START_COL, 1, 4)
              .setValues([[_truthy(g.missed_lead), g.objection||'', geoSrc, g.service_type||'']]);
    graded[String(c.id)]=true; if(c.phone) graded['pd:'+c.phone+'|'+c.date]=true; done++;
  }
  Logger.log(client.id+': graded '+done+' new call(s).');
}

// ======================= PROVIDER ADAPTERS =======================
var ADAPTERS = {
  ctm: {
    fetchCalls: function(client, auth){
      var since = Utilities.formatDate(new Date(Date.now()-LOOKBACK_HOURS*3600*1000), 'UTC', 'yyyy-MM-dd');
      var url = 'https://api.calltrackingmetrics.com/api/v1/accounts/'+client.account+'/calls.json?start_date='+since+'&per_page=100';
      var res = UrlFetchApp.fetch(url, {headers:{Authorization:'Basic '+auth}, muteHttpExceptions:true});
      if(res.getResponseCode()!=200){ Logger.log('CTM '+res.getResponseCode()); return []; }
      var j = JSON.parse(res.getContentText()); var raw = j.calls||j.data||[];
      return raw.map(function(c){
        var t=c.talk_time; if(typeof t=='string'&&t.indexOf(':')>=0){var p=t.split(':');t=(+p[p.length-2])*60+(+p[p.length-1]);} t=parseInt(t||0,10)||0;
        return {id:c.id, recordingUrl:c.audio, source:c.source, phone:_norm(c.caller_number_bare||c.caller_number), date:(c.called_at||'').substring(0,10), talk:t};
      });
    },
    download: function(c, auth){
      var r = UrlFetchApp.fetch(c.recordingUrl, {headers:{Authorization:'Basic '+auth}, followRedirects:false, muteHttpExceptions:true});
      var code=r.getResponseCode();
      if(code==200){ var b=r.getBlob(); return {bytes:b.getBytes(), type:b.getContentType()||'audio/mpeg'}; }
      if(code>=300&&code<400){ var loc=r.getHeaders()['Location']; if(loc){ var s=UrlFetchApp.fetch(loc,{muteHttpExceptions:true}); if(s.getResponseCode()==200){var bb=s.getBlob(); return {bytes:bb.getBytes(), type:bb.getContentType()||'audio/mpeg'};}}}
      return null;
    }
  },
  callrail: {
    // TODO when the first CallRail client onboards. CallRail REST:
    //   GET https://api.callrail.com/v3/a/{account}/calls.json?fields=recording,...  (Authorization: Token token="<key>")
    //   recording URL is on the call object; download with the same token.
    // Normalize to {id, recordingUrl, source, phone, date, talk} and it flows through the same core.
    fetchCalls: function(client, key){ Logger.log('CallRail adapter not built yet for '+client.id); return []; },
    download: function(c, key){ return null; }
  }
};

// ======================= SHARED SERVICES =======================
function _deepgram(bytes, ctype, key){
  var url='https://api.deepgram.com/v1/listen?model=nova-3&diarize=true&punctuate=true&smart_format=true&utterances=true';
  var res=UrlFetchApp.fetch(url,{method:'post',contentType:ctype,payload:bytes,headers:{Authorization:'Token '+key},muteHttpExceptions:true});
  if(res.getResponseCode()!=200){ Logger.log('deepgram '+res.getResponseCode()); return null; }
  var j=JSON.parse(res.getContentText()); var u=(j.results&&j.results.utterances)||[];
  if(u.length) return u.map(function(x){return 'Speaker '+(x.speaker||0)+': '+(x.transcript||'');}).join('\n').trim();
  try{ return j.results.channels[0].alternatives[0].transcript||''; }catch(e){ return ''; }
}
// 2026-08-13: max_tokens raised 600 -> 1500. The 2026-08-13 prompt asks for three more
// keys (caller_town, objection, service_type) on top of a 1-2 sentence summary, and 600
// was truncating the JSON mid-string - which surfaced only as a silent "grade fail".
// Also retries once, because a truncated or empty body is usually transient.
var CLAUDE_MAX_TOKENS = 1500;

function _claude(transcript, meta, key){
  for(var attempt=1; attempt<=2; attempt++){
    var g = _claudeOnce(transcript, meta, key, attempt);
    if(g) return g;
    if(attempt==1){ Logger.log('  retrying grade...'); Utilities.sleep(1200); }
  }
  return null;
}
function _claudeOnce(transcript, meta, key, attempt){
  var payload=JSON.stringify({model:MODEL,max_tokens:CLAUDE_MAX_TOKENS,system:GRADE_PROMPT,
    messages:[{role:'user',content:'Metadata: '+JSON.stringify(meta)+'\n\nTranscript:\n'+transcript+'\n\nReturn ONLY the JSON.'}]});
  var res=UrlFetchApp.fetch('https://api.anthropic.com/v1/messages',{method:'post',contentType:'application/json',
    headers:{'x-api-key':key,'anthropic-version':'2023-06-01'},payload:payload,muteHttpExceptions:true});
  if(res.getResponseCode()!=200){ Logger.log('anthropic '+res.getResponseCode()+': '+res.getContentText().substring(0,150)); return null; }
  var j=JSON.parse(res.getContentText());
  var t=''; (j.content||[]).forEach(function(b){if(b.type=='text')t+=b.text;});
  t=t.trim(); if(t.indexOf('```')==0) t=t.replace(/```(json)?/g,'');
  // stop_reason 'max_tokens' means the JSON is cut off - say so instead of guessing.
  if(j.stop_reason=='max_tokens') Logger.log('  TRUNCATED at max_tokens ('+CLAUDE_MAX_TOKENS+') - raise CLAUDE_MAX_TOKENS.');
  var open=t.indexOf('{'), close=t.lastIndexOf('}');
  if(open<0 || close<open){ Logger.log('  attempt '+attempt+': no JSON object in reply ('+(t?t.substring(0,80):'EMPTY BODY')+')'); return null; }
  try{ return JSON.parse(t.substring(open,close+1)); }
  catch(e){ Logger.log('  attempt '+attempt+' parse fail: '+t.substring(0,200)); return null; }
}
// Canonical `Call Grades` header row. A..K (indexes 0..10) are the ORIGINAL columns and
// must never be reordered - other sheets/formulas address them by position. L..P are the
// 2026-08-12 additions and are only ever appended.
var GRADE_HEADERS = ['call_id','date','source','phone','lead_type','quality','insurance','summary','next_step','leads_row','graded_at',
                     'booked','job_market','acx_status_at_grade','in_crm_at_grade','dispute_eligible'];
var GRADE_ORIG_COLS = 11;   // A..K existed before 2026-08-12

// 2026-08-13. Q..AC (17..29) are LIVE CALC COLUMNS owned by the sheet - calc-phone10,
// calc-channel, calc-zip, ... bucket. They must never be written by this script. The new
// grader fields therefore start at AD, past the end of the calc block.
var EXT_START_COL = 30;                                        // AD
var EXT_HEADERS = ['missed_lead','objection','geo_source','service_type','dupe_of'];  // AD..AH
// AH (dupe_of) is deliberately its OWN column. It used to share AF (geo_source), and that
// collision was a live trap: the geo backfill and the re-grade both SELECT on AF, and treat
// a non-empty AF as "already handled". Stamping 'superseded-by-row-N' there made every
// duplicate row permanently invisible to both, with nothing logged. Order-of-operations is
// not a fix for that - separate columns are.

function _ensureGradeTab(ss, name){
  var s=ss.getSheetByName(name);
  if(!s){ s=ss.insertSheet(name); s.appendRow(GRADE_HEADERS.slice()); }
  _ensureGradeCols(s);
  return s;
}
// Make the sheet safe to appendRow() GRADE_HEADERS.length values into, on a tab that
// predates the new columns. Widens the grid if needed and fills ONLY the L..P header
// cells. Never writes to columns 1..11, so no existing column can shift or be clobbered.
function _ensureGradeCols(s){
  try{
    var need = GRADE_HEADERS.length;
    var maxc = s.getMaxColumns();
    if(maxc < need) s.insertColumnsAfter(maxc, need - maxc);
    if(s.getLastRow() < 1){ s.getRange(1,1,1,need).setValues([GRADE_HEADERS.slice()]); }
    else {
      var hdr = s.getRange(1,1,1,need).getValues()[0], missing = false;
      for(var i=GRADE_ORIG_COLS;i<need;i++) if(!hdr[i]) missing = true;
      if(missing){
        var add = GRADE_HEADERS.slice(GRADE_ORIG_COLS);
        s.getRange(1, GRADE_ORIG_COLS+1, 1, add.length).setValues([add]);
        Logger.log('Call Grades: added columns '+add.join(', '));
      }
    }
    // AD..AF. Widen past the calc block if needed and label them, without ever
    // reading or writing Q..AC.
    var endc = EXT_START_COL + EXT_HEADERS.length - 1;
    if(s.getMaxColumns() < endc) s.insertColumnsAfter(s.getMaxColumns(), endc - s.getMaxColumns());
    var eh = s.getRange(1, EXT_START_COL, 1, EXT_HEADERS.length).getValues()[0];
    if(!eh[0] || !eh[1] || !eh[2] || !eh[3] || !eh[4]){
      s.getRange(1, EXT_START_COL, 1, EXT_HEADERS.length).setValues([EXT_HEADERS.slice()]);
      Logger.log('Call Grades: added columns '+EXT_HEADERS.join(', ')+' at AD..AF');
    }
  }catch(e){ Logger.log('_ensureGradeCols skipped: '+e); }   // never block grading
}
// STALE (2026-08-13): Google removed LSA lead DISPUTES earlier this year - you can only RATE
// leads now. Kept only so column P does not shift. Read it as "junk LSA lead, rate it down",
// never as "file a dispute", and do not put dispute language in front of a client.
function _disputeEligible(source, leadType){
  if((''+(source||'')).toLowerCase().indexOf('lsa') < 0) return false;
  return leadType=='spam_robocall' || leadType=='wrong_number' || leadType=='out_of_scope' ||
         leadType=='solicitation_vendor' || leadType=='job_seeker';
}
function _truthy(v){ return (''+v).toLowerCase()=='true'; }
// Returns a set keyed BOTH by call_id and by 'pd:<phone>|<date>' (cols D and B), so the
// caller can reject a re-grade of the same conversation arriving under a new call_id.
function _gradedIds(sheet){
  var set={},last=sheet.getLastRow(); if(last<2) return set;
  var v=sheet.getRange(2,1,last-1,4).getValues();
  for(var i=0;i<v.length;i++){
    set[String(v[i][0])]=true;
    var ph=_norm(v[i][3]), dt=(''+(v[i][1]||'')).substring(0,10);
    if(v[i][1] instanceof Date) dt=Utilities.formatDate(v[i][1],'UTC','yyyy-MM-dd');
    if(ph) set['pd:'+ph+'|'+dt]=true;
  }
  return set;
}
function _norm(p){ var d=(''+(p||'')).replace(/\D/g,''); if(d.length==11&&d.charAt(0)=='1') d=d.substring(1); return d.length==10?d:''; }
function _stampLead(ss, client, phone, date, g, callId){
  var out={row:null,next_step:'',al:'',inacx:''}; if(!phone) return out;
  var sh=ss.getSheetByName(client.leadsTab); var last=sh.getLastRow(); if(last<2) return out;
  var rng=sh.getRange(2,1,last-1,32).getValues();  // A..AF (phone_norm=AF=index31, date=B=index1)
  for(var i=rng.length-1;i>=0;i--){
    var pn=_norm(rng[i][31]||rng[i][8]); if(pn!=phone) continue;
    var rd=(''+(rng[i][1]||'')).substring(0,10); if(date&&rd&&rd!=date) continue;
    if(sh.getRange(i+2, client.cols.callid).getValue()) continue;   // already graded row
    var row=i+2, alStatus=String(sh.getRange(row,28).getValue()||''), inAcx=String(sh.getRange(row,29).getValue()||'');
    var ns=_nextStep(g.lead_type,g.booked,alStatus,inAcx,g.job_market||'',_scopeStep(g));
    sh.getRange(row, client.cols.grade, 1, 6).setValues([[g.lead_type,g.quality_grade||'',(g.summary||'').substring(0,120),g.insurance_claim?'Y':'',ns,callId]]);
    return {row:row, next_step:ns, al:alStatus, inacx:inAcx};
  }
  return out;
}
function _nextStep(lt,booked,al,inacx,market,scopeStep){
  // Scope beats everything except a job already won or in the CRM: there is no point
  // routing someone to a callback for work the company does not take.
  if(lt=='real_lead' && scopeStep){
    var st0=(al||'').toLowerCase();
    if(st0!='closed'&&st0!='won'&&st0!='completed'&&(''+inacx).toUpperCase()!='Y') return scopeStep;
  }
  if(lt=='real_lead'){ var s=(al||'').toLowerCase();
    if(s=='closed'||s=='won'||s=='completed') return 'Won - no action';
    if(s=='cancelled') return 'RE-ENGAGE - was lost';
    if((''+inacx).toUpperCase()=='Y') return 'Follow up to close';
    // A booked appt we can't find in AccuLynx is an internal handoff gap, NOT an out-of-area
    // write-off. Check booked BEFORE out_of_area so these surface instead of being ignored.
    if((''+booked).toLowerCase()=='true') return 'BOOKED - not in AccuLynx, confirm';
    if((''+market).toLowerCase().indexOf('out_of_area')>=0) return 'No action - out of area';
    return 'CALL BACK - not in CRM'; }
  if(lt=='existing_customer') return 'Route to service';
  if(lt=='spam_robocall'||lt=='wrong_number'||lt=='out_of_scope') return 'Junk';
  if(lt=='not_reached') return 'Missed connect';
  return '';
}


// ===================================================================================
// 2026-08-13 ONE-TIME BACKFILL  (safe to delete once it has been run to completion)
// ===================================================================================
// The geography fix above only affects NEW calls. These two functions repair the rows
// already in `Call Grades`.
//
//   rfGrade_backfillDryRun()   read-only. Prints what WOULD change. Run this first.
//   rfGrade_backfillGeo()      re-grades the bad rows for real, 12 at a time.
//   rfGrade_flagDupes()        marks duplicate phone+date rows (writes col AF only).
//
// Why re-grade instead of patch: the old rows never stored caller_town or objection, so
// there is nothing to apply the new rule TO. The transcript is the only ground truth, so
// each flagged call is re-transcribed and re-graded with the corrected prompt.
//
// Scope: ONLY rows where job_market (col M) reads 'out_of_area'. Every other row is left
// exactly as it is. Apps Script caps at ~6 minutes, so this does 12 rows per run and
// records progress in col AF (geo_source) - a row with AF filled in is done. Note AF is not
// shared with anything else; the duplicate flag lives in AH. Just run it
// again until the log says 0 remaining.

var BACKFILL_PER_RUN = 12;

function rfGrade_backfillDryRun(){ _backfill(true); }
function rfGrade_backfillGeo(){ _backfill(false); }

function _backfill(dry){
  var client = CLIENTS[0];
  var props = PropertiesService.getScriptProperties();
  var dg = props.getProperty('DEEPGRAM_API_KEY'), an = props.getProperty('ANTHROPIC_API_KEY');
  var provKey = props.getProperty(client.keyProp);
  if(!dg || !an || !provKey){ Logger.log('missing a key.'); return; }

  var sh = _ensureGradeTab(SpreadsheetApp.openById(client.sheetId), client.gradeTab);
  var last = sh.getLastRow(); if(last<2){ Logger.log('nothing to do'); return; }
  var vals = sh.getRange(2,1,last-1,GRADE_HEADERS.length).getValues();
  var ext  = sh.getRange(2,EXT_START_COL,last-1,4).getValues();

  var todo = [];
  for(var i=0;i<vals.length;i++){
    var jm = (''+(vals[i][12]||'')).toLowerCase();      // M job_market
    var done = (''+(ext[i][2]||'')).trim();             // AF geo_source
    if(jm=='out_of_area' && !done) todo.push({row:i+2, id:vals[i][0], phone:vals[i][3]});
  }
  Logger.log('backfill: '+todo.length+' row(s) still to repair.');
  if(!todo.length) return;

  var n = Math.min(todo.length, BACKFILL_PER_RUN), changed = 0;
  for(var k=0;k<n;k++){
    var t = todo[k];
    var call = _ctmGetCall(client, provKey, t.id);
    if(!call || !call.audio){ Logger.log('row '+t.row+' call '+t.id+': no recording, skipped'); continue; }
    var audio = ADAPTERS.ctm.download({recordingUrl:call.audio}, provKey);
    if(!audio){ Logger.log('row '+t.row+': audio download failed'); continue; }
    var transcript = _deepgram(audio.bytes, audio.type, dg);
    if(!transcript){ Logger.log('row '+t.row+': transcribe failed'); continue; }
    var g = _claude(transcript, {source:call.source, phone:t.phone, date:(call.called_at||'').substring(0,10)}, an);
    if(!g || !g.lead_type){ Logger.log('row '+t.row+': grade failed'); continue; }
    var geoSrc = _resolveGeo(g);

    Logger.log('row '+t.row+' '+t.phone+': out_of_area -> '+(g.job_market||'(blank)')+
               '  [town='+(g.caller_town||'-')+' objection='+(g.objection||'-')+' missed_lead='+g.missed_lead+']  '+geoSrc);
    if(dry) continue;

    // Rewrite only the graded fields. call_id/date/source/phone (A-D), leads_row (J),
    // graded_at (K) and the grade-time snapshots (N/O) are left alone.
    sh.getRange(t.row, 5, 1, 4).setValues([[g.lead_type, g.quality_grade||'', g.insurance_claim?'Y':'', (g.summary||'').substring(0,120)]]);
    sh.getRange(t.row,12).setValue(_truthy(g.booked));
    sh.getRange(t.row,13).setValue(g.job_market||'');
    sh.getRange(t.row,16).setValue(_disputeEligible(call.source, g.lead_type));
    sh.getRange(t.row,EXT_START_COL,1,4).setValues([[_truthy(g.missed_lead), g.objection||'', geoSrc, g.service_type||'']]);
    changed++;
  }
  Logger.log((dry?'DRY RUN - nothing written. ':'wrote '+changed+' row(s). ')+
             (todo.length-n)+' row(s) remain - run again.');
}

// CTM single-call lookup. The normal fetchCalls() only reaches back LOOKBACK_HOURS, which
// is no use for a July backfill, so pull the call object by id.
function _ctmGetCall(client, auth, id){
  var url = 'https://api.calltrackingmetrics.com/api/v1/accounts/'+client.account+'/calls/'+id+'.json';
  var res = UrlFetchApp.fetch(url, {headers:{Authorization:'Basic '+auth}, muteHttpExceptions:true});
  if(res.getResponseCode()!=200){ Logger.log('CTM call '+id+': '+res.getResponseCode()); return null; }
  try{ var j=JSON.parse(res.getContentText()); return j.call||j; }catch(e){ return null; }
}

// 56 rows share phone+date with another row and the verdicts disagree. This does NOT delete
// anything - it stamps col AH (dupe_of) so the newest grade per phone+date wins and the older
// ones can be filtered out downstream. AH, not AF: see the EXT_HEADERS note above. Safe to
// run at any point now - it no longer interferes with the backfill or the re-grade.
function rfGrade_flagDupes(){
  var client = CLIENTS[0];
  var sh = _ensureGradeTab(SpreadsheetApp.openById(client.sheetId), client.gradeTab);
  var last = sh.getLastRow(); if(last<2) return;
  var vals = sh.getRange(2,1,last-1,GRADE_HEADERS.length).getValues();
  var keep = {};   // phone|date -> row of the LAST (newest) occurrence
  for(var i=0;i<vals.length;i++){
    var ph=_norm(vals[i][3]); if(!ph) continue;
    var d=vals[i][1], dt = (d instanceof Date) ? Utilities.formatDate(d,'UTC','yyyy-MM-dd') : (''+(d||'')).substring(0,10);
    keep[ph+'|'+dt] = i;
  }
  var flagged=0;
  for(var j=0;j<vals.length;j++){
    var p=_norm(vals[j][3]); if(!p) continue;
    var dd=vals[j][1], ds = (dd instanceof Date) ? Utilities.formatDate(dd,'UTC','yyyy-MM-dd') : (''+(dd||'')).substring(0,10);
    if(keep[p+'|'+ds]!==j){ sh.getRange(j+2,EXT_START_COL+4).setValue('superseded-by-row-'+(keep[p+'|'+ds]+2)); flagged++; }
  }
  Logger.log('flagged '+flagged+' superseded duplicate row(s) in col AH (dupe_of).');
}
