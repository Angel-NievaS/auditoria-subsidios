# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para Auditoría de Subsidios.

Para construir el ejecutable:
    .venv\Scripts\pyinstaller auditoria.spec

El resultado queda en dist\Auditoria Subsidios\
"""
import glob
import os

TESS_DIR = r"C:\Program Files\Tesseract-OCR"
TESS_DATA = os.path.join(TESS_DIR, "tessdata")

# ── Archivos de datos ────────────────────────────────────────────────────────
datas = [
    ("templates",  "templates"),
    ("static",     "static"),
    # Ejecutable de Tesseract
    (os.path.join(TESS_DIR, "tesseract.exe"), "tesseract"),
    # Modelos de idioma (sólo los necesarios)
    (os.path.join(TESS_DATA, "spa.traineddata"), "tessdata"),
    (os.path.join(TESS_DATA, "eng.traineddata"), "tessdata"),
    (os.path.join(TESS_DATA, "osd.traineddata"), "tessdata"),
    (os.path.join(TESS_DATA, "pdf.ttf"),          "tessdata"),
]

# ── DLLs de Tesseract (todas las del directorio de instalación) ──────────────
binaries = [
    (dll, "tesseract")
    for dll in glob.glob(os.path.join(TESS_DIR, "*.dll"))
]

# ── Análisis ─────────────────────────────────────────────────────────────────
a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # pdfplumber y dependencias
        "pdfminer",
        "pdfminer.high_level",
        "pdfminer.layout",
        "pdfminer.converter",
        "pdfminer.pdfpage",
        "pdfplumber",
        # PyMuPDF
        "fitz",
        # Imagen
        "PIL",
        "PIL.Image",
        "PIL.ImageEnhance",
        "PIL.ImageFilter",
        # OCR
        "pytesseract",
        # Excel
        "openpyxl",
        "openpyxl.styles",
        "openpyxl.utils",
        # Flask y dependencias
        "flask",
        "jinja2",
        "jinja2.ext",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.routing",
        # Módulos internos (asegurar inclusión completa)
        "src.domain.models",
        "src.domain.auditor",
        "src.export.excel_exporter",
        "src.parsing.classifier",
        "src.parsing.extractors.base",
        "src.parsing.extractors.liquidacion",
        "src.parsing.extractors.certificado_v1",
        "src.parsing.extractors.certificado_v2",
        "src.parsing.extractors.comprobante_ocr",
        "src.services.analysis_service",
        "src.sources.base",
        "src.sources.local_source",
        "src.sources.drive_source",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Auditoria Subsidios",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # consola visible: muestra logs de Flask y errores de inicio
    icon="icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Auditoria Subsidios",
)
