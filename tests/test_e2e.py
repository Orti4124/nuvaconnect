"""Prueba de integración: relay + transporte cifrado E2E.

No requiere pantalla ni GUI: verifica el núcleo (emparejamiento, cifrado,
handshake de autenticación y contraseña incorrecta).
Ejecutar:  python tests/test_e2e.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuvaconnect import config, protocol
from nuvaconnect.transport import Transport
from server.relay_server import RelayServer

import websockets

RESULTS = []


def check(name, ok):
    RESULTS.append((name, ok))
    print(("  PASS " if ok else "  FAIL ") + name)


async def run():
    # Arrancar relay en un puerto de prueba
    config.RELAY_PORT = 9799
    server = RelayServer()
    async with websockets.serve(server.handler, "localhost", config.RELAY_PORT,
                                max_size=16 * 1024 * 1024):
        await asyncio.sleep(0.2)

        sid = "111222333"
        pw = "secret42"

        # --- Caso 1: contraseña correcta, emparejamiento + cifrado ---
        host = Transport(sid, pw, protocol.ROLE_HOST)
        viewer = Transport(sid, pw, protocol.ROLE_VIEWER)
        await host.connect()
        await viewer.connect()

        host_msgs = host.messages()
        viewer_msgs = viewer.messages()

        # Esperar peer_joined en ambos
        await _until(host_msgs, lambda m: m.get("_ctrl") == protocol.C_PEER_JOINED)
        await _until(viewer_msgs, lambda m: m.get("_ctrl") == protocol.C_PEER_JOINED)
        check("emparejamiento host+viewer por ID", True)

        # Host manda un frame cifrado; viewer lo descifra
        payload = os.urandom(5000)
        await host.send(protocol.A_FRAME, x=0, y=0, w=10, h=10, data=payload)
        msg = await _until(viewer_msgs, lambda m: m.get("t") == protocol.A_FRAME)
        check("frame cifrado enviado y descifrado correctamente",
              msg.get("data") == payload)

        # Viewer manda input; host lo recibe
        await viewer.send(protocol.A_MOUSE_MOVE, nx=0.5, ny=0.5)
        msg = await _until(host_msgs, lambda m: m.get("t") == protocol.A_MOUSE_MOVE)
        check("evento de input entregado al host",
              abs(msg.get("nx", 0) - 0.5) < 1e-9)

        # Handshake de auth: host reta, viewer responde
        nonce = os.urandom(16)
        await host.send(protocol.A_AUTH_CHALLENGE, nonce=nonce)
        chal = await _until(viewer_msgs, lambda m: m.get("t") == protocol.A_AUTH_CHALLENGE)
        await viewer.send(protocol.A_AUTH_RESPONSE, nonce=chal.get("nonce"))
        resp = await _until(host_msgs, lambda m: m.get("t") == protocol.A_AUTH_RESPONSE)
        check("handshake de autenticación (nonce round-trip)",
              resp.get("nonce") == nonce)

        await host.close()
        await viewer.close()
        await asyncio.sleep(0.2)

        # --- Caso 2: contraseña incorrecta -> no descifra ---
        sid2 = "444555666"
        host2 = Transport(sid2, "correcta", protocol.ROLE_HOST)
        viewer2 = Transport(sid2, "INCORRECTA", protocol.ROLE_VIEWER)
        await host2.connect()
        await viewer2.connect()
        h2 = host2.messages()
        v2 = viewer2.messages()
        await _until(h2, lambda m: m.get("_ctrl") == protocol.C_PEER_JOINED)
        await _until(v2, lambda m: m.get("_ctrl") == protocol.C_PEER_JOINED)

        await host2.send(protocol.A_AUTH_CHALLENGE, nonce=os.urandom(16))
        msg = await _until(v2, lambda m: m.get("t") in
                           (protocol.A_AUTH_CHALLENGE, protocol.A_AUTH_FAIL))
        check("contraseña incorrecta => fallo de descifrado detectado",
              msg.get("t") == protocol.A_AUTH_FAIL and msg.get("_decrypt_error"))

        await host2.close()
        await viewer2.close()

    ok = all(r[1] for r in RESULTS)
    print("\nRESULTADO:", "TODO OK ✔" if ok else "HAY FALLOS �“")
    sys.exit(0 if ok else 1)


async def _until(gen, pred, timeout=5.0):
    async def _loop():
        async for m in gen:
            if pred(m):
                return m
    return await asyncio.wait_for(_loop(), timeout=timeout)


if __name__ == "__main__":
    asyncio.run(run())
