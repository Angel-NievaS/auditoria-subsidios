"""Formato 2: Comprobante Transferencia Electrónica BancoEstado.
Estrategia: texto (pdfplumber) → OCR (Tesseract) → revisión manual.
"""
import re

from src.domain.models import Alerta, Comprobante
from .base import (
    Extractor, extraer_texto_pdf,
    normalizar_fecha, normalizar_monto, normalizar_rut,
    numero_cuenta_desde_rut,
)

RUT_EMPRESA = "76.697.561-5"


class ComprobanteOCRExtractor(Extractor):
    def extract(self, pdf_bytes: bytes, link: str) -> Comprobante:
        texto = extraer_texto_pdf(pdf_bytes)

        # Intento 1: extraer desde texto (PDFs más recientes sí tienen texto)
        datos = _extraer_datos(texto)
        ocr_error = None
        texto_usado = texto

        if datos.get("rut") or datos.get("monto"):
            fuente = "texto"
            alertas: list[Alerta] = []
            nota = None
        else:
            # Intento 2: OCR con Tesseract
            ocr_texto, ocr_error = self._ocr_text(pdf_bytes)
            if ocr_texto:
                datos = _extraer_datos(ocr_texto)
                fuente = "ocr"
                texto_usado = ocr_texto
                alertas = []
                nota = None
            else:
                fuente = "manual"
                if ocr_error:
                    nota = f"OCR falló: {ocr_error}"
                else:
                    nota = "OCR no disponible. Revisar manualmente."
                alertas = [Alerta("⚠️", "warn", f"Datos en imagen — revisar manualmente: {link}")]

        # _imprimir_resumen(link, fuente, datos, texto_usado, ocr_error)  # traza desactivada

        rut = normalizar_rut(datos.get("rut"))

        # Banco, tipo de cuenta y número de cuenta desde el documento
        banco_doc = datos.get("banco") or "BancoEstado"
        num_cuenta_raw = datos.get("num_cuenta_raw")

        if "estado" in banco_doc.lower():
            banco = "BancoEstado"
            tipo_cuenta = "CuentaRUT"
            num_cuenta = num_cuenta_raw or numero_cuenta_desde_rut(rut)
        else:
            banco = banco_doc
            tipo_cuenta = datos.get("tipo_cuenta")  # None si no se detectó explícitamente
            num_cuenta = num_cuenta_raw

        incompleto = fuente == "manual" or not rut or not datos.get("monto")

        return Comprobante(
            archivo="",
            semana=None,
            indice_pago=1,
            tipo_documento="comprobante_ocr",
            nombre_beneficiario=datos.get("nombre"),
            rut_beneficiario=rut,
            monto=normalizar_monto(datos.get("monto")),
            tipo_cuenta=tipo_cuenta,
            numero_cuenta=num_cuenta,
            numero_operacion=datos.get("num_op"),
            banco=banco,
            fecha_pago=normalizar_fecha(datos.get("fecha")),
            estado_pago=datos.get("estado", "Pagado"),
            datos_incompletos=incompleto,
            fuente=fuente,
            nota=nota,
            link=link,
            alertas=alertas,
        )

    def _ocr_text(self, pdf_bytes: bytes) -> tuple[str | None, str | None]:
        """
        Rasteriza con PyMuPDF y corre Tesseract.
        Retorna (texto, None) si tiene éxito, o (None, motivo_error) si falla.
        """
        try:
            import os
            import fitz
            import pytesseract
            from PIL import Image
            from config import TESSERACT_CMD

            # Configurar ruta a Tesseract si existe el archivo (Windows)
            if TESSERACT_CMD and os.path.isfile(TESSERACT_CMD):
                pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

            from PIL import ImageEnhance, ImageFilter

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            partes = []
            for page in doc:
                mat = fitz.Matrix(200 / 72, 200 / 72)  # 200 dpi
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                img = _preprocesar_imagen(img)
                partes.append(pytesseract.image_to_string(img, lang="spa", config="--oem 1 --psm 6"))
                # salir si ya se extrajeron los campos clave
                texto_parcial = "\n".join(partes)
                datos_parcial = _extraer_datos(texto_parcial)
                if datos_parcial.get("rut") and datos_parcial.get("monto"):
                    break
            doc.close()
            return "\n".join(partes), None

        except Exception as exc:
            return None, str(exc)


# ---------------------------------------------------------------------------
# Preprocesamiento de imagen para mejorar calidad OCR
# ---------------------------------------------------------------------------

def _preprocesar_imagen(img):
    """
    Pipeline de mejora de imagen antes de Tesseract:
      1. Contraste x2  → texto más negro, fondo más blanco
      2. Enfoque (UnsharpMask) → bordes de caracteres más nítidos
      3. Binarización con umbral fijo → elimina ruido de fondo gris
    """
    from PIL import ImageEnhance, ImageFilter
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
    img = img.point(lambda x: 255 if x > 140 else 0)
    return img


