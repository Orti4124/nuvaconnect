# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — SOLO el Viewer/Controlador (NuvaConnect.exe), GUI.
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
ICON = os.path.join(ROOT, "installer", "windows", "nuvaconnect.ico")
ICON = ICON if os.path.exists(ICON) else None

pyqt_datas, pyqt_binaries, pyqt_hidden = collect_all("PyQt6")
hidden = ["websockets", "cryptography", "msgpack", "mss", "pynput",
          "pynput.keyboard._win32", "pynput.mouse._win32"]

a = Analysis(
    [os.path.join(ROOT, "run_viewer.py")],
    pathex=[ROOT],
    binaries=pyqt_binaries, datas=pyqt_datas,
    hiddenimports=hidden + pyqt_hidden,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="NuvaConnect", console=False, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="NuvaConnect")
