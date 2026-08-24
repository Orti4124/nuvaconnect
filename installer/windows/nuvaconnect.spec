# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para NuvaConnect (Windows).
# Genera DOS ejecutables en un solo directorio dist/NuvaConnect/:
#   - NuvaConnect.exe       -> Viewer/Controlador (con GUI, sin consola)
#   - NuvaConnect-Host.exe  -> Agente Host (consola, muestra ID y contraseña)
#
# Ejecutar DESDE LA RAIZ del proyecto:
#   pyinstaller installer/windows/nuvaconnect.spec

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Raiz del proyecto: las rutas de un .spec se resuelven relativas a SU carpeta,
# no al directorio actual. Por eso anclamos todo a la raiz del repo.
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
ICON = os.path.join(ROOT, "installer", "windows", "nuvaconnect.ico")
ICON = ICON if os.path.exists(ICON) else None

pyqt_datas, pyqt_binaries, pyqt_hidden = collect_all("PyQt6")

common_hidden = [
    "websockets", "cryptography", "msgpack",
    "mss", "pynput",
    "pynput.keyboard._win32", "pynput.mouse._win32",
]

viewer_a = Analysis(
    [os.path.join(ROOT, "run_viewer.py")],
    pathex=[ROOT],
    binaries=pyqt_binaries,
    datas=pyqt_datas,
    hiddenimports=common_hidden + pyqt_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)

host_a = Analysis(
    [os.path.join(ROOT, "run_host.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=common_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["PyQt6"],
)

viewer_pyz = PYZ(viewer_a.pure)
host_pyz = PYZ(host_a.pure)

viewer_exe = EXE(
    viewer_pyz, viewer_a.scripts, [],
    exclude_binaries=True,
    name="NuvaConnect",
    console=False,
    icon=ICON,
)

host_exe = EXE(
    host_pyz, host_a.scripts, [],
    exclude_binaries=True,
    name="NuvaConnect-Host",
    console=True,
    icon=ICON,
)

coll = COLLECT(
    viewer_exe, viewer_a.binaries, viewer_a.datas,
    host_exe, host_a.binaries, host_a.datas,
    strip=False,
    upx=True,
    name="NuvaConnect",
)
