"""Transferencia de archivos por chunks, cifrada extremo a extremo.

Simétrico: tanto el host como el viewer usan `FileManager`. Cualquiera de los
dos puede iniciar un envío con `start_send()`; el otro extremo recibe la
oferta y la va escribiendo a disco. Cada chunk viaja dentro del canal cifrado
del `Transport`, así que la transferencia hereda el cifrado E2E.

Protocolo:
  A_FILE_OFFER  {id, name, size}
  A_FILE_ACCEPT {id}                      (auto: el receptor acepta)
  A_FILE_CHUNK  {id, seq, data}
  A_FILE_DONE   {id}
  A_FILE_ERROR  {id, reason}
"""
from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import config, protocol


@dataclass
class _Incoming:
    file_id: str
    name: str
    size: int
    fh: object
    received: int = 0
    path: str = ""


@dataclass
class _Outgoing:
    file_id: str
    path: str
    size: int
    accepted: asyncio.Event = field(default_factory=asyncio.Event)


class FileManager:
    def __init__(self, transport, download_dir: str,
                 on_progress: Optional[Callable[[str, str, int, int], None]] = None):
        """
        on_progress(direction, name, done, total): callback opcional de UI.
          direction = "recv" | "send"
        """
        self.t = transport
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        self._incoming: dict[str, _Incoming] = {}
        self._outgoing: dict[str, _Outgoing] = {}
        self.on_progress = on_progress

    # ------------------------------------------------------------------
    # Enviar
    # ------------------------------------------------------------------
    async def start_send(self, path: str):
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        file_id = uuid.uuid4().hex
        size = os.path.getsize(path)
        out = _Outgoing(file_id=file_id, path=path, size=size)
        self._outgoing[file_id] = out
        await self.t.send(protocol.A_FILE_OFFER, id=file_id,
                          name=os.path.basename(path), size=size)
        # Espera aceptación (con timeout razonable).
        try:
            await asyncio.wait_for(out.accepted.wait(), timeout=30)
        except asyncio.TimeoutError:
            self._outgoing.pop(file_id, None)
            raise TimeoutError("el otro extremo no aceptó la transferencia")

        seq = 0
        sent = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(config.FILE_CHUNK_SIZE)
                if not chunk:
                    break
                await self.t.send(protocol.A_FILE_CHUNK, id=file_id, seq=seq, data=chunk)
                seq += 1
                sent += len(chunk)
                if self.on_progress:
                    self.on_progress("send", os.path.basename(path), sent, size)
        await self.t.send(protocol.A_FILE_DONE, id=file_id)
        self._outgoing.pop(file_id, None)

    # ------------------------------------------------------------------
    # Manejo de mensajes entrantes (lo llama el loop principal)
    # ------------------------------------------------------------------
    async def handle(self, msg: dict) -> bool:
        """Devuelve True si el mensaje fue de transferencia y se manejó."""
        mt = msg.get("t")
        if mt == protocol.A_FILE_OFFER:
            await self._on_offer(msg)
        elif mt == protocol.A_FILE_ACCEPT:
            self._on_accept(msg)
        elif mt == protocol.A_FILE_CHUNK:
            self._on_chunk(msg)
        elif mt == protocol.A_FILE_DONE:
            self._on_done(msg)
        elif mt == protocol.A_FILE_ERROR:
            self._on_error(msg)
        else:
            return False
        return True

    async def _on_offer(self, msg: dict):
        file_id = msg["id"]
        name = os.path.basename(msg.get("name", "archivo"))
        size = int(msg.get("size", 0))
        dest = self._safe_dest(name)
        inc = _Incoming(file_id=file_id, name=name, size=size,
                        fh=open(dest, "wb"), path=dest)
        self._incoming[file_id] = inc
        await self.t.send(protocol.A_FILE_ACCEPT, id=file_id)

    def _on_accept(self, msg: dict):
        out = self._outgoing.get(msg["id"])
        if out:
            out.accepted.set()

    def _on_chunk(self, msg: dict):
        inc = self._incoming.get(msg["id"])
        if not inc:
            return
        data = msg.get("data", b"")
        inc.fh.write(data)
        inc.received += len(data)
        if self.on_progress:
            self.on_progress("recv", inc.name, inc.received, inc.size)

    def _on_done(self, msg: dict):
        inc = self._incoming.pop(msg["id"], None)
        if inc:
            inc.fh.close()

    def _on_error(self, msg: dict):
        inc = self._incoming.pop(msg.get("id", ""), None)
        if inc:
            inc.fh.close()

    # ------------------------------------------------------------------
    def _safe_dest(self, name: str) -> str:
        """Evita sobrescribir y rutas maliciosas (path traversal)."""
        name = os.path.basename(name) or "archivo"
        base, ext = os.path.splitext(name)
        dest = os.path.join(self.download_dir, name)
        i = 1
        while os.path.exists(dest):
            dest = os.path.join(self.download_dir, f"{base} ({i}){ext}")
            i += 1
        return dest
