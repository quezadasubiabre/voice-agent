from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import asyncio
import json

app = FastAPI()

from fastapi.responses import FileResponse

@app.get("/")
async def get():
    return FileResponse("walkie-talkie/walkie_talkie.html")


class AudioRoom:
    def __init__(self):
        self.clients: List[WebSocket] = []
        self.callsigns: dict[WebSocket, str] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.append(ws)
        print(f"Client connected. Total: {len(self.clients)}")

    async def disconnect(self, ws: WebSocket):
        callsign = self.callsigns.pop(ws, None)
        if ws in self.clients:
            self.clients.remove(ws)
        print(f"Client disconnected ({callsign}). Total: {len(self.clients)}")
        if callsign:
            await self.broadcast_event(ws, json.dumps({"type": "leave", "callsign": callsign}))

    async def broadcast_audio(self, sender: WebSocket, data: bytes):
        """Send audio to everyone except the sender."""
        dead = []
        for client in self.clients:
            if client is sender:
                continue
            try:
                await client.send_bytes(data)
            except Exception:
                dead.append(client)
        for d in dead:
            if d in self.clients:
                self.clients.remove(d)
            self.callsigns.pop(d, None)

    async def broadcast_event(self, sender: WebSocket, msg: str):
        """Send a text event to everyone except the sender."""
        dead = []
        for client in self.clients:
            if client is sender:
                continue
            try:
                await client.send_text(msg)
            except Exception:
                dead.append(client)
        for d in dead:
            if d in self.clients:
                self.clients.remove(d)
            self.callsigns.pop(d, None)

room = AudioRoom()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await room.connect(ws)
    try:
        while True:
            msg = await ws.receive()

            if msg["type"] == "websocket.receive":
                if "bytes" in msg and msg["bytes"]:
                    await room.broadcast_audio(ws, msg["bytes"])
                elif "text" in msg and msg["text"]:
                    # track callsign from join messages
                    try:
                        data = json.loads(msg["text"])
                        if data.get("type") == "join":
                            room.callsigns[ws] = data.get("callsign", "ANON")
                    except Exception:
                        pass
                    await room.broadcast_event(ws, msg["text"])

    except WebSocketDisconnect:
        await room.disconnect(ws)