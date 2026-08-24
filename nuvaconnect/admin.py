"""Utilidad de administración de seguridad de NuvaConnect.

Permite al usuario del host revisar la bitácora de auditoría y gestionar la
allowlist de dispositivos de confianza.

Uso:
    python -m nuvaconnect.admin audit [N]          # ver últimos N eventos
    python -m nuvaconnect.admin list               # listar dispositivos de confianza
    python -m nuvaconnect.admin trust <fp> [label] # agregar dispositivo
    python -m nuvaconnect.admin revoke <fp>        # revocar dispositivo
    python -m nuvaconnect.admin whoami             # ver fingerprint de este equipo
"""
import sys
from datetime import datetime

from .security import AuditLog, Allowlist, DeviceIdentity


def _fmt_ts(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return

    cmd = argv[0]

    if cmd == "audit":
        n = int(argv[1]) if len(argv) > 1 else 50
        for e in AuditLog().tail(n):
            extra = {k: v for k, v in e.items() if k not in ("ts", "event")}
            print(f"{_fmt_ts(e['ts'])}  {e['event']:<22} {extra}")

    elif cmd == "list":
        al = Allowlist().all()
        if not al:
            print("No hay dispositivos de confianza.")
        for fp, meta in al.items():
            print(f"{fp}  {meta.get('label','')}  (desde {_fmt_ts(meta.get('added',0))})")

    elif cmd == "trust" and len(argv) >= 2:
        label = argv[2] if len(argv) > 2 else ""
        Allowlist().add(argv[1], label)
        print(f"Dispositivo {argv[1]} agregado a la allowlist.")

    elif cmd == "revoke" and len(argv) >= 2:
        Allowlist().remove(argv[1])
        print(f"Dispositivo {argv[1]} revocado.")

    elif cmd == "whoami":
        print("Fingerprint de este equipo:", DeviceIdentity.load_or_create().fingerprint())

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
