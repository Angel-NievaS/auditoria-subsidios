"""Reglas de auditoría. Opera solo sobre modelos de dominio; sin I/O."""
import re
import unicodedata

from .models import Alerta, Comprobante, ResultadoAlumno


def auditar_alumno(
    nombre_carpeta: str,
    comprobantes: list[Comprobante],
    curso: str = "",
    num_semanas: int | None = None,
) -> ResultadoAlumno:
    """Aplica todas las reglas y retorna ResultadoAlumno con alertas y semanas faltantes."""
    alertas_alumno: list[Alerta] = []

    if not comprobantes:
        alertas_alumno.append(Alerta("🟡", "warn", "Carpeta de alumno sin comprobantes PDF"))
        return ResultadoAlumno(nombre=nombre_carpeta, comprobantes=[], alertas=alertas_alumno)

    # Alertas a nivel de alumno
    alertas_alumno.extend(_detectar_rut_inconsistente(comprobantes))

    # Alertas por comprobante
    for c in comprobantes:
        if num_semanas is not None and c.semana is not None and c.semana > num_semanas:
            c.alertas.append(Alerta("🟡", "warn",
                f"Semana {c.semana} excede las {num_semanas} semanas del curso — no se considera en la revisión"))
        if c.monto is None:
            c.alertas.append(Alerta("🟡", "warn", "Monto no encontrado — revisar manualmente"))
        c.alertas.extend(_alertas_nombre_no_coincide(nombre_carpeta, c))
        c.alertas.extend(_alertas_duplicado(c, comprobantes))

    semanas_faltantes: list[int] = []
    for cat, label in (("subsidio", "Subsidio"), ("cuidados", "Cuidados")):
        comps_cat = [c for c in comprobantes if c.categoria == cat]
        faltantes = _detectar_semanas_faltantes(comps_cat, num_semanas)
        if faltantes:
            semanas_faltantes.extend(faltantes)
            alertas_alumno.append(
                Alerta("⚪", "info",
                       f"Semanas faltantes ({label}): {', '.join(str(s) for s in faltantes)}")
            )

    return ResultadoAlumno(
        nombre=nombre_carpeta,
        curso=curso,
        comprobantes=comprobantes,
        alertas=alertas_alumno,
        semanas_faltantes=semanas_faltantes,
    )


def _detectar_rut_inconsistente(comprobantes: list[Comprobante]) -> list[Alerta]:
    """🔴 RUT distinto entre comprobantes del mismo alumno."""
    ruts = {c.rut_beneficiario for c in comprobantes if c.rut_beneficiario}
    if len(ruts) > 1:
        return [Alerta("🔴", "error", f"RUTs distintos en comprobantes del alumno: {', '.join(sorted(ruts))}")]
    return []


def _alertas_nombre_no_coincide(nombre_carpeta: str, c: Comprobante) -> list[Alerta]:
    """🔴 Nombre en PDF no coincide con nombre de carpeta."""
    if not c.nombre_beneficiario:
        return []
    if not _nombres_coinciden(c.nombre_beneficiario, nombre_carpeta):
        return [Alerta("🔴", "error",
                       f"Nombre en PDF '{c.nombre_beneficiario}' no coincide con carpeta '{nombre_carpeta}'")]
    return []


def _alertas_duplicado(c: Comprobante, todos: list[Comprobante]) -> list[Alerta]:
    """🟡 Mismo semana + monto + RUT + fecha (posible duplicado, requiere revisión)."""
    alertas = []
    for otro in todos:
        if otro is c:
            continue
        if (
            c.semana is not None and c.semana == otro.semana
            and c.monto is not None and c.monto == otro.monto
            and c.rut_beneficiario and c.rut_beneficiario == otro.rut_beneficiario
            and c.fecha_pago and c.fecha_pago == otro.fecha_pago
        ):
            alertas.append(Alerta("🟡", "warn",
                                  f"Posible duplicado con {otro.archivo} (semana {c.semana}, ${c.monto})"))
            break
    return alertas


def _detectar_semanas_faltantes(
    comprobantes: list[Comprobante],
    num_semanas: int | None = None,
) -> list[int]:
    """⚪ Semanas sin comprobante.

    Con num_semanas: se revisa el rango completo 1..num_semanas (las semanas
    que exceden el curso se ignoran). Sin num_semanas: huecos entre la mínima
    y la máxima presentes.
    """
    semanas = {c.semana for c in comprobantes if c.semana is not None}
    if num_semanas is not None:
        semanas = {s for s in semanas if s <= num_semanas}
        if not semanas:
            return []
        return [s for s in range(1, num_semanas + 1) if s not in semanas]
    if len(semanas) < 2:
        return []
    rango = range(min(semanas), max(semanas) + 1)
    return [s for s in rango if s not in semanas]


def _normalizar_nombre(nombre: str) -> str:
    """Quita diacríticos, pasa a mayúsculas, colapsa espacios."""
    nfd = unicodedata.normalize("NFD", nombre)
    sin_tildes = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_tildes).strip().upper()


def _tokens_significativos(nombre: str) -> set[str]:
    """Palabras de más de 2 caracteres (excluye artículos y preposiciones cortas)."""
    EXCLUIR = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "E"}
    return {t for t in _normalizar_nombre(nombre).split() if len(t) > 2 and t not in EXCLUIR}


def _nombres_coinciden(nombre_pdf: str, nombre_carpeta: str) -> bool:
    """Coincide si comparten ≥2 tokens significativos o ≥50% de los tokens del nombre del PDF."""
    tokens_pdf = _tokens_significativos(nombre_pdf)
    tokens_carpeta = _tokens_significativos(nombre_carpeta)
    if not tokens_pdf:
        return True  # sin info suficiente, no alertar
    comunes = tokens_pdf & tokens_carpeta
    if len(comunes) >= 2:
        return True
    if len(comunes) / len(tokens_pdf) >= 0.5:
        return True
    return False
