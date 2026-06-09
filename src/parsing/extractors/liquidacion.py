"""Formato 1: Liquidación de Pago (~14 KB, texto). Parsing por texto + regex."""
import re

from src.domain.models import Comprobante
from .base import Extractor, extraer_texto_pdf, normalizar_fecha, normalizar_monto, normalizar_rut, numero_cuenta_desde_rut


class LiquidacionExtractor(Extractor):
    def extract(self, pdf_bytes: bytes, link: str) -> Comprobante:
        texto = extraer_texto_pdf(pdf_bytes)

        nombre = _buscar_nombre(texto)
        rut = normalizar_rut(_buscar_rut(texto))
        monto = normalizar_monto(_buscar_monto(texto))
        fecha = normalizar_fecha(_buscar_fecha_pago(texto))
        num_op = _buscar_num_operacion(texto)
        tipo_cuenta = _buscar_tipo_cuenta(texto)
        banco = _buscar_banco(texto)

        # Si es CuentaRUT, el número de cuenta es el cuerpo del RUT (sin dígito verificador)
        numero_cuenta = numero_cuenta_desde_rut(rut) if tipo_cuenta == "CuentaRUT" else None

        incompleto = any(v is None for v in [nombre, rut, monto, fecha])

        # _imprimir_resumen(link, texto, {...})  # traza desactivada

        return Comprobante(
            archivo="",
            semana=None,
            indice_pago=1,
            tipo_documento="liquidacion",
            nombre_beneficiario=nombre,
            rut_beneficiario=rut,
            monto=monto,
            tipo_cuenta=tipo_cuenta,
            numero_cuenta=numero_cuenta,
            numero_operacion=num_op,
            banco=banco,
            fecha_pago=fecha,
            estado_pago="Pagado",
            datos_incompletos=incompleto,
            fuente="texto",
            nota=None,
            link=link,
        )


def _buscar_nombre(texto: str) -> str | None:
    """
    Nombre y RUT están en celdas adyacentes de la tabla.
    pdfplumber los extrae en la misma línea (separados por espacio) o en líneas contiguas.
    El RUT puede venir con o sin puntos: "18.544.100-8" o "18544100-8".
    """
    # Con RUT con puntos en la misma línea: "NOMBRE  12.345.678-9"
    m = re.search(
        r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s+\d{1,2}\.\d{3}\.\d{3}-[\dkK]",
        texto, re.MULTILINE
    )
    if m:
        return m.group(1).strip()

    # Con RUT sin puntos en la misma línea: "NOMBRE  18544100-8"
    m = re.search(
        r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?)\s+\d{7,8}-[\dkK]\b",
        texto, re.MULTILINE
    )
    if m:
        return m.group(1).strip()

    # Nombre en línea propia seguido de la etiqueta "Nombre Beneficiario"
    m = re.search(
        r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{5,})\s*\n[^\n]*Nombre\s+Beneficiario",
        texto, re.MULTILINE | re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    return None


