import os
import time
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

BIN_ID = "6ad5e140ac6210605a3e42e3"
MASTER_KEY = "$2a$10$UCtiBKkVUgl0HFVAffaIG.hnfbL0FDEPi.nRcfJbPbGIs2smtPOXy"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": MASTER_KEY,
}

# Bad word list to filter out
BAD_WORDS = [
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "dick",
    "cunt",
    "pussy",
    "bastard",
    "nigger",
    "nigga",
    "slut",
    "whore",
]


def censor_message(text):
  words = text.split()
  censored_words = []
  for w in words:
    clean_w = "".join([c for c in w if c.isalnum()]).lower()
    if clean_w in BAD_WORDS:
      censored_words.append("*" * len(w))
    else:
      censored_words.append(w)
  return " ".join(censored_words)


def load_cloud_data():
  try:
    res = requests.get(JSONBIN_URL, headers=HEADERS)
    if res.status_code == 200:
      data = res.json().get("record", {})
      return data.get(
          "tabs", {"global": {"name": "global", "display": "Global Lobby"}}
      ), data.get("messages", {"global": []})
  except Exception:
    pass
  return {"global": {"name": "global", "display": "Global Lobby"}}, {
      "global": []
  }


def save_cloud_data(tabs_data, messages_data):
  try:
    # Ensure strict 100-message limit per tab before saving to bin
    for tab_name in messages_data:
      if len(messages_data[tab_name]) > 100:
        messages_data[tab_name] = messages_data[tab_name][-100:]

    payload = {"tabs": tabs_data, "messages": messages_data}
    requests.put(JSONBIN_URL, headers=HEADERS, json=payload)
  except Exception:
    pass


tabs, messages = load_cloud_data()
last_message_times = {}
active_users = {}

MESSAGE_LIMIT = 200
SLOW_MODE_COOLDOWN = 5.0
MAX_SAVED_MESSAGES = 100


@app.route("/", methods=["GET"])
def home():
  return jsonify({"status": "Server is running smoothly!"})


@app.route("/tabs", methods=["GET"])
def get_tabs():
  global tabs, messages
  tabs, messages = load_cloud_data()

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


@app.route("/tabs", methods=["POST"])
def create_tab():
  global tabs, messages
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

  save_cloud_data(tabs, messages)
  return jsonify({"success": True, "tab": tabs[tab_name]})


@app.route("/tabs/<tab_name>", methods=["DELETE"])
def delete_tab(tab_name):
  global tabs, messages
  username = request.args.get("username", "")

  if username.lower() != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if tab_name == "global":
    return jsonify({"error": "Cannot delete the default global tab."}), 400

  if tab_name in tabs:
    del tabs[tab_name]
    if tab_name in messages:
      del messages[tab_name]

    save_cloud_data(tabs, messages)
    return jsonify({"success": True})

  return jsonify({"error": "Tab not found."}), 404


# Owner endpoint to clear messages in a tab
@app.route("/messages/clear", methods=["POST"])
def clear_messages():
  global messages
  data = request.json or {}
  username = data.get("username", "")
  tab = data.get("tab", "global")

  if username.lower() != "the_sagor":
    return jsonify({"error": "Unauthorized. Owner only."}), 403

  if tab in messages:
    messages[tab] = []
    save_cloud_data(tabs, messages)
    return jsonify({"success": True})

  return jsonify({"error": "Tab not found."}), 404


@app.route("/messages", methods=["GET"])
def get_messages():
  global messages
  username = request.args.get("username", "")
  if username:
    active_users[username] = time.time()

  tab = request.args.get("tab", "global")
  if tab not in messages:
    messages[tab] = []

  tab_messages = messages[tab]
  after_id = request.args.get("after")

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


@app.route("/messages", methods=["POST"])
def post_message():
  global messages
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

  # Apply bad word censor
  msg_text = censor_message(msg_text)

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

  # Strictly keep max 100 messages
  if len(messages[tab]) > MAX_SAVED_MESSAGES:
    messages[tab] = messages[tab][-MAX_SAVED_MESSAGES:]

  save_cloud_data(tabs, messages)
  return jsonify({"success": True, "message": new_msg})


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)
