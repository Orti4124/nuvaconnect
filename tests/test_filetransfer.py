"""Prueba de transferencia de archivos cifrada sobre el relay."""
import asyncio
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nuvaconnect import config, protocol
from nuvaconnect.transport import Transport
from nuvaconnect.filetransfer import FileManager
from server.relay_server import RelayServer
import websockets


async def pump(transport, fm, stop):
    async for msg in transport.messages():
        if msg.get("_ctrl"):
            continue
        await fm.handle(msg)
        if stop.is_set():
            break


async def run():
    config.RELAY_PORT = 9801
    server = RelayServer()
    async with websockets.serve(server.handler, "localhost", config.RELAY_PORT,
                                max_size=16 * 1024 * 1024):
        await asyncio.sleep(0.2)
        sid, pw = "999888777", "clave"
        host = Transport(sid, pw, protocol.ROLE_HOST)
        viewer = Transport(sid, pw, protocol.ROLE_VIEWER)
        await host.connect(); await viewer.connect()

        tmp = tempfile.mkdtemp()
        recv_dir = os.path.join(tmp, "recibidos")
        # Archivo de ~1.3 MB de datos aleatorios
        src = os.path.join(tmp, "prueba.bin")
        data = os.urandom(1_300_000)
        with open(src, "wb") as f:
            f.write(data)

        host_fm = FileManager(host, recv_dir)
        viewer_fm = FileManager(viewer, os.path.join(tmp, "viewer_recv"))

        stop = asyncio.Event()
        # El host escucha y recibe; el viewer envía.
        host_task = asyncio.create_task(pump(host, host_fm, stop))
        viewer_task = asyncio.create_task(pump(viewer, viewer_fm, stop))

        # Esperar emparejamiento (ambos consumidos por pump; damos margen)
        await asyncio.sleep(0.5)
        await viewer_fm.start_send(src)
        await asyncio.sleep(1.0)  # dejar drenar los chunks

        received = os.path.join(recv_dir, "prueba.bin")
        ok_exists = os.path.isfile(received)
        ok_hash = False
        if ok_exists:
            h1 = hashlib.sha256(data).hexdigest()
            with open(received, "rb") as f:
                h2 = hashlib.sha256(f.read()).hexdigest()
            ok_hash = h1 == h2

        print("  PASS archivo recibido" if ok_exists else "  FAIL archivo no recibido")
        print("  PASS integridad SHA-256 idéntica" if ok_hash else "  FAIL hash distinto")

        stop.set()
        await host.close(); await viewer.close()
        host_task.cancel(); viewer_task.cancel()
        sys.exit(0 if (ok_exists and ok_hash) else 1)


if __name__ == "__main__":
    asyncio.run(run())
