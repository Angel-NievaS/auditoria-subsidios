"""
Genera icon.ico para el ejecutable: un gatito auditor con corbata.
Ejecutar una vez antes de construir con PyInstaller:
    python make_icon.py
"""
from PIL import Image, ImageDraw


# ── Paleta ────────────────────────────────────────────────────────────────────
CARA       = (255, 205, 130)   # anaranjado claro
OREJA_INT  = (255, 165, 165)   # rosa oreja
OUTLINE    = (150, 110,  50)   # café contorno
OJO_FONDO  = (255, 255, 255)   # blanco del ojo
OJO_PUPILA = ( 45,  30,  15)   # café oscuro pupila
NARIZ      = (220,  90,  90)   # rosa nariz
BIGOTE     = (160, 130,  90)   # beige bigote
CORBATA    = ( 30,  70, 180)   # azul corbata
CORBATA_D  = ( 20,  50, 130)   # azul oscuro (sombra corbata)


def dibujar_gato(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)
    s   = size
    cx  = s // 2
    cy  = s // 2

    fr  = int(s * 0.38)   # radio cara
    lw  = max(1, s // 64) # grosor líneas

    # ── Orejas (dibujadas antes de la cara para que queden detrás) ─────────────
    ear_h = int(s * 0.23)
    ear_w = int(s * 0.17)
    ear_y = cy - fr + int(s * 0.06)

    for signo in (-1, 1):
        ex = cx + signo * int(s * 0.22)
        # Oreja exterior
        d.polygon([
            (ex,                    ear_y),
            (ex + signo * ear_w,    ear_y),
            (ex + signo * ear_w//2, ear_y - ear_h),
        ], fill=CARA, outline=OUTLINE)
        # Oreja interior (rosa)
        off = int(ear_w * 0.22)
        d.polygon([
            (ex + signo * off,                    ear_y - int(ear_h * 0.15)),
            (ex + signo * (ear_w - off),           ear_y - int(ear_h * 0.15)),
            (ex + signo * (ear_w//2),              ear_y - int(ear_h * 0.78)),
        ], fill=OREJA_INT)

    # ── Cara ──────────────────────────────────────────────────────────────────
    d.ellipse([cx - fr, cy - fr, cx + fr, cy + fr],
              fill=CARA, outline=OUTLINE, width=lw)

    # ── Ojos ─────────────────────────────────────────────────────────────────
    ey  = cy - int(s * 0.07)
    exo = int(s * 0.115)
    er  = int(s * 0.072)
    pr  = int(er * 0.62)
    sr  = max(2, int(pr * 0.38))

    for signo in (-1, 1):
        ox = cx + signo * exo
        d.ellipse([ox - er, ey - er, ox + er, ey + er],
                  fill=OJO_FONDO, outline=OUTLINE, width=lw)
        d.ellipse([ox - pr, ey - pr, ox + pr, ey + pr], fill=OJO_PUPILA)
        # Brillo
        d.ellipse([ox - pr + sr, ey - pr + sr,
                   ox - pr + sr * 2, ey - pr + sr * 2], fill="white")

    # ── Nariz ────────────────────────────────────────────────────────────────
    ny = cy + int(s * 0.055)
    ns = int(s * 0.042)
    d.polygon([(cx, ny - ns), (cx - ns, ny + ns // 2), (cx + ns, ny + ns // 2)],
              fill=NARIZ, outline=OUTLINE)

    # ── Boca ─────────────────────────────────────────────────────────────────
    my  = ny + int(s * 0.035)
    mw  = int(s * 0.062)
    mh  = int(s * 0.045)
    for signo in (-1, 1):
        bx0 = cx + signo * 2
        bx1 = cx + signo * (mw + 2)
        d.arc([min(bx0, bx1) - 1, my - mh // 2,
               max(bx0, bx1) + 1, my + mh // 2],
              start=0, end=180, fill=OUTLINE, width=lw)

    # ── Bigotes ───────────────────────────────────────────────────────────────
    wy1  = ny + int(s * 0.005)
    wy2  = ny + int(s * 0.055)
    wlen = int(s * 0.28)
    wxs  = int(s * 0.055)

    for signo in (-1, 1):
        xs = cx + signo * wxs
        xe = cx + signo * (wxs + wlen)
        d.line([xs, wy1, xe, wy1 - int(s * 0.025)], fill=BIGOTE, width=lw)
        d.line([xs, wy2, xe, wy2 + int(s * 0.025)], fill=BIGOTE, width=lw)

    # ── Corbata (detalle de auditor) ──────────────────────────────────────────
    ty   = cy + fr - int(s * 0.20)   # arranque corbata (sobre el borde cara)
    tkw  = int(s * 0.075)            # ancho nudo
    tkh  = int(s * 0.055)            # alto nudo
    tw   = int(s * 0.10)             # ancho cuerpo inferior
    th   = int(s * 0.115)            # largo cuerpo inferior

    # Parte superior (triángulo invertido)
    d.polygon([
        (cx - tw, ty - int(th * 0.35)),
        (cx + tw, ty - int(th * 0.35)),
        (cx + tkw, ty),
        (cx - tkw, ty),
    ], fill=CORBATA)
    # Nudo
    d.rectangle([cx - tkw, ty, cx + tkw, ty + tkh],
                fill=CORBATA_D, outline=OUTLINE, width=lw)
    # Cuerpo inferior (trapezoide)
    d.polygon([
        (cx - tkw,      ty + tkh),
        (cx + tkw,      ty + tkh),
        (cx + tw,       ty + tkh + th),
        (cx - tw,       ty + tkh + th),
    ], fill=CORBATA, outline=OUTLINE)
    # Punta
    d.polygon([
        (cx - tw,       ty + tkh + th),
        (cx + tw,       ty + tkh + th),
        (cx,            ty + tkh + th + int(th * 0.35)),
    ], fill=CORBATA, outline=OUTLINE)

    return img


# ── Escribir ICO multi-tamaño manualmente ─────────────────────────────────────
# Pillow no escribe ICO con múltiples tamaños de forma confiable.
# Este escritor codifica cada imagen como PNG y las combina en un ICO válido.
import io
import os
import struct


def guardar_ico(imagenes: list, ruta: str) -> None:
    """Guarda una lista de PIL Images como archivo ICO multi-tamaño."""
    pngs = []
    for img in imagenes:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        pngs.append(buf.getvalue())

    n = len(imagenes)
    directorio_size = 6 + n * 16  # header + n entradas de 16 bytes
    offsets = []
    offset = directorio_size
    for data in pngs:
        offsets.append(offset)
        offset += len(data)

    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, n))  # ICONDIR

    for i, img in enumerate(imagenes):
        w, h = img.size
        # En ICO, 256 se codifica como 0
        out.write(struct.pack(
            "<BBBBHHLL",
            0 if w == 256 else w,
            0 if h == 256 else h,
            0, 0,           # colorCount, reserved
            1, 32,          # planes, bitCount
            len(pngs[i]),
            offsets[i],
        ))

    for data in pngs:
        out.write(data)

    with open(ruta, "wb") as f:
        f.write(out.getvalue())


SIZES  = [256, 128, 64, 48, 32, 16]
frames = [dibujar_gato(s) for s in SIZES]
output = "icon.ico"
guardar_ico(frames, output)

kb = os.path.getsize(output) // 1024
print(f"Generado: {output}  ({kb} KB)  tamaños: {SIZES}")
