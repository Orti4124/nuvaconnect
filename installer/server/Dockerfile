# NuvaConnect — Servidor relay
# Imagen ligera para desplegar el servidor de emparejamiento.
FROM python:3.11-slim

LABEL org.opencontainers.image.title="NuvaConnect Relay" \
      org.opencontainers.image.vendor="NuvaProd"

WORKDIR /app

# Solo el relay necesita estas dependencias (no mss/pynput/PyQt6).
RUN pip install --no-cache-dir "websockets>=12.0" "cryptography>=42.0" "msgpack>=1.0"

# Copiar el código necesario para el servidor.
COPY nuvaconnect/ /app/nuvaconnect/
COPY server/ /app/server/
COPY run_server.py /app/run_server.py

# Puerto del relay (coincide con config.RELAY_PORT por defecto).
EXPOSE 9765

ENV NUVA_RELAY_HOST=0.0.0.0 \
    NUVA_RELAY_PORT=9765

# Usuario sin privilegios.
RUN useradd -m -u 10001 nuva && chown -R nuva:nuva /app
USER nuva

CMD ["python", "run_server.py"]
