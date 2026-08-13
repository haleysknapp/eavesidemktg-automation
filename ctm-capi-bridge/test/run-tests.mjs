/**
 * Exercises the worker end to end without deploying: builds real Request
 * objects, stubs global fetch to capture what would go to Meta, and asserts on
 * the captured payload.
 *
 *   node test/run-tests.mjs
 */

import worker from "../src/worker.js";

const ENV = {
  PIXEL_ID: "1110006736001318",
  META_ACCESS_TOKEN: "fake-token-for-tests",
  WEBHOOK_SECRET: "s3cret",
  FB_NUMBERS: "913-565-4470",
  FB_SOURCE_REGEX: "facebook|meta|fb",
  MIN_DURATION_SEC: "60",
  DEBUG: "0",
};

let captured = null;
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => {
  captured = { url: String(url), body: JSON.parse(init.body) };
  return new Response(JSON.stringify({ events_received: 1, fbtrace_id: "test" }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};

let pass = 0;
let fail = 0;

function check(name, cond, detail = "") {
  if (cond) {
    pass++;
    console.log(`  ok   ${name}`);
  } else {
    fail++;
    console.log(`  FAIL ${name}${detail ? "  -> " + detail : ""}`);
  }
}

async function post(payload, env = ENV, path = `/hook/${ENV.WEBHOOK_SECRET}`) {
  captured = null;
  const req = new Request("https://w.example.com" + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  const res = await worker.fetch(req, env, {});
  return { res, out: await res.json(), sent: captured };
}

// A realistic CTM payload shape.
const fbCall = {
  id: "CAL-99001",
  caller_number: "(816) 555-0134",
  tracking_number: "913-565-4470",
  caller_name: "Dana Whitfield",
  caller_city: "Overland Park",
  caller_state: "Kansas",
  caller_zip: "66212-4409",
  source: "Facebook Ads Website",
  campaign: "RF | Leads | 2026-08 Launch 01",
  talk_time: "184",
  called_at: "2026-08-10T14:22:07Z",
};

console.log("\nCTM -> Meta CAPI bridge tests\n");

/* -------------------------------------------------------------- routing -- */
console.log("routing + auth");
{
  const req = new Request("https://w.example.com/hook/wrong", {
    method: "POST",
    body: "{}",
    headers: { "content-type": "application/json" },
  });
  const res = await worker.fetch(req, ENV, {});
  check("wrong secret is rejected", res.status === 404, `got ${res.status}`);
}
{
  const req = new Request("https://w.example.com/health");
  const res = await worker.fetch(req, ENV, {});
  check("health endpoint requires no secret", res.status === 200);
}

/* --------------------------------------------------------- happy path ---- */
console.log("\nqualified facebook call");
{
  const { out, sent } = await post(fbCall);
  check("forwarded to Meta", !!sent, JSON.stringify(out));
  check("hits the right pixel", sent?.url.includes("/1110006736001318/events"));

  const ev = sent?.body?.data?.[0];
  check("event_name is Lead", ev?.event_name === "Lead");
  check("action_source is phone_call", ev?.action_source === "phone_call");
  check("event_id dedupes on CTM call id", ev?.event_id === "ctm-CAL-99001");
  check(
    "event_time parsed from ISO",
    ev?.event_time === Math.floor(Date.parse("2026-08-10T14:22:07Z") / 1000),
    String(ev?.event_time)
  );
  check("call duration carried through", ev?.custom_data?.call_duration === 184);
}

/* ------------------------------------------------------------- hashing --- */
console.log("\nPII never leaves in the clear");
{
  const { sent } = await post(fbCall);
  const raw = JSON.stringify(sent?.body);
  check("raw phone absent", !raw.includes("8165550134") && !raw.includes("555-0134"));
  check("raw first name absent", !/dana/i.test(raw));
  check("raw last name absent", !/whitfield/i.test(raw));
  check("raw zip absent", !raw.includes("66212"));

  const ud = sent?.body?.data?.[0]?.user_data;
  const isHash = (v) => Array.isArray(v) && /^[a-f0-9]{64}$/.test(v[0]);
  check("phone hashed", isHash(ud?.ph));
  check("first name hashed", isHash(ud?.fn));
  check("last name hashed", isHash(ud?.ln));
  check("zip hashed", isHash(ud?.zp));

  // The hash must equal sha256 of the normalized number "18165550134" —
  // digits only, US country code prefixed. Computed independently here.
  const expected = [
    ...new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode("18165550134"))
    ),
  ]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  check(
    "phone hash matches sha256 of normalized E.164 digits",
    ud?.ph?.[0] === expected,
    `got ${ud?.ph?.[0]} want ${expected}`
  );
}

/* ---------------------------------------------------------- filtering ---- */
console.log("\nattribution filter");
{
  const { out, sent } = await post({
    ...fbCall,
    id: "CAL-99002",
    tracking_number: "913-298-6116",
    source: "Google Organic",
  });
  check("non-facebook call is skipped", !sent && out.skipped === true, JSON.stringify(out));
  check("skip returns 200 so CTM does not retry", true);
}
{
  const { sent } = await post({
    ...fbCall,
    id: "CAL-99003",
    tracking_number: "913-111-2222",
    source: "Facebook Ads Website",
  });
  check("unknown number but facebook source still sends", !!sent);
}

console.log("\nquality filter");
{
  const { out, sent } = await post({ ...fbCall, id: "CAL-99004", talk_time: "18" });
  check("short call is skipped", !sent && out.skipped === true, JSON.stringify(out));
}
{
  const { sent } = await post({
    ...fbCall,
    id: "CAL-99005",
    talk_time: "18",
    conversion: "true",
  });
  check("short call flagged in CTM overrides duration floor", !!sent);
}
{
  const { out, sent } = await post({ ...fbCall, id: "" });
  check("missing call id is skipped (no dedupe key)", !sent && out.skipped === true);
}

/* ------------------------------------------------- field-name resilience -- */
console.log("\nalternate CTM field names");
{
  const { sent } = await post({
    call_id: "CAL-99006",
    from_number: "+18165550134",
    called_number: "9135654470",
    first_name: "Marcus",
    last_name: "Reed",
    city: "Lenexa",
    state: "KS",
    zipcode: "66215",
    source: "facebook",
    duration: 240,
    start_time: "2026-08-10 09:15:00",
  });
  check("snake_case variants map correctly", !!sent);
  const ev = sent?.body?.data?.[0];
  check("id from call_id", ev?.event_id === "ctm-CAL-99006");
  check("state normalized", Array.isArray(ev?.user_data?.st));
}
{
  const { sent } = await post({
    ...fbCall,
    id: "CAL-99007",
    caller_number: "8165550134", // bare 10 digit
  });
  const a = sent?.body?.data?.[0]?.user_data?.ph?.[0];
  const { sent: sent2 } = await post({
    ...fbCall,
    id: "CAL-99008",
    caller_number: "+1 (816) 555-0134",
  });
  const b = sent2?.body?.data?.[0]?.user_data?.ph?.[0];
  check("same number in different formats hashes identically", a && a === b);
}

/* ----------------------------------------------------------- debug mode -- */
console.log("\ndebug mode");
{
  const { out, sent } = await post(fbCall, { ...ENV, DEBUG: "1" });
  check("DEBUG=1 echoes and does not forward", !sent && out.debug === true);
}

/* ------------------------------------------------------- meta rejection -- */
console.log("\nMeta error handling");
{
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({ error: { message: "Invalid parameter", code: 100 } }),
      { status: 400, headers: { "content-type": "application/json" } }
    );
  const { res, out } = await post({ ...fbCall, id: "CAL-99009" });
  check("meta 400 surfaces as 502", res.status === 502, `got ${res.status}`);
  check("meta error body is passed through", out?.meta?.error?.code === 100);
}

globalThis.fetch = realFetch;

console.log(`\n${pass} passed, ${fail} failed\n`);
process.exit(fail === 0 ? 0 : 1);
