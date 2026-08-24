"""Servidor relay de NuvaConnect.

Función: emparejar dos clientes (host y viewer) que comparten el mismo ID de
sesión y reenviar entre ellos los frames binarios cifrados. Como todo el
contenido va cifrado extremo a extremo, el relay NUNCA ve pantallas, teclas
ni archivos: solo mueve bytes. Esto permite operar detrás de NAT/firewalls
sin abrir puertos en las máquinas de los usuarios (igual que AnyDesk/TeamViewer).

Arquitectura de salas:
- Cada ID de sesión es una "sala" con capacidad para 2: un host y un viewer.
- El primero en registrarse suele ser el host. Cuando entra el viewer, ambos
  reciben `peer_joined` y comienza el handshake E2E entre ellos.

Ejecutar:
    python server/relay_server.py
Variables de entorno útiles: NUVA_RELAY_HOST, NUVA_RELAY_PORT.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import websockets
from websockets.server import WebSocketServerProtocol

# Permitir ejecutar el archivo directamente (añade la raíz del repo al path)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuvaconnect import config, protocol  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [relay] %(levelname)s %(message)s",
)
log = logging.getLogger("nuvaconnect.relay")


class Room:
    """Una sala de sesión: como mucho un host y un viewer."""

    __slots__ = ("session_id", "host", "viewer")

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.host: WebSocketServerProtocol | None = None
        self.viewer: WebSocketServerProtocol | None = None

    def slot(self, role: str):
        return self.host if role == protocol.ROLE_HOST else self.viewer

    def set(self, role: str, ws):
        if role == protocol.ROLE_HOST:
            self.host = ws
        else:
            self.viewer = ws

    def peer_of(self, ws):
        if ws is self.host:
            return self.viewer
        if ws is self.viewer:
            return self.host
        return None

    def is_empty(self) -> bool:
        return self.host is None and self.viewer is None


class RelayServer:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        # Mapea cada conexión a (session_id, role) para limpieza rápida.
        self.conns: dict[WebSocketServerProtocol, tuple[str, str]] = {}

    async def handler(self, ws: WebSocketServerProtocol):
        peer_ip = ws.remote_address[0] if ws.remote_address else "?"
        log.info("Conexión entrante desde %s", peer_ip)
        try:
            async for message in ws:
                if isinstance(message, str):
                    await self._on_control(ws, message)
                else:
                    await self._on_binary(ws, message)
        except websockets.ConnectionClosed:
            pass
        finally:
            await self._cleanup(ws)

    async def _on_control(self, ws, raw: str):
        try:
            msg = protocol.parse_control(raw)
        except Exception:
            return
        if msg.get("type") == protocol.C_REGISTER:
            await self._register(ws, msg)

    async def _register(self, ws, msg: dict):
        session_id = str(msg.get("session_id", "")).strip()
        role = msg.get("role")
        if not session_id or role not in (protocol.ROLE_HOST, protocol.ROLE_VIEWER):
            await ws.send(protocol.control(protocol.C_ERROR, reason="registro inválido"))
            return

        room = self.rooms.setdefault(session_id, Room(session_id))
        if room.slot(role) is not None:
            await ws.send(
                protocol.control(protocol.C_ERROR, reason=f"ya hay un {role} en esta sesión")
            )
            return

        room.set(role, ws)
        self.conns[ws] = (session_id, role)
        await ws.send(protocol.control(protocol.C_REGISTERED, role=role, session_id=session_id))
        log.info("Registrado %s en sesión %s", role, session_id)

        # Si ya están ambos, notificar a los dos que el emparejamiento está listo.
        peer = room.peer_of(ws)
        if peer is not None:
            await ws.send(protocol.control(protocol.C_PEER_JOINED))
            await peer.send(protocol.control(protocol.C_PEER_JOINED))
            log.info("Sesión %s emparejada (host+viewer).", session_id)

    async def _on_binary(self, ws, data: bytes):
        """Reenvía el frame cifrado al otro extremo de la sala."""
        info = self.conns.get(ws)
        if not info:
            return
        session_id, _ = info
        room = self.rooms.get(session_id)
        if not room:
            return
        peer = room.peer_of(ws)
        if peer is not None:
            try:
                await peer.send(data)
            except websockets.ConnectionClosed:
                pass

    async def _cleanup(self, ws):
        info = self.conns.pop(ws, None)
        if not info:
            return
        session_id, role = info
        room = self.rooms.get(session_id)
        if not room:
            return
        peer = room.peer_of(ws)
        room.set(role, None)
        if peer is not None:
            try:
                await peer.send(protocol.control(protocol.C_PEER_LEFT))
            except websockets.ConnectionClosed:
                pass
        if room.is_empty():
            self.rooms.pop(session_id, None)
        log.info("Desconectado %s de sesión %s", role, session_id)


async def main():
    server = RelayServer()
    log.info("Servidor relay NuvaConnect escuchando en %s:%s", config.RELAY_HOST, config.RELAY_PORT)
    async with websockets.serve(
        server.handler,
        config.RELAY_HOST,
        config.RELAY_PORT,
        max_size=16 * 1024 * 1024,  # frames de pantalla pueden ser grandes
        ping_interval=20,
        ping_timeout=20,
    ):
        await asyncio.Future()  # corre para siempre


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Servidor detenido.")
