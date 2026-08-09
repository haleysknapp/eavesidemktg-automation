"""Search-term classification + verdict logic (shared by weekly analyzer + daily)."""
import os, re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---- thresholds (tune here) ----
TARGET_CPL = 180.0
CUT_RELEVANT_SPEND = 90.0    # 0-conv relevant term: cut at half a lead's value...
CUT_RELEVANT_CLICKS = 6      # ...with real click evidence (SOP: never mass-negate thin 5-click terms)
CUT_COMPETITOR_SPEND = 50.0  # competitor/brand names: SOP threshold ~$50-75 / 0 conv
CUT_COMPETITOR_WEEKS = 2     # shown for context
WATCH_SPEND = 30.0           # 0-conv, on the radar
REVIEW_CPL_MULT = 2.0        # converting but CPL > 2x target -> review

JUNK_PATTERNS = [
    (r"\b(jobs?|hiring|careers?|salary|salaries|apprentice(ship)?|employment|resume)\b", "job seeker"),
    (r"\b(training|certification|certified course|classes?|school|course|license requirements?)\b", "training/edu"),
    (r"\b(diy|do it yourself|yourself|how to (install|replace|repair|fix|shingle))\b", "DIY"),
    (r"\b(kit|kits|supply|supplies|supplier|wholesale|distributor|for sale|prices? per (square|bundle|sheet)|home depot|lowe'?s|menards)\b", "materials/retail"),
    (r"\b(calculator|software|template|invoice|app)\b", "tools/software"),
    (r"\b(rental|rent a|used|craigslist|facebook marketplace)\b", "marketplace"),
    (r"\b(what is|definition|meaning|wiki|history of)\b", "informational"),
    (r"\b(insurance adjuster (job|training|salary)|become an? adjuster)\b", "adjuster career"),
]
SAFE_OVERRIDES = r"\b(estimate|quote|inspection|contractor|company|companies|near me|repair service|replace my|my roof|leak)\b"

OWN_BRAND = ["roofing force", "roofingforce", "eaveside"]

def _load_list(fname):
    path = os.path.join(BASE_DIR, fname)
    pats = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip().lower()
            if line and not line.startswith("#"):
                pats.append(line)
    return pats

def load_competitors(): return _load_list("competitors.txt")
def load_brands():      return _load_list("brands.txt")

# ---- core-term protection ----
CORE_STEM = re.compile(r"\broof\w*\b")
CORE_INTENT = re.compile(r"(compan|compañ|contractor|repair|replac|install|estimate|quote|inspect|service|near me)")
CORE_BARE = re.compile(r"^(metal |flat |tile |shingle |commercial |residential )?roof(ing|ers?)?$")
SPANISH = re.compile(r"(compañ|techo|tejado|reparaci|gotera|para el|mi casa)")
GUTTER = re.compile(r"\bgutter")
GEO = re.compile(r"\b(kansas city|kc|joplin|st\.? louis|saint louis|stl|fort smith|mena|wichita|olathe|overland park|lenexa|van buren|greenwood|springfield|arkansas|missouri|oklahoma|kansas)\b")

# company-name shape: has a company suffix word + at least one non-generic token
COMPANY_SUFFIX = re.compile(r"\b(roofing|construction|restoration|exteriors?|contracting)\b")
GENERIC_TOKENS = set("""roof roofs roofing roofer roofers metal flat tile shingle shingles commercial residential
local best top rated quality reliable trusted affordable cheap new free companies company contractor contractors
construction restoration exteriors exterior contracting reviews review compañías compañia compania de en el la los las para mejores cerca mi
repair repairs replacement replace installation install installers installer estimate estimates quote quotes
inspection inspections cost costs price prices near me in and & the a of for with my your that services service
systems system solutions llc inc co gutter gutters siding storm damage insurance hail leak leaking emergency
kansas city kc joplin st saint louis stl fort smith mena wichita olathe overland park lenexa van buren greenwood
springfield arkansas missouri oklahoma mo ks ar ok mulvane derby haysville independence liberty carthage neosho
pittsburg rogers fayetteville bentonville lawrence hutchinson salina topeka wellington newton mcpherson emporia
shawnee gardner ottawa paola gladstone raytown grandview belton raymore nixa ozark republic bolivar monett
aurora cassville springdale siloam alma sallisaw poteau spiro sapulpa claremore owasso""".split())

