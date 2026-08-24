# Empaquetado para Windows (.exe)

Genera ejecutables independientes con [PyInstaller](https://pyinstaller.org/).

## Requisitos

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

## Host (agente)

```powershell
pyinstaller --noconfirm --onefile --name NuvaConnect-Host `
  --collect-submodules mss --collect-submodules pynput `
  run_host.py
```

## Viewer (controlador, con GUI)

```powershell
pyinstaller --noconfirm --onefile --windowed --name NuvaConnect `
  --collect-all PyQt6 `
  run_viewer.py
```

Los binarios quedan en `dist/`.

## Firma de código (recomendado para producción)

Sin firma, Windows SmartScreen mostrará advertencias. Firma con un certificado de code-signing:

```powershell
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 dist\NuvaConnect.exe
```

## Notas

- Para **acceso desatendido**, empaqueta el host como servicio de Windows (p. ej. con `pywin32` / `nssm`).
- Prueba en una VM limpia para detectar dependencias nativas faltantes.
