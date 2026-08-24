"""Viewer / Controlador de NuvaConnect (GUI de escritorio, PyQt6).

Muestra la pantalla remota, captura mouse y teclado y los envía al host, y
permite transferir archivos. La parte de red (asyncio) corre en un hilo
aparte; la comunicación con la GUI se hace con señales de Qt.

Uso:
    python run_viewer.py
"""
from __future__ import annotations

import asyncio
import os
import threading
import time

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPainter, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel, QFileDialog, QToolBar, QStatusBar, QMessageBox,
    QVBoxLayout,
)

from . import config, protocol
from .filetransfer import FileManager
from .transport import Transport
from .security import DeviceIdentity


# ---------------------------------------------------------------------------
# Mapeo de teclas Qt -> nombres de nuestro protocolo
# ---------------------------------------------------------------------------
_QT_SPECIAL = {
    Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter",
    Qt.Key.Key_Escape: "esc", Qt.Key.Key_Backspace: "backspace",
    Qt.Key.Key_Tab: "tab", Qt.Key.Key_Space: "space",
    Qt.Key.Key_Delete: "delete", Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
    Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end",
    Qt.Key.Key_PageUp: "page_up", Qt.Key.Key_PageDown: "page_down",
    Qt.Key.Key_Shift: "shift", Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Alt: "alt", Qt.Key.Key_Meta: "cmd",
    Qt.Key.Key_CapsLock: "caps_lock",
    Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
    Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
    Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
    Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
}


# ---------------------------------------------------------------------------
# Cliente de red (asyncio en hilo aparte)
# ---------------------------------------------------------------------------
class ViewerClient(QObject):
    screenInfo = pyqtSignal(int, int)
    frame = pyqtSignal(int, int, bytes)
    authOk = pyqtSignal()
    authFailed = pyqtSignal(str)
    disconnected = pyqtSignal()
    status = pyqtSignal(str)
    progress = pyqtSignal(str, str, int, int)  # dir, name, done, total
    need2fa = pyqtSignal()

    def __init__(self, session_id: str, password: str):
        super().__init__()
        self.session_id = session_id
        self.password = password
        self.transport = Transport(session_id, password, protocol.ROLE_VIEWER)
        self.identity = DeviceIdentity.load_or_create()
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._authed = False
        self.files: FileManager | None = None

    # -- ciclo de vida ------------------------------------------------
    def start(self):
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run())
        except Exception as e:  # noqa: BLE001
            self.status.emit(f"Error de conexión: {e}")
        finally:
            self.disconnected.emit()

    async def _run(self):
        downloads = os.path.join(os.path.expanduser("~"), "NuvaConnect", "Recibidos")
        self.files = FileManager(
            self.transport, downloads,
            on_progress=lambda d, n, done, tot: self.progress.emit(d, n, done, tot),
        )
        self.status.emit("Conectando al servidor...")
        await self.transport.connect()
        self.status.emit("Conectado. Esperando al host / autenticando...")

        async for msg in self.transport.messages():
            ctrl = msg.get("_ctrl")
            if ctrl == protocol.C_PEER_LEFT:
                self.status.emit("El host se desconectó.")
                break
            if ctrl == protocol.C_ERROR:
                self.authFailed.emit(msg.get("reason", "error del servidor"))
                break
            if ctrl is not None:
                continue

            if self.files and await self.files.handle(msg):
                continue
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict):
        mt = msg.get("t")
        if mt == protocol.A_AUTH_CHALLENGE:
            # Sabemos descifrar => contraseña correcta. Firmamos el reto con la
            # clave de este dispositivo (prueba de identidad) y respondemos.
            nonce = msg.get("nonce")
            signature = self.identity.sign(nonce)
            await self.transport.send(
                protocol.A_AUTH_RESPONSE,
                nonce=nonce,
                device_pub=self.identity.public_bytes(),
                signature=signature,
            )
        elif mt == protocol.A_AUTH_2FA_REQUIRED:
            self.status.emit("El host solicita código 2FA...")
            self.need2fa.emit()
        elif mt == protocol.A_AUTH_LOCKED:
            self.authFailed.emit(
                f"Conexión bloqueada por demasiados intentos "
                f"({msg.get('seconds', 0)}s).")
        elif mt == protocol.A_AUTH_DENIED:
            self.authFailed.emit(msg.get("reason", "El host rechazó la sesión."))
        elif mt == protocol.A_AUTH_FAIL:
            if msg.get("_decrypt_error"):
                self.authFailed.emit("Contraseña incorrecta.")
            else:
                self.authFailed.emit(
                    f"Autenticación rechazada: {msg.get('reason', 'error')}.")
        elif mt == protocol.A_AUTH_OK:
            self._authed = True
            self.authOk.emit()
            self.status.emit("Autenticado. Recibiendo pantalla...")
            await self.transport.send(protocol.A_REQUEST_FULL)
        elif mt == protocol.A_SCREEN_INFO:
            self.screenInfo.emit(int(msg["width"]), int(msg["height"]))
        elif mt == protocol.A_FRAME:
            self.frame.emit(int(msg["x"]), int(msg["y"]), msg["data"])
        elif mt == protocol.A_PONG:
            pass

    # -- envío desde la GUI (thread-safe) -----------------------------
    def _submit(self, coro):
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)

    def send_mouse_move(self, nx, ny):
        self._submit(self.transport.send(protocol.A_MOUSE_MOVE, nx=nx, ny=ny))

    def send_mouse_click(self, nx, ny, button, pressed):
        self._submit(self.transport.send(
            protocol.A_MOUSE_CLICK, nx=nx, ny=ny, button=button, pressed=pressed))

    def send_mouse_scroll(self, dx, dy):
        self._submit(self.transport.send(protocol.A_MOUSE_SCROLL, dx=dx, dy=dy))

    def send_key(self, name, char, pressed):
        self._submit(self.transport.send(
            protocol.A_KEY, name=name, char=char, pressed=pressed))

    def send_file(self, path):
        if self.files:
            self._submit(self.files.start_send(path))

    def send_2fa(self, code):
        self._submit(self.transport.send(protocol.A_AUTH_2FA_CODE, code=code))

    def stop(self):
        self._submit(self.transport.close())


