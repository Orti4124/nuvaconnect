"""Cifrado extremo a extremo para NuvaConnect.

Modelo de seguridad
-------------------
- El host genera un ID de sesión (público, se comparte para conectar) y una
  contraseña de sesión (secreta, se comparte por un canal aparte).
- La clave simétrica se DERIVA de la contraseña con PBKDF2 + un salt que
  viaja con el ID. Ni el servidor relay ni un atacante en la red ven la
  contraseña ni el contenido: el relay solo reenvía bytes cifrados.
- Autenticación: el host manda un reto (nonce) cifrado; el viewer debe
  devolverlo cifrado correctamente. Si la contraseña es incorrecta, la
  descifrado falla y el host cierra la sesión.

Para el prototipo usamos Fernet (AES-128-CBC + HMAC-SHA256), que ya incluye
autenticación de mensajes. En producción se recomienda migrar a un
handshake tipo Noise/libsodium con claves efímeras (forward secrecy).
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from . import config

# "Pepper" fijo de la app: se combina con el ID de sesión para el salt. Un salt
# no necesita ser secreto, solo único por sesión; derivarlo del ID evita tener
# que transmitirlo antes de establecer el cifrado.
_APP_PEPPER = b"nuvaconnect.v1"


class SessionCipher:
    """Cifra/descifra los mensajes de una sesión con una clave derivada de la
    contraseña compartida y del ID de sesión (usado como salt)."""

    def __init__(self, password: str, session_id: str):
        salt = self._salt_for(session_id)
        self._fernet = Fernet(self._derive_key(password, salt))

    @staticmethod
    def _salt_for(session_id: str) -> bytes:
        return hashlib.sha256(_APP_PEPPER + session_id.encode("utf-8")).digest()[:16]

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=config.KDF_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def encrypt(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt(self, token: bytes) -> bytes:
        """Lanza InvalidToken si la contraseña/clave no coincide."""
        return self._fernet.decrypt(token)


# Re-exportamos la excepción para que host/viewer no importen cryptography.
BadPassword = InvalidToken
