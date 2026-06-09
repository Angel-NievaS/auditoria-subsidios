"""Orquesta: source -> navegar -> parsear -> auditar -> ResultadoAuditoria."""
import os
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Callable

from src.domain.auditor import auditar_alumno
from src.domain.models import Alerta, Comprobante, ResultadoAlumno, ResultadoAuditoria
from src.parsing.classifier import classify
from src.parsing.extractors.certificado_v1 import CertificadoV1Extractor
from src.parsing.extractors.certificado_v2 import CertificadoV2Extractor
from src.parsing.extractors.comprobante_ocr import ComprobanteOCRExtractor
from src.parsing.extractors.liquidacion import LiquidacionExtractor
from src.sources.base import ReceiptFile, ReceiptSource, StudentFolder

_EXTRACTORS = {
    "liquidacion": LiquidacionExtractor(),
    "comprobante_ocr": ComprobanteOCRExtractor(),
    "certificado_v1": CertificadoV1Extractor(),
    "certificado_v2": CertificadoV2Extractor(),
}

_MAX_WORKERS = os.cpu_count() or 4  # un hilo por núcleo disponible


def run_analysis(
    source: ReceiptSource,
    on_progress: Callable[[str, str, int, int], None] | None = None,
    cancelado: Callable[[], bool] | None = None,
) -> ResultadoAuditoria:
    """
    Procesa hasta _MAX_WORKERS alumnos en paralelo con ThreadPoolExecutor.

    on_progress(event, nombre, n_done, n_total)
      event="start"  → alumno comenzó a procesarse
      event="done"   → alumno terminó (n_done ya incluye este alumno)
    """
    carpeta_nombre = _nombre_raiz(source)
    alumnos_raw = source.list_student_folders()
    n_total = len(alumnos_raw)

    duplicados = _detectar_carpetas_duplicadas(alumnos_raw)
    resultados: list[ResultadoAlumno | None] = [None] * n_total

    lock = threading.Lock()
    n_done_ref = [0]

    def _procesar_uno(idx: int, folder: StudentFolder) -> tuple[int, ResultadoAlumno | None]:
        if cancelado and cancelado():
            return idx, None
        if on_progress:
            with lock:
                on_progress("start", folder.name, n_done_ref[0], n_total)
        try:
            receipts = source.list_receipts(folder)
            comprobantes = _procesar_receipts(source, folder, receipts)
            _rellenar_nombres_faltantes(comprobantes)
            resultado = auditar_alumno(folder.name, comprobantes, curso=folder.curso)
            if folder.name in duplicados:
                resultado.alertas.insert(0, Alerta("🟡", "warn",
                    f"Carpeta duplicada: '{folder.name}' aparece en más de una ruta"))
            # _imprimir_alertas(folder.name, resultado)  # traza desactivada
        except Exception as exc:
            resultado = ResultadoAlumno(
                nombre=folder.name,
                curso=folder.curso,
                alertas=[Alerta("🔴", "error", f"Error al procesar carpeta: {exc}")],
            )
            print(f"[ERROR] {folder.name}: {exc}")

        with lock:
            n_done_ref[0] += 1
            if on_progress:
                on_progress("done", folder.name, n_done_ref[0], n_total)

        return idx, resultado

    workers = max(1, min(_MAX_WORKERS, n_total))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_procesar_uno, i, folder)
            for i, folder in enumerate(alumnos_raw)
        ]
        for future in as_completed(futures):
            idx, resultado = future.result()
            if resultado is not None:
                resultados[idx] = resultado

    return ResultadoAuditoria(
        carpeta=carpeta_nombre,
        fecha=date.today().strftime("%d-%m-%Y"),
        alumnos=[r for r in resultados if r is not None],
    )


def _procesar_receipts(
    source: ReceiptSource,
    folder: StudentFolder,
    receipts: list[ReceiptFile],
) -> list[Comprobante]:
    """Por alumno: agrupar por (categoria, semana), ordenar parciales, extraer cada PDF."""
    por_grupo: dict[tuple[str, int | None], list[ReceiptFile]] = {}
    for r in receipts:
        key = (r.categoria, _extraer_semana(r.name))
        por_grupo.setdefault(key, []).append(r)

    comprobantes: list[Comprobante] = []
    # subsidio primero, luego cuidados; dentro de cada uno, ordenado por semana
    for (categoria, semana), archivos in sorted(
        por_grupo.items(),
        key=lambda x: (x[0][0] != "subsidio", x[0][1] is None, x[0][1] or 0),
    ):
        archivos_ord = sorted(archivos, key=lambda r: _indice_pago(r.name))
        for idx, receipt in enumerate(archivos_ord, start=1):
            c = _extraer_receipt(source, receipt)
            c.archivo = receipt.name
            c.semana = semana
            c.indice_pago = idx
            c.categoria = categoria
            c.link = source.link_for(receipt)
            comprobantes.append(c)

    return comprobantes


