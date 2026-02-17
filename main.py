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
FOOTBALL_API_KEY = os.environ.get("b48a24d06c2c4b42a4aa56d12e9a6199")
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER", "whatsapp:+27671502312")

# ----------------------------
# In-memory storage (upgrade to DB if needed)
# ----------------------------
approved_users = {}  # {user_number: VIP_status}
vouchers = {}        # {voucher_code: expiration_date}

# ----------------------------
# League codes (must match your API)
# ----------------------------
LEAGUES = {
    "EPL": "PL",
    "LALIGA": "PD",
    "SERIEA": "SA",
    "BUNDESLIGA": "BL1",
    "BETWAY": "SA-PREM",
    "PORTUGAL": "PPL",
    "TURKEY": "TUR",
    "SWITZERLAND": "SWI",
    "MLS": "USA-MLS"
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
        try:
            res = requests.get(url, headers={"X-Auth-Token": FOOTBALL_API_KEY}, timeout=10)
            data = res.json()
            for table in data.get("standings", []):
                for t in table.get("table", []):
                    if team.lower() in t["team"]["name"].lower():
                        return 100 - t["position"]
        except:
            continue
    return 50  # default strength if not found

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

    return f"""
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

# ----------------------------
# Fetch Fixtures
# ----------------------------
def get_fixtures(league):
    code = LEAGUES.get(league.upper())
    if not code:
        return "League not found. Try EPL, LALIGA, SERIEA, BUNDESLIGA, BETWAY, PORTUGAL, TURKEY, SWITZERLAND, MLS."
    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    try:
        res = requests.get(url, headers={"X-Auth-Token": FOOTBALL_API_KEY}, timeout=10)
        fixtures = []
        for m in res.json().get("matches", [])[:10]:
            fixtures.append(f"{m['homeTeam']['name']} vs {m['awayTeam']['name']}")
        return "\n".join(fixtures) if fixtures else "No upcoming fixtures."
    except:
        return "Could not fetch fixtures. Try again later."

# ----------------------------
# WhatsApp Endpoint
# ----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")
    print(f"[DEBUG] Incoming from {user}: {incoming}")  # logs for debugging
    resp = MessagingResponse()
    msg = resp.message()

    text = incoming.lower().strip()

    # ---------- ADMIN COMMANDS ----------
    if user == ADMIN_NUMBER:
        if text == "admin generate":
            code, exp = generate_voucher()
            msg.body(f"🎟️ New Voucher Created\nCode: {code}\nExpires: {exp}\n— UMKHOMA 🤖")
            return str(resp)
        if text == "admin list":
            msg.body("Current vouchers:\n" + "\n".join([f"{c} -> {d}" for c,d in vouchers.items()]))
            return str(resp)

    # ---------- NEW USER ----------
    if user not in approved_users:
        approved_users[user] = False
        msg.body("Welcome to UMKHOMA 🤖. Send your voucher to upgrade to VIP!")
        return str(resp)

    # ---------- VOUCHER REDEMPTION ----------
    if incoming.upper() in vouchers:
        approved_users[user] = True
        msg.body(f"🎉 VIP activated! Enjoy premium predictions.\nExpires: {vouchers[incoming.upper()]}")
        return str(resp)

    # ---------- FIXTURES ----------
    if text.startswith("fixtures"):
        parts = text.split()
        league = parts[1].upper() if len(parts) > 1 else None
        if league:
            msg.body(get_fixtures(league))
        else:
            msg.body("Usage: fixtures EPL")
        return str(resp)

    # ---------- PREDICTIONS ----------
    if "vs" in text:
        try:
            parts = text.split("vs")
            if len(parts) >= 2:
                team1 = parts[0].strip().title()
                team2 = parts[1].strip().title()
                msg.body(predict_match(team1, team2))
            else:
                msg.body("Send in format: Team1 vs Team2")
        except Exception as e:
            msg.body(f"Send in format: Team1 vs Team2\nError: {str(e)}")
        return str(resp)

    # ---------- DEFAULT HELP ----------
    msg.body(
        "Commands:\n"
        "- Team1 vs Team2 (prediction)\n"
        "- fixtures LEAGUE (upcoming matches)\n"
        "- Send VIP voucher code to activate VIP\n"
        "- Admin: 'admin generate', 'admin list'\n"
        "Supported leagues: EPL, LALIGA, SERIEA, BUNDESLIGA, BETWAY, PORTUGAL, TURKEY, SWITZERLAND, MLS"
    )
    return str(resp)

# ----------------------------
# RUN APP (Render-Compatible)
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Render sets this automatically
    app.run(host="0.0.0.0", port=port)
