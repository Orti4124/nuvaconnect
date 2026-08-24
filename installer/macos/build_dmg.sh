#!/usr/bin/env bash
#
# build_dmg.sh — Genera el instalador .dmg de NuvaConnect para macOS.
#
# Requisitos en el Mac:
#   - Python 3.10+  (python.org o Homebrew)
#   - create-dmg    (brew install create-dmg)   [opcional: si falta, hace un .dmg simple con hdiutil]
#
# Uso (desde la raíz del proyecto):
#   bash installer/macos/build_dmg.sh
#
# Firma/notarización opcionales vía variables de entorno:
#   SIGN_IDENTITY="Developer ID Application: TU EMPRESA (TEAMID)"
#   NOTARY_PROFILE="AC_PASSWORD"   (perfil guardado con notarytool)
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
ROOT="$(pwd)"
echo "== Compilando NuvaConnect para macOS =="
echo "Raíz: $ROOT"

# 1) venv + dependencias
if [[ ! -d ".venv" ]]; then
  echo "-> Creando entorno virtual..."
  python3 -m venv .venv
fi
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt pyinstaller

# 2) Empaquetar con PyInstaller
echo "-> Empaquetando con PyInstaller..."
./.venv/bin/pyinstaller --noconfirm --clean installer/macos/nuvaconnect_mac.spec

APP="dist/NuvaConnect.app"

# 3) Firma de código (opcional)
if [[ -n "${SIGN_IDENTITY:-}" ]]; then
  echo "-> Firmando la app con: $SIGN_IDENTITY"
  codesign --deep --force --options runtime \
    --entitlements installer/macos/NuvaConnect.entitlements \
    --sign "$SIGN_IDENTITY" "$APP"
fi

# 4) Crear el .dmg
mkdir -p dist_installer
DMG="dist_installer/NuvaConnect.dmg"
rm -f "$DMG"

if command -v create-dmg >/dev/null 2>&1; then
  echo "-> Creando .dmg con create-dmg..."
  create-dmg \
    --volname "NuvaConnect" \
    --app-drop-link 450 180 \
    --icon "NuvaConnect.app" 150 180 \
    --window-size 600 400 \
    "$DMG" "$APP"
else
  echo "-> create-dmg no está instalado; usando hdiutil (dmg simple)..."
  STAGE="$(mktemp -d)"
  cp -R "$APP" "$STAGE/"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname "NuvaConnect" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
  rm -rf "$STAGE"
fi

# 5) Notarización (opcional)
if [[ -n "${NOTARY_PROFILE:-}" ]]; then
  echo "-> Enviando a notarización de Apple..."
  xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi

echo ""
echo "✔ Listo: $DMG"
echo "  El Host queda en dist/NuvaConnect-Host/ (ejecutable de consola)."
echo "  Recuerda: en el primer uso, macOS pedirá permisos de Grabación de"
echo "  pantalla y Accesibilidad para el Host."
