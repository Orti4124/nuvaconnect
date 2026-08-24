"""Protocolo de mensajería de NuvaConnect.

Dos capas:

1) CONTROL (texto/JSON, entre cliente y relay): sirve para registrarse y
   emparejarse. El relay entiende estos mensajes.

2) APP (binario, extremo a extremo): los mensajes de la aplicación
   (pantalla, input, archivos) se serializan con msgpack, se cifran con la
   clave de sesión y se envían como frames BINARIOS. El relay NO los entiende;
   solo reenvía cualquier frame binario al otro extremo de la sala.

Formato de un mensaje APP (antes de cifrar): un dict msgpack con la clave
"t" (tipo) y campos específicos. `data` puede ser bytes (msgpack lo soporta
de forma nativa, ideal para JPEG y chunks de archivos).
"""
from __future__ import annotations

import json
from typing import Any

import msgpack

# ---------------------------------------------------------------------------
# Tipos de mensajes de CONTROL (relay) — viajan como texto JSON
# ---------------------------------------------------------------------------
C_REGISTER = "register"        # cliente -> relay: unirse a una sala por ID
C_REGISTERED = "registered"    # relay -> cliente: registro OK
C_PEER_JOINED = "peer_joined"  # relay -> cliente: el otro extremo se conectó
C_PEER_LEFT = "peer_left"      # relay -> cliente: el otro extremo se fue
C_ERROR = "error"              # relay -> cliente: error (sala llena, etc.)

ROLE_HOST = "host"
ROLE_VIEWER = "viewer"


def control(msg_type: str, **fields: Any) -> str:
    """Construye un mensaje de control como texto JSON."""
    payload = {"type": msg_type}
    payload.update(fields)
    return json.dumps(payload)


def parse_control(raw: str) -> dict:
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Tipos de mensajes de APP (extremo a extremo, cifrados) — frames binarios
# ---------------------------------------------------------------------------
# Handshake / autenticación
A_AUTH_CHALLENGE = "auth_challenge"  # host -> viewer: reto (nonce) cifrado
A_AUTH_RESPONSE = "auth_response"    # viewer -> host: respuesta al reto (+ firma device)
A_AUTH_OK = "auth_ok"                # host -> viewer: autenticado
A_AUTH_FAIL = "auth_fail"            # host -> viewer: contraseña/factor incorrecto
A_AUTH_2FA_REQUIRED = "auth_2fa"     # host -> viewer: se requiere código TOTP
A_AUTH_2FA_CODE = "auth_2fa_code"    # viewer -> host: código TOTP
A_AUTH_LOCKED = "auth_locked"        # host -> viewer: bloqueado por fuerza bruta
A_AUTH_DENIED = "auth_denied"        # host -> viewer: el usuario del host rechazó

# Pantalla
A_SCREEN_INFO = "screen_info"        # host -> viewer: resolución, monitores
A_FRAME = "frame"                    # host -> viewer: tile/frame JPEG
A_REQUEST_FULL = "request_full"      # viewer -> host: pide frame completo

# Entrada (input)
A_MOUSE_MOVE = "mouse_move"
A_MOUSE_CLICK = "mouse_click"
A_MOUSE_SCROLL = "mouse_scroll"
A_KEY = "key"

# Transferencia de archivos
A_FILE_OFFER = "file_offer"          # emisor -> receptor: metadata del archivo
A_FILE_ACCEPT = "file_accept"        # receptor -> emisor: acepta
A_FILE_CHUNK = "file_chunk"          # emisor -> receptor: un chunk
A_FILE_DONE = "file_done"            # emisor -> receptor: fin del archivo
A_FILE_ERROR = "file_error"

# Control de sesión
A_PING = "ping"
A_PONG = "pong"
A_BYE = "bye"


def pack(msg_type: str, **fields: Any) -> bytes:
    """Serializa un mensaje de app a bytes (msgpack). Aún SIN cifrar."""
    payload = {"t": msg_type}
    payload.update(fields)
    return msgpack.packb(payload, use_bin_type=True)


def unpack(raw: bytes) -> dict:
    """Deserializa un mensaje de app (ya descifrado)."""
    return msgpack.unpackb(raw, raw=False)
