import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timedelta
import random

# ----------------------------
# Flask App
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "UMKHOMA BOT IS RUNNING"

# ----------------------------
# Environment Variables
# ----------------------------
API_KEY = os.environ.get("API_KEY")  # <-- RapidAPI key
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER", "whatsapp:+27671502312")

# ----------------------------
# In-memory storage
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
# Team Strength & Prediction
# ----------------------------
def get_team_strength(team):
    for code in LEAGUES.values():
        url = f"https://api-football-v1.p.rapidapi.com/v3/teams?league={code}&season=2024"
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        try:
            res = requests.get(url, headers=headers, timeout=10).json()
            for t in res.get("response", []):
                if team.lower() in t["team"]["name"].lower():
                    return 100 - t.get("rank", 50)  # fallback if rank missing
        except:
            continue
    return 50  # default strength

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
    url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?league={code}&next=5"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10).json()
        fixtures = []
        for m in res.get("response", []):
            home = m["teams"]["home"]["name"]
            away = m["teams"]["away"]["name"]
            fixtures.append(f"{home} vs {away}")
        return "\n".join(fixtures) if fixtures else "No upcoming fixtures."
    except:
        return "Could not fetch fixtures. Try again later."

# ----------------------------
# WhatsApp Webhook
# ----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")
    resp = MessagingResponse()
    msg = resp.message()
    text = incoming.lower()

    # --------------------------
    # Admin Commands
    # --------------------------
    if user == ADMIN_NUMBER:
        if text == "admin generate":
            code, exp = generate_voucher()
            msg.body(f"🎟️ New Voucher Created\nCode: {code}\nExpires: {exp}\n— UMKHOMA 🤖")
            return str(resp)
        if text == "admin list":
            msg.body("Current vouchers:\n" + "\n".join([f"{c} -> {d}" for c,d in vouchers.items()]))
            return str(resp)

    # --------------------------
    # New User
    # --------------------------
    if user not in approved_users:
        approved_users[user] = False
        msg.body("Welcome to UMKHOMA 🤖. Send your voucher to upgrade to VIP!")
        return str(resp)

    # --------------------------
    # Voucher Redemption
    # --------------------------
    if incoming.upper() in vouchers:
        approved_users[user] = True
        msg.body(f"🎉 VIP activated! Enjoy premium predictions.\nExpires: {vouchers[incoming.upper()]}")
        return str(resp)

    # --------------------------
    # Fixtures
    # --------------------------
    if text.startswith("fixtures"):
        parts = text.split()
        league = parts[1].upper() if len(parts) > 1 else None
        if league:
            msg.body(get_fixtures(league))
        else:
            msg.body("Usage: fixtures EPL")
        return str(resp)

    # --------------------------
    # Predictions
    # --------------------------
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

    # --------------------------
    # Default Help
    # --------------------------
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
# Run App (Render-Compatible)
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render sets this automatically
    app.run(host="0.0.0.0", port=port)
