"""
Chat éphémère — Backend FastAPI + WebSockets
Aucun stockage disque. Messages et fichiers en mémoire uniquement.
"""

import asyncio
import json
import os
import uuid
from urllib.parse import quote, unquote

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

app = FastAPI()

# ─── Configuration ─────────────────────────────────────────────────────────────
MAX_FILE_SIZE = 50 * 1024 * 1024       # 50 Mo
FILE_EXPIRY_SECONDS = 15 * 60          # 15 minutes si jamais téléchargé

# ─── État en mémoire (éphémère) ────────────────────────────────────────────────
# { pseudo: WebSocket }
connected_users: dict[str, WebSocket] = {}

# Fichiers en transit, gardés en RAM uniquement, jamais écrits sur disque.
# { transfer_id: {"from", "to", "filename", "size", "content_type", "data"} }
pending_files: dict[str, dict] = {}
pending_file_tasks: dict[str, asyncio.Task] = {}


# ─── Helpers WebSocket ──────────────────────────────────────────────────────────

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


def _purge_transfer(transfer_id: str):
    """Retire un transfert de la mémoire et annule sa tâche d'expiration."""
    pending_files.pop(transfer_id, None)
    task = pending_file_tasks.pop(transfer_id, None)
    if task:
        task.cancel()


async def _purge_user_transfers(pseudo: str):
    """À la déconnexion d'un utilisateur, retire tout fichier qui le concerne
    et prévient l'autre partie que le transfert est annulé."""
    involved = [tid for tid, f in pending_files.items()
                if f["from"] == pseudo or f["to"] == pseudo]
    for tid in involved:
        entry = pending_files.get(tid)
        other = entry["to"] if entry and entry["from"] == pseudo else (entry["from"] if entry else None)
        _purge_transfer(tid)
        if other:
            await send_to(other, {"type": "file_expired", "transfer_id": tid})


# ─── Routes HTTP ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.post("/upload")
async def upload_file(request: Request):
    """
    Reçoit un fichier en corps brut (pas de multipart), entièrement en mémoire.
    Query params : from=<pseudo expéditeur>, to=<pseudo destinataire>, filename=<nom encodé>
    """
    frm = request.query_params.get("from", "").strip()[:32]
    to = request.query_params.get("to", "").strip()[:32]
    filename = unquote(request.query_params.get("filename", "fichier"))[:255]
    content_type = request.headers.get("content-type") or "application/octet-stream"

    if frm not in connected_users:
        raise HTTPException(401, "Vous n'êtes plus connecté.")
    if to not in connected_users:
        raise HTTPException(404, f"'{to}' n'est plus connecté.")

    # Lecture en flux avec plafond strict — jamais de fichier temporaire sur disque.
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_FILE_SIZE:
            raise HTTPException(
                413, f"Fichier trop volumineux (max {MAX_FILE_SIZE // (1024 * 1024)} Mo)."
            )
        chunks.append(chunk)
    data = b"".join(chunks)

    if total == 0:
        raise HTTPException(400, "Fichier vide.")

    transfer_id = uuid.uuid4().hex
    pending_files[transfer_id] = {
        "from": frm,
        "to": to,
        "filename": filename,
        "size": total,
        "content_type": content_type,
        "data": data,
    }

    async def expire():
        try:
            await asyncio.sleep(FILE_EXPIRY_SECONDS)
        except asyncio.CancelledError:
            return
        if pending_files.pop(transfer_id, None):
            pending_file_tasks.pop(transfer_id, None)
            await send_to(to, {"type": "file_expired", "transfer_id": transfer_id})
            await send_to(frm, {"type": "file_expired", "transfer_id": transfer_id})

    pending_file_tasks[transfer_id] = asyncio.create_task(expire())

    # Notifier le destinataire
    await send_to(to, {
        "type": "file",
        "from": frm,
        "to": to,
        "transfer_id": transfer_id,
        "filename": filename,
        "size": total,
    })
    # Confirmer à l'expéditeur
    await send_to(frm, {
        "type": "file_sent",
        "from": frm,
        "to": to,
        "transfer_id": transfer_id,
        "filename": filename,
        "size": total,
    })

    return {"transfer_id": transfer_id}


@app.get("/download/{transfer_id}")
async def download_file(transfer_id: str):
    """Téléchargement à usage unique — le fichier est retiré de la mémoire
    dès qu'il est servi."""
    entry = pending_files.pop(transfer_id, None)
    if not entry:
        raise HTTPException(404, "Ce fichier n'est plus disponible (expiré ou déjà téléchargé).")

    task = pending_file_tasks.pop(transfer_id, None)
    if task:
        task.cancel()

    filename = entry["filename"]
    data = entry["data"]
    content_type = entry["content_type"]

    ascii_fallback = filename.encode("ascii", "ignore").decode() or "fichier"
    disposition = f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"

    # Prévenir les deux parties que le transfert est terminé
    await send_to(entry["to"], {"type": "file_expired", "transfer_id": transfer_id})
    await send_to(entry["from"], {
        "type": "file_downloaded",
        "transfer_id": transfer_id,
        "by": entry["to"],
    })

    return Response(content=data, media_type=content_type, headers={"Content-Disposition": disposition})


# ─── WebSocket ──────────────────────────────────────────────────────────────────

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
        await _purge_user_transfers(pseudo)
        await broadcast_user_list()
