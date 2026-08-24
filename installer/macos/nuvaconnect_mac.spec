# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec para NuvaConnect en macOS.
# Genera una app .app (Viewer con GUI) y un ejecutable Host de consola.
#
# Ejecutar DESDE LA RAIZ del proyecto:
#   pyinstaller installer/macos/nuvaconnect_mac.spec

import os
from PyInstaller.utils.hooks import collect_all

# Raiz del proyecto: las rutas de un .spec se resuelven relativas a SU carpeta.
ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
icon = os.path.join(ROOT, "installer", "macos", "nuvaconnect.icns")
icon = icon if os.path.exists(icon) else None

pyqt_datas, pyqt_binaries, pyqt_hidden = collect_all("PyQt6")

common_hidden = [
    "websockets", "cryptography", "msgpack", "mss", "pynput",
    "pynput.keyboard._darwin", "pynput.mouse._darwin",
]

viewer_a = Analysis(
    [os.path.join(ROOT, "run_viewer.py")], pathex=[ROOT],
    binaries=pyqt_binaries, datas=pyqt_datas,
    hiddenimports=common_hidden + pyqt_hidden,
)
viewer_pyz = PYZ(viewer_a.pure)
viewer_exe = EXE(viewer_pyz, viewer_a.scripts, [], exclude_binaries=True,
                 name="NuvaConnect", console=False, icon=icon)
viewer_coll = COLLECT(viewer_exe, viewer_a.binaries, viewer_a.datas,
                      strip=False, upx=False, name="NuvaConnect")

app = BUNDLE(
    viewer_coll,
    name="NuvaConnect.app",
    icon=icon,
    bundle_identifier="com.nuvaprod.nuvaconnect",
    info_plist={
        "CFBundleName": "NuvaConnect",
        "CFBundleDisplayName": "NuvaConnect",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "NSScreenCaptureUsageDescription":
            "NuvaConnect necesita capturar la pantalla para el soporte remoto.",
        "NSAccessibilityUsageDescription":
            "NuvaConnect necesita controlar teclado y mouse durante la sesion remota.",
    },
)

host_a = Analysis(
    [os.path.join(ROOT, "run_host.py")], pathex=[ROOT],
    binaries=[], datas=[], hiddenimports=common_hidden,
    excludes=["PyQt6"],
)
host_pyz = PYZ(host_a.pure)
host_exe = EXE(host_pyz, host_a.scripts, [], exclude_binaries=True,
               name="NuvaConnect-Host", console=True, icon=icon)
host_coll = COLLECT(host_exe, host_a.binaries, host_a.datas,
                    strip=False, upx=False, name="NuvaConnect-Host")
