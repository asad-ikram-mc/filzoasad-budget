import urllib.request, urllib.error, json, datetime, os, sys, time

month_names = ["","January","February","March","April","May","June",
               "July","August","September","October","November","December"]

override = os.environ.get('MONTH_OVERRIDE', '').strip()
if override:
    month_key = override
    year, mon = int(override.split('_')[0]), int(override.split('_')[1])
else:
    now = datetime.datetime.utcnow()
    first = now.replace(day=1)
    prev = first - datetime.timedelta(days=1)
    year, mon = prev.year, prev.month
    month_key = f"{year}_{mon:02d}"

month_name = f"{month_names[mon]} {year}"
print(f"Generating analysis for: {month_name} ({month_key})")

firebase_url = os.environ['FIREBASE_URL'].rstrip('/')
api_key = os.environ['ANTHROPIC_API_KEY']

def firebase_get(path):
    url = f"{firebase_url}/{path}.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"Firebase GET {path} failed: {e}")
        return None

def firebase_put(path, data):
    url = f"{firebase_url}/{path}.json"
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='PUT')
    req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

month_data   = firebase_get(f"af/{month_key}") or {}
expenses_data = month_data.get('expenses', {})
income_data   = month_data.get('income', {})

EXPENSES = [
    {"id":"petrol",   "name":"Petrol",        "who":"asad",  "budget":30000,                        "acct":"ABL"},
    {"id":"shopping", "name":"Shopping",       "who":"asad",  "budget":40000,                        "acct":"ABL"},
    {"id":"dining",   "name":"Dining Out",     "who":"asad",  "budget":40000,                        "acct":"ABL"},
    {"id":"daily_a",  "name":"Daily (Asad)",   "who":"asad",  "budget":20000 if mon<=4 else 30000,   "acct":"HBL"},
    {"id":"ammi",     "name":"Ammi",           "who":"asad",  "budget":50000,                        "acct":"HBL"},
    {"id":"internet", "name":"Internet Bill",  "who":"asad",  "budget":14000,                        "acct":"HBL"},
    {"id":"phone_a",  "name":"Phone (Asad)",   "who":"asad",  "budget":5000,                         "acct":"HBL"},
    {"id":"grocery",  "name":"Grocery",        "who":"filza", "budget":50000,                        "acct":"SCB"},
    {"id":"mama",     "name":"Mama",           "who":"filza", "budget":50000,                        "acct":"HBL"},
    {"id":"toilet",   "name":"Toiletries",     "who":"filza", "budget":15000,                        "acct":"SCB"},
    {"id":"daily_f",  "name":"Daily (Filza)",  "who":"filza", "budget":20000 if mon<=4 else 30000,   "acct":"HBL"},
    {"id":"misc",     "name":"Miscellaneous",  "who":"filza", "budget":30000,                        "acct":"HBL"},
    {"id":"phone_f",  "name":"Phone (Filza)",  "who":"filza", "budget":5000,                         "acct":"HBL"},
    {"id":"server",   "name":"Server Sub",     "who":"filza", "budget":10000,                        "acct":"SCB"},
    {"id":"netflix",  "name":"Netflix",        "who":"filza", "budget":1100,                         "acct":"SCB"},
]

INCOME_SOURCES = [
    {"id":"filza_sal", "name":"Filza Salary",  "who":"filza", "exp":150000},
    {"id":"asad_mc",   "name":"M&C Saatchi",   "who":"asad",  "exp":600000 if mon<=4 else 966000},
    {"id":"asad_free", "name":"Freelance CXG", "who":"asad",  "exp":515000 if mon<=4 else 380000},
]

def total_spent(cat_id):
    cat = expenses_data.get(cat_id, {})
    if isinstance(cat, dict):
        return sum(v.get('amt', 0) for v in cat.values() if isinstance(v, dict))
    return 0

def inc_recvd(who):
    total = 0
    for src in INCOME_SOURCES:
        if src['who'] != who: continue
        inc = income_data.get(src['id'], {})
        if isinstance(inc, dict) and inc.get('received'):
            actual = inc.get('actual', src['exp'])
            total += float(actual) if actual else src['exp']
    return total

def sh(n):
    n = abs(round(n))
    if n >= 100000: return f"{n/100000:.1f}L"
    if n >= 1000:   return f"{round(n/1000)}K"
    return str(n)

a_exp = [e for e in EXPENSES if e['who']=='asad']
f_exp = [e for e in EXPENSES if e['who']=='filza']
a_bu  = sum(e['budget'] for e in a_exp)
f_bu  = sum(e['budget'] for e in f_exp)
a_sp  = sum(total_spent(e['id']) for e in a_exp)
f_sp  = sum(total_spent(e['id']) for e in f_exp)
a_inc = inc_recvd('asad')
f_inc = inc_recvd('filza')
t_inc = a_inc + f_inc
t_sp  = a_sp + f_sp
net   = t_inc - t_sp

over = [f"{e['name']} (over by {sh(total_spent(e['id'])-e['budget'])})"
        for e in EXPENSES if total_spent(e['id']) > e['budget']]
