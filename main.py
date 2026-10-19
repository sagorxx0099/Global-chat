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

BAD_WORDS = [
    "fuck", "shit", "bitch", "asshole", "dick", "cunt", "pussy",
    "bastard", "nigger", "nigga", "slut", "whore",
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
            return data.get("tabs", {"global": {"name": "global", "display": "Global Lobby"}}), data.get("messages", {"global": []})
    except Exception:
        pass
    return {"global": {"name": "global", "display": "Global Lobby"}}, {"global": []}

def save_cloud_data(tabs_data, messages_data):
    try:
        for tab_name in messages_data:
            if len(messages_data[tab_name]) > 100:
                messages_data[tab_name] = messages_data[tab_name][-100:]
        payload = {"tabs": tabs_data, "messages": messages_data}
        requests.put(JSONBIN_URL, headers=HEADERS, json=payload)
    except Exception:
        pass

tabs, messages = load_cloud_data()
last_message_times = {}
active_users = {}  # username -> {time, displayName, gameName, jobId, placeId}

# Join Requests storage: list of dicts
join_requests = []

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
    inactive_users = [u for u, d in active_users.items() if current_time - d.get("time", 0) > 25]
    for u in inactive_users:
        del active_users[u]
    tab_list = list(tabs.values())
    return jsonify({"tabs": tab_list, "onlineCount": max(1, len(active_users))})


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


@app.route("/profile/<username>", methods=["GET"])
def get_profile(username):
    u_key = username.lower()
    user_data = active_users.get(u_key)
    if not user_data:
        return jsonify({
            "username": username, "displayName": username,
            "game": "Unknown / Offline", "online": False,
            "placeId": None, "jobId": None,
        })
    return jsonify({
        "username": username,
        "displayName": user_data.get("displayName", username),
        "game": user_data.get("gameName", "Roblox Experience"),
        "online": (time.time() - user_data.get("time", 0) < 30),
        "placeId": user_data.get("placeId"),
        "jobId": user_data.get("jobId"),
    })


@app.route("/messages", methods=["GET"])
def get_messages():
    global messages
    username = request.args.get("username", "")
    display_name = request.args.get("displayName", username)
    game_name = request.args.get("game", "Roblox Experience")
    job_id = request.args.get("jobId", "")
    place_id = request.args.get("placeId", "")

    if username:
        active_users[username.lower()] = {
            "time": time.time(),
            "displayName": display_name,
            "gameName": game_name,
            "jobId": job_id,
            "placeId": place_id,
        }

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
    game_name = data.get("game", "Roblox Experience")
    job_id = data.get("jobId", "")
    place_id = data.get("placeId", "")

    if not msg_text:
        return jsonify({"error": "Message cannot be empty."}), 400

    active_users[username.lower()] = {
        "time": time.time(),
        "displayName": display_name,
        "gameName": game_name,
        "jobId": job_id,
        "placeId": place_id,
    }

    if len(msg_text) > MESSAGE_LIMIT:
        msg_text = msg_text[:MESSAGE_LIMIT]
    msg_text = censor_message(msg_text)

    current_time = time.time()
    if username in last_message_times:
        elapsed = current_time - last_message_times[username]
        if elapsed < SLOW_MODE_COOLDOWN:
            remaining = round(SLOW_MODE_COOLDOWN - elapsed, 1)
            return jsonify({"error": f"Slow mode enabled. Please wait {remaining}s."}), 429

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
    if len(messages[tab]) > MAX_SAVED_MESSAGES:
        messages[tab] = messages[tab][-MAX_SAVED_MESSAGES:]
    save_cloud_data(tabs, messages)
    return jsonify({"success": True, "message": new_msg})


# ============================================================
# NEW: Server Info (proxies Roblox API)
# ============================================================
@app.route("/server-info", methods=["GET"])
def get_server_info():
    place_id = request.args.get("placeId", "")
    job_id = request.args.get("jobId", "")
    if not place_id or not job_id:
        return jsonify({"error": "Missing placeId or jobId"}), 400
    try:
        # Roblox public API to list servers for a place
        url = f"https://games.roblox.com/v1/games/{place_id}/servers/0?sortOrder=1&excludeFullGames=false&limit=100"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        if resp.status_code != 200:
            return jsonify({"error": "Failed to fetch server list"}), 502
        data = resp.json()
        for server in data.get("data", []):
            if server.get("id") == job_id:
                return jsonify({
                    "id": server.get("id"),
                    "playing": server.get("playing", 0),
                    "maxPlayers": server.get("maxPlayers", 0),
                    "placeId": place_id,
                })
        return jsonify({"error": "Server not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================
# NEW: Join Request System
# ============================================================
@app.route("/join-request", methods=["POST"])
def create_join_request():
    global join_requests
    data = request.json or {}
    from_user = data.get("from", "")
    to_user = data.get("to", "")
    place_id = data.get("placeId", "")
    job_id = data.get("jobId", "")
    if not from_user or not to_user or not place_id or not job_id:
        return jsonify({"error": "Missing fields"}), 400
    # Optional: check server not full via server-info (skip for brevity)
    req_id = str(time.time() * 1000)
    join_requests.append({
        "id": req_id,
        "from": from_user,
        "to": to_user,
        "placeId": place_id,
        "jobId": job_id,
        "status": "pending",
        "timestamp": time.time(),
    })
    # Keep only last 50 requests
    if len(join_requests) > 50:
        join_requests = join_requests[-50:]
    return jsonify({"success": True, "id": req_id})


@app.route("/join-requests/<username>", methods=["GET"])
def get_join_requests(username):
    pending = [r for r in join_requests if r["to"].lower() == username.lower() and r["status"] == "pending"]
    return jsonify({"requests": pending})


@app.route("/join-request/respond", methods=["POST"])
def respond_join_request():
    global join_requests
    data = request.json or {}
    req_id = data.get("id", "")
    action = data.get("action", "")  # "accept" or "reject"
    for r in join_requests:
        if r["id"] == req_id:
            if action == "accept":
                r["status"] = "accepted"
            elif action == "reject":
                r["status"] = "rejected"
            else:
                return jsonify({"error": "Invalid action"}), 400
            return jsonify({"success": True})
    return jsonify({"error": "Request not found"}), 404


@app.route("/join-request/status/<req_id>", methods=["GET"])
def get_join_request_status(req_id):
    for r in join_requests:
        if r["id"] == req_id:
            return jsonify({"status": r["status"], "placeId": r["placeId"], "jobId": r["jobId"]})
    return jsonify({"error": "Request not found"}), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
