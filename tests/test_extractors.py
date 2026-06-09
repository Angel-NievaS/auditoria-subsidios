"""Tests para clasificador y extractores (casos sintéticos de texto)."""
import io
import pytest


def _make_pdf(texto: str) -> bytes:
    """Genera un PDF mínimo con el texto dado; cada línea usa Td para salto real."""
    lineas = texto.split("\n")
    ops = [b"BT\n/F1 12 Tf\n50 750 Td\n"]
    for i, linea in enumerate(lineas):
        encoded = linea.encode("latin-1", errors="replace")
        ops.append(b"(" + encoded + b") Tj\n")
        if i < len(lineas) - 1:
            ops.append(b"0 -15 Td\n")
    ops.append(b"ET\n")
    stream = b"".join(ops)
    resources = b"<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>"
    page_content = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R /Resources " + resources + b" >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream\nendobj\n"
    )
    xref_offset = len(b"%PDF-1.4\n") + len(page_content)
    pdf = (
        b"%PDF-1.4\n"
        + page_content
        + b"xref\n0 5\n0000000000 65535 f \n"
        + b"trailer\n<< /Size 5 /Root 1 0 R >>\n"
        + b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    )
    return pdf


# ---- Classifier ----

class TestClassifier:
    def test_clasifica_liquidacion(self):
        from src.parsing.classifier import classify
        pdf = _make_pdf("LIQUIDACION DE PAGO\nSUSTANTIVA SPA")
        assert classify(pdf) == "liquidacion"

    def test_clasifica_certificado_v2(self):
        from src.parsing.classifier import classify
        pdf = _make_pdf("CERTIFICADO DE PAGO\nPS-SUSTANTIVA")
        assert classify(pdf) == "certificado_v2"

    def test_clasifica_certificado_v1(self):
        from src.parsing.classifier import classify
        pdf = _make_pdf("CERTIFICADO PAGO\nBANCOESTADO certifica")
        assert classify(pdf) == "certificado_v1"

    def test_clasifica_desconocido(self):
        from src.parsing.classifier import classify
        pdf = _make_pdf("Texto sin firmas reconocidas")
        assert classify(pdf) == "desconocido"


# ---- Normalización ----

class TestNormalizacion:
    def test_normalizar_monto_con_puntos(self):
        from src.parsing.extractors.base import normalizar_monto
        assert normalizar_monto("$16.265") == 16265

    def test_normalizar_monto_sin_signo(self):
        from src.parsing.extractors.base import normalizar_monto
        assert normalizar_monto("16265") == 16265

    def test_normalizar_monto_none(self):
        from src.parsing.extractors.base import normalizar_monto
        assert normalizar_monto("") is None

    def test_normalizar_fecha_ddmmyyyy(self):
        from src.parsing.extractors.base import normalizar_fecha
        assert normalizar_fecha("15/03/2026") == "15-03-2026"

    def test_normalizar_fecha_typo_anio(self):
        from src.parsing.extractors.base import normalizar_fecha
        assert normalizar_fecha("15/03/22026") == "15-03-2026"

    def test_normalizar_fecha_texto(self):
        from src.parsing.extractors.base import normalizar_fecha
        assert normalizar_fecha("15 de marzo de 2026") == "15-03-2026"

    def test_normalizar_rut(self):
        from src.parsing.extractors.base import normalizar_rut
        assert normalizar_rut("12345678-9") == "12.345.678-9"

    def test_normalizar_rut_ya_formateado(self):
        from src.parsing.extractors.base import normalizar_rut
        assert normalizar_rut("12.345.678-9") == "12.345.678-9"

    def test_normalizar_rut_none(self):
        from src.parsing.extractors.base import normalizar_rut
        assert normalizar_rut("") is None


# ---- Extractores con texto sintético ----

