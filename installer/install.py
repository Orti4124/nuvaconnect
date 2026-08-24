#!/usr/bin/env python3
"""Instalador universal de NuvaConnect (sin compilar binarios).

Funciona en Windows, macOS y Linux. Crea un entorno virtual aislado, instala
las dependencias y genera lanzadores fáciles de usar. Es la vía más rápida si
no quieres generar un .exe/.dmg nativo.

Uso:
    python installer/install.py --component client   # host + viewer
    python installer/install.py --component server   # solo relay

Opciones:
    --prefix DIR   Carpeta de instalación (por defecto: ~/NuvaConnect)
    --relay URL    Fija el servidor relay (ej. ws://relay.nuvaprod.com:9765)
"""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

CLIENT_DEPS = ["websockets>=12.0", "cryptography>=42.0", "msgpack>=1.0",
               "mss>=9.0", "pynput>=1.7", "Pillow>=10.0", "PyQt6>=6.6"]
SERVER_DEPS = ["websockets>=12.0", "cryptography>=42.0", "msgpack>=1.0"]

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def log(msg):
    print(f"  {msg}")


def make_venv(venv_dir: Path):
    log(f"Creando entorno virtual en {venv_dir} ...")
    venv.create(venv_dir, with_pip=True)
    return venv_dir / ("Scripts" if os.name == "nt" else "bin")


def pip_install(bindir: Path, deps):
    py = bindir / ("python.exe" if os.name == "nt" else "python")
    subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-q", *deps])


def copy_code(prefix: Path):
    import shutil
    log(f"Copiando código a {prefix} ...")
    prefix.mkdir(parents=True, exist_ok=True)
    for item in ["nuvaconnect", "server", "run_host.py", "run_viewer.py", "run_server.py"]:
        src = PROJECT_ROOT / item
        dst = prefix / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)


def write_launchers(prefix: Path, bindir: Path, component: str, relay: str | None):
    py = bindir / ("python.exe" if os.name == "nt" else "python")

    if component == "server":
        # El SERVIDOR escucha en 0.0.0.0; de --relay solo tomamos el puerto.
        bind_host, bind_port = "0.0.0.0", _port(relay)
        targets = [("NuvaConnect-Relay", "run_server.py")]
        env_pairs = [("NUVA_RELAY_HOST", bind_host), ("NUVA_RELAY_PORT", bind_port)]
    else:
        # El CLIENTE (host+viewer) se CONECTA al relay indicado en --relay.
        targets = [("NuvaConnect", "run_viewer.py"), ("NuvaConnect-Host", "run_host.py")]
        env_pairs = ([("NUVA_RELAY_HOST", _host(relay)), ("NUVA_RELAY_PORT", _port(relay))]
                     if relay else [])

    env_line_sh = ("export " + " ".join(f'{k}="{v}"' for k, v in env_pairs)) if env_pairs else ""
    env_line_bat = "\n".join(f"set {k}={v}" for k, v in env_pairs)

    for name, script in targets:
        if os.name == "nt":
            launcher = prefix / f"{name}.bat"
            launcher.write_text(
                f'@echo off\ncd /d "{prefix}"\n{env_line_bat}\n"{py}" "{script}" %*\n',
                encoding="utf-8")
        else:
            launcher = prefix / f"{name}.command"
            launcher.write_text(
                f'#!/usr/bin/env bash\ncd "{prefix}"\n{env_line_sh}\n"{py}" "{script}" "$@"\n',
                encoding="utf-8")
            os.chmod(launcher, 0o755)
        log(f"Lanzador creado: {launcher.name}")


def _host(relay):
    if not relay:
        return "localhost"
    return relay.split("://", 1)[-1].split(":")[0]


def _port(relay):
    if not relay or ":" not in relay.split("://", 1)[-1]:
        return "9765"
    return relay.split("://", 1)[-1].split(":")[1].split("/")[0]


def main():
    ap = argparse.ArgumentParser(description="Instalador universal de NuvaConnect")
    ap.add_argument("--component", choices=["client", "server"], required=True)
    ap.add_argument("--prefix", default=str(Path.home() / "NuvaConnect"))
    ap.add_argument("--relay", default=None)
    args = ap.parse_args()

    prefix = Path(args.prefix).expanduser().resolve()
    print(f"== Instalando NuvaConnect ({args.component}) en {prefix} ==")

    copy_code(prefix)
    bindir = make_venv(prefix / ".venv")
    deps = CLIENT_DEPS if args.component == "client" else SERVER_DEPS
    log("Instalando dependencias (puede tardar unos minutos)...")
    pip_install(bindir, deps)
    write_launchers(prefix, bindir, args.component, args.relay)

    print("\n✔ Instalación completa.")
    if args.component == "client":
        print("  Para CONTROLAR otro equipo:  ejecuta NuvaConnect")
        print("  Para COMPARTIR este equipo:  ejecuta NuvaConnect-Host")
    else:
        print("  Para iniciar el servidor:    ejecuta NuvaConnect-Relay")
    print(f"  (Los lanzadores están en: {prefix})")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"\nError durante la instalación: {e}", file=sys.stderr)
        sys.exit(1)