top3 = sorted(EXPENSES, key=lambda e: total_spent(e['id']), reverse=True)[:3]
top3 = [f"{e['name']}: {sh(total_spent(e['id']))}" for e in top3 if total_spent(e['id']) > 0]
unsp = [e['name'] for e in EXPENSES if total_spent(e['id']) == 0]

banks = [
    {"name":"Asad ABL",  "ids":["petrol","shopping","dining"]},
    {"name":"Asad HBL",  "ids":["daily_a","ammi","internet","phone_a"]},
    {"name":"Filza HBL", "ids":["mama","daily_f","misc","phone_f"]},
    {"name":"Filza SCB", "ids":["grocery","toilet","server","netflix"]},
]
bank_lines = []
for b in banks:
    exps = [e for e in EXPENSES if e['id'] in b['ids']]
    bu = sum(e['budget'] for e in exps)
    sp = sum(total_spent(e['id']) for e in exps)
    diff = bu - sp
    status = f"OVER by {sh(abs(diff))}" if diff < 0 else f"{sh(diff)} under"
    cats = ", ".join(f"{e['name']} {sh(total_spent(e['id']))}/{sh(e['budget'])}" for e in exps)
    bank_lines.append(f"- {b['name']} ({status}): {cats}")

prompt = f"""You are a deeply analytical personal finance advisor for a Pakistani household.
Write a thorough, specific, and insightful financial analysis. Be direct, detailed, and honest.
Reference specific PKR numbers. Use their names (Asad & Filza).

MONTH: {month_name}
HOUSEHOLD: Asad & Filza, Lahore Pakistan

INCOME RECEIVED:
- Asad: PKR {round(a_inc):,}
- Filza: PKR {round(f_inc):,}
- Combined: PKR {round(t_inc):,}
- Fix.com GBP 2,900 stays in UK Lloyds (separate)

EXPENSES:
- Asad: PKR {round(a_sp):,} of PKR {round(a_bu):,} budget ({round(a_sp/a_bu*100) if a_bu else 0}% used)
- Filza: PKR {round(f_sp):,} of PKR {round(f_bu):,} budget ({round(f_sp/f_bu*100) if f_bu else 0}% used)
- Net saved: PKR {round(net):,}

BANK BREAKDOWN:
{chr(10).join(bank_lines)}

TOP SPENDING: {', '.join(top3) if top3 else 'None logged'}
OVER BUDGET: {', '.join(over) if over else 'None - excellent!'}
UNSPENT: {', '.join(unsp[:5]) if unsp else 'All spent'}

DREAM GOALS: Jaecoo J5 PKR 50L, Europe Trip PKR 25L, Baby Fund PKR 50L, Visa Fund PKR 20L each

Write exactly these 4 sections with headings on their own line:

SUMMARY
(3-4 sentences on overall health, specific PKR wins and concerns.)

CATEGORY DEEP DIVE
(Each bank account analysis. Exact numbers. What was efficient, what needs attention.)

RECOMMENDATIONS
(5 numbered actions for next month. Each must cite specific PKR amounts.)

ACTIONS
(Write ONLY as a numbered list. Each line must start with a number and period e.g. "1. Do this". No intro sentences, no sub-headings, no markdown bold. Cover: 1) Did household overspend vs total budget - if yes exact PKR to withdraw from Pakistan Savings. 2) Any bank account needing funds moved. 3) Any budget reallocation for next month. 4) Any accounts that need no action. Max 6 numbered lines. Each line one clear action with exact PKR amount.)

TIP OF THE MONTH
(3-4 sentences connecting habits to their dream goals. Make it personal and motivating.)"""

# Read any extra prompt the user added from the website
extra_prompt_data = firebase_get(f"af/claude_extra_prompt/{month_key}") or {}
extra_prompt = extra_prompt_data.get("prompt", "").strip()
if extra_prompt:
    prompt += f"\n\nADDITIONAL INSTRUCTIONS FROM USER:\n{extra_prompt}"
    print(f"Extra prompt added: {extra_prompt[:80]}")

print(f"Calling Claude API... Income={sh(t_inc)}, Spent={sh(t_sp)}, Saved={sh(net)}")

payload = json.dumps({
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 1500,
    "messages": [{"role": "user", "content": prompt}]
}).encode('utf-8')

req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('x-api-key', api_key)
req.add_header('anthropic-version', '2023-06-01')

try:
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read().decode())
        text = resp['content'][0]['text']
        print(f"Claude responded! {len(text)} chars")
        print("--- PREVIEW ---")
        print(text[:400])
        print("---")
except urllib.error.HTTPError as e:
    print(f"API Error {e.code}: {e.read().decode()}")
    sys.exit(1)

result = firebase_put(f"af/claude_summary/{month_key}", {
    "text": text, "month": month_key,
    "savedAt": int(time.time()*1000), "savedBy": "github-actions"
})
print(f"Saved to Firebase! Analysis for {month_name} is live.")