class TestLiquidacionExtractor:
    def test_extrae_campos_completos(self):
        from src.parsing.extractors.liquidacion import LiquidacionExtractor
        texto = (
            "LIQUIDACION DE PAGO\n"
            "SUSTANTIVA SPA 01/03/2026\n"
            "JUAN PEREZ GARCIA  12.345.678-9\n"
            "987654321\n"
            "$16.265  Total Liquido a pagar\n"
            "Abono en CuentaRUT BANCOESTADO 01/03/2026\n"
        )
        pdf = _make_pdf(texto)
        c = LiquidacionExtractor().extract(pdf, "/ruta/test.pdf")
        assert c.monto == 16265
        assert c.tipo_cuenta == "CuentaRUT"
        assert c.banco == "BancoEstado"
        assert c.fecha_pago == "01-03-2026"

    def test_rut_sin_puntos(self):
        """RUT sin puntos en el PDF debe normalizarse igual."""
        from src.parsing.extractors.liquidacion import LiquidacionExtractor
        texto = (
            "LIQUIDACION DE PAGO\n"
            "SUSTANTIVA SPA 10-11-2025\n"
            "ALEXANDER JOSE VALLADARES PENAILILLO 18544100-8\n"
            "Nombre Beneficiario Rut Beneficiario\n"
            " $ 28.726\n"
            "Identificador de Pago Total Liquido a pagar\n"
            "Abono en CuentaRUT 903501130 BANCOESTADO  10-11-2025\n"
            "Modalidad de Pago Numero de operacion Banco Sucursal de pago Fecha de Cobro\n"
        )
        pdf = _make_pdf(texto)
        c = LiquidacionExtractor().extract(pdf, "/ruta/test.pdf")
        assert c.rut_beneficiario == "18.544.100-8"
        assert c.monto == 28726
        assert c.numero_operacion == "903501130"
        assert c.numero_cuenta == "18544100"
        assert c.fecha_pago == "10-11-2025"

    def test_monto_en_linea_separada_de_etiqueta(self):
        """Monto y 'Total Líquido a pagar' en líneas distintas (estructura de tabla real)."""
        from src.parsing.extractors.liquidacion import LiquidacionExtractor
        texto = (
            "LIQUIDACION DE PAGO\n"
            "SUSTANTIVA SPA\n"
            "MARIA LOPEZ 98.765.432-1\n"
            "$ 5.367\n"
            "Identificador de Pago Total Liquido a pagar\n"
            "Abono en CuentaRUT 926222447 BANCOESTADO  02/02/22026\n"
        )
        pdf = _make_pdf(texto)
        c = LiquidacionExtractor().extract(pdf, "/ruta/test.pdf")
        assert c.monto == 5367
        assert c.fecha_pago == "02-02-2026"  # corrige typo de año

    def test_numero_cuenta_cuentarut(self):
        """Si es CuentaRUT, numero_cuenta = cuerpo del RUT."""
        from src.parsing.extractors.base import numero_cuenta_desde_rut
        assert numero_cuenta_desde_rut("18.544.100-8") == "18544100"
        assert numero_cuenta_desde_rut("12.345.678-9") == "12345678"
        assert numero_cuenta_desde_rut(None) is None


class TestComprobanteOCRExtractor:
    def test_extrae_desde_texto(self):
        """Cuando el PDF tiene texto legible no debe necesitar OCR."""
        from src.parsing.extractors.comprobante_ocr import ComprobanteOCRExtractor
        texto = (
            "600 660 0033 | soportei@bancoestado.cl  Fecha - Hora\n"
            "29/12/2025 - 21:50\n"
            "Nombre Empresa SUSTANTIVA SPA  Rut Empresa 76.697.561-5\n"
            "Nombre Usuario ROBERTO ALEJANDRO SOTO  Rut Usuario 13.234.530-9\n"
            "Comprobante Transferencia Electronica\n"
            "Detalle Transferencia Electronica | N 7014989\n"
            "Fecha Transaccion\n"
            "27/10/2025\n"
            "ID TEF\n"
            "1932545253\n"
            "Estado\n"
            "Autorizada\n"
            "Beneficiario\n"
            "185441008\n"
            "ALEXANDER JOS VALLADARES PEAILILLO | 18.544.100-8 | BANCO DEL ESTADO DE CHILE | Cuenta Rut 00000000018544100\n"
            "Alexanderjose.ing@gmail.com\n"
            "Monto\n"
            "$2.488\n"
        )
        pdf = _make_pdf(texto)
        c = ComprobanteOCRExtractor().extract(pdf, "/ruta/test.pdf")
        assert c.fuente == "texto"
        assert c.rut_beneficiario == "18.544.100-8"
        assert c.nombre_beneficiario == "ALEXANDER JOS VALLADARES PEAILILLO"
        assert c.monto == 2488
        assert c.numero_operacion == "1932545253"
        assert c.fecha_pago == "27-10-2025"
        assert c.tipo_cuenta == "CuentaRUT"
        assert c.numero_cuenta == "18544100"
        assert c.banco == "BancoEstado"

    def test_no_captura_rut_usuario(self):
        """El Rut Usuario del encabezado no debe confundirse con el RUT del beneficiario."""
        from src.parsing.extractors.comprobante_ocr import _buscar_rut_usuario
        texto = "Rut Usuario 13.234.530-9"
        assert _buscar_rut_usuario(texto) == "13.234.530-9"


