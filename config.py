import os
import sys

# RUT de SUSTANTIVA SPA (empresa emisora, no es RUT de beneficiario)
RUT_EMPRESA = "76.697.561-5"

TEMP_UPLOAD_DIR = "uploads_tmp"

# Ruta al ejecutable de Tesseract OCR.
# En modo ejecutable bundled, se usa el Tesseract incluido en el paquete.
# En desarrollo, se usa la instalación local de Windows.
def _tesseract_cmd() -> str | None:
    if hasattr(sys, "_MEIPASS"):
        bundled = os.path.join(sys._MEIPASS, "tesseract", "tesseract.exe")
        return bundled if os.path.exists(bundled) else None
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"

TESSERACT_CMD = _tesseract_cmd()