# ---------------------------------------------------------------------------
# Extracción de datos desde texto (texto pdfplumber u OCR)
# ---------------------------------------------------------------------------

def _extraer_datos(texto: str) -> dict:
    datos: dict[str, str] = {}

    # --- Fecha de transacción ---
    # El encabezado puede ser "Fecha Transacción" o "Fecha Preparación TEF" (según versión del PDF).
    # En ambos casos el valor queda en la línea siguiente junto al ID TEF y Estado.
    # Permite hasta 2 líneas basura de OCR entre el encabezado y la fecha
    m = re.search(
        r"Fecha\s+(?:Transac\w*|Preparaci\w*\s+TEF)[^\n]*(?:\n[^\n]{0,30}){0,2}\n\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4,5})",
        texto, re.IGNORECASE
    )
    if m:
        datos["fecha"] = m.group(1)

    # --- ID TEF → numero_operacion ---
    # El valor está en la línea siguiente al encabezado, después de la fecha+hora:
    # "27/10/2025 - 18:00 1932545253"
    # Se requieren 8+ dígitos para distinguirlo de los números de la fecha (27, 10, 2025).
    # OCR puede leer "1D TEF" en vez de "ID TEF".
    m = re.search(r"[I1]D\s+TEF[^\n]*\n[^\n]*?(\d{8,})", texto, re.IGNORECASE)
    if m:
        datos["num_op"] = m.group(1)
    else:
        # N° del encabezado de detalle: "N° 7014989" o "N" Operación 7024363"
        # OCR puede usar *, ", º como sustitutos de °; puede incluir la palabra "Operación"
        m = re.search(r"N[°º*\"]\s*(?:Operaci[oó]n\s+)?(\d{5,})", texto)
        if m:
            datos["num_op"] = m.group(1)

    # --- Estado ---
    # Caso 1: "Estado: Autorizada" o "Estado\nAutorizada" (valor inmediato)
    m = re.search(r"\bEstado\b[:\s]*\n?\s*(Autorizada|Autorizado|Pagado|Aceptado|Rechazado)",
                  texto, re.IGNORECASE)
    if not m:
        # Caso 2: "Estado" como encabezado de columna; valor al final de la fila de datos.
        # OCR puede insertar 1-2 líneas basura entre el encabezado y la fila con el valor.
        m = re.search(r"\bEstado\b[^\n]*(?:\n[^\n]{0,50}){0,2}\n[^\n]*(Autorizada|Autorizado|Pagado|Aceptado|Rechazado)",
                      texto, re.IGNORECASE)
    if m:
        datos["estado"] = m.group(1).capitalize()

    # --- Línea de beneficiario ---
    # Formato A (4 pipes): "NOMBRE | RUT | BANCO | Cuenta Rut/Corriente/Chequera Electronica NUMERO"
    # Formato B (3 pipes): "NOMBRE | RUT | BANCO NUMERO"
    # El primer separador puede ser '[' por error OCR (confusión con '|').
    m4 = re.search(
        r"([^\n|\[]+?)\s*[|\[]\s*(\d[\d\.]*-[\dkK])\s*\|\s*([^\|\n]+?)\s*\|\s*([A-Za-záéíóúÁÉÍÓÚñÑ]+(?:\s+[A-Za-záéíóúÁÉÍÓÚñÑ]+)*)\s+(\d+)",
        texto, re.IGNORECASE,
    )
    m3 = None if m4 else re.search(
        r"([^\n|\[]+?)\s*[|\[]\s*(\d[\d\.]*-[\dkK])\s*\|\s*([^\d\n|][^\n|]*?)\s+(\d{6,})\s*(?:\n|$)",
        texto, re.MULTILINE,
    )
    if m4:
        datos["rut"] = m4.group(2).strip()
        datos["banco"] = _normalizar_banco(m4.group(3))
        tipo_raw = m4.group(4).strip()
        datos["tipo_cuenta"] = _normalizar_tipo_cuenta(tipo_raw)
        datos["num_cuenta_raw"] = m4.group(5).lstrip("0") or "0"
        nombre_candidato = m4.group(1).strip()
        if not re.fullmatch(r"\d+", nombre_candidato):
            datos["nombre"] = nombre_candidato
    elif m3:
        datos["rut"] = m3.group(2).strip()
        datos["banco"] = _normalizar_banco(m3.group(3))
        datos["num_cuenta_raw"] = m3.group(4).lstrip("0") or "0"
        nombre_candidato = m3.group(1).strip()
        if not re.fullmatch(r"\d+", nombre_candidato):
            datos["nombre"] = nombre_candidato
    else:
        # Fallback: buscar RUT del beneficiario (distinto al de empresa y al Rut Usuario del header)
        rut_usuario = _buscar_rut_usuario(texto)
        rut_empresa_digits = re.sub(r"[^\dkK]", "", RUT_EMPRESA)
        for r in re.findall(r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", texto):
            digits = re.sub(r"[^\dkK]", "", r)
            if digits != rut_empresa_digits and r != rut_usuario:
                datos["rut"] = r
                break
        # Intento sin puntos
        if "rut" not in datos:
            for match in re.finditer(r"\b(\d{7,8})-([0-9kK])\b", texto):
                cuerpo, dv = match.group(1), match.group(2)
                digits = cuerpo + dv
                if digits != rut_empresa_digits:
                    rut_norm = normalizar_rut(f"{cuerpo}-{dv}")
                    if rut_norm != rut_usuario:
                        datos["rut"] = f"{cuerpo}-{dv}"
                        break

    # --- Nombre del beneficiario (si no se capturó desde la línea pipe) ---
    if "nombre" not in datos:
        # Anclar a inicio de línea para no capturar "Mensaje a Beneficiario"
        m = re.search(r"^Beneficiario\s*\n([A-ZÁÉÍÓÚÑ][^\n]+?)(?:\s*\||\s*$)",
                      texto, re.IGNORECASE | re.MULTILINE)
        if m:
            datos["nombre"] = m.group(1).strip()

    # --- Monto ---
    # "Monto\n$2.488" o "Monto $2.488" o "Monto\nConcepto\n$2.488"
    m = re.search(r"\bMonto\b[:\s]*\n?\s*\$?\s*([\d\.]+)", texto, re.IGNORECASE)
    if m:
        datos["monto"] = m.group(1)
    else:
        m = re.search(r"\$\s*([\d\.]+)", texto)
        if m:
            datos["monto"] = m.group(1)

    return datos


def _buscar_rut_usuario(texto: str) -> str | None:
    """Extrae el Rut Usuario del encabezado (es el originador, no el beneficiario)."""
    m = re.search(r"Rut\s+Usuario[:\s]+(\d{1,2}\.\d{3}\.\d{3}-[\dkK])", texto, re.IGNORECASE)
    return m.group(1) if m else None


def _normalizar_tipo_cuenta(raw: str) -> str:
    rl = raw.lower()
    if "rut" in rl:
        return "CuentaRUT"
    if "chequera" in rl:
        return "Chequera Electrónica"
    if "corriente" in rl:
        return "Cuenta Corriente"
    if "vista" in rl:
        return "Cuenta Vista"
    return raw.strip()


def _normalizar_banco(raw: str) -> str:
    raw_up = raw.upper().strip()
    if "ESTADO" in raw_up or "B.ESTADO" in raw_up:
        return "BancoEstado"
    if "BICE" in raw_up:
        return "Banco BICE"
    if "SANTANDER" in raw_up:
        return "Santander"
    if re.search(r"\bCHILE\b", raw_up) and "ESTADO" not in raw_up:
        return "Banco de Chile"
    if "SCOTIABANK" in raw_up:
        return "Scotiabank"
    if "FALABELLA" in raw_up:
        return "Banco Falabella"
    if re.search(r"ITAU|ITAÚ", raw_up):
        return "Itaú"
    if "TENPO" in raw_up:
        return "Tenpo Prepago"
    if "RIPLEY" in raw_up:
        return "Banco Ripley"
    if "SECURITY" in raw_up:
        return "Banco Security"
    if "INTERNACIONAL" in raw_up:
        return "Banco Internacional"
    if "CONSORCIO" in raw_up:
        return "Banco Consorcio"
    return raw.strip().title()


# ---------------------------------------------------------------------------
# Resumen de diagnóstico (se imprime para cada comprobante_ocr)
# ---------------------------------------------------------------------------

_CAMPOS_RESUMEN = [
    ("nombre",         "Nombre"),
    ("rut",            "RUT"),
    ("banco",          "Banco"),
    ("tipo_cuenta",    "Tipo cuenta"),
    ("num_cuenta_raw", "N° cuenta"),
    ("monto",          "Monto"),
    ("fecha",          "Fecha"),
    ("estado",         "Estado"),
    ("num_op",         "ID TEF"),
]


def _imprimir_resumen(
    link: str,
    fuente: str,
    datos: dict,
    texto: str,
    ocr_error: str | None,
) -> None:
    """Por cada comprobante_ocr: muestra el texto extraído y los campos obtenidos."""
    m = re.search(r"semana\s*(\d+)", link, re.IGNORECASE)
    nombre_archivo = link.replace("\\", "/").split("/")[-1]
    semana_label = f"Semana {m.group(1)}" if m else nombre_archivo

    sep = "─" * 70
    print(f"\n┌{sep}")
    print(f"│ {semana_label}  [{fuente}]  {nombre_archivo}")
    print(f"├{sep}")

    if ocr_error:
        print(f"│ [OCR ERROR: {ocr_error}]")
    elif texto.strip():
        for linea in texto.strip().splitlines():
            print(f"│ {linea}")
    else:
        print("│ [sin texto]")

    print(f"├{sep}")
    for clave, etiqueta in _CAMPOS_RESUMEN:
        v = datos.get(clave)
        marca = v if v else "✗"
        print(f"│   {etiqueta:<14}: {marca}")
    print(f"└{sep}")
