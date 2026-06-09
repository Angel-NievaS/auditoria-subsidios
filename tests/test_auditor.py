"""Tests para reglas de auditoría."""
import pytest
from src.domain.models import Alerta, Comprobante
from src.domain.auditor import (
    _detectar_rut_inconsistente,
    _detectar_semanas_faltantes,
    _nombres_coinciden,
    auditar_alumno,
)


def _comp(**kwargs) -> Comprobante:
    defaults = dict(
        archivo="semana1.pdf", semana=1, indice_pago=1,
        tipo_documento="liquidacion",
        nombre_beneficiario="Juan Perez", rut_beneficiario="12.345.678-9",
        monto=16265, tipo_cuenta="CuentaRUT", numero_cuenta=None,
        numero_operacion=None, banco="BancoEstado",
        fecha_pago="01-03-2026", estado_pago="Pagado",
        datos_incompletos=False, fuente="texto", nota=None,
        link="/ruta/semana1.pdf",
    )
    defaults.update(kwargs)
    return Comprobante(**defaults)


class TestRutInconsistente:
    def test_detecta_rut_diferente(self):
        comps = [
            _comp(rut_beneficiario="12.345.678-9"),
            _comp(rut_beneficiario="98.765.432-1"),
        ]
        alertas = _detectar_rut_inconsistente(comps)
        assert any(a.severidad == "error" for a in alertas)

    def test_ok_mismo_rut(self):
        comps = [_comp(), _comp(semana=2)]
        assert _detectar_rut_inconsistente(comps) == []

    def test_ignora_none(self):
        comps = [_comp(rut_beneficiario=None), _comp(rut_beneficiario="12.345.678-9")]
        assert _detectar_rut_inconsistente(comps) == []


class TestNombreNoCoincide:
    def test_detecta_nombre_distinto(self):
        resultado = auditar_alumno("Carlos Gonzalez", [_comp(nombre_beneficiario="Pedro Ramirez")])
        alertas = [a for c in resultado.comprobantes for a in c.alertas if a.severidad == "error"]
        assert any("no coincide" in a.mensaje.lower() for a in alertas)

    def test_ok_nombre_con_tildes(self):
        # "José García" vs "Jose Garcia" -> deben coincidir
        resultado = auditar_alumno("Jose Garcia", [_comp(nombre_beneficiario="José García")])
        alertas = [a for c in resultado.comprobantes for a in c.alertas if a.severidad == "error"]
        assert not any("no coincide" in a.mensaje.lower() for a in alertas)

    def test_ok_nombre_parcial_dos_tokens(self):
        resultado = auditar_alumno("Juan Alberto Perez Soto", [_comp(nombre_beneficiario="Juan Perez")])
        alertas = [a for c in resultado.comprobantes for a in c.alertas if a.severidad == "error"]
        assert not any("no coincide" in a.mensaje.lower() for a in alertas)

    def test_tokens_significativos_excluyen_articulos(self):
        assert _nombres_coinciden("Juan de la Rosa", "Juan Rosa") is True


class TestDuplicados:
    def test_detecta_duplicado_exacto(self):
        c1 = _comp(semana=5, monto=16265, rut_beneficiario="12.345.678-9", fecha_pago="01-03-2026")
        c2 = _comp(semana=5, monto=16265, rut_beneficiario="12.345.678-9", fecha_pago="01-03-2026",
                   archivo="semana5_copia.pdf")
        resultado = auditar_alumno("Juan Perez", [c1, c2])
        alertas = [a for c in resultado.comprobantes for a in c.alertas if a.severidad == "error"]
        assert any("duplicado" in a.mensaje.lower() for a in alertas)

    def test_pagos_parciales_no_son_duplicados(self):
        # Mismo monto, misma fecha, pero uno tiene indice_pago=2 (parcial real)
        c1 = _comp(semana=5, indice_pago=1, monto=8000, fecha_pago="01-03-2026")
        c2 = _comp(semana=5, indice_pago=2, monto=8000, fecha_pago="08-03-2026",
                   archivo="semana5 (1).pdf")
        resultado = auditar_alumno("Juan Perez", [c1, c2])
        alertas = [a for c in resultado.comprobantes for a in c.alertas if a.severidad == "error"]
        assert not any("duplicado" in a.mensaje.lower() for a in alertas)


class TestSemanasFaltantes:
    def test_detecta_huecos(self):
        comps = [
            _comp(semana=1), _comp(semana=3), _comp(semana=5),
        ]
        faltantes = _detectar_semanas_faltantes(comps)
        assert 2 in faltantes
        assert 4 in faltantes
        assert 1 not in faltantes
        assert 3 not in faltantes

    def test_sin_huecos(self):
        comps = [_comp(semana=1), _comp(semana=2), _comp(semana=3)]
        assert _detectar_semanas_faltantes(comps) == []

    def test_semana_none_ignorada(self):
        comps = [_comp(semana=None), _comp(semana=1), _comp(semana=3)]
        faltantes = _detectar_semanas_faltantes(comps)
        assert 2 in faltantes

    def test_una_sola_semana_no_genera_faltantes(self):
        comps = [_comp(semana=5)]
        assert _detectar_semanas_faltantes(comps) == []


class TestCarpetaVacia:
    def test_alerta_carpeta_sin_comprobantes(self):
        resultado = auditar_alumno("Juan Perez", [])
        assert any(a.severidad == "warn" for a in resultado.alertas)
        assert resultado.comprobantes == []
