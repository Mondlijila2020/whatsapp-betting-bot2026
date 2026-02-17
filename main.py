import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# ===============================
# ENV VARIABLES
# ===============================
API_KEY = os.environ.get("API_KEY")
ADMIN_NUMBER = "+27671502312"   # ✅ YOUR ADMIN NUMBER

# ===============================
# SAFE API REQUEST FUNCTION
# ===============================
def safe_request(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.json()
        return None
    except:
        return None

# ===============================
# GET MATCH PREDICTION
# ===============================
def get_prediction(team1, team2):
    url = f"https://api-football-v1.p.rapidapi.com/v3/predictions?team={team1}"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }

    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()

        if data["response"]:
            pred = data["response"][0]["predictions"]["winner"]["name"]
            return f"🔮 Prediction:\n{team1} vs {team2}\nWinner: {pred}"
        else:
            return "❌ No prediction available."
    except:
        return "⚠️ Prediction error."

# ===============================
# GET UPCOMING MATCHES
# ===============================
def get_upcoming():
    leagues = {
        "Betway Premiership": 288,
        "Portugal Liga": 94,
        "Turkey Super Lig": 203,
        "Switzerland Super League": 207,
        "USA MLS": 253
    }

    msg = "📅 Upcoming Matches:\n\n"

    for name, league_id in leagues.items():
        url = f"https://api-football-v1.p.rapidapi.com/v3/fixtures?league={league_id}&next=3"
        headers = {
            "X-RapidAPI-Key": API_KEY,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }

        try:
            r = requests.get(url, headers=headers, timeout=15)
            data = r.json()

            msg += f"🏆 {name}\n"

            for game in data["response"]:
                home = game["teams"]["home"]["name"]
                away = game["teams"]["away"]["name"]
                msg += f"{home} vs {away}\n"

            msg += "\n"

        except:
            msg += f"{name} unavailable\n\n"

    return msg

# ===============================
# WEBHOOK ROUTE
# ===============================
@app.route("/", methods=["GET"])
def home():
    return "UMKHOMA BOT IS RUNNING"

@app.route("/bot", methods=["POST"])
def bot():
    try:
        incoming = request.values.get("Body", "").strip()
        sender = request.values.get("From", "")

        resp = MessagingResponse()
        msg = resp.message()

        text = incoming.lower()

        # ===============================
        # COMMANDS
        # ===============================
        if text == "hi":
            msg.body("👋 Welcome to UMKHOMA FREE BOT\n\nCommands:\n• upcoming\n• prediction\n• Team1 vs Team2")

        elif text == "upcoming":
            msg.body(get_upcoming())

        elif text == "prediction":
            msg.body("Send in format:\nTeam1 vs Team2")

        elif " vs " in text:
            teams = incoming.split(" vs ")
            if len(teams) == 2:
                msg.body(get_prediction(teams[0], teams[1]))
            else:
                msg.body("❌ Format must be:\nTeam1 vs Team2")

        else:
            msg.body("❓ Unknown command\nType HI")

        return str(resp)

    except Exception as e:
        print("ERROR:", e)
        r = MessagingResponse()
        r.message("⚠️ An unexpected error occurred! Please try again.")
        return str(r)

# ===============================
# RUN APP
# ===============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
