"""
Chat éphémère — Backend FastAPI + WebSockets
Aucun stockage. Messages en mémoire uniquement.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json
import os

app = FastAPI()

# ─── État en mémoire (éphémère) ───────────────────────────────────────────────
# { pseudo: WebSocket }
connected_users: dict[str, WebSocket] = {}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def broadcast_user_list():
    """Envoie la liste des connectés à tous."""
    msg = json.dumps({
        "type": "user_list",
        "users": list(connected_users.keys())
    })
    for ws in connected_users.values():
        try:
            await ws.send_text(msg)
        except Exception:
            pass


async def send_to(pseudo: str, payload: dict):
    """Envoie un message à un utilisateur précis."""
    ws = connected_users.get(pseudo)
    if ws:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            pass


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.websocket("/ws/{pseudo}")
async def websocket_endpoint(websocket: WebSocket, pseudo: str):
    pseudo = pseudo.strip()[:32]  # max 32 caractères

    # Refus si pseudo déjà pris
    if pseudo in connected_users:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Ce pseudo est déjà utilisé."
        }))
        await websocket.close()
        return

    await websocket.accept()
    connected_users[pseudo] = websocket

    # Notifier tout le monde
    await broadcast_user_list()
    await send_to(pseudo, {
        "type": "system",
        "message": f"Bienvenue, {pseudo} !"
    })

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "private":
                dest = data.get("to", "").strip()
                text = data.get("text", "").strip()

                if not text:
                    continue

                if dest not in connected_users:
                    await send_to(pseudo, {
                        "type": "error",
                        "message": f"'{dest}' n'est plus connecté."
                    })
                    continue

                # Livrer au destinataire
                await send_to(dest, {
                    "type": "message",
                    "from": pseudo,
                    "to": dest,
                    "text": text
                })

                # Copie à l'expéditeur (confirmation)
                await send_to(pseudo, {
                    "type": "message_sent",
                    "from": pseudo,
                    "to": dest,
                    "text": text
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        connected_users.pop(pseudo, None)
        await broadcast_user_list()
