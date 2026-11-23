import csv, random, os, sys, datetime as dt
from industries import I, GENERIC_PAINS

R = random.Random(20261122)
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
N = 50000
TODAY = dt.date(2026, 11, 22)
assert len(I) == 50, len(I)

CITIES = [
 ("Phoenix","Maricopa","602",0.30,["85003","85004","85006","85008","85012","85014","85015","85016","85018","85020","85021","85022","85027","85032","85034","85040","85044","85048","85050","85085"],
  ["Central Ave","Camelback Rd","Indian School Rd","McDowell Rd","Thomas Rd","Bell Rd","Cactus Rd","7th St","16th St","24th St","Glendale Ave","Baseline Rd","Southern Ave","Washington St","Van Buren St","Northern Ave","Dunlap Ave","Tatum Blvd","Union Hills Dr","Deer Valley Rd"]),
 ("Tucson","Pima","520",0.20,["85701","85704","85705","85710","85711","85712","85713","85715","85716","85718","85719","85730","85741","85745","85748","85750"],
  ["Speedway Blvd","Broadway Blvd","Oracle Rd","Grant Rd","Campbell Ave","Stone Ave","22nd St","Tanque Verde Rd","Ina Rd","Swan Rd","Kolb Rd","Congress St","Fort Lowell Rd","River Rd","Craycroft Rd","Wilmot Rd"]),
 ("Mesa","Maricopa","480",0.15,["85201","85202","85203","85204","85205","85206","85207","85209","85210","85212","85213","85215"],
  ["Main St","University Dr","Broadway Rd","Southern Ave","Power Rd","Dobson Rd","Alma School Rd","Country Club Dr","Gilbert Rd","Higley Rd","Baseline Rd","McKellips Rd"]),
 ("Scottsdale","Maricopa","480",0.13,["85250","85251","85254","85255","85257","85258","85259","85260","85262","85266"],
  ["Scottsdale Rd","Shea Blvd","Hayden Rd","Pima Rd","Camelback Rd","Indian Bend Rd","Frank Lloyd Wright Blvd","Via Linda","Thunderbird Rd","Raintree Dr"]),
 ("Tempe","Maricopa","480",0.12,["85281","85282","85283","85284","85285"],
  ["Mill Ave","University Dr","Rural Rd","Apache Blvd","Broadway Rd","McClintock Dr","Southern Ave","Warner Rd","Elliot Rd","Priest Dr"]),
 ("Flagstaff","Coconino","928",0.10,["86001","86004","86005"],
  ["Route 66","Milton Rd","Butler Ave","San Francisco St","Beaver St","Fort Valley Rd","Lake Mary Rd","Country Club Dr","Huntington Dr","Cedar Ave"]),
]