class TestCertificadoV1Extractor:
    def test_extrae_campos_completos(self):
        from src.parsing.extractors.certificado_v1 import CertificadoV1Extractor
        texto = (
            "N° DEPOSITO 123456  15/03/2026\n"
            "CERTIFICADO PAGO\n"
            "BANCOESTADO certifica que nuestro cliente SUSTANTIVA SPA...\n"
            "Beneficiario: MARIA LOPEZ  Rut: 98.765.432-1\n"
            "Fecha de Pago: 15/03/2026  Monto: $32.000\n"
            "Forma de Pago: Abono en CuentaRUT\n"
            "Estado Pago: Pagado\n"
        )
        pdf = _make_pdf(texto)
        c = CertificadoV1Extractor().extract(pdf, "/ruta/test.pdf")
        assert c.monto == 32000
        assert c.rut_beneficiario == "98.765.432-1"
        assert c.nombre_beneficiario == "MARIA LOPEZ"
        assert c.estado_pago == "Pagado"


class TestCertificadoV2Extractor:
    def test_extrae_sin_nombre(self):
        from src.parsing.extractors.certificado_v2 import CertificadoV2Extractor
        texto = (
            "Santiago 10 de abril de 2026\n"
            "CERTIFICADO DE PAGO\n"
            "Banco Estado certifica... PS-SUSTANTIVA...\n"
            "Rut Benef: 11.222.333-4  Fecha de Pago: 10/04/2026\n"
            "Monto Pago: 18.500  Forma Pago: CUENTA CORRIENTE\n"
            "Nro Cuenta: 00012345  Banco: B.ESTADO  Estado: ACEPTADO\n"
        )
        pdf = _make_pdf(texto)
        c = CertificadoV2Extractor().extract(pdf, "/ruta/test.pdf")
        assert c.monto == 18500
        assert c.estado_pago == "Pagado"
        assert c.banco == "BancoEstado"
        # Forma Pago no es tipo_cuenta; siempre es CuentaRUT al ser BancoEstado
        assert c.tipo_cuenta == "CuentaRUT"
        assert c.numero_cuenta == "11222333"  # cuerpo del RUT

    def test_fecha_yyyymmdd(self):
        from src.parsing.extractors.certificado_v2 import CertificadoV2Extractor
        texto = (
            "Santiago\n"
            "viernes, 10 de abril de 2026\n"
            "CERTIFICADO DE PAGO\n"
            "Banco Estado certifica... PS-SUSTANTIVA...\n"
            "Rut Benef.\n"
            "18544100-8\n"
            "Fecha de Pago:\n"
            "20251229\n"
            "Monto Pago\n"
            "23402\n"
            "Banco: B.ESTADO\n"
            "Estado: ACEPTADO\n"
        )
        pdf = _make_pdf(texto)
        c = CertificadoV2Extractor().extract(pdf, "/ruta/test.pdf")
        assert c.rut_beneficiario == "18.544.100-8"
        assert c.fecha_pago == "29-12-2025"
        assert c.monto == 23402
        assert c.tipo_cuenta == "CuentaRUT"
        assert c.numero_cuenta == "18544100"
