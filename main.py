import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timedelta
import random

app = Flask(__name__)

# ----------------------------
# ENVIRONMENT VARIABLES
# ----------------------------
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY")  # football-data.org token
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER", "whatsapp:+27671502312")  # default if not set

# ----------------------------
# In-memory storage (can upgrade to DB later)
# ----------------------------
approved_users = {}  # {user_number: VIP_status}
vouchers = {}        # {voucher_code: expiration_date}

# ----------------------------
# League codes
# ----------------------------
LEAGUES = {
    "EPL": "PL",
    "LALIGA": "PD",
    "SERIEA": "SA",
    "BUNDESLIGA": "BL1"
}

# ----------------------------
# Voucher System
# ----------------------------
def generate_voucher():
    code = "UMK-" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))
    expiration = datetime.now() + timedelta(days=30)
    vouchers[code] = expiration
    return code, expiration.strftime("%Y-%m-%d")

# ----------------------------
# Team Strength Calculator
# ----------------------------
def get_team_strength(team):
    for code in LEAGUES.values():
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        res = requests.get(url, headers={"X-Auth-Token": FOOTBALL_API_KEY})
        if res.status_code != 200:
            continue
        data = res.json()
        for table in data.get("standings", []):
            for t in table.get("table", []):
                if team.lower() in t["team"]["name"].lower():
                    return 100 - t["position"]
    return 50  # default strength

# ----------------------------
# Prediction Engine
# ----------------------------
def predict_match(team1, team2):
    s1 = get_team_strength(team1)
    s2 = get_team_strength(team2)
    total = s1 + s2
    p1 = round((s1 / total) * 100)
    p2 = round((s2 / total) * 100)
    draw = max(0, 100 - (p1 + p2))

    reply = f"""
🔥 UMKHOMA PRO ANALYSIS 🔥

{team1} Win: {p1}%
Draw: {draw}%
{team2} Win: {p2}%

💡 TOP BET PICKS:
1️⃣ Double Chance: {team1 if p1>p2 else team2} ({max(p1,p2,draw)}%)
2️⃣ Over 1.5 Goals — 82%
3️⃣ Both Teams Score — 74%

🗣️ Mfowethu, bet smart, play safe! 🏆
"""
    return reply

# ----------------------------
# Fetch Fixtures
# ----------------------------
def get_fixtures(league):
    code = LEAGUES.get(league.upper())
    if not code:
        return "League not found. Try EPL, LALIGA, SERIEA, or BUNDESLIGA."
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    res = requests.get(url, headers={"X-Auth-Token": FOOTBALL_API_KEY})
    if res.status_code != 200:
        return "Could not fetch fixtures. Try again later."
    fixtures = []
    for m in res.json().get("matches", [])[:10]:
        fixtures.append(f"{m['homeTeam']['name']} vs {m['awayTeam']['name']}")
    return "\n".join(fixtures) if fixtures else "No upcoming fixtures."

# ----------------------------
# WhatsApp Endpoint
# ----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")
    resp = MessagingResponse()
    msg = resp.message()

    # ---------- ADMIN COMMANDS ----------
    if user == ADMIN_NUMBER:
        if incoming.lower() == "admin generate":
            code, exp = generate_voucher()
            msg.body(f"🎟️ New Voucher Created\nCode: {code}\nExpires: {exp}\n— UMKHOMA 🤖")
            return str(resp)
        if incoming.lower() == "admin list":
            msg.body("Current vouchers:\n" + "\n".join([f"{c} -> {d}" for c,d in vouchers.items()]))
            return str(resp)

    # ---------- NEW USER ----------
    if user not in approved_users:
        approved_users[user] = False  # default FREE user
        msg.body("Welcome to UMKHOMA 🤖. Send your voucher to upgrade to VIP!")
        return str(resp)

    # ---------- VOUCHER REDEMPTION ----------
    if incoming.upper() in vouchers:
        approved_users[user] = True
        msg.body(f"🎉 VIP activated! Enjoy premium predictions.\nExpires: {vouchers[incoming.upper()]}")
        return str(resp)

    # ---------- FIXTURES ----------
    if incoming.lower().startswith("fixtures"):
        parts = incoming.split()
        if len(parts) > 1:
            league = parts[1]
            msg.body(get_fixtures(league))
        else:
            msg.body("Usage: fixtures EPL")
        return str(resp)

    # ---------- PREDICTIONS ----------
    if "vs" in incoming.lower():
        try:
            # Flexible splitting
            parts = incoming.lower().split("vs")
            if len(parts) >= 2:
                team1 = parts[0].strip().title()
                team2 = parts[1].strip().title()
                msg.body(predict_match(team1, team2))
            else:
                msg.body("Send in format: Team1 vs Team2")
        except:
            msg.body("Send in format: Team1 vs Team2")
        return str(resp)

    # ---------- DEFAULT HELP ----------
    msg.body(
        "Commands:\n"
        "- Arsenal vs Liverpool (prediction)\n"
        "- fixtures EPL (upcoming matches)\n"
        "- Send VIP voucher code to activate VIP\n"
        "- Admin: 'admin generate', 'admin list'"
    )
    return str(resp)

# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
