#!/usr/bin/env python3
"""Generador del ícono de marca de NuvaConnect.

Diseño original con la paleta oficial de NuvaProd (cyan #00B4D8 → navy #03045E).
Motivo: dos nodos conectados = conexión remota, con un acento amarillo de la
alianza. Exporta:
  - installer/assets/nuvaconnect.png     (master 1024x1024)
  - installer/windows/nuvaconnect.ico    (multi-tamaño)
  - installer/macos/nuvaconnect.icns     (macOS)

Uso:  python installer/generate_icon.py
"""
import math
import os

from PIL import Image, ImageDraw

# --- Paleta oficial NuvaProd ------------------------------------------------
CYAN_LIGHT = (144, 224, 239)   # #90E0EF
CYAN = (0, 180, 216)           # #00B4D8
BLUE = (0, 119, 182)           # #0077B6
NAVY = (3, 4, 94)              # #03045E
YELLOW = (255, 195, 19)        # #FFC313 (acento alianza)
WHITE = (255, 255, 255)

SIZE = 1024
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def diagonal_gradient(size, stops):
    """Gradiente diagonal (esquina sup-izq -> inf-der) con varias paradas."""
    img = Image.new("RGB", (size, size))
    px = img.load()
    n = len(stops) - 1
    maxd = (size - 1) * 2
    for y in range(size):
        for x in range(size):
            t = (x + y) / maxd
            seg = min(int(t * n), n - 1)
            local = t * n - seg
            px[x, y] = _lerp(stops[seg], stops[seg + 1], local)
    return img


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make_master():
    # Fondo con gradiente de marca y esquinas redondeadas (estilo app icon).
    bg = diagonal_gradient(SIZE, [CYAN_LIGHT, CYAN, BLUE, NAVY])
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), rounded_mask(SIZE, int(SIZE * 0.22)))

    draw = ImageDraw.Draw(icon)

    # --- Motivo de "conexión remota": dos nodos unidos ---
    # Nodo grande (equipo controlado) e nodo pequeño (controlador), unidos.
    cx1, cy1 = int(SIZE * 0.34), int(SIZE * 0.40)   # nodo grande
    cx2, cy2 = int(SIZE * 0.68), int(SIZE * 0.66)   # nodo pequeño
    r1, r2 = int(SIZE * 0.115), int(SIZE * 0.075)

    # Línea de conexión (blanca, gruesa, con nodo amarillo de acento en medio)
    draw.line([cx1, cy1, cx2, cy2], fill=WHITE, width=int(SIZE * 0.045))

    # Punto medio con acento amarillo (paquete de datos viajando)
    mx, my = (cx1 + cx2) // 2, (cy1 + cy2) // 2
    rm = int(SIZE * 0.038)
    draw.ellipse([mx - rm, my - rm, mx + rm, my + rm], fill=YELLOW)

    # Nodos: anillo blanco relleno de color de marca (aro grueso)
    def node(cx, cy, r, fill):
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)
        ri = int(r * 0.62)
        draw.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=fill)

    node(cx1, cy1, r1, CYAN)
    node(cx2, cy2, r2, NAVY)

    return icon


def main():
    assets = os.path.join(ROOT, "installer", "assets")
    os.makedirs(assets, exist_ok=True)
    master = make_master()

    png_path = os.path.join(assets, "nuvaconnect.png")
    master.save(png_path)
    print("PNG master  ->", png_path)

    # .ico multi-tamaño (Windows)
    ico_path = os.path.join(ROOT, "installer", "windows", "nuvaconnect.ico")
    master.save(ico_path, format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ICO Windows ->", ico_path)

    # .icns (macOS) — Pillow genera el contenedor con múltiples resoluciones
    icns_path = os.path.join(ROOT, "installer", "macos", "nuvaconnect.icns")
    try:
        master.save(icns_path, format="ICNS")
        print("ICNS macOS  ->", icns_path)
    except Exception as e:  # noqa: BLE001
        print("Aviso: no se pudo generar .icns con Pillow:", e)
        print("       Usa 'iconutil' en un Mac o el iconset generado.")


if __name__ == "__main__":
    main()
