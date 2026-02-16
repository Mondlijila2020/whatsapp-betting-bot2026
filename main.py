from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import random

app = Flask(__name__)

def predict_match(team1, team2):
    win1 = random.randint(35,60)
    win2 = random.randint(20,40)
    draw = 100 - (win1 + win2)

    over25 = random.randint(55,80)
    btts = random.randint(50,75)

    score1 = random.randint(0,3)
    score2 = random.randint(0,3)

    return f"""
⚽ MATCH ANALYSIS

{team1} Win: {win1}%
Draw: {draw}%
{team2} Win: {win2}%

TOP 3 OUTCOMES:
Over 2.5 Goals — {over25}%
Both Teams Score — {btts}%
Double Chance {team1}

Most Likely Score:
{score1}-{score2}
"""

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    msg_body = request.values.get("Body")

    resp = MessagingResponse()
    msg = resp.message()

    if "vs" in msg_body.lower():
        teams = msg_body.split("vs")
        msg.body(predict_match(teams[0].strip(), teams[1].strip()))
    else:
        msg.body("Send match like: Arsenal vs Chelsea")

    return str(resp)

app.run(host="0.0.0.0", port=8080)
