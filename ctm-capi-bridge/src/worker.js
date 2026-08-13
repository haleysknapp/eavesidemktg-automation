/**
 * CTM -> Meta Conversions API bridge
 *
 * Why this exists: CallTrackingMetrics' built-in Facebook integration posts to the
 * Offline Conversions API, which Meta deprecated at v17. Every send returns
 * 400 (#21018). This worker replaces it with a direct Conversions API call.
 *
 * Flow:  CTM webhook -> this worker -> graph.facebook.com/<PIXEL_ID>/events
 *
 * Events are sent as:
 *   event_name    "Lead"
 *   action_source "phone_call"
 *   event_id      the CTM call id  (dedupes against retries AND against the
 *                 website Lead pixel event, so one human never counts twice)
 *
 * Everything identifying is SHA-256 hashed before it leaves this worker.
 * Raw phone numbers and names are never sent to Meta.
 */

const GRAPH_VERSION = "v21.0";

export default {
  async fetch(request, env, ctx) {
    // ---- auth -------------------------------------------------------------
    // CTM does not sign its webhooks, so the shared secret rides in the path:
    //   https://<worker>/hook/<WEBHOOK_SECRET>
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ ok: true, pixel: env.PIXEL_ID, version: GRAPH_VERSION });
    }

    if (request.method !== "POST") {
      return json({ error: "POST only" }, 405);
    }

    const expected = `/hook/${env.WEBHOOK_SECRET}`;
    if (url.pathname !== expected) {
      // Deliberately vague — don't confirm or deny the path shape.
      return json({ error: "not found" }, 404);
    }

    // ---- parse ------------------------------------------------------------
    let payload;
    try {
      const ct = request.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        payload = await request.json();
      } else {
        // CTM can be configured to send form-encoded
        const form = await request.formData();
        payload = Object.fromEntries(form.entries());
      }
    } catch (err) {
      return json({ error: "unparseable body", detail: String(err) }, 400);
    }

    // DEBUG=1 echoes the payload back instead of forwarding. Use this on the
    // very first CTM test so we can see the real field names before going live.
    if (env.DEBUG === "1") {
      return json({ debug: true, received: payload }, 200);
    }

    // ---- normalize --------------------------------------------------------
    const call = normalizeCall(payload);

    // ---- eligibility ------------------------------------------------------
    const decision = shouldSend(call, env);
    if (!decision.send) {
      // 200, not an error: CTM should not retry a call we deliberately skipped.
      return json({ skipped: true, reason: decision.reason, call_id: call.id });
    }

    // ---- build + send -----------------------------------------------------
    const event = await buildEvent(call, env);

    const body = { data: [event] };
    if (env.TEST_EVENT_CODE) body.test_event_code = env.TEST_EVENT_CODE;

    const endpoint =
      `https://graph.facebook.com/${GRAPH_VERSION}/${env.PIXEL_ID}/events` +
      `?access_token=${encodeURIComponent(env.META_ACCESS_TOKEN)}`;

    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });

    const metaBody = await res.text();

    if (!res.ok) {
      // Surface the failure to CTM so it shows in their API log, and to us.
      console.error("CAPI reject", res.status, metaBody, "call", call.id);
      return json(
        { sent: false, status: res.status, meta: safeParse(metaBody), call_id: call.id },
        502
      );
    }

    console.log("CAPI ok", call.id, metaBody);
    return json({ sent: true, call_id: call.id, meta: safeParse(metaBody) });
  },
};

/* ------------------------------------------------------------------------ */
/* normalization                                                             */
/* ------------------------------------------------------------------------ */

/**
 * Field names confirmed against a real Roofing Force webhook payload
 * (84 fields, "Log Data" body type, captured 2026-08-10). Candidate lists are
 * kept so the same worker survives a CTM schema change or a different account.
 */
