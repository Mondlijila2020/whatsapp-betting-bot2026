import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests, random, math, json
from datetime import datetime, timedelta
from time import time

app = Flask(__name__)

# ------------------------------
# CONFIG
# ------------------------------
VOUCHER_FILE = os.path.join(os.getcwd(), "vouchers.json")
approved_users = {}

# Environment variables (set on Render)
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")  # d011b6d8d9mshdad193e8e30d8b0p13c504jsnf3f2e88fddd7
RAPIDAPI_HOST = os.environ.get("RAPIDAPI_HOST")  # flashscore4.p.rapidapi.com
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER")  # whatsapp:+27671502312

# ------------------------------
# TEAM DATABASE
# ------------------------------
teams = {
    "arsenal": 85, "liverpool": 88, "chelsea": 80, "man city": 92, "man united": 84,
    "real madrid": 90, "barcelona": 89, "atletico madrid": 84,
    "juventus": 88, "inter": 86, "ac milan": 84,
    "bayern": 91, "dortmund": 86, "leipzig": 82,
    "sundowns": 88, "pirates": 82, "chiefs": 80, "stellies": 75
}

# ------------------------------
# LEAGUE MODIFIERS
# ------------------------------
league_modifiers = {
    "epl": {"avg_goals": 2.8, "home_advantage": 5},
    "la liga": {"avg_goals": 2.5, "home_advantage": 4},
    "serie a": {"avg_goals": 2.4, "home_advantage": 4},
    "bundesliga": {"avg_goals": 3.0, "home_advantage": 6},
    "psl": {"avg_goals": 2.1, "home_advantage": 7}
}

