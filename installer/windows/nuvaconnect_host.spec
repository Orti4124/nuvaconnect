# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — SOLO el Host (NuvaConnect-Host.exe), consola.
import os

block_cipher = None
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
ICON = os.path.join(ROOT, "installer", "windows", "nuvaconnect.ico")
ICON = ICON if os.path.exists(ICON) else None

hidden = ["websockets", "cryptography", "msgpack", "mss", "pynput",
          "pynput.keyboard._win32", "pynput.mouse._win32"]

a = Analysis(
    [os.path.join(ROOT, "run_host.py")],
    pathex=[ROOT],
    binaries=[], datas=[],
    hiddenimports=hidden,
    excludes=["PyQt6"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="NuvaConnect-Host", console=True, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="NuvaConnect-Host")