function normalizeCall(p) {
  const pick = (...keys) => {
    for (const k of keys) {
      const v = p[k];
      if (v !== undefined && v !== null && String(v).trim() !== "") return v;
    }
    return "";
  };

  const rawCaller = pick(
    "caller_number_e164", "caller_number", "caller_id", "from_number", "from"
  );
  const rawDialed = pick(
    "tracking_number_e164", "tracking_number", "called_number", "to_number", "to"
  );

  // CTM sends either one "name" or separate first/last.
  let first = pick("caller_first_name", "first_name", "fname");
  let last = pick("caller_last_name", "last_name", "lname");
  if (!first && !last) {
    const whole = String(pick("caller_name", "name", "contact_name")).trim();
    if (whole) {
      const bits = whole.split(/\s+/);
      first = bits.shift() || "";
      last = bits.join(" ");
    }
  }

  // talk_time is conversation seconds; duration includes ring time. Talk is the
  // honest measure of whether anyone actually spoke.
  const durationRaw = pick("talk_time", "duration", "call_duration", "billed_duration");

  // CTM nests the paid-traffic attribution: paid: {source: "facebook", ...}
  const paid = p.paid && typeof p.paid === "object" ? p.paid : {};

  // No conversion/lead boolean exists in CTM's payload — the human signal is a
  // tag applied to the call in their UI.
  const tags = Array.isArray(p.tag_list) ? p.tag_list.map((t) => String(t).toLowerCase()) : [];

  return {
    id: String(pick("id", "call_id", "callsid", "sid", "activity_id") || ""),
    phone: normalizePhone(rawCaller),
    dialed: normalizePhone(rawDialed),
    first,
    last,
    email: String(pick("email", "caller_email", "contact_email") || ""),
    city: pick("caller_city", "city"),
    state: pick("caller_state", "state", "region"),
    zip: pick("caller_zip", "zip", "zipcode", "postal_code"),
    country: pick("caller_country", "country") || "us",
    source: String(pick("source", "source_name", "referrer_source", "utm_source") || ""),
    webSource: String(pick("web_source") || ""),
    paidSource: String(paid.source || ""),
    campaign: String(pick("campaign", "campaign_name", "utm_campaign") || ""),
    duration: toInt(durationRaw),
    marked: tags.some((t) => /lead|convert|sold|appointment|booked|estimate/.test(t)),
    // CTM's own housekeeping flags.
    excluded: truthy(pick("excluded")),
    redacted: truthy(pick("redacted")),
    // Careful: "no-answer" contains "answer", so the negative cases are tested
    // first. A call with talk seconds on the clock was self-evidently answered.
    answered: (() => {
      const s = String(pick("call_status", "dial_status", "status") || "").toLowerCase();
      if (/no.?answer|busy|failed|cancel|declin|voicemail/.test(s)) return false;
      if (/answer|complet/.test(s)) return true;
      return toInt(durationRaw) > 0;
    })(),
    hasAudio: !!pick("audio", "recording", "recording_url"),
    ringTime: toInt(pick("ring_time")),
    totalDuration: toInt(pick("duration")),
    statusText: String(pick("call_status", "dial_status", "status") || "").toLowerCase(),
    // unix_time is a clean epoch. called_at is "2026-08-10 05:16 PM -05:00",
    // which Date.parse cannot read — hence the dedicated parser below.
    time: toEpochSeconds(pick("unix_time"), pick("called_at", "start_time", "date", "created_at")),
    value: toFloat(pick("value", "conversion_value", "sale_amount")),
  };
}

function normalizePhone(v) {
  const digits = String(v || "").replace(/\D/g, "");
  if (!digits) return "";
  if (digits.length === 10) return "1" + digits;      // bare US
  if (digits.length === 11 && digits[0] === "1") return digits;
  return digits;                                       // already international
}

function toInt(v) {
  const n = parseInt(String(v || "").replace(/[^\d-]/g, ""), 10);
  return Number.isFinite(n) ? n : 0;
}

