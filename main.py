import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory storage for tabs, messages, and slow mode cooldowns
tabs = {"global": {"name": "global", "display": "Global Lobby"}}
messages = {"global": []}
last_message_times = {}  # Tracks user slow mode cooldowns (username -> timestamp)

MESSAGE_LIMIT = 200
SLOW_MODE_COOLDOWN = 5.0  # 5 seconds cooldown


@app.route("/", methods=["GET"])
def home():
  return jsonify({"status": "Server is running!"})


# Get all chat tabs
@app.route("/tabs", methods=["GET"])
def get_tabs():
  tab_list = list(tabs.values())
  return jsonify({"tabs": tab_list})


# Create a new tab (Owner only: username must be "the_sagor")
@app.route("/tabs", methods=["POST"])
def create_tab():
  data = request.json or {}
  username = data.get("username", "")
  tab_name = data.get("tabName", "").strip().lower()
  display_name = data.get("displayName", tab_name)

  if username != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if not tab_name or tab_name in tabs:
    return jsonify({"error": "Invalid or existing tab name."}), 400

  tabs[tab_name] = {"name": tab_name, "display": display_name}
  messages[tab_name] = []
  return jsonify({"success": True, "tab": tabs[tab_name]})


# Delete a tab (Owner only: username must be "the_sagor")
@app.route("/tabs/<tab_name>", methods=["DELETE"])
def delete_tab(tab_name):
  username = request.args.get("username", "")

  if username != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if tab_name == "global":
    return jsonify({"error": "Cannot delete the default global tab."}), 400

  if tab_name in tabs:
    del tabs[tab_name]
    if tab_name in messages:
      del messages[tab_name]
    return jsonify({"success": True})

  return jsonify({"error": "Tab not found."}), 404


# Get messages for a specific tab
@app.route("/messages", methods=["GET"])
def get_messages():
  tab = request.args.get("tab", "global")
  if tab not in messages:
    messages[tab] = []

  tab_messages = messages[tab]
  after_id = request.args.get("after")

  if after_id:
    filtered = []
    found = False
    for m in tab_messages:
      if found:
        filtered.append(m)
      if str(m.get("id")) == str(after_id):
        found = True
    if not found and not tab_messages:
      filtered = tab_messages
    return jsonify({"messages": filtered})

  return jsonify({"messages": tab_messages})


# Post a message (Enforces character limit, slow mode, owner tag, and display names)
@app.route("/messages", methods=["POST"])
def post_message():
  data = request.json or {}
  tab = data.get("tab", "global")
  username = data.get("username", "Unknown")  # Real username for owner check
  display_name = data.get("displayName", username)  # Roblox Display Name
  msg_text = data.get("message", "").strip()

  if not msg_text:
    return jsonify({"error": "Message cannot be empty."}), 400

  # 6. Character limit: 200 characters maximum
  if len(msg_text) > MESSAGE_LIMIT:
    msg_text = msg_text[:MESSAGE_LIMIT]

  # 7. Slow mode: 5-second cooldown per user
  current_time = time.time()
  if username in last_message_times:
    elapsed = current_time - last_message_times[username]
    if elapsed < SLOW_MODE_COOLDOWN:
      remaining = round(SLOW_MODE_COOLDOWN - elapsed, 1)
      return (
          jsonify({
              "error": f"Slow mode enabled. Please wait {remaining}s."
          }),
          429,
      )

  last_message_times[username] = current_time

  if tab not in messages:
    messages[tab] = []

  # 2. Owner tag detection for username "the_sagor"
  is_owner = username.lower() == "the_sagor"

  new_msg = {
      "id": str(time.time() * 1000),
      "username": display_name,  # 3. Show Roblox display name
      "rawUsername": username,
      "message": msg_text,
      "isOwner": is_owner,  # 2. Owner tag flag
      "timestamp": int(time.time()),
  }

  messages[tab].append(new_msg)
  if len(messages[tab]) > 150:
    messages[tab].pop(0)

  return jsonify({"success": True, "message": new_msg})

import os

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
  
      
