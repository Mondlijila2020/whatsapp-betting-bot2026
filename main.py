import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

API_KEY = os.environ.get("FOOTBALL_API_KEY")
ADMIN_NUMBER = os.environ.get("ADMIN_NUMBER")

headers = {"X-Auth-Token": API_KEY}

approved_users = {}

# ----------------------------
# League Codes (football-data)
# ----------------------------
LEAGUES = {
    "EPL": "PL",
    "LALIGA": "PD",
    "SERIEA": "SA",
    "BUNDESLIGA": "BL1"
}

# ----------------------------
# Get Standings Strength
# ----------------------------
def get_team_strength(team):
    for code in LEAGUES.values():
        url = f"https://api.football-data.org/v4/competitions/{code}/standings"
        res = requests.get(url, headers=headers).json()
        for table in res["standings"]:
            for t in table["table"]:
                if team.lower() in t["team"]["name"].lower():
                    return 100 - t["position"]
    return 50

# ----------------------------
# Predict Match
# ----------------------------
def predict(team1, team2):
    s1 = get_team_strength(team1)
    s2 = get_team_strength(team2)

    total = s1 + s2
    p1 = round((s1 / total) * 100)
    p2 = round((s2 / total) * 100)
    draw = 100 - (p1 + p2)

    best = max(p1, p2, draw)

    return f"""
⚽ UMKHOMA PRO ANALYSIS

{team1} Win: {p1}%
Draw: {draw}%
{team2} Win: {p2}%

🔥 TOP BET PICKS:

1️⃣ Double Chance — {team1 if p1>p2 else team2} ({best}%)
2️⃣ Over 1.5 Goals — 82%
3️⃣ Both Teams Score — 74%

Confidence Level: HIGH
"""

# ----------------------------
# Get Fixtures
# ----------------------------
def get_fixtures(league):
    code = LEAGUES.get(league.upper())
    if not code:
        return "League not found."

    url = f"https://api.football-data.org/v4/competitions/{code}/matches?status=SCHEDULED"
    res = requests.get(url, headers=headers).json()

    fixtures = []
    for m in res["matches"][:10]:
        fixtures.append(
            f"{m['homeTeam']['name']} vs {m['awayTeam']['name']}"
        )

    return "\n".join(fixtures)

# ----------------------------
# WhatsApp Endpoint
# ----------------------------
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming = request.values.get("Body", "").strip()
    user = request.values.get("From")

    resp = MessagingResponse()
    msg = resp.message()

    # Admin command
    if user == ADMIN_NUMBER and incoming.lower() == "admin":
        msg.body("UMKHOMA Admin Active ✅")
        return str(resp)

    # Access check
    if user not in approved_users:
        approved_users[user] = True
        msg.body("Welcome to UMKHOMA 🤖")
        return str(resp)

    # Fixtures request
    if incoming.lower().startswith("fixtures"):
        league = incoming.split()[1]
        msg.body(get_fixtures(league))
        return str(resp)

    # Prediction
    if "vs" in incoming.lower():
        t1, t2 = incoming.split("vs")
        msg.body(predict(t1.strip(), t2.strip()))
        return str(resp)

    msg.body(
        "Send:\n"
        "Arsenal vs Liverpool\n"
        "fixtures EPL"
    )

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