PREFIX = ["Saguaro","Desert","Sonoran","Copper","Mesa","Canyon","Red Rock","Camelback","Superstition","Ironwood","Palo Verde","Mesquite","Ocotillo","Agave","Cholla","Sunset","Sunrise","Valley","Cactus","Coyote","Roadrunner","Javelina","Monsoon","Granite","Sandstone","Adobe","Pueblo","Hacienda","Casa","Rio","Salt River","Gila","Verde","Santa Cruz","Catalina","Rincon","Tortolita","Pinnacle","Summit","Highland","Ponderosa","Aspen","Pine","Mountain","Peak","Northern","Southwest","Western","Arizona","Grand","Heritage","Legacy","Cornerstone","Keystone","Trailhead","Frontier","Pioneer","Liberty","Golden","Silver","Turquoise","Amber","Bluebird","Quail","Hummingbird","Falcon","Hawk","Phoenix Rising","Oasis","Mirage","Horizon","Vista","Skyline","Starlight","Cottonwood","Willow","Sycamore","Juniper","Sage","Prickly Pear","Bisbee","Tombstone","Prescott","Sedona","Kayenta","Navajo","Hopi","Tubac","Patagonia","Wickenburg","Paradise","Arcadia","Encanto","Biltmore","Ahwatukee","Gilbert","Chandler","Ventana","Sabino","Tanque","Dove Mountain","McDowell","Papago","South Mountain","Estrella","White Tank","Four Peaks","Bright Angel","Kaibab","Mogollon","Tonto","Apache","Coronado","Dragoon","Chiricahua","Painted Desert","Petrified","Lumberjack","Snowbowl","Elden","Humphreys","Kachina","Route 66","Old Town","Downtown","Uptown","Midtown","Eastside","Westside","Northside","Southside","Crossroads","Main Street","Union","Capitol","Metro","Premier","Elite","True North","Bright Path","Clear Water","Blue Sky","Green Leaf","Evergreen","Summit Ridge","Stone Creek","River Bend","Sun Valley","Sun Country","Copper State"]
FIRST = ["Maria","Jose","Juan","Ana","Luis","Carlos","Sofia","Diego","Elena","Miguel","Isabel","Gabriel","Lucia","Antonio","Valeria","James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth","William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Christopher","Karen","Daniel","Nancy","Matthew","Lisa","Anthony","Betty","Mark","Sandra","Steven","Ashley","Andrew","Kimberly","Joshua","Emily","Kevin","Donna","Brian","Michelle","Ryan","Amanda","Jacob","Melissa","Nicholas","Stephanie","Tyler","Rebecca","Brandon","Laura","Justin","Rachel","Aaron","Megan","Adam","Hannah","Nathan","Olivia","Kyle","Emma","Ethan","Ava","Noah","Mia","Liam","Chloe","Mason","Grace","Wei","Mei","Jin","Hana","Yuki","Kenji","Priya","Raj","Anjali","Arjun","Fatima","Omar","Layla","Ahmed","Nadia","Tariq","Aisha","Kwame","Imani","Malik","Jada","Darnell","Keisha","Tanisha","Marcus","Andre","Leilani","Kai","Nizhoni","Ahiga","Shilah","Dyani","Tse","Chenoa","Hiroshi","Minh","Linh","Thanh","Huy","Seo-yeon","Min-jun","Ji-woo","Dmitri","Anya","Ivan","Katya","Sven","Ingrid","Lars","Marco","Giulia","Paolo","Francesca","Pierre","Camille","Hector","Rosa","Ramon","Carmen","Alejandro","Gloria","Ricardo","Teresa","Fernando","Pilar","Rafael","Beatriz"]
LAST = ["Garcia","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Perez","Sanchez","Ramirez","Torres","Flores","Rivera","Gomez","Diaz","Reyes","Morales","Cruz","Ortiz","Gutierrez","Chavez","Ramos","Ruiz","Alvarez","Mendoza","Castillo","Jimenez","Vasquez","Romero","Herrera","Medina","Aguilar","Vargas","Guzman","Salazar","Delgado","Valenzuela","Soto","Contreras","Silva","Estrada","Smith","Johnson","Williams","Brown","Jones","Miller","Davis","Wilson","Anderson","Taylor","Thomas","Moore","Jackson","Martin","Lee","Thompson","White","Harris","Clark","Lewis","Robinson","Walker","Young","Allen","King","Wright","Scott","Hill","Green","Adams","Baker","Nelson","Carter","Mitchell","Roberts","Turner","Phillips","Campbell","Parker","Evans","Edwards","Collins","Stewart","Morris","Murphy","Cook","Rogers","Morgan","Peterson","Cooper","Reed","Bailey","Bell","Kelly","Howard","Ward","Cox","Richardson","Wood","Watson","Brooks","Bennett","Gray","James","Hughes","Price","Sanders","Myers","Long","Ross","Foster","Powell","Jenkins","Perry","Russell","Sullivan","Fisher","Henderson","Coleman","Patterson","Jordan","Graham","Reynolds","Hamilton","Ford","Wallace","Nguyen","Tran","Le","Pham","Huynh","Vo","Kim","Park","Choi","Chen","Wang","Li","Zhang","Liu","Yang","Huang","Wu","Tanaka","Sato","Suzuki","Yamamoto","Patel","Shah","Singh","Kumar","Gupta","Sharma","Khan","Ali","Hassan","Ibrahim","Begay","Yazzie","Benally","Tsosie","Nez","Etsitty","Harjo","Johnson-Begay","Okafor","Mensah","Diallo","Ivanov","Petrov","Novak","Kowalski","Larsen","Nielsen","Rossi","Romano","Bianchi","Dubois","Moreau","Schmidt","Muller","Weber","O'Brien","Murray","Doyle","Byrne","Fitzgerald"]
SUFFIX = ["LLC","Inc","Co","Group","LLC","LLC","Inc","PLLC"]

def pick_weighted(items, weights): return R.choices(items, weights=weights, k=1)[0]

def slug(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())

