"""Agente HOST de NuvaConnect (la máquina que se comparte).

Responsabilidades:
- Generar el ID de sesión + contraseña + salt y mostrarlos al usuario.
- Conectarse al relay y esperar al viewer.
- Handshake de autenticación (verifica que el viewer conoce la contraseña).
- Capturar la pantalla y enviar solo los tiles que cambian (ahorro de ancho
  de banda), codificados en JPEG y cifrados.
- Recibir eventos de mouse/teclado y reproducirlos con pynput.
- Recibir/enviar archivos.

Uso:
    python run_host.py                 # genera credenciales automáticas
    python run_host.py --password 1234 # fija la contraseña
"""
from __future__ import annotations

import argparse
import asyncio
import io
import os
import secrets
import time

import mss
from PIL import Image
from pynput.keyboard import Controller as KbController, Key, KeyCode
from pynput.mouse import Button, Controller as MouseController

from . import config, protocol
from .filetransfer import FileManager
from .transport import Transport
from .security import (
    TOTP, DeviceIdentity, Allowlist, AuditLog, BruteForceGuard, state_dir,
)


# ---------------------------------------------------------------------------
# Utilidades de credenciales
# ---------------------------------------------------------------------------
def _gen_session_id() -> str:
    digits = "".join(secrets.choice("0123456789") for _ in range(config.SESSION_ID_LENGTH))
    return digits


def _gen_password() -> str:
    # Contraseña temporal legible (6 dígitos), como el modo "acceso rápido".
    return "".join(secrets.choice("0123456789") for _ in range(6))


def _pretty_id(session_id: str) -> str:
    # Agrupa de a 3 para lectura: 123 456 789
    return " ".join(session_id[i:i + 3] for i in range(0, len(session_id), 3))


# ---------------------------------------------------------------------------
# Mapeo de teclas especiales (nombre -> pynput Key)
# ---------------------------------------------------------------------------
_SPECIAL_KEYS = {
    "enter": Key.enter, "return": Key.enter, "esc": Key.esc, "escape": Key.esc,
    "backspace": Key.backspace, "tab": Key.tab, "space": Key.space,
    "delete": Key.delete, "up": Key.up, "down": Key.down, "left": Key.left,
    "right": Key.right, "home": Key.home, "end": Key.end,
    "page_up": Key.page_up, "page_down": Key.page_down,
    "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt, "cmd": Key.cmd,
    "caps_lock": Key.caps_lock,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4, "f5": Key.f5,
    "f6": Key.f6, "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10,
    "f11": Key.f11, "f12": Key.f12,
}