def _extraer_receipt(source: ReceiptSource, receipt: ReceiptFile) -> Comprobante:
    """Lee, clasifica y extrae. Captura errores sin romper el análisis."""
    try:
        pdf_bytes = source.read_bytes(receipt)
        link = source.link_for(receipt)
        doc_type = classify(pdf_bytes)
        extractor = _EXTRACTORS.get(doc_type)
        if extractor:
            return extractor.extract(pdf_bytes, link)
        print(f"[ERROR] Formato desconocido: {receipt.name}")
        return _comprobante_desconocido(receipt.name, link)
    except Exception as exc:
        print(f"[ERROR] Excepción procesando {receipt.name}: {exc}")
        return _comprobante_error(receipt.name, source.link_for(receipt), str(exc))


def _comprobante_desconocido(archivo: str, link: str) -> Comprobante:
    return Comprobante(
        archivo=archivo, semana=None, indice_pago=1,
        tipo_documento="desconocido",
        nombre_beneficiario=None, rut_beneficiario=None, monto=None,
        tipo_cuenta=None, numero_cuenta=None, numero_operacion=None,
        banco=None, fecha_pago=None, estado_pago=None,
        datos_incompletos=True, fuente="manual",
        nota="Formato de documento no reconocido — revisar manualmente",
        link=link,
        alertas=[Alerta("⚠️", "warn", "Formato desconocido — revisar manualmente")],
    )


def _comprobante_error(archivo: str, link: str, detalle: str) -> Comprobante:
    return Comprobante(
        archivo=archivo, semana=None, indice_pago=1,
        tipo_documento="error",
        nombre_beneficiario=None, rut_beneficiario=None, monto=None,
        tipo_cuenta=None, numero_cuenta=None, numero_operacion=None,
        banco=None, fecha_pago=None, estado_pago=None,
        datos_incompletos=True, fuente="manual",
        nota=f"Error al procesar: {detalle}",
        link=link,
        alertas=[Alerta("⚠️", "warn", f"Error al procesar: {detalle}")],
    )


def _rellenar_nombres_faltantes(comprobantes: list[Comprobante]) -> None:
    """
    Si un comprobante no tiene nombre pero sí RUT, y otro comprobante del mismo alumno
    tiene ese mismo RUT con nombre (ej: liquidación), copia el nombre.
    """
    rut_a_nombre: dict[str, str] = {
        c.rut_beneficiario: c.nombre_beneficiario
        for c in comprobantes
        if c.rut_beneficiario and c.nombre_beneficiario
    }
    for c in comprobantes:
        if c.nombre_beneficiario is None and c.rut_beneficiario in rut_a_nombre:
            c.nombre_beneficiario = rut_a_nombre[c.rut_beneficiario]


def _extraer_semana(filename: str) -> int | None:
    # Acepta "SEMANA" y variantes con error tipográfico como "SAMANA"
    m = re.search(r"s[ae]mana\s*(\d+)", filename, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _indice_pago(filename: str) -> int:
    """Determina el índice de pago dentro de una semana.
    semana19.pdf → 1
    semana19 (1).pdf → 2   (formato con paréntesis)
    SAMANA24.1 / SAMANA24.1.pdf → 2   (formato con punto)
    """
    # Formato (N)
    m = re.search(r"\((\d+)\)", filename)
    if m:
        return int(m.group(1)) + 1
    # Formato .N al final del nombre (antes de extensión opcional)
    m = re.search(r"\.(\d+)(?:\.\w+)?$", filename, re.IGNORECASE)
    if m:
        return int(m.group(1)) + 1
    return 1


def _detectar_carpetas_duplicadas(folders: list[StudentFolder]) -> set[str]:
    """Retorna nombres de carpetas que aparecen más de una vez dentro del mismo curso."""
    conteo: dict[tuple[str, str], int] = {}
    for f in folders:
        key = (_normalizar(f.name), f.curso)
        conteo[key] = conteo.get(key, 0) + 1
    duplicados = {(norm, curso) for (norm, curso), v in conteo.items() if v > 1}
    return {f.name for f in folders if (_normalizar(f.name), f.curso) in duplicados}


def _normalizar(nombre: str) -> str:
    nfd = unicodedata.normalize("NFD", nombre)
    sin_tildes = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _imprimir_alertas(nombre: str, resultado) -> None:
    """Imprime en consola las alertas error/warn del alumno y sus comprobantes."""
    alertas_alumno = [a for a in resultado.alertas if a.severidad != "info"]
    alertas_comp = [
        (c.archivo, a)
        for c in resultado.comprobantes
        for a in c.alertas
        if a.severidad != "info"
    ]
    if not alertas_alumno and not alertas_comp:
        return
    sep = "─" * 60
    print(f"\n┌{sep}")
    print(f"│ {nombre}")
    print(f"├{sep}")
    for a in alertas_alumno:
        print(f"│ {a.icono} {a.mensaje}")
    for archivo, a in alertas_comp:
        print(f"│ {a.icono} [{archivo}] {a.mensaje}")
    print(f"└{sep}")


def _nombre_raiz(source: ReceiptSource) -> str:
    """Intenta obtener el nombre de la carpeta raíz desde LocalSource."""
    try:
        from src.sources.local_source import LocalSource
        if isinstance(source, LocalSource):
            return source._root.name
    except Exception:
        pass
    return "AUDITORIA"
