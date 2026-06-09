"""Tests para LocalSource: navegación, detección de subcarpeta COMPROBANTES, índice de pago."""
import pytest
from pathlib import Path

from src.sources.local_source import LocalSource
from src.services.analysis_service import _indice_pago, _extraer_semana


class TestLocalSourceNavegacion:
    def test_alumnos_en_raiz(self, tmp_path):
        (tmp_path / "Juan Perez").mkdir()
        (tmp_path / "Maria Lopez").mkdir()
        source = LocalSource(tmp_path)
        nombres = [f.name for f in source.list_student_folders()]
        assert "Juan Perez" in nombres
        assert "Maria Lopez" in nombres

    def test_alumnos_en_subcarpeta_comprobantes(self, tmp_path):
        comp = tmp_path / "COMPROBANTES"
        comp.mkdir()
        (comp / "Juan Perez").mkdir()
        (comp / "Maria Lopez").mkdir()
        source = LocalSource(tmp_path)
        nombres = [f.name for f in source.list_student_folders()]
        assert "Juan Perez" in nombres
        assert "Maria Lopez" in nombres

    def test_alumnos_en_subcarpeta_comprobante_sin_s(self, tmp_path):
        comp = tmp_path / "COMPROBANTE"
        comp.mkdir()
        (comp / "Ana Ruiz").mkdir()
        source = LocalSource(tmp_path)
        nombres = [f.name for f in source.list_student_folders()]
        assert "Ana Ruiz" in nombres

    def test_ignora_archivos_no_pdf(self, tmp_path):
        alumno = tmp_path / "Juan Perez"
        alumno.mkdir()
        (alumno / "semana1.pdf").write_bytes(b"%PDF-1.4")
        (alumno / "semana1.docx").write_bytes(b"word")
        (alumno / "semana1.png").write_bytes(b"img")
        source = LocalSource(tmp_path)
        folder = source.list_student_folders()[0]
        receipts = source.list_receipts(folder)
        assert len(receipts) == 1
        assert receipts[0].name == "semana1.pdf"

    def test_carpeta_vacia(self, tmp_path):
        (tmp_path / "Juan Perez").mkdir()
        source = LocalSource(tmp_path)
        folder = source.list_student_folders()[0]
        receipts = source.list_receipts(folder)
        assert receipts == []

    def test_read_bytes(self, tmp_path):
        alumno = tmp_path / "Juan Perez"
        alumno.mkdir()
        (alumno / "semana1.pdf").write_bytes(b"%PDF-test")
        source = LocalSource(tmp_path)
        folder = source.list_student_folders()[0]
        receipt = source.list_receipts(folder)[0]
        assert source.read_bytes(receipt) == b"%PDF-test"

    def test_link_for_es_ruta_absoluta(self, tmp_path):
        alumno = tmp_path / "Juan Perez"
        alumno.mkdir()
        (alumno / "semana1.pdf").write_bytes(b"%PDF")
        source = LocalSource(tmp_path)
        folder = source.list_student_folders()[0]
        receipt = source.list_receipts(folder)[0]
        link = source.link_for(receipt)
        assert Path(link).is_absolute()


class TestIndicePago:
    def test_archivo_sin_sufijo_es_pago_1(self):
        assert _indice_pago("semana19.pdf") == 1

    def test_sufijo_1_es_pago_2(self):
        assert _indice_pago("semana19 (1).pdf") == 2

    def test_sufijo_2_es_pago_3(self):
        assert _indice_pago("semana19 (2).pdf") == 3

    def test_extrae_semana_case_insensitive(self):
        assert _extraer_semana("SEMANA7.pdf") == 7
        assert _extraer_semana("Semana7.pdf") == 7
        assert _extraer_semana("semana 7.pdf") == 7

    def test_extrae_semana_none_si_no_hay(self):
        assert _extraer_semana("comprobante.pdf") is None
