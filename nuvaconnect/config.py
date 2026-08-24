"""Configuración central de NuvaConnect.

Todos los parámetros ajustables del prototipo viven aquí para facilitar el
tuning durante pruebas y el paso a producción (variables de entorno).
"""
import os


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


# ---------------------------------------------------------------------------
# Servidor relay
# ---------------------------------------------------------------------------
# Host/puerto del servidor de emparejamiento. En producción esto apunta a tu
# dominio (p. ej. wss://relay.nuvaprod.com). Para pruebas locales: localhost.
RELAY_HOST = _env("NUVA_RELAY_HOST", "localhost")
RELAY_PORT = int(_env("NUVA_RELAY_PORT", "9765"))

# Si se usa TLS (wss://) en el servidor. En producción SIEMPRE True.
USE_TLS = _env("NUVA_USE_TLS", "0") == "1"


def relay_url() -> str:
    scheme = "wss" if USE_TLS else "ws"
    return f"{scheme}://{RELAY_HOST}:{RELAY_PORT}"


# ---------------------------------------------------------------------------
# Streaming de pantalla
# ---------------------------------------------------------------------------
# Calidad JPEG (1-95). Menor = menos ancho de banda, más artefactos.
JPEG_QUALITY = int(_env("NUVA_JPEG_QUALITY", "55"))

# FPS objetivo del host. El host adapta automáticamente si la red va lenta.
TARGET_FPS = int(_env("NUVA_TARGET_FPS", "12"))

# Escala máxima de envío. 1.0 = resolución nativa. 0.75 reduce ancho de banda.
MAX_SCALE = float(_env("NUVA_MAX_SCALE", "1.0"))

# Tamaño de bloque para detección de cambios (envío diferencial). px.
TILE_SIZE = int(_env("NUVA_TILE_SIZE", "128"))


# ---------------------------------------------------------------------------
# Transferencia de archivos
# ---------------------------------------------------------------------------
# Tamaño de chunk para archivos (bytes). 256 KB es un buen equilibrio.
FILE_CHUNK_SIZE = int(_env("NUVA_FILE_CHUNK", str(256 * 1024)))


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
# Iteraciones PBKDF2 para derivar la clave desde la contraseña de sesión.
KDF_ITERATIONS = int(_env("NUVA_KDF_ITERS", "200000"))

# Longitud del ID de sesión que se genera automáticamente en el host.
SESSION_ID_LENGTH = 9  # p.ej. 123 456 789 estilo AnyDesk


# ---------------------------------------------------------------------------
# Ciberseguridad (controles del host)
# ---------------------------------------------------------------------------
# El usuario del host debe aceptar manualmente cada sesión entrante (como el
# diálogo de aprobación de TeamViewer). Recomendado ON.
REQUIRE_APPROVAL = _env("NUVA_REQUIRE_APPROVAL", "1") == "1"

# Exigir segundo factor (TOTP) además de la contraseña de sesión.
REQUIRE_2FA = _env("NUVA_REQUIRE_2FA", "0") == "1"

# Solo permitir dispositivos cuyo fingerprint esté en la allowlist del host.
ENFORCE_ALLOWLIST = _env("NUVA_ENFORCE_ALLOWLIST", "0") == "1"

# Intentos fallidos antes de bloquear temporalmente (anti fuerza bruta).
MAX_AUTH_ATTEMPTS = int(_env("NUVA_MAX_AUTH_ATTEMPTS", "5"))
LOCKOUT_SECONDS = int(_env("NUVA_LOCKOUT_SECONDS", "300"))
