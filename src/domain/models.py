"""Modelo de dominio. Sin dependencias de Flask ni rutas locales."""
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Alerta:
    icono: str       # 🔴 / 🟡 / 🔵 / ⚠️
    severidad: Literal["error", "warn", "info"]
    mensaje: str


@dataclass
class Comprobante:
    archivo: str
    semana: int | None
    indice_pago: int                   # 1 = primer pago de la semana, 2 = segundo, …
    tipo_documento: str
    nombre_beneficiario: str | None
    rut_beneficiario: str | None
    monto: int | None
    tipo_cuenta: str | None
    numero_cuenta: str | None
    numero_operacion: str | None
    banco: str | None
    fecha_pago: str | None             # DD-MM-YYYY
    estado_pago: str | None
    datos_incompletos: bool
    fuente: Literal["texto", "ocr", "manual"]
    nota: str | None
    link: str
    categoria: str = "subsidio"  # "subsidio" | "cuidados"
    alertas: list[Alerta] = field(default_factory=list)


@dataclass
class ResultadoAlumno:
    nombre: str
    curso: str = ""  # código RTD del curso al que pertenece
    comprobantes: list[Comprobante] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    semanas_faltantes: list[int] = field(default_factory=list)


@dataclass
class ResultadoAuditoria:
    carpeta: str
    fecha: str                         # DD-MM-YYYY
    alumnos: list[ResultadoAlumno] = field(default_factory=list)
    num_semanas: int | None = None     # semanas del curso indicadas por el usuario