function toFloat(v) {
  const n = parseFloat(String(v || "").replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

/**
 * Prefers CTM's unix_time. Falls back to called_at, which arrives as
 * "2026-08-10 05:16 PM -05:00" — a format Date.parse returns NaN for, so it
 * gets rewritten into something parseable before trying.
 */
function toEpochSeconds(epoch, textual) {
  const e = String(epoch || "");
  if (/^\d{10}$/.test(e)) return parseInt(e, 10);
  if (/^\d{13}$/.test(e)) return Math.floor(parseInt(e, 10) / 1000);

  const s = String(textual || "").trim();
  if (s) {
    // "2026-08-10 05:16 PM -05:00" -> "2026-08-10T17:16:00-05:00"
    const m = s.match(
      /^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?\s*([+-]\d{2}):?(\d{2})?$/i
    );
    if (m) {
      let [, y, mo, d, hh, mi, ss, ampm, tzh, tzm] = m;
      let h = parseInt(hh, 10);
      if (ampm) {
        const upper = ampm.toUpperCase();
        if (upper === "PM" && h !== 12) h += 12;
        if (upper === "AM" && h === 12) h = 0;
      }
      const iso =
        `${y}-${mo}-${d}T${String(h).padStart(2, "0")}:${mi}:${ss || "00"}` +
        `${tzh}:${tzm || "00"}`;
      const t = Date.parse(iso);
      if (Number.isFinite(t)) return Math.floor(t / 1000);
    }
    const t = Date.parse(s);
    if (Number.isFinite(t)) return Math.floor(t / 1000);
  }

  return Math.floor(Date.now() / 1000);
}

function truthy(v) {
  const s = String(v).toLowerCase().trim();
  return s === "true" || s === "1" || s === "yes" || s === "y";
}

/* ------------------------------------------------------------------------ */
/* eligibility                                                               */
/* ------------------------------------------------------------------------ */

/**
 * Two filters, both deliberate:
 *
 * 1. Attribution. Only calls that came in on a Facebook-attributed tracking
 *    number (or whose CTM source says Facebook) get sent. Feeding Meta every
 *    Google and organic call would let it claim credit for calls it never
 *    caused, which quietly wrecks the numbers you use to judge the channel.
 *
 * 2. Quality. Short calls are wrong numbers, hangups and robocalls. Sending
 *    them teaches Meta to find more people who hang up. If CTM has already
 *    flagged the call as a conversion we trust that and skip the duration test.
 */
function shouldSend(call, env) {
  if (!call.phone) return { send: false, reason: "no caller number" };
  if (!call.id) return { send: false, reason: "no call id (needed for dedupe)" };

  // CTM's own verdicts, respected before ours.
  if (call.excluded) return { send: false, reason: "excluded in CTM (spam)" };
  if (call.redacted) return { send: false, reason: "redacted in CTM" };

  // A voicemail is a lead. Someone who sits through the beep and describes
  // their roof is a prospect, even though nobody picked up. Length is the
  // filter: a two-second message is a hangup, not an enquiry.
  const vmMin = toInt(env.VOICEMAIL_MIN_SEC || "10");
  const vmLength = Math.max(call.totalDuration - call.ringTime, 0);
  const looksLikeVoicemail =
    !call.answered &&
    env.COUNT_VOICEMAIL !== "0" &&
    (call.hasAudio || /voicemail|message/.test(call.statusText)) &&
    vmLength > 0;

  if (!call.answered) {
    if (!looksLikeVoicemail) return { send: false, reason: "not answered, no message left" };
    if (vmLength < vmMin) {
      return { send: false, reason: `voicemail too short (${vmLength}s < ${vmMin}s)` };
    }
  }

  const fbNumbers = (env.FB_NUMBERS || "")
    .split(",")
    .map((s) => normalizePhone(s))
    .filter(Boolean);

  const rx = new RegExp(env.FB_SOURCE_REGEX || "facebook|meta|fb", "i");
  // Three independent signals; any one is enough. source is the CTM source
  // name ("Facebook Ads Website"), web_source the channel ("facebook"), and
  // paid.source CTM's own paid-traffic attribution.
  const sourceMatches =
    rx.test(call.source) || rx.test(call.webSource) || rx.test(call.paidSource);
  const numberMatches = fbNumbers.length > 0 && fbNumbers.includes(call.dialed);

  if (!numberMatches && !sourceMatches) {
    return {
      send: false,
      reason: `not facebook-attributed (dialed ${call.dialed || "?"}, source "${call.source || "?"}")`,
    };
  }

  if (call.marked) return { send: true, reason: "flagged as conversion in CTM" };

  // Voicemails cleared their own length check above; the talk-time floor below
  // is about conversations and would reject every message ever left.
  if (!call.answered) return { send: true, reason: `voicemail (${vmLength}s message)` };

  // The tracking number forwards to the client's own line, so their voicemail
  // sits downstream and CTM reports "answered" either way — a human picking up
  // and an answering machine picking up are identical in the payload. The only
  // signal left is when the call happened.
  //
  // In hours: every second is conversation, so a short call can still be real.
  // Out of hours: the first ~27s is the outgoing greeting, so the bar is higher.
  const open = isDuringBusinessHours(call.time, env);
  const min = open
    ? toInt(env.MIN_DURATION_SEC_OPEN || "20")
    : toInt(env.MIN_DURATION_SEC_CLOSED || "40");

  if (call.duration < min) {
    return {
      send: false,
      reason: `too short (${call.duration}s < ${min}s, ${open ? "in hours" : "after hours"})`,
    };
  }

  return {
    send: true,
    reason: `qualified call (${call.duration}s, ${open ? "in hours" : "after hours"})`,
  };
}

const DAY_INDEX = { sun: 0, mon: 1, tue: 2, wed: 3, thu: 4, fri: 5, sat: 6 };

/**
 * True if the call started inside the client's staffed hours, evaluated in
 * their local timezone. Uses Intl rather than a fixed UTC offset so this keeps
 * working across daylight saving instead of silently drifting an hour in March
 * and November.
 */
function isDuringBusinessHours(epochSeconds, env) {
  const tz = env.BUSINESS_TZ || "America/Chicago";
  const days = String(env.BUSINESS_DAYS || "1,2,3,4,5")
    .split(",")
    .map((d) => parseInt(d.trim(), 10))
    .filter((d) => Number.isFinite(d));
  const start = toInt(env.BUSINESS_START_HOUR || "8");
  const end = toInt(env.BUSINESS_END_HOUR || "17");

  let weekday;
  let hour;
  try {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      weekday: "short",
      hour: "numeric",
      hourCycle: "h23",
    }).formatToParts(new Date(epochSeconds * 1000));
    weekday = parts.find((p) => p.type === "weekday")?.value;
    hour = parseInt(parts.find((p) => p.type === "hour")?.value, 10);
  } catch {
    // Bad timezone string: fall back to treating it as out of hours, which is
    // the stricter of the two thresholds.
    return false;
  }

  const dayNum = DAY_INDEX[String(weekday || "").slice(0, 3).toLowerCase()];
  if (dayNum === undefined || !Number.isFinite(hour)) return false;
  if (!days.includes(dayNum)) return false;

  return hour >= start && hour < end;
}