# ------------------------------
# VOUCHER FUNCTIONS
# ------------------------------
def load_vouchers():
    try:
        with open(VOUCHER_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_vouchers(vouchers):
    with open(VOUCHER_FILE, "w") as f:
        json.dump(vouchers, f)

def generate_code():
    import string
    return "UMK-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def create_voucher():
    vouchers = load_vouchers()
    code = generate_code()
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    vouchers.append({"code": code, "expires": expiry, "used": False, "used_by": None})
    save_vouchers(vouchers)
    return code, expiry

def validate_voucher(user, code):
    vouchers = load_vouchers()
    for v in vouchers:
        if v["code"] == code:
            if datetime.now() > datetime.strptime(v["expires"], "%Y-%m-%d"):
                return "expired"
            if v["used"]:
                return "used"
            v["used"] = True
            v["used_by"] = user
            save_vouchers(vouchers)
            return "valid"
    return "invalid"

# ------------------------------
# LEAGUE DETECTION
# ------------------------------
def detect_league(team1, team2):
    t1, t2 = team1.lower(), team2.lower()
    if t1 in ["arsenal","liverpool","chelsea","man city","man united"] or \
       t2 in ["arsenal","liverpool","chelsea","man city","man united"]:
        return "epl"
    elif t1 in ["real madrid","barcelona","atletico madrid"] or \
         t2 in ["real madrid","barcelona","atletico madrid"]:
        return "la liga"
    elif t1 in ["juventus","inter","ac milan"] or \
         t2 in ["juventus","inter","ac milan"]:
        return "serie a"
    elif t1 in ["bayern","dortmund","leipzig"] or \
         t2 in ["bayern","dortmund","leipzig"]:
        return "bundesliga"
    elif t1 in ["sundowns","pirates","chiefs","stellies"] or \
         t2 in ["sundowns","pirates","chiefs","stellies"]:
        return "psl"
    else:
        return "epl"

# ------------------------------
# POISSON FUNCTION
# ------------------------------
def poisson(lmbda):
    L = math.exp(-lmbda)
    k = 0
    p = 1
    while p > L:
        k += 1
        p *= random.random()
    return k - 1

# ------------------------------
# MATCH PREDICTION
# ------------------------------
def predict_match(team1, team2, high_prob=False):
    s1, s2 = teams.get(team1.lower(), 75), teams.get(team2.lower(), 75)
    league = detect_league(team1, team2)
    mod = league_modifiers.get(league, {"avg_goals":2.5,"home_advantage":5})
    s1 += mod["home_advantage"]

    total = s1 + s2
    win1, win2 = (s1/total)*100, (s2/total)*100
    draw = 100 - (win1 + win2)

    if high_prob:
        max_prob = max(win1, win2, draw)
        if max_prob < 80:
            diff = 80 - max_prob
            if max_prob == win1:
                win1 += diff
                others = win2 + draw
                win2 -= diff*(win2/others)
                draw -= diff*(draw/others)
            elif max_prob == win2:
                win2 += diff
                others = win1 + draw
                win1 -= diff*(win1/others)
                draw -= diff*(draw/others)
            else:
                draw += diff
                others = win1 + win2
                win1 -= diff*(win1/others)
                win2 -= diff*(win2/others)
    win1, win2, draw = round(win1), round(win2), round(draw)
    lambda1, lambda2 = s1/100*mod["avg_goals"], s2/100*mod["avg_goals"]
    score1, score2 = poisson(lambda1), poisson(lambda2)

    over25 = max(50,min(85,60+int((lambda1+lambda2-2)*10)))
    btts = max(45,min(80,50+int(abs(lambda1-lambda2)*5)))
    double_chance = win1+draw

    return f"""
⚽ UMKHOMA MATCH ANALYSIS ({league.upper()})

{team1} Win: {win1}%
Draw: {draw}%
{team2} Win: {win2}%

TOP 3 BETTING OUTCOMES:

1️⃣ Over 2.5 Goals — {over25}%
2️⃣ Both Teams To Score — {btts}%
3️⃣ Double Chance {team1} — {double_chance}%

Most Likely Score:
{score1}-{score2}
"""

# ------------------------------
# CACHE
# ------------------------------
fixtures_cache = {}
odds_cache = {}

# ------------------------------
# LIVE FIXTURES (CACHED)
# ------------------------------
def fetch_live_fixtures_cached(league_slug):
    now = time()
    if league_slug in fixtures_cache:
        t, data = fixtures_cache[league_slug]
        if now - t < 600:
            return data
    data = fetch_live_fixtures(league_slug)
    fixtures_cache[league_slug] = (now, data)
    return data

def fetch_live_fixtures(league_slug):
    try:
        url = f"https://api.sportdb.dev/api/football/{league_slug}/fixtures"
        response = requests.get(url)
        data = response.json()
        fixtures = []
        for match in data.get("data", []):
            home = match.get("home_team", {}).get("name")
            away = match.get("away_team", {}).get("name")
            date = match.get("date", "").split("T")[0]
            if home and away:
                fixtures.append(f"{home} vs {away} ({date})")
        return fixtures if fixtures else ["No upcoming fixtures found."]
    except Exception as e:
        return [f"Error fetching fixtures: {e}"]

# ------------------------------
# LIVE ODDS (CACHED)
# ------------------------------
def fetch_live_odds_cached(league, team1, team2):
    now = time()
    key = f"{league.lower()}_{team1.lower()}_{team2.lower()}"
    if key in odds_cache:
        t, data = odds_cache[key]
        if now - t < 300:
            return data
    data = fetch_live_odds(league, team1, team2)
    odds_cache[key] = (now,data)
    return data

def fetch_live_odds(league, team1, team2):
    try:
        url = f"https://{RAPIDAPI_HOST}/odds"
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }
        params = {"league": league.lower(), "team1": team1, "team2": team2}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        if data and "odds" in data and len(data["odds"])>0:
            odds = data["odds"][0]
            return f"📊 Live Odds ({team1} vs {team2}):\nHome Win: {odds.get('home')}\nDraw: {odds.get('draw')}\nAway Win: {odds.get('away')}"
        return "⚠️ No odds found for this match."
    except Exception as e:
        return f"⚠️ Error fetching odds: {e}"

# ------------------------------
# UMKHOMA SIGNATURE
# ------------------------------
def umkhoma_signature(text):
    return f"{text}\n\n— UMKHOMA 🤖"