def employees():
    band = pick_weighted(["1-49","50-99","100-250"], [0.82,0.11,0.07])
    if band == "1-49":
        n = int(min(49, max(1, R.lognormvariate(2.2, 0.8))))
    elif band == "50-99":
        n = R.randint(50, 99)
    else:
        n = R.randint(100, 250)
    return n, band

used_names = set()
def company_name(ind):
    words = ind[6]
    for _ in range(50):
        p = R.random()
        if p < 0.55:
            base = f"{R.choice(PREFIX)} {R.choice(words)}"
        elif p < 0.85:
            base = f"{R.choice(LAST)} {R.choice(words)}"
        else:
            base = f"{R.choice(LAST)} & {R.choice(LAST)} {R.choice(words)}"
        if base not in used_names:
            used_names.add(base)
            return base
    base = f"{R.choice(PREFIX)} {R.choice(PREFIX)} {R.choice(words)}"
    i = 2
    while base in used_names:
        base = f"{base} {i}"; i += 1
    used_names.add(base)
    return base

def fphone(area, ext=None):
    s = f"({area}) 555-01{R.randint(0,99):02d}"
    return f"{s} ext. {ext}" if ext else s

def rdate(days_back_max, days_back_min=0):
    return TODAY - dt.timedelta(days=R.randint(days_back_min, days_back_max))

PLATFORMS = ["WordPress","Wix","Squarespace","Shopify","GoDaddy Builder","Custom","Webflow","None"]
CRMS = ["None","Spreadsheet","HubSpot","Salesforce","Zoho CRM","Pipedrive","Industry-specific system"]
POS = ["None","Square","Toast","Clover","Lightspeed","Shopify POS","Industry-specific system"]
BOOK = ["None","Phone only","Calendly","Mindbody","Vagaro","Jane","Industry-specific system","Online ordering only"]
EVENTS = ["Opened a new location","Remodeled the space","New ownership","Added a new service line","Won a local award","Expanded hours","Moved to a larger space","Launched a new website","Hired a new manager","None"]
STATUS = ["New","New","New","New","Contacted","Contacted","Replied","Quoted","Customer","Lost"]
OWNERSHIP = ["Independent","Independent","Independent","Local group","Regional chain","National chain franchise"]
STRUCT = ["LLC","LLC","LLC","S-Corp","Corporation","Sole proprietorship","Partnership"]
PREF = ["Email","Email","Phone","Text","LinkedIn"]

NOTE_TEMPLATES = [
 "Spoke w/ front desk {d} - owner busy, call back AM. Mentioned {p}.",
 "met at {ev} mixer. interested but 'not till after Q1'. pain pt: {p}",
 "Website says open 7 days but phone msg says closed Sun?? verify",
 "{p} - came up twice. owner {o} handles all vendor decisions",
 "LVM x2. no response. try {pref} instead",
 "Referred by existing client. warm. ask about {p}",
 "said they already have someone for this... contract ends {d}",
 "Mgr {m} friendly, decision is {o}'s. budget tight this yr",
 "",
 "",
 "new location coming per their IG. {p} likely",
 "DO NOT call before 10am per {m}",
]

companies, contacts = [], []
cid = 0
city_weights = [c[3] for c in CITIES]

