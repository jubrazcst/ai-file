import os
import sys
import json
import time
import requests
import websocket
from keep_alive import keep_alive
from openrouter_ai import AIResponder, gateway_loop

status = "online" #online/dnd/idle

GUILD_ID = os.getenv("GUILD_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SELF_MUTE = os.getenv("SELF_MUTE")
SELF_DEAF = os.getenv("SELF_DEAF")

usertoken = os.getenv("TOKEN")
if not usertoken:
  print("[ERROR] Please add a token inside Secrets.")
  sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

validate = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers)
if validate.status_code != 200:
  print("[ERROR] Your token might be invalid. Please check it again.")
  sys.exit()

userinfo = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers).json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]

ai = AIResponder(usertoken, userid)

def joiner(token, status):
    ws = websocket.WebSocket()
    ws.connect('wss://gateway.discord.gg/?v=9&encoding=json')
    start = json.loads(ws.recv())
    heartbeat = start['d']['heartbeat_interval']
    auth = {"op": 2,"d": {"token": token,"properties": {"$os": "Windows 10","$browser": "Google Chrome","$device": "Windows"},"presence": {"status": status,"afk": False}},"s": None,"t": None}
    vc = {"op": 4,"d": {"guild_id": GUILD_ID,"channel_id": CHANNEL_ID,"self_mute": str(SELF_MUTE).lower() == "true","self_deaf": str(SELF_DEAF).lower() == "true"}}
    ws.send(json.dumps(auth))
    # Keep the existing connection alive and receive mention/reply events.
    try:
        gateway_loop(ws, heartbeat, ai, vc)
    finally:
        ws.close()

def run_joiner():
  os.system("clear")
  print(f"Logged in as {username}#{discriminator} ({userid}).")
  while True:
    try:
      joiner(usertoken, status)
    except (websocket.WebSocketException, OSError, ValueError):
      print("[Connection] Disconnected; retrying in 30 seconds.")
    time.sleep(30)

keep_alive()
run_joiner()
