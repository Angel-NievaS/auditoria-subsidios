"""Interfaz Extractor y helpers de normalización comunes a todos los formatos."""
import re
from abc import ABC, abstractmethod

from src.domain.models import Comprobante


class Extractor(ABC):
    @abstractmethod
    def extract(self, pdf_bytes: bytes, link: str) -> Comprobante: ...


def normalizar_monto(raw: str) -> int | None:
    """'$16.265' o '16.265' o '16265' -> 16265. None si no puede parsear."""
    if not raw:
        return None
    limpio = re.sub(r"[^\d]", "", raw)
    return int(limpio) if limpio else None


def normalizar_fecha(raw: str) -> str | None:
    """
    Convierte fechas al formato DD-MM-YYYY.
    Corrige errores tipográficos de año (ej: '22026' -> '2026').
    Acepta separadores . / - y meses en texto (español).
    """
    if not raw:
        return None

    MESES = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
        "ene": "01", "feb": "02", "mar": "03", "abr": "04",
        "may": "05", "jun": "06", "jul": "07", "ago": "08",
        "sep": "09", "oct": "10", "nov": "11", "dic": "12",
    }

    raw = raw.strip()

    # YYYYMMDD: "20251229" -> "29-12-2025"
    m = re.fullmatch(r"(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])", raw)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # "15 de marzo de 2026" o "15 de marzo 2026"
    m = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4,5})",
        raw, re.IGNORECASE
    )
    if m:
        dia, mes_txt, anio = m.group(1), m.group(2).lower(), m.group(3)
        mes = MESES.get(mes_txt)
        if mes:
            anio = _corregir_anio(anio)
            return f"{dia.zfill(2)}-{mes}-{anio}"

    # "DD/MM/YYYY", "DD-MM-YYYY", "DD.MM.YYYY"
    m = re.search(r"(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4,5})", raw)
    if m:
        dia, mes, anio = m.group(1), m.group(2), m.group(3)
        anio = _corregir_anio(anio)
        return f"{dia.zfill(2)}-{mes.zfill(2)}-{anio}"

    return None


def _corregir_anio(anio: str) -> str:
    """'22026' -> '2026', '2026' -> '2026'."""
    if len(anio) == 5 and anio.startswith("2"):
        return anio[1:]
    return anio


def normalizar_rut(raw: str) -> str | None:
    """Devuelve el RUT en formato XX.XXX.XXX-X o None."""
    if not raw:
        return None
    limpio = re.sub(r"[^\dkK]", "", raw)
    if len(limpio) < 7:
        return None
    cuerpo, dv = limpio[:-1], limpio[-1].upper()
    # formato con puntos
    cuerpo_fmt = re.sub(r"(\d)(?=(\d{3})+$)", r"\1.", cuerpo)
    return f"{cuerpo_fmt}-{dv}"


def numero_cuenta_desde_rut(rut: str | None) -> str | None:
    """CuentaRUT: el número de cuenta es el cuerpo del RUT sin dígito verificador ni puntos."""
    if not rut:
        return None
    m = re.match(r"^([\d\.]+)-", rut)
    if m:
        return re.sub(r"\.", "", m.group(1))
    return None


def extraer_texto_pdf(pdf_bytes: bytes) -> str:
    """Extrae texto completo del PDF con pdfplumber. Retorna string vacío si falla."""
    try:
        import pdfplumber, io
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            partes = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    partes.append(t)
            return "\n".join(partes)
    except Exception:
        return ""