# ------------------------------
# FLASK ENDPOINT
# ------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")
    resp = MessagingResponse()
    msg = resp.message()

    # Admin generate voucher
    if user == ADMIN_NUMBER and incoming.lower() == "admin generate":
        code, expiry = create_voucher()
        msg.body(umkhoma_signature(f"🎟️ New Voucher Created\nCode: {code}\nExpires: {expiry}"))
        return str(resp)

    # Voucher validation
    if user not in approved_users:
        result = validate_voucher(user, incoming)
        if result == "valid":
            approved_users[user] = True
            msg.body(umkhoma_signature("✅ Voucher accepted! UMKHOMA at your service! You can now request matches or fixtures."))
            return str(resp)
        elif result == "expired":
            msg.body(umkhoma_signature("❌ Voucher expired."))
            return str(resp)
        elif result == "used":
            msg.body(umkhoma_signature("❌ Voucher already used."))
            return str(resp)
        else:
            msg.body(umkhoma_signature("🔐 Enter a valid voucher code to access UMKHOMA predictions."))
            return str(resp)

    # Fixtures request
    if incoming.lower().startswith("fixtures"):
        parts = incoming.split()
        if len(parts) == 2:
            league = parts[1].lower()
            slug_map = {"epl":"england/premier-league","la liga":"spain/laliga","serie a":"italy/serie-a","bundesliga":"germany/bundesliga","psl":"south-africa/psl"}
            slug = slug_map.get(league)
            if slug:
                fixtures = fetch_live_fixtures_cached(slug)
                msg.body(umkhoma_signature(f"📅 Upcoming {league.upper()} Fixtures:\n" + "\n".join(fixtures)))
            else:
                msg.body(umkhoma_signature("❌ League not found."))
        else:
            msg.body(umkhoma_signature("Send like: fixtures EPL"))
        return str(resp)

    # High probability
    high_prob = False
    if incoming.lower().startswith("high probability"):
        incoming = incoming.replace("high probability","").strip()
        high_prob = True

    # Odds all
    if incoming.lower() == "odds all":
        all_odds_messages = []
        leagues = {"EPL":"england/premier-league","La Liga":"spain/laliga","Serie A":"italy/serie-a","Bundesliga":"germany/bundesliga","PSL":"south-africa/psl"}
        for league_name, slug in leagues.items():
            fixtures = fetch_live_fixtures_cached(slug)
            for match in fixtures[:3]:
                try:
                    team1, team2 = match.split(" vs ")[0], match.split(" vs ")[1].split(" (")[0]
                    odds_text = fetch_live_odds_cached(league_name, team1, team2)
                    all_odds_messages.append(f"{league_name} | {team1} vs {team2}\n{odds_text}")
                except:
                    all_odds_messages.append(f"{league_name} | Error fetching odds for match: {match}")
        msg.body(umkhoma_signature("\n\n".join(all_odds_messages)))
        return str(resp)

    # Single match odds
    if incoming.lower().startswith("odds"):
        parts = incoming.split()
        if len(parts) >= 4:
            league = parts[1]
            team1 = parts[2]
            team2 = parts[4] if parts[3].lower()=="vs" else parts[3]
            odds_text = fetch_live_odds_cached(league, team1, team2)
            msg.body(umkhoma_signature(odds_text))
        else:
            msg.body(umkhoma_signature("Send like: odds EPL Arsenal vs Liverpool"))
        return str(resp)

    # Match prediction
    if "vs" in incoming.lower():
        teams_input = incoming.split("vs")
        if len(teams_input) == 2:
            result = predict_match(teams_input[0].strip(), teams_input[1].strip(), high_prob=high_prob)
            msg.body(umkhoma_signature(result))
        else:
            msg.body(umkhoma_signature("❌ Invalid format. Send like: Arsenal vs Liverpool"))
    else:
        msg.body(umkhoma_signature(
            "Send a match like:\nArsenal vs Liverpool\nSundowns vs Pirates\n"
            "Or request fixtures:\nfixtures EPL\n"
            "Or odds:\nodds EPL Arsenal vs Liverpool\n"
            "Or type: odds all\nUMKHOMA is here to help you with live predictions and betting insights!"
        ))

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
