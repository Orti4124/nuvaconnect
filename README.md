# NuvaConnect

**Herramienta de acceso remoto y transferencia de archivos** — prototipo funcional multiplataforma (Windows / macOS), con los beneficios centrales de AnyDesk y TeamViewer:

- 🔗 **Conexión por ID** a través de un servidor relay → funciona **detrás de NAT/firewalls** sin abrir puertos.
- 🖥️ **Control remoto** de pantalla, teclado y mouse en tiempo real.
- 📁 **Transferencia de archivos** bidireccional con verificación de integridad.
- 🔒 **Cifrado extremo a extremo** — el servidor relay solo reenvía bytes cifrados; nunca ve pantallas, teclas ni archivos.

> Estado: **MVP funcional verificado**. El núcleo de red, cifrado, emparejamiento, autenticación y transferencia de archivos están probados automáticamente (`tests/`). El host y el viewer requieren un escritorio real para ejecutarse (captura de pantalla e input).

---

## 1. Arquitectura

```
   ┌─────────────┐        WebSocket/TLS        ┌─────────────┐        WebSocket/TLS        ┌─────────────┐
   │   HOST      │ ─── frames cifrados E2E ───▶ │   RELAY     │ ─── frames cifrados E2E ───▶ │   VIEWER    │
   │ (se comparte)│ ◀── input / archivos ────── │ (empareja   │ ◀── input / archivos ────── │(controlador)│
   │  mss+pynput │        por ID de sesión      │  por ID)    │        GUI PyQt6            │             │
   └─────────────┘                              └─────────────┘                              └─────────────┘
         │                                                                                          │
         └──────────────── clave AES derivada de la contraseña (PBKDF2) ─────────────────────────────┘
                      el relay NUNCA puede descifrar el contenido
```

**Componentes:**

| Módulo | Rol |
|--------|-----|
| `server/relay_server.py` | Servidor de emparejamiento. Une host y viewer por ID de sesión y reenvía frames cifrados. Escala horizontalmente. |
| `nuvaconnect/host.py` | Agente que comparte la máquina: captura de pantalla diferencial, inyección de input, archivos. |
| `nuvaconnect/viewer.py` | GUI del controlador: render de pantalla, captura de input, envío de archivos. |
| `nuvaconnect/transport.py` | Capa de transporte con cifrado E2E (compartida). |
| `nuvaconnect/crypto.py` | Derivación de clave (PBKDF2) y cifrado autenticado (Fernet/AES). |
| `nuvaconnect/filetransfer.py` | Transferencia por chunks, cifrada, con anti path-traversal. |
| `nuvaconnect/protocol.py` | Definición de mensajes de control y de aplicación. |

**Decisiones técnicas clave:**

- **Streaming diferencial por tiles:** el host divide la pantalla en bloques de 128 px, calcula un hash por bloque y **solo envía los que cambian**. Reduce drásticamente el ancho de banda en uso típico de escritorio.
- **Cifrado E2E:** la clave se deriva de la contraseña de sesión con PBKDF2 (200k iteraciones) usando el ID como salt. El relay es "ciego": si un tercero intercepta el tráfico, solo ve JPEG cifrados.
- **Autenticación por reto/respuesta:** el host envía un nonce cifrado; el viewer debe devolverlo. Contraseña incorrecta ⇒ el descifrado falla y la sesión se rechaza.

---

## 2. Instalación

Requiere **Python 3.10+**.

```bash
git clone <repo>  # o descomprime el paquete
cd nuvaconnect
pip install -r requirements.txt
```

> En macOS, el host necesita permisos de **Accesibilidad** y **Grabación de pantalla** (Preferencias del Sistema → Privacidad y seguridad). En Windows, ejecutar como administrador mejora la captura de ciertas ventanas.

---

## 3. Uso rápido (prueba local)

Abre **3 terminales**:

**Terminal 1 — servidor relay:**
```bash
python run_server.py
```

**Terminal 2 — host (máquina a compartir):**
```bash
python run_host.py
# Imprime el ID de sesión y la contraseña. Compártelos.
```

**Terminal 3 — viewer (controlador):**
```bash
python run_viewer.py
# Ingresa el ID y la contraseña en el diálogo.
```

### Uso en red real

En producción se despliega **un** servidor relay en un servidor con IP pública/dominio, y todos los clientes apuntan a él:

```bash
# En el servidor relay:
NUVA_RELAY_HOST=0.0.0.0 NUVA_RELAY_PORT=9765 python run_server.py

# En host y viewer:
export NUVA_RELAY_HOST=relay.nuvaprod.com
export NUVA_USE_TLS=1        # tras un reverse proxy con TLS (recomendado)
```

En el viewer también puedes fijar el servidor directamente en el diálogo de conexión.

---

## 4. Parámetros ajustables (variables de entorno)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `NUVA_RELAY_HOST` | `localhost` | Host del relay |
| `NUVA_RELAY_PORT` | `9765` | Puerto del relay |
| `NUVA_USE_TLS` | `0` | `1` para `wss://` (TLS) |
| `NUVA_JPEG_QUALITY` | `55` | Calidad de imagen (1-95) |
| `NUVA_TARGET_FPS` | `12` | FPS objetivo |
| `NUVA_MAX_SCALE` | `1.0` | Escala de envío (`0.75` = menos ancho de banda) |
| `NUVA_FILE_CHUNK` | `262144` | Tamaño de chunk de archivos |

---

## 5. Ciberseguridad (defensa en profundidad)

NuvaConnect incluye varias capas de seguridad independientes. Ver [`docs/SEGURIDAD.md`](docs/SEGURIDAD.md) para el detalle completo y el modelo de amenazas.

- 🔐 **Cifrado extremo a extremo** — el relay nunca ve el contenido.
- 🔑 **Contraseña de sesión** (1er factor, deriva la clave con PBKDF2).
- 🪪 **Identidad de dispositivo Ed25519** — el host verifica *qué máquina* se conecta (firma criptográfica).
- 📱 **2FA (TOTP)** — compatible con Google Authenticator / Authy (RFC 6238).
- ✅ **Allowlist de dispositivos** de confianza.
- 👤 **Aprobación humana** de cada sesión (estilo TeamViewer).
- 🛡️ **Anti fuerza bruta** con bloqueo temporal.
- 📋 **Bitácora de auditoría** (append-only).

Host de máxima seguridad:
```bash
NUVA_REQUIRE_2FA=1 NUVA_ENFORCE_ALLOWLIST=1 python run_host.py
```

Administración de seguridad:
```bash
python -m nuvaconnect.admin whoami     # fingerprint de este equipo
python -m nuvaconnect.admin list       # dispositivos de confianza
python -m nuvaconnect.admin audit 100  # bitácora de auditoría
```

## 6. Pruebas

```bash
python tests/test_e2e.py           # relay + cifrado + auth + input
python tests/test_filetransfer.py  # transferencia con verificación SHA-256
python tests/test_security.py      # 2FA/TOTP, device keys, allowlist, anti-fuerza-bruta, auditoría
```

---

## 7. Instaladores y empaquetado

- **Guía de instalación completa:** [`INSTALACION.md`](INSTALACION.md) — servidor (Docker/systemd) y cliente (Windows `.exe`, macOS `.dmg`, universal).
- **Compilación automática en la nube (recomendada):** [`docs/GITHUB_CI.md`](docs/GITHUB_CI.md) — GitHub Actions genera el `.exe`, el `.dmg` y la imagen Docker sin necesidad de máquinas Windows/Mac. Crea un tag `vX.Y.Z` y obtienes un Release descargable.
- **Ícono de marca:** generado con `installer/generate_icon.py` (paleta oficial NuvaProd). Se aplica automáticamente al `.exe` y al `.app`.
- Detalle manual por PyInstaller: [`build/build_windows.md`](build/build_windows.md) y [`build/build_macos.md`](build/build_macos.md).

---

## 8. Roadmap comercial

Ver [`docs/ROADMAP_COMERCIAL.md`](docs/ROADMAP_COMERCIAL.md) para la ruta de MVP → producto (audio, multi-monitor, portapapeles compartido, sesiones desatendidas, panel de administración, licenciamiento, hardening de seguridad).

---

## 9. Uso legal y ético

⚠️ NuvaConnect debe usarse **solo con consentimiento explícito** del usuario de la máquina remota. El host muestra siempre el ID y la contraseña al usuario, que debe compartirlos voluntariamente. Antes de comercializar, revisa el cumplimiento normativo aplicable (protección de datos, aviso de sesión visible, registro de auditoría). No uses esta herramienta para acceso no autorizado.

---

*(c) NuvaProd — Prototipo. Licencia por definir.*
