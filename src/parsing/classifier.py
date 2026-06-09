"""Clasifica un PDF en uno de los 4 formatos conocidos por firmas de texto."""
from typing import Literal

from src.parsing.extractors.base import extraer_texto_pdf

DocType = Literal["liquidacion", "comprobante_ocr", "certificado_v1", "certificado_v2", "desconocido"]

RUT_EMPRESA = "76.697.561-5"


def classify(pdf_bytes: bytes) -> DocType:
    """Extrae texto con pdfplumber y retorna el tipo de documento."""
    texto = extraer_texto_pdf(pdf_bytes)

    if "LIQUIDACION DE PAGO" in texto:
        return "liquidacion"

    if "CERTIFICADO DE PAGO" in texto and "PS-SUSTANTIVA" in texto:
        return "certificado_v2"

    if ("CERTIFICADO PAGO" in texto or "CERTIFICADO DE PAGO" in texto) and "BANCOESTADO certifica" in texto:
        return "certificado_v1"

    if _es_comprobante_ocr(texto):
        return "comprobante_ocr"

    return "desconocido"


def _es_comprobante_ocr(texto: str) -> bool:
    """
    Formato 2: empieza con '600 660 0033' y NO trae monto ni RUT del beneficiario en el texto.
    El RUT de la empresa (76.697.561-5) no cuenta como RUT de beneficiario.
    """
    if "600 660 0033" not in texto:
        return False

    # Si tiene monto legible en texto -> no es Formato 2
    import re
    if re.search(r"\$\s*[\d\.]+", texto):
        # Verificar que no sea solo el RUT empresa repetido como texto
        texto_sin_empresa = texto.replace(RUT_EMPRESA, "")
        # Buscar RUT de beneficiario (distinto al de empresa)
        ruts = re.findall(r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", texto_sin_empresa)
        if ruts:
            return False

    return True