def _looks_like_company(t):
    if not COMPANY_SUFFIX.search(t):
        return False
    if t.endswith("roofing systems") or t.endswith("roofing and construction") or t.endswith("roofing & construction"):
        return True
    toks = re.findall(r"[a-zà-ÿ&']+", t)
    return any(tok not in GENERIC_TOKENS for tok in toks)

def classify(term, competitors, brands=None):
    """Returns (category, detail): brand / competitor / junk / maybe_company / relevant."""
    t = term.lower()
    for pat in OWN_BRAND:
        if pat in t:
            return "own_brand", pat
    for pat in (brands or []):
        if pat in t:
            return "brand", pat
    for pat in competitors:
        if pat in t:
            return "competitor", pat
    for pat, reason in JUNK_PATTERNS:
        if re.search(pat, t):
            if re.search(SAFE_OVERRIDES, t) and reason in ("informational",):
                continue
            return "junk", reason
    if _looks_like_company(t):
        return "maybe_company", None
    return "relevant", None

def verdict(cat, cost, conv, weeks_active, term="", clicks=0):
    """CUT / VERIFY / WATCH / REVIEW / OK with a plain-English reason."""
    if cat == "own_brand":
        return "OK", ""
    if conv > 0:
        cpl = cost / conv
        if cpl > REVIEW_CPL_MULT * TARGET_CPL and cost >= TARGET_CPL:
            return "REVIEW", f"converts but CPL ${cpl:,.0f} vs ${TARGET_CPL:.0f} target — check CTM call grades before judging (SOP lead-quality rule)"
        return "OK", ""      # it produces leads — never a negative candidate
    if cat == "junk" and cost > 0:
        return "CUT", "junk intent — not a customer, cut at any spend"
    if cat == "brand":
        if cost >= CUT_COMPETITOR_SPEND:
            return "CUT", f"materials brand / supplier search, ${cost:,.0f} with 0 leads (SOP: cut at ~$50-75)"
        if cost >= 15:
            return "WATCH", f"materials brand — ${cost:,.0f} so far; cut at ${CUT_COMPETITOR_SPEND:.0f} (note: supplier searches occasionally convert)"
        return "OK", ""
    if GUTTER.search(term.lower()) and cat == "relevant" and cost >= WATCH_SPEND:
        return "REVIEW", f"gutter gray zone (${cost:,.0f}, 0 leads) — converted once in Fort Smith; check FS data before negating (SOP standing exception)"
    t = term.lower().strip()
    is_core = cat == "relevant" and (
        (CORE_STEM.search(t) and (CORE_INTENT.search(t) or GEO.search(t))) or CORE_BARE.match(t)
        or SPANISH.search(t))    # SOP: Spanish roofing queries historically convert — never cut
    if conv == 0:
        if cat == "competitor":
            if cost >= CUT_COMPETITOR_SPEND:
                return "CUT", f"competitor name, ${cost:,.0f} across {weeks_active} wk(s), never converted — campaign-level phrase negative (SOP)"
            if cost > 0:
                return "WATCH", f"competitor name — ${cost:,.0f} so far, cut at ${CUT_COMPETITOR_SPEND:.0f}"
        if cat == "maybe_company":
            if cost >= WATCH_SPEND:
                return "VERIFY", f"looks like a company name (${cost:,.0f}, 0 leads) — confirm competitor vs coincidence, then add to competitors.txt"
            return "OK", ""
        if is_core:
            if cost >= CUT_RELEVANT_SPEND and clicks >= CUT_RELEVANT_CLICKS:
                return "REVIEW", f"real customer query at ${cost:,.0f}/{clicks:.0f} clicks with 0 leads — check ad group/landing fit or tracking; do NOT negate"
            return "OK", ""
        if cat == "relevant":
            if cost >= CUT_RELEVANT_SPEND and clicks >= CUT_RELEVANT_CLICKS:
                return "CUT", f"${cost:,.0f} / {clicks:.0f} clicks with 0 leads — past the evidence bar"
            if cost >= CUT_RELEVANT_SPEND:
                return "WATCH", f"${cost:,.0f} but only {clicks:.0f} click(s) — pricey clicks, thin evidence; cut at {CUT_RELEVANT_CLICKS}+ clicks"
            if cost >= WATCH_SPEND:
                return "WATCH", f"${cost:,.0f}, 0 leads so far — cut bar is ${CUT_RELEVANT_SPEND:.0f} + {CUT_RELEVANT_CLICKS} clicks"
    return "OK", ""