/* ------------------------------------------------------------------------ */
/* event construction                                                        */
/* ------------------------------------------------------------------------ */

async function buildEvent(call, env) {
  const user_data = {};

  const add = async (key, value, normalizer) => {
    const v = normalizer ? normalizer(value) : String(value || "").trim().toLowerCase();
    if (v) user_data[key] = [await sha256(v)];
  };

  // Phone is the identifier that actually matches a caller to a Meta user.
  await add("ph", call.phone, (v) => String(v || ""));
  // Email, when CTM has one, lifts match quality more than any other field.
  await add("em", call.email, (v) => String(v || "").trim().toLowerCase());
  await add("fn", call.first, cleanName);
  await add("ln", call.last, cleanName);
  await add("ct", call.city, (v) => String(v || "").toLowerCase().replace(/[^a-z]/g, ""));
  await add("st", call.state, normalizeState);
  await add("zp", call.zip, (v) => String(v || "").replace(/\D/g, "").slice(0, 5));
  await add("country", call.country, (v) => String(v || "us").toLowerCase().slice(0, 2));

  const event = {
    event_name: "Lead",
    event_time: call.time,
    event_id: `ctm-${call.id}`,   // dedupe key
    action_source: "phone_call",
    user_data,
    custom_data: {
      lead_event_source: "CallTrackingMetrics",
      lead_source: call.source || "facebook",
      call_duration: call.duration,
      call_status: call.answered ? "answered" : "voicemail",
      currency: "USD",
    },
  };

  if (call.value > 0) event.custom_data.value = call.value;
  if (call.campaign) event.custom_data.campaign = call.campaign;

  return event;
}

function cleanName(v) {
  return String(v || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")   // strip accents
    .replace(/[^a-z]/g, "");
}

const STATES = {
  kansas: "ks", missouri: "mo", nebraska: "ne", oklahoma: "ok", iowa: "ia",
  arkansas: "ar", colorado: "co", texas: "tx", illinois: "il",
};

function normalizeState(v) {
  const s = String(v || "").toLowerCase().replace(/[^a-z]/g, "");
  if (s.length === 2) return s;
  return STATES[s] || s.slice(0, 2);
}

/* ------------------------------------------------------------------------ */
/* helpers                                                                   */
/* ------------------------------------------------------------------------ */

async function sha256(text) {
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(String(text))
  );
  return [...new Uint8Array(buf)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function safeParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
