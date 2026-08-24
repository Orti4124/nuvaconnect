"""Transporte E2E compartido por host y viewer.

Envuelve la conexión WebSocket al relay y aplica cifrado a cada mensaje de
aplicación. Expone una API sencilla:

    t = Transport(session_id, password, salt, role)
    await t.connect()
    await t.send(protocol.A_PING, ts=...)      # empaqueta, cifra y envía
    async for msg in t.messages():             # recibe, descifra y entrega dicts
        ...

Los eventos de control del relay (peer_joined / peer_left / error) se exponen
como banderas y a través de la cola de mensajes con la clave especial "_ctrl".
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

import websockets

from . import config, protocol
from .crypto import SessionCipher, BadPassword


class Transport:
    def __init__(self, session_id: str, password: str, role: str):
        self.session_id = session_id
        self.role = role
        self.cipher = SessionCipher(password, session_id)
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._peer_present = asyncio.Event()
        self._closed = asyncio.Event()

    # ------------------------------------------------------------------
    async def connect(self):
        url = config.relay_url()
        self._ws = await websockets.connect(url, max_size=16 * 1024 * 1024)
        await self._ws.send(
            protocol.control(
                protocol.C_REGISTER, role=self.role, session_id=self.session_id
            )
        )

    async def wait_peer(self, timeout: Optional[float] = None):
        await asyncio.wait_for(self._peer_present.wait(), timeout=timeout)

    @property
    def peer_present(self) -> bool:
        return self._peer_present.is_set()

    # ------------------------------------------------------------------
    async def send(self, msg_type: str, **fields):
        """Empaqueta, cifra y envía un mensaje de aplicación."""
        if self._ws is None:
            raise RuntimeError("transporte no conectado")
        plaintext = protocol.pack(msg_type, **fields)
        token = self.cipher.encrypt(plaintext)
        await self._ws.send(token)

    async def send_raw_encrypted(self, token: bytes):
        if self._ws is not None:
            await self._ws.send(token)

    def encrypt(self, msg_type: str, **fields) -> bytes:
        """Devuelve el token cifrado sin enviarlo (útil para pre-codificar)."""
        return self.cipher.encrypt(protocol.pack(msg_type, **fields))

    # ------------------------------------------------------------------
    async def messages(self) -> AsyncIterator[dict]:
        """Itera mensajes entrantes.

        - Mensajes de control del relay se entregan como {"_ctrl": <tipo>}.
        - Frames binarios se descifran y se entregan como el dict de la app.
        - Si un frame no descifra (contraseña incorrecta o ruido) se ignora,
          salvo que sea el primer intento de auth (lo maneja el host).
        """
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if isinstance(raw, str):
                    ctrl = protocol.parse_control(raw)
                    ctype = ctrl.get("type")
                    if ctype == protocol.C_PEER_JOINED:
                        self._peer_present.set()
                    elif ctype == protocol.C_PEER_LEFT:
                        self._peer_present.clear()
                    yield {"_ctrl": ctype, **ctrl}
                else:
                    try:
                        plain = self.cipher.decrypt(raw)
                    except BadPassword:
                        yield {"t": protocol.A_AUTH_FAIL, "_decrypt_error": True}
                        continue
                    yield protocol.unpack(plain)
        except websockets.ConnectionClosed:
            pass
        finally:
            self._closed.set()

    async def close(self):
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
