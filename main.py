import os
import time
from flask import Flask, jsonify, request

app = Flask(__name__)

# Permanent in-memory storage for tabs and messages
tabs = {"global": {"name": "global", "display": "Global Lobby"}}
messages = {"global": []}
last_message_times = {}  # Tracks user slow mode cooldowns
active_users = {}  # Tracks online presence

MESSAGE_LIMIT = 200
SLOW_MODE_COOLDOWN = 5.0  # 5 seconds cooldown
MAX_SAVED_MESSAGES = 100  # Keeps the last 100 messages saved per tab


@app.route("/", methods=["GET"])
def home():
  return jsonify({"status": "Server is running!"})


# Get all chat tabs & online count
@app.route("/tabs", methods=["GET"])
def get_tabs():
  current_time = time.time()
  inactive_users = [
      u for u, t in active_users.items() if current_time - t > 20
  ]
  for u in inactive_users:
    del active_users[u]

  tab_list = list(tabs.values())
  return jsonify(
      {"tabs": tab_list, "onlineCount": max(1, len(active_users))}
  )


# Create a new tab (Owner only: username must be "the_sagor")
@app.route("/tabs", methods=["POST"])
def create_tab():
  data = request.json or {}
  username = data.get("username", "")
  tab_name = data.get("tabName", "").strip().lower()
  display_name = data.get("displayName", tab_name)

  if username.lower() != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if not tab_name or tab_name in tabs:
    return jsonify({"error": "Invalid or existing tab name."}), 400

  tabs[tab_name] = {"name": tab_name, "display": display_name}
  if tab_name not in messages:
    messages[tab_name] = []
  return jsonify({"success": True, "tab": tabs[tab_name]})


# Delete a tab (Owner only: username must be "the_sagor")
@app.route("/tabs/<tab_name>", methods=["DELETE"])
def delete_tab(tab_name):
  username = request.args.get("username", "")

  if username.lower() != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if tab_name == "global":
    return jsonify({"error": "Cannot delete the default global tab."}), 400

  if tab_name in tabs:
    del tabs[tab_name]
    if tab_name in messages:
      del messages[tab_name]
    return jsonify({"success": True})

  return jsonify({"error": "Tab not found."}), 404


# Get messages (Returns full history on join, or new messages after 'after')
@app.route("/messages", methods=["GET"])
def get_messages():
  username = request.args.get("username", "")
  if username:
    active_users[username] = time.time()

  tab = request.args.get("tab", "global")
  if tab not in messages:
    messages[tab] = []

  tab_messages = messages[tab]
  after_id = request.args.get("after")

  # If no 'after' ID is provided (e.g. when first joining or switching tabs),
  # send all saved messages so history isn't lost!
  if not after_id:
    return jsonify({"messages": tab_messages})

  filtered = []
  found = False
  for m in tab_messages:
    if found:
      filtered.append(m)
    if str(m.get("id")) == str(after_id):
      found = True

  return jsonify({"messages": filtered})


# Post a message & save it permanently in history
@app.route("/messages", methods=["POST"])
def post_message():
  data = request.json or {}
  tab = data.get("tab", "global")
  username = data.get("username", "Unknown")
  display_name = data.get("displayName", username)
  msg_text = data.get("message", "").strip()

  if not msg_text:
    return jsonify({"error": "Message cannot be empty."}), 400

  active_users[username] = time.time()

  if len(msg_text) > MESSAGE_LIMIT:
    msg_text = msg_text[:MESSAGE_LIMIT]

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

  is_owner = username.lower() == "the_sagor"

  new_msg = {
      "id": str(time.time() * 1000),
      "username": display_name,
      "rawUsername": username,
      "message": msg_text,
      "isOwner": is_owner,
      "timestamp": int(time.time()),
  }

  messages[tab].append(new_msg)

  # Keep up to MAX_SAVED_MESSAGES saved in memory so it doesn't overflow
  if len(messages[tab]) > MAX_SAVED_MESSAGES:
    messages[tab].pop(0)

  return jsonify({"success": True, "message": new_msg})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
