#!/usr/bin/env bash
#
# Instalador del servidor relay NuvaConnect para Linux (sin Docker).
# Crea un usuario de servicio, instala en /opt/nuvaconnect y registra un
# servicio systemd que arranca en el boot.
#
# Uso (como root):   sudo bash installer/server/install_server_linux.sh
#
set -euo pipefail

APP_DIR=/opt/nuvaconnect
SERVICE_USER=nuva
PORT="${NUVA_RELAY_PORT:-9765}"

echo "== Instalador del servidor relay NuvaConnect =="

if [[ $EUID -ne 0 ]]; then
  echo "Este script debe ejecutarse como root (usa sudo)." >&2
  exit 1
fi

# 1) Dependencias del sistema
echo "-> Instalando Python y venv..."
if command -v apt-get >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3 python3-venv python3-pip
elif command -v dnf >/dev/null; then
  dnf install -y python3 python3-pip
fi

# 2) Usuario de servicio
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "-> Creando usuario de servicio '$SERVICE_USER'..."
  useradd --system --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# 3) Copiar el código (asume que se ejecuta desde la raíz del proyecto)
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "-> Copiando archivos a $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r "$SRC_DIR/nuvaconnect" "$SRC_DIR/server" "$SRC_DIR/run_server.py" "$APP_DIR/"

# 4) Entorno virtual y dependencias del relay
echo "-> Creando entorno virtual e instalando dependencias..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet "websockets>=12.0" "cryptography>=42.0" "msgpack>=1.0"

chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

# 5) Servicio systemd
echo "-> Registrando servicio systemd..."
sed "s/NUVA_RELAY_PORT=9765/NUVA_RELAY_PORT=$PORT/" \
    "$SRC_DIR/installer/server/nuvaconnect-relay.service" \
    > /etc/systemd/system/nuvaconnect-relay.service
systemctl daemon-reload
systemctl enable --now nuvaconnect-relay

echo ""
echo "✔ Servidor relay instalado y en ejecución."
echo "  Estado:   systemctl status nuvaconnect-relay"
echo "  Logs:     journalctl -u nuvaconnect-relay -f"
echo "  Puerto:   $PORT"
echo ""
echo "Recuerda abrir el puerto $PORT en el firewall y, para producción,"
echo "poner un reverse proxy con TLS (wss://) delante del relay."
