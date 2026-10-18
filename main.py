
import os
import time
import threading
from collections import deque

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Global Community Chat")

API_KEY = os.environ.get("CHAT_API_KEY", "")
OWNER_USER_ID = int(os.environ.get("OWNER_USER_ID", "0"))

lock = threading.Lock()
messages = deque(maxlen=200)
channels = [{"id": "global", "name": "GLOBAL CHAT"}]
next_message_id = 1


class MessageInput(BaseModel):
    user_id: int
    display_name: str = Field(min_length=1, max_length=50)
    text: str = Field(min_length=1, max_length=300)
    channel_id: str = "global"


class ChannelInput(BaseModel):
    name: str = Field(min_length=1, max_length=30)


def check_key(key):
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def check_owner(user_id):
    if not OWNER_USER_ID or user_id != OWNER_USER_ID:
        raise HTTPException(status_code=403, detail="Owner only")


@app.get("/")
def home():
    return {"status": "online", "service": "Global Community Chat"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/channels")
def get_channels(x_chat_key: str = Header(default="")):
    check_key(x_chat_key)
    with lock:
        return {"channels": list(channels)}


@app.get("/messages")
def get_messages(
    after: int = 0,
    channel_id: str = "global",
    x_chat_key: str = Header(default="")
):
    check_key(x_chat_key)
    with lock:
        result = [
            dict(m) for m in messages
            if m["id"] > after
            and m["channel_id"] == channel_id
        ]
    return {"messages": result}


@app.post("/messages")
def send_message(
    data: MessageInput,
    x_chat_key: str = Header(default="")
):
    global next_message_id
    check_key(x_chat_key)

    text = data.text.strip()
    display_name = data.display_name.strip()

    if not text or not display_name:
        raise HTTPException(status_code=400, detail="Empty message")

    with lock:
        if not any(c["id"] == data.channel_id for c in channels):
            raise HTTPException(status_code=404, detail="Channel not found")

        item = {
            "id": next_message_id,
            "user_id": data.user_id,
            "display_name": display_name,
            "text": text,
            "channel_id": data.channel_id,
            "is_owner": data.user_id == OWNER_USER_ID,
            "time": int(time.time())
        }
        next_message_id += 1
        messages.append(item)

    return {"message": item}


@app.post("/channels")
def create_channel(
    data: ChannelInput,
    x_chat_key: str = Header(default=""),
    x_owner_id: int = Header(default=0)
):
    check_key(x_chat_key)
    check_owner(x_owner_id)

    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name required")

    with lock:
        if any(c["name"].casefold() == name.casefold() for c in channels):
            raise HTTPException(status_code=409, detail="Channel exists")

        channel = {
            "id": "channel-" + str(int(time.time() * 1000)),
            "name": name.upper()
        }
        channels.append(channel)

    return {"channel": channel}


@app.delete("/channels/{channel_id}")
def delete_channel(
    channel_id: str,
    x_chat_key: str = Header(default=""),
    x_owner_id: int = Header(default=0)
):
    check_key(x_chat_key)
    check_owner(x_owner_id)

    if channel_id == "global":
        raise HTTPException(status_code=400, detail="Cannot delete default channel")

    with lock:
        global channels
        if not any(c["id"] == channel_id for c in channels):
            raise HTTPException(status_code=404, detail="Channel not found")
        channels = [c for c in channels if c["id"] != channel_id]
        remaining = [m for m in messages if m["channel_id"] != channel_id]
        messages.clear()
        messages.extend(remaining)

    return {"ok": True}
