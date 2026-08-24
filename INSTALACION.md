# NuvaConnect — Guía de instalación

Hay dos piezas a instalar:

- **Servidor (relay):** se instala **una vez** en un servidor con IP/dominio público. Empareja las conexiones.
- **Cliente:** se instala en cada equipo. Incluye el **Host** (compartir tu equipo) y el **Viewer** (controlar otro equipo).

Elige la vía que prefieras. Todas las rutas están en la carpeta `installer/`.

---

## A) Servidor relay

### Opción 1 — Docker (recomendada, un comando)

```bash
docker compose -f installer/server/docker-compose.yml up -d --build
```

El relay queda escuchando en el puerto **9765**. Para TLS automático (`wss://`) con tu dominio, descomenta el bloque `caddy` del `docker-compose.yml`, edita el `Caddyfile` con tu dominio y vuelve a levantar.

### Opción 2 — Linux nativo (systemd)

```bash
sudo bash installer/server/install_server_linux.sh
```

Crea un usuario de servicio, instala en `/opt/nuvaconnect` y registra el servicio `nuvaconnect-relay` (arranca en el boot).

```bash
systemctl status nuvaconnect-relay      # ver estado
journalctl -u nuvaconnect-relay -f      # ver logs
```

> Recuerda abrir el puerto 9765 en el firewall/grupo de seguridad.

---

## B) Cliente (Host + Viewer)

### Opción 1 — Instalador nativo de Windows (.exe)

En una máquina **Windows** con Python 3.10+ e [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```powershell
.\installer\windows\build.ps1
```

Genera **`dist_installer\NuvaConnect-Setup.exe`**: un instalador con asistente que crea accesos directos ("Controlar otro equipo" y "Compartir mi equipo") y pregunta por la dirección del servidor relay.

### Opción 2 — Instalador nativo de macOS (.dmg)

En un **Mac** con Python 3.10+ (y opcionalmente `brew install create-dmg`):

```bash
bash installer/macos/build_dmg.sh
```

Genera **`dist_installer/NuvaConnect.dmg`**. Arrástralo a Aplicaciones. En el primer uso, macOS pedirá permisos de **Grabación de pantalla** y **Accesibilidad** para el Host.

### Opción 3 — Instalador universal sin compilar (Windows/macOS/Linux)

La vía más rápida: crea un entorno aislado y genera lanzadores, sin producir binarios.

```bash
python installer/install.py --component client --relay ws://relay.nuvaprod.com:9765
```

Al terminar tendrás, en `~/NuvaConnect/`:
- **NuvaConnect** → controlar otro equipo (Viewer)
- **NuvaConnect-Host** → compartir tu equipo (Host)

---

## Resumen de comandos

| Objetivo | Comando |
|----------|---------|
| Servidor con Docker | `docker compose -f installer/server/docker-compose.yml up -d --build` |
| Servidor con systemd | `sudo bash installer/server/install_server_linux.sh` |
| Instalador Windows (.exe) | `.\installer\windows\build.ps1` |
| Instalador macOS (.dmg) | `bash installer/macos/build_dmg.sh` |
| Cliente universal | `python installer/install.py --component client --relay ws://TU_RELAY:9765` |

---

## Notas para producción

- **Firma de código:** firma el `.exe` (signtool) y notariza el `.app`/`.dmg` (notarytool) para evitar alertas de seguridad. Los scripts ya tienen los ganchos (`SIGN_IDENTITY`, `NOTARY_PROFILE`).
- **TLS:** usa `wss://` en el relay (Caddy/nginx) y configura `NUVA_USE_TLS=1` en los clientes.
- **Íconos:** coloca `installer/windows/nuvaconnect.ico` y `installer/macos/nuvaconnect.icns` para personalizar la marca (los scripts los detectan automáticamente).
