"""Formato 4: Certificado de Pago BancoEstado v2 (~200 KB, texto). Nombre puede estar incompleto."""
import re

from src.domain.models import Comprobante
from .base import Extractor, extraer_texto_pdf, normalizar_fecha, normalizar_monto, normalizar_rut, numero_cuenta_desde_rut


class CertificadoV2Extractor(Extractor):
    def extract(self, pdf_bytes: bytes, link: str) -> Comprobante:
        texto = extraer_texto_pdf(pdf_bytes)

        rut = normalizar_rut(_buscar_rut(texto))
        monto = normalizar_monto(_buscar_monto(texto))
        fecha = normalizar_fecha(_buscar_fecha(texto))
        banco = _buscar_banco(texto)
        nombre = _buscar_nombre(texto)

        # En este formato "Forma Pago" describe la modalidad de transferencia bancaria,
        # no el tipo de cuenta del beneficiario. Como el banco es siempre BancoEstado,
        # la cuenta es CuentaRUT y el número se deriva del cuerpo del RUT.
        tipo_cuenta = "CuentaRUT"
        num_cuenta = numero_cuenta_desde_rut(rut)

        incompleto = any(v is None for v in [rut, monto, fecha])

        return Comprobante(
            archivo="",
            semana=None,
            indice_pago=1,
            tipo_documento="certificado_v2",
            nombre_beneficiario=nombre,
            rut_beneficiario=rut,
            monto=monto,
            tipo_cuenta=tipo_cuenta,
            numero_cuenta=num_cuenta,
            numero_operacion=None,
            banco=banco,
            fecha_pago=fecha,
            estado_pago="Pagado",
            datos_incompletos=incompleto,
            fuente="texto",
            nota=None if nombre else "Nombre de beneficiario no disponible en este formato",
            link=link,
        )


def _buscar_rut(texto: str) -> str | None:
    from config import RUT_EMPRESA
    rut_empresa_digits = re.sub(r"[^\dkK]", "", RUT_EMPRESA)

    # "Rut Benef." o "Rut Benef:" — la etiqueta termina con punto o dos puntos
    # El valor puede estar en la misma línea o en la siguiente
    m = re.search(r"Rut\s+Benef\.?\s*[:\s]\s*(\d[\d\.]*-[\dkK])", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"Rut\s+Benef\.?\s*\n\s*(\d[\d\.]*-[\dkK])", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Fallback: RUT con puntos (formato estándar)
    for r in re.findall(r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", texto):
        if r != RUT_EMPRESA:
            return r

    # Fallback: RUT sin puntos (7-8 dígitos + guión + dígito/k)
    for match in re.finditer(r"\b(\d{7,8})-([0-9kK])\b", texto):
        cuerpo, dv = match.group(1), match.group(2)
        if (cuerpo + dv).upper() != rut_empresa_digits.upper():
            return f"{cuerpo}-{dv}"

    return None


def _buscar_monto(texto: str) -> str | None:
    m = re.search(r"Monto\s+Pago[:\s]+\$?\s*([\d\.\s]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"Monto[:\s]+\$?\s*([\d\.]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _buscar_fecha(texto: str) -> str | None:
    # El valor puede estar en la misma línea o en la siguiente (estructura de tabla PDF)
    # Captura cualquier valor no-espacio después del label; normalizar_fecha lo interpreta
    m = re.search(r"Fecha\s+de\s+Pago[:\s]*\n?\s*(\S+)", texto, re.IGNORECASE)
    if m:
        candidato = m.group(1)
        # Descartar si el "valor" parece ser otra etiqueta (contiene letras del label)
        if not re.search(r"[A-Za-z]{3,}", candidato):
            return candidato  # número puro (ej: "20251229" o "15/03/2026")
        # Si tiene texto, intentar de todos modos
        return candidato

    # "Santiago viernes, 10 de abril de 2026" — puede haber día de semana entre Santiago y la fecha
    m = re.search(r"Santiago[^\n]*?(\d{1,2}\s+de\s+\w+\s+(?:de\s+)?\d{4,5})", texto, re.IGNORECASE)
    if m:
        return m.group(1)

    return None


def _buscar_banco(texto: str) -> str | None:
    # "Banco: B.ESTADO" — requiere dos puntos para evitar capturar "Banco Estado certifica"
    m = re.search(r"\bBanco\s*:\s*([^\s\n\r]+)", texto, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if val.upper().startswith("B.ESTADO") or val.upper() == "BANCOESTADO":
            return "BancoEstado"
        return val
    if re.search(r"BANCOESTADO", texto, re.IGNORECASE):
        return "BancoEstado"
    return None


def _buscar_nombre(texto: str) -> str | None:
    m = re.search(r"Nombre\s+Benef[:\s]+([A-ZÁÉÍÓÚÑ][^\n\r]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None
