"""Módulo de ciberseguridad de NuvaConnect.

Añade sobre el cifrado E2E base varias capas de seguridad de nivel producto:

1. TOTP (2FA)          — segundo factor de tiempo (RFC 6238), sin dependencias.
2. DeviceIdentity      — identidad criptográfica del dispositivo (Ed25519).
3. Allowlist           — lista de dispositivos de confianza (fingerprints).
4. AuditLog            — bitácora de auditoría en JSONL (append-only).
5. BruteForceGuard     — bloqueo tras N intentos fallidos de autenticación.

Todo el estado persistente vive en ~/.nuvaconnect/.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.exceptions import InvalidSignature


# ---------------------------------------------------------------------------
# Rutas de estado
# ---------------------------------------------------------------------------
def state_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".nuvaconnect")
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# 1) TOTP — autenticación de dos factores (RFC 6238), implementado a mano
# ---------------------------------------------------------------------------
class TOTP:
    """Time-based One-Time Password. Compatible con Google Authenticator, Authy,
    Microsoft Authenticator, etc."""

    def __init__(self, secret_b32: str, digits: int = 6, period: int = 30):
        self.secret_b32 = secret_b32
        self.digits = digits
        self.period = period

    @staticmethod
    def new_secret() -> str:
        """Genera un secreto aleatorio en Base32 (20 bytes = 160 bits)."""
        return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")

    def _code_at(self, counter: int) -> str:
        key = base64.b32decode(self.secret_b32 + "=" * (-len(self.secret_b32) % 8))
        msg = struct.pack(">Q", counter)
        digest = hmac.new(key, msg, hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** self.digits)
        return str(code).zfill(self.digits)

    def now(self, at: float | None = None) -> str:
        at = time.time() if at is None else at
        return self._code_at(int(at // self.period))

    def verify(self, code: str, at: float | None = None, window: int = 1) -> bool:
        """Verifica un código permitiendo ±`window` periodos de desfase de reloj."""
        if not code:
            return False
        code = code.strip().replace(" ", "")
        at = time.time() if at is None else at
        counter = int(at // self.period)
        for w in range(-window, window + 1):
            if hmac.compare_digest(self._code_at(counter + w), code):
                return True
        return False

    def provisioning_uri(self, account: str, issuer: str = "NuvaConnect") -> str:
        """URI otpauth:// para generar un QR y escanearlo en la app de 2FA."""
        from urllib.parse import quote
        label = quote(f"{issuer}:{account}")
        return (f"otpauth://totp/{label}?secret={self.secret_b32}"
                f"&issuer={quote(issuer)}&digits={self.digits}&period={self.period}")


# ---------------------------------------------------------------------------
# 2) Identidad de dispositivo (Ed25519)
# ---------------------------------------------------------------------------
class DeviceIdentity:
    """Par de claves Ed25519 persistente que identifica de forma única a este
    dispositivo. Permite que el host verifique criptográficamente QUÉ máquina
    se está conectando (no solo que conoce la contraseña)."""

    def __init__(self, private_key: Ed25519PrivateKey):
        self._priv = private_key
        self._pub = private_key.public_key()

    @classmethod
    def load_or_create(cls, path: str | None = None) -> "DeviceIdentity":
        path = path or os.path.join(state_dir(), "device_key.bin")
        if os.path.exists(path):
            with open(path, "rb") as f:
                priv = Ed25519PrivateKey.from_private_bytes(f.read())
        else:
            priv = Ed25519PrivateKey.generate()
            from cryptography.hazmat.primitives import serialization
            raw = priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(path, "wb") as f:
                f.write(raw)
            try:
                os.chmod(path, 0o600)  # solo el dueño puede leer la clave
            except OSError:
                pass
        return cls(priv)

    def public_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self._pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def fingerprint(self) -> str:
        """Huella legible del dispositivo (SHA-256 de la clave pública)."""
        return hashlib.sha256(self.public_bytes()).hexdigest()[:32]

    def sign(self, data: bytes) -> bytes:
        return self._priv.sign(data)

    @staticmethod
    def verify(public_bytes: bytes, signature: bytes, data: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, data)
            return True
        except (InvalidSignature, ValueError):
            return False

    @staticmethod
    def fingerprint_of(public_bytes: bytes) -> str:
        return hashlib.sha256(public_bytes).hexdigest()[:32]


# ---------------------------------------------------------------------------
# 3) Allowlist de dispositivos de confianza
# ---------------------------------------------------------------------------
class Allowlist:
    """Lista de fingerprints de dispositivos autorizados a controlar este host."""

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(state_dir(), "allowlist.json")
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._data = json.load(f)
            except (OSError, json.JSONDecodeError):
                self._data = {}

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)

    def is_trusted(self, fingerprint: str) -> bool:
        return fingerprint in self._data

    def add(self, fingerprint: str, label: str = ""):
        self._data[fingerprint] = {"label": label, "added": int(time.time())}
        self._save()

    def remove(self, fingerprint: str):
        self._data.pop(fingerprint, None)
        self._save()

    def all(self) -> dict:
        return dict(self._data)


# ---------------------------------------------------------------------------
# 4) Registro de auditoría (append-only, JSONL)
# ---------------------------------------------------------------------------
class AuditLog:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(state_dir(), "audit.log")

    def record(self, event: str, **fields):
        entry = {"ts": int(time.time()), "event": event}
        entry.update(fields)
        line = json.dumps(entry, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return entry

    def tail(self, n: int = 50) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
        return out


# ---------------------------------------------------------------------------
# 5) Protección contra fuerza bruta
# ---------------------------------------------------------------------------
@dataclass
class BruteForceGuard:
    """Bloquea nuevos intentos tras `max_attempts` fallos dentro de `window`
    segundos, durante `lockout` segundos."""
    max_attempts: int = 5
    window: float = 300.0     # 5 min
    lockout: float = 300.0    # 5 min de bloqueo
    _fails: list[float] = field(default_factory=list)
    _locked_until: float = 0.0

    def is_locked(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return now < self._locked_until

    def seconds_left(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        return max(0, int(self._locked_until - now))

    def record_failure(self, now: float | None = None) -> bool:
        """Registra un fallo. Devuelve True si con esto se activa el bloqueo."""
        now = time.time() if now is None else now
        self._fails = [t for t in self._fails if now - t < self.window]
        self._fails.append(now)
        if len(self._fails) >= self.max_attempts:
            self._locked_until = now + self.lockout
            self._fails.clear()
            return True
        return False

    def record_success(self):
        self._fails.clear()
        self._locked_until = 0.0
