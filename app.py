from flask import Flask, jsonify, request

app = Flask(__name__)

# Message storage
messages = [
    {"sender": "System", "displayName": "System", "text": "Welcome to the Global Script Chat!", "tag": "SYSTEM"}
]

# Your exact Roblox username
OWNER_USER = "the_sagor"
ADMINS = []

@app.route('/messages', methods=['GET'])
def get_messages():
    return jsonify(messages)

@app.route('/send', methods=['POST'])
def send_message():
    data = request.json
    username = data.get("username", "Anonymous")
    displayName = data.get("displayName", "Anonymous")
    text = data.get("text", "")
    
    if not text.strip():
        return jsonify({"status": "error", "message": "Empty text"}), 400
        
    tag = "USER"
    if username == OWNER_USER:
        tag = "👑 OWNER"
    elif username in ADMINS:
        tag = "🛡️ ADMIN"
        
    if text.startswith("/clear") and (username == OWNER_USER or username in ADMINS):
        messages.clear()
        messages.append({"sender": "System", "displayName": "System", "text": f"Chat cleared by {displayName}!", "tag": "SYSTEM"})
        return jsonify({"status": "success"})
        
    messages.append({"sender": username, "displayName": displayName, "text": text, "tag": tag})
    if len(messages) > 50:
        messages.pop(0)
        
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