class HostAgent:
    def __init__(self, session_id: str, password: str):
        self.session_id = session_id
        self.password = password
        self.transport = Transport(session_id, password, protocol.ROLE_HOST)
        self.mouse = MouseController()
        self.kb = KbController()
        self._authed = False
        self._auth_nonce = secrets.token_bytes(16)
        self._streaming = False
        self._screen_w = 0
        self._screen_h = 0
        # Cache de hashes de tiles para el diff.
        self._tile_hashes: dict[tuple[int, int], int] = {}
        self._need_full = True
        downloads = os.path.join(os.path.expanduser("~"), "NuvaConnect", "Recibidos")
        self.files = FileManager(self.transport, downloads,
                                 on_progress=self._file_progress)

        # --- Ciberseguridad ------------------------------------------------
        self.identity = DeviceIdentity.load_or_create()
        self.allowlist = Allowlist()
        self.audit = AuditLog()
        self.guard = BruteForceGuard(
            max_attempts=config.MAX_AUTH_ATTEMPTS,
            lockout=config.LOCKOUT_SECONDS,
        )
        self.totp = self._load_totp() if config.REQUIRE_2FA else None
        # Estado del handshake en curso
        self._awaiting_2fa = False
        self._pending_fp: str | None = None

    def _load_totp(self) -> TOTP:
        """Carga (o crea) el secreto TOTP persistente del host."""
        path = os.path.join(state_dir(), "totp_secret.txt")
        if os.path.exists(path):
            with open(path) as f:
                secret = f.read().strip()
        else:
            secret = TOTP.new_secret()
            with open(path, "w") as f:
                f.write(secret)
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
        return TOTP(secret)

    # ------------------------------------------------------------------
    async def run(self):
        await self.transport.connect()
        print("\n" + "=" * 48)
        print("  NuvaConnect — HOST listo para conexión")
        print("=" * 48)
        print(f"  ID de sesión : {_pretty_id(self.session_id)}")
        print(f"  Contraseña   : {self.password}")
        print("  Comparte AMBOS datos con quien te dará soporte.")
        print("  El ID es público; la contraseña, por un canal aparte.")
        print("-" * 48)
        print(f"  Fingerprint de este equipo : {self.identity.fingerprint()}")
        print("  Seguridad activa:")
        print(f"    · Cifrado E2E ................. sí")
        print(f"    · Aprobación manual .......... {'sí' if config.REQUIRE_APPROVAL else 'no'}")
        print(f"    · 2FA (TOTP) ................. {'sí' if config.REQUIRE_2FA else 'no'}")
        print(f"    · Allowlist de dispositivos .. {'sí' if config.ENFORCE_ALLOWLIST else 'no'}")
        print(f"    · Anti fuerza bruta .......... {config.MAX_AUTH_ATTEMPTS} intentos")
        if self.totp is not None:
            print("-" * 48)
            print("  2FA habilitado. Escanea este código en tu app de autenticación:")
            print(f"    {self.totp.provisioning_uri(account=self.session_id)}")
        print("=" * 48 + "\n")
        print("Esperando a que se conecte el controlador...\n")
        self.audit.record("host_started", session_id=self.session_id,
                          fingerprint=self.identity.fingerprint())

        capture_task: asyncio.Task | None = None
        async for msg in self.transport.messages():
            ctrl = msg.get("_ctrl")
            if ctrl == protocol.C_PEER_JOINED:
                print("Controlador conectado. Iniciando autenticación...")
                self.audit.record("peer_connected")
                await self._begin_auth()
                continue
            if ctrl == protocol.C_PEER_LEFT:
                print("El controlador se desconectó. Esperando de nuevo...")
                self.audit.record("peer_disconnected", authed=self._authed)
                self._reset_auth_state()
                self._streaming = False
                if capture_task:
                    capture_task.cancel()
                    capture_task = None
                continue
            if ctrl is not None:
                continue

            # Contraseña incorrecta: llegó un frame que no se pudo descifrar.
            if msg.get("_decrypt_error"):
                await self._on_bad_password()
                continue

            # Auditar transferencias de archivos antes de procesarlas.
            self._audit_file_event(msg)
            # Mensajes de aplicación (ya descifrados)
            if self._authed and await self.files.handle(msg):
                continue
            await self._dispatch(msg)

            if self._authed and not self._streaming:
                self._streaming = True
                self._need_full = True
                capture_task = asyncio.create_task(self._capture_loop())

    # ------------------------------------------------------------------
    # Autenticación reforzada (contraseña E2E + firma de dispositivo + 2FA
    # + allowlist + aprobación humana + anti fuerza bruta)
    # ------------------------------------------------------------------
    def _reset_auth_state(self):
        self._authed = False
        self._awaiting_2fa = False
        self._pending_fp = None
        self._auth_nonce = secrets.token_bytes(16)

    async def _begin_auth(self):
        self._reset_auth_state()
        if self.guard.is_locked():
            secs = self.guard.seconds_left()
            print(f"⛔ Conexión bloqueada por fuerza bruta ({secs}s restantes).")
            self.audit.record("auth_blocked", seconds_left=secs)
            await self.transport.send(protocol.A_AUTH_LOCKED, seconds=secs)
            return
        await self.transport.send(
            protocol.A_AUTH_CHALLENGE,
            nonce=self._auth_nonce,
            need_2fa=config.REQUIRE_2FA,
        )

    async def _on_bad_password(self):
        """Se recibió un frame indescifrable => contraseña incorrecta."""
        locked = self.guard.record_failure()
        self.audit.record("bad_password")
        print("⚠ Intento con contraseña incorrecta.")
        if locked:
            print("⛔ Demasiados intentos: sesión bloqueada temporalmente.")
            self.audit.record("lockout_triggered")

    async def _auth_fail(self, reason: str):
        locked = self.guard.record_failure()
        self.audit.record("auth_fail", reason=reason)
        print(f"⚠ Autenticación fallida: {reason}")
        if locked:
            self.audit.record("lockout_triggered")
            await self.transport.send(protocol.A_AUTH_LOCKED,
                                      seconds=self.guard.seconds_left())
        else:
            await self.transport.send(protocol.A_AUTH_FAIL, reason=reason)

    async def _handle_auth_response(self, msg: dict):
        # 1) Verificar el nonce del reto
        if msg.get("nonce") != self._auth_nonce:
            await self._auth_fail("nonce inválido")
            return
        # 2) Verificar la firma de dispositivo sobre el nonce (identidad real)
        device_pub = msg.get("device_pub")
        signature = msg.get("signature")
        if not device_pub or not signature or not DeviceIdentity.verify(
                device_pub, signature, self._auth_nonce):
            await self._auth_fail("firma de dispositivo inválida")
            return
        fp = DeviceIdentity.fingerprint_of(device_pub)
        self._pending_fp = fp
        print(f"  Dispositivo remoto: {fp}"
              f" {'(de confianza)' if self.allowlist.is_trusted(fp) else '(nuevo)'}")

        # 3) Allowlist
        if config.ENFORCE_ALLOWLIST and not self.allowlist.is_trusted(fp):
            if not config.REQUIRE_APPROVAL:
                self.audit.record("device_denied", fingerprint=fp)
                await self.transport.send(protocol.A_AUTH_DENIED,
                                          reason="dispositivo no autorizado")
                print("⛔ Dispositivo no está en la allowlist. Rechazado.")
                return
            # Con aprobación, se decide en el paso de aprobación humana.

        # 4) Segundo factor (2FA)
        if config.REQUIRE_2FA and self.totp is not None:
            self._awaiting_2fa = True
            await self.transport.send(protocol.A_AUTH_2FA_REQUIRED)
            print("  Esperando código 2FA del controlador...")
            return

        await self._finalize_auth()

    async def _handle_2fa(self, msg: dict):
        if not self._awaiting_2fa or self.totp is None:
            return
        code = str(msg.get("code", ""))
        if not self.totp.verify(code):
            self._awaiting_2fa = False
            await self._auth_fail("código 2FA incorrecto")
            return
        self._awaiting_2fa = False
        self.audit.record("2fa_ok", fingerprint=self._pending_fp)
        await self._finalize_auth()

    async def _finalize_auth(self):
        fp = self._pending_fp or "?"
        # Aprobación humana (como el diálogo de TeamViewer)
        if config.REQUIRE_APPROVAL:
            prompt = (f"\n¿Aceptar la conexión del dispositivo {fp}? [s/N]: ")
            answer = (await asyncio.to_thread(input, prompt)).strip().lower()
            if answer not in ("s", "si", "sí", "y", "yes"):
                self.audit.record("session_denied_by_user", fingerprint=fp)
                await self.transport.send(protocol.A_AUTH_DENIED,
                                          reason="el usuario del host rechazó la sesión")
                print("Sesión rechazada por el usuario.")
                return
            # Si aprobó un dispositivo nuevo con allowlist activa, recordarlo.
            if config.ENFORCE_ALLOWLIST and not self.allowlist.is_trusted(fp):
                add = (await asyncio.to_thread(
                    input, "¿Recordar este dispositivo como de confianza? [s/N]: "
                )).strip().lower()
                if add in ("s", "si", "sí", "y", "yes"):
                    self.allowlist.add(fp, label="aprobado interactivamente")
                    print("Dispositivo agregado a la allowlist.")

        self._authed = True
        self.guard.record_success()
        self.audit.record("session_start", fingerprint=fp)
        await self.transport.send(protocol.A_AUTH_OK)
        await self._send_screen_info()
        print("✔ Autenticación correcta. Compartiendo pantalla.")

    async def _dispatch(self, msg: dict):
        mt = msg.get("t")
        if mt == protocol.A_AUTH_RESPONSE:
            await self._handle_auth_response(msg)
            return
        if mt == protocol.A_AUTH_2FA_CODE:
            await self._handle_2fa(msg)
            return
        if not self._authed:
            return  # ignorar todo lo demás hasta autenticar
        if mt == protocol.A_REQUEST_FULL:
            self._need_full = True
        elif mt == protocol.A_MOUSE_MOVE:
            self._do_mouse_move(msg)
        elif mt == protocol.A_MOUSE_CLICK:
            self._do_mouse_click(msg)
        elif mt == protocol.A_MOUSE_SCROLL:
            self._do_mouse_scroll(msg)
        elif mt == protocol.A_KEY:
            self._do_key(msg)
        elif mt == protocol.A_PING:
            await self.transport.send(protocol.A_PONG, ts=msg.get("ts"))

    # ------------------------------------------------------------------
    # Streaming de pantalla (diff por tiles)
    # ------------------------------------------------------------------
    async def _send_screen_info(self):
        with mss.mss() as sct:
            mon = sct.monitors[1]
            self._screen_w = mon["width"]
            self._screen_h = mon["height"]
        await self.transport.send(
            protocol.A_SCREEN_INFO, width=self._screen_w, height=self._screen_h
        )

    async def _capture_loop(self):
        frame_interval = 1.0 / max(1, config.TARGET_FPS)
        try:
            while self._streaming and self.transport.peer_present:
                t0 = time.time()
                tiles = await asyncio.to_thread(self._grab_changed_tiles)
                for (x, y, w, h, jpeg) in tiles:
                    await self.transport.send(
                        protocol.A_FRAME, x=x, y=y, w=w, h=h, data=jpeg
                    )
                dt = time.time() - t0
                await asyncio.sleep(max(0, frame_interval - dt))
        except asyncio.CancelledError:
            pass

    def _grab_changed_tiles(self):
        """Captura la pantalla y devuelve solo los tiles que cambiaron.

        Devuelve lista de (x, y, w, h, jpeg_bytes) en coordenadas de la imagen
        enviada (ya escalada si MAX_SCALE < 1)."""
        with mss.mss() as sct:
            mon = sct.monitors[1]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        if config.MAX_SCALE < 1.0:
            new_size = (int(img.width * config.MAX_SCALE),
                        int(img.height * config.MAX_SCALE))
            img = img.resize(new_size, Image.BILINEAR)

        W, H = img.width, img.height
        ts = config.TILE_SIZE
        changed = []
        full = self._need_full
        self._need_full = False

        for ty in range(0, H, ts):
            for tx in range(0, W, ts):
                box = (tx, ty, min(tx + ts, W), min(ty + ts, H))
                tile = img.crop(box)
                h = hash(tile.tobytes())
                key = (tx, ty)
                if full or self._tile_hashes.get(key) != h:
                    self._tile_hashes[key] = h
                    buf = io.BytesIO()
                    tile.save(buf, format="JPEG", quality=config.JPEG_QUALITY)
                    changed.append((tx, ty, box[2] - tx, box[3] - ty, buf.getvalue()))
        return changed

    # ------------------------------------------------------------------
    # Inyección de input
    # ------------------------------------------------------------------
    def _abs_pos(self, msg: dict):
        # El viewer manda coordenadas normalizadas 0..1 -> mapear a pantalla.
        x = int(msg.get("nx", 0) * self._screen_w)
        y = int(msg.get("ny", 0) * self._screen_h)
        return x, y

    def _do_mouse_move(self, msg):
        self.mouse.position = self._abs_pos(msg)

    def _do_mouse_click(self, msg):
        self.mouse.position = self._abs_pos(msg)
        btn = {"left": Button.left, "right": Button.right,
               "middle": Button.middle}.get(msg.get("button"), Button.left)
        if msg.get("pressed"):
            self.mouse.press(btn)
        else:
            self.mouse.release(btn)

    def _do_mouse_scroll(self, msg):
        self.mouse.scroll(msg.get("dx", 0), msg.get("dy", 0))

    def _do_key(self, msg):
        key = self._resolve_key(msg)
        if key is None:
            return
        try:
            if msg.get("pressed"):
                self.kb.press(key)
            else:
                self.kb.release(key)
        except Exception:
            pass

    def _resolve_key(self, msg):
        name = msg.get("name")
        char = msg.get("char")
        if name and name in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[name]
        if char:
            try:
                return KeyCode.from_char(char)
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    def _audit_file_event(self, msg: dict):
        mt = msg.get("t")
        if mt == protocol.A_FILE_OFFER:
            self.audit.record("file_incoming", name=msg.get("name"),
                              size=msg.get("size"), fingerprint=self._pending_fp)
        elif mt == protocol.A_FILE_DONE:
            self.audit.record("file_completed", fingerprint=self._pending_fp)

    def _file_progress(self, direction, name, done, total):
        pct = (done / total * 100) if total else 0
        arrow = "↓ recibiendo" if direction == "recv" else "↑ enviando"
        print(f"  {arrow} {name}: {pct:5.1f}%", end="\r")
        if done >= total:
            print(f"  {arrow} {name}: completado.            ")


async def _amain():
    parser = argparse.ArgumentParser(description="NuvaConnect Host")
    parser.add_argument("--session-id", help="ID fijo (por defecto se genera)")
    parser.add_argument("--password", help="Contraseña fija (por defecto se genera)")
    args = parser.parse_args()

    session_id = args.session_id or _gen_session_id()
    password = args.password or _gen_password()
    agent = HostAgent(session_id, password)
    try:
        await agent.run()
    except KeyboardInterrupt:
        pass
    finally:
        await agent.transport.close()


def main():
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