def _buscar_rut(texto: str) -> str | None:
    from config import RUT_EMPRESA
    rut_empresa_digits = re.sub(r"[^\dkK]", "", RUT_EMPRESA)

    # Primero buscar con puntos (más específico, menos falsos positivos)
    for r in re.findall(r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", texto):
        if r != RUT_EMPRESA:
            return r

    # Luego buscar sin puntos: 7-8 dígitos seguidos de guión y dígito/k
    for m in re.finditer(r"\b(\d{7,8})-([0-9kK])\b", texto):
        cuerpo, dv = m.group(1), m.group(2)
        if (cuerpo + dv).upper() != rut_empresa_digits.upper():
            return f"{cuerpo}-{dv}"

    return None


def _buscar_monto(texto: str) -> str | None:
    """
    En el PDF, el monto ($28.726) y su etiqueta 'Total Líquido a pagar' están en
    celdas separadas de la tabla, por lo que pdfplumber los puede poner en líneas distintas.
    Buscamos el $ amount que precede a la etiqueta dentro de ~150 caracteres.
    """
    # Mismo línea: "$ 28.726  Total Líquido a pagar"
    m = re.search(r"\$\s*([\d\.]+)\s+Total\s+L[ií]quido", texto, re.IGNORECASE)
    if m:
        return m.group(1)

    # Líneas separadas: buscamos $ amount cuyo contexto siguiente contiene "Total Líquido"
    for match in re.finditer(r"\$\s*([\d\.]+)", texto):
        contexto = texto[match.start(): match.start() + 150]
        if re.search(r"Total\s+L[ií]quido", contexto, re.IGNORECASE):
            return match.group(1)

    # Fallback: "Total Líquido a pagar" seguido del monto
    m = re.search(r"Total\s+L[ií]quido\s+a\s+pagar\s*\$?\s*([\d\.]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _buscar_fecha_pago(texto: str) -> str | None:
    # Fecha al final de la línea "Abono en ... BANCO... DD-MM-YYYY"
    m = re.search(
        r"^Abono\s+en\s+.+\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4,5})\s*$",
        texto, re.MULTILINE | re.IGNORECASE
    )
    if m:
        return m.group(1)
    # Fecha al final del documento
    m = re.search(r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4,5})\s*$", texto.strip())
    if m:
        return m.group(1)
    return None


def _buscar_num_operacion(texto: str) -> str | None:
    # "Abono en [tipo completo] [num] [BANCO]"
    # Incluye "Cuenta" solo (cuando el subtipo aparece en la línea siguiente)
    m = re.search(
        r"Abono\s+en\s+(?:CuentaRUT|Chequera\s+Electr[oó]nica|Cuenta\s+Vista|Cuenta\s+Corriente|Cuenta)"
        r"\s+(\d{6,})\s+(?:BANCOESTADO|BANCO)",
        texto, re.IGNORECASE
    )
    if m:
        return m.group(1)

    # Etiqueta explícita "Numero de operación: 123"
    m = re.search(r"N[°º]?\s*(?:de\s+)?[Oo]peraci[oó]n[:\s]+(\d+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _buscar_tipo_cuenta(texto: str) -> str | None:
    if re.search(r"Chequera\s+Electr[oó]nica", texto, re.IGNORECASE):
        return "Chequera Electrónica"
    if re.search(r"CuentaRUT", texto, re.IGNORECASE):
        return "CuentaRUT"
    if re.search(r"Cuenta\s+Vista", texto, re.IGNORECASE):
        return "Cuenta Vista"
    if re.search(r"Cuenta\s+Corriente", texto, re.IGNORECASE):
        return "Cuenta Corriente"
    # "Abono en Cuenta\nCorriente" — tipo partido en dos líneas
    if re.search(r"Abono\s+en\s+Cuenta\s+\d+\s+\S.*\n\s*Corriente", texto, re.IGNORECASE):
        return "Cuenta Corriente"
    if re.search(r"Abono\s+en\s+Cuenta\s+\d+\s+\S.*\n\s*Vista", texto, re.IGNORECASE):
        return "Cuenta Vista"
    return None


def _buscar_banco(texto: str) -> str | None:
    if "BANCOESTADO" in texto.upper():
        return "BancoEstado"
    if re.search(r"BANCO\s+DE\s+CHILE", texto, re.IGNORECASE):
        return "Banco de Chile"
    if re.search(r"BANCO\s+SANTANDER", texto, re.IGNORECASE):
        return "Santander"
    if re.search(r"BANCO\s+BICE\b", texto, re.IGNORECASE):
        return "Banco BICE"
    if re.search(r"SCOTIABANK", texto, re.IGNORECASE):
        return "Scotiabank"
    if re.search(r"ITAU|ITAÚ", texto, re.IGNORECASE):
        return "Itaú"
    # Banco en la línea de Abono (evita capturar encabezados de columna)
    m = re.search(
        r"^Abono\s+en\s+.+\s+(BANCO\s+[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)\s+\d{1,2}[-/\.]",
        texto, re.MULTILINE | re.IGNORECASE
    )
    if m:
        return m.group(1).strip().title()
    return None


# ---------------------------------------------------------------------------
# Traza de diagnóstico
# ---------------------------------------------------------------------------

_CAMPOS_RESUMEN = [
    ("nombre",      "Nombre"),
    ("rut",         "RUT"),
    ("tipo_cuenta", "Tipo cuenta"),
    ("banco",       "Banco"),
    ("monto",       "Monto"),
    ("fecha",       "Fecha"),
    ("num_op",      "N° operación"),
]


def _imprimir_resumen(link: str, texto: str, datos: dict) -> None:
    m = re.search(r"semana\s*(\d+)", link, re.IGNORECASE)
    nombre_archivo = link.replace("\\", "/").split("/")[-1]
    semana_label = f"Semana {m.group(1)}" if m else nombre_archivo

    sep = "─" * 70
    print(f"\n┌{sep}")
    print(f"│ {semana_label}  [liquidacion]  {nombre_archivo}")
    print(f"├{sep}")
    if texto.strip():
        for linea in texto.strip().splitlines():
            print(f"│ {linea}")
    else:
        print("│ [sin texto]")
    print(f"├{sep}")
    for clave, etiqueta in _CAMPOS_RESUMEN:
        v = datos.get(clave)
        print(f"│   {etiqueta:<14}: {v if v else '✗'}")
    print(f"└{sep}")


