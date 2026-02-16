from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests, random, math, json
from datetime import datetime, timedelta

app = Flask(__name__)

# ------------------------------
# CONFIG
# ------------------------------
VOUCHER_FILE = "vouchers.json"
approved_users = {}
ADMIN_NUMBER = "whatsapp:+27611502312"  # Replace with your WhatsApp number
SPORTDB_API_KEY = "curl -H "X-API-Key: YOUR_API_KEY" https://api.sportdb.dev/api/flashscore/Y"    # Replace with your SportDB.dev API Key

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
    return "EPL-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

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
    team1_lower = team1.lower()
    team2_lower = team2.lower()
    if team1_lower in ["arsenal","liverpool","chelsea","man city","man united"] or \
       team2_lower in ["arsenal","liverpool","chelsea","man city","man united"]:
        return "epl"
    elif team1_lower in ["real madrid","barcelona","atletico madrid"] or \
         team2_lower in ["real madrid","barcelona","atletico madrid"]:
        return "la liga"
    elif team1_lower in ["juventus","inter","ac milan"] or \
         team2_lower in ["juventus","inter","ac milan"]:
        return "serie a"
    elif team1_lower in ["bayern","dortmund","leipzig"] or \
         team2_lower in ["bayern","dortmund","leipzig"]:
        return "bundesliga"
    elif team1_lower in ["sundowns","pirates","chiefs","stellies"] or \
         team2_lower in ["sundowns","pirates","chiefs","stellies"]:
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
# MATCH PREDICTION FUNCTION
# ------------------------------
def predict_match(team1, team2, high_prob=False):
    team1_lower = team1.lower()
    team2_lower = team2.lower()
    s1 = teams.get(team1_lower, 75)
    s2 = teams.get(team2_lower, 75)

    league = detect_league(team1, team2)
    modifier = league_modifiers.get(league, {"avg_goals":2.5, "home_advantage":5})
    s1 += modifier["home_advantage"]

    total = s1 + s2
    win1 = (s1/total)*100
    win2 = (s2/total)*100
    draw = 100 - (win1 + win2)

    if high_prob:
        max_prob = max(win1, win2, draw)
        if max_prob < 80:
            diff = 80 - max_prob
            if max_prob == win1:
                win1 += diff
                others = win2 + draw
                win2 -= diff * (win2/others)
                draw -= diff * (draw/others)
            elif max_prob == win2:
                win2 += diff
                others = win1 + draw
                win1 -= diff * (win1/others)
                draw -= diff * (draw/others)
            else:
                draw += diff
                others = win1 + win2
                win1 -= diff * (win1/others)
                win2 -= diff * (win2/others)
    win1, win2, draw = round(win1), round(win2), round(draw)

    lambda1 = s1/100 * modifier["avg_goals"]
    lambda2 = s2/100 * modifier["avg_goals"]
    score1 = poisson(lambda1)
    score2 = poisson(lambda2)

    over25 = 60 + int((lambda1+lambda2-2)*10)
    over25 = max(50, min(over25, 85))
    btts = 50 + int(abs(lambda1-lambda2)*5)
    btts = max(45, min(btts, 80))
    double_chance = win1 + draw

    return f"""
⚽ MATCH ANALYSIS ({league.upper()})

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
# LIVE FIXTURES FETCH
# ------------------------------
def fetch_live_fixtures(league_slug):
    try:
        url = f"https://api.sportdb.dev/api/football/{league_slug}/fixtures?api_key={SPORTDB_API_KEY}"
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
# FLASK ENDPOINT
# ------------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")
    resp = MessagingResponse()
    msg = resp.message()

    # Admin command
    if user == ADMIN_NUMBER and incoming.lower() == "admin generate":
        code, expiry = create_voucher()
        msg.body(f"🎟️ New Voucher Created\nCode: {code}\nExpires: {expiry}")
        return str(resp)

    # Voucher check
    if user not in approved_users:
        result = validate_voucher(user, incoming)
        if result == "valid":
            approved_users[user] = True
            msg.body("✅ Voucher accepted! You can now request matches or fixtures.")
            return str(resp)
        elif result == "expired":
            msg.body("❌ Voucher expired.")
            return str(resp)
        elif result == "used":
            msg.body("❌ Voucher already used.")
            return str(resp)
        else:
            msg.body("🔐 Enter a valid voucher code to access predictions.")
            return str(resp)

    # Fixtures request
    if incoming.lower().startswith("fixtures"):
        parts = incoming.split()
        if len(parts) == 2:
            league = parts[1].lower()
            # Map user input to SportDB slug
            slug_map = {
                "epl": "england/premier-league",
                "la liga": "spain/laliga",
                "serie a": "italy/serie-a",
                "bundesliga": "germany/bundesliga",
                "psl": "south-africa/psl"
            }
            slug = slug_map.get(league)
            if slug:
                fixtures = fetch_live_fixtures(slug)
                msg.body(f"📅 Upcoming {league.upper()} Fixtures:\n" + "\n".join(fixtures))
            else:
                msg.body("❌ League not found.")
        else:
            msg.body("Send like: fixtures EPL")
        return str(resp)

    # High probability predictions
    high_prob = False
    if incoming.lower().startswith("high probability"):
        incoming = incoming.replace("high probability", "").strip()
        high_prob = True

    # Match predictions
    if "vs" in incoming.lower():
        teams_input = incoming.split("vs")
        if len(teams_input) == 2:
            result = predict_match(teams_input[0].strip(), teams_input[1].strip(), high_prob=high_prob)
            msg.body(result)
        else:
            msg.body("❌ Invalid format. Send like: Arsenal vs Liverpool")
    else:
        msg.body("Send a match like:\nArsenal vs Liverpool\nSundowns vs Pirates\nOr request fixtures:\nfixtures EPL")

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