def make_company(ind, forced=None):
    global cid
    cid += 1
    city = forced["city"] if forced else pick_weighted(CITIES, city_weights)
    name = forced["name"] if forced else company_name(ind)
    emp, band = (forced["emp"], forced["band"]) if forced else employees()
    suffix = R.choice(SUFFIX) if ind[2] not in ("Community & Education",) else R.choice(["Inc","Foundation",""])
    legal = f"{name} {suffix}".strip()
    dom = slug(name) + ".example"
    rev = round(emp * ind[3] * R.lognormvariate(0, 0.25), -2)
    margin = max(0.005, R.gauss(ind[4], 0.05))
    if R.random() < 0.08: margin = -abs(R.gauss(0.04, 0.03))
    exp = round(rev * (1 - margin), -2)
    net = rev - exp
    growth = round(R.gauss(0.04, 0.09) * 100, 1)
    reviews = int(R.lognormvariate(3.3 if emp < 50 else 4.2, 0.9))
    rating = round(min(5.0, max(2.6, R.gauss(4.3, 0.35))), 1)
    web_plat = pick_weighted(PLATFORMS, [30,15,12,6,8,15,4,10])
    pains = R.sample(GENERIC_PAINS, R.randint(0,2)) + R.sample(ind[8], R.randint(1, min(2, len(ind[8]))))
    pains = pains[:3]
    if web_plat == "None" and "outdated website" not in pains: pains = (["no website"] + pains)[:3]
    fb = R.random() < 0.75; ig = R.random() < 0.6; li = R.random() < (0.7 if ind[2] in ("Professional Services","B2B & Industrial") else 0.4); tt = R.random() < 0.2
    city_name, county, area, _, zips, streets = city
    if forced:
        addr = forced["addr"]
    elif city_name in ("Phoenix","Mesa","Scottsdale","Tempe"):
        addr = f"{R.randint(100, 9899)} {R.choice(['E','W','N','S'])} {R.choice(streets)}"
    else:
        addr = f"{R.randint(100, 9899)} {R.choice(streets)}"
    zipc = forced["zip"] if forced else R.choice(zips)
    verified = rdate(900, 400) if R.random() < 0.10 else rdate(330)
    dnc = R.random() < 0.04
    status = R.choice(STATUS)
    owner_first, owner_last = R.choice(FIRST), R.choice(LAST)
    mgr_first = R.choice(FIRST)
    ev = pick_weighted(EVENTS, [6,7,4,7,4,5,4,6,5,52])
    note = R.choice(NOTE_TEMPLATES).format(d=rdate(200).strftime("%m/%d"), p=pains[0] if pains else "pricing", ev=R.choice(["Chamber","BNI","networking","trade show"]),
                                           o=owner_first, m=mgr_first, pref=R.choice(["email","text","LinkedIn"]))
    if R.random() < 0.03:  # conflicting note
        note = (note + " ").strip() + f" Owner said they have about {max(1, emp*3)} employees."
    row = {
        "company_id": f"AZC-{cid:05d}",
        "company_name": name,
        "legal_name": legal,
        "naics_code": ind[0], "naics_title": ind[1], "industry_group": ind[2],
        "year_founded": R.randint(1972, 2025),
        "legal_structure": R.choice(STRUCT) if "Community" not in ind[2] else "Nonprofit",
        "ownership_type": R.choice(OWNERSHIP),
        "employees": emp, "size_band": band,
        "locations": 1 if emp < 30 else R.choice([1,1,2,2,3,4]),
        "square_feet": int(emp * R.randint(150, 600) + R.randint(600, 2500)),
        "building_age_years": R.randint(1, 60),
        "street_address": addr, "city": city_name, "state": "AZ", "zip": zipc, "county": county,
        "main_phone": fphone(area),
        "website": "" if web_plat == "None" else f"https://www.{dom}",
        "general_email": "" if R.random() < 0.05 else f"{R.choice(['info','hello','office','contact'])}@{dom}",
        "annual_revenue": int(rev), "annual_expenses": int(exp), "net_income": int(net),
        "profit_margin_pct": round(net / rev * 100, 1) if rev else 0,
        "revenue_growth_pct": growth,
        "open_job_postings": max(0, int(R.gauss(emp/25, 1.5))),
        "recent_event": ev,
        "recent_event_date": "" if ev == "None" else rdate(365).isoformat(),
        "website_platform": web_plat,
        "website_last_updated": "",
        "has_facebook": "Yes" if fb else "No", "facebook_followers": int(R.lognormvariate(6.5, 1.1)) if fb else 0,
        "has_instagram": "Yes" if ig else "No", "instagram_followers": int(R.lognormvariate(6.8, 1.3)) if ig else 0,
        "has_linkedin": "Yes" if li else "No", "linkedin_followers": int(R.lognormvariate(5.5, 1.2)) if li else 0,
        "has_tiktok": "Yes" if tt else "No",
        "has_google_business_profile": "Yes" if R.random() < 0.85 else "No",
        "google_rating": rating, "google_review_count": reviews,
        "est_marketing_budget": int(rev * ind[5] * R.lognormvariate(0, 0.35)),
        "est_it_budget": int(rev * R.uniform(0.01, 0.04)),
        "est_facilities_budget": int(rev * R.uniform(0.01, 0.05)),
        "crm_system": R.choice(CRMS),
        "pos_system": R.choice(POS),
        "booking_system": R.choice(BOOK),
        "online_booking_or_ordering": "Yes" if R.random() < 0.45 else "No",
        "pain_points": "; ".join(pains),
        "lead_status": status,
        "do_not_contact": "Yes" if dnc else "No",
        "last_verified": verified.isoformat(),
        "record_note": note,
        "_area": area, "_dom": dom, "_owner": (owner_first, owner_last), "_mgr": mgr_first,
    }
    founded = dt.date(row["year_founded"], 6, 1)
    if web_plat != "None":
        span = max(30, (TODAY - founded).days)
        row["website_last_updated"] = (TODAY - dt.timedelta(days=R.randint(0, min(span, 2200)))).isoformat()
    return row