# ---------------------------------------------------------------------------
# Widget que dibuja la pantalla remota y captura input
# ---------------------------------------------------------------------------
class RemoteView(QWidget):
    def __init__(self, client: ViewerClient):
        super().__init__()
        self.client = client
        self._image: QImage | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 400)
        self._last_move = 0.0

        client.screenInfo.connect(self._on_screen_info)
        client.frame.connect(self._on_frame)

    # -- recepción de pantalla ---------------------------------------
    def _on_screen_info(self, w, h):
        self._image = QImage(w, h, QImage.Format.Format_RGB888)
        self._image.fill(Qt.GlobalColor.black)
        self.update()

    def _on_frame(self, x, y, data: bytes):
        if self._image is None:
            return
        tile = QImage()
        tile.loadFromData(data, "JPEG")
        if tile.isNull():
            return
        p = QPainter(self._image)
        p.drawImage(QPoint(x, y), tile)
        p.end()
        self.update()

    # -- render -------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.GlobalColor.black)
        if self._image is not None:
            target = self._fitted_rect()
            p.drawImage(target, self._image)
        p.end()

    def _fitted_rect(self):
        """Rectángulo destino manteniendo el aspect ratio (letterbox)."""
        from PyQt6.QtCore import QRect
        if self._image is None:
            return self.rect()
        iw, ih = self._image.width(), self._image.height()
        ww, wh = self.width(), self.height()
        if iw == 0 or ih == 0:
            return self.rect()
        scale = min(ww / iw, wh / ih)
        dw, dh = int(iw * scale), int(ih * scale)
        return QRect((ww - dw) // 2, (wh - dh) // 2, dw, dh)

    # -- mapeo de coordenadas a normalizadas 0..1 --------------------
    def _to_norm(self, pos):
        r = self._fitted_rect()
        if r.width() == 0 or r.height() == 0:
            return None
        nx = (pos.x() - r.x()) / r.width()
        ny = (pos.y() - r.y()) / r.height()
        if 0 <= nx <= 1 and 0 <= ny <= 1:
            return nx, ny
        return None

    # -- eventos de mouse --------------------------------------------
    def mouseMoveEvent(self, e):
        now = time.time()
        if now - self._last_move < 0.02:  # ~50 Hz máx
            return
        self._last_move = now
        n = self._to_norm(e.position().toPoint())
        if n:
            self.client.send_mouse_move(*n)

    def _btn(self, e):
        b = e.button()
        if b == Qt.MouseButton.LeftButton:
            return "left"
        if b == Qt.MouseButton.RightButton:
            return "right"
        if b == Qt.MouseButton.MiddleButton:
            return "middle"
        return "left"

    def mousePressEvent(self, e):
        n = self._to_norm(e.position().toPoint())
        if n:
            self.client.send_mouse_click(*n, self._btn(e), True)

    def mouseReleaseEvent(self, e):
        n = self._to_norm(e.position().toPoint())
        if n:
            self.client.send_mouse_click(*n, self._btn(e), False)

    def wheelEvent(self, e):
        dy = e.angleDelta().y() / 120.0
        dx = e.angleDelta().x() / 120.0
        self.client.send_mouse_scroll(dx, dy)

    # -- eventos de teclado ------------------------------------------
    def keyPressEvent(self, e: QKeyEvent):
        self._send_key(e, True)

    def keyReleaseEvent(self, e: QKeyEvent):
        self._send_key(e, False)

    def _send_key(self, e: QKeyEvent, pressed: bool):
        name = _QT_SPECIAL.get(Qt.Key(e.key()))
        char = None
        if name is None:
            txt = e.text()
            if txt and txt.isprintable() and txt != "":
                char = txt
        if name or char:
            self.client.send_key(name, char, pressed)


# ---------------------------------------------------------------------------
# Diálogo de conexión
# ---------------------------------------------------------------------------
class ConnectDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NuvaConnect — Conectar")
        layout = QFormLayout(self)
        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("123 456 789")
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.relay_edit = QLineEdit(config.relay_url())
        layout.addRow("ID de sesión:", self.id_edit)
        layout.addRow("Contraseña:", self.pw_edit)
        layout.addRow("Servidor relay:", self.relay_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self):
        sid = self.id_edit.text().replace(" ", "").strip()
        return sid, self.pw_edit.text(), self.relay_edit.text().strip()


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self, client: ViewerClient):
        super().__init__()
        self.client = client
        self.setWindowTitle("NuvaConnect — Controlador")
        self.resize(1100, 720)

        self.view = RemoteView(client)
        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.view)
        self.setCentralWidget(central)

        toolbar = QToolBar()
        self.addToolBar(toolbar)
        send_action = toolbar.addAction("Enviar archivo →")
        send_action.triggered.connect(self._send_file)

        self.setStatusBar(QStatusBar())
        self._set_status("Iniciando...")

        client.status.connect(self._set_status)
        client.authOk.connect(lambda: self._set_status("Conectado y autenticado."))
        client.authFailed.connect(self._on_auth_failed)
        client.disconnected.connect(lambda: self._set_status("Desconectado."))
        client.progress.connect(self._on_progress)
        client.need2fa.connect(self._ask_2fa)

    def _set_status(self, text):
        self.statusBar().showMessage(f"NuvaConnect · {text}")

    def _on_auth_failed(self, reason):
        QMessageBox.critical(self, "Autenticación fallida", reason)
        self._set_status(reason)

    def _on_progress(self, direction, name, done, total):
        pct = (done / total * 100) if total else 0
        arrow = "Recibiendo" if direction == "recv" else "Enviando"
        self._set_status(f"{arrow} {name}: {pct:.0f}%")

    def _send_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona un archivo para enviar")
        if path:
            self.client.send_file(path)

    def _ask_2fa(self):
        from PyQt6.QtWidgets import QInputDialog
        code, ok = QInputDialog.getText(
            self, "Verificación en dos pasos",
            "Ingresa el código de 6 dígitos de tu app de autenticación:")
        if ok and code:
            self.client.send_2fa(code.strip())

    def closeEvent(self, e):
        self.client.stop()
        super().closeEvent(e)


def main():
    import sys
    app = QApplication(sys.argv)

    dialog = ConnectDialog()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    session_id, password, relay = dialog.values()
    if not session_id or not password:
        QMessageBox.warning(None, "Datos incompletos", "Ingresa ID y contraseña.")
        return

    # Permitir override del relay desde el diálogo.
    if relay:
        _apply_relay_override(relay)

    client = ViewerClient(session_id, password)
    window = MainWindow(client)
    window.show()
    client.start()
    sys.exit(app.exec())


def _apply_relay_override(relay_url: str):
    """Parsea ws(s)://host:port y ajusta la config en runtime."""
    try:
        scheme, rest = relay_url.split("://", 1)
        host, _, port = rest.partition(":")
        config.USE_TLS = scheme == "wss"
        config.RELAY_HOST = host
        if port:
            config.RELAY_PORT = int(port.split("/")[0])
    except Exception:
        pass


if __name__ == "__main__":
    main()
