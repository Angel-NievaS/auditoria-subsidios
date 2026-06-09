"""Formato 3: Certificado de Pago BancoEstado v1 (~32-41 KB, texto)."""
import re

from src.domain.models import Comprobante
from .base import Extractor, extraer_texto_pdf, normalizar_fecha, normalizar_monto, normalizar_rut, numero_cuenta_desde_rut


class CertificadoV1Extractor(Extractor):
    def extract(self, pdf_bytes: bytes, link: str) -> Comprobante:
        texto = extraer_texto_pdf(pdf_bytes)

        nombre = _buscar_nombre(texto)
        rut = normalizar_rut(_buscar_rut(texto))
        monto = normalizar_monto(_buscar_monto(texto))
        fecha = normalizar_fecha(_buscar_fecha(texto))
        num_op = _buscar_num_deposito(texto)
        forma_pago = _buscar_forma_pago(texto)
        estado = _buscar_estado(texto)

        # _imprimir_resumen(...)  # traza desactivada

        incompleto = any(v is None for v in [nombre, rut, monto, fecha])

        return Comprobante(
            archivo="",
            semana=None,
            indice_pago=1,
            tipo_documento="certificado_v1",
            nombre_beneficiario=nombre,
            rut_beneficiario=rut,
            monto=monto,
            tipo_cuenta=forma_pago,
            numero_cuenta=numero_cuenta_desde_rut(rut),
            numero_operacion=num_op,
            banco="BancoEstado",
            fecha_pago=fecha,
            estado_pago=estado,
            datos_incompletos=incompleto,
            fuente="texto",
            nota=None,
            link=link,
        )


def _buscar_nombre(texto: str) -> str | None:
    # Formato certificado: "Nombre GISSELLE JAMILETTE BARRERA CONTRERAS" (línea propia)
    m = re.search(r"^Nombre\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:\r?\n|$)", texto, re.MULTILINE)
    if m:
        candidato = m.group(1).strip()
        # Excluir cabecera "Nombre Empresa SUSTANTIVA SPA"
        if "empresa" not in candidato.lower():
            return candidato
    # Formato inline: "Beneficiario: NOMBRE  Rut:" (nombre en la misma línea)
    m = re.search(r"Beneficiario[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?=\s*Rut\s*[:\s]|[\r\n]|$)", texto, re.IGNORECASE)
    if m:
        candidato = m.group(1).strip()
        if candidato.lower() != "beneficiario" and candidato:
            return candidato
    return None


def _buscar_rut(texto: str) -> str | None:
    from config import RUT_EMPRESA
    # Con puntos: "12.345.678-9"
    m = re.search(r"Rut[:\s]+(\d{1,2}\.\d{3}\.\d{3}-[\dkK])", texto, re.IGNORECASE)
    if m and m.group(1) != RUT_EMPRESA:
        return m.group(1)
    # Sin puntos: "12345678-9"
    m = re.search(r"Rut[:\s]+(\d{7,8}-[\dkK])", texto, re.IGNORECASE)
    if m:
        rut_empresa_digits = re.sub(r"[^\dkK]", "", RUT_EMPRESA)
        if re.sub(r"[^\dkK]", "", m.group(1)) != rut_empresa_digits:
            return m.group(1)
    ruts = re.findall(r"\d{1,2}\.\d{3}\.\d{3}-[\dkK]", texto)
    for r in ruts:
        if r != RUT_EMPRESA:
            return r
    return None


def _buscar_monto(texto: str) -> str | None:
    # "Monto $ $2.030" o "Monto $2.030" o "Monto: 2.030" — uno o más $ antes del número
    m = re.search(r"Monto[:\s]+[\$\s]*([\d\.]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _buscar_fecha(texto: str) -> str | None:
    m = re.search(r"Fecha\s+de\s+Pago[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4,5})", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    # Fecha al inicio "Nº DEPOSITO 123456  15/03/2026"
    m = re.search(r"N[°º]\s*DEPOSITO\s+\d+\s+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4,5})", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _buscar_num_deposito(texto: str) -> str | None:
    m = re.search(r"N[°º]\s*DEPOSITO\s+(\d+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    return None


def _buscar_forma_pago(texto: str) -> str | None:
    m = re.search(r"Forma\s+de\s+Pago[:\s]+([^\n\r]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _buscar_estado(texto: str) -> str | None:
    m = re.search(r"Estado\s+Pago[:\s]+([^\n\r]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Traza de diagnóstico
# ---------------------------------------------------------------------------

_CAMPOS_RESUMEN = [
    ("nombre",     "Nombre"),
    ("rut",        "RUT"),
    ("forma_pago", "Tipo cuenta"),
    ("monto",      "Monto"),
    ("fecha",      "Fecha"),
    ("estado",     "Estado"),
    ("num_op",     "N° depósito"),
]


def _imprimir_resumen(link: str, texto: str, datos: dict) -> None:
    m = re.search(r"semana\s*(\d+)", link, re.IGNORECASE)
    nombre_archivo = link.replace("\\", "/").split("/")[-1]
    semana_label = f"Semana {m.group(1)}" if m else nombre_archivo

    sep = "─" * 70
    print(f"\n┌{sep}")
    print(f"│ {semana_label}  [certificado_v1]  {nombre_archivo}")
    print(f"├{sep}")

    if texto.strip():
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