ind_weights = [1]*50
for _ in range(N - int(N*0.03)):
    ind = R.choice(I)
    companies.append(make_company(ind))

# near-duplicates (~3%)
for src in R.sample(companies, N - len(companies)):
    ind = next(i for i in I if i[0] == src["naics_code"])
    city = next(c for c in CITIES if c[0] == src["city"])
    variant = R.choice([src["company_name"] + " " + R.choice(["LLC","Inc"]), src["company_name"].replace(" & ", " and "), src["company_name"] + " Co", "The " + src["company_name"]])
    used_names.add(variant)
    d = make_company(ind, forced={"city": city, "name": variant, "emp": src["employees"], "band": src["size_band"], "addr": src["street_address"], "zip": src["zip"]})
    d["record_note"] = (d["record_note"] + " possible dup?").strip()
    companies.append(d)

R.shuffle(companies)
for i, c in enumerate(companies, 1):
    c["company_id"] = f"AZC-{i:05d}"

# contacts
ctr = 0
for c in companies:
    ind = next(i for i in I if i[0] == c["naics_code"])
    roles = [(ind[7][0], "Final say"), (ind[7][1], "Influencer"), (ind[7][2], "Gatekeeper")]
    for k, (title, decision) in enumerate(roles):
        ctr += 1
        if k == 0:
            fn, ln = c["_owner"]
        elif k == 1:
            fn, ln = c["_mgr"], R.choice(LAST)
        else:
            fn, ln = R.choice(FIRST), R.choice(LAST)
        email = f"{slug(fn)}.{slug(ln)}@{c['_dom']}"
        if R.random() < 0.05: email = ""
        yrs = R.randint(1, max(1, min(35, TODAY.year - c["year_founded"])))
        contacts.append({
            "contact_id": f"CON-{ctr:06d}",
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "first_name": fn, "last_name": ln, "title": title,
            "contact_role": ["Owner / decision-maker","Operations","Office / marketing"][k],
            "decision_role": decision,
            "email": email,
            "direct_phone": fphone(c["_area"], R.randint(100, 899)),
            "mobile_phone": fphone(c["_area"]) if R.random() < 0.7 else "",
            "preferred_contact": R.choice(PREF),
            "years_at_company": yrs,
            "email_opt_in": "No" if c["do_not_contact"] == "Yes" else ("Yes" if R.random() < 0.8 else "No"),
            "last_contacted": "" if c["lead_status"] == "New" else rdate(240).isoformat(),
            "headline": f"{title} at {c['company_name']} | {yrs} yrs in {ind[2].split(' & ')[0].lower()}",
        })

def write(name, rows, fields):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

cfields = [k for k in companies[0] if not k.startswith("_")]
write("companies.csv", companies, cfields)
write("contacts.csv", contacts, list(contacts[0].keys()))
write("industries.csv", [{"naics_code":i[0],"naics_title":i[1],"industry_group":i[2],"typical_revenue_per_employee":i[3],"typical_profit_margin_pct":round(i[4]*100,1),"typical_marketing_pct_of_revenue":round(i[5]*100,1),"common_pain_points":"; ".join(i[8]),"owner_title":i[7][0],"operations_title":i[7][1],"office_marketing_title":i[7][2]} for i in I],
      ["naics_code","naics_title","industry_group","typical_revenue_per_employee","typical_profit_margin_pct","typical_marketing_pct_of_revenue","common_pain_points","owner_title","operations_title","office_marketing_title"])
write("cities.csv", [{"city":c[0],"state":"AZ","county":c[1],"area_code":c[2],"share_of_companies_pct":int(c[3]*100),"zip_codes":" ".join(c[4])} for c in CITIES],
      ["city","state","county","area_code","share_of_companies_pct","zip_codes"])
print(len(companies), len(contacts))
