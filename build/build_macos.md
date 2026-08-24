# Empaquetado para macOS (.app)

Genera aplicaciones con [PyInstaller](https://pyinstaller.org/).

## Requisitos

```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Host (agente)

```bash
pyinstaller --noconfirm --onefile --name NuvaConnect-Host \
  --collect-submodules mss --collect-submodules pynput \
  run_host.py
```

## Viewer (controlador, con GUI)

```bash
pyinstaller --noconfirm --windowed --name NuvaConnect \
  --collect-all PyQt6 \
  run_viewer.py
```

## Permisos de macOS (imprescindibles para el host)

El agente host necesita permisos que el usuario debe conceder en
**Preferencias del Sistema → Privacidad y seguridad**:

- **Grabación de pantalla** (para capturar la pantalla).
- **Accesibilidad** (para inyectar teclado y mouse con pynput).

Sin estos permisos, el host se conecta pero no captura ni controla.

## Firma y notarización (producción)

Para distribuir sin la alerta de "app de desarrollador no identificado":

```bash
codesign --deep --force --options runtime \
  --sign "Developer ID Application: TU EMPRESA (TEAMID)" \
  dist/NuvaConnect.app

xcrun notarytool submit dist/NuvaConnect.app --keychain-profile "AC_PASSWORD" --wait
xcrun stapler staple dist/NuvaConnect.app
```

## Notas

- Añade las *usage descriptions* en el `Info.plist` (`NSScreenCaptureUsageDescription`, etc.).
- Para acceso desatendido, empaqueta el host como `LaunchDaemon`.
